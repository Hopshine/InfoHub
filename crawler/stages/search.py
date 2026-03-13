"""搜狗微信搜索阶段"""
import re
from bs4 import BeautifulSoup
from typing import List, Dict
from utils.logger import setup_logger

logger = setup_logger('stage_search')


class SogouSearchStage:
    """搜狗微信搜索结果解析"""

    def __init__(self, session_mgr):
        self.session_mgr = session_mgr

    async def search(self, keyword: str, max_results: int = 10) -> List[Dict]:
        """执行搜狗微信搜索并返回文章列表"""
        session = await self.session_mgr.get_session()
        params = {
            'type': '2',
            'query': keyword,
            'ie': 'utf8',
            's_from': 'input',
        }

        try:
            async with session.get(
                self.session_mgr.SEARCH_URL,
                params=params,
                headers={'Referer': self.session_mgr.BASE_URL}
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"搜索请求失败: {resp.status}")
                    return []
                html = await resp.text()
        except Exception as e:
            logger.error(f"搜索请求异常: {e}")
            return []

        if self.check_captcha(html):
            logger.warning("遇到验证码，搜索中止")
            return []

        articles = self.parse_search_results(html)
        return articles[:max_results]

    @staticmethod
    def parse_search_results(html: str) -> List[Dict]:
        """解析搜狗搜索结果页面HTML，提取文章列表"""
        articles = []
        if not html:
            return articles

        soup = BeautifulSoup(html, 'lxml')
        items = soup.select('div.txt-box') or soup.select('ul.news-list > li')

        for item in items:
            try:
                article = {}

                # 标题和链接
                title_tag = item.select_one('h3 a') or item.select_one('a')
                if not title_tag:
                    continue

                article['title'] = title_tag.get_text(strip=True)
                article['url'] = title_tag.get('href', '')

                # 补全URL
                if article['url'] and not article['url'].startswith('http'):
                    article['url'] = 'https://weixin.sogou.com' + article['url']

                # 摘要
                summary_tag = item.select_one('p.txt-info') or item.select_one('p')
                if summary_tag:
                    article['summary'] = summary_tag.get_text(strip=True)

                # 公众号名称
                account_tag = item.select_one('a.account') or item.select_one('div.s-p a')
                if account_tag:
                    article['account_name'] = account_tag.get_text(strip=True)

                # 发布时间
                time_tag = item.select_one('span.s2') or item.select_one('div.s-p span')
                if time_tag:
                    time_text = time_tag.get_text(strip=True)
                    article['publish_time'] = time_text

                if article.get('title') and article.get('url'):
                    articles.append(article)

            except Exception as e:
                logger.warning(f"解析搜索结果项失败: {e}")
                continue

        logger.info(f"解析到 {len(articles)} 条搜索结果")
        return articles

    @staticmethod
    def check_captcha(html: str) -> bool:
        """检查是否遇到验证码"""
        if not html:
            return False
        return '请输入验证码' in html or 'antispider' in html.lower()
