"""
Chrome Cookie提取器 - 从本地Chrome浏览器提取cookies用于Playwright
支持Windows DPAPI + AES-GCM解密

使用方式:
  1. 关闭Chrome浏览器
  2. 运行: python -m crawler.chrome_cookies
  3. 重新打开Chrome
  cookies会被导出到 config/chrome_cookies.json，后续采集自动使用
"""
import os
import json
import shutil
import sqlite3
import base64
import tempfile
from typing import List, Dict, Optional
from utils.logger import setup_logger

logger = setup_logger('chrome_cookies')

COOKIES_EXPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'config', 'chrome_cookies.json'
)

# Windows专用
try:
    import ctypes
    import ctypes.wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ('cbData', ctypes.wintypes.DWORD),
            ('pbData', ctypes.POINTER(ctypes.c_char))
        ]

    def _dpapi_decrypt(encrypted: bytes) -> bytes:
        """使用Windows DPAPI解密"""
        blob_in = DATA_BLOB(len(encrypted), ctypes.create_string_buffer(encrypted, len(encrypted)))
        blob_out = DATA_BLOB()

        if ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        ):
            data = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return data
        raise Exception("DPAPI解密失败")

    HAS_DPAPI = True
except Exception:
    HAS_DPAPI = False


def _get_chrome_user_data_dir() -> str:
    """获取Chrome用户数据目录"""
    return os.path.join(os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data')


def _get_encryption_key() -> Optional[bytes]:
    """从Chrome Local State获取AES加密密钥"""
    local_state_path = os.path.join(_get_chrome_user_data_dir(), 'Local State')
    if not os.path.exists(local_state_path):
        return None

    with open(local_state_path, 'r', encoding='utf-8') as f:
        local_state = json.load(f)

    encrypted_key = base64.b64decode(local_state['os_crypt']['encrypted_key'])
    # 去掉 'DPAPI' 前缀 (5字节)
    encrypted_key = encrypted_key[5:]
    return _dpapi_decrypt(encrypted_key)


def _decrypt_cookie_value(encrypted_value: bytes, key: bytes) -> str:
    """解密Chrome cookie值（AES-256-GCM）"""
    if not encrypted_value:
        return ''

    # v10/v20 前缀表示使用AES-GCM加密
    if encrypted_value[:3] in (b'v10', b'v20'):
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            nonce = encrypted_value[3:15]
            ciphertext = encrypted_value[15:]
            aesgcm = AESGCM(key)
            return aesgcm.decrypt(nonce, ciphertext, None).decode('utf-8')
        except ImportError:
            logger.error("需要安装cryptography库: pip install cryptography")
            return ''
        except Exception as e:
            logger.debug(f"AES解密失败: {e}")
            return ''

    # 旧版DPAPI加密
    try:
        return _dpapi_decrypt(encrypted_value).decode('utf-8')
    except Exception:
        return ''


def get_chrome_cookies(domain: str, profile: str = 'Default') -> List[Dict]:
    """
    从Chrome浏览器提取指定域名的cookies

    Args:
        domain: 域名（如 '.zhihu.com'）
        profile: Chrome配置文件名，默认 'Default'

    Returns:
        Playwright格式的cookie列表
    """
    if not HAS_DPAPI:
        logger.warning("当前平台不支持DPAPI，无法提取Chrome cookies")
        return []

    # Cookie数据库路径
    cookie_db = os.path.join(
        _get_chrome_user_data_dir(), profile, 'Network', 'Cookies'
    )
    if not os.path.exists(cookie_db):
        # 旧版Chrome路径
        cookie_db = os.path.join(
            _get_chrome_user_data_dir(), profile, 'Cookies'
        )

    if not os.path.exists(cookie_db):
        logger.error(f"Chrome Cookie数据库不存在: {cookie_db}")
        return []

    # 复制数据库（Chrome运行时会锁定原文件）
    tmp_db = os.path.join(tempfile.gettempdir(), 'chrome_cookies_tmp.db')
    try:
        shutil.copy2(cookie_db, tmp_db)
    except PermissionError:
        # Chrome正在运行，用二进制读取绕过文件锁
        try:
            with open(cookie_db, 'rb') as src:
                data = src.read()
            with open(tmp_db, 'wb') as dst:
                dst.write(data)
        except Exception as e:
            logger.error(f"读取Cookie数据库失败: {e}")
            return []
    except Exception as e:
        logger.error(f"复制Cookie数据库失败: {e}")
        return []

    # 获取加密密钥
    key = _get_encryption_key()
    if not key:
        logger.error("无法获取Chrome加密密钥")
        os.remove(tmp_db)
        return []

    cookies = []
    try:
        conn = sqlite3.connect(tmp_db)
        conn.text_factory = bytes  # 防止SQLite尝试解码二进制数据
        cursor = conn.cursor()

        # 查询指定域名的cookies（参数必须是bytes）
        cursor.execute(
            'SELECT host_key, name, path, encrypted_value, is_secure, '
            'is_httponly, expires_utc, samesite '
            'FROM cookies WHERE host_key LIKE ?',
            (f'%{domain}%'.encode('utf-8'),)
        )

        for row in cursor.fetchall():
            host_key, name, path, encrypted_value, is_secure, \
                is_httponly, expires_utc, samesite = row

            # 解码文本字段
            try:
                host_key = host_key.decode('utf-8') if isinstance(host_key, bytes) else host_key
                name = name.decode('utf-8') if isinstance(name, bytes) else name
                path = path.decode('utf-8') if isinstance(path, bytes) else path
            except Exception:
                continue

            value = _decrypt_cookie_value(encrypted_value, key)
            if not value:
                continue

            # 转换为Playwright cookie格式
            cookie = {
                'name': name,
                'value': value,
                'domain': host_key,
                'path': path,
                'secure': bool(is_secure),
                'httpOnly': bool(is_httponly),
            }

            # 设置过期时间
            if expires_utc > 0:
                # Chrome的时间戳是从1601年开始的微秒数
                # 转换为Unix时间戳（秒）
                cookie['expires'] = (expires_utc / 1000000) - 11644473600

            # sameSite映射
            samesite_map = {-1: 'None', 0: 'None', 1: 'Lax', 2: 'Strict'}
            cookie['sameSite'] = samesite_map.get(samesite, 'None')

            cookies.append(cookie)

        conn.close()
    except Exception as e:
        logger.error(f"读取Cookie数据库失败: {e}")
    finally:
        try:
            os.remove(tmp_db)
        except Exception:
            pass

    logger.info(f"从Chrome提取了 {len(cookies)} 个 {domain} cookies")
    return cookies


def get_zhihu_cookies() -> List[Dict]:
    """获取知乎的cookies"""
    return get_chrome_cookies('.zhihu.com')


def get_weibo_cookies() -> List[Dict]:
    """获取微博的cookies"""
    return get_chrome_cookies('.weibo.com')


def export_cookies(domains: List[str] = None):
    """
    导出Chrome cookies到JSON文件供Playwright使用

    Args:
        domains: 要导出的域名列表，默认导出知乎和微博
    """
    if domains is None:
        domains = ['.zhihu.com', '.weibo.com', '.baidu.com', '.toutiao.com']

    all_cookies = []
    for domain in domains:
        cookies = get_chrome_cookies(domain)
        all_cookies.extend(cookies)

    if not all_cookies:
        print("未提取到任何cookies，请确保Chrome已关闭且已登录目标网站")
        return

    os.makedirs(os.path.dirname(COOKIES_EXPORT_PATH), exist_ok=True)
    with open(COOKIES_EXPORT_PATH, 'w', encoding='utf-8') as f:
        json.dump(all_cookies, f, ensure_ascii=False, indent=2)

    # 统计
    domain_counts = {}
    for c in all_cookies:
        d = c['domain']
        domain_counts[d] = domain_counts.get(d, 0) + 1

    print(f"已导出 {len(all_cookies)} 个cookies到 {COOKIES_EXPORT_PATH}")
    for d, cnt in sorted(domain_counts.items()):
        print(f"  {d}: {cnt} 个")


def load_exported_cookies() -> List[Dict]:
    """加载已导出的cookies文件"""
    if not os.path.exists(COOKIES_EXPORT_PATH):
        return []
    try:
        with open(COOKIES_EXPORT_PATH, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        logger.info(f"从文件加载了 {len(cookies)} 个cookies")
        return cookies
    except Exception as e:
        logger.error(f"加载cookies文件失败: {e}")
        return []


if __name__ == '__main__':
    print("Chrome Cookie导出工具")
    print("请确保Chrome浏览器已关闭！")
    print()
    export_cookies()
