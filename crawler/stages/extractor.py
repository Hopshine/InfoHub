"""BeautifulSoup内容提取阶段"""
import re
from bs4 import BeautifulSoup
from typing import Dict, Optional
from utils.logger import setup_logger

logger = setup_logger('stage_extractor')


class ExtractorStage:
    """微信文章内容提取"""

    @staticmethod
    def extract(html: str, url: str = '') -> Optional[Dict]:
        """从微信文章HTML提取结构化数据"""
        if not html:
            return None

        try:
            soup = BeautifulSoup(html, 'lxml')
            article = {}

            # 标题
            title_tag = (
                soup.select_one('#activity-name') or
                soup.select_one('h1.rich_media_title') or
                soup.select_one('h2.rich_media_title')
            )
            article['title'] = title_tag.get_text(strip=True) if title_tag else ''

            # 作者
            author_tag = (
                soup.select_one('#js_author_name') or
                soup.select_one('span.rich_media_meta_text')
            )
            article['author'] = author_tag.get_text(strip=True) if author_tag else ''

            # 公众号名称
            account_tag = (
                soup.select_one('#js_name') or
                soup.select_one('a.rich_media_meta_link')
            )
            article['account_name'] = account_tag.get_text(strip=True) if account_tag else ''

            # 发布时间
            publish_time = ''
            # 尝试从script中提取
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'publish_time' in script.string:
                    match = re.search(r'var\s+publish_time\s*=\s*["\'](\d+)["\']', script.string)
                    if match:
                        import datetime
                        ts = int(match.group(1))
                        publish_time = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                        break
            # 备选：从页面元素提取
            if not publish_time:
                time_tag = soup.select_one('#publish_time') or soup.select_one('em.rich_media_meta_text')
                if time_tag:
                    publish_time = time_tag.get_text(strip=True)
            article['publish_time'] = publish_time

            # 正文内容
            content_tag = (
                soup.select_one('#js_content') or
                soup.select_one('div.rich_media_content')
            )
            if content_tag:
                # 移除script和style
                for tag in content_tag.find_all(['script', 'style']):
                    tag.decompose()
                article['content'] = content_tag.get_text(separator='\n', strip=True)
            else:
                article['content'] = ''

            article['url'] = url

            # 验证：至少有标题
            if not article['title']:
                logger.warning(f"未能提取标题: {url}")
                return None

            logger.info(f"提取成功: {article['title'][:40]}")
            return article

        except Exception as e:
            logger.error(f"内容提取失败: {e}")
            return None
