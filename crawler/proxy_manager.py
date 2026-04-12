"""
代理管理器 - 处理代理池加载、验证、轮换和失效追踪
"""
import os
import time
import random
from typing import Optional, List, Dict
from utils.logger import setup_logger

logger = setup_logger('proxy_manager')


class ProxyManager:
    """代理池管理器"""

    def __init__(self, proxy_file: Optional[str] = None, max_failures: int = 3):
        """
        初始化代理管理器

        Args:
            proxy_file: 代理列表文件路径
            max_failures: 代理最大失败次数
        """
        self.proxy_file = proxy_file
        self.max_failures = max_failures
        self.proxies: List[Dict] = []
        self.current_index = 0
        self.proxy_stats: Dict[str, Dict] = {}

        # 从文件或环境变量加载代理
        self._load_proxies()

    def _load_proxies(self):
        """从配置文件或环境变量加载代理列表"""
        proxy_list = []

        # 1. 尝试从环境变量加载
        env_proxies = os.getenv('PROXY_LIST', '')
        if env_proxies:
            proxy_list = [p.strip() for p in env_proxies.split(',') if p.strip()]
            logger.info(f"从环境变量加载了 {len(proxy_list)} 个代理")

        # 2. 尝试从文件加载
        if not proxy_list and self.proxy_file and os.path.exists(self.proxy_file):
            try:
                with open(self.proxy_file, 'r', encoding='utf-8') as f:
                    proxy_list = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                logger.info(f"从文件 {self.proxy_file} 加载了 {len(proxy_list)} 个代理")
            except Exception as e:
                logger.error(f"加载代理文件失败: {e}")

        # 3. 解析代理列表
        for proxy_url in proxy_list:
            proxy_dict = self._parse_proxy(proxy_url)
            if proxy_dict:
                self.proxies.append(proxy_dict)
                # 初始化统计信息
                self.proxy_stats[proxy_url] = {
                    'failures': 0,
                    'successes': 0,
                    'last_failure': 0,
                    'disabled': False,
                    'cooldown_until': 0
                }

        if self.proxies:
            logger.info(f"代理池初始化完成，共 {len(self.proxies)} 个可用代理")
        else:
            logger.warning("未配置代理，将使用直连模式")

    def _parse_proxy(self, proxy_url: str) -> Optional[Dict]:
        """
        解析代理URL为Playwright格式

        Args:
            proxy_url: 代理URL (http://user:pass@host:port 或 http://host:port)

        Returns:
            代理配置字典
        """
        try:
            # 支持格式: http://host:port, http://user:pass@host:port, socks5://host:port
            if '://' not in proxy_url:
                proxy_url = f'http://{proxy_url}'

            from urllib.parse import urlparse
            parsed = urlparse(proxy_url)

            proxy_dict = {
                'server': f'{parsed.scheme}://{parsed.hostname}:{parsed.port}',
                'url': proxy_url
            }

            # 如果有用户名密码
            if parsed.username and parsed.password:
                proxy_dict['username'] = parsed.username
                proxy_dict['password'] = parsed.password

            return proxy_dict

        except Exception as e:
            logger.error(f"解析代理URL失败 {proxy_url}: {e}")
            return None

    def get_proxy(self, strategy: str = 'random') -> Optional[Dict]:
        """
        获取一个可用代理

        Args:
            strategy: 轮换策略 ('random' 或 'round-robin')

        Returns:
            代理配置字典，无可用代理返回None
        """
        if not self.proxies:
            return None

        # 过滤掉被禁用或在冷却期的代理
        available_proxies = []
        current_time = time.time()

        for proxy in self.proxies:
            proxy_url = proxy['url']
            stats = self.proxy_stats[proxy_url]

            # 检查是否在冷却期
            if stats['cooldown_until'] > current_time:
                continue

            # 检查是否被永久禁用
            if stats['disabled']:
                continue

            available_proxies.append(proxy)

        if not available_proxies:
            logger.warning("没有可用代理，所有代理都在冷却期或被禁用")
            return None

        # 根据策略选择代理
        if strategy == 'random':
            selected = random.choice(available_proxies)
        else:  # round-robin
            selected = available_proxies[self.current_index % len(available_proxies)]
            self.current_index += 1

        logger.debug(f"选择代理: {selected['server']}")
        return selected

    def report_success(self, proxy: Dict):
        """
        报告代理使用成功

        Args:
            proxy: 代理配置字典
        """
        if not proxy or 'url' not in proxy:
            return

        proxy_url = proxy['url']
        if proxy_url in self.proxy_stats:
            stats = self.proxy_stats[proxy_url]
            stats['successes'] += 1
            stats['failures'] = 0  # 重置失败计数
            logger.debug(f"代理成功: {proxy['server']} (总成功: {stats['successes']})")

    def report_failure(self, proxy: Dict):
        """
        报告代理使用失败

        Args:
            proxy: 代理配置字典
        """
        if not proxy or 'url' not in proxy:
            return

        proxy_url = proxy['url']
        if proxy_url not in self.proxy_stats:
            return

        stats = self.proxy_stats[proxy_url]
        stats['failures'] += 1
        stats['last_failure'] = time.time()

        logger.warning(f"代理失败: {proxy['server']} (失败次数: {stats['failures']}/{self.max_failures})")

        # 如果失败次数达到阈值，进入冷却期
        if stats['failures'] >= self.max_failures:
            cooldown_duration = 300  # 5分钟冷却期
            stats['cooldown_until'] = time.time() + cooldown_duration
            stats['failures'] = 0  # 重置计数
            logger.warning(f"代理 {proxy['server']} 进入冷却期 {cooldown_duration}秒")

    def disable_proxy(self, proxy: Dict):
        """
        永久禁用代理

        Args:
            proxy: 代理配置字典
        """
        if not proxy or 'url' not in proxy:
            return

        proxy_url = proxy['url']
        if proxy_url in self.proxy_stats:
            self.proxy_stats[proxy_url]['disabled'] = True
            logger.warning(f"代理已禁用: {proxy['server']}")

    def get_stats(self) -> Dict:
        """
        获取代理池统计信息

        Returns:
            统计信息字典
        """
        total = len(self.proxies)
        available = sum(1 for url, stats in self.proxy_stats.items()
                       if not stats['disabled'] and stats['cooldown_until'] <= time.time())
        disabled = sum(1 for stats in self.proxy_stats.values() if stats['disabled'])
        cooling = sum(1 for stats in self.proxy_stats.values()
                     if stats['cooldown_until'] > time.time())

        return {
            'total': total,
            'available': available,
            'disabled': disabled,
            'cooling': cooling,
            'details': self.proxy_stats
        }

    def reset_all(self):
        """重置所有代理状态"""
        for stats in self.proxy_stats.values():
            stats['failures'] = 0
            stats['successes'] = 0
            stats['disabled'] = False
            stats['cooldown_until'] = 0
        logger.info("所有代理状态已重置")
