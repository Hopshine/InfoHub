import asyncio
import time
import uuid
from typing import Any, Callable, Coroutine, Dict, List, Optional
from datetime import datetime
from utils.logger import setup_logger

logger = setup_logger('parallel_executor')


class ParallelExecutor:
    """并行任务执行器，使用 asyncio.Semaphore 控制并发"""

    def __init__(self, max_concurrency: int = 5, db=None):
        self.max_concurrency = max_concurrency
        self.db = db
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._llm_logger_callback: Optional[Callable] = None

    def set_llm_logger(self, callback: Callable) -> None:
        self._llm_logger_callback = callback

    async def execute_tasks(
        self,
        tasks: List[Dict],
        task_fn: Callable[[Dict], Coroutine[Any, Any, Dict]],
        batch_id: Optional[str] = None,
        stage: Optional[str] = None,
    ) -> List[Dict]:
        if not tasks:
            return []

        batch_id = batch_id or uuid.uuid4().hex[:12]
        self._semaphore = asyncio.Semaphore(self.max_concurrency)

        async def _wrapped(task: Dict) -> Dict:
            task_id = task.get('id') or uuid.uuid4().hex[:8]
            task_record = {
                'task_id': task_id,
                'batch_id': batch_id,
                'stage': stage,
                'status': 'running',
                'started_at': datetime.now().isoformat(),
                'input_summary': str(task.get('title', ''))[:200],
            }
            db_task_id = self._track_task_start(task_record)

            async with self._semaphore:
                start_ts = time.monotonic()
                try:
                    if self._llm_logger_callback:
                        task['_llm_logger'] = self._llm_logger_callback
                        task['_batch_id'] = batch_id
                        task['_task_id'] = task_id

                    result = await task_fn(task)
                    duration_ms = int((time.monotonic() - start_ts) * 1000)

                    self._track_task_complete(db_task_id, {
                        'status': 'completed',
                        'duration_ms': duration_ms,
                        'completed_at': datetime.now().isoformat(),
                        'output_summary': str(result.get('title', ''))[:200] if isinstance(result, dict) else '',
                    })

                    logger.info(f"[{stage}] task {task_id} completed in {duration_ms}ms")
                    return {'task_id': task_id, 'status': 'completed', 'result': result}

                except Exception as e:
                    duration_ms = int((time.monotonic() - start_ts) * 1000)
                    self._handle_task_error(db_task_id, {
                        'status': 'failed',
                        'duration_ms': duration_ms,
                        'completed_at': datetime.now().isoformat(),
                        'error': str(e),
                    })
                    logger.error(f"[{stage}] task {task_id} failed: {e}")
                    return {'task_id': task_id, 'status': 'failed', 'error': str(e)}

        results = await asyncio.gather(*[_wrapped(t) for t in tasks])
        completed = sum(1 for r in results if r['status'] == 'completed')
        failed = sum(1 for r in results if r['status'] == 'failed')
        logger.info(f"[{stage}] batch {batch_id} done: {completed} completed, {failed} failed")
        return list(results)

    def _track_task_start(self, task_record: Dict) -> Optional[int]:
        if not self.db:
            return None
        try:
            return self.db.create_agent_task_log(task_record)
        except Exception as e:
            logger.warning(f"Failed to log task start: {e}")
            return None

    def _track_task_complete(self, db_task_id: Optional[int], updates: Dict) -> None:
        if not self.db or db_task_id is None:
            return
        try:
            self.db.update_agent_task_log(db_task_id, updates)
        except Exception as e:
            logger.warning(f"Failed to log task completion: {e}")

    def _handle_task_error(self, db_task_id: Optional[int], updates: Dict) -> None:
        if not self.db or db_task_id is None:
            return
        try:
            self.db.update_agent_task_log(db_task_id, updates)
        except Exception as e:
            logger.warning(f"Failed to log task error: {e}")
