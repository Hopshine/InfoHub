import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # LLM API配置
    LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'anthropic')  # anthropic 或 openai
    LLM_API_KEY = os.getenv('LLM_API_KEY', os.getenv('ANTHROPIC_API_KEY', ''))
    LLM_BASE_URL = os.getenv('LLM_BASE_URL', '')  # 自定义API地址，留空则使用官方默认
    ANALYSIS_MODEL = os.getenv('ANALYSIS_MODEL', 'claude-sonnet-4-6')

    # 兼容旧配置
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')

    # 数据库配置
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/articles.db')

    # 采集配置
    SEARCH_KEYWORDS = os.getenv('SEARCH_KEYWORDS', '热点,头条,突发,社会,财经').split(',')
    MAX_ARTICLES_PER_SEARCH = int(os.getenv('MAX_ARTICLES_PER_SEARCH', 20))

    # 爬虫配置
    CRAWL_CONCURRENCY = 3          # 最大并发数
    CRAWL_RATE_LIMIT = 2.0         # 每秒请求数
    CRAWL_RETRY_MAX = 3            # 最大重试次数
    CRAWL_RETRY_BACKOFF = 1.0      # 重试基础延迟(秒)
    CRAWL_REQUEST_TIMEOUT = 20     # 请求超时(秒)
    CRAWL_DEDUP_HAMMING = 3        # simhash汉明距离阈值

    # 搜狗微信搜索配置
    SOGOU_WEIXIN_SEARCH_URL = 'https://weixin.sogou.com/weixin'

    # 微信公众号API配置
    WECHAT_APP_ID = os.getenv('WECHAT_APP_ID', '')
    WECHAT_APP_SECRET = os.getenv('WECHAT_APP_SECRET', '')

    # 热点新闻源配置
    HOTNEWS_SOURCES = os.getenv('HOTNEWS_SOURCES', 'toutiao,baidu,weibo').split(',')
    HOTNEWS_REFRESH_INTERVAL = int(os.getenv('HOTNEWS_REFRESH_INTERVAL', 30))  # 分钟

    # Playwright浏览器配置
    USE_PLAYWRIGHT = os.getenv('USE_PLAYWRIGHT', 'true').lower() == 'true'
    PLAYWRIGHT_HEADLESS = os.getenv('PLAYWRIGHT_HEADLESS', 'true').lower() == 'true'
    PLAYWRIGHT_TIMEOUT = int(os.getenv('PLAYWRIGHT_TIMEOUT', '30000'))  # 毫秒
    MAX_BROWSER_INSTANCES = int(os.getenv('MAX_BROWSER_INSTANCES', '3'))

    # 代理配置
    PROXY_ENABLED = os.getenv('PROXY_ENABLED', 'false').lower() == 'true'
    PROXY_LIST_FILE = os.getenv('PROXY_LIST_FILE', 'config/proxies.txt')
    PROXY_ROTATION = os.getenv('PROXY_ROTATION', 'random')  # random 或 round-robin
    PROXY_MAX_FAILURES = int(os.getenv('PROXY_MAX_FAILURES', '3'))

    # 反检测配置
    RANDOM_DELAY_MIN = float(os.getenv('RANDOM_DELAY_MIN', '1.0'))
    RANDOM_DELAY_MAX = float(os.getenv('RANDOM_DELAY_MAX', '3.0'))
    SIMULATE_HUMAN_BEHAVIOR = os.getenv('SIMULATE_HUMAN_BEHAVIOR', 'true').lower() == 'true'

    # 文章生成配置
    ARTICLE_MODEL = os.getenv('ARTICLE_MODEL', os.getenv('ANALYSIS_MODEL', 'claude-sonnet-4-6'))
    ARTICLE_STYLE = os.getenv('ARTICLE_STYLE', 'news')  # news, comment, deep
    ARTICLE_MAX_TOKENS = int(os.getenv('ARTICLE_MAX_TOKENS', 4000))

    # 调度配置
    SCHEDULER_HOTNEWS_CRON = os.getenv('SCHEDULER_HOTNEWS_CRON', '*/30 * * * *')
    SCHEDULER_GENERATE_CRON = os.getenv('SCHEDULER_GENERATE_CRON', '0 8,12,18 * * *')
    SCHEDULER_PUBLISH_CRON = os.getenv('SCHEDULER_PUBLISH_CRON', '0 9,13,19 * * *')
    SCHEDULER_AUTO_PUBLISH = os.getenv('SCHEDULER_AUTO_PUBLISH', 'false').lower() == 'true'

    @classmethod
    def validate(cls):
        """验证必要的配置项"""
        if not cls.LLM_API_KEY:
            raise ValueError("LLM_API_KEY 未设置，请在 .env 文件中配置")
        if cls.LLM_PROVIDER not in ['anthropic', 'openai']:
            raise ValueError(f"LLM_PROVIDER 必须是 'anthropic' 或 'openai'，当前值: {cls.LLM_PROVIDER}")
        return True

    @classmethod
    def validate_wechat(cls):
        """验证微信公众号配置"""
        if not cls.WECHAT_APP_ID or not cls.WECHAT_APP_SECRET:
            raise ValueError("WECHAT_APP_ID 和 WECHAT_APP_SECRET 未设置")
