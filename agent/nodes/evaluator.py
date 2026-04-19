"""
评估节点 - 用Ollama评估话题传播价值
"""
import json
from typing import Dict
from openai import OpenAI
from utils.logger import setup_logger
from agent.prompts import EVALUATE_PROMPT

logger = setup_logger('node.evaluator')

# Ollama OpenAI兼容API
OLLAMA_CLIENT = OpenAI(base_url='http://localhost:11434/v1', api_key='ollama')


def evaluate_topics(state: Dict) -> Dict:
    """
    评估话题传播价值，排序取Top5

    Args:
        state: Agent状态字典

    Returns:
        更新后的状态 {evaluated_topics: [...]}
    """
    logger.info("=== 开始评估话题价值 ===")

    raw_topics = state.get('raw_topics', [])
    if not raw_topics:
        logger.warning("没有待评估的话题")
        state['evaluated_topics'] = []
        return state

    evaluated = []
    for topic in raw_topics:
        try:
            title = topic.get('title', '')
            prompt = EVALUATE_PROMPT.format(
                title=title,
                source=topic.get('source', 'unknown'),
                heat=topic.get('heat', 'N/A'),
                summary=topic.get('summary', topic.get('title', ''))
            )

            response = OLLAMA_CLIENT.chat.completions.create(
                model='gemma4:latest',
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.3
            )

            result_text = response.choices[0].message.content.strip()
            # 提取JSON
            if '```' in result_text:
                result_text = result_text.split('```')[1]
                if result_text.startswith('json'):
                    result_text = result_text[4:]

            score_data = json.loads(result_text)
            topic['evaluation'] = score_data
            topic['score'] = score_data.get('score', 0)
            evaluated.append(topic)

            logger.info(f"评估完成: {title[:30]} -> {topic['score']}分")

        except json.JSONDecodeError as e:
            logger.warning(f"评估结果解析失败: {topic.get('title', '')[:30]} - {e}")
            topic['score'] = 50
            topic['evaluation'] = {'score': 50, 'reason': '解析失败，默认评分'}
            evaluated.append(topic)
        except Exception as e:
            logger.error(f"评估失败: {topic.get('title', '')[:30]} - {e}")
            continue

    # 按分数排序，取Top5
    evaluated.sort(key=lambda x: x.get('score', 0), reverse=True)
    top_topics = evaluated[:5]

    logger.info(f"评估完成，Top5话题: {[t.get('title', '')[:20] for t in top_topics]}")

    state['evaluated_topics'] = top_topics
    return state
