"""令牌桶限速器"""
import asyncio
import time


class RateLimiter:
    """令牌桶算法限速器"""

    def __init__(self, rate: float = 2.0, burst: int = 5):
        """
        Args:
            rate: 每秒允许的请求数
            burst: 突发上限
        """
        self.rate = rate
        self.burst = burst
        self.tokens = float(burst)
        self.last_time = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """获取一个令牌，满时等待"""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_time
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_time = now

            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1
