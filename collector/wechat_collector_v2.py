"""
微信公众号文章采集器 - 完整实现版本

支持多种采集方式：
1. 手动URL列表导入（最稳定）
2. 搜狗微信搜索（需要处理反爬）
3. 第三方API接口（推荐生产环境）
"""

import requests
from bs4 import BeautifulSoup
import time
import random
import json
from typing import List, Dict, Optional
from utils.logger import setup_logger
import re

logger = setup_logger('collector')


class WeChatCollectorV2:
    """微信公众号文章采集器 - 增强版"""

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    # ==================== 方式1: 手动URL列表导入 ====================

    def collect_from_url_list(self, urls: List[str]) -> List[Dict]:
        """
        从URL列表采集文章
        这是最稳定的方式，适合手动收集URL后批量处理
        """
        logger.info(f"开始从URL列表采集，共 {len(urls)} 个链接")
        articles = []

        for i, url in enumerate(urls, 1):
            logger.info(f"[{i}/{len(urls)}] 正在采集: {url}")

            try:
                article = self.fetch_article_from_url(url)
                if article:
                    articles.append(article)
                    logger.info(f"✓ 成功: {article['title'][:50]}")
                else:
                    logger.warning(f"✗ 失败: {url}")

                # 随机延迟，避免被封
                time.sleep(random.uniform(2, 5))

            except Exception as e:
                logger.error(f"采集失败 {url}: {str(e)}")
                continue

        logger.info(f"采集完成，成功 {len(articles)}/{len(urls)} 篇")
        return articles

    def fetch_article_from_url(self, url: str) -> Optional[Dict]:
        """从单个URL获取文章详细信息"""
        try:
            response = self.session.get(url, timeout=15)
            response.encoding = 'utf-8'

            if response.status_code != 200:
                logger.warning(f"请求失败，状态码: {response.status_code}")
                return None

            soup = BeautifulSoup(response.text, 'lxml')

            # 提取标题
            title = self._extract_title(soup)

            # 提取公众号名称
            account_name = self._extract_account_name(soup)

            # 提取作者
            author = self._extract_author(soup) or account_name

            # 提取发布时间
            publish_time = self._extract_publish_time(soup)

            # 提取文章内容
            content = self._extract_content(soup)

            if not title or not content:
                logger.warning("未能提取到标题或内容")
                return None

            return {
                'title': title,
                'author': author,
                'account_name': account_name,
                'publish_time': publish_time,
                'url': url,
                'content': content
            }

        except Exception as e:
            logger.error(f"解析文章失败: {str(e)}")
            return None

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """提取文章标题"""
        # 方法1: id="activity-name"
        title_elem = soup.find('h1', id='activity-name')
        if title_elem:
            return title_elem.get_text(strip=True)

        # 方法2: class="rich_media_title"
        title_elem = soup.find('h1', class_='rich_media_title')
        if title_elem:
            return title_elem.get_text(strip=True)

        # 方法3: meta标签
        meta_title = soup.find('meta', property='og:title')
        if meta_title:
            return meta_title.get('content', '').strip()

        return ''

    def _extract_account_name(self, soup: BeautifulSoup) -> str:
        """提取公众号名称"""
        # 方法1: id="profileBt"
        account_elem = soup.find('strong', class_='profile_nickname')
        if account_elem:
            return account_elem.get_text(strip=True)

        # 方法2: id="js_name"
        account_elem = soup.find('a', id='js_name')
        if account_elem:
            return account_elem.get_text(strip=True)

        # 方法3: meta标签
        meta_account = soup.find('meta', property='og:article:author')
        if meta_account:
            return meta_account.get('content', '').strip()

        return ''

    def _extract_author(self, soup: BeautifulSoup) -> str:
        """提取作者"""
        # 方法1: id="js_author_name"
        author_elem = soup.find('span', id='js_author_name')
        if author_elem:
            return author_elem.get_text(strip=True)

        # 方法2: class="rich_media_meta_text"
        author_elem = soup.find('a', class_='rich_media_meta_link')
        if author_elem:
            return author_elem.get_text(strip=True)

        return ''

    def _extract_publish_time(self, soup: BeautifulSoup) -> str:
        """提取发布时间"""
        # 方法1: id="publish_time"
        time_elem = soup.find('em', id='publish_time')
        if time_elem:
            return time_elem.get_text(strip=True)

        # 方法2: class="rich_media_meta_text"
        time_elem = soup.find('span', class_='rich_media_meta_text')
        if time_elem:
            return time_elem.get_text(strip=True)

        # 方法3: 从script中提取
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and 'publish_time' in script.string:
                match = re.search(r'publish_time\s*=\s*"([^"]+)"', script.string)
                if match:
                    return match.group(1)

        return ''

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """提取文章内容"""
        # 方法1: id="js_content"
        content_div = soup.find('div', id='js_content')
        if content_div:
            # 移除script和style标签
            for tag in content_div.find_all(['script', 'style']):
                tag.decompose()

            # 提取纯文本
            content = content_div.get_text(separator='\n', strip=True)
            return content

        # 方法2: class="rich_media_content"
        content_div = soup.find('div', class_='rich_media_content')
        if content_div:
            for tag in content_div.find_all(['script', 'style']):
                tag.decompose()
            content = content_div.get_text(separator='\n', strip=True)
            return content

        return ''

    # ==================== 方式2: 搜狗微信搜索 ====================

    def search_articles_sogou(self, keyword: str, max_results: int = 20) -> List[Dict]:
        """
        通过搜狗微信搜索采集文章
        注意: 容易遇到验证码，建议配合代理使用
        """
        logger.info(f"搜狗搜索关键词: {keyword}")

        try:
            search_url = 'https://weixin.sogou.com/weixin'
            params = {
                'type': 2,
                'query': keyword,
                'ie': 'utf8',
            }

            response = self.session.get(search_url, params=params, timeout=10)

            if response.status_code == 200:
                if '请输入验证码' in response.text or 'antispider' in response.text:
                    logger.warning("遇到验证码，请使用其他方式或配置代理")
                    return []

                articles = self._parse_sogou_results(response.text, max_results)
                logger.info(f"搜索到 {len(articles)} 篇文章")
                return articles
            else:
                logger.warning(f"搜索失败，状态码: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"搜狗搜索失败: {str(e)}")
            return []

    def _parse_sogou_results(self, html: str, max_results: int) -> List[Dict]:
        """解析搜狗搜索结果"""
        articles = []

        try:
            soup = BeautifulSoup(html, 'lxml')
            news_list = soup.find_all('div', class_='news-box')

            for item in news_list[:max_results]:
                try:
                    # 提取标题和链接
                    title_elem = item.find('h3')
                    if not title_elem:
                        continue

                    link_elem = title_elem.find('a')
                    if not link_elem:
                        continue

                    title = link_elem.get_text(strip=True)
                    url = link_elem.get('href', '')

                    # 处理搜狗跳转链接
                    if url and not url.startswith('http'):
                        # 相对路径，需要补全
                        if url.startswith('/'):
                            url = 'https://weixin.sogou.com' + url

                    # 如果是搜狗跳转链接，需要访问获取真实URL
                    if url and 'sogou.com' in url:
                        try:
                            logger.info(f"正在解析跳转链接: {url[:80]}...")
                            # 访问跳转链接获取真实URL
                            response = self.session.get(
                                url,
                                timeout=15,
                                allow_redirects=True,
                                headers={
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                                    'Referer': 'https://weixin.sogou.com/'
                                }
                            )

                            # 获取最终跳转后的URL
                            final_url = response.url

                            # 验证是否是微信文章URL
                            if 'mp.weixin.qq.com' in final_url:
                                url = final_url
                                logger.info(f"成功获取真实URL: {url[:80]}...")
                            else:
                                logger.warning(f"跳转后不是微信URL: {final_url[:80]}...")
                                continue

                        except Exception as e:
                            logger.warning(f"获取真实URL失败: {str(e)}")
                            continue

                    # 提取公众号
                    account_elem = item.find('a', class_='account')
                    account_name = account_elem.get_text(strip=True) if account_elem else ''

                    # 提取时间
                    time_elem = item.find('span', class_='s2')
                    publish_time = time_elem.get_text(strip=True) if time_elem else ''

                    # 提取摘要
                    summary_elem = item.find('p', class_='txt-info')
                    summary = summary_elem.get_text(strip=True) if summary_elem else ''

                    if title and url:
                        articles.append({
                            'title': title,
                            'url': url,
                            'account_name': account_name,
                            'publish_time': publish_time,
                            'summary': summary,
                            'author': account_name,
                            'content': ''  # 需要进一步获取
                        })

                except Exception as e:
                    logger.warning(f"解析单条结果失败: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"解析搜索结果失败: {str(e)}")

        return articles

    # ==================== 方式3: 从文件读取URL ====================

    def collect_from_file(self, file_path: str) -> List[Dict]:
        """
        从文件读取URL列表并采集
        文件格式: 每行一个URL
        """
        logger.info(f"从文件读取URL: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip() and line.strip().startswith('http')]

            logger.info(f"读取到 {len(urls)} 个URL")
            return self.collect_from_url_list(urls)

        except Exception as e:
            logger.error(f"读取文件失败: {str(e)}")
            return []

    # ==================== 辅助方法 ====================

    def test_url(self, url: str) -> bool:
        """测试URL是否可访问"""
        try:
            response = self.session.head(url, timeout=5)
            return response.status_code == 200
        except:
            return False


# 保持向后兼容
class WeChatCollector(WeChatCollectorV2):
    """向后兼容的类名"""
    pass
