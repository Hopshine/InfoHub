from flask import Flask, render_template, jsonify, request, Response
import sys
import os
import json
import time
import threading
import asyncio
import uuid
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage.database import Database
from analyzer.content_analyzer import ContentAnalyzer
from collector.wechat_collector_v2 import WeChatCollectorV2
from collector.sogou_enhanced import SogouWeixinCollector
from config import Config
from config_loader import LLMConfigLoader
from crawler.job_manager import JobManager
from crawler.engine import CrawlEngine
from collector.trending_scheduler import TrendingScheduler
from collector.hotnews_article_collector import HotNewsArticleCollector
from generator.article_generator import ArticleGenerator
from publisher.wechat_publisher import WeChatPublisher
from generator.workflow_manager import WorkflowManager
from utils.parallel_executor import ParallelExecutor, LLMLogger
from agent.decisions import (
    log_decision, decision_scan_sufficient, decision_enough_valuable,
    decision_collect_complete, decision_analysis_depth,
    decision_write_precheck, decision_quality_routing, decision_post_optimize
)
from utils.logger import setup_logger

logger = setup_logger('web_app')

app = Flask(__name__)

# 初始化组件 - 优先使用demo.db（如果存在）
db_path = 'data/demo.db' if os.path.exists('data/demo.db') else Config.DATABASE_PATH
db = Database(db_path)
print(f"使用数据库: {db_path}")

# 初始化任务管理器
job_manager = JobManager(db)

# 初始化热点监控调度器
trending_scheduler = TrendingScheduler(db, interval_minutes=30)
trending_scheduler.start()

# 初始化文章生成器和发布器
article_generator = ArticleGenerator()
wechat_publisher = WeChatPublisher()
hotnews_article_collector = HotNewsArticleCollector()
workflow_manager = WorkflowManager(db, db_path)

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/app')
def app_page():
    """新版SPA应用入口"""
    return render_template('app.html')

@app.route('/api/stats')
def get_stats():
    """获取统计信息"""
    try:
        articles = db.get_all_articles(limit=1000)

        total = len(articles)
        analyzed = sum(1 for a in articles if a['analysis'])

        # 分类统计
        categories = {}
        for article in articles:
            if article['category']:
                categories[article['category']] = categories.get(article['category'], 0) + 1

        return jsonify({
            'success': True,
            'data': {
                'total': total,
                'analyzed': analyzed,
                'pending': total - analyzed,
                'categories': categories
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/articles')
def get_articles():
    """获取文章列表"""
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))

        articles = db.get_all_articles(limit=limit * page)

        # 分页
        start = (page - 1) * limit
        end = start + limit
        page_articles = articles[start:end]

        return jsonify({
            'success': True,
            'data': {
                'articles': page_articles,
                'total': len(articles),
                'page': page,
                'limit': limit
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/article/<int:article_id>')
def get_article(article_id):
    """获取文章详情"""
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM articles WHERE id = ?', (article_id,))
        article = cursor.fetchone()
        conn.close()

        if article:
            return jsonify({
                'success': True,
                'data': dict(article)
            })
        else:
            return jsonify({'success': False, 'error': '文章不存在'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/article/<int:article_id>', methods=['DELETE'])
def delete_article(article_id):
    """删除单篇文章"""
    try:
        if db.delete_article(article_id):
            return jsonify({'success': True, 'message': '删除成功'})
        else:
            return jsonify({'success': False, 'error': '文章不存在'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/articles/delete', methods=['POST'])
def delete_articles():
    """批量删除文章"""
    try:
        article_ids = request.json.get('article_ids', [])
        if not article_ids:
            return jsonify({'success': False, 'error': '未选择文章'})

        deleted_count = db.delete_articles(article_ids)
        return jsonify({
            'success': True,
            'data': {'deleted_count': deleted_count}
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/articles/unanalyzed')
def get_unanalyzed_articles_api():
    """专门返回待分析文章列表"""
    try:
        limit = int(request.args.get('limit', 10))
        articles = db.get_unanalyzed_articles(limit=limit)
        return jsonify({
            'success': True,
            'articles': articles
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/generated_articles')
def get_generated_articles_api():
    """获取所有生成文章（不限草稿状态）"""
    try:
        status = request.args.get('status')
        limit = int(request.args.get('limit', 20))
        articles = db.get_generated_articles(status=status, limit=limit)
        return jsonify({
            'success': True,
            'articles': articles
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/analyze/<int:article_id>', methods=['POST'])
def analyze_article(article_id):
    """分析单篇文章"""
    try:
        # 检查API Key
        if not Config.LLM_API_KEY:
            return jsonify({'success': False, 'error': '未配置LLM_API_KEY'})

        # 获取文章
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM articles WHERE id = ?', (article_id,))
        article = cursor.fetchone()
        conn.close()

        if not article:
            return jsonify({'success': False, 'error': '文章不存在'})

        # 分析
        llm_config = LLMConfigLoader.get_config(db, 'content_analysis')
        analyzer = ContentAnalyzer(config=llm_config)
        result = analyzer.analyze_article(dict(article))

        # 更新数据库
        db.update_analysis(
            article_id,
            result['analysis'],
            result['summary'],
            result['keywords'],
            result['category']
        )

        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/analyze/batch', methods=['POST'])
def analyze_batch():
    """批量分析文章"""
    try:
        if not Config.LLM_API_KEY:
            return jsonify({'success': False, 'error': '未配置LLM_API_KEY'})

        # 支持两种模式：指定文章ID列表 或 获取未分析文章
        article_ids = request.json.get('article_ids', [])

        if article_ids:
            # 模式1：分析指定的文章
            articles = db.get_articles_by_ids(article_ids)
        else:
            # 模式2：获取未分析的文章（向后兼容）
            limit = int(request.json.get('limit', 10))
            articles = db.get_unanalyzed_articles(limit=limit)

        llm_config = LLMConfigLoader.get_config(db, 'content_analysis')
        analyzer = ContentAnalyzer(config=llm_config)
        success_count = 0
        failed_count = 0

        for article in articles:
            try:
                result = analyzer.analyze_article(article)
                db.update_analysis(
                    article['id'],
                    result['analysis'],
                    result['summary'],
                    result['keywords'],
                    result['category']
                )
                results.append({
                    'id': article['id'],
                    'title': article['title'],
                    'success': True
                })
                success_count += 1
            except Exception as e:
                results.append({
                    'id': article['id'],
                    'title': article['title'],
                    'success': False,
                    'error': str(e)
                })
                failed_count += 1

        return jsonify({
            'success': True,
            'data': {
                'results': results,
                'total': len(results),
                'success': success_count,
                'failed': failed_count
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/collect/url', methods=['POST'])
def collect_from_url():
    """从单个URL采集文章"""
    try:
        url = request.json.get('url', '').strip()

        if not url:
            return jsonify({'success': False, 'error': 'URL不能为空'})

        if not url.startswith('http'):
            return jsonify({'success': False, 'error': '无效的URL'})

        # 检查是否已存在
        if db.article_exists(url):
            return jsonify({'success': False, 'error': '文章已存在'})

        # 采集文章
        collector = WeChatCollectorV2()
        article = collector.fetch_article_from_url(url)

        if not article:
            return jsonify({'success': False, 'error': '采集失败，请检查URL是否正确'})

        # 保存到数据库
        article_id = db.insert_article(article)

        if article_id:
            return jsonify({
                'success': True,
                'data': {
                    'id': article_id,
                    'title': article['title']
                }
            })
        else:
            return jsonify({'success': False, 'error': '保存到数据库失败'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/collect/batch', methods=['POST'])
def collect_from_urls():
    """从多个URL批量采集"""
    try:
        urls = request.json.get('urls', [])

        if not urls:
            return jsonify({'success': False, 'error': 'URL列表不能为空'})

        collector = WeChatCollectorV2()
        results = []

        for url in urls:
            url = url.strip()
            if not url or not url.startswith('http'):
                results.append({
                    'url': url,
                    'success': False,
                    'error': '无效的URL'
                })
                continue

            # 检查是否已存在
            if db.article_exists(url):
                results.append({
                    'url': url,
                    'success': False,
                    'error': '文章已存在'
                })
                continue

            # 采集文章
            article = collector.fetch_article_from_url(url)

            if article:
                article_id = db.insert_article(article)
                if article_id:
                    results.append({
                        'url': url,
                        'success': True,
                        'id': article_id,
                        'title': article['title']
                    })
                else:
                    results.append({
                        'url': url,
                        'success': False,
                        'error': '保存失败'
                    })
            else:
                results.append({
                    'url': url,
                    'success': False,
                    'error': '采集失败'
                })

        success_count = sum(1 for r in results if r['success'])

        return jsonify({
            'success': True,
            'data': {
                'total': len(results),
                'success': success_count,
                'failed': len(results) - success_count,
                'results': results
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/collect/search', methods=['POST'])
def collect_from_search():
    """搜索并采集文章（使用增强版采集器）"""
    try:
        keyword = request.json.get('keyword', '').strip()
        max_results = int(request.json.get('max_results', 10))

        if not keyword:
            return jsonify({'success': False, 'error': '关键词不能为空'})

        # 使用增强版采集器
        collector = SogouWeixinCollector()

        # 搜索并采集（一步到位）
        articles = collector.search_and_collect(keyword, max_results)

        if not articles:
            return jsonify({'success': False, 'error': '未搜索到文章或遇到验证码'})

        # 保存到数据库
        results = []
        for article in articles:
            # 检查是否已存在
            if db.article_exists(article['url']):
                results.append({
                    'title': article['title'],
                    'success': False,
                    'error': '已存在'
                })
                continue

            # 保存文章
            article_id = db.insert_article(article)

            if article_id:
                results.append({
                    'title': article['title'],
                    'success': True,
                    'id': article_id
                })
            else:
                results.append({
                    'title': article['title'],
                    'success': False,
                    'error': '保存失败'
                })

        success_count = sum(1 for r in results if r['success'])

        return jsonify({
            'success': True,
            'data': {
                'total': len(results),
                'success': success_count,
                'failed': len(results) - success_count,
                'results': results
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== 爬虫任务API ====================

@app.route('/api/crawl/start', methods=['POST'])
def crawl_start():
    """提交采集任务"""
    try:
        data = request.json or {}
        job_type = data.get('job_type', 'search')

        if job_type == 'search':
            keyword = data.get('keyword', '').strip()
            max_results = int(data.get('max_results', 5))
            if not keyword:
                return jsonify({'success': False, 'error': '关键词不能为空'})

            params = {'keyword': keyword, 'max_results': max_results}

            async def coro_factory(job_id, progress, cancel_event):
                engine = CrawlEngine(db)
                await engine.crawl_search(keyword, max_results, job_id, progress, cancel_event)

            job_id = job_manager.submit_job('search', params, coro_factory)

        elif job_type == 'batch_url':
            urls = data.get('urls', [])
            if not urls:
                return jsonify({'success': False, 'error': 'URL列表不能为空'})

            # 过滤无效URL
            urls = [u.strip() for u in urls if u.strip().startswith('http')]
            if not urls:
                return jsonify({'success': False, 'error': '没有有效的URL'})

            params = {'urls': urls}

            async def coro_factory(job_id, progress, cancel_event):
                engine = CrawlEngine(db)
                await engine.crawl_urls(urls, job_id, progress, cancel_event)

            job_id = job_manager.submit_job('batch_url', params, coro_factory)

        elif job_type == 'single_url':
            url = data.get('url', '').strip()
            if not url or not url.startswith('http'):
                return jsonify({'success': False, 'error': '无效的URL'})

            params = {'urls': [url]}

            async def coro_factory(job_id, progress, cancel_event):
                engine = CrawlEngine(db)
                await engine.crawl_urls([url], job_id, progress, cancel_event)

            job_id = job_manager.submit_job('single_url', params, coro_factory)
        else:
            return jsonify({'success': False, 'error': f'未知任务类型: {job_type}'})

        return jsonify({'success': True, 'data': {'job_id': job_id}})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/crawl/progress/<job_id>')
def crawl_progress(job_id):
    """获取采集任务进度"""
    try:
        progress = job_manager.get_progress(job_id)
        if progress:
            return jsonify({'success': True, 'data': progress})
        return jsonify({'success': False, 'error': '任务不存在'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/crawl/cancel/<job_id>', methods=['POST'])
def crawl_cancel(job_id):
    """取消采集任务"""
    try:
        if job_manager.cancel_job(job_id):
            return jsonify({'success': True, 'message': '任务已取消'})
        return jsonify({'success': False, 'error': '任务不存在或已完成'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/crawl/stream/<job_id>')
def crawl_stream(job_id):
    """SSE实时进度流"""
    def generate():
        while True:
            progress = job_manager.get_progress(job_id)
            if progress:
                yield f"data: {json.dumps(progress, ensure_ascii=False)}\n\n"
                status = progress.get('status', '')
                if status in ('completed', 'failed', 'cancelled'):
                    break
            else:
                yield f"data: {json.dumps({'error': '任务不存在'})}\n\n"
                break
            time.sleep(0.5)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


# ==================== 热点监控API ====================

@app.route('/trending')
def trending_page():
    """热点监控页面"""
    return render_template('trending.html')


@app.route('/api/trending')
def get_trending():
    """获取最新热点数据"""
    try:
        platform = request.args.get('platform')
        items = db.get_latest_trending(platform)

        # 按平台分组
        grouped = {}
        for item in items:
            plat = item['platform']
            if plat not in grouped:
                grouped[plat] = []
            grouped[plat].append(item)

        return jsonify({
            'success': True,
            'data': {
                'trending': grouped,
                'last_update': trending_scheduler.last_update,
                'scheduler': trending_scheduler.status
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/trending/refresh', methods=['POST'])
def refresh_trending():
    """手动刷新热点数据"""
    try:
        platform = request.json.get('platform') if request.json else None
        result = trending_scheduler.refresh(platform)
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/trending/status')
def trending_status():
    """获取热点监控状态"""
    return jsonify({
        'success': True,
        'data': trending_scheduler.status
    })


@app.route('/api/trending/collect', methods=['POST'])
def collect_trending_articles():
    """从热点新闻链接爬取原文到文章库"""
    try:
        data = request.json or {}
        trending_ids = data.get('ids', [])
        platform = data.get('platform')
        limit = data.get('limit', 10)
        analyze = data.get('analyze', True)

        # 获取热点列表
        if trending_ids:
            # 指定ID采集
            hotnews_list = []
            for tid in trending_ids:
                items = db.get_latest_trending()
                item = next((i for i in items if i['id'] == tid), None)
                if item:
                    hotnews_list.append(item)
        else:
            # 按平台获取最新热点
            hotnews_list = db.get_latest_trending(platform=platform, limit=limit)

        if not hotnews_list:
            return jsonify({'success': False, 'error': '没有找到可采集的热点新闻'})

        # 过滤掉没有URL的热点
        hotnews_list = [h for h in hotnews_list if h.get('url', '').strip()]
        if not hotnews_list:
            return jsonify({'success': False, 'error': '热点新闻中没有有效的URL'})

        # 转换trending字段名到hotnews格式
        for item in hotnews_list:
            item.setdefault('source', item.get('platform', ''))

        result = hotnews_article_collector.collect_and_save(
            db, hotnews_list, analyze=analyze)

        return jsonify({'success': True, 'data': result})

    except Exception as e:
        logger.error(f"热点文章采集失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ==================== 文章生成API ====================

@app.route('/api/generate', methods=['POST'])
def generate_articles():
    """基于热点生成文章"""
    try:
        data = request.json or {}
        count = data.get('count', 5)
        style = data.get('style', Config.ARTICLE_STYLE)
        hotnews_ids = data.get('hotnews_ids', [])

        # 获取待生成的热点
        if hotnews_ids:
            news_list = [db.get_hotnews_by_id(nid) for nid in hotnews_ids]
            news_list = [n for n in news_list if n]
        else:
            news_list = db.get_latest_trending(limit=count)

        results = []
        llm_config = LLMConfigLoader.get_config(db, 'article_generation')
        generator = ArticleGenerator(config=llm_config)
        for news in news_list[:count]:
            article_id = generator.generate_and_save(db, news, style)
            if article_id:
                results.append({'hotnews_id': news.get('id'), 'article_id': article_id})

        return jsonify({
            'success': True,
            'data': {'generated': len(results), 'articles': results}
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/publish', methods=['POST'])
def publish_articles():
    """发布文章到微信公众号"""
    try:
        data = request.json or {}
        article_ids = data.get('article_ids', [])
        publish_type = data.get('publish_type', 'draft')

        if not article_ids:
            return jsonify({'success': False, 'error': '请选择要发布的文章'})

        results = []
        for article_id in article_ids:
            article = db.get_generated_article_by_id(article_id)
            if not article:
                continue
            result = wechat_publisher.publish_article(article, db, publish_type)
            results.append(result)

        return jsonify({
            'success': True,
            'data': {'published': len(results), 'results': results}
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/drafts')
def get_drafts():
    """获取草稿文章列表"""
    try:
        articles = db.get_generated_articles(status='draft')
        return jsonify({'success': True, 'data': articles})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/drafts/<int:draft_id>')
def get_draft(draft_id):
    """获取单个草稿详情"""
    try:
        article = db.get_generated_article_by_id(draft_id)
        if article and article.get('status') == 'draft':
            return jsonify({
                'success': True,
                'data': {
                    'id': article['id'],
                    'title': article['title'],
                    'content': article['content'],
                    'updated_at': article.get('updated_at', article.get('created_at'))
                }
            })
        return jsonify({'success': False, 'error': '草稿不存在'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/drafts', methods=['POST'])
def create_draft():
    """创建新草稿"""
    try:
        data = request.json or {}
        article_data = {
            'title': data.get('title', ''),
            'content': data.get('content', ''),
            'status': 'draft'
        }
        article_id = db.insert_generated_article(article_data)
        if article_id:
            article = db.get_generated_article_by_id(article_id)
            return jsonify({
                'success': True,
                'data': {
                    'id': article['id'],
                    'title': article['title'],
                    'content': article['content'],
                    'updated_at': article.get('updated_at', article.get('created_at'))
                }
            })
        return jsonify({'success': False, 'error': '创建草稿失败'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/drafts/<int:draft_id>', methods=['PUT'])
def update_draft(draft_id):
    """更新草稿"""
    try:
        data = request.json or {}
        update_data = {
            'title': data.get('title', ''),
            'content': data.get('content', '')
        }
        if db.update_generated_article(draft_id, update_data):
            article = db.get_generated_article_by_id(draft_id)
            return jsonify({
                'success': True,
                'data': {
                    'id': article['id'],
                    'title': article['title'],
                    'content': article['content'],
                    'updated_at': article.get('updated_at', article.get('created_at'))
                }
            })
        return jsonify({'success': False, 'error': '草稿不存在或更新失败'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/drafts/<int:draft_id>', methods=['DELETE'])
def delete_draft(draft_id):
    """删除草稿"""
    try:
        if db.delete_generated_article(draft_id):
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': '草稿不存在'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/published')
def get_published():
    """获取发布记录"""
    try:
        records = db.get_publish_records()
        return jsonify({'success': True, 'data': records})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==================== 公众号管理API ====================

@app.route('/api/accounts', methods=['POST'])
def create_account():
    """创建公众号配置"""
    try:
        data = request.json or {}
        account_id = db.insert_wechat_account(data)
        if account_id:
            return jsonify({'success': True, 'data': {'id': account_id}})
        return jsonify({'success': False, 'error': '创建失败，AppID可能已存在'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/accounts')
def get_accounts():
    """获取公众号列表"""
    try:
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        accounts = db.get_wechat_accounts(active_only=active_only)
        return jsonify({'success': True, 'data': accounts})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/accounts/<int:account_id>', methods=['PUT'])
def update_account(account_id):
    """更新公众号配置"""
    try:
        data = request.json or {}
        db.update_wechat_account(account_id, data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/accounts/<int:account_id>', methods=['DELETE'])
def delete_account(account_id):
    """删除公众号配置"""
    try:
        if db.delete_wechat_account(account_id):
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': '公众号不存在'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==================== 智能工作流API ====================

@app.route('/api/workflow/start', methods=['POST'])
def start_workflow():
    """启动智能生成工作流"""
    try:
        data = request.json or {}
        hotnews_id = data.get('hotnews_id')
        parallel = data.get('parallel', True)

        if not hotnews_id:
            return jsonify({'success': False, 'error': '请指定热点新闻ID'})

        results = workflow_manager.run(hotnews_id, parallel=parallel)
        return jsonify({'success': True, 'data': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/workflow/pending')
def get_pending_workflows():
    """获取待审核的工作流"""
    try:
        pending = workflow_manager.get_pending_reviews()
        return jsonify({'success': True, 'data': pending})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/workflow/review', methods=['POST'])
def submit_review():
    """提交审核决定"""
    try:
        data = request.json or {}
        thread_id = data.get('thread_id')
        decision = data.get('decision')

        if not thread_id or not decision:
            return jsonify({'success': False, 'error': '缺少参数'})

        result = workflow_manager.resume(thread_id, decision)
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/workflow/visualization')
def get_workflow_visualization():
    """获取工作流可视化"""
    try:
        mermaid = workflow_manager.get_visualization()
        return jsonify({'success': True, 'data': {'mermaid': mermaid}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==================== LLM模型渠道管理API ====================

@app.route('/api/llm/providers', methods=['GET'])
def get_llm_providers_api():
    try:
        providers = db.get_llm_providers()
        # 脱敏api_key
        for p in providers:
            if p.get('api_key'):
                p['api_key_masked'] = '****' + p['api_key'][-4:] if len(p['api_key']) > 4 else '****'
        return jsonify({'success': True, 'data': providers})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/llm/providers', methods=['POST'])
def create_llm_provider_api():
    try:
        data = request.json
        if not data.get('name') or not data.get('default_model'):
            return jsonify({'success': False, 'error': '名称和模型不能为空'})
        provider_id = db.create_llm_provider(data)
        if provider_id:
            LLMConfigLoader.invalidate()
            return jsonify({'success': True, 'data': {'id': provider_id}})
        return jsonify({'success': False, 'error': '创建失败'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/llm/providers/<int:provider_id>', methods=['PUT'])
def update_llm_provider_api(provider_id):
    try:
        data = request.json
        db.update_llm_provider(provider_id, data)
        LLMConfigLoader.invalidate()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/llm/providers/<int:provider_id>', methods=['DELETE'])
def delete_llm_provider_api(provider_id):
    try:
        bindings = db.get_all_llm_bindings()
        if any(b['provider_id'] == provider_id for b in bindings):
            return jsonify({'success': False, 'error': '该渠道正在被使用，请先解除绑定'})
        db.delete_llm_provider(provider_id)
        LLMConfigLoader.invalidate()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/llm/providers/<int:provider_id>/default', methods=['POST'])
def set_default_provider_api(provider_id):
    try:
        db.set_default_provider(provider_id)
        LLMConfigLoader.invalidate()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/llm/providers/<int:provider_id>/test', methods=['POST'])
def test_llm_provider_api(provider_id):
    try:
        provider = db.get_llm_provider(provider_id)
        if not provider:
            return jsonify({'success': False, 'error': '渠道不存在'})

        ptype = provider['provider_type']
        api_key = provider.get('api_key', '')
        base_url = provider.get('base_url', '')
        model = provider['default_model']

        start = time.time()

        if ptype == 'anthropic':
            from anthropic import Anthropic
            kwargs = {'api_key': api_key}
            if base_url:
                kwargs['base_url'] = base_url
            client = Anthropic(**kwargs)
            client.messages.create(
                model=model, max_tokens=10,
                messages=[{"role": "user", "content": "请回复OK"}]
            )
        else:  # openai / ollama
            from openai import OpenAI
            kwargs = {'api_key': api_key or 'ollama'}
            if base_url:
                kwargs['base_url'] = base_url
            client = OpenAI(**kwargs)
            client.chat.completions.create(
                model=model, max_tokens=10,
                messages=[{"role": "user", "content": "请回复OK"}]
            )

        elapsed = round(time.time() - start, 2)
        return jsonify({'success': True, 'data': {'elapsed': elapsed}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== LLM功能绑定API ====================

@app.route('/api/llm/bindings', methods=['GET'])
def get_llm_bindings_api():
    try:
        bindings = db.get_all_llm_bindings()
        return jsonify({'success': True, 'data': bindings})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/llm/bindings', methods=['POST'])
def save_llm_bindings_api():
    try:
        data = request.get_json(silent=True) or []
        if not isinstance(data, list):
            data = [data]
        for item in data:
            if item.get('function_key') and item.get('provider_id'):
                db.upsert_llm_binding(
                    item['function_key'],
                    item['provider_id'],
                    item.get('model_override'),
                    item.get('max_tokens_override')
                )
        LLMConfigLoader.invalidate()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== 自动迁移环境变量配置 ====================

# ==================== Agent全局状态（增强三层结构） ====================

agent_state = {
    'running': False,
    'batch_id': None,
    'started_at': None,
    'finished_at': None,
    'error': None,
    'current_node': None,
    'nodes': {
        'scan':     {'status': 'pending', 'count': 0, 'label': '热点扫描'},
        'evaluate': {'status': 'pending', 'count': 0, 'label': '价值评估'},
        'collect':  {'status': 'pending', 'count': 0, 'label': '内容采集'},
        'analyze':  {'status': 'pending', 'count': 0, 'label': '深度分析'},
        'plan':     {'status': 'pending', 'count': 0, 'label': '创意策划'},
        'write':    {'status': 'pending', 'count': 0, 'label': '推文生成'},
        'check':    {'status': 'pending', 'count': 0, 'label': '质量检查'},
        'compose':  {'status': 'pending', 'count': 0, 'label': '编排推送'},
    },
    'articles_generated': 0,
    'stages': {},
    'tasks': {},
    'llm_logs': [],
    'decisions': [],
}

agent_schedule_state = {
    'active': False,
    'interval_minutes': 60,
    'timer': None,
}


def _reset_nodes():
    for k in agent_state['nodes']:
        agent_state['nodes'][k]['status'] = 'pending'
        agent_state['nodes'][k]['count'] = 0
    agent_state['articles_generated'] = 0
    agent_state['current_node'] = None
    agent_state['stages'] = {}
    agent_state['tasks'] = {}
    agent_state['llm_logs'] = []
    agent_state['decisions'] = []
    agent_state['finished_at'] = None


def _set_node(name, status, count=None):
    agent_state['current_node'] = name
    agent_state['nodes'][name]['status'] = status
    if count is not None:
        agent_state['nodes'][name]['count'] = count


def _update_stage(name, status, total=0, completed=0, failed=0):
    agent_state['stages'][name] = {
        'status': status,
        'total': total,
        'completed': completed,
        'failed': failed,
        'updated_at': datetime.now().isoformat(),
    }


def _register_task(task_id, stage, name, status='pending'):
    agent_state['tasks'][task_id] = {
        'stage': stage,
        'name': name,
        'status': status,
        'started_at': None,
        'completed_at': None,
        'error': None,
    }


def _update_task(task_id, status, error=None):
    if task_id in agent_state['tasks']:
        agent_state['tasks'][task_id]['status'] = status
        if status == 'running':
            agent_state['tasks'][task_id]['started_at'] = datetime.now().isoformat()
        if status in ('completed', 'failed'):
            agent_state['tasks'][task_id]['completed_at'] = datetime.now().isoformat()
        if error:
            agent_state['tasks'][task_id]['error'] = error


def _flush_llm_logs(llm_logger):
    for log in llm_logger.logs:
        agent_state['llm_logs'].append(log)
        try:
            db.create_agent_llm_log(log)
        except Exception:
            pass


# ==================== Async Task Functions ====================

async def scan_platform_async(platform, llm_logger):
    items = await asyncio.to_thread(db.get_latest_trending, platform)
    return items or []


async def evaluate_topic_async(topic, batch_id, llm_logger):
    task_data = {
        'task_type': 'evaluate',
        'stage': 'evaluate',
        'task_key': f"eval_{topic.get('id', '')}",
        'task_name': topic.get('title', ''),
        'status': 'completed',
        'input_data': json.dumps({'title': topic.get('title', '')}, ensure_ascii=False),
        'output_data': json.dumps({'selected': True}, ensure_ascii=False),
        'batch_id': batch_id,
    }
    await asyncio.to_thread(db.create_agent_task, task_data)
    return topic


async def collect_article_async(topic, llm_logger):
    result = await asyncio.to_thread(
        hotnews_article_collector.collect_from_hotnews,
        {
            'title': topic.get('title', ''),
            'url': topic.get('url', ''),
            'source': topic.get('platform', ''),
        }
    )
    if result:
        topic['_content'] = result.get('content', '')
    return result


async def analyze_article_async(topic, analyzer, llm_logger):
    content = topic.get('_content', '')
    if not content:
        return None
    result = await asyncio.to_thread(
        analyzer.analyze_article,
        {'title': topic.get('title', ''), 'content': content}
    )
    topic['_analysis'] = result
    return result


async def plan_article_async(topic, llm_logger):
    return topic


async def write_article_async(topic, generator, batch_id, llm_logger):
    task_data = {
        'task_type': 'write',
        'stage': 'write',
        'task_key': f"write_{topic.get('id', '')}",
        'task_name': topic.get('title', ''),
        'status': 'running',
        'input_data': json.dumps({'title': topic.get('title', '')}, ensure_ascii=False),
        'batch_id': batch_id,
    }
    task_id = await asyncio.to_thread(db.create_agent_task, task_data)

    result = await asyncio.to_thread(
        generator.generate_article,
        {'title': topic.get('title', ''), 'source': topic.get('platform', '')}
    )

    if result and result.get('content'):
        await asyncio.to_thread(db.create_agent_article, {
            'topic_title': topic.get('title', ''),
            'platform': topic.get('platform', ''),
            'hot_value': str(topic.get('hot_value', '')),
            'article_type': 'wechat',
            'title': result.get('title', topic.get('title', '')),
            'content': result.get('content', ''),
            'summary': result.get('summary', ''),
            'keywords': result.get('keywords', ''),
            'status': 'draft',
            'batch_id': batch_id,
        })
        if task_id:
            await asyncio.to_thread(db.update_agent_task, task_id, {
                'status': 'completed',
                'output_data': json.dumps({'title': result.get('title', '')}, ensure_ascii=False),
                'completed_at': datetime.now().isoformat(),
            })
        return result
    return None


async def check_article_async(article, llm_logger):
    title = article.get('title', '')
    content = article.get('content', '')

    score_details = []
    total_score = 0.0

    title_score = 0
    title_len = len(title)
    if title_len < 10:
        score_details.append({'item': '标题吸引力', 'score': 0, 'reason': f'标题过短({title_len}字)，缺乏信息量'})
    elif title_len > 50:
        title_score = 8
        score_details.append({'item': '标题吸引力', 'score': 8, 'reason': f'标题过长({title_len}字)，不够精炼'})
    else:
        title_score = 15

    hook_words = ['暴涨', '暴跌', '突破', '首次', '曝光', '揭秘', '真相', '内幕', '竟然', '居然', '没想到', '震惊', '重磅']
    conflict_words = ['vs', '对决', '反击', '回应', '质疑', '争议', '翻车']
    number_pattern = any(c.isdigit() for c in title)
    question_pattern = '?' in title or '？' in title or '吗' in title or '呢' in title

    if any(w in title for w in hook_words):
        title_score += 5
        score_details.append({'item': '标题吸引力', 'score': title_score, 'reason': f'包含吸睛词汇，长度{title_len}字'})
    elif any(w in title for w in conflict_words):
        title_score += 4
        score_details.append({'item': '标题吸引力', 'score': title_score, 'reason': f'包含冲突元素，长度{title_len}字'})
    elif number_pattern:
        title_score += 3
        score_details.append({'item': '标题吸引力', 'score': title_score, 'reason': f'包含具体数字，长度{title_len}字'})
    elif question_pattern:
        title_score += 3
        score_details.append({'item': '标题吸引力', 'score': title_score, 'reason': f'疑问式标题，长度{title_len}字'})
    else:
        score_details.append({'item': '标题吸引力', 'score': title_score, 'reason': f'标题平淡，缺乏钩子，长度{title_len}字'})
    total_score += min(title_score, 25)

    first_100 = content[:100] if len(content) >= 100 else content
    opening_score = 10
    if any(w in first_100 for w in ['最近', '今天', '刚刚', '突发', '紧急']):
        opening_score += 5
        score_details.append({'item': '开篇吸引力', 'score': opening_score, 'reason': '开篇有时效性，能快速抓住注意力'})
    elif '?' in first_100 or '？' in first_100:
        opening_score += 4
        score_details.append({'item': '开篇吸引力', 'score': opening_score, 'reason': '开篇设置悬念，引发好奇'})
    elif any(c.isdigit() for c in first_100):
        opening_score += 3
        score_details.append({'item': '开篇吸引力', 'score': opening_score, 'reason': '开篇有具体数据，增强可信度'})
    else:
        score_details.append({'item': '开篇吸引力', 'score': opening_score, 'reason': '开篇平淡，缺乏冲击力'})
    total_score += min(opening_score, 20)

    content_len = len(content)
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
    para_count = len(paragraphs)
    if content_len < 500:
        score_details.append({'item': '内容可读性', 'score': 0, 'reason': f'内容过短({content_len}字)，信息量不足'})
    elif content_len > 3000:
        total_score += 10
        score_details.append({'item': '内容可读性', 'score': 10, 'reason': f'内容过长({content_len}字)，可能导致读者流失'})
    elif 800 <= content_len <= 2000:
        total_score += 20
        score_details.append({'item': '内容可读性', 'score': 20, 'reason': f'长度适中({content_len}字)，{para_count}段，易读完'})
    else:
        total_score += 15
        score_details.append({'item': '内容可读性', 'score': 15, 'reason': f'长度可接受({content_len}字)，{para_count}段'})

    emotion_positive = ['感动', '温暖', '励志', '正能量', '点赞', '支持', '加油', '厉害']
    emotion_negative = ['愤怒', '气愤', '可恶', '无语', '离谱', '荒唐', '过分']
    emotion_surprise = ['震惊', '意外', '没想到', '竟然', '居然', '惊呆', '惊讶']
    emotion_score = 0
    if any(w in content for w in emotion_surprise):
        emotion_score = 15
        score_details.append({'item': '情绪共鸣', 'score': 15, 'reason': '内容有反转/意外，易引发传播'})
    elif any(w in content for w in emotion_negative):
        emotion_score = 12
        score_details.append({'item': '情绪共鸣', 'score': 12, 'reason': '内容引发负面情绪，有讨论价值'})
    elif any(w in content for w in emotion_positive):
        emotion_score = 10
        score_details.append({'item': '情绪共鸣', 'score': 10, 'reason': '内容传递正能量，有分享价值'})
    else:
        emotion_score = 5
        score_details.append({'item': '情绪共鸣', 'score': 5, 'reason': '内容平淡，缺乏情绪触点'})
    total_score += emotion_score

    interactive_score = 0
    question_count = content.count('?') + content.count('？')
    if '你怎么看' in content or '你觉得' in content or '你认为' in content:
        interactive_score = 10
        score_details.append({'item': '互动潜力', 'score': 10, 'reason': '直接引导读者发表观点'})
    elif question_count >= 2:
        interactive_score = 8
        score_details.append({'item': '互动潜力', 'score': 8, 'reason': f'包含{question_count}个疑问，引发思考'})
    elif any(w in content for w in ['争议', '讨论', '观点', '看法']):
        interactive_score = 6
        score_details.append({'item': '互动潜力', 'score': 6, 'reason': '内容有讨论空间'})
    else:
        interactive_score = 3
        score_details.append({'item': '互动潜力', 'score': 3, 'reason': '缺少互动引导'})
    total_score += interactive_score

    value_score = 5
    if any(w in content for w in ['数据', '报告', '研究', '调查', '统计']):
        value_score = 10
        score_details.append({'item': '信息价值', 'score': 10, 'reason': '包含数据/研究，有参考价值'})
    elif any(w in content for w in ['方法', '技巧', '建议', '攻略', '教程']):
        value_score = 9
        score_details.append({'item': '信息价值', 'score': 9, 'reason': '包含实用信息，有收藏价值'})
    elif any(w in content for w in ['独家', '首发', '最新', '爆料']):
        value_score = 8
        score_details.append({'item': '信息价值', 'score': 8, 'reason': '信息独特，有传播价值'})
    else:
        score_details.append({'item': '信息价值', 'score': 5, 'reason': '信息价值一般'})
    total_score += value_score

    final_score = round(total_score / 100, 2)

    await asyncio.to_thread(db.update_agent_article, article['id'], {
        'quality_score': final_score,
        'quality_detail': json.dumps({
            'total_score': total_score,
            'final_score': final_score,
            'details': score_details,
            'metrics': {
                'title_length': title_len,
                'content_length': content_len,
                'paragraph_count': para_count,
                'question_count': question_count,
                'keyword_count': len([k.strip() for k in article.get('keywords', '').split(',') if k.strip()]),
                'summary_length': len(article.get('summary', ''))
            }
        }, ensure_ascii=False)
    })
    return final_score


async def run_agent_pipeline_async(batch_id):
    """Async agent pipeline with WorkflowExecutor for parallel topic processing."""
    from agent.workflow_engine import WorkflowExecutor, compose_wechat_draft

    try:
        agent_state['running'] = True
        agent_state['batch_id'] = batch_id
        agent_state['started_at'] = datetime.now().isoformat()
        agent_state['error'] = None
        _reset_nodes()

        executor = ParallelExecutor(max_concurrency=5)

        # ===== Stage 1: Scan (4 platforms in parallel) =====
        _set_node('scan', 'running')
        _update_stage('scan', 'running', total=4)
        platforms = ['weibo', 'zhihu', 'baidu', 'douyin']
        scan_tasks = []
        for p in platforms:
            tid = f"scan_{p}"
            _register_task(tid, 'scan', f'扫描{p}')
            _update_task(tid, 'running')
            llm_log = LLMLogger(tid, batch_id)
            scan_tasks.append({'fn': scan_platform_async, 'args': (p, llm_log), 'id': tid, '_logger': llm_log})

        scan_results = await executor.run(scan_tasks)
        trending = []
        completed_scan = 0
        for r in scan_results:
            _update_task(r['id'], 'completed' if not r['error'] else 'failed', r.get('error'))
            if r['result']:
                trending.extend(r['result'])
            completed_scan += 1
        _update_stage('scan', 'completed', total=4, completed=completed_scan)

        if not trending:
            trending = await asyncio.to_thread(db.get_latest_trending, None, 50)
        if not trending:
            _set_node('scan', 'completed', 0)
            agent_state['error'] = '无热点数据'
            agent_state['running'] = False
            return
        _set_node('scan', 'completed', len(trending))

        # 决策1: 扫描结果是否充足
        scan_ok = await decision_scan_sufficient(trending, agent_state)
        if not scan_ok:
            logger.warning(f"扫描结果不足，仅{len(trending)}条")

        # ===== Stage 2: Evaluate (10 topics in parallel) =====
        _set_node('evaluate', 'running')
        topics = trending[:10]
        _update_stage('evaluate', 'running', total=len(topics))
        eval_tasks = []
        for i, topic in enumerate(topics):
            tid = f"eval_{i}"
            _register_task(tid, 'evaluate', topic.get('title', '')[:30])
            _update_task(tid, 'running')
            llm_log = LLMLogger(tid, batch_id)
            eval_tasks.append({'fn': evaluate_topic_async, 'args': (topic, batch_id, llm_log), 'id': tid, '_logger': llm_log})

        eval_executor = ParallelExecutor(max_concurrency=10)
        eval_results = await eval_executor.run(eval_tasks)
        eval_ok = sum(1 for r in eval_results if not r['error'])
        for r in eval_results:
            _update_task(r['id'], 'completed' if not r['error'] else 'failed', r.get('error'))
        _update_stage('evaluate', 'completed', total=len(topics), completed=eval_ok)
        _set_node('evaluate', 'completed', eval_ok)

        # 决策2: 筛选有价值的话题
        topics = await decision_enough_valuable(topics, agent_state)

        # ===== Stage 3-7: WorkflowExecutor处理 (collect/analyze/plan/write/check) =====
        _set_node('collect', 'running')
        _update_stage('workflow', 'running', total=len(topics))

        workflow_executor = WorkflowExecutor(db, batch_id, max_workers=5)
        await workflow_executor.create_workflows(topics)

        # 启动并等待所有workflow完成
        await workflow_executor.run()

        # 获取汇总
        summary = workflow_executor.get_summary()
        logger.info(f"Workflow summary: {summary['completed']}/{summary['total']} completed")

        agent_state['articles_generated'] = summary['completed']
        _set_node('check', 'completed', summary['completed'])
        _update_stage('workflow', 'completed', total=summary['total'], completed=summary['completed'], failed=summary['failed'])

        # ===== Stage 8: Compose WeChat Draft =====
        _set_node('compose', 'running')
        draft_id = await compose_wechat_draft(db, batch_id)
        if draft_id:
            logger.info(f"Created wechat draft {draft_id}")
            _set_node('compose', 'completed', 1)
        else:
            logger.warning("Failed to create wechat draft")
            _set_node('compose', 'completed', 0)

    except Exception as e:
        agent_state['error'] = str(e)
        if agent_state['current_node']:
            agent_state['nodes'][agent_state['current_node']]['status'] = 'failed'
        logger.error(f"Agent pipeline error: {e}")
    finally:
        agent_state['running'] = False
        agent_state['finished_at'] = datetime.now().isoformat()


def run_agent_pipeline(batch_id):
    """Sync wrapper that creates an event loop for the async pipeline."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(run_agent_pipeline_async(batch_id))
    finally:
        loop.close()


def agent_schedule_tick():
    """定时调度触发"""
    if not agent_schedule_state['active']:
        return
    batch_id = f"sched_{uuid.uuid4().hex[:8]}"
    threading.Thread(target=run_agent_pipeline, args=(batch_id,), daemon=True).start()
    if agent_schedule_state['active']:
        t = threading.Timer(agent_schedule_state['interval_minutes'] * 60, agent_schedule_tick)
        t.daemon = True
        agent_schedule_state['timer'] = t
        t.start()


# ==================== Agent API ====================

@app.route('/api/agent/run', methods=['POST'])
def agent_run():
    """手动触发Agent运行"""
    if agent_state['running']:
        return jsonify({'success': False, 'error': 'Agent正在运行中'})
    batch_id = f"manual_{uuid.uuid4().hex[:8]}"
    threading.Thread(target=run_agent_pipeline, args=(batch_id,), daemon=True).start()
    return jsonify({'success': True, 'data': {'batch_id': batch_id}})


@app.route('/api/agent/status')
def agent_status():
    """获取Agent运行状态（含节点级别进度）- 向后兼容"""
    return jsonify({'success': True, 'data': {
        'running': agent_state['running'],
        'batch_id': agent_state['batch_id'],
        'started_at': agent_state['started_at'],
        'current_node': agent_state['current_node'],
        'nodes': agent_state['nodes'],
        'articles_generated': agent_state['articles_generated'],
        'error': agent_state['error'],
    }})


@app.route('/api/agent/status/detailed')
def agent_status_detailed():
    """获取Agent详细运行状态（三层结构：stages/tasks/llm_logs + decisions）"""
    return jsonify({'success': True, 'data': {
        'running': agent_state['running'],
        'batch_id': agent_state['batch_id'],
        'started_at': agent_state['started_at'],
        'finished_at': agent_state.get('finished_at'),
        'current_node': agent_state['current_node'],
        'nodes': agent_state['nodes'],
        'stages': agent_state.get('stages', {}),
        'tasks': agent_state.get('tasks', {}),
        'llm_logs': agent_state.get('llm_logs', []),
        'decisions': agent_state.get('decisions', []),
        'articles_generated': agent_state['articles_generated'],
        'error': agent_state['error'],
    }})


@app.route('/api/agent/tasks/<batch_id>')
def agent_tasks_by_batch(batch_id):
    """获取指定batch的任务列表，可按stage过滤"""
    stage = request.args.get('stage')
    tasks = db.list_agent_tasks(batch_id=batch_id, stage=stage)
    return jsonify({'success': True, 'data': tasks})


@app.route('/api/agent/llm-logs/<task_id>')
def agent_llm_logs(task_id):
    """获取指定task的LLM调用日志"""
    logs = db.get_agent_llm_logs(task_id=task_id)
    return jsonify({'success': True, 'data': logs})


@app.route('/api/agent/workflows/<batch_id>')
def agent_workflows_by_batch(batch_id):
    """获取指定batch的所有workflow列表（DAG可视化数据）"""
    try:
        workflows = db.get_topic_workflows_by_batch(batch_id) if hasattr(db, 'get_topic_workflows_by_batch') else []

        # 解析JSON字段
        for wf in workflows:
            for field in ['collect_result', 'analysis_result', 'plan_result', 'decisions']:
                val = wf.get(field)
                if isinstance(val, str) and val:
                    try:
                        wf[field] = json.loads(val)
                    except Exception:
                        pass

        # 获取compose状态
        drafts = db.get_wechat_drafts_by_batch(batch_id) if hasattr(db, 'get_wechat_drafts_by_batch') else []
        compose = {
            'status': 'completed' if drafts else 'pending',
            'selected_articles': [],
            'draft_id': drafts[0]['id'] if drafts else None
        }
        if drafts:
            try:
                article_ids = json.loads(drafts[0].get('article_ids', '[]'))
                compose['selected_articles'] = article_ids
                compose['article_count'] = drafts[0].get('article_count', 0)
                compose['title'] = drafts[0].get('title', '')
            except Exception:
                pass

        # 统计
        total = len(workflows)
        completed = sum(1 for w in workflows if w.get('status') == 'completed')
        failed = sum(1 for w in workflows if w.get('status') == 'failed')

        return jsonify({
            'success': True,
            'data': {
                'batch_id': batch_id,
                'total_topics': total,
                'completed_topics': completed,
                'failed_topics': failed,
                'workflows': workflows,
                'compose': compose
            }
        })
    except Exception as e:
        logger.error(f"Get workflows error: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/agent/workflow/<workflow_id>')
def agent_workflow_detail(workflow_id):
    """获取单个workflow的详细信息"""
    try:
        workflow = db.get_topic_workflow(workflow_id) if hasattr(db, 'get_topic_workflow') else None
        if not workflow:
            return jsonify({'success': False, 'error': 'Workflow不存在'})

        # 解析JSON字段
        for field in ['collect_result', 'analysis_result', 'plan_result', 'decisions']:
            val = workflow.get(field)
            if isinstance(val, str) and val:
                try:
                    workflow[field] = json.loads(val)
                except Exception:
                    pass

        # 获取状态转换历史
        transitions = db.get_workflow_transitions(workflow_id) if hasattr(db, 'get_workflow_transitions') else []
        workflow['transitions'] = transitions

        # 如果有关联文章，获取文章详情
        if workflow.get('article_id'):
            article = db.get_agent_article(workflow['article_id'])
            if article:
                workflow['article'] = article

        return jsonify({'success': True, 'data': workflow})
    except Exception as e:
        logger.error(f"Get workflow detail error: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/agent/tasks')
def agent_tasks():
    """获取Agent任务列表"""
    batch_id = request.args.get('batch_id')
    tasks = db.list_agent_tasks(batch_id=batch_id)
    return jsonify({'success': True, 'data': tasks})


@app.route('/api/agent/articles')
def agent_articles():
    """获取Agent推文列表"""
    status = request.args.get('status')
    articles = db.list_agent_articles(status=status)
    return jsonify({'success': True, 'data': articles})


@app.route('/api/agent/articles/<int:article_id>/review', methods=['POST'])
def agent_article_review(article_id):
    """审核推文"""
    data = request.json or {}
    decision = data.get('decision')
    if decision not in ('approve', 'reject'):
        return jsonify({'success': False, 'error': 'decision必须是approve或reject'})
    new_status = 'approved' if decision == 'approve' else 'rejected'
    db.update_agent_article(article_id, {'status': new_status})
    return jsonify({'success': True, 'data': {'status': new_status}})


@app.route('/api/agent/articles/<int:article_id>/publish', methods=['POST'])
def agent_article_publish(article_id):
    """发布推文"""
    data = request.json or {}
    platform = data.get('platform', 'wechat')

    article = db.get_agent_article(article_id)
    if not article:
        return jsonify({'success': False, 'error': '推文不存在'})
    if article['status'] != 'approved':
        return jsonify({'success': False, 'error': '只能发布已审核通过的推文'})

    # TODO: 实际发布到对应平台的逻辑
    # 这里先模拟发布成功
    publish_result = {
        'platform': platform,
        'success': True,
        'message': f'已发布到{platform}',
        'url': f'https://{platform}.com/article/{article_id}'  # 模拟URL
    }

    db.update_agent_article(article_id, {
        'status': 'published',
        'publish_platform': platform,
        'publish_url': publish_result.get('url'),
        'publish_result': json.dumps(publish_result, ensure_ascii=False),
        'published_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    })

    return jsonify({'success': True, 'data': {
        'status': 'published',
        'platform': platform,
        'url': publish_result.get('url')
    }})


@app.route('/api/agent/articles/<int:article_id>/revert', methods=['POST'])
def agent_article_revert(article_id):
    """撤回到待审核状态"""
    article = db.get_agent_article(article_id)
    if not article:
        return jsonify({'success': False, 'error': '推文不存在'})
    if article['status'] == 'published':
        return jsonify({'success': False, 'error': '已发布的推文不能撤回'})
    db.update_agent_article(article_id, {'status': 'draft'})
    return jsonify({'success': True, 'data': {'status': 'draft'}})


# ==================== Agent调度API ====================

@app.route('/api/agent/schedule/start', methods=['POST'])
def agent_schedule_start():
    """启动定时调度"""
    if agent_schedule_state['active']:
        return jsonify({'success': False, 'error': '调度已在运行'})
    data = request.json or {}
    agent_schedule_state['interval_minutes'] = data.get('interval_minutes', 60)
    agent_schedule_state['active'] = True
    agent_schedule_tick()
    return jsonify({'success': True, 'data': {'interval_minutes': agent_schedule_state['interval_minutes']}})


@app.route('/api/agent/schedule/stop', methods=['POST'])
def agent_schedule_stop():
    """停止定时调度"""
    agent_schedule_state['active'] = False
    if agent_schedule_state['timer']:
        agent_schedule_state['timer'].cancel()
        agent_schedule_state['timer'] = None
    return jsonify({'success': True})


@app.route('/api/agent/schedule/status')
def agent_schedule_status():
    """获取调度状态"""
    return jsonify({'success': True, 'data': {
        'active': agent_schedule_state['active'],
        'interval_minutes': agent_schedule_state['interval_minutes'],
    }})


# ==================== Agent Prompt管理API ====================

@app.route('/api/agent/prompts')
def agent_prompts_list():
    """获取Prompt列表"""
    prompts = db.list_agent_prompts()
    return jsonify({'success': True, 'data': prompts})


@app.route('/api/agent/prompts', methods=['POST'])
def agent_prompts_create():
    """新建Prompt"""
    data = request.json or {}
    if not data.get('name') or not data.get('prompt_type') or not data.get('content'):
        return jsonify({'success': False, 'error': '名称、类型和内容不能为空'})
    prompt_id = db.create_agent_prompt(data)
    return jsonify({'success': True, 'data': {'id': prompt_id}})


@app.route('/api/agent/prompts/<int:prompt_id>', methods=['PUT'])
def agent_prompts_update(prompt_id):
    """修改Prompt"""
    data = request.json or {}
    prompt = db.get_agent_prompt(prompt_id)
    if not prompt:
        return jsonify({'success': False, 'error': 'Prompt不存在'})
    updates = {}
    for key in ('name', 'prompt_type', 'content'):
        if key in data:
            updates[key] = data[key]
    if updates:
        db.update_agent_prompt(prompt_id, updates)
    return jsonify({'success': True})


@app.route('/api/agent/prompts/<int:prompt_id>', methods=['DELETE'])
def agent_prompts_delete(prompt_id):
    """删除Prompt（内置不可删）"""
    if db.delete_agent_prompt(prompt_id):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': '内置Prompt不可删除或Prompt不存在'})


@app.route('/api/agent/prompts/<int:prompt_id>/activate', methods=['POST'])
def agent_prompts_activate(prompt_id):
    """激活Prompt"""
    prompt = db.get_agent_prompt(prompt_id)
    if not prompt:
        return jsonify({'success': False, 'error': 'Prompt不存在'})
    db.activate_agent_prompt(prompt_id)
    return jsonify({'success': True})


# ==================== 自动迁移环境变量配置 ====================

def auto_migrate_env_config():
    """首次启动时自动迁移环境变量配置到数据库"""
    try:
        providers = db.get_llm_providers()
        if len(providers) > 0 or not Config.LLM_API_KEY:
            return
        provider_id = db.create_llm_provider({
            'name': '默认渠道（自动迁移）',
            'provider_type': Config.LLM_PROVIDER,
            'api_key': Config.LLM_API_KEY,
            'base_url': Config.LLM_BASE_URL or '',
            'default_model': Config.ANALYSIS_MODEL,
            'max_tokens': Config.ARTICLE_MAX_TOKENS,
            'is_active': 1,
            'is_default': 1
        })
        if provider_id:
            db.upsert_llm_binding('content_analysis', provider_id, Config.ANALYSIS_MODEL, None)
            db.upsert_llm_binding('article_generation', provider_id,
                                  Config.ARTICLE_MODEL if Config.ARTICLE_MODEL != Config.ANALYSIS_MODEL else None, None)
            logger.info("已自动迁移环境变量LLM配置到数据库")
    except Exception as e:
        logger.error(f"自动迁移LLM配置失败: {e}")

auto_migrate_env_config()

if __name__ == '__main__':
    print("=" * 60)
    print("InfoHub Web 管理界面")
    print("=" * 60)
    print("访问地址: http://localhost:9000")
    print("按 Ctrl+C 停止服务器")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=9000)
