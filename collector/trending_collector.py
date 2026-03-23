"""
热点采集器 - 支持多平台热榜数据采集
支持平台：微博热搜、知乎热榜、百度热搜、抖音热榜
"""
import requests
from typing import List, Dict
import json
import urllib3

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class TrendingCollector:
    """多平台热点采集器"""

    PLATFORMS = {
        'weibo': '微博热搜',
        'zhihu': '知乎热榜',
        'baidu': '百度热搜',
        'douyin': '抖音热榜'
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/120.0.0.0 Safari/537.36')
        })

    def collect_all(self) -> Dict[str, List[Dict]]:
        """采集所有平台热点"""
        return {
            'weibo': self.collect_weibo(),
            'zhihu': self.collect_zhihu(),
            'baidu': self.collect_baidu(),
            'douyin': self.collect_douyin()
        }

    def collect_weibo(self) -> List[Dict]:
        """采集微博热搜"""
        try:
            # 使用完整的浏览器请求头来避免403
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://weibo.com/',
                'Origin': 'https://weibo.com',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
            }

            url = 'https://weibo.com/ajax/side/hotSearch'
            resp = self.session.get(url, headers=headers, timeout=10)

            if resp.status_code != 200:
                print(f"微博API返回状态码: {resp.status_code}")
                return []

            # 确保正确的编码
            resp.encoding = 'utf-8'
            data = resp.json()
            items = data.get('data', {}).get('realtime', [])

            if not items:
                print("微博API返回数据为空")
                return []

            trends = []
            for idx, item in enumerate(items[:50], 1):
                word = item.get('word', '')
                trends.append({
                    'rank': idx,
                    'title': item.get('note', word),
                    'hot_value': item.get('num', 0),
                    'url': f'https://s.weibo.com/weibo?q=%23{word}%23',
                    'label': item.get('label_name', '')
                })

            print(f"微博热搜采集成功: {len(trends)}条")
            return trends
        except Exception as e:
            import traceback
            print(f"微博热搜采集失败: {e}")
            print(traceback.format_exc())
            return []

    def collect_zhihu(self) -> List[Dict]:
        """采集知乎热榜 - 使用移动端API"""
        try:
            # 使用知乎移动端API（更稳定）
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 ZhihuHybrid/6.0.0',
                'x-app-version': '6.0.0',
                'x-api-version': '3.0.91',
            }
            url = 'https://api.zhihu.com/topstory/hot-list?limit=50'
            resp = self.session.get(url, headers=headers, timeout=10)

            if resp.status_code != 200:
                return []

            data = resp.json()
            trends = []

            for idx, item in enumerate(data.get('data', [])[:50], 1):
                target = item.get('target', {})

                # 提取嵌套的数据
                title = target.get('title_area', {}).get('text', '')
                excerpt = target.get('excerpt_area', {}).get('text', '')
                hot_value = target.get('metrics_area', {}).get('text', '')
                url = target.get('link', {}).get('url', '')

                if title:  # 只添加有标题的条目
                    trends.append({
                        'rank': idx,
                        'title': title,
                        'hot_value': hot_value,
                        'url': url,
                        'excerpt': excerpt[:100] if excerpt else ''
                    })

            return trends

        except Exception as e:
            print(f"知乎热榜采集失败: {e}")
            return []

    def collect_baidu(self) -> List[Dict]:
        """采集百度热搜"""
        try:
            url = 'https://top.baidu.com/api/board?platform=wise&tab=realtime'
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return []
            data = resp.json()
            cards = data.get('data', {}).get('cards', [])
            if not cards:
                return []
            # 百度API结构: cards[0].content[0].content[]
            top_content = cards[0].get('content', [])
            if not top_content or not isinstance(top_content[0], dict):
                return []
            items = top_content[0].get('content', [])
            trends = []
            for item in items[:50]:
                rank = item.get('index', 0)
                if item.get('isTop'):
                    rank = 0
                trends.append({
                    'rank': rank if rank > 0 else len(trends) + 1,
                    'title': item.get('word', ''),
                    'hot_value': item.get('hotTag', ''),
                    'url': item.get('url', ''),
                    'label': item.get('labelTagName', '')
                })
            return trends
        except Exception as e:
            print(f"百度热搜采集失败: {e}")
            return []

    def collect_douyin(self) -> List[Dict]:
        """采集抖音热榜"""
        try:
            # 使用完整的浏览器请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Referer': 'https://www.douyin.com/',
                'Origin': 'https://www.douyin.com',
            }

            url = 'https://www.douyin.com/aweme/v1/web/hot/search/list/'
            resp = self.session.get(url, headers=headers, timeout=10)

            if resp.status_code != 200:
                print(f"抖音API返回状态码: {resp.status_code}")
                return []

            resp.encoding = 'utf-8'
            data = resp.json()

            # 数据在 data.word_list 中
            items = data.get('data', {}).get('word_list', [])

            if not items:
                print("抖音API返回数据为空")
                return []

            trends = []
            for item in items[:50]:
                word = item.get('word', '')
                position = item.get('position', 0)
                hot_value = item.get('hot_value', 0)

                trends.append({
                    'rank': position,
                    'title': word,
                    'hot_value': hot_value,
                    'url': f'https://www.douyin.com/search/{word}',
                    'label': ''
                })

            print(f"抖音热榜采集成功: {len(trends)}条")
            return trends

        except Exception as e:
            import traceback
            print(f"抖音热榜采集失败: {e}")
            print(traceback.format_exc())
            return []

    def collect_single(self, platform: str) -> List[Dict]:
        """采集单个平台"""
        method = getattr(self, f'collect_{platform}', None)
        if method:
            return method()
        return []
