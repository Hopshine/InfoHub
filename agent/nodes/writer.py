"""
写作节点 - 用Anthropic生成推文（公众号版+知乎版），RAG检索历史文章
"""
import json
from typing import Dict
from utils.logger import setup_logger
from agent.prompts import WRITE_WECHAT_PROMPT, WRITE_ZHIHU_PROMPT
from config_loader import LLMConfigLoader
from storage.database import Database

logger = setup_logger('node.writer')


def _get_client_and_config():
    """获取Anthropic客户端"""
    db = Database()
    config = LLMConfigLoader.get_config(db, 'article_generation')
    from openai import OpenAI
    client = OpenAI(
        api_key=config['api_key'],
        base_url=config['base_url'] if config['base_url'] else None
    )
    return client, config


def write_articles(state: Dict) -> Dict:
    """
    生成推文（公众号版+知乎版）

    Args:
        state: Agent状态字典

    Returns:
        更新后的状态 {written_articles: [...]}
    """
    logger.info("=== 开始生成文章 ===")

    planned = state.get('planned_articles', [])
    if not planned:
        logger.warning("没有待写作的选题")
        state['written_articles'] = []
        return state

    # RAG检索历史文章作为参考
    vector_store = state.get('vector_store')
    client, config = _get_client_and_config()

    written = []
    for item in planned:
        title = item.get('title', '')
        plan = item.get('plan', {})
        content = item.get('content', '')
        angles = plan.get('angles', [])

        if not angles:
            angles = [{'title': title, 'outline': [], 'style': 'wechat'}]

        # 取推荐角度
        rec_idx = plan.get('recommended_index', 0)
        angle = angles[min(rec_idx, len(angles) - 1)]

        # RAG检索参考文章
        reference = ""
        if vector_store:
            try:
                similar = vector_store.search_similar(title, n=3)
                if similar:
                    reference = "\n---\n".join([s['content'][:500] for s in similar])
            except Exception as e:
                logger.warning(f"RAG检索失败: {e}")

        outline = json.dumps(angle.get('outline', []), ensure_ascii=False)

        try:
            # 生成公众号版
            wechat_prompt = WRITE_WECHAT_PROMPT.format(
                title=angle.get('title', title),
                outline=outline,
                content=content[:3000],
                reference=reference[:1000] if reference else "无参考"
            )

            wechat_resp = client.chat.completions.create(
                model=config['model'],
                messages=[{'role': 'user', 'content': wechat_prompt}],
                max_tokens=config.get('max_tokens', 4000),
                temperature=0.8
            )
            wechat_article = wechat_resp.choices[0].message.content.strip()

            # 生成知乎版
            zhihu_prompt = WRITE_ZHIHU_PROMPT.format(
                title=angle.get('title', title),
                outline=outline,
                content=content[:3000],
                reference=reference[:1000] if reference else "无参考"
            )

            zhihu_resp = client.chat.completions.create(
                model=config['model'],
                messages=[{'role': 'user', 'content': zhihu_prompt}],
                max_tokens=config.get('max_tokens', 4000),
                temperature=0.7
            )
            zhihu_article = zhihu_resp.choices[0].message.content.strip()

            # 存入向量库
            if vector_store:
                try:
                    vector_store.add_article(wechat_article, {
                        'title': angle.get('title', title),
                        'platform': 'wechat',
                        'source_topic': title
                    })
                except Exception:
                    pass

            written.append({
                'title': angle.get('title', title),
                'source_topic': title,
                'wechat': wechat_article,
                'zhihu': zhihu_article,
                'score': item.get('score', 0),
                'plan': angle
            })

            logger.info(f"写作完成: {angle.get('title', title)[:30]}")

        except Exception as e:
            logger.error(f"写作失败: {title[:30]} - {e}")
            written.append({
                'title': title,
                'source_topic': title,
                'wechat': '',
                'zhihu': '',
                'score': item.get('score', 0),
                'error': str(e)
            })

    logger.info(f"文章生成完成，共 {len(written)} 篇")
    state['written_articles'] = written
    return state
