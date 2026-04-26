from typing import Dict, Optional
from utils.logger import setup_logger
from config import Config

logger = setup_logger('analyzer')

class ContentAnalyzer:
    """内容分析器，支持 Anthropic 和 OpenAI 兼容 API"""

    def __init__(self, api_key: str = None, base_url: str = None, provider: str = None, config: Optional[Dict] = None):
        """
        初始化分析器

        Args:
            api_key: API密钥（向后兼容）
            base_url: API地址（向后兼容）
            provider: 提供商类型（向后兼容）
            config: 配置字典 {provider_type, api_key, base_url, model, max_tokens}
        """
        if config:
            self.provider = config['provider_type']
            self.api_key = config['api_key']
            self.base_url = config['base_url']
            self.model = config['model']
            self.max_tokens = config.get('max_tokens', 2000)
        else:
            # 向后兼容旧参数方式
            self.provider = provider or Config.LLM_PROVIDER
            self.api_key = api_key or Config.LLM_API_KEY
            self.base_url = base_url or Config.LLM_BASE_URL
            self.model = Config.ANALYSIS_MODEL
            self.max_tokens = 2000

        if self.provider == 'openai' or self.provider == 'ollama':
            from openai import OpenAI
            kwargs = {'api_key': self.api_key or 'ollama'}
            if self.base_url:
                kwargs['base_url'] = self.base_url
            self.client = OpenAI(**kwargs)
        else:
            from anthropic import Anthropic
            kwargs = {'api_key': self.api_key}
            if self.base_url:
                kwargs['base_url'] = self.base_url
            self.client = Anthropic(**kwargs)

    def analyze_article(self, article: Dict) -> Dict:
        """分析单篇文章"""
        title = article.get('title', '')
        content = article.get('content', '')

        if not content:
            logger.warning(f"文章内容为空，跳过分析: {title}")
            return {
                'summary': '',
                'keywords': '',
                'category': '',
                'analysis': ''
            }

        logger.info(f"开始分析文章: {title}")

        try:
            prompt = self._build_analysis_prompt(title, content)

            if self.provider == 'openai' or self.provider == 'ollama':
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=2000,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                response_text = response.choices[0].message.content
            else:
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                # 处理anthropic返回的content（可能包含ThinkingBlock）
                response_text = ''
                for block in message.content:
                    if hasattr(block, 'text'):
                        response_text += block.text
                    elif hasattr(block, 'type') and block.type == 'text':
                        response_text += block.text if hasattr(block, 'text') else str(block)
            result = self._parse_analysis_result(response_text)

            logger.info(f"文章分析完成: {title}")
            return result

        except Exception as e:
            logger.error(f"分析文章失败 {title}: {str(e)}")
            return {
                'summary': '',
                'keywords': '',
                'category': '',
                'analysis': f'分析失败: {str(e)}'
            }

    def _build_analysis_prompt(self, title: str, content: str) -> str:
        """构建分析提示词"""
        return f"""请分析以下文章内容。

文章标题：{title}

文章内容：
{content[:4000]}

请按以下格式输出分析结果：

【摘要】
用2-3句话概括文章核心内容

【关键词】
提取5-8个关键词，用逗号分隔

【分类】
根据文章实际内容选择最合适的分类，如：时事政治、社会民生、财经商业、科技数码、娱乐八卦、体育竞技、国际局势、文化教育、生活健康、军事国防、法治司法、其他

【深度分析】
从以下角度进行分析：
1. 核心事件和关键信息
2. 事件背景和来龙去脉
3. 各方观点和社会影响
4. 后续发展趋势判断
"""

    def _parse_analysis_result(self, response: str) -> Dict:
        """解析分析结果"""
        result = {
            'summary': '',
            'keywords': '',
            'category': '',
            'analysis': response
        }

        try:
            lines = response.split('\n')
            current_section = None

            for line in lines:
                line = line.strip()

                if '【摘要】' in line:
                    current_section = 'summary'
                    continue
                elif '【关键词】' in line:
                    current_section = 'keywords'
                    continue
                elif '【分类】' in line:
                    current_section = 'category'
                    continue
                elif '【深度分析】' in line:
                    current_section = 'analysis'
                    continue

                if current_section and line:
                    if current_section == 'summary':
                        result['summary'] += line + ' '
                    elif current_section == 'keywords':
                        result['keywords'] = line
                    elif current_section == 'category':
                        result['category'] = line
                    elif current_section == 'analysis':
                        result['analysis'] += line + '\n'

            # 清理结果
            result['summary'] = result['summary'].strip()
            result['analysis'] = result['analysis'].strip()

        except Exception as e:
            logger.warning(f"解析分析结果失败: {str(e)}")

        return result
