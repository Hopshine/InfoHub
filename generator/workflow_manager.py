"""
工作流管理器 - 封装 LangGraph 工作流执行
"""
from typing import Dict, List, Optional
import uuid
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from langgraph.checkpoint.sqlite import SqliteSaver
from generator.langgraph_workflow import create_workflow_graph, WorkflowState
from generator.article_generator import ArticleGenerator
from utils.logger import setup_logger

logger = setup_logger('workflow_manager')


class WorkflowManager:
    """工作流管理器"""

    def __init__(self, db, db_path: str):
        self.db = db
        self.db_path = db_path
        self.generator = ArticleGenerator()
        self.checkpointer = SqliteSaver.from_conn_string(db_path)
        self.app = create_workflow_graph(db, self.generator)

    def run(self, hotnews_id: int, parallel: bool = True) -> List[Dict]:
        """执行工作流，支持并行处理多个公众号"""
        news_item = self.db.get_hotnews_by_id(hotnews_id)

        if not news_item:
            logger.error(f"热点新闻不存在: {hotnews_id}")
            return []

        logger.info(f"启动工作流: {news_item['title']}")

        # 获取活跃的公众号
        accounts = self.db.get_wechat_accounts(active_only=True)
        if not accounts:
            logger.warning("没有可用的公众号配置")
            return []

        # 简单匹配：基于关键词
        matched_accounts = []
        title_lower = news_item['title'].lower()

        for acc in accounts:
            keywords = acc.get('topic_keywords', '')
            if keywords:
                kw_list = [k.strip() for k in keywords.split(',')]
                if any(kw.lower() in title_lower for kw in kw_list if kw):
                    matched_accounts.append(acc['id'])

        # 如果没有匹配，使用所有公众号
        if not matched_accounts:
            matched_accounts = [acc['id'] for acc in accounts]

        logger.info(f"匹配到 {len(matched_accounts)} 个公众号")

        # 并行或顺序处理
        if parallel and len(matched_accounts) > 1:
            return self._run_parallel(hotnews_id, news_item, matched_accounts)
        else:
            return self._run_sequential(hotnews_id, news_item, matched_accounts)

    def _run_single_account(self, hotnews_id: int, news_item: Dict, account_id: int) -> Dict:
        """为单个公众号执行工作流"""
        thread_id = f"{hotnews_id}_{account_id}_{uuid.uuid4().hex[:8]}"

        initial_state: WorkflowState = {
            'hotnews_id': hotnews_id,
            'hotnews_title': news_item['title'],
            'hotnews_summary': news_item.get('summary', ''),
            'matched_accounts': [account_id],
            'current_account_id': account_id,
            'account_name': '',
            'account_style': 'news',
            'custom_prompt': '',
            'generated_title': '',
            'generated_content': '',
            'generated_summary': '',
            'generated_keywords': '',
            'quality_score': 0.0,
            'quality_issues': [],
            'review_decision': '',
            'article_id': 0,
            'error': ''
        }

        config = {"configurable": {"thread_id": thread_id}}

        try:
            result = self.app.invoke(initial_state, config)
            self.db.insert_workflow_state({
                'thread_id': thread_id,
                'hotnews_id': hotnews_id,
                'account_id': account_id,
                'current_node': result.get('review_decision') and 'human_review' or 'completed',
                'state_data': json.dumps(result, ensure_ascii=False),
                'status': 'pending' if result.get('quality_score', 1.0) < 0.7 else 'completed'
            })
            return {'thread_id': thread_id, 'result': result}
        except Exception as e:
            logger.error(f"工作流执行失败 [账号 {account_id}]: {e}")
            return {'thread_id': thread_id, 'error': str(e)}

    def _run_parallel(self, hotnews_id: int, news_item: Dict, account_ids: List[int]) -> List[Dict]:
        """并行处理多个公众号"""
        logger.info(f"并行处理 {len(account_ids)} 个公众号")
        results = []

        with ThreadPoolExecutor(max_workers=min(len(account_ids), 5)) as executor:
            futures = {
                executor.submit(self._run_single_account, hotnews_id, news_item, acc_id): acc_id
                for acc_id in account_ids
            }

            for future in as_completed(futures):
                acc_id = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"并行执行失败 [账号 {acc_id}]: {e}")
                    results.append({'account_id': acc_id, 'error': str(e)})

        return results

    def _run_sequential(self, hotnews_id: int, news_item: Dict, account_ids: List[int]) -> List[Dict]:
        """顺序处理多个公众号"""
        logger.info(f"顺序处理 {len(account_ids)} 个公众号")
        results = []
        for acc_id in account_ids:
            result = self._run_single_account(hotnews_id, news_item, acc_id)
            results.append(result)
        return results

    def resume(self, thread_id: str, review_decision: str) -> Dict:
        """恢复工作流并提交审核决定"""
        logger.info(f"恢复工作流: {thread_id}, 决定: {review_decision}")

        workflow_state = self.db.get_workflow_state(thread_id)
        if not workflow_state:
            return {'error': '工作流不存在'}

        state_data = json.loads(workflow_state['state_data'])
        state_data['review_decision'] = review_decision

        config = {"configurable": {"thread_id": thread_id}}

        try:
            result = self.graph.invoke(state_data, config)
            self.db.update_workflow_state(thread_id, {
                'state_data': json.dumps(result, ensure_ascii=False),
                'status': 'completed' if result.get('article_id') else 'failed'
            })
            return {'thread_id': thread_id, 'result': result}
        except Exception as e:
            logger.error(f"恢复工作流失败: {e}")
            return {'thread_id': thread_id, 'error': str(e)}

    def get_pending_reviews(self) -> List[Dict]:
        """获取待审核的工作流"""
        return self.db.get_pending_workflows()

    def get_visualization(self) -> str:
        """获取工作流可视化（Mermaid格式）"""
        try:
            return self.app.get_graph().draw_mermaid()
        except Exception as e:
            logger.error(f"生成可视化失败: {e}")
            return ""

