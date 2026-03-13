from anthropic import Anthropic
from typing import Dict
from utils.logger import setup_logger
from config import Config

logger = setup_logger('analyzer')

class ContentAnalyzer:
    """内容分析器，使用Claude API分析文章"""

    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.model = Config.ANALYSIS_MODEL

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

            message = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = message.content[0].text
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
        return f"""请分析以下微信公众号文章，这是一篇关于大模型/AI的文章。

文章标题：{title}

文章内容：
{content[:4000]}

请按以下格式输出分析结果：

【摘要】
用2-3句话概括文章核心内容

【关键词】
提取5-8个关键词，用逗号分隔

【分类】
从以下类别中选择最合适的一个：技术解读、行业动态、产品评测、应用案例、观点评论、教程指南

【深度分析】
从以下角度进行分析：
1. 主要观点和论据
2. 技术创新点或亮点
3. 实用价值和应用场景
4. 潜在影响和趋势判断
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
