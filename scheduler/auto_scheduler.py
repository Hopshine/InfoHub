"""
自动调度器 - 整合热点采集、文章生成、自动发布的完整流程
支持定时执行和手动触发
"""
import time
import threading
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from utils.logger import setup_logger
from config import Config
from storage.database import Database
from collector.trending_collector import TrendingCollector
from generator.article_generator import ArticleGenerator
from publisher.wechat_publisher import WeChatPublisher

logger = setup_logger('scheduler')


class AutoScheduler:
    """自动调度器：采集 -> 生成 -> 发布"""

    def __init__(self, db: Database):
        self.db = db
        self.collector = TrendingCollector()
        self.generator = ArticleGenerator()
        self._running = False
        self._thread = None

    def collect_hotnews(self) -> Dict:
        """采集热点新闻并保存"""
        batch_id = datetime.now().strftime('%Y%m%d%H%M%S') + '_' + uuid.uuid4().hex[:6]
        results = {'batch_id': batch_id, 'total': 0, 'platforms': {}}

        logger.info("开始采集热点新闻...")
        all_data = self.collector.collect_all()

        for platform, items in all_data.items():
            count = len(items) if items else 0
            if items:
                self.db.save_hotnews(platform, items, batch_id)
            results['platforms'][platform] = count
            results['total'] += count
            logger.info(f"  {platform}: {count}条")

        logger.info(f"热点采集完成，共{results['total']}条")
        return results

    def generate_articles(self, count: int = None,
                          style: str = None) -> List[Dict]:
        """从未处理的热点新闻生成文章

        Args:
            count: 生成数量，默认从配置读取
            style: 文章风格(news/comment/deep)，默认从配置读取
        """
        count = count or 5
        style = style or Config.ARTICLE_STYLE

        # 获取未处理的热点新闻
        hotnews_list = self.db.get_unprocessed_hotnews(limit=count)
        if not hotnews_list:
            logger.info("没有未处理的热点新闻")
            return []

        logger.info(f"开始生成文章，共{len(hotnews_list)}条热点，风格: {style}")
        generated = []

        for news in hotnews_list:
            article_id = self.generator.generate_and_save(
                self.db, news, style)
            if article_id:
                article = self.db.get_generated_article(article_id)
                if article:
                    generated.append(article)
            time.sleep(1)  # 避免API限流

        logger.info(f"文章生成完成，成功{len(generated)}篇")
        return generated

    def publish_drafts(self, article_ids: List[int] = None,
                       publish_type: str = 'draft') -> List[Dict]:
        """发布草稿文章到微信公众号

        Args:
            article_ids: 指定文章ID列表，为空则发布所有草稿
            publish_type: 'draft'(存草稿) 或 'publish'(直接发布)
        """
        Config.validate_wechat()
        publisher = WeChatPublisher()

        if article_ids:
            articles = [
                self.db.get_generated_article(aid) for aid in article_ids
            ]
            articles = [a for a in articles if a]
        else:
            articles = self.db.get_draft_articles(limit=10)

        if not articles:
            logger.info("没有待发布的文章")
            return []

        logger.info(f"开始发布{len(articles)}篇文章，方式: {publish_type}")
        results = []

        for article in articles:
            result = publisher.publish_article(
                article, db=self.db, publish_type=publish_type)
            results.append(result)
            logger.info(
                f"  [{result['status']}] {article['title']}")
            time.sleep(1)

        success = sum(1 for r in results if r['status'] != 'failed')
        logger.info(f"发布完成，成功{success}/{len(results)}篇")
        return results

    def run_full_pipeline(self, generate_count: int = None,
                          style: str = None,
                          auto_publish: bool = None) -> Dict:
        """执行完整流程：采集 -> 生成 -> 发布

        Args:
            generate_count: 生成文章数量
            style: 文章风格
            auto_publish: 是否自动发布
        """
        auto_publish = auto_publish if auto_publish is not None \
            else Config.SCHEDULER_AUTO_PUBLISH

        logger.info("=" * 50)
        logger.info("开始执行完整流程")
        logger.info("=" * 50)

        result = {
            'started_at': datetime.now().isoformat(),
            'collect': {},
            'generate': [],
            'publish': [],
        }

        # 1. 采集热点
        result['collect'] = self.collect_hotnews()

        # 2. 生成文章
        time.sleep(2)
        generated = self.generate_articles(
            count=generate_count, style=style)
        result['generate'] = [
            {'id': a['id'], 'title': a['title']} for a in generated
        ]

        # 3. 自动发布（如果开启）
        if auto_publish and generated:
            time.sleep(2)
            article_ids = [a['id'] for a in generated]
            result['publish'] = self.publish_drafts(
                article_ids=article_ids, publish_type='draft')

        result['finished_at'] = datetime.now().isoformat()
        logger.info("完整流程执行完毕")
        return result

    def start(self, interval_minutes: int = None):
        """启动定时调度"""
        if self._running:
            logger.warning("调度器已在运行")
            return

        interval = (interval_minutes or 60) * 60
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, args=(interval,), daemon=True)
        self._thread.start()
        logger.info(f"自动调度已启动，间隔{interval // 60}分钟")

    def stop(self):
        """停止定时调度"""
        self._running = False
        logger.info("自动调度已停止")

    def _run_loop(self, interval: int):
        """定时循环"""
        self.run_full_pipeline()
        while self._running:
            time.sleep(interval)
            if self._running:
                self.run_full_pipeline()

    @property
    def status(self) -> Dict:
        return {
            'running': self._running,
            'auto_publish': Config.SCHEDULER_AUTO_PUBLISH,
        }
