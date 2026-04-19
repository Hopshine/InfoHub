import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from utils.logger import setup_logger

logger = setup_logger('llm_logger')


class LLMLogger:
    """记录 LLM 调用日志到内存状态和数据库"""

    def __init__(self, agent_state: Dict[str, Any], db=None):
        self.agent_state = agent_state
        self.db = db
        self.agent_state.setdefault('llm_logs', [])

    def log_call(
        self,
        task_id: str,
        model: str,
        prompt: str,
        response: Any,
        tokens: Optional[Dict[str, int]] = None,
        duration_ms: Optional[int] = None,
        batch_id: Optional[str] = None,
        provider: Optional[str] = None,
        stage: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        response_text = self._extract_response_text(response)
        log_entry = {
            'task_id': task_id,
            'batch_id': batch_id,
            'stage': stage,
            'provider': provider,
            'model': model,
            'prompt': prompt,
            'response': response_text,
            'tokens': tokens or {},
            'duration_ms': duration_ms,
            'metadata': metadata or {},
            'created_at': datetime.now().isoformat(),
        }

        self.agent_state['llm_logs'].append(log_entry)

        if self.db:
            try:
                self.db.create_agent_llm_log(log_entry)
            except Exception as e:
                logger.warning(f"Failed to persist LLM log: {e}")

        logger.info(f"Logged LLM call for task {task_id}, model={model}, duration={duration_ms}ms")
        return log_entry

    async def wrap_openai_call(
        self,
        task_id: str,
        model: str,
        prompt: str,
        call_fn: Callable[..., Any],
        *args,
        batch_id: Optional[str] = None,
        stage: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Any:
        start = time.monotonic()
        response = await call_fn(*args, **kwargs)
        duration_ms = int((time.monotonic() - start) * 1000)
        tokens = self._extract_openai_tokens(response)
        self.log_call(
            task_id=task_id,
            model=model,
            prompt=prompt,
            response=response,
            tokens=tokens,
            duration_ms=duration_ms,
            batch_id=batch_id,
            provider='openai',
            stage=stage,
            metadata=metadata,
        )
        return response

    async def wrap_anthropic_call(
        self,
        task_id: str,
        model: str,
        prompt: str,
        call_fn: Callable[..., Any],
        *args,
        batch_id: Optional[str] = None,
        stage: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Any:
        start = time.monotonic()
        response = await call_fn(*args, **kwargs)
        duration_ms = int((time.monotonic() - start) * 1000)
        tokens = self._extract_anthropic_tokens(response)
        self.log_call(
            task_id=task_id,
            model=model,
            prompt=prompt,
            response=response,
            tokens=tokens,
            duration_ms=duration_ms,
            batch_id=batch_id,
            provider='anthropic',
            stage=stage,
            metadata=metadata,
        )
        return response

    def _extract_response_text(self, response: Any) -> str:
        if response is None:
            return ''
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            return str(response)

        choices = getattr(response, 'choices', None)
        if choices:
            message = getattr(choices[0], 'message', None)
            content = getattr(message, 'content', None)
            if content:
                return str(content)

        content = getattr(response, 'content', None)
        if content:
            if isinstance(content, list):
                texts: List[str] = []
                for block in content:
                    text = getattr(block, 'text', None)
                    if text:
                        texts.append(text)
                return '\n'.join(texts)
            return str(content)

        return str(response)

    def _extract_openai_tokens(self, response: Any) -> Dict[str, int]:
        usage = getattr(response, 'usage', None)
        if not usage:
            return {}
        return {
            'prompt_tokens': getattr(usage, 'prompt_tokens', 0) or 0,
            'completion_tokens': getattr(usage, 'completion_tokens', 0) or 0,
            'total_tokens': getattr(usage, 'total_tokens', 0) or 0,
        }

    def _extract_anthropic_tokens(self, response: Any) -> Dict[str, int]:
        usage = getattr(response, 'usage', None)
        if not usage:
            return {}
        input_tokens = getattr(usage, 'input_tokens', 0) or 0
        output_tokens = getattr(usage, 'output_tokens', 0) or 0
        return {
            'prompt_tokens': input_tokens,
            'completion_tokens': output_tokens,
            'total_tokens': input_tokens + output_tokens,
        }
