"""
热点定时采集调度器
每30分钟自动采集各平台热点数据
"""
import threading
import time
import uuid
from datetime import datetime
from collector.trending_collector import TrendingCollector


class TrendingScheduler:
    """热点采集定时调度器"""

    def __init__(self, db, interval_minutes=30):
        self.db = db
        self.interval = interval_minutes * 60
        self.collector = TrendingCollector()
        self._running = False
        self._thread = None
        self.last_update = None
        self.last_error = None

    def start(self):
        """启动定时采集"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True)
        self._thread.start()
        print(f"热点监控已启动，每{self.interval // 60}分钟更新")

    def stop(self):
        """停止定时采集"""
        self._running = False

    def _run_loop(self):
        """定时循环"""
        # 启动时立即采集一次
        self.refresh()
        while self._running:
            time.sleep(self.interval)
            if self._running:
                self.refresh()

    def refresh(self, platform: str = None) -> dict:
        """手动/自动刷新热点数据"""
        batch_id = datetime.now().strftime('%Y%m%d%H%M%S') + '_' + uuid.uuid4().hex[:6]
        results = {'batch_id': batch_id, 'platforms': {}}

        try:
            if platform:
                items = self.collector.collect_single(platform)
                if items:
                    self.db.save_trending(platform, items, batch_id)
                results['platforms'][platform] = len(items) if items else 0
            else:
                all_data = self.collector.collect_all()
                for plat, items in all_data.items():
                    if items:
                        self.db.save_trending(plat, items, batch_id)
                    results['platforms'][plat] = len(items)

            self.last_update = datetime.now().isoformat()
            self.last_error = None

            # 清理72小时前的旧数据
            self.db.cleanup_old_trending(72)

        except Exception as e:
            self.last_error = str(e)
            print(f"热点采集出错: {e}")

        return results

    @property
    def status(self) -> dict:
        return {
            'running': self._running,
            'interval_minutes': self.interval // 60,
            'last_update': self.last_update,
            'last_error': self.last_error
        }
