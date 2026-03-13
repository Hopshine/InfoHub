"""异步爬虫引擎 - 编排采集流水线"""
import asyncio
import json
from typing import Dict, List, Optional, Callable
from config import Config
from utils.logger import setup_logger
from crawler.session import SessionManager
from crawler.rate_limiter import RateLimiter
from crawler.dedup import DeduplicationFilter

logger = setup_logger('crawl_engine')


class CrawlEngine:
    """异步爬虫引擎"""

    def __init__(self, db):
        self.db = db
        self.session_mgr = SessionManager(timeout=Config.CRAWL_REQUEST_TIMEOUT)
        self.rate_limiter = RateLimiter(rate=Config.CRAWL_RATE_LIMIT, burst=5)
        self.dedup = DeduplicationFilter(hamming_threshold=Config.CRAWL_DEDUP_HAMMING)
        self.semaphore = asyncio.Semaphore(Config.CRAWL_CONCURRENCY)

    async def close(self):
        await self.session_mgr.close()

    async def crawl_search(self, keyword: str, max_results: int, job_id: str,
                           progress, cancel_event: asyncio.Event):
        """搜索采集主流程"""
        from crawler.stages.search import SogouSearchStage
        from crawler.stages.resolver import RedirectResolverStage
        from crawler.stages.fetcher import ContentFetchStage
        from crawler.stages.extractor import ExtractorStage
        from crawler.stages.storage import StorageStage

        try:
            # 初始化会话
            progress.set_step('初始化搜狗会话...')
            self._push_progress(job_id, progress)
            await self.session_mgr.init_sogou_session()

            # 搜索
            progress.set_step('搜索文章中...')
            self._push_progress(job_id, progress)
            search_stage = SogouSearchStage(self.session_mgr)
            articles = await search_stage.search(keyword, max_results)

            if not articles:
                progress.set_step('未搜索到文章')
                progress.total = 0
                return

            progress.total = len(articles)
            progress.set_step(f'搜索到 {len(articles)} 篇文章，开始采集...')
            self._push_progress(job_id, progress)

            # 并行处理每篇文章
            resolver = RedirectResolverStage(self.session_mgr)
            fetcher = ContentFetchStage(self.session_mgr)
            extractor = ExtractorStage()
            storage = StorageStage(self.db, self.dedup)

            tasks = []
            for article in articles:
                task = asyncio.create_task(
                    self._process_article(
                        article, resolver, fetcher, extractor, storage,
                        job_id, progress, cancel_event
                    )
                )
                tasks.append(task)

            await asyncio.gather(*tasks, return_exceptions=True)

        finally:
            await self.close()

    async def crawl_urls(self, urls: List[str], job_id: str,
                         progress, cancel_event: asyncio.Event):
        """批量URL采集"""
        from crawler.stages.fetcher import ContentFetchStage
        from crawler.stages.extractor import ExtractorStage
        from crawler.stages.storage import StorageStage

        try:
            progress.total = len(urls)
            progress.set_step(f'开始采集 {len(urls)} 个URL...')

            fetcher = ContentFetchStage(self.session_mgr)
            extractor = ExtractorStage()
            storage = StorageStage(self.db, self.dedup)

            tasks = []
            for url in urls:
                task = asyncio.create_task(
                    self._process_url(
                        url, fetcher, extractor, storage,
                        job_id, progress, cancel_event
                    )
                )
                tasks.append(task)

            await asyncio.gather(*tasks, return_exceptions=True)

        finally:
            await self.close()

    async def _process_article(self, article: Dict, resolver, fetcher, extractor,
                                storage, job_id, progress, cancel_event):
        """处理单篇搜索结果文章"""
        async with self.semaphore:
            if cancel_event.is_set():
                return

            title = article.get('title', '未知')
            url = article.get('url', '')

            try:
                await self.rate_limiter.acquire()

                # URL去重
                if self.dedup.check_url(url):
                    progress.update(False, title, '重复URL，已跳过')
                    self._push_progress(job_id, progress)
                    return

                if self.db.article_exists(url):
                    progress.update(False, title, '数据库中已存在')
                    self._push_progress(job_id, progress)
                    return

                # 解析跳转
                real_url = await self._retry(lambda: resolver.resolve(url))
                if not real_url:
                    real_url = url

                # 获取内容
                html = await self._retry(lambda: fetcher.fetch(real_url))
                if not html:
                    progress.update(False, title, '获取内容失败')
                    self._push_progress(job_id, progress)
                    return

                # 提取
                extracted = extractor.extract(html, real_url)
                if not extracted:
                    progress.update(False, title, '内容提取失败')
                    self._push_progress(job_id, progress)
                    return

                # 合并搜索结果中的信息
                if not extracted.get('title') and title:
                    extracted['title'] = title
                if not extracted.get('account_name') and article.get('account_name'):
                    extracted['account_name'] = article['account_name']

                # 内容去重
                content_text = extracted.get('content', '')
                if content_text and self.dedup.check_content(content_text):
                    progress.update(False, extracted.get('title', title), '内容重复，已跳过')
                    self._push_progress(job_id, progress)
                    return

                # 计算内容指纹
                extracted['content_hash'] = self.dedup.content_hash(content_text) if content_text else None
                extracted['source'] = 'crawl'
                extracted['url'] = real_url

                # 存储
                article_id = storage.save(extracted)
                if article_id:
                    progress.update(True, extracted.get('title', title))
                else:
                    progress.update(False, extracted.get('title', title), '保存失败或已存在')

                self._push_progress(job_id, progress)

            except Exception as e:
                logger.error(f"处理文章失败 [{title}]: {e}")
                progress.update(False, title, str(e))
                self._push_progress(job_id, progress)

    async def _process_url(self, url: str, fetcher, extractor, storage,
                           job_id, progress, cancel_event):
        """处理单个URL"""
        async with self.semaphore:
            if cancel_event.is_set():
                return

            try:
                await self.rate_limiter.acquire()

                # URL去重
                if self.dedup.check_url(url):
                    progress.update(False, url[:50], '重复URL，已跳过')
                    self._push_progress(job_id, progress)
                    return

                if self.db.article_exists(url):
                    progress.update(False, url[:50], '数据库中已存在')
                    self._push_progress(job_id, progress)
                    return

                # 获取内容
                html = await self._retry(lambda: fetcher.fetch(url))
                if not html:
                    progress.update(False, url[:50], '获取内容失败')
                    self._push_progress(job_id, progress)
                    return

                # 提取
                extracted = extractor.extract(html, url)
                if not extracted:
                    progress.update(False, url[:50], '内容提取失败')
                    self._push_progress(job_id, progress)
                    return

                title = extracted.get('title', url[:50])

                # 内容去重
                content_text = extracted.get('content', '')
                if content_text and self.dedup.check_content(content_text):
                    progress.update(False, title, '内容重复，已跳过')
                    self._push_progress(job_id, progress)
                    return

                extracted['content_hash'] = self.dedup.content_hash(content_text) if content_text else None
                extracted['source'] = 'crawl'
                extracted['url'] = url

                article_id = storage.save(extracted)
                if article_id:
                    progress.update(True, title)
                else:
                    progress.update(False, title, '保存失败或已存在')

                self._push_progress(job_id, progress)

            except Exception as e:
                logger.error(f"处理URL失败 [{url[:50]}]: {e}")
                progress.update(False, url[:50], str(e))
                self._push_progress(job_id, progress)

    async def _retry(self, coro_factory, max_retries: int = None, backoff: float = None):
        """指数退避重试"""
        max_retries = max_retries or Config.CRAWL_RETRY_MAX
        backoff = backoff or Config.CRAWL_RETRY_BACKOFF

        for attempt in range(max_retries):
            try:
                return await coro_factory()
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.warning(f"重试{max_retries}次后仍失败: {e}")
                    return None
                wait = backoff * (2 ** attempt)
                logger.debug(f"第{attempt+1}次重试，等待{wait}s: {e}")
                await asyncio.sleep(wait)
        return None

    def _push_progress(self, job_id: str, progress):
        """推送进度（由JobManager的SSE机制处理）"""
        # 进度已在progress对象中更新，SSE轮询会读取
        pass
