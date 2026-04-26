"""
话题评估器 - 使用LLM进行多维度评估
"""
import json
import time
import subprocess
from typing import Dict, Optional
from openai import OpenAI
from config_loader import LLMConfigLoader
from utils.logger import setup_logger

logger = setup_logger('topic_evaluator')


class TopicEvaluator:
    """话题评估器 - 使用LLM进行智能评估"""

    # 系统提示词模板
    SYSTEM_PROMPT = """你是一个专业的内容评估专家，负责评估热点话题是否适合创作微信公众号文章。

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

    EVALUATION_PROMPT = """请评估以下热点话题：

标题：{title}
平台：{platform}
热度值：{hot_value}
链接：{url}

请从5个维度进行评分，并给出详细理由。返回JSON格式：
{{
  "scores": {{
    "热度价值": {{"score": 0-25, "reason": "评分理由"}},
    "标题质量": {{"score": 0-20, "reason": "评分理由"}},
    "话题性": {{"score": 0-25, "reason": "评分理由"}},
    "内容潜力": {{"score": 0-15, "reason": "评分理由"}},
    "时效性": {{"score": 0-15, "reason": "评分理由"}}
  }},
  "total_score": 0-100,
  "grade": "S/A/B/C",
  "selected": true/false,
  "summary": "总体评价（1-2句话）"
}}"""

    def __init__(self, db):
        """初始化评估器"""
        self.db = db
        self.client = None
        self.config = None
        self._init_client()

    def _check_ollama(self) -> bool:
        """检查Ollama是否运行，如果没有则尝试启动"""
        try:
            # 检查ollama list命令
            result = subprocess.run(['ollama', 'list'],
                                  capture_output=True,
                                  text=True,
                                  timeout=5)
            if result.returncode == 0:
                logger.info("Ollama已运行")
                # 检查是否有可用模型
                if 'NAME' in result.stdout:
                    models = [line.split()[0] for line in result.stdout.split('\n')[1:] if line.strip()]
                    if models:
                        logger.info(f"可用模型: {', '.join(models[:5])}")
                        return True
                logger.warning("Ollama运行中但没有可用模型")
                return True
            return False
        except FileNotFoundError:
            logger.error("Ollama未安装")
            return False
        except subprocess.TimeoutExpired:
            logger.warning("Ollama命令超时")
            return False
        except Exception as e:
            logger.error(f"检查Ollama失败: {e}")
            return False

    def _init_client(self):
        """初始化LLM客户端"""
        try:
            self.config = LLMConfigLoader.get_config(self.db, 'topic_evaluation')
            provider = self.config['provider_type']

            if provider == 'ollama':
                if not self._check_ollama():
                    logger.warning("Ollama未运行，将使用规则评估")
                    return

            if provider in ('openai', 'ollama'):
                self.client = OpenAI(
                    api_key=self.config['api_key'] or 'ollama',
                    base_url=self.config['base_url'] or None
                )
            elif provider == 'anthropic':
                from anthropic import Anthropic
                kwargs = {'api_key': self.config['api_key']}
                if self.config['base_url']:
                    kwargs['base_url'] = self.config['base_url']
                self.client = Anthropic(**kwargs)
            else:
                logger.warning(f"不支持的provider类型: {provider}")
                return

            logger.info(f"LLM客户端初始化成功: {provider} - {self.config['model']}")
        except Exception as e:
            logger.error(f"初始化LLM客户端失败: {e}")

    def evaluate(self, topic: Dict, llm_logger=None) -> Dict:
        """
        评估话题 - 必须使用LLM，不降级

        Args:
            topic: 话题信息 {title, platform, hot_value, url}
            llm_logger: LLM日志记录器

        Returns:
            评估结果 {scores, total_score, grade, selected, summary}

        Raises:
            Exception: LLM调用失败时抛出异常
        """
        if not self.client:
            raise Exception("LLM客户端未初始化，无法进行评估")

        start_time = time.time()

        # 构建提示词
        prompt = self.EVALUATION_PROMPT.format(
            title=topic.get('title', ''),
            platform=topic.get('platform', '未知'),
            hot_value=topic.get('hot_value', '0'),
            url=topic.get('url', '无')
        )

        provider = self.config['provider_type']

        if provider == 'anthropic':
            response = self.client.messages.create(
                model=self.config['model'],
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=self.config.get('max_tokens', 1000)
            )
            duration_ms = int((time.time() - start_time) * 1000)
            content = response.content[0].text.strip()
            p_tokens = response.usage.input_tokens if hasattr(response, 'usage') else 0
            c_tokens = response.usage.output_tokens if hasattr(response, 'usage') else 0
        else:
            response = self.client.chat.completions.create(
                model=self.config['model'],
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=self.config.get('max_tokens', 1000)
            )
            duration_ms = int((time.time() - start_time) * 1000)
            content = response.choices[0].message.content.strip()
            p_tokens = response.usage.prompt_tokens if hasattr(response, 'usage') else 0
            c_tokens = response.usage.completion_tokens if hasattr(response, 'usage') else 0

        # 记录LLM调用
        if llm_logger:
            llm_logger.log(
                model=self.config['model'],
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
                duration_ms=duration_ms,
                stage='evaluate',
                status='success'
            )

        # 解析JSON结果
        result = self._parse_llm_response(content)
        logger.info(f"LLM评估完成: {topic.get('title', '')[:30]} - {result['grade']}级({result['total_score']}分)")
        return result

    def _parse_llm_response(self, content: str) -> Dict:
        """解析LLM返回的JSON"""
        try:
            # 尝试提取JSON
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()

            result = json.loads(content)

            # 验证必需字段
            if 'scores' not in result or 'total_score' not in result:
                raise ValueError("缺少必需字段")

            # 确保selected字段存在
            if 'selected' not in result:
                result['selected'] = result['total_score'] >= 40

            return result
        except Exception as e:
            logger.error(f"解析LLM响应失败: {e}, content: {content[:200]}")
            raise

    def _rule_based_evaluation(self, topic: Dict) -> Dict:
        """规则评估（降级方案）"""
        title = topic.get('title', '')
        hot_value = topic.get('hot_value', '0')

        try:
            hot_num = int(str(hot_value).replace(',', '') or 0)
        except:
            hot_num = 0

        scores = {}
        total = 0

        # 热度价值
        if hot_num >= 500000:
            scores['热度价值'] = {'score': 25, 'reason': f'超高热度({hot_num:,})'}
        elif hot_num >= 100000:
            scores['热度价值'] = {'score': 20, 'reason': f'高热度({hot_num:,})'}
        elif hot_num >= 10000:
            scores['热度价值'] = {'score': 15, 'reason': f'中等热度({hot_num:,})'}
        else:
            scores['热度价值'] = {'score': 8, 'reason': f'低热度({hot_num:,})'}
        total += scores['热度价值']['score']

        # 标题质量
        title_len = len(title)
        if 8 <= title_len <= 30:
            scores['标题质量'] = {'score': 15, 'reason': f'长度适中({title_len}字)'}
        else:
            scores['标题质量'] = {'score': 8, 'reason': f'长度一般({title_len}字)'}
        total += scores['标题质量']['score']

        # 话题性
        scores['话题性'] = {'score': 15, 'reason': '一般话题'}
        total += scores['话题性']['score']

        # 内容潜力
        scores['内容潜力'] = {'score': 8, 'reason': '中等潜力'}
        total += scores['内容潜力']['score']

        # 时效性
        scores['时效性'] = {'score': 10, 'reason': '一般时效'}
        total += scores['时效性']['score']

        grade = 'S' if total >= 80 else 'A' if total >= 60 else 'B' if total >= 40 else 'C'

        return {
            'scores': scores,
            'total_score': total,
            'grade': grade,
            'selected': total >= 40,
            'summary': f'规则评估：{grade}级({total}分)'
        }

    def optimize_prompt(self, feedback: str) -> bool:
        """
        根据反馈优化提示词

        Args:
            feedback: 用户反馈

        Returns:
            是否成功优化
        """
        # TODO: 实现提示词自动优化逻辑
        # 可以收集评估结果和用户反馈，定期调整评分标准
        logger.info(f"收到提示词优化反馈: {feedback}")
        return True
