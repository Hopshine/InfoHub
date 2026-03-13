"""跳转链接解析阶段"""
import re
from typing import Optional
from utils.logger import setup_logger

logger = setup_logger('stage_resolver')


class RedirectResolverStage:
    """解析搜狗跳转链接，获取真实微信文章URL"""

    def __init__(self, session_mgr):
        self.session_mgr = session_mgr

    async def resolve(self, url: str) -> Optional[str]:
        """访问跳转链接，解析出真实微信文章URL"""
        if not self.is_sogou_redirect(url):
            return url

        session = await self.session_mgr.get_session()
        try:
            async with session.get(
                url,
                headers={'Referer': self.session_mgr.SEARCH_URL},
                allow_redirects=False
            ) as resp:
                # 检查30x重定向
                if resp.status in (301, 302):
                    location = resp.headers.get('Location', '')
                    if 'mp.weixin.qq.com' in location:
                        return location

                html = await resp.text()
                return self.extract_real_url(html) or url
        except Exception as e:
            logger.error(f"解析跳转链接失败: {e}")
            return url

    @staticmethod
    def extract_real_url(html: str) -> Optional[str]:
        """从跳转页面HTML中提取真实URL

        搜狗跳转页面通常包含JS代码拼接真实URL
        """
        if not html:
            return None

        # 尝试拼接 url += 'xxx' 模式
        url_parts = []
        for match in re.finditer(r"url\s*\+?=\s*['\"]([^'\"]*)['\"]", html):
            url_parts.append(match.group(1))

        if url_parts:
            full_url = ''.join(url_parts)
            if 'mp.weixin.qq.com' in full_url:
                logger.debug(f"JS拼接提取URL: {full_url[:80]}...")
                return full_url

        # 方法2: 直接匹配微信文章URL
        wx_pattern = r'(https?://mp\.weixin\.qq\.com/s[^\s\'"<>]+)'
        match = re.search(wx_pattern, html)
        if match:
            url = match.group(1)
            logger.debug(f"正则提取URL: {url[:80]}...")
            return url

        # 方法3: meta refresh
        meta_pattern = r'<meta[^>]+url=([^\s\'"<>]+)'
        match = re.search(meta_pattern, html, re.IGNORECASE)
        if match:
            return match.group(1)

        logger.warning("未能从跳转页面提取真实URL")
        return None

    @staticmethod
    def is_sogou_redirect(url: str) -> bool:
        """判断是否是搜狗跳转链接"""
        return 'weixin.sogou.com/link' in url or ('sogou.com' in url and 'mp.weixin.qq.com' not in url)
