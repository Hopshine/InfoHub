import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API配置
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

    # 数据库配置
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/articles.db')

    # 采集配置
    SEARCH_KEYWORDS = os.getenv('SEARCH_KEYWORDS', '大模型,Claude,GPT,AI').split(',')
    MAX_ARTICLES_PER_SEARCH = int(os.getenv('MAX_ARTICLES_PER_SEARCH', 20))

    # 分析配置
    ANALYSIS_MODEL = os.getenv('ANALYSIS_MODEL', 'claude-sonnet-4-6')

    # 爬虫配置
    CRAWL_CONCURRENCY = 3          # 最大并发数
    CRAWL_RATE_LIMIT = 2.0         # 每秒请求数
    CRAWL_RETRY_MAX = 3            # 最大重试次数
    CRAWL_RETRY_BACKOFF = 1.0      # 重试基础延迟(秒)
    CRAWL_REQUEST_TIMEOUT = 20     # 请求超时(秒)
    CRAWL_DEDUP_HAMMING = 3        # simhash汉明距离阈值

    # 搜狗微信搜索配置
    SOGOU_WEIXIN_SEARCH_URL = 'https://weixin.sogou.com/weixin'

    @classmethod
    def validate(cls):
        """验证必要的配置项"""
        if not cls.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY 未设置，请在 .env 文件中配置")
        return True
