"""
野望Agent - LangGraph工作流主类
编排7个节点完成从热点扫描到文章生成的完整流水线
"""
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from utils.logger import setup_logger
from agent.vector_store import VectorStore
from agent.nodes.scanner import scan_trending
from agent.nodes.evaluator import evaluate_topics
from agent.nodes.collector import collect_content
from agent.nodes.analyzer import analyze_content
from agent.nodes.planner import plan_articles
from agent.nodes.writer import write_articles
from agent.nodes.checker import check_quality

logger = setup_logger('yewang_agent')


class AgentState(TypedDict, total=False):
    """Agent完整状态定义"""
    # 向量存储
    vector_store: Any
    # 扫描阶段
    raw_topics: List[Dict]
    scan_time: float
    # 评估阶段
    evaluated_topics: List[Dict]
    # 采集阶段
    collected_content: List[Dict]
    # 分析阶段
    analyzed_content: List[Dict]
    # 策划阶段
    planned_articles: List[Dict]
    # 写作阶段
    written_articles: List[Dict]
    # 质量检查阶段
    checked_articles: List[Dict]
    quality_pass: bool
    # 错误信息
    error: Optional[str]


def _should_optimize(state: Dict) -> str:
    """条件路由：质量检查后决定是否需要优化"""
    if state.get('quality_pass', True):
        return 'done'
    return 'needs_optimization'


class YewangAgent:
    """野望Agent - 热点追踪到内容生成的自动化流水线"""

    def __init__(self):
        self.graph = self._build_graph()
        self.vector_store = VectorStore()
        logger.info("YewangAgent initialized")

    def _build_graph(self) -> StateGraph:
        """构建LangGraph工作流"""
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("scan", scan_trending)
        workflow.add_node("evaluate", evaluate_topics)
        workflow.add_node("collect", collect_content)
        workflow.add_node("analyze", analyze_content)
        workflow.add_node("plan", plan_articles)
        workflow.add_node("write", write_articles)
        workflow.add_node("check", check_quality)

        # 设置入口
        workflow.set_entry_point("scan")

        # 线性流程
        workflow.add_edge("scan", "evaluate")
        workflow.add_edge("evaluate", "collect")
        workflow.add_edge("collect", "analyze")
        workflow.add_edge("analyze", "plan")
        workflow.add_edge("plan", "write")
        workflow.add_edge("write", "check")

        # 条件路由：质量检查后
        workflow.add_conditional_edges(
            "check",
            _should_optimize,
            {
                'done': END,
                'needs_optimization': END
            }
        )

        return workflow.compile()

    def run(self) -> Dict:
        """
        执行完整流水线

        Returns:
            最终状态字典
        """
        logger.info("========== 野望Agent 开始执行 ==========")

        initial_state: AgentState = {
            'vector_store': self.vector_store,
            'raw_topics': [],
            'evaluated_topics': [],
            'collected_content': [],
            'analyzed_content': [],
            'planned_articles': [],
            'written_articles': [],
            'checked_articles': [],
            'quality_pass': False,
            'error': None
        }

        try:
            final_state = self.graph.invoke(initial_state)

            # 输出摘要
            checked = final_state.get('checked_articles', [])
            quality_pass = final_state.get('quality_pass', False)

            logger.info("========== 执行完成 ==========")
            logger.info(f"生成文章数: {len(checked)}")
            logger.info(f"质量全部达标: {quality_pass}")

            if not quality_pass:
                needs_opt = [a for a in checked if a.get('needs_optimization')]
                logger.warning(f"需优化文章数: {len(needs_opt)}")

            return final_state

        except Exception as e:
            logger.error(f"Agent执行失败: {e}", exc_info=True)
            return {'error': str(e)}

    def run_from(self, start_node: str, state: Dict) -> Dict:
        """
        从指定节点开始执行（用于重试）

        Args:
            start_node: 起始节点名
            state: 初始状态

        Returns:
            最终状态字典
        """
        logger.info(f"从 {start_node} 节点重新执行")
        state['vector_store'] = self.vector_store

        try:
            final_state = self.graph.invoke(state)
            return final_state
        except Exception as e:
            logger.error(f"Agent执行失败: {e}", exc_info=True)
            return {'error': str(e)}
