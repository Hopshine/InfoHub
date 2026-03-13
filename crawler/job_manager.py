"""任务管理器 - 线程安全，守护线程运行asyncio事件循环"""
import asyncio
import threading
import uuid
import json
from datetime import datetime
from typing import Dict, Optional, Callable
from collections import defaultdict
from utils.logger import setup_logger

logger = setup_logger('job_manager')


class JobProgress:
    """任务进度追踪"""

    def __init__(self, job_id: str, total: int = 0):
        self.job_id = job_id
        self.total = total
        self.completed = 0
        self.succeeded = 0
        self.failed = 0
        self.status = 'pending'  # pending, running, completed, cancelled, failed
        self.items = []  # 每条结果详情
        self.current_step = ''
        self._lock = threading.Lock()

    def update(self, success: bool, title: str = '', error: str = ''):
        with self._lock:
            self.completed += 1
            if success:
                self.succeeded += 1
            else:
                self.failed += 1
            self.items.append({
                'title': title,
                'success': success,
                'error': error
            })

    def set_step(self, step: str):
        with self._lock:
            self.current_step = step

    def snapshot(self) -> Dict:
        with self._lock:
            return {
                'job_id': self.job_id,
                'status': self.status,
                'total': self.total,
                'completed': self.completed,
                'succeeded': self.succeeded,
                'failed': self.failed,
                'current_step': self.current_step,
                'items': list(self.items),
                'progress_pct': round(self.completed / self.total * 100) if self.total > 0 else 0
            }


class JobManager:
    """任务管理器 - 在守护线程中运行asyncio事件循环"""

    def __init__(self, db):
        self.db = db
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._jobs: Dict[str, JobProgress] = {}
        self._cancel_flags: Dict[str, asyncio.Event] = {}
        self._sse_queues: Dict[str, list] = defaultdict(list)  # job_id -> list of asyncio.Queue
        self._lock = threading.Lock()
        self._start_loop()

    def _start_loop(self):
        """启动守护线程运行事件循环"""
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("JobManager 事件循环已启动")

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def submit_job(self, job_type: str, params: Dict, crawl_coro_factory) -> str:
        """
        提交采集任务

        Args:
            job_type: 'search' | 'batch_url' | 'single_url'
            params: 任务参数
            crawl_coro_factory: 接收(job_id, progress, cancel_event)返回协程的工厂函数

        Returns:
            job_id
        """
        job_id = str(uuid.uuid4())[:8]

        progress = JobProgress(job_id)
        cancel_event = asyncio.Event()

        with self._lock:
            self._jobs[job_id] = progress
            self._cancel_flags[job_id] = cancel_event

        # 保存到数据库
        self.db.insert_crawl_job({
            'id': job_id,
            'job_type': job_type,
            'params': json.dumps(params, ensure_ascii=False),
            'status': 'pending'
        })

        # 在事件循环中启动任务
        async def _run():
            try:
                progress.status = 'running'
                self.db.update_crawl_job(job_id, {'status': 'running'})
                await crawl_coro_factory(job_id, progress, cancel_event)
                if progress.status == 'running':
                    progress.status = 'completed'
                    self.db.update_crawl_job(job_id, {
                        'status': 'completed',
                        'total': progress.total,
                        'completed': progress.completed,
                        'succeeded': progress.succeeded,
                        'failed': progress.failed,
                        'progress': json.dumps(progress.items, ensure_ascii=False)
                    })
                # 发送完成事件到SSE
                self._push_sse_event(job_id, progress.snapshot())
            except asyncio.CancelledError:
                progress.status = 'cancelled'
                self.db.update_crawl_job(job_id, {'status': 'cancelled'})
                self._push_sse_event(job_id, progress.snapshot())
            except Exception as e:
                logger.error(f"任务 {job_id} 执行失败: {e}")
                progress.status = 'failed'
                self.db.update_crawl_job(job_id, {'status': 'failed'})
                self._push_sse_event(job_id, progress.snapshot())

        asyncio.run_coroutine_threadsafe(_run(), self._loop)
        logger.info(f"任务已提交: {job_id} ({job_type})")
        return job_id

    def get_progress(self, job_id: str) -> Optional[Dict]:
        """获取任务进度快照"""
        with self._lock:
            progress = self._jobs.get(job_id)
        if progress:
            return progress.snapshot()
        # 从数据库查
        return self.db.get_crawl_job(job_id)

    def cancel_job(self, job_id: str) -> bool:
        """取消任务"""
        with self._lock:
            cancel_event = self._cancel_flags.get(job_id)
            progress = self._jobs.get(job_id)
        if cancel_event and progress:
            self._loop.call_soon_threadsafe(cancel_event.set)
            progress.status = 'cancelled'
            self.db.update_crawl_job(job_id, {'status': 'cancelled'})
            logger.info(f"任务已取消: {job_id}")
            return True
        return False

    def create_sse_queue(self, job_id: str) -> asyncio.Queue:
        """创建SSE事件队列"""
        queue = asyncio.Queue()
        with self._lock:
            self._sse_queues[job_id].append(queue)
        return queue

    def remove_sse_queue(self, job_id: str, queue: asyncio.Queue):
        """移除SSE事件队列"""
        with self._lock:
            if job_id in self._sse_queues:
                try:
                    self._sse_queues[job_id].remove(queue)
                except ValueError:
                    pass

    def _push_sse_event(self, job_id: str, data: Dict):
        """推送事件到所有SSE队列"""
        with self._lock:
            queues = list(self._sse_queues.get(job_id, []))
        for q in queues:
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                pass

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        return self._loop
