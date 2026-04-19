"""
采集节点 - 采集Top话题的完整内容
"""
from typing import Dict
from utils.logger import setup_logger

logger = setup_logger('node.collector')


def collect_content(state: Dict) -> Dict:
    """
    采集Top话题的完整文章内容

    Args:
        state: Agent状态字典

    Returns:
        更新后的状态 {collected_content: [...]}
    """
    logger.info("=== 开始采集完整内容 ===")

    topics = state.get('evaluated_topics', [])
    if not topics:
        logger.warning("没有待采集的话题")
        state['collected_content'] = []
        return state

    try:
        from collector.hotnews_article_collector import HotNewsArticleCollector
        collector = HotNewsArticleCollector()
    except Exception as e:
        logger.error(f"初始化文章采集器失败: {e}")
        state['collected_content'] = []
        return state

    collected = []
    for topic in topics:
        url = topic.get('url', '')
        title = topic.get('title', '')

        if not url:
            logger.warning(f"话题无URL，跳过: {title[:30]}")
            collected.append({
                'title': title,
                'content': topic.get('summary', title),
                'source': topic.get('source', 'unknown'),
                'url': '',
                'score': topic.get('score', 0)
            })
            continue

        try:
            logger.info(f"采集内容: {title[:30]} - {url}")
            article = collector.collect_article(url)

            if article and article.get('content'):
                collected.append({
                    'title': title,
                    'content': article['content'],
                    'source': topic.get('source', 'unknown'),
                    'url': url,
                    'score': topic.get('score', 0),
                    'images': article.get('images', [])
                })
                logger.info(f"采集成功: {title[:30]} ({len(article['content'])}字)")
            else:
                collected.append({
                    'title': title,
                    'content': topic.get('summary', title),
                    'source': topic.get('source', 'unknown'),
                    'url': url,
                    'score': topic.get('score', 0)
                })
                logger.warning(f"采集内容为空: {title[:30]}")

        except Exception as e:
            logger.error(f"采集失败: {title[:30]} - {e}")
            collected.append({
                'title': title,
                'content': topic.get('summary', title),
                'source': topic.get('source', 'unknown'),
                'url': url,
                'score': topic.get('score', 0)
            })

    logger.info(f"内容采集完成，共 {len(collected)} 篇")
    state['collected_content'] = collected
    return state
