"""
浏览器管理器 - 管理Playwright浏览器生命周期、反检测和资源池化
"""
import asyncio
import os
import threading
from typing import Optional, Dict, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import random
from utils.logger import setup_logger
from crawler.proxy_manager import ProxyManager

logger = setup_logger('browser_manager')


class BrowserManager:
    """Playwright浏览器管理器 - 支持反检测、资源池化和Chrome登录态复用"""

    # 用户代理池
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]

    def __init__(self,
                 headless: bool = True,
                 max_contexts: int = 3,
                 proxy_manager: Optional[ProxyManager] = None,
                 chrome_user_data_dir: str = '',
                 cdp_url: str = ''):
        """
        初始化浏览器管理器

        Args:
            headless: 是否无头模式
            max_contexts: 最大并发浏览器上下文数
            proxy_manager: 代理管理器实例
            chrome_user_data_dir: Chrome用户数据目录（未使用）
            cdp_url: Chrome DevTools Protocol URL，如 http://localhost:9222
        """
        self.headless = headless
        self.max_contexts = max_contexts
        self.proxy_manager = proxy_manager
        self.chrome_user_data_dir = chrome_user_data_dir
        self.cdp_url = cdp_url

        self.playwright = None
        self.browser: Optional[Browser] = None
        self.contexts: List[BrowserContext] = []
        self._initialized = False
        self._init_lock = asyncio.Lock()
        self._context_lock = asyncio.Lock()
        self._cookies: List[Dict] = []  # Chrome导出的cookies
        self._is_cdp_browser = False  # 是否通过CDP连接

    async def initialize(self):
        """初始化Playwright和浏览器"""
        async with self._init_lock:
            if self._initialized:
                return

            try:
                self.playwright = await async_playwright().start()

                # 优先通过CDP连接运行中的Chrome（复用登录态）
                if self.cdp_url:
                    try:
                        self.browser = await self.playwright.chromium.connect_over_cdp(self.cdp_url)
                        self._is_cdp_browser = True
                        self._initialized = True
                        logger.info(f"通过CDP连接Chrome成功 ({self.cdp_url})，复用登录态")
                        return
                    except Exception as e:
                        logger.warning(f"CDP连接失败: {e}，回退到独立浏览器模式")

                # 回退：启动独立浏览器
                self.browser = await self.playwright.chromium.launch(
                    headless=self.headless,
                    channel='chrome',
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-web-security',
                        '--disable-features=IsolateOrigins,site-per-process',
                    ]
                )
                self._initialized = True
                logger.info(f"浏览器初始化成功 (headless={self.headless})")
            except Exception as e:
                logger.error(f"浏览器初始化失败: {e}")
                raise

    async def get_context(self, use_proxy: bool = True) -> BrowserContext:
        """
        创建新的浏览器上下文（线程安全）
        CDP模式下直接使用现有contexts

        Args:
            use_proxy: 是否使用代理（CDP模式下忽略）

        Returns:
            浏览器上下文
        """
        if not self._initialized:
            await self.initialize()

        # CDP模式：使用浏览器的默认context（包含登录态）
        if self._is_cdp_browser:
            contexts = self.browser.contexts
            if contexts:
                return contexts[0]
            # 如果没有context，创建一个
            return await self.browser.new_context()

        # 独立浏览器模式：创建新context
        context_options = self._get_context_options()

        # 添加代理配置
        if use_proxy and self.proxy_manager:
            proxy = self.proxy_manager.get_proxy()
            if proxy:
                context_options['proxy'] = {
                    'server': proxy['server']
                }
                if 'username' in proxy:
                    context_options['proxy']['username'] = proxy['username']
                    context_options['proxy']['password'] = proxy['password']
                logger.debug(f"使用代理: {proxy['server']}")

        context = await self.browser.new_context(**context_options)
        await self._apply_stealth(context)

        async with self._context_lock:
            self.contexts.append(context)
            ctx_count = len(self.contexts)
        logger.debug(f"创建新浏览器上下文 (当前: {ctx_count})")

        return context

    def _get_context_options(self) -> Dict:
        """生成随机化的浏览器上下文配置"""
        # 随机视口大小
        viewport_width = random.randint(1280, 1920)
        viewport_height = random.randint(720, 1080)

        # 随机用户代理
        user_agent = random.choice(self.USER_AGENTS)

        return {
            'viewport': {'width': viewport_width, 'height': viewport_height},
            'user_agent': user_agent,
            'locale': 'zh-CN',
            'timezone_id': 'Asia/Shanghai',
            'permissions': ['geolocation'],
            'geolocation': {'latitude': 39.9042, 'longitude': 116.4074},  # 北京
            'color_scheme': 'light',
            'accept_downloads': False,
            'ignore_https_errors': True,
        }

    async def _apply_stealth(self, context: BrowserContext):
        """
        应用反检测措施到浏览器上下文

        Args:
            context: 浏览器上下文
        """
        # 注入反检测脚本
        await context.add_init_script("""
            // 覆盖 navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // 覆盖 chrome 对象
            window.chrome = {
                runtime: {}
            };

            // 覆盖 permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // 覆盖 plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // 覆盖 languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en']
            });
        """)

    async def create_page(self, context: BrowserContext) -> Page:
        """
        在上下文中创建新页面

        Args:
            context: 浏览器上下文

        Returns:
            页面对象
        """
        page = await context.new_page()

        # 设置默认超时
        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(30000)

        return page

    async def close_context(self, context: BrowserContext):
        """
        关闭浏览器上下文（线程安全）
        CDP模式下不关闭context（共享的），只关闭page
        """
        try:
            if self._is_cdp_browser:
                return  # CDP模式不关闭context

            async with self._context_lock:
                if context in self.contexts:
                    self.contexts.remove(context)
            await context.close()
            logger.debug("浏览器上下文已关闭")
        except Exception as e:
            logger.error(f"关闭浏览器上下文失败: {e}")

    async def cleanup(self):
        """清理所有资源"""
        try:
            # 关闭所有上下文
            for context in self.contexts:
                await context.close()
            self.contexts.clear()

            # 关闭浏览器
            if self.browser:
                await self.browser.close()

            # 停止Playwright
            if self.playwright:
                await self.playwright.stop()

            self._initialized = False
            logger.info("浏览器资源清理完成")
        except Exception as e:
            logger.error(f"清理浏览器资源失败: {e}")

    async def simulate_human_behavior(self, page: Page):
        """
        模拟人类行为

        Args:
            page: 页面对象
        """
        try:
            # 随机滚动
            scroll_count = random.randint(1, 3)
            for _ in range(scroll_count):
                scroll_y = random.randint(300, 800)
                await page.evaluate(f"window.scrollBy(0, {scroll_y})")
                await asyncio.sleep(random.uniform(0.5, 1.5))

            # 随机鼠标移动
            viewport_size = page.viewport_size
            if viewport_size:
                x = random.randint(100, viewport_size['width'] - 100)
                y = random.randint(100, viewport_size['height'] - 100)
                await page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.2, 0.5))

        except Exception as e:
            logger.debug(f"模拟人类行为失败: {e}")

    async def wait_for_content(self, page: Page, selectors: List[str], timeout: int = 10000) -> bool:
        """
        等待页面内容加载（尝试多个选择器）

        Args:
            page: 页面对象
            selectors: 选择器列表
            timeout: 超时时间（毫秒）

        Returns:
            是否成功加载
        """
        for selector in selectors:
            try:
                await page.wait_for_selector(selector, timeout=timeout, state='visible')
                logger.debug(f"内容加载成功: {selector}")
                return True
            except Exception:
                continue

        logger.warning(f"所有选择器都未找到: {selectors}")
        return False

    def __enter__(self):
        """同步上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """同步上下文管理器出口"""
        if self._initialized:
            asyncio.run(self.cleanup())

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.cleanup()
