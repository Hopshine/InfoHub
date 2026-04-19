"""
百度热搜采集器 - 从百度热搜榜获取实时热搜数据
支持多个榜单：热搜榜、民生榜、财经榜、体育榜、文娱榜、国际榜等
"""
import requests
from typing import List, Dict, Optional
from datetime import datetime
from utils.logger import setup_logger

logger = setup_logger('baidu_trending')

HOT_TAG_MAP = {
    '0': '热议',
    '1': '新',
    '2': '沸',
    '3': '热',
}

BOARD_TABS = {
    'realtime': '热搜榜',
    'livelihood': '民生榜',
    'finance': '财经榜',
    'sports': '体育榜',
    'new_entertainment': '文娱榜',
    'internation_news': '国际榜',
}


class BaiduTrendingCollector:
    """百度热搜采集器"""

    API_URL = 'https://top.baidu.com/api/board'

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/125.0.0.0 Safari/537.36'
            ),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': 'https://top.baidu.com/board?tab=realtime',
        })

    def collect(self, tab: str = 'realtime', limit: int = 50) -> List[Dict]:
        """
        采集百度热搜榜单

        Args:
            tab: 榜单类型 (realtime/livelihood/finance/sports/new_entertainment/internation_news)
            limit: 返回条数限制

        Returns:
            热搜列表，每项包含: rank, title, url, hot_value, hot_tag, category
        """
        try:
            params = {
                'platform': 'wise',
                'tab': tab
            }

            logger.info(f"正在采集百度{BOARD_TABS.get(tab, tab)}...")
            resp = self.session.get(
                self.API_URL,
                params=params,
                timeout=self.timeout
            )

            if resp.status_code != 200:
                logger.error(f"API返回状态码: {resp.status_code}")
                return []

            data = resp.json()

            if not data.get('success'):
                logger.error(f"API返回失败: {data.get('error', {}).get('message', 'Unknown error')}")
                return []

            return self._parse_response(data, tab, limit)

        except requests.exceptions.Timeout:
            logger.error(f"请求超时 (>{self.timeout}s)")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求失败: {e}")
            return []
        except Exception as e:
            logger.error(f"采集失败: {e}", exc_info=True)
            return []

    def _parse_response(self, data: Dict, tab: str, limit: int) -> List[Dict]:
        """解析API响应数据"""
        try:
            cards = data.get('data', {}).get('cards', [])
            if not cards:
                logger.warning("响应中没有找到cards数据")
                return []

            content_list = cards[0].get('content', [])
            if not content_list or not isinstance(content_list[0], dict):
                logger.warning("响应格式异常")
                return []

            items = content_list[0].get('content', [])
            if not items:
                logger.warning("没有找到热搜条目")
                return []

            results = []
            for item in items[:limit]:
                rank = item.get('index')
                if rank is None and item.get('isTop'):
                    rank = 0
                elif rank is None:
                    continue

                hot_tag = item.get('hotTag', '')
                hot_tag_name = HOT_TAG_MAP.get(hot_tag, '')

                if not hot_tag_name and item.get('newHotName'):
                    hot_tag_name = item.get('newHotName')

                label_tag = item.get('labelTagName', '')

                results.append({
                    'rank': rank + 1 if rank > 0 else 1,
                    'title': item.get('word', '').strip(),
                    'url': item.get('url', ''),
                    'hot_value': hot_tag,
                    'hot_tag': hot_tag_name,
                    'category': label_tag or BOARD_TABS.get(tab, '热搜'),
                    'is_top': item.get('isTop', False),
                    'collected_at': datetime.now().isoformat(),
                })

            logger.info(f"成功解析 {len(results)} 条热搜")
            return results

        except Exception as e:
            logger.error(f"解析响应失败: {e}", exc_info=True)
            return []

    def collect_all_boards(self, limit: int = 30) -> Dict[str, List[Dict]]:
        """采集所有榜单"""
        results = {}
        for tab, name in BOARD_TABS.items():
            logger.info(f"开始采集 {name}...")
            items = self.collect(tab=tab, limit=limit)
            if items:
                results[tab] = items
                logger.info(f"{name} 采集成功: {len(items)}条")
            else:
                logger.warning(f"{name} 采集失败或无数据")
        return results

    def get_top_n(self, n: int = 10, tab: str = 'realtime') -> List[Dict]:
        """获取前N条热搜"""
        items = self.collect(tab=tab, limit=n)
        return items[:n]
