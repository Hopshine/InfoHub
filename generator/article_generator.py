"""
微信公众号文章生成器 - 基于热点新闻使用LLM生成文章
支持风格：资讯(news)、评论(comment)、深度(deep)
"""
from typing import Dict, Optional
from utils.logger import setup_logger
from config import Config

logger = setup_logger('generator')

STYLE_PROMPTS = {
    'news': {
        'name': '资讯速报',
        'instruction': '以新闻资讯的风格撰写，语言简洁客观，重点突出事实和数据。',
        'structure': '导语（1段）+ 正文（3-4段，每段一个要点）+ 结尾总结（1段）',
    },
    'comment': {
        'name': '热点评论',
        'instruction': '以评论分析的风格撰写，有观点有态度，结合背景深入分析。',
        'structure': '引入话题（1段）+ 背景分析（1-2段）+ 观点论述（2-3段）+ 总结展望（1段）',
    },
    'deep': {
        'name': '深度解读',
        'instruction': '以深度报道的风格撰写，全面详尽，多角度分析，引用数据和案例。',
        'structure': '导语引入（1段）+ 事件回顾（1-2段）+ 深度分析（3-4段）+ 影响展望（1-2段）+ 结语（1段）',
    },
}


class ArticleGenerator:
    """微信公众号文章生成器"""

    def __init__(self, api_key: str = None, provider: str = None):
        self.provider = provider or Config.LLM_PROVIDER
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = Config.LLM_BASE_URL
        self.model = Config.ARTICLE_MODEL
        self.max_tokens = Config.ARTICLE_MAX_TOKENS

        if self.provider == 'openai':
            from openai import OpenAI
            kwargs = {'api_key': self.api_key}
            if self.base_url:
                kwargs['base_url'] = self.base_url
            self.client = OpenAI(**kwargs)
        else:
            from anthropic import Anthropic
            kwargs = {'api_key': self.api_key}
            if self.base_url:
                kwargs['base_url'] = self.base_url
            self.client = Anthropic(**kwargs)

    def _call_llm(self, prompt: str) -> str:
        """调用LLM API"""
        if self.provider == 'openai':
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        else:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text

    def generate_article(self, news: Dict, style: str = None) -> Dict:
        """基于热点新闻生成完整文章"""
        style = style or Config.ARTICLE_STYLE
        if style not in STYLE_PROMPTS:
            style = 'news'

        title = news.get('title', '')
        summary = news.get('summary', '')
        source = news.get('source', '')

        logger.info(f"开始生成文章 [{STYLE_PROMPTS[style]['name']}]: {title}")

        try:
            # 生成文章标题
            gen_title = self._generate_title(title, summary, style)
            # 生成文章正文
            content = self._generate_content(title, summary, gen_title, style)
            # 生成摘要和关键词
            meta = self._generate_meta(gen_title, content)

            result = {
                'hotnews_id': news.get('id'),
                'title': gen_title,
                'content': content,
                'summary': meta.get('summary', ''),
                'keywords': meta.get('keywords', ''),
                'style': style,
                'status': 'draft',
            }
            logger.info(f"文章生成完成: {gen_title}")
            return result

        except Exception as e:
            logger.error(f"文章生成失败 [{title}]: {e}")
            return {
                'hotnews_id': news.get('id'),
                'title': f'【生成失败】{title}',
                'content': f'生成失败: {e}',
                'summary': '',
                'keywords': '',
                'style': style,
                'status': 'failed',
            }

    def _generate_title(self, news_title: str, summary: str, style: str) -> str:
        """生成吸引人的文章标题"""
        style_info = STYLE_PROMPTS[style]
        prompt = f"""你是一位资深的微信公众号编辑。请根据以下热点新闻，生成一个吸引人的公众号文章标题。

热点标题：{news_title}
相关摘要：{summary}
文章风格：{style_info['name']}

要求：
- 标题要吸引眼球，适合微信公众号传播
- 不要使用标题党，保持信息准确
- 长度控制在15-30个字
- 只输出标题文本，不要加引号或其他标记"""

        return self._call_llm(prompt).strip().strip('"\'""''')

    def _generate_content(self, news_title: str, summary: str,
                          article_title: str, style: str) -> str:
        """生成文章正文"""
        style_info = STYLE_PROMPTS[style]
        prompt = f"""你是一位资深的微信公众号内容创作者。请根据以下信息撰写一篇完整的公众号文章。

原始热点：{news_title}
相关信息：{summary}
文章标题：{article_title}

写作风格：{style_info['name']}
风格要求：{style_info['instruction']}
文章结构：{style_info['structure']}

写作要求：
1. 内容充实，有深度，不少于800字
2. 语言流畅自然，适合微信公众号阅读
3. 段落清晰，适当使用小标题
4. 结尾要有总结或引发思考
5. 不要在文章开头重复标题
6. 直接输出文章正文，不要加"正文："等前缀"""

        return self._call_llm(prompt).strip()

    def _generate_meta(self, title: str, content: str) -> Dict:
        """生成文章摘要和关键词"""
        prompt = f"""请为以下微信公众号文章生成摘要和关键词。

标题：{title}
正文：{content[:2000]}

请按以下格式输出：
【摘要】用1-2句话概括文章核心内容，适合作为公众号文章的摘要展示
【关键词】提取5-8个关键词，用逗号分隔"""

        response = self._call_llm(prompt)
        result = {'summary': '', 'keywords': ''}
        current = None
        for line in response.split('\n'):
            line = line.strip()
            if '【摘要】' in line:
                current = 'summary'
                text = line.split('【摘要】')[-1].strip()
                if text:
                    result['summary'] = text
                continue
            elif '【关键词】' in line:
                current = 'keywords'
                text = line.split('【关键词】')[-1].strip()
                if text:
                    result['keywords'] = text
                continue
            if current and line:
                if current == 'summary' and not result['summary']:
                    result['summary'] = line
                elif current == 'keywords' and not result['keywords']:
                    result['keywords'] = line
        return result

    def generate_and_save(self, db, news: Dict, style: str = None) -> Optional[int]:
        """生成文章并保存到数据库"""
        article = self.generate_article(news, style)
        article_id = db.insert_generated_article(article)
        if article_id:
            # 标记热点新闻为已处理
            if news.get('id'):
                db.update_hotnews_status(news['id'], 'processed')
            logger.info(f"文章已保存 [ID: {article_id}]: {article['title']}")
        return article_id
