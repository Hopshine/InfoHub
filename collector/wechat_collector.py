import requests
from bs4 import BeautifulSoup
import time
import random
from typing import List, Dict
from utils.logger import setup_logger

logger = setup_logger('collector')

class WeChatCollector:
    """微信公众号文章采集器"""

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        self.sogou_search_url = 'https://weixin.sogou.com/weixin'

    def search_articles(self, keyword: str, max_results: int = 20) -> List[Dict]:
        """
        搜索微信文章
        注意：搜狗微信搜索有反爬机制，实际使用需要：
        1. 使用代理IP池
        2. 添加验证码识别
        3. 或使用第三方API服务
        """
        logger.info(f"开始搜索关键词: {keyword}")

        articles = []

        try:
            params = {
                'type': 2,  # 2表示搜索文章
                'query': keyword,
            }

            response = requests.get(
                self.sogou_search_url,
                params=params,
                headers=self.headers,
                timeout=10
            )

            if response.status_code == 200:
                articles = self._parse_search_results(response.text, max_results)
                logger.info(f"成功获取 {len(articles)} 篇文章")
            else:
                logger.warning(f"搜索请求失败，状态码: {response.status_code}")

        except Exception as e:
            logger.error(f"搜索出错: {str(e)}")

        return articles

    def _parse_search_results(self, html: str, max_results: int) -> List[Dict]:
        """解析搜索结果页面"""
        articles = []

        try:
            soup = BeautifulSoup(html, 'lxml')

            # 查找文章列表
            news_list = soup.find_all('div', class_='news-box')

            for item in news_list[:max_results]:
                try:
                    title_elem = item.find('h3')
                    if not title_elem:
                        continue

                    link_elem = title_elem.find('a')
                    title = link_elem.get_text(strip=True) if link_elem else ''
                    url = link_elem.get('href', '') if link_elem else ''

                    # 获取公众号名称
                    account_elem = item.find('a', class_='account')
                    account_name = account_elem.get_text(strip=True) if account_elem else ''

                    # 获取发布时间
                    time_elem = item.find('span', class_='s2')
                    publish_time = time_elem.get_text(strip=True) if time_elem else ''

                    # 获取摘要
                    summary_elem = item.find('p', class_='txt-info')
                    summary = summary_elem.get_text(strip=True) if summary_elem else ''

                    if title and url:
                        articles.append({
                            'title': title,
                            'url': url,
                            'account_name': account_name,
                            'publish_time': publish_time,
                            'summary': summary,
                            'author': account_name
                        })

                except Exception as e:
                    logger.warning(f"解析单篇文章失败: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"解析搜索结果失败: {str(e)}")

        return articles

    def fetch_article_content(self, url: str) -> str:
        """获取文章详细内容"""
        try:
            time.sleep(random.uniform(1, 3))  # 随机延迟，避免被封

            response = requests.get(url, headers=self.headers, timeout=15)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'lxml')

                # 微信文章内容通常在 id="js_content" 的div中
                content_div = soup.find('div', id='js_content')

                if content_div:
                    # 提取纯文本
                    content = content_div.get_text(strip=True, separator='\n')
                    return content
                else:
                    logger.warning(f"未找到文章内容: {url}")
                    return ""

        except Exception as e:
            logger.error(f"获取文章内容失败 {url}: {str(e)}")

        return ""
