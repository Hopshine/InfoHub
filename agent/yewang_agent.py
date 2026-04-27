"""
野望Agent - 基于LangGraph的ReAct智能决策Agent

核心特性：
1. ReAct模式：Think → Act → Observe 循环
2. 动态决策：根据配置和当前状态自主选择下一步
3. 质量反馈：选题不够好时自动扩大范围重新评估
4. 账号对齐：确保生成内容符合公众号定位
"""

import json
import asyncio
from typing import Dict, List, Optional, TypedDict, Annotated
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_anthropic import ChatAnthropic


class AgentState(TypedDict):
    """Agent状态"""
    messages: List
    batch_id: str
    config: Dict
    scanned_topics: List[Dict]
    collected_topics: List[Dict]
    evaluated_topics: List[Dict]
    selected_topics: List[Dict]
    generated_articles: List[Dict]
    current_step: str
    iteration: int
    max_iterations: int
    decision_log: List[Dict]


class YewangAgent:
    """野望Agent - ReAct决策引擎"""

    def __init__(self, db, llm_config: Dict = None):
        self.db = db
        self.llm_config = llm_config or {}
        self.llm = self._init_llm()
        self.graph = self._build_graph()

    def _init_llm(self):
        """初始化LLM"""
        # 从配置读取，默认使用Anthropic
        api_key = self.llm_config.get('api_key', 'your-api-key')
        model = self.llm_config.get('model', 'claude-3-5-sonnet-20241022')
        return ChatAnthropic(
            api_key=api_key,
            model=model,
            temperature=0.7,
        )

    def _build_graph(self):
        """构建LangGraph决策图"""
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("think", self.think_node)
        workflow.add_node("scan", self.scan_node)
        workflow.add_node("collect_evaluate", self.collect_evaluate_node)
        workflow.add_node("select_refine", self.select_refine_node)
        workflow.add_node("write", self.write_node)
        workflow.add_node("finish", self.finish_node)

        # 设置入口
        workflow.set_entry_point("think")

        # 添加条件边：think节点根据决策路由到不同节点
        workflow.add_conditional_edges(
            "think",
            self.route_decision,
            {
                "scan": "scan",
                "collect_evaluate": "collect_evaluate",
                "select_refine": "select_refine",
                "write": "write",
                "finish": "finish",
            }
        )

        # 其他节点完成后回到think
        workflow.add_edge("scan", "think")
        workflow.add_edge("collect_evaluate", "think")
        workflow.add_edge("select_refine", "think")
        workflow.add_edge("write", "think")
        workflow.add_edge("finish", END)

        return workflow.compile()

    async def think_node(self, state: AgentState) -> AgentState:
        """思考节点：分析当前状态，决定下一步行动"""
        config = state['config']
        target_count = config['generation']['target_count']

        # 构建思考提示
        system_prompt = f"""你是野望Agent的决策大脑。根据当前状态，决定下一步行动。

当前状态：
- 已扫描话题数：{len(state.get('scanned_topics', []))}
- 已采集评估话题数：{len(state.get('collected_topics', []))}
- 已评估通过话题数：{len(state.get('evaluated_topics', []))}
- 已精选话题数：{len(state.get('selected_topics', []))}
- 已生成文章数：{len(state.get('generated_articles', []))}
- 目标文章数：{target_count}
- 当前迭代：{state['iteration']}/{state['max_iterations']}

配置要求：
- 话题关键词：{config['topics']['keywords']}
- 话题描述：{config['topics']['description']}
- 最低质量分：{config['generation']['min_quality_score']}

可选行动：
1. scan - 扫描热点（当话题不足时）
2. collect_evaluate - 采集内容并评估（当有未处理的扫描话题时）
3. select_refine - 精选话题并优化（当评估话题足够但精选不足时）
4. write - 生成文章（当精选话题足够时）
5. finish - 完成（当达到目标或超过最大迭代次数时）

请分析当前状态，给出下一步行动及理由。"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content="请决定下一步行动。只返回JSON格式：{\"action\": \"行动名称\", \"reason\": \"理由\"}")
        ]

        response = await self.llm.ainvoke(messages)

        try:
            decision = json.loads(response.content)
        except:
            # 如果解析失败，使用规则决策
            decision = self._rule_based_decision(state)

        # 记录决策
        state['decision_log'].append({
            'timestamp': datetime.now().isoformat(),
            'iteration': state['iteration'],
            'decision': decision,
            'state_summary': {
                'scanned': len(state.get('scanned_topics', [])),
                'collected': len(state.get('collected_topics', [])),
                'evaluated': len(state.get('evaluated_topics', [])),
                'selected': len(state.get('selected_topics', [])),
                'generated': len(state.get('generated_articles', [])),
            }
        })

        state['current_step'] = decision['action']
        state['messages'].append(AIMessage(content=f"决策：{decision['action']} - {decision['reason']}"))
        state['iteration'] += 1

        return state

    def _rule_based_decision(self, state: AgentState) -> Dict:
        """基于规则的决策（LLM失败时的后备）"""
        config = state['config']
        target_count = config['generation']['target_count']

        scanned_count = len(state.get('scanned_topics', []))
        evaluated_count = len(state.get('evaluated_topics', []))
        selected_count = len(state.get('selected_topics', []))
        generated_count = len(state.get('generated_articles', []))

        # 决策逻辑
        if generated_count >= target_count:
            return {"action": "finish", "reason": "已达到目标文章数"}

        if state['iteration'] >= state['max_iterations']:
            return {"action": "finish", "reason": "达到最大迭代次数"}

        if selected_count >= target_count:
            return {"action": "write", "reason": "精选话题充足，开始写作"}

        if evaluated_count >= target_count * 2:
            return {"action": "select_refine", "reason": "评估话题充足，进行精选"}

        if scanned_count > 0:
            return {"action": "collect_evaluate", "reason": "有待处理的扫描话题"}

        return {"action": "scan", "reason": "话题不足，需要扫描"}

    def route_decision(self, state: AgentState) -> str:
        """路由决策到对应节点"""
        return state['current_step']

    async def scan_node(self, state: AgentState) -> AgentState:
        """扫描节点：从4个平台采集热点"""
        from collector.trending_collector import TrendingCollector

        collector = TrendingCollector()
        platforms = ['weibo', 'zhihu', 'baidu', 'douyin']

        all_topics = []
        for platform in platforms:
            try:
                if platform == 'weibo':
                    items = await asyncio.to_thread(collector.collect_weibo)
                elif platform == 'zhihu':
                    items = await asyncio.to_thread(collector.collect_zhihu)
                elif platform == 'baidu':
                    items = await asyncio.to_thread(collector.collect_baidu)
                elif platform == 'douyin':
                    items = await asyncio.to_thread(collector.collect_douyin)
                else:
                    items = []

                for item in items:
                    item['platform'] = platform
                    # 保存到数据库
                    try:
                        existing = self.db.get_trending_by_title(platform, item.get('title', ''))
                        if not existing:
                            self.db.save_trending_item(item)
                    except:
                        pass

                all_topics.extend(items)
            except Exception as e:
                print(f"扫描{platform}失败: {e}")

        # 去重
        seen_titles = set()
        unique_topics = []
        for topic in all_topics:
            title = topic.get('title', '').strip()
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_topics.append(topic)

        state['scanned_topics'] = unique_topics
        state['messages'].append(AIMessage(content=f"扫描完成：获取{len(unique_topics)}个话题"))

        return state

    async def collect_evaluate_node(self, state: AgentState) -> AgentState:
        """采集评估节点：获取内容并用LLM评估"""
        from collector.hotnews_article_collector import HotNewsArticleCollector
        from agent.topic_evaluator import TopicEvaluator

        collector = HotNewsArticleCollector()
        evaluator = TopicEvaluator(self.db)
        config = state['config']

        # 取未处理的话题
        topics_to_process = state.get('scanned_topics', [])[:20]  # 每次处理20个

        evaluated = []
        for topic in topics_to_process:
            # 1. 采集内容
            try:
                result = await asyncio.to_thread(
                    collector.collect_from_hotnews,
                    {
                        'title': topic.get('title', ''),
                        'url': topic.get('url', ''),
                        'source': topic.get('platform', ''),
                    }
                )
                if result:
                    topic['_content'] = result.get('content', '')
            except:
                topic['_content'] = ''

            # 2. LLM评估（包含内容）
            try:
                eval_result = await asyncio.to_thread(evaluator.evaluate, topic, None)
                if eval_result.get('selected'):
                    topic['_eval_score'] = eval_result.get('total_score', 0)
                    topic['_eval_grade'] = eval_result.get('grade', 'C')
                    topic['_eval_result'] = eval_result
                    evaluated.append(topic)
            except Exception as e:
                print(f"评估失败: {e}")

        state['collected_topics'] = state.get('collected_topics', []) + topics_to_process
        state['evaluated_topics'] = state.get('evaluated_topics', []) + evaluated
        state['scanned_topics'] = state.get('scanned_topics', [])[20:]  # 移除已处理的

        state['messages'].append(AIMessage(content=f"采集评估完成：{len(evaluated)}/{len(topics_to_process)}通过"))

        return state

    async def select_refine_node(self, state: AgentState) -> AgentState:
        """精选优化节点：选择Top话题，检查是否符合账号定位"""
        config = state['config']
        target_count = config['generation']['target_count']
        min_score = config['generation']['min_quality_score']

        # 按分数排序
        evaluated = state.get('evaluated_topics', [])
        evaluated.sort(key=lambda t: t.get('_eval_score', 0), reverse=True)

        # 取Top N
        candidates = evaluated[:target_count * 2]  # 取2倍候选

        # 用LLM检查是否符合账号定位
        account_id = config['linked_accounts'].get('wechat_account_id')
        account_info = ""
        if account_id:
            account = self.db.get_wechat_account(account_id)
            if account:
                account_info = f"公众号：{account.get('name', '')}\n话题关键词：{account.get('topic_keywords', '')}\n风格偏好：{account.get('style_preference', '')}"

        topic_desc = config['topics'].get('description', '')
        keywords = config['topics'].get('keywords', [])

        system_prompt = f"""你是内容策划专家。从候选话题中精选{target_count}个最适合的话题。

账号定位：
{account_info}

话题要求：
- 描述：{topic_desc}
- 关键词：{', '.join(keywords)}
- 最低分数：{min_score}

候选话题：
{json.dumps([{'title': t.get('title'), 'score': t.get('_eval_score'), 'grade': t.get('_eval_grade')} for t in candidates], ensure_ascii=False, indent=2)}

请选择最符合定位的{target_count}个话题，返回JSON数组：[话题索引列表]"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content="请返回精选话题的索引数组，如 [0, 2, 5, ...]")
        ]

        try:
            response = await self.llm.ainvoke(messages)
            selected_indices = json.loads(response.content)
            selected = [candidates[i] for i in selected_indices if i < len(candidates)]
        except:
            # 降级：直接取Top N
            selected = candidates[:target_count]

        # 如果精选数量不足，记录需要扩大范围
        if len(selected) < target_count:
            state['messages'].append(AIMessage(content=f"精选话题不足（{len(selected)}/{target_count}），需要扩大扫描范围"))
            # 清空已评估话题，强制重新扫描
            state['evaluated_topics'] = []
        else:
            state['selected_topics'] = selected
            state['messages'].append(AIMessage(content=f"精选完成：选出{len(selected)}个话题"))

        return state

    async def write_node(self, state: AgentState) -> AgentState:
        """写作节点：为精选话题生成文章"""
        from generator.article_generator import ArticleGenerator
        from config_loader import LLMConfigLoader

        llm_config = LLMConfigLoader.get_config(self.db, 'article_generation')
        generator = ArticleGenerator(config=llm_config)

        selected = state.get('selected_topics', [])
        batch_id = state['batch_id']

        generated = []
        for topic in selected:
            try:
                result = await asyncio.to_thread(
                    generator.generate_article,
                    {'title': topic.get('title', ''), 'source': topic.get('platform', '')}
                )

                if result and result.get('content'):
                    # 保存到数据库
                    article_data = {
                        'topic_title': topic.get('title', ''),
                        'platform': topic.get('platform', ''),
                        'hot_value': str(topic.get('hot_value', '')),
                        'article_type': 'wechat',
                        'title': result.get('title', topic.get('title', '')),
                        'content': result.get('content', ''),
                        'summary': result.get('summary', ''),
                        'keywords': result.get('keywords', ''),
                        'status': 'draft',
                        'batch_id': batch_id,
                    }
                    article_id = self.db.create_agent_article(article_data)
                    result['id'] = article_id
                    generated.append(result)
            except Exception as e:
                print(f"生成文章失败: {e}")

        state['generated_articles'] = state.get('generated_articles', []) + generated
        state['messages'].append(AIMessage(content=f"生成完成：{len(generated)}篇文章"))

        return state

    async def finish_node(self, state: AgentState) -> AgentState:
        """完成节点：总结并结束"""
        summary = {
            'batch_id': state['batch_id'],
            'scanned': len(state.get('scanned_topics', [])),
            'evaluated': len(state.get('evaluated_topics', [])),
            'selected': len(state.get('selected_topics', [])),
            'generated': len(state.get('generated_articles', [])),
            'iterations': state['iteration'],
            'decisions': state['decision_log'],
        }

        state['messages'].append(AIMessage(content=f"任务完成：{json.dumps(summary, ensure_ascii=False)}"))

        return state

    async def run(self, batch_id: str, config: Dict) -> Dict:
        """运行Agent"""
        initial_state = AgentState(
            messages=[],
            batch_id=batch_id,
            config=config,
            scanned_topics=[],
            collected_topics=[],
            evaluated_topics=[],
            selected_topics=[],
            generated_articles=[],
            current_step="scan",
            iteration=0,
            max_iterations=10,
            decision_log=[],
        )

        final_state = await self.graph.ainvoke(initial_state)

        return {
            'success': True,
            'batch_id': batch_id,
            'generated_count': len(final_state.get('generated_articles', [])),
            'iterations': final_state['iteration'],
            'decisions': final_state['decision_log'],
        }
