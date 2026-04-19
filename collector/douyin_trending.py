"""
抖音热点采集器 - 从抖音热搜榜获取实时热点数据
"""
import requests
from typing import List, Dict
from utils.logger import setup_logger

logger = setup_logger('douyin_trending')


class DouyinTrendingCollector:
    """抖音热点采集器"""

    API_URL = 'https://www.douyin.com/aweme/v1/web/hot/search/list/'

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
            'Referer': 'https://www.douyin.com/',
        })

    def collect(self, limit: int = 50) -> List[Dict]:
        """
        采集抖音热点榜单

        Args:
            limit: 返回条数限制

        Returns:
            热点列表，每项包含: rank, title, url, hot_value
        """
        try:
            logger.info("正在采集抖音热点...")
            resp = self.session.get(
                self.API_URL,
                timeout=self.timeout
            )

            if resp.status_code != 200:
                logger.error(f"API返回状态码: {resp.status_code}")
                return []

            data = resp.json()

            word_list = data.get('data', {}).get('word_list', [])
            if not word_list:
                logger.warning("未获取到热点数据")
                return []

            results = []
            for idx, item in enumerate(word_list[:limit], 1):
                try:
                    word = item.get('word', '').strip()
                    if not word:
                        continue

                    # 获取热度值
                    hot_value = item.get('hot_value', 0)

                    # 获取事件时间
                    event_time = item.get('event_time', '')

                    # 抖音热搜没有直接的URL，使用搜索页面
                    url = f'https://www.douyin.com/search/{word}'

                    results.append({
                        'rank': idx,
                        'title': word,
                        'url': url,
                        'hot_value': hot_value,
                        'event_time': event_time,
                        'source': '抖音',
                        'collected_at': None
                    })

                except Exception as e:
                    logger.warning(f"解析第{idx}条数据失败: {e}")
                    continue

            logger.info(f"抖音热点采集成功: {len(results)}条")
            return results

        except requests.exceptions.Timeout:
            logger.error(f"请求超时 (>{self.timeout}s)")
            return []

        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求失败: {e}")
            return []

        except ValueError as e:
            logger.error(f"JSON解析失败: {e}")
            return []

        except Exception as e:
            logger.error(f"采集失败: {e}", exc_info=True)
            return []

    def get_top_n(self, n: int = 10) -> List[Dict]:
        """获取前N条热点"""
        items = self.collect(limit=n)
        return items[:n]


if __name__ == '__main__':
    collector = DouyinTrendingCollector()
    trending = collector.get_top_n(10)

    print(f"\n{'='*60}")
    print(f"抖音热点 TOP 10")
    print(f"{'='*60}\n")

    for item in trending:
        print(f"{item['rank']:2d}. {item['title']}")
        print(f"    热度: {item['hot_value']:,}")
        if item.get('event_time'):
            print(f"    时间: {item['event_time']}")
        print(f"    链接: {item['url']}")
        print()
