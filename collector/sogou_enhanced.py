"""
搜狗微信搜索增强版采集器
模拟真实浏览器行为，避免验证码
"""

import requests
from bs4 import BeautifulSoup
import time
import random
import json
from typing import List, Dict, Optional
from utils.logger import setup_logger
import re
from urllib.parse import urljoin, quote

logger = setup_logger('sogou_collector')


class SogouWeixinCollector:
    """搜狗微信搜索增强版采集器"""

    def __init__(self):
        # 创建Session保持会话
        self.session = requests.Session()

        # 模拟真实浏览器的Headers
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }

        self.session.headers.update(self.headers)

        # 搜狗微信搜索URL
        self.base_url = 'https://weixin.sogou.com'
        self.search_url = 'https://weixin.sogou.com/weixin'

        # 初始化：访问首页获取Cookie
        self._init_session()

    def _init_session(self):
        """初始化会话，访问首页获取Cookie"""
        try:
            logger.info("初始化会话，访问搜狗微信首页...")
            response = self.session.get(self.base_url, timeout=10)

            if response.status_code == 200:
                logger.info(f"首页访问成功，获取到Cookie: {len(self.session.cookies)} 个")
                # 随机延迟，模拟真实用户
                time.sleep(random.uniform(1, 2))
            else:
                logger.warning(f"首页访问失败，状态码: {response.status_code}")

        except Exception as e:
            logger.error(f"初始化会话失败: {str(e)}")

    def search_articles(self, keyword: str, max_results: int = 10, page: int = 1) -> List[Dict]:
        """
        搜索微信文章

        Args:
            keyword: 搜索关键词
            max_results: 最多返回结果数
            page: 页码（从1开始）

        Returns:
            文章列表
        """
        logger.info(f"搜索关键词: {keyword}, 页码: {page}")

        articles = []

        try:
            # 构建搜索参数
            params = {
                'type': 2,  # 2表示搜索文章
                'query': keyword,
                'ie': 'utf8',
                'page': page,
                's_from': 'input',  # 来源：输入框
            }

            # 更新Referer
            self.session.headers.update({
                'Referer': self.base_url + '/',
            })

            # 发送搜索请求
            logger.info(f"发送搜索请求: {self.search_url}")
            response = self.session.get(
                self.search_url,
                params=params,
                timeout=15
            )

            logger.info(f"搜索响应状态码: {response.status_code}")

            if response.status_code == 200:
                # 检查是否遇到验证码
                if self._check_captcha(response.text):
                    logger.warning("遇到验证码，请稍后重试或使用URL导入方式")
                    return []

                # 解析搜索结果
                articles = self._parse_search_results(response.text, max_results)
                logger.info(f"成功解析 {len(articles)} 篇文章")

                # 随机延迟
                time.sleep(random.uniform(2, 4))

            else:
                logger.warning(f"搜索请求失败，状态码: {response.status_code}")

        except Exception as e:
            logger.error(f"搜索出错: {str(e)}")

        return articles

    def _check_captcha(self, html: str) -> bool:
        """检查是否遇到验证码"""
        captcha_keywords = [
            '请输入验证码',
            'antispider',
            'captcha',
            '验证码',
            'id="seccodeImage"',
        ]

        for keyword in captcha_keywords:
            if keyword in html:
                return True

        return False

    def _parse_search_results(self, html: str, max_results: int) -> List[Dict]:
        """解析搜索结果页面"""
        articles = []

        try:
            soup = BeautifulSoup(html, 'lxml')

            # 查找文章列表
            # 搜狗微信的文章列表在 <ul class="news-list"> 中
            news_list = soup.find('ul', class_='news-list')

            if not news_list:
                # 尝试另一种结构
                news_list = soup.find_all('div', class_='news-box')
                logger.info(f"使用备用解析方式，找到 {len(news_list)} 个结果")
            else:
                news_list = news_list.find_all('li')
                logger.info(f"找到 {len(news_list)} 个搜索结果")

            for item in news_list[:max_results]:
                try:
                    article = self._parse_article_item(item)
                    if article:
                        articles.append(article)

                except Exception as e:
                    logger.warning(f"解析单条结果失败: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"解析搜索结果失败: {str(e)}")

        return articles

    def _parse_article_item(self, item) -> Optional[Dict]:
        """解析单个文章项"""
        try:
            # 查找标题和链接
            title_elem = item.find('h3')
            if not title_elem:
                title_elem = item.find('h4')

            if not title_elem:
                return None

            link_elem = title_elem.find('a')
            if not link_elem:
                return None

            title = link_elem.get_text(strip=True)
            url = link_elem.get('href', '')

            # 处理URL
            if url:
                # 如果是相对路径，补全
                if not url.startswith('http'):
                    url = urljoin(self.base_url, url)

                logger.info(f"找到文章: {title[:30]}...")
                logger.info(f"  原始URL: {url[:80]}...")

                # 如果是搜狗跳转链接，尝试获取真实URL
                if 'sogou.com' in url and '/link?' in url:
                    real_url = self._get_real_url(url)
                    if real_url:
                        url = real_url
                        logger.info(f"  真实URL: {url[:80]}...")

            # 提取公众号名称
            account_name = ''
            account_elem = item.find('a', class_='account')
            if not account_elem:
                account_elem = item.find('span', class_='account')
            if account_elem:
                account_name = account_elem.get_text(strip=True)

            # 提取发布时间
            publish_time = ''
            time_elem = item.find('span', class_='s2')
            if not time_elem:
                time_elem = item.find('span', class_='time')
            if time_elem:
                publish_time = time_elem.get_text(strip=True)

            # 提取摘要
            summary = ''
            summary_elem = item.find('p', class_='txt-info')
            if not summary_elem:
                summary_elem = item.find('div', class_='txt-box')
            if summary_elem:
                summary = summary_elem.get_text(strip=True)

            # 只返回有效的微信文章URL
            if title and url and 'mp.weixin.qq.com' in url:
                return {
                    'title': title,
                    'url': url,
                    'account_name': account_name,
                    'publish_time': publish_time,
                    'summary': summary,
                    'author': account_name,
                    'content': ''  # 需要进一步获取
                }

        except Exception as e:
            logger.warning(f"解析文章项失败: {str(e)}")

        return None

    def _get_real_url(self, sogou_url: str) -> Optional[str]:
        """
        获取搜狗跳转链接的真实URL

        Args:
            sogou_url: 搜狗跳转链接

        Returns:
            真实的微信文章URL
        """
        try:
            logger.info("正在解析跳转链接...")

            # 更新Headers，模拟点击
            headers = self.session.headers.copy()
            headers.update({
                'Referer': self.search_url,
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
            })

            # 访问跳转链接
            response = self.session.get(
                sogou_url,
                headers=headers,
                timeout=15,
                allow_redirects=True  # 允许重定向
            )

            # 获取最终URL
            final_url = response.url

            # 验证是否是微信文章URL
            if 'mp.weixin.qq.com' in final_url:
                logger.info(f"成功获取真实URL")
                return final_url
            else:
                logger.warning(f"跳转后不是微信URL: {final_url[:80]}...")

                # 尝试从响应内容中提取
                if response.status_code == 200:
                    real_url = self._extract_url_from_html(response.text)
                    if real_url:
                        return real_url

        except Exception as e:
            logger.error(f"获取真实URL失败: {str(e)}")

        return None

    def _extract_url_from_html(self, html: str) -> Optional[str]:
        """从HTML中提取微信文章URL"""
        try:
            # 方式1: 从JavaScript拼接的URL中提取
            # 搜狗会将URL分段隐藏在JS中，需要拼接
            if "url += '" in html or 'url += "' in html:
                logger.info("检测到分段URL，正在拼接...")

                # 提取所有 url += 'xxx' 的部分
                import re
                pattern = r"url\s*\+=\s*['\"]([^'\"]+)['\"]"
                matches = re.findall(pattern, html)

                if matches:
                    full_url = ''.join(matches)
                    # 移除@符号（搜狗的混淆）
                    full_url = full_url.replace('@', '')

                    if 'mp.weixin.qq.com' in full_url:
                        logger.info(f"成功拼接URL: {full_url[:80]}...")
                        return full_url

            # 方式2: 直接匹配完整URL
            patterns = [
                r'var\s+url\s*=\s*["\']([^"\']+mp\.weixin\.qq\.com[^"\']+)["\']',
                r'location\.(?:href|replace)\s*[=\(]\s*["\']([^"\']+mp\.weixin\.qq\.com[^"\']+)["\']',
                r'href=["\']([^"\']+mp\.weixin\.qq\.com[^"\']+)["\']',
                r'(https?://mp\.weixin\.qq\.com/s[^\s<>"\']+)',
            ]

            for pattern in patterns:
                match = re.search(pattern, html)
                if match:
                    url = match.group(1)
                    logger.info(f"从HTML中提取到URL: {url[:80]}...")
                    return url

        except Exception as e:
            logger.warning(f"从HTML提取URL失败: {str(e)}")

        return None

    def fetch_article_content(self, url: str) -> Optional[Dict]:
        """
        获取文章详细内容

        Args:
            url: 微信文章URL

        Returns:
            文章详细信息
        """
        try:
            logger.info(f"获取文章内容: {url[:60]}...")

            # 随机延迟
            time.sleep(random.uniform(2, 4))

            # 更新Headers
            headers = self.session.headers.copy()
            headers.update({
                'Referer': self.search_url,
            })

            response = self.session.get(url, headers=headers, timeout=20)
            response.encoding = 'utf-8'

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'lxml')

                # 提取标题
                title = ''
                title_elem = soup.find('h1', id='activity-name')
                if not title_elem:
                    title_elem = soup.find('h1', class_='rich_media_title')
                if title_elem:
                    title = title_elem.get_text(strip=True)

                # 提取公众号
                account_name = ''
                account_elem = soup.find('strong', class_='profile_nickname')
                if not account_elem:
                    account_elem = soup.find('a', id='js_name')
                if account_elem:
                    account_name = account_elem.get_text(strip=True)

                # 提取作者
                author = account_name
                author_elem = soup.find('span', id='js_author_name')
                if author_elem:
                    author = author_elem.get_text(strip=True)

                # 提取发布时间
                publish_time = ''
                time_elem = soup.find('em', id='publish_time')
                if time_elem:
                    publish_time = time_elem.get_text(strip=True)

                # 提取内容
                content = ''
                content_div = soup.find('div', id='js_content')
                if content_div:
                    # 移除script和style
                    for tag in content_div.find_all(['script', 'style']):
                        tag.decompose()
                    content = content_div.get_text(separator='\n', strip=True)

                if title and content:
                    logger.info(f"成功获取文章: {title[:30]}...")
                    return {
                        'title': title,
                        'author': author,
                        'account_name': account_name,
                        'publish_time': publish_time,
                        'url': url,
                        'content': content
                    }
                else:
                    logger.warning("文章标题或内容为空")

            else:
                logger.warning(f"获取文章失败，状态码: {response.status_code}")

        except Exception as e:
            logger.error(f"获取文章内容失败: {str(e)}")

        return None

    def search_and_collect(self, keyword: str, max_results: int = 10) -> List[Dict]:
        """
        搜索并采集文章（一步到位）

        Args:
            keyword: 搜索关键词
            max_results: 最多采集数量

        Returns:
            完整的文章列表（包含内容）
        """
        logger.info(f"开始搜索并采集: {keyword}")

        # 第1步：搜索
        articles = self.search_articles(keyword, max_results)

        if not articles:
            logger.warning("未搜索到文章")
            return []

        logger.info(f"搜索到 {len(articles)} 篇文章，开始采集内容...")

        # 第2步：采集详细内容
        full_articles = []
        for i, article in enumerate(articles, 1):
            logger.info(f"[{i}/{len(articles)}] 采集: {article['title'][:30]}...")

            full_article = self.fetch_article_content(article['url'])

            if full_article:
                full_articles.append(full_article)
            else:
                # 如果获取失败，至少保留基本信息
                full_articles.append(article)

        logger.info(f"采集完成，成功 {len(full_articles)}/{len(articles)} 篇")

        return full_articles
