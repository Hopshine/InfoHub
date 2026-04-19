"""
微博热搜采集器 - 从微博热搜榜获取实时热搜数据
"""
import requests
from typing import List, Dict
from urllib.parse import quote
from utils.logger import setup_logger

logger = setup_logger('weibo_trending')


class WeiboTrendingCollector:
    """微博热搜采集器"""

    API_URL = 'https://weibo.com/ajax/side/hotSearch'

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
            'Referer': 'https://weibo.com',
        })

    def collect(self, limit: int = 50) -> List[Dict]:
        """
        采集微博热搜榜单

        Args:
            limit: 返回条数限制

        Returns:
            热搜列表，每项包含: rank, title, url, hot_value, label
        """
        try:
            logger.info("正在采集微博热搜...")
            resp = self.session.get(
                self.API_URL,
                timeout=self.timeout
            )

            if resp.status_code != 200:
                logger.error(f"API返回状态码: {resp.status_code}")
                return []

            data = resp.json()

            if not data.get('ok'):
                logger.error(f"API返回失败: {data}")
                return []

            realtime_data = data.get('data', {}).get('realtime', [])
            if not realtime_data:
                logger.warning("未获取到热搜数据")
                return []

            results = []
            for idx, item in enumerate(realtime_data[:limit], 1):
                try:
                    word = item.get('word', '').strip()
                    if not word:
                        continue

                    # 构建热搜URL
                    encoded_word = quote(f'#{word}#')
                    url = f'https://s.weibo.com/weibo?q={encoded_word}'

                    # 获取热度值
                    hot_value = item.get('num', 0)

                    # 获取标签（新、热、沸等）
                    label = item.get('label_name', '')

                    # 获取描述
                    note = item.get('note', '')

                    results.append({
                        'rank': idx,
                        'title': word,
                        'url': url,
                        'hot_value': hot_value,
                        'label': label,
                        'excerpt': note,
                        'source': '微博',
                        'collected_at': None
                    })

                except Exception as e:
                    logger.warning(f"解析第{idx}条数据失败: {e}")
                    continue

            logger.info(f"微博热搜采集成功: {len(results)}条")
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
        """获取前N条热搜"""
        items = self.collect(limit=n)
        return items[:n]


if __name__ == '__main__':
    collector = WeiboTrendingCollector()
    trending = collector.get_top_n(10)

    print(f"\n{'='*60}")
    print(f"微博热搜 TOP 10")
    print(f"{'='*60}\n")

    for item in trending:
        label_str = f"[{item['label']}]" if item['label'] else ""
        print(f"{item['rank']:2d}. {label_str} {item['title']}")
        print(f"    热度: {item['hot_value']:,}")
        if item['excerpt']:
            print(f"    描述: {item['excerpt']}")
        print(f"    链接: {item['url']}")
        print()
