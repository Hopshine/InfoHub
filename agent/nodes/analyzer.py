"""
分析节点 - 用Ollama深度分析内容，提取观点
"""
import json
from typing import Dict
from openai import OpenAI
from utils.logger import setup_logger
from agent.prompts import ANALYZE_PROMPT

logger = setup_logger('node.analyzer')

OLLAMA_CLIENT = OpenAI(base_url='http://localhost:11434/v1', api_key='ollama')


def analyze_content(state: Dict) -> Dict:
    """
    深度分析内容，提取观点

    Args:
        state: Agent状态字典

    Returns:
        更新后的状态 {analyzed_content: [...]}
    """
    logger.info("=== 开始深度分析 ===")

    collected = state.get('collected_content', [])
    if not collected:
        logger.warning("没有待分析的内容")
        state['analyzed_content'] = []
        return state

    analyzed = []
    for item in collected:
        title = item.get('title', '')
        content = item.get('content', '')

        # 截断过长内容
        if len(content) > 5000:
            content = content[:5000] + "..."

        try:
            prompt = ANALYZE_PROMPT.format(title=title, content=content)

            response = OLLAMA_CLIENT.chat.completions.create(
                model='gemma4:latest',
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.3
            )

            result_text = response.choices[0].message.content.strip()
            if '```' in result_text:
                result_text = result_text.split('```')[1]
                if result_text.startswith('json'):
                    result_text = result_text[4:]

            analysis = json.loads(result_text)
            item['analysis'] = analysis
            analyzed.append(item)

            logger.info(f"分析完成: {title[:30]}")

        except json.JSONDecodeError as e:
            logger.warning(f"分析结果解析失败: {title[:30]} - {e}")
            item['analysis'] = {
                'core_event': title,
                'key_viewpoints': [],
                'potential_angles': [title]
            }
            analyzed.append(item)
        except Exception as e:
            logger.error(f"分析失败: {title[:30]} - {e}")
            item['analysis'] = {'core_event': title, 'key_viewpoints': [], 'potential_angles': []}
            analyzed.append(item)

    logger.info(f"深度分析完成，共 {len(analyzed)} 篇")
    state['analyzed_content'] = analyzed
    return state
