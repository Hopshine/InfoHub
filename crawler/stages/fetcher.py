"""微信文章内容获取阶段"""
from typing import Optional
from utils.logger import setup_logger

logger = setup_logger('stage_fetcher')


class ContentFetchStage:
    """微信文章内容获取"""

    WX_HEADERS = {
        'Referer': 'https://mp.weixin.qq.com/',
        'Sec-Fetch-Site': 'same-origin',
    }

    def __init__(self, session_mgr):
        self.session_mgr = session_mgr

    async def fetch(self, url: str) -> Optional[str]:
        """获取微信文章HTML内容"""
        session = await self.session_mgr.get_session()
        try:
            async with session.get(url, headers=self.WX_HEADERS) as resp:
                if resp.status != 200:
                    logger.warning(f"获取文章失败 [{resp.status}]: {url[:60]}")
                    return None
                html = await resp.text()
                if self.validate_response(html):
                    return html
                logger.warning(f"文章内容无效: {url[:60]}")
                return None
        except Exception as e:
            logger.error(f"获取文章异常: {e}")
            return None

    @staticmethod
    def validate_response(html: str) -> bool:
        """验证获取到的内容是否是有效的微信文章"""
        if not html:
            return False
        if len(html) < 500:
            return False
        indicators = ['js_content', 'rich_media_content', 'activity-detail']
        return any(ind in html for ind in indicators)
