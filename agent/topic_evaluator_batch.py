"""
批量话题评估器 - 一次LLM调用评估多个话题
"""
import json
import time
from typing import Dict, List
from openai import OpenAI
from config_loader import LLMConfigLoader
from utils.logger import setup_logger

logger = setup_logger('topic_evaluator_batch')


class BatchTopicEvaluator:
    """批量话题评估器 - 显著提升评估速度"""

    SYSTEM_PROMPT = """你是一个专业的内容评估专家，负责批量评估热点话题是否适合创作微信公众号文章。

评估维度（满分100分）：
1. 热度价值 (0-25分)：话题的传播热度和关注度
2. 标题质量 (0-20分)：标题的吸引力、清晰度和完整性
3. 话题性 (0-25分)：话题的社会价值、讨论空间和受众广度
4. 内容潜力 (0-15分)：可挖掘的内容深度和创作空间
5. 时效性 (0-15分)：话题的新鲜度和时间敏感性

评分标准：
- S级 (80-100分)：顶级话题，强烈推荐
- A级 (60-79分)：优质话题，推荐创作
- B级 (40-59分)：合格话题，可以创作
- C级 (0-39分)：不合格，不推荐

请严格按照JSON格式返回评估结果，不要包含任何其他文字。"""

    def __init__(self, db):
        self.db = db
        self.config = LLMConfigLoader.get_config(db, 'topic_evaluation')
        self.client = OpenAI(
            api_key=self.config['api_key'] or 'ollama',
            base_url=self.config['base_url'] or None
        )

    def evaluate_batch(self, topics: List[Dict], batch_size: int = 10) -> List[Dict]:
        """
        批量评估话题

        Args:
            topics: 话题列表
            batch_size: 每批评估数量（Ollama 默认输出限制约 2048 tokens，10个话题安全）

        Returns:
            评估结果列表
        """
        logger.info(f"开始批量评估: topics={len(topics)}, batch_size={batch_size}, model={self.config.get('model')}")
        results = []

        for i in range(0, len(topics), batch_size):
            batch = topics[i:i + batch_size]
            try:
                batch_results = self._evaluate_one_batch(batch)
                results.extend(batch_results)
            except Exception as e:
                logger.error(f"批量评估失败 (batch {i//batch_size + 1}): {e}")
                logger.warning(f"降级为逐个评估模式（共{len(batch)}个话题）")
                # 降级：逐个评估
                for topic in batch:
                    try:
                        result = self._evaluate_single(topic)
                        results.append(result)
                    except:
                        results.append(self._fallback_result(topic))

        return results

    def _evaluate_one_batch(self, topics: List[Dict]) -> List[Dict]:
        """评估一批话题（一次LLM调用）"""
        start_time = time.time()

        # 构建批量提示词
        topics_text = ""
        for idx, topic in enumerate(topics, 1):
            content = topic.get('_content', '') or ''
            content_preview = content[:400].strip() if content else '（暂无内容）'

            topics_text += f"""
话题{idx}:
- 标题: {topic.get('title', '')}
- 平台: {topic.get('platform', '未知')}
- 热度: {topic.get('hot_value', '0')}
- 内容摘要: {content_preview}

"""

        prompt = f"""请批量评估以下{len(topics)}个热点话题，为每个话题从5个维度进行评分。

{topics_text}

返回JSON数组格式（严格按顺序对应话题1到话题{len(topics)}）：
[
  {{
    "topic_index": 1,
    "scores": {{
      "热度价值": {{"score": 0-25, "reason": "简短理由"}},
      "标题质量": {{"score": 0-20, "reason": "简短理由"}},
      "话题性": {{"score": 0-25, "reason": "简短理由"}},
      "内容潜力": {{"score": 0-15, "reason": "简短理由"}},
      "时效性": {{"score": 0-15, "reason": "简短理由"}}
    }},
    "total_score": 0-100,
    "grade": "S/A/B/C",
    "selected": true/false,
    "summary": "总体评价（1句话）"
  }},
  ...
]"""

        response = self.client.chat.completions.create(
            model=self.config['model'],
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            # gemma4 context 128K，输出侧给 32K 足够覆盖大批量评估
            max_tokens=32768
        )

        duration_ms = int((time.time() - start_time) * 1000)
        content = response.choices[0].message.content.strip()

        # 解析JSON数组
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            content = content.split('```')[1].split('```')[0].strip()

        try:
            batch_results = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}\n内容前500字: {content[:500]}")
            # 自动降级：逐个评估
            logger.warning(f"降级为逐个评估模式")
            batch_results = []
            for topic in topics:
                try:
                    result = self._evaluate_single(topic)
                    batch_results.append(result)
                except Exception as e2:
                    logger.error(f"单个评估也失败: {e2}")
                    batch_results.append(self._fallback_result(topic))
            return batch_results

        # 验证结果数量
        if len(batch_results) != len(topics):
            logger.warning(f"返回结果数量不匹配: 期望{len(topics)}，实际{len(batch_results)}")

        logger.info(f"批量评估完成: {len(topics)}个话题，耗时{duration_ms}ms，平均{duration_ms//len(topics)}ms/个")

        return batch_results

    def _evaluate_single(self, topic: Dict) -> Dict:
        """单个评估（降级方案）"""
        from agent.topic_evaluator import TopicEvaluator
        evaluator = TopicEvaluator(self.db)
        return evaluator.evaluate(topic)

    def _fallback_result(self, topic: Dict) -> Dict:
        """降级结果（评估失败时）"""
        return {
            "scores": {
                "热度价值": {"score": 0, "reason": "评估失败"},
                "标题质量": {"score": 0, "reason": "评估失败"},
                "话题性": {"score": 0, "reason": "评估失败"},
                "内容潜力": {"score": 0, "reason": "评估失败"},
                "时效性": {"score": 0, "reason": "评估失败"}
            },
            "total_score": 0,
            "grade": "C",
            "selected": False,
            "summary": "评估失败"
        }
