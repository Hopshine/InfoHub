"""
策划节点 - 用Anthropic策划选题角度和大纲
"""
import json
from typing import Dict
from utils.logger import setup_logger
from agent.prompts import PLAN_PROMPT
from config_loader import LLMConfigLoader
from storage.database import Database

logger = setup_logger('node.planner')


def _get_anthropic_client():
    """获取Anthropic客户端配置"""
    db = Database()
    config = LLMConfigLoader.get_config(db, 'article_generation')
    return config


def plan_articles(state: Dict) -> Dict:
    """
    策划选题角度和大纲

    Args:
        state: Agent状态字典

    Returns:
        更新后的状态 {planned_articles: [...]}
    """
    logger.info("=== 开始策划选题 ===")

    analyzed = state.get('analyzed_content', [])
    if not analyzed:
        logger.warning("没有待策划的内容")
        state['planned_articles'] = []
        return state

    config = _get_anthropic_client()

    from openai import OpenAI
    client = OpenAI(
        api_key=config['api_key'],
        base_url=config['base_url'] if config['base_url'] else None
    )

    planned = []
    for item in analyzed:
        title = item.get('title', '')
        analysis = json.dumps(item.get('analysis', {}), ensure_ascii=False)

        try:
            prompt = PLAN_PROMPT.format(title=title, analysis=analysis)

            response = client.chat.completions.create(
                model=config['model'],
                messages=[{'role': 'user', 'content': prompt}],
                max_tokens=config.get('max_tokens', 2000),
                temperature=0.7
            )

            result_text = response.choices[0].message.content.strip()
            if '```' in result_text:
                result_text = result_text.split('```')[1]
                if result_text.startswith('json'):
                    result_text = result_text[4:]

            plan = json.loads(result_text)
            item['plan'] = plan
            planned.append(item)

            logger.info(f"策划完成: {title[:30]} -> {len(plan.get('angles', []))}个角度")

        except json.JSONDecodeError as e:
            logger.warning(f"策划结果解析失败: {title[:30]} - {e}")
            item['plan'] = {'angles': [{'title': title, 'outline': [], 'style': 'wechat'}]}
            planned.append(item)
        except Exception as e:
            logger.error(f"策划失败: {title[:30]} - {e}")
            item['plan'] = {'angles': [{'title': title, 'outline': [], 'style': 'wechat'}]}
            planned.append(item)

    logger.info(f"选题策划完成，共 {len(planned)} 个话题")
    state['planned_articles'] = planned
    return state
