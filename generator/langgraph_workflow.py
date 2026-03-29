"""
LangGraph 智能文章生成工作流
"""
from typing import TypedDict, List, Dict, Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage
import json
from utils.logger import setup_logger

logger = setup_logger('workflow')


class WorkflowState(TypedDict):
    """工作流状态"""
    hotnews_id: int
    hotnews_title: str
    hotnews_summary: str
    matched_accounts: List[int]
    current_account_id: int
    account_name: str
    account_style: str
    custom_prompt: str
    generated_title: str
    generated_content: str
    generated_summary: str
    generated_keywords: str
    quality_score: float
    quality_issues: List[str]
    review_decision: str
    article_id: int
    error: str


def analyze_hotnews(state: WorkflowState) -> WorkflowState:
    """分析热点新闻，提取关键信息"""
    logger.info(f"分析热点: {state['hotnews_title']}")
    # 简化实现：直接使用原始信息
    return state


def match_accounts(state: WorkflowState, db) -> WorkflowState:
    """匹配适合的公众号"""
    logger.info("匹配公众号...")
    accounts = db.get_wechat_accounts(active_only=True)

    if not accounts:
        state['error'] = '没有可用的公众号配置'
        return state

    # 简化匹配：基于关键词匹配
    matched = []
    title_lower = state['hotnews_title'].lower()

    for acc in accounts:
        keywords = acc.get('topic_keywords', '')
        if keywords:
            kw_list = [k.strip() for k in keywords.split(',')]
            if any(kw.lower() in title_lower for kw in kw_list if kw):
                matched.append(acc['id'])

    # 如果没有匹配，使用所有公众号
    if not matched:
        matched = [acc['id'] for acc in accounts]

    state['matched_accounts'] = matched
    logger.info(f"匹配到 {len(matched)} 个公众号")
    return state


def generate_content(state: WorkflowState, generator, db) -> WorkflowState:
    """生成文章内容"""
    account_id = state['current_account_id']
    account = db.get_wechat_account(account_id)

    if not account:
        state['error'] = f'公众号配置不存在: {account_id}'
        return state

    state['account_name'] = account['name']
    state['account_style'] = account.get('style_preference', 'news')
    state['custom_prompt'] = account.get('custom_prompt', '')

    logger.info(f"为公众号 [{account['name']}] 生成文章...")

    news = {
        'id': state['hotnews_id'],
        'title': state['hotnews_title'],
        'summary': state['hotnews_summary']
    }

    article = generator.generate_article(news, state['account_style'])
    state['generated_title'] = article['title']
    state['generated_content'] = article['content']
    state['generated_summary'] = article['summary']
    state['generated_keywords'] = article['keywords']

    return state


def quality_check(state: WorkflowState) -> WorkflowState:
    """高级质量检查"""
    logger.info("执行质量检查...")

    content = state['generated_content']
    title = state['generated_title']
    issues = []
    score = 1.0

    # 长度检查
    if len(content) < 500:
        issues.append('内容过短（少于500字）')
        score -= 0.3
    elif len(content) < 800:
        issues.append('内容偏短（少于800字）')
        score -= 0.1

    # 标题检查
    if len(title) < 10 or len(title) > 40:
        issues.append('标题长度不合适')
        score -= 0.1

    # 段落结构检查
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
    if len(paragraphs) < 3:
        issues.append('段落过少，结构不够清晰')
        score -= 0.2

    # 敏感词检查（简化版）
    sensitive_words = ['敏感', '违规', '政治']
    if any(word in content for word in sensitive_words):
        issues.append('可能包含敏感内容')
        score -= 0.3

    state['quality_score'] = max(0.0, score)
    state['quality_issues'] = issues

    logger.info(f"质量评分: {state['quality_score']:.2f}, 问题: {len(issues)}")
    return state


def human_review(state: WorkflowState) -> WorkflowState:
    """人工审核节点（暂停等待）"""
    logger.info("等待人工审核...")
    # 此节点会暂停工作流，等待外部输入
    return state


def save_draft(state: WorkflowState, db) -> WorkflowState:
    """保存文章草稿"""
    logger.info("保存文章草稿...")

    article = {
        'hotnews_id': state['hotnews_id'],
        'title': state['generated_title'],
        'content': state['generated_content'],
        'summary': state['generated_summary'],
        'keywords': state['generated_keywords'],
        'style': state['account_style'],
        'status': 'draft'
    }

    article_id = db.insert_generated_article(article)
    if article_id:
        state['article_id'] = article_id
        db.update_hotnews_status(state['hotnews_id'], 'processed')
        logger.info(f"文章已保存 [ID: {article_id}]")
    else:
        state['error'] = '保存文章失败'

    return state


def decide_next_step(state: WorkflowState) -> Literal["save_draft", "human_review"]:
    """决定下一步：直接保存或人工审核"""
    if state['quality_score'] >= 0.7:
        return "save_draft"
    return "human_review"


def check_review_decision(state: WorkflowState) -> Literal["save_draft", "generate_content", END]:
    """检查审核决定"""
    decision = state.get('review_decision', '')
    if decision == 'approve':
        return "save_draft"
    elif decision == 'regenerate':
        return "generate_content"
    return END


def create_workflow_graph(db, generator):
    """创建工作流图"""
    from langgraph.graph import StateGraph, END

    workflow = StateGraph(WorkflowState)

    # 添加节点
    workflow.add_node("analyze_hotnews", analyze_hotnews)
    workflow.add_node("match_accounts", lambda state: match_accounts(state, db))
    workflow.add_node("generate_content", lambda state: generate_content(state, generator, db))
    workflow.add_node("quality_check", quality_check)
    workflow.add_node("human_review", human_review)
    workflow.add_node("save_draft", lambda state: save_draft(state, db))

    # 设置入口
    workflow.set_entry_point("analyze_hotnews")

    # 添加边
    workflow.add_edge("analyze_hotnews", "match_accounts")
    workflow.add_edge("match_accounts", "generate_content")
    workflow.add_edge("generate_content", "quality_check")

    # 条件路由：质量检查后
    workflow.add_conditional_edges(
        "quality_check",
        decide_next_step,
        {
            "save_draft": "save_draft",
            "human_review": "human_review"
        }
    )

    # 条件路由：人工审核后
    workflow.add_conditional_edges(
        "human_review",
        check_review_decision,
        {
            "save_draft": "save_draft",
            "generate_content": "generate_content",
            END: END
        }
    )

    # 保存后结束
    workflow.add_edge("save_draft", END)

    return workflow.compile()

