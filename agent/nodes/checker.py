"""
质量检查节点 - 评分并标记需优化的文章
"""
import json
from typing import Dict
from openai import OpenAI
from utils.logger import setup_logger
from agent.prompts import CHECK_PROMPT

logger = setup_logger('node.checker')

OLLAMA_CLIENT = OpenAI(base_url='http://localhost:11434/v1', api_key='ollama')


def check_quality(state: Dict) -> Dict:
    """
    质量检查评分，低分标记需优化

    Args:
        state: Agent状态字典

    Returns:
        更新后的状态 {checked_articles: [...], quality_pass: bool}
    """
    logger.info("=== 开始质量检查 ===")

    written = state.get('written_articles', [])
    if not written:
        logger.warning("没有待检查的文章")
        state['checked_articles'] = []
        state['quality_pass'] = True
        return state

    checked = []
    all_pass = True

    for article in written:
        title = article.get('title', '')

        # 检查公众号版
        wechat_content = article.get('wechat', '')
        zhihu_content = article.get('zhihu', '')

        wechat_score = _check_single(title, 'wechat', wechat_content)
        zhihu_score = _check_single(title, 'zhihu', zhihu_content)

        article['quality'] = {
            'wechat': wechat_score,
            'zhihu': zhihu_score
        }

        wechat_pass = wechat_score.get('overall_score', 0) >= 80
        zhihu_pass = zhihu_score.get('overall_score', 0) >= 80
        article['needs_optimization'] = not (wechat_pass and zhihu_pass)

        if article['needs_optimization']:
            all_pass = False
            logger.warning(
                f"质量不达标: {title[:30]} "
                f"(wechat={wechat_score.get('overall_score', 0)}, "
                f"zhihu={zhihu_score.get('overall_score', 0)})"
            )
        else:
            logger.info(f"质量达标: {title[:30]}")

        checked.append(article)

    state['checked_articles'] = checked
    state['quality_pass'] = all_pass

    logger.info(f"质量检查完成: {'全部通过' if all_pass else '部分需优化'}")
    return state


def _check_single(title: str, platform: str, content: str) -> Dict:
    """检查单篇文章质量"""
    if not content:
        return {'overall_score': 0, 'pass': False, 'reason': '内容为空'}

    try:
        prompt = CHECK_PROMPT.format(
            title=title,
            platform=platform,
            content=content[:4000]
        )

        response = OLLAMA_CLIENT.chat.completions.create(
            model='gemma4:latest',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.2
        )

        result_text = response.choices[0].message.content.strip()
        if '```' in result_text:
            result_text = result_text.split('```')[1]
            if result_text.startswith('json'):
                result_text = result_text[4:]

        return json.loads(result_text)

    except json.JSONDecodeError:
        return {'overall_score': 70, 'pass': False, 'reason': '评分解析失败'}
    except Exception as e:
        logger.error(f"质量检查失败: {title[:30]} ({platform}) - {e}")
        return {'overall_score': 60, 'pass': False, 'reason': str(e)}
