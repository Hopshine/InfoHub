"""
热点新闻收集器 - 从多个源获取热点新闻用于文章生成
支持平台：今日头条、百度热搜、微博热搜
"""
import requests
import uuid
from typing import List, Dict
from datetime import datetime
from utils.logger import setup_logger
from config import Config

logger = setup_logger('hotnews')


class HotNewsCollector:
    """热点新闻收集器"""

    SOURCES = {
        'toutiao': '今日头条',
        'baidu': '百度热搜',
        'weibo': '微博热搜',
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/120.0.0.0 Safari/537.36')
        })

    def collect_all(self, sources: List[str] = None) -> Dict[str, List[Dict]]:
        """采集所有配置的热点源"""
        sources = sources or Config.HOTNEWS_SOURCES
        results = {}
        for source in sources:
            source = source.strip()
            if source in self.SOURCES:
                logger.info(f"正在采集 {self.SOURCES[source]} ...")
                items = self.collect_single(source)
                results[source] = items
                logger.info(f"{self.SOURCES[source]} 采集完成: {len(items)}条")
            else:
                logger.warning(f"不支持的新闻源: {source}")
        return results

    def collect_single(self, source: str) -> List[Dict]:
        """采集单个平台"""
        method = getattr(self, f'_collect_{source}', None)
        if method:
            try:
                return method()
            except Exception as e:
                logger.error(f"{source} 采集失败: {e}")
                return []
        return []

    def _collect_toutiao(self) -> List[Dict]:
        """采集今日头条热榜"""
        try:
            url = 'https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc'
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Referer': 'https://www.toutiao.com/',
            }
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                logger.warning(f"今日头条API返回状态码: {resp.status_code}")
                return []

            data = resp.json()
            items = data.get('data', [])
            results = []
            for idx, item in enumerate(items[:30], 1):
                results.append({
                    'rank': idx,
                    'title': item.get('Title', ''),
                    'url': item.get('Url', ''),
                    'hot_value': item.get('HotValue', ''),
                    'summary': item.get('Abstract', ''),
                })
            return results
        except Exception as e:
            logger.error(f"今日头条采集失败: {e}")
            return []

    def _collect_baidu(self) -> List[Dict]:
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
            top_content = cards[0].get('content', [])
            if not top_content or not isinstance(top_content[0], dict):
                return []
            items = top_content[0].get('content', [])
            results = []
            for idx, item in enumerate(items[:30], 1):
                results.append({
                    'rank': idx,
                    'title': item.get('word', ''),
                    'url': item.get('url', ''),
                    'hot_value': item.get('hotTag', ''),
                    'summary': item.get('desc', ''),
                })
            return results
        except Exception as e:
            logger.error(f"百度热搜采集失败: {e}")
            return []

    def _collect_weibo(self) -> List[Dict]:
        """采集微博热搜"""
        try:
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Referer': 'https://weibo.com/',
                'Origin': 'https://weibo.com',
            }
            url = 'https://weibo.com/ajax/side/hotSearch'
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return []
            data = resp.json()
            items = data.get('data', {}).get('realtime', [])
            results = []
            for idx, item in enumerate(items[:30], 1):
                word = item.get('word', '')
                results.append({
                    'rank': idx,
                    'title': item.get('note', word),
                    'url': f'https://s.weibo.com/weibo?q=%23{word}%23',
                    'hot_value': item.get('num', 0),
                    'summary': '',
                })
            return results
        except Exception as e:
            logger.error(f"微博热搜采集失败: {e}")
            return []

    def collect_and_save(self, db, sources: List[str] = None) -> int:
        """采集并保存到数据库"""
        all_news = self.collect_all(sources)
        batch_id = datetime.now().strftime('%Y%m%d%H%M%S') + '_' + uuid.uuid4().hex[:8]
        total = 0
        for source, items in all_news.items():
            if items:
                db.save_hotnews(source, items, batch_id)
                total += len(items)
        logger.info(f"热点新闻采集完成，共保存 {total} 条，batch_id: {batch_id}")
        return total
