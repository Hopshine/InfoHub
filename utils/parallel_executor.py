import asyncio
import time
from typing import List, Callable, Any, Dict, Optional
from utils.logger import setup_logger

logger = setup_logger('parallel_executor')


class LLMLogger:
    """Records LLM call metadata for each task."""

    def __init__(self, task_id: str, batch_id: str):
        self.task_id = task_id
        self.batch_id = batch_id
        self.logs: List[Dict] = []

    def log(self, model: str = '', prompt_tokens: int = 0,
            completion_tokens: int = 0, duration_ms: int = 0,
            stage: str = '', status: str = 'success', error: str = ''):
        self.logs.append({
            'task_id': self.task_id,
            'batch_id': self.batch_id,
            'model': model,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'duration_ms': duration_ms,
            'stage': stage,
            'status': status,
            'error': error,
            'timestamp': time.time(),
        })


class ParallelExecutor:
    """Runs async callables with bounded concurrency."""

    def __init__(self, max_concurrency: int = 5):
        self.max_concurrency = max_concurrency

    async def run(self, tasks: List[Dict]) -> List[Dict]:
        """Execute tasks in parallel with semaphore.

        Each task dict: {'fn': async_callable, 'args': tuple, 'id': str}
        Returns list of {'id': str, 'result': Any, 'error': str|None}
        """
        sem = asyncio.Semaphore(self.max_concurrency)
        results = []

        async def _wrap(task):
            async with sem:
                task_id = task.get('id', '')
                try:
                    result = await task['fn'](*task.get('args', ()))
                    return {'id': task_id, 'result': result, 'error': None}
                except Exception as e:
                    logger.error(f"Task {task_id} failed: {e}")
                    return {'id': task_id, 'result': None, 'error': str(e)}

        results = await asyncio.gather(*[_wrap(t) for t in tasks])
        return list(results)
