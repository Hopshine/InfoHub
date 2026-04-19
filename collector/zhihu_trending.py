"""
知乎热榜采集器 - 从知乎热榜获取实时热门内容
"""
import requests
from typing import List, Dict
from utils.logger import setup_logger

logger = setup_logger('zhihu_trending')


class ZhihuTrendingCollector:
    """知乎热榜采集器"""

    # v3 API需要登录，使用api.zhihu.com的公开接口
    API_URL = 'https://api.zhihu.com/topstory/hot-list'

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
        })
        # 不需要初始化cookies，api.zhihu.com可以直接访问

    def collect(self, limit: int = 50) -> List[Dict]:
        """
        采集知乎热榜

        Args:
            limit: 返回条数限制

        Returns:
            热榜列表，每项包含: rank, title, url, hot_value, excerpt
        """
        try:
            params = {
                'limit': limit
            }

            logger.info("正在采集知乎热榜...")
            resp = self.session.get(
                self.API_URL,
                params=params,
                timeout=self.timeout
            )

            if resp.status_code != 200:
                logger.error(f"API返回状态码: {resp.status_code}")
                return []

            data = resp.json()

            hot_list = data.get('data', [])
            if not hot_list:
                logger.warning("未获取到热榜数据")
                return []

            results = []
            for idx, item in enumerate(hot_list[:limit], 1):
                try:
                    target = item.get('target', {})
                    title = target.get('title', '').strip()
                    if not title:
                        continue

                    # 获取问题ID
                    question_id = target.get('id', '')

                    # 构建URL
                    url = f'https://www.zhihu.com/question/{question_id}' if question_id else ''

                    # 获取热度文本
                    hot_value = item.get('detail_text', '')

                    # 获取摘要
                    excerpt = target.get('excerpt', '')

                    results.append({
                        'rank': idx,
                        'title': title,
                        'url': url,
                        'hot_value': hot_value,
                        'excerpt': excerpt,
                        'source': '知乎',
                        'collected_at': None
                    })

                except Exception as e:
                    logger.warning(f"解析第{idx}条数据失败: {e}")
                    continue

            logger.info(f"知乎热榜采集成功: {len(results)}条")
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
        """获取前N条热榜"""
        items = self.collect(limit=n)
        return items[:n]


if __name__ == '__main__':
    collector = ZhihuTrendingCollector()
    trending = collector.get_top_n(10)

    print(f"\n{'='*60}")
    print(f"知乎热榜 TOP 10")
    print(f"{'='*60}\n")

    for item in trending:
        print(f"{item['rank']:2d}. {item['title']}")
        print(f"    热度: {item['hot_value']}")
        if item['excerpt']:
            print(f"    摘要: {item['excerpt'][:100]}...")
        print(f"    链接: {item['url']}")
        print()
