"""
扫描节点 - 调用4个采集器获取热点话题并去重
"""
from typing import Dict, List
from utils.logger import setup_logger
from agent.vector_store import VectorStore
import time

logger = setup_logger('node.scanner')


def scan_trending(state: Dict) -> Dict:
    """
    扫描热点话题

    Args:
        state: Agent状态字典

    Returns:
        更新后的状态 {raw_topics: [...]}
    """
    logger.info("=== 开始扫描热点话题 ===")

    try:
        # 初始化向量存储
        vector_store = state.get('vector_store')
        if not vector_store:
            vector_store = VectorStore()
            state['vector_store'] = vector_store

        # 导入采集器
        from collector.weibo_trending import WeiboTrendingCollector
        from collector.zhihu_trending import ZhihuTrendingCollector
        from collector.baidu_trending import BaiduTrendingCollector
        from collector.douyin_trending import DouyinTrendingCollector

        collectors = [
            ('weibo', WeiboTrendingCollector()),
            ('zhihu', ZhihuTrendingCollector()),
            ('baidu', BaiduTrendingCollector()),
            ('douyin', DouyinTrendingCollector())
        ]

        all_topics = []
        for source, collector in collectors:
            try:
                logger.info(f"采集 {source} 热点...")
                topics = collector.collect()
                logger.info(f"{source} 采集到 {len(topics)} 条")

                # 添加来源标识
                for topic in topics:
                    topic['source'] = source

                all_topics.extend(topics)
            except Exception as e:
                logger.error(f"{source} 采集失败: {e}")
                continue

        logger.info(f"总共采集到 {len(all_topics)} 条热点")

        # ChromaDB去重
        unique_topics = []
        for topic in all_topics:
            title = topic.get('title', '')
            if not title:
                continue

            # 检查是否重复
            if not vector_store.is_duplicate(title, threshold=0.85):
                # 添加到向量库
                metadata = {
                    'source': topic.get('source', 'unknown'),
                    'url': topic.get('url', ''),
                    'timestamp': int(time.time()),
                    'heat': topic.get('heat', 0)
                }
                vector_store.add_topic(title, metadata)
                unique_topics.append(topic)

        logger.info(f"去重后剩余 {len(unique_topics)} 条热点")

        state['raw_topics'] = unique_topics
        state['scan_time'] = time.time()

        return state

    except Exception as e:
        logger.error(f"扫描热点失败: {e}", exc_info=True)
        state['raw_topics'] = []
        state['error'] = str(e)
        return state
