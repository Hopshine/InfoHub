"""
热点新闻文章采集器 - 从热点新闻URL爬取完整文章内容
支持多种新闻源：微博、百度、今日头条等
"""
import requests
from bs4 import BeautifulSoup
import time
import random
from typing import Dict, Optional, List
from utils.logger import setup_logger
import re
from urllib.parse import urlparse

logger = setup_logger('hotnews_article_collector')


class HotNewsArticleCollector:
    """热点新闻文章采集器 - 从热点URL抓取原文"""

    def __init__(self):
        self.headers = {
            'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/131.0.0.0 Safari/537.36'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"macOS"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    # ==================== 核心方法 ====================

    def collect_from_hotnews(self, hotnews_item: Dict) -> Optional[Dict]:
        """
        从单条热点新闻采集文章内容

        Args:
            hotnews_item: 热点新闻数据（含 url, title, source 等）

        Returns:
            文章数��字典，失败返回 None
        """
        url = hotnews_item.get('url', '').strip()
        if not url or url == '#':
            logger.warning(f"热点新闻无有效URL: {hotnews_item.get('title')}")
            return None

        source = hotnews_item.get('source', '')
        logger.info(f"开始采集 [{source}] {hotnews_item.get('title')}")

        try:
            if 'mp.weixin.qq.com' in url:
                article = self._fetch_wechat_article(url)
            elif 'weibo.com' in url or 's.weibo.com' in url:
                article = self._fetch_weibo_article(url, hotnews_item)
            elif 'zhihu.com' in url:
                article = self._fetch_zhihu_article(url)
                # 知乎反爬较强，失败时回退到搜狗搜索
                if not article:
                    article = self._fetch_via_search(
                        url, hotnews_item.get('title', ''))
            elif 'baidu.com' in url or 'baijiahao' in url:
                article = self._fetch_baidu_article(url, hotnews_item)
            elif 'douyin.com' in url or 'toutiao.com' in url:
                article = self._fetch_toutiao_article(url, hotnews_item)
            else:
                article = self._fetch_generic_article(url)

            if article:
                article['hotnews_id'] = hotnews_item.get('id')
                article['hotnews_title'] = hotnews_item.get('title')
                article['source_platform'] = source
                article['hot_value'] = hotnews_item.get('hot_value', '')
                # 用原始热点平台作为来源，而非最终跳转的网站域名
                article['source'] = source or article.get('source', '')
                logger.info(f"采集成功: {article.get('title', '')[:50]}")
                return article

            logger.warning(f"采集失败: {url}")
            return None

        except Exception as e:
            logger.error(f"采集异常 {url}: {e}")
            return None

    def collect_batch(self, hotnews_list: List[Dict],
                      delay: tuple = (2, 5)) -> List[Dict]:
        """
        批量采集热点新闻文章

        Args:
            hotnews_list: 热点新闻列表
            delay: 请求间隔(最小秒数, 最大秒数)

        Returns:
            成功采集的文章列表
        """
        articles = []
        total = len(hotnews_list)

        for i, item in enumerate(hotnews_list, 1):
            logger.info(f"[{i}/{total}] 处理: {item.get('title', '')[:40]}")

            article = self.collect_from_hotnews(item)
            if article:
                articles.append(article)

            if i < total:
                time.sleep(random.uniform(*delay))

        logger.info(f"批量采集完成: 成功 {len(articles)}/{total}")
        return articles

    def collect_and_save(self, db, hotnews_list: List[Dict],
                         analyze: bool = True) -> Dict:
        """
        采集热点文章并保存到数据库，可选自动分析

        Args:
            db: 数据库实例
            hotnews_list: 热点新闻列表
            analyze: 是否自动进行分析分类

        Returns:
            结果统计字典
        """
        result = {
            'total': len(hotnews_list),
            'collected': 0,
            'skipped': 0,
            'failed': 0,
            'analyzed': 0,
            'articles': [],
        }

        for i, item in enumerate(hotnews_list, 1):
            url = item.get('url', '').strip()
            title = item.get('title', '')
            logger.info(f"[{i}/{result['total']}] {title[:40]}")

            # 跳过已存在的文章
            if url and db.article_exists(url):
                logger.info(f"文章已存在，跳过")
                result['skipped'] += 1
                continue

            # 采集文章
            article = self.collect_from_hotnews(item)
            if not article or not article.get('content'):
                result['failed'] += 1
                continue

            # 保存到数据库
            article_id = db.insert_article(article)
            if article_id:
                article['id'] = article_id
                result['collected'] += 1
                result['articles'].append({
                    'id': article_id,
                    'title': article.get('title', ''),
                    'hotnews_id': item.get('id'),
                })

                # 更新热点新闻状态为已采集
                if item.get('id'):
                    db.update_hotnews_status(item['id'], 'collected')
            else:
                result['failed'] += 1

            if i < result['total']:
                time.sleep(random.uniform(2, 5))

        # 自动分析
        if analyze and result['collected'] > 0:
            result['analyzed'] = self._analyze_articles(
                db, [a['id'] for a in result['articles']])

        logger.info(
            f"采集完成: 成功{result['collected']} "
            f"跳过{result['skipped']} 失败{result['failed']} "
            f"分析{result['analyzed']}")
        return result

    # ==================== 平台采集方法 ====================

    def _fetch_wechat_article(self, url: str) -> Optional[Dict]:
        """采集微信公众号文章"""
        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = 'utf-8'
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, 'html.parser')

            title = ''
            title_el = soup.find('h1', id='activity-name')
            if title_el:
                title = title_el.get_text(strip=True)

            author = ''
            author_el = soup.find('a', id='js_name')
            if author_el:
                author = author_el.get_text(strip=True)

            content = ''
            content_el = soup.find('div', id='js_content')
            if content_el:
                content = self._clean_html_content(content_el)

            if not title or not content:
                return None

            return {
                'title': title,
                'content': content,
                'account_name': author,
                'url': url,
                'source': 'wechat',
            }
        except Exception as e:
            logger.error(f"微信文章采集失败: {e}")
            return None

    def _fetch_zhihu_article(self, url: str) -> Optional[Dict]:
        """采集知乎问题/文章"""
        try:
            # 知乎需要cookie模拟登录状态
            headers = dict(self.headers)
            headers['Referer'] = 'https://www.zhihu.com/'

            resp = self.session.get(url, timeout=15, headers=headers)
            resp.encoding = 'utf-8'
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, 'html.parser')

            # 知乎问题页
            title = ''
            title_el = soup.find('h1', class_='QuestionHeader-title')
            if title_el:
                title = title_el.get_text(strip=True)

            # 知乎文章页
            if not title:
                title_el = soup.find('h1', class_='Post-Title')
                if title_el:
                    title = title_el.get_text(strip=True)

            if not title:
                title = self._extract_title(soup)

            # 提取回答内容
            content = ''
            # 获取最佳回答
            answer_el = soup.select_one('div.RichContent-inner')
            if answer_el:
                content = self._clean_html_content(answer_el)

            # 知乎文章正文
            if not content:
                article_el = soup.select_one('div.Post-RichTextContainer')
                if article_el:
                    content = self._clean_html_content(article_el)

            if not content:
                content = self._extract_main_content(soup)

            if not title or len(content) < 50:
                return None

            return {
                'title': title,
                'content': content,
                'account_name': '知乎',
                'url': url,
                'source': 'zhihu',
            }
        except Exception as e:
            logger.error(f"知乎内容采集失败: {e}")
            return None

    def _fetch_weibo_article(self, url: str,
                             hotnews_item: Dict = None) -> Optional[Dict]:
        """采集微博内容（微博热搜URL是搜索页，改用百度搜新闻原文）"""
        title = (hotnews_item or {}).get('title', '')
        # 微博热搜链接是搜索结果页，通过百度搜索获取新闻原文
        return self._fetch_via_search(url, title)

    def _fetch_baidu_article(self, url: str,
                             hotnews_item: Dict = None) -> Optional[Dict]:
        """采集百度热搜文章（百度热搜URL是搜索页，获取实际新闻文章）"""
        try:
            resp = self.session.get(url, timeout=15, allow_redirects=True)
            resp.encoding = 'utf-8'
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, 'html.parser')

            # 检查是否是搜索结果页
            if ('baidu.com/s?' in url or 'baidu.com/s?' in resp.url
                    or 'm.baidu.com/s' in url):
                # 搜索结果页，用热点标题通过百度新闻搜索
                title = (hotnews_item or {}).get('title', '')
                if title:
                    return self._fetch_via_search(url, title)
                return None

            # 百家号文章页面直接提取
            title = ''
            for sel in ['h1.article-title', 'h2.article-title',
                        'div.article-title', 'h1']:
                el = soup.select_one(sel)
                if el and el.get_text(strip=True):
                    title = el.get_text(strip=True)
                    break

            if not title:
                title = self._extract_title(soup)

            author = ''
            for sel in ['span.author-name', 'div.author-name',
                        'a.author-name']:
                el = soup.select_one(sel)
                if el and el.get_text(strip=True):
                    author = el.get_text(strip=True)
                    break

            content = ''
            for sel in ['div.article-content', 'article',
                        'div.index-module_articleWrap']:
                el = soup.select_one(sel)
                if el:
                    content = self._clean_html_content(el)
                    if len(content) > 100:
                        break

            if not content:
                content = self._extract_main_content(soup)

            if not title or not content:
                return None

            return {
                'title': title,
                'content': content,
                'account_name': author or '百度资讯',
                'url': resp.url,
                'source': 'baidu',
            }
        except Exception as e:
            logger.error(f"百度文章采集失败: {e}")
            return None

    def _fetch_toutiao_article(self, url: str,
                               hotnews_item: Dict = None) -> Optional[Dict]:
        """采集今日头条/抖音热点（搜索页URL，改用百度搜新闻原文）"""
        title = (hotnews_item or {}).get('title', '')
        return self._fetch_via_search(url, title)

    def _fetch_via_search(self, original_url: str,
                          keyword: str) -> Optional[Dict]:
        """通过Bing搜索获取热点相关的实际新闻文章"""
        if not keyword:
            return None

        # 优先新闻类网站
        news_domains = [
            'inews.qq.com', 'news.qq.com', 'sina.com', 'sohu.com',
            'thepaper.cn', 'bjnews.com', 'chinanews.com',
            'people.com', 'xinhuanet.com', 'cctv.com',
            'guancha.cn', 'huanqiu.com', 'ifeng.com',
            'toutiao.com', 'china.com', 'news.163.com',
            'ynet.com', 'takefoto.cn', 'youth.cn',
            'gmw.cn', '81.cn', 'cnr.cn',
        ]

        # 策略1: Bing网页搜索
        article = self._search_bing_web(keyword, news_domains)
        if article:
            return article

        # 策略2: Bing新闻搜索
        article = self._search_bing_news(keyword, news_domains)
        if article:
            return article

        return None

    def _search_bing_web(self, keyword: str,
                         news_domains: list) -> Optional[Dict]:
        """Bing网页搜索"""
        try:
            resp = self.session.get(
                'https://cn.bing.com/search',
                params={'q': keyword},
                timeout=15)
            resp.encoding = 'utf-8'
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, 'html.parser')
            results = soup.select('li.b_algo h2 a')

            # 优先新闻网站
            for link in results:
                href = link.get('href', '')
                if not href or not href.startswith('http'):
                    continue
                if any(domain in href for domain in news_domains):
                    article = self._fetch_generic_article(href)
                    if article and len(article.get('content', '')) > 100:
                        article['hotnews_keyword'] = keyword
                        return article

            # 回退：前3条任意结果
            for link in results[:3]:
                href = link.get('href', '')
                if (href and href.startswith('http')
                        and 'bing.com' not in href):
                    article = self._fetch_generic_article(href)
                    if article and len(article.get('content', '')) > 100:
                        article['hotnews_keyword'] = keyword
                        return article

            return None
        except Exception as e:
            logger.error(f"Bing网页搜索失败 [{keyword}]: {e}")
            return None

    def _search_bing_news(self, keyword: str,
                          news_domains: list) -> Optional[Dict]:
        """Bing新闻搜索"""
        try:
            resp = self.session.get(
                'https://cn.bing.com/news/search',
                params={'q': keyword},
                timeout=15)
            resp.encoding = 'utf-8'
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Bing新闻结果
            for link in soup.select('a.title'):
                href = link.get('href', '')
                if (href and href.startswith('http')
                        and 'bing.com' not in href
                        and 'msn.com' not in href):
                    article = self._fetch_generic_article(href)
                    if article and len(article.get('content', '')) > 100:
                        article['hotnews_keyword'] = keyword
                        return article

            return None
        except Exception as e:
            logger.error(f"Bing新闻搜索失败 [{keyword}]: {e}")
            return None

    def _extract_first_baidu_result(self, soup: BeautifulSoup) -> str:
        """从百度搜索结果中提取第一条有效链接"""
        for item in soup.select('div.result a, div.c-container h3 a, '
                                '.result-op a'):
            href = item.get('href', '')
            if href and href.startswith('http') and 'baidu.com/link' in href:
                # 百度跳转链接，需要跟踪重定向
                try:
                    r = self.session.head(href, timeout=10,
                                          allow_redirects=True)
                    final_url = r.url
                    # 跳过百度自身页面
                    if ('baidu.com' not in final_url
                            and 'baiducontent.com' not in final_url):
                        return final_url
                except Exception:
                    continue
            elif (href and href.startswith('http')
                  and 'baidu.com' not in href):
                return href
        return ''

    def _fetch_generic_article(self, url: str) -> Optional[Dict]:
        """通用文章采集方法"""
        try:
            resp = self.session.get(url, timeout=15, allow_redirects=True)
            resp.encoding = resp.apparent_encoding or 'utf-8'
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, 'html.parser')

            title = self._extract_title(soup)
            content = self._extract_main_content(soup)

            if not title or not content or len(content) < 50:
                return None

            domain = urlparse(resp.url).netloc
            return {
                'title': title,
                'content': content,
                'account_name': domain,
                'url': resp.url,
                'source': domain,
            }
        except Exception as e:
            logger.error(f"通用采集失败: {e}")
            return None

    # ==================== 内容提取工具 ====================

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """智能提取文章标题"""
        # 优先从常见标题标签中获取
        for sel in ['h1', 'h2.title', '.article-title', '.post-title']:
            el = soup.select_one(sel)
            if el:
                text = el.get_text(strip=True)
                if 10 < len(text) < 100:
                    return text

        # 从 og:title 提取
        og = soup.find('meta', property='og:title')
        if og and og.get('content'):
            return og['content'].strip()

        # 从 <title> 标签提取
        title_el = soup.find('title')
        if title_el:
            title = title_el.get_text(strip=True)
            # 去掉常见后缀
            for sep in [' - ', ' | ', '_', ' – ']:
                if sep in title:
                    title = title.split(sep)[0].strip()
            return title

        return ''

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """智能提取文章正文"""
        # 移除无关标签
        for tag in soup.find_all(['script', 'style', 'nav', 'header',
                                   'footer', 'aside', 'iframe']):
            tag.decompose()

        # 常见正文容器选择器
        selectors = [
            'article', '.article-content', '.post-content',
            '.content', '.article-body', '#article-content',
            '.main-content', '.entry-content', '.text-content',
            'div[class*="content"]', 'div[class*="article"]',
        ]

        best_text = ''
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                text = self._clean_html_content(el)
                if len(text) > len(best_text):
                    best_text = text

        # 如果都没找到，用最长的 <p> 集合
        if len(best_text) < 100:
            paragraphs = soup.find_all('p')
            texts = [p.get_text(strip=True) for p in paragraphs
                     if len(p.get_text(strip=True)) > 20]
            combined = '\n\n'.join(texts)
            if len(combined) > len(best_text):
                best_text = combined

        return best_text

    def _clean_html_content(self, element) -> str:
        """清洗HTML元素，提取干净的文本内容"""
        # 移除不需要的内部元素
        for tag in element.find_all(['script', 'style', 'iframe', 'noscript']):
            tag.decompose()

        # 提取文本，保留段落结构
        paragraphs = []
        for child in element.find_all(['p', 'h2', 'h3', 'h4', 'li',
                                        'blockquote']):
            text = child.get_text(strip=True)
            if text and len(text) > 5:
                paragraphs.append(text)

        if paragraphs:
            return '\n\n'.join(paragraphs)

        # 如果没有段落标签，直接获取文本
        text = element.get_text(separator='\n', strip=True)
        # 清理多余空行
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    # ==================== 分析分类 ====================

    def _analyze_articles(self, db, article_ids: List[int]) -> int:
        """对采集到的文章进行分析分类"""
        try:
            from analyzer.content_analyzer import ContentAnalyzer
            analyzer = ContentAnalyzer()
        except Exception as e:
            logger.error(f"初始化分析器失败: {e}")
            return 0

        analyzed = 0
        for article_id in article_ids:
            try:
                # 从数据库获取文章
                articles = db.get_all_articles(limit=1000)
                article = next(
                    (a for a in articles if a['id'] == article_id), None)
                if not article:
                    continue

                result = analyzer.analyze_article(article)
                db.update_analysis(
                    article_id,
                    result['analysis'],
                    result['summary'],
                    result['keywords'],
                    result['category']
                )
                analyzed += 1
                logger.info(f"分析完成 [ID:{article_id}] "
                            f"分类:{result['category']} "
                            f"关键词:{result['keywords']}")
                time.sleep(1)  # 避免API限流
            except Exception as e:
                logger.error(f"分析失败 [ID:{article_id}]: {e}")
                continue

        return analyzed
