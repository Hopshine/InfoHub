"""
Workflow Engine - 话题工作流状态机和执行器
"""
import asyncio
import uuid
import json
from datetime import datetime
from typing import Dict, List, Optional
from utils.logger import setup_logger

logger = setup_logger('workflow_engine')


class TopicWorkflow:
    """单个话题的工作流实例"""
    STAGES = ['pending', 'collecting', 'analyzing', 'planning', 'writing', 'checking', 'completed', 'failed']

    def __init__(self, workflow_id: str, topic_data: Dict, db, batch_id: str):
        self.id = workflow_id
        self.topic = topic_data
        self.db = db
        self.batch_id = batch_id
        self.current_stage = 'pending'
        self.status = 'waiting'
        self.retry_count = 0
        self.article_id = None
        self.quality_score = 0.0
        self.error_message = None
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at

        # 持久化到数据库
        self._persist_to_db()

    def _persist_to_db(self):
        """持久化workflow到数据库"""
        workflow_data = {
            'id': self.id,
            'batch_id': self.batch_id,
            'topic_title': self.topic.get('title', ''),
            'platform': self.topic.get('platform', ''),
            'hot_value': str(self.topic.get('hot_value', '')),
            'current_stage': self.current_stage,
            'status': self.status,
            'retry_count': self.retry_count,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'completed_at': None,
            'collect_result': None,
            'analysis_result': None,
            'plan_result': None,
            'article_id': self.article_id,
            'quality_score': self.quality_score,
            'decisions': None,
        }
        self.db.create_topic_workflow(workflow_data)

    async def transition_to(self, next_stage: str, action: str = 'proceed', reason: str = ''):
        """状态转换并记录到数据库"""
        old_stage = self.current_stage
        self.current_stage = next_stage
        self.updated_at = datetime.now().isoformat()

        # 记录transition
        transition_data = {
            'workflow_id': self.id,
            'from_stage': old_stage,
            'to_stage': next_stage,
            'action': action,
            'reason': reason,
            'timestamp': self.updated_at,
        }
        await asyncio.to_thread(self.db.create_workflow_transition, transition_data)

        # 更新workflow状态
        updates = {
            'current_stage': self.current_stage,
            'updated_at': self.updated_at,
        }
        if next_stage == 'completed':
            updates['completed_at'] = self.updated_at
            updates['status'] = 'completed'
            self.status = 'completed'
        elif next_stage == 'failed':
            updates['status'] = 'failed'
            self.status = 'failed'

        await asyncio.to_thread(self.db.update_topic_workflow, self.id, updates)

        logger.info(f"Workflow {self.id}: {old_stage} -> {next_stage} ({action}): {reason}")

    async def execute_stage(self, stage_name: str):
        """执行当前阶段"""
        try:
            if stage_name == 'pending':
                await self.transition_to('collecting')
            elif stage_name == 'collecting':
                await self._collect()
            elif stage_name == 'analyzing':
                await self._analyze()
            elif stage_name == 'planning':
                await self._plan()
            elif stage_name == 'writing':
                await self._write()
            elif stage_name == 'checking':
                await self._check()
        except Exception as e:
            logger.error(f"Workflow {self.id} stage {stage_name} failed: {e}")
            self.error_message = str(e)
            await self.transition_to('failed', 'error', str(e))
            raise

    async def retry_stage(self, stage_name: str):
        """重试当前阶段"""
        self.retry_count += 1
        logger.info(f"Workflow {self.id} retrying {stage_name}, attempt {self.retry_count}")
        await self.execute_stage(stage_name)

    async def _collect(self):
        """采集阶段 - 获取话题相关内容"""
        from collector.hotnews_article_collector import HotNewsArticleCollector
        collector = HotNewsArticleCollector()
        result = await asyncio.to_thread(
            collector.collect_from_hotnews,
            {
                'title': self.topic.get('title', ''),
                'url': self.topic.get('url', ''),
                'source': self.topic.get('platform', ''),
            }
        )
        if result:
            self.topic['_content'] = result.get('content', '')
            # 存储采集结果到数据库
            await asyncio.to_thread(self.db.update_topic_workflow, self.id, {
                'collect_result': json.dumps(result, ensure_ascii=False),
                'updated_at': datetime.now().isoformat()
            })
            await self.transition_to('analyzing', 'proceed', 'Content collected')
        else:
            raise Exception("Failed to collect content")

    async def _analyze(self):
        """分析阶段 - 分析内容"""
        from analyzer.content_analyzer import ContentAnalyzer
        from config_loader import LLMConfigLoader

        content = self.topic.get('_content', '')
        if not content:
            await self.transition_to('planning', 'skip', 'No content to analyze')
            return

        llm_config = LLMConfigLoader.get_config(self.db, 'content_analysis')
        analyzer = ContentAnalyzer(config=llm_config)
        result = await asyncio.to_thread(
            analyzer.analyze_article,
            {'title': self.topic.get('title', ''), 'content': content}
        )
        self.topic['_analysis'] = result
        # 存储分析结果到数据库
        await asyncio.to_thread(self.db.update_topic_workflow, self.id, {
            'analysis_result': json.dumps(result, ensure_ascii=False),
            'updated_at': datetime.now().isoformat()
        })
        await self.transition_to('planning', 'proceed', 'Analysis completed')

    async def _plan(self):
        """规划阶段 - 文章大纲"""
        # 目前的实现较简单，保留topic数据传递
        # 存储策划结果（即使是简单的pass-through）
        plan_data = {
            'topic': self.topic.get('title', ''),
            'analysis': self.topic.get('_analysis', {}),
            'approach': 'direct_generation'
        }
        await asyncio.to_thread(self.db.update_topic_workflow, self.id, {
            'plan_result': json.dumps(plan_data, ensure_ascii=False),
            'updated_at': datetime.now().isoformat()
        })
        await self.transition_to('writing', 'proceed', 'Plan ready')

    async def _write(self):
        """写作阶段 - 生成文章"""
        from generator.article_generator import ArticleGenerator
        from config_loader import LLMConfigLoader

        llm_config = LLMConfigLoader.get_config(self.db, 'article_generation')
        generator = ArticleGenerator(config=llm_config)

        result = await asyncio.to_thread(
            generator.generate_article,
            {'title': self.topic.get('title', ''), 'source': self.topic.get('platform', '')}
        )

        if not result or not result.get('content'):
            raise Exception("Article generation failed")

        batch_id = self.topic.get('_batch_id')
        article_id = await asyncio.to_thread(self.db.create_agent_article, {
            'topic_title': self.topic.get('title', ''),
            'platform': self.topic.get('platform', ''),
            'hot_value': str(self.topic.get('hot_value', '')),
            'article_type': 'wechat',
            'title': result.get('title', self.topic.get('title', '')),
            'content': result.get('content', ''),
            'summary': result.get('summary', ''),
            'keywords': result.get('keywords', ''),
            'status': 'draft',
            'batch_id': batch_id,
        })
        self.article_id = article_id
        await asyncio.to_thread(self.db.update_topic_workflow, self.id, {
            'article_id': article_id, 'updated_at': datetime.now().isoformat()
        })
        await self.transition_to('checking', 'proceed', f'Article {article_id} written')

    async def _check(self):
        """质量检查阶段"""
        if not self.article_id:
            raise Exception("No article_id to check")

        article = await asyncio.to_thread(self.db.get_agent_article, self.article_id)
        if not article:
            raise Exception(f"Article {self.article_id} not found")

        # 使用简化的质量评分
        score = self._calculate_quality_score(article)
        self.quality_score = score

        await asyncio.to_thread(self.db.update_agent_article, self.article_id, {
            'quality_score': score,
            'quality_detail': json.dumps({'final_score': score}, ensure_ascii=False),
        })
        await asyncio.to_thread(self.db.update_topic_workflow, self.id, {
            'quality_score': score, 'updated_at': datetime.now().isoformat()
        })

        self.status = 'completed'
        await self.transition_to('completed', 'proceed', f'Quality score: {score}')

    def _calculate_quality_score(self, article: Dict) -> float:
        """简化的质量评分 - 基于启发式规则"""
        content = article.get('content', '') or ''
        title = article.get('title', '') or ''

        score = 0.5  # 基础分

        # 标题
        if 10 <= len(title) <= 50:
            score += 0.1
        # 内容长度
        content_len = len(content)
        if 800 <= content_len <= 2500:
            score += 0.2
        elif 500 <= content_len < 800:
            score += 0.1

        # 关键词
        if article.get('keywords'):
            score += 0.05
        # 摘要
        if article.get('summary'):
            score += 0.05
        # 段落
        paragraphs = [p for p in content.split('\n\n') if p.strip()]
        if len(paragraphs) >= 3:
            score += 0.1

        return round(min(score, 1.0), 2)


class WorkflowExecutor:
    """工作流执行器 - 管理多个TopicWorkflow并行执行"""

    def __init__(self, db, batch_id: str, max_workers: int = 5):
        self.db = db
        self.batch_id = batch_id
        self.workflows: Dict[str, TopicWorkflow] = {}
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.max_workers = max_workers
        self.on_workflow_update = None  # 可选回调，用于状态更新

    async def create_workflows(self, topics: List[Dict]):
        """为每个话题创建workflow实例"""
        for topic in topics:
            wf_id = f"wf_{uuid.uuid4().hex[:8]}"
            topic['_batch_id'] = self.batch_id
            wf = TopicWorkflow(wf_id, topic, self.db, self.batch_id)
            wf.current_stage = 'collecting'
            self.workflows[wf_id] = wf
            await self.task_queue.put(wf)

    async def run(self):
        """启动worker池并行处理"""
        workers = [asyncio.create_task(self._worker()) for _ in range(self.max_workers)]
        await self.task_queue.join()
        for w in workers:
            w.cancel()
        # 等待取消完成
        await asyncio.gather(*workers, return_exceptions=True)

    async def _worker(self):
        """Worker从队列拉取任务执行整个工作流"""
        while True:
            try:
                wf = await self.task_queue.get()
            except asyncio.CancelledError:
                break

            try:
                # 顺序执行剩余阶段直到completed或failed
                terminal_stages = {'completed', 'failed'}
                safety_limit = 20
                steps = 0
                while wf.current_stage not in terminal_stages and steps < safety_limit:
                    stage = wf.current_stage
                    try:
                        await wf.execute_stage(stage)
                    except Exception as e:
                        logger.error(f"Workflow {wf.id} stage {stage} error: {e}")
                        wf.status = 'failed'
                        wf.current_stage = 'failed'
                        break
                    steps += 1
                    if self.on_workflow_update:
                        try:
                            self.on_workflow_update(wf)
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f"Workflow {wf.id} failed: {e}")
            finally:
                self.task_queue.task_done()

    def get_summary(self) -> Dict:
        """获取所有workflow的汇总状态"""
        summary = {'total': len(self.workflows), 'completed': 0, 'failed': 0, 'workflows': []}
        for wf in self.workflows.values():
            wf_info = {
                'id': wf.id,
                'title': wf.topic.get('title', ''),
                'stage': wf.current_stage,
                'status': wf.status,
                'article_id': wf.article_id,
                'quality_score': wf.quality_score,
                'error': wf.error_message,
            }
            summary['workflows'].append(wf_info)
            if wf.current_stage == 'completed':
                summary['completed'] += 1
            elif wf.current_stage == 'failed':
                summary['failed'] += 1
        return summary


async def compose_wechat_draft(db, batch_id: str) -> Optional[int]:
    """所有workflow完成后，编排推送草稿"""
    # 使用已有的批次文章查询
    articles = await asyncio.to_thread(db.get_agent_articles_by_batch, batch_id)
    if not articles:
        logger.warning(f"No articles found for batch {batch_id}")
        return None

    # 只保留质量分>=0.7的完成文章
    def _score(a):
        try:
            return float(a.get('quality_score') or 0)
        except (TypeError, ValueError):
            return 0.0

    completed = [a for a in articles if (a.get('status') in ('draft', 'completed')) and _score(a) >= 0.7]
    completed.sort(key=_score, reverse=True)
    selected = completed[:8]

    if len(selected) < 2:
        logger.warning(f"Not enough articles for draft: {len(selected)}")
        return None

    draft_data = {
        'batch_id': batch_id,
        'title': f"今日热点精选 {len(selected)}篇",
        'article_ids': json.dumps([a['id'] for a in selected]),
        'article_count': len(selected),
        'status': 'draft',
        'created_at': datetime.now().isoformat(),
    }

    if hasattr(db, 'create_wechat_draft'):
        draft_id = await asyncio.to_thread(db.create_wechat_draft, draft_data)
        logger.info(f"Created wechat draft {draft_id} with {len(selected)} articles")
        return draft_id

    logger.warning("db.create_wechat_draft not available; skipping draft creation")
    return None
