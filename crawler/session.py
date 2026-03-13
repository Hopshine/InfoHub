"""aiohttp会话管理 + 搜狗Cookie流程"""
import aiohttp
import asyncio
import random
from typing import Optional
from utils.logger import setup_logger

logger = setup_logger('crawler_session')


class SessionManager:
    """异步会话管理器"""

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }

    BASE_URL = 'https://weixin.sogou.com'
    SEARCH_URL = 'https://weixin.sogou.com/weixin'

    def __init__(self, timeout: int = 20):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None
        self._initialized = False

    async def get_session(self) -> aiohttp.ClientSession:
        """获取或创建会话"""
        if self._session is None or self._session.closed:
            jar = aiohttp.CookieJar(unsafe=True)
            self._session = aiohttp.ClientSession(
                headers=self.HEADERS,
                cookie_jar=jar,
                timeout=self.timeout
            )
        return self._session

    async def init_sogou_session(self):
        """初始化搜狗会话，访问首页获取Cookie"""
        session = await self.get_session()
        try:
            logger.info("初始化搜狗会话...")
            async with session.get(self.BASE_URL) as resp:
                if resp.status == 200:
                    logger.info(f"搜狗首页访问成功，Cookie数: {len(session.cookie_jar)}")
                    self._initialized = True
                else:
                    logger.warning(f"搜狗首页访问失败: {resp.status}")
            # 模拟真实用户延迟
            await asyncio.sleep(random.uniform(1, 2))
        except Exception as e:
            logger.error(f"初始化搜狗会话失败: {e}")

    @property
    def initialized(self) -> bool:
        return self._initialized

    async def close(self):
        """关闭会话"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            self._initialized = False
