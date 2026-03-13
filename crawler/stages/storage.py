"""SQLite存储阶段"""
from typing import Dict, Optional
from storage.database import Database
from crawler.dedup import DeduplicationFilter
from utils.logger import setup_logger

logger = setup_logger('stage_storage')


class StorageStage:
    """文章存储阶段"""

    def __init__(self, db: Database, dedup: DeduplicationFilter):
        self.db = db
        self.dedup = dedup

    def save(self, article: Dict) -> Optional[int]:
        """保存文章到数据库

        Returns:
            article_id if saved, None if duplicate or failed
        """
        url = article.get('url', '')
        title = article.get('title', '')

        # URL去重
        if url and self.db.article_exists(url):
            logger.info(f"URL已存在，跳过: {title[:30]}")
            return None

        # 内容指纹
        content = article.get('content', '')
        if content:
            content_hash = self.dedup.content_hash(content)
            article['content_hash'] = content_hash

            # 内容去重
            if self.db.article_exists_by_hash(content_hash):
                logger.info(f"内容指纹重复，跳过: {title[:30]}")
                return None

        article['source'] = 'crawler'

        article_id = self.db.insert_article(article)
        if article_id:
            logger.info(f"保存成功 [ID={article_id}]: {title[:30]}")
        else:
            logger.warning(f"保存失败（可能重复）: {title[:30]}")

        return article_id
