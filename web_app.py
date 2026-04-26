from flask import Flask, render_template, jsonify, request, Response
import sys
import os
import json
import time
import threading
import asyncio
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename

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

# 微信发布器延迟初始化（使用时从数据库读取账号配置）
def get_wechat_publisher():
    """获取微信发布器实例，从数据库读取账号配置"""
    accounts = db.get_wechat_accounts()

    # 优先使用默认账号
    default_account = next((acc for acc in accounts if acc.get('is_default') == 1), None)
    if default_account:
        return WeChatPublisher(
            app_id=default_account['app_id'],
            app_secret=default_account['app_secret'],
            db=db
        )

    # 如果没有默认账号，使用第一个活跃账号
    active_accounts = [acc for acc in accounts if acc.get('is_active') == 1]
    if active_accounts:
        account = active_accounts[0]
        return WeChatPublisher(
            app_id=account['app_id'],
            app_secret=account['app_secret'],
            db=db
        )

    # 最后回退到环境变量
    return WeChatPublisher(db=db)

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
        analyze = data.get('analyze', False)  # 默认不自动分析，采集和分析分开

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
            news_list = [db.get_trending_by_id(nid) for nid in hotnews_ids]
            news_list = [n for n in news_list if n]
        else:
            news_list = db.get_latest_trending(limit=count)

        if not news_list:
            return jsonify({'success': False, 'error': '没有找到热点数据'})

        results = []
        llm_config = LLMConfigLoader.get_config(db, 'article_generation')
        generator = ArticleGenerator(config=llm_config)

        for news in news_list[:count]:
            article_id = generator.generate_and_save(db, news, style)
            if article_id:
                results.append({'hotnews_id': news.get('id'), 'article_id': article_id})

        # 如果是单篇生成，返回文章详情
        if len(results) == 1 and results[0]['article_id']:
            article = db.get_generated_article_by_id(results[0]['article_id'])
            if article:
                return jsonify({
                    'success': True,
                    'data': {
                        'generated': 1,
                        'article_id': article['id'],
                        'title': article['title'],
                        'content': article['content'],
                        'summary': article.get('summary', ''),
                    }
                })

        return jsonify({
            'success': True,
            'data': {'generated': len(results), 'articles': results}
        })
    except Exception as e:
        logger.error(f"文章生成失败: {e}")
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
        publisher = get_wechat_publisher()
        for article_id in article_ids:
            article = db.get_generated_article_by_id(article_id)
            if not article:
                continue
            result = publisher.publish_article(article, db, publish_type)
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
                    'content_wechat': article.get('content_wechat', article['content']),
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
            'content_wechat': data.get('content_wechat', data.get('content', '')),
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
                    'content_wechat': article.get('content_wechat', article['content']),
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
        if 'content_wechat' in data:
            update_data['content_wechat'] = data['content_wechat']

        if db.update_generated_article(draft_id, update_data):
            article = db.get_generated_article_by_id(draft_id)
            return jsonify({
                'success': True,
                'data': {
                    'id': article['id'],
                    'title': article['title'],
                    'content': article['content'],
                    'content_wechat': article.get('content_wechat', article['content']),
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
    """扫描平台热点 - 实际采集新数据"""
    from collector.trending_collector import TrendingCollector

    collector = TrendingCollector()

    # 根据平台调用对应的采集方法
    if platform == 'weibo':
        items = await asyncio.to_thread(collector.collect_weibo)
    elif platform == 'zhihu':
        items = await asyncio.to_thread(collector.collect_zhihu)
    elif platform == 'baidu':
        items = await asyncio.to_thread(collector.collect_baidu)
    elif platform == 'douyin':
        items = await asyncio.to_thread(collector.collect_douyin)
    else:
        items = []

    # 存储到数据库（防重复）
    saved_count = 0
    if items:
        for item in items:
            try:
                # 检查是否已存在（根据平台+标题）
                existing = db.get_trending_by_title(platform, item.get('title', ''))
                if not existing:
                    # 添加平台字段
                    item['platform'] = platform
                    db.save_trending_item(item)
                    saved_count += 1
            except Exception as e:
                logger.error(f"保存热点失败: {e}")
                continue

    return {
        'platform': platform,
        'count': len(items),
        'saved': saved_count,
        'items': items  # 返回所有采集的数据
    }


async def evaluate_topic_async(topic, batch_id, llm_logger, task_id):
    """使用LLM进行多维度评估 - 结果持久化到trending表，防重复评估"""
    from agent.topic_evaluator import TopicEvaluator

    trending_id = topic.get('id')

    # 防重复：检查是否已有评估结果
    if trending_id:
        cached = await asyncio.to_thread(db.get_trending_evaluation, trending_id)
        if cached and cached.get('eval_result'):
            result = cached['eval_result']
            selected = result.get('selected', False)
            logger.info(f"跳过已评估话题: {topic.get('title', '')[:30]} ({cached['eval_grade']}级)")

            # 更新task记录为缓存结果
            await asyncio.to_thread(db.update_agent_task, task_id, {
                'status': 'completed' if selected else 'failed',
                'output_data': json.dumps(result, ensure_ascii=False),
                'completed_at': datetime.now().isoformat()
            })

            if not selected:
                return None
            topic['_eval_score'] = result.get('total_score', 0)
            topic['_eval_grade'] = result.get('grade', 'C')
            return topic

    # 调用LLM评估
    evaluator = TopicEvaluator(db)
    result = await asyncio.to_thread(evaluator.evaluate, topic, llm_logger)

    selected = result.get('selected', False)

    # 持久化评估结果到trending表
    if trending_id:
        model_name = evaluator.config.get('model', 'unknown') if evaluator.config else 'unknown'
        await asyncio.to_thread(db.save_trending_evaluation, trending_id, result, model_name)

    # 更新task记录
    await asyncio.to_thread(db.update_agent_task, task_id, {
        'status': 'completed' if selected else 'failed',
        'output_data': json.dumps(result, ensure_ascii=False),
        'completed_at': datetime.now().isoformat()
    })

    if not selected:
        return None
    topic['_eval_score'] = result.get('total_score', 0)
    topic['_eval_grade'] = result.get('grade', 'C')
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
    from utils.ollama_checker import ensure_ollama_running

    try:
        agent_state['running'] = True
        agent_state['batch_id'] = batch_id
        agent_state['started_at'] = datetime.now().isoformat()
        agent_state['error'] = None
        _reset_nodes()

        # 确保Ollama服务运行
        await asyncio.to_thread(ensure_ollama_running)

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

            # 创建数据库任务记录
            await asyncio.to_thread(db.create_agent_task, {
                'task_key': tid,
                'stage': 'scan',
                'task_type': 'scan',
                'task_name': p,  # 平台名称
                'status': 'running',
                'batch_id': batch_id
            })

            llm_log = LLMLogger(tid, batch_id)
            scan_tasks.append({'fn': scan_platform_async, 'args': (p, llm_log), 'id': tid, '_logger': llm_log})

        scan_results = await executor.run(scan_tasks)
        trending = []
        completed_scan = 0
        for r in scan_results:
            result = r.get('result', {})
            platform = result.get('platform', 'unknown')
            count = result.get('count', 0)
            saved = result.get('saved', 0)
            items = result.get('items', [])

            # 更新任务状态，包含平台和数量信息
            _update_task(r['id'], 'completed' if not r['error'] else 'failed', r.get('error'))

            # 存储扫描结果到task
            if not r['error']:
                await asyncio.to_thread(db.update_agent_task, r['id'], {
                    'output_data': json.dumps({
                        'platform': platform,
                        'count': count,
                        'saved': saved
                    }, ensure_ascii=False)
                })
                trending.extend(items)
                completed_scan += 1
        _update_stage('scan', 'completed', total=4, completed=completed_scan)

        if not trending:
            trending = await asyncio.to_thread(db.get_latest_trending, None, 200)
        if not trending:
            _set_node('scan', 'completed', 0)
            agent_state['error'] = '无热点数据'
            agent_state['running'] = False
            return

        # 去重（按标题）
        seen_titles = set()
        unique_trending = []
        for item in trending:
            title = item.get('title', '').strip()
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_trending.append(item)
        trending = unique_trending

        # 按热度排序（高热度优先）
        def get_hot_value(item):
            try:
                return int(str(item.get('hot_value', '0')).replace(',', '') or 0)
            except:
                return 0
        trending.sort(key=get_hot_value, reverse=True)

        _set_node('scan', 'completed', len(trending))
        logger.info(f"扫描完成: {len(trending)}条热点（去重后）")

        # 决策1: 扫描结果是否充足
        scan_ok = await decision_scan_sufficient(trending, agent_state)
        if not scan_ok:
            logger.warning(f"扫描结果不足，仅{len(trending)}条")

        # ===== Stage 2: Evaluate (评估所有采集到的热点) =====
        _set_node('evaluate', 'running')
        topics_to_eval = trending  # 评估所有热点
        _update_stage('evaluate', 'running', total=len(topics_to_eval))
        eval_tasks = []
        for i, topic in enumerate(topics_to_eval):
            tid = f"eval_{i}"
            _register_task(tid, 'evaluate', topic.get('title', '')[:30])
            _update_task(tid, 'running')

            # 预先创建数据库记录
            await asyncio.to_thread(db.create_agent_task, {
                'task_key': tid,
                'stage': 'evaluate',
                'task_type': 'evaluate',
                'task_name': topic.get('title', '')[:60],
                'status': 'running',
                'input_data': json.dumps({
                    'title': topic.get('title', ''),
                    'platform': topic.get('platform', ''),
                    'hot_value': str(topic.get('hot_value', ''))
                }, ensure_ascii=False),
                'batch_id': batch_id
            })

            llm_log = LLMLogger(tid, batch_id)
            eval_tasks.append({'fn': evaluate_topic_async, 'args': (topic, batch_id, llm_log, tid), 'id': tid, '_logger': llm_log})

        eval_executor = ParallelExecutor(max_concurrency=20)
        eval_results = await eval_executor.run(eval_tasks)

        # 只保留通过评估的话题（result不为None）
        selected_topics = []
        eval_passed = 0
        for r in eval_results:
            _update_task(r['id'], 'completed' if not r['error'] else 'failed', r.get('error'))
            if r['result'] is not None:
                selected_topics.append(r['result'])
                eval_passed += 1

        _update_stage('evaluate', 'completed', total=len(topics_to_eval), completed=eval_passed)
        _set_node('evaluate', 'completed', eval_passed)

        logger.info(f"Evaluation: {eval_passed}/{len(topics_to_eval)} topics selected")

        # 决策2: 筛选有价值的话题（已在evaluate中完成）
        topics = selected_topics

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
    """获取Agent详细运行状态"""
    # 从数据库读取完整的task数据
    tasks_data = {}
    if agent_state.get('batch_id'):
        try:
            db_tasks = db.list_agent_tasks(batch_id=agent_state['batch_id'])
            for task in db_tasks:
                task_key = task.get('task_key', f"task_{task.get('id')}")
                tasks_data[task_key] = task
        except Exception as e:
            logger.error(f"读取数据库tasks失败: {e}")

    # 补充内存中还没写入数据库的task
    for task_id, mem_task in agent_state.get('tasks', {}).items():
        if task_id not in tasks_data:
            tasks_data[task_id] = mem_task

    return jsonify({'success': True, 'data': {
        'running': agent_state['running'],
        'batch_id': agent_state['batch_id'],
        'started_at': agent_state['started_at'],
        'finished_at': agent_state.get('finished_at'),
        'current_node': agent_state['current_node'],
        'nodes': agent_state['nodes'],
        'stages': agent_state.get('stages', {}),
        'tasks': tasks_data,
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

        # 获取LLM调用日志
        llm_logs = []
        if hasattr(db, 'get_agent_llm_logs'):
            try:
                llm_logs = db.get_agent_llm_logs(task_id=workflow_id)
            except Exception as e:
                logger.warning(f"Failed to get LLM logs: {e}")
        workflow['llm_logs'] = llm_logs

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


# ==================== Agent文章转草稿 ====================

def markdown_to_wechat_html(md_text):
    """Markdown转微信公众号HTML"""
    import markdown as md_lib
    import bleach
    from bs4 import BeautifulSoup

    if not md_text:
        return ''

    html = md_lib.markdown(md_text, extensions=[
        'markdown.extensions.extra',
        'markdown.extensions.toc'
    ])

    allowed_tags = [
        'h1', 'h2', 'h3', 'h4', 'p', 'br', 'strong', 'em', 'b', 'i',
        'u', 'a', 'img', 'ul', 'ol', 'li', 'blockquote', 'code', 'pre',
        'table', 'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'span', 'div'
    ]
    allowed_attrs = {
        'a': ['href', 'title'],
        'img': ['src', 'alt', 'title'],
        'th': ['align'], 'td': ['align']
    }
    html = bleach.clean(html, tags=allowed_tags, attributes=allowed_attrs)

    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup.find_all(['h1', 'h2']):
        tag['style'] = 'font-size:20px;font-weight:bold;color:#333;margin:24px 0 12px;padding-bottom:8px;border-bottom:1px solid #eee;'
    for tag in soup.find_all('h3'):
        tag['style'] = 'font-size:17px;font-weight:bold;color:#333;margin:20px 0 10px;'
    for tag in soup.find_all('p'):
        tag['style'] = 'font-size:16px;line-height:1.8;color:#3f3f3f;margin:10px 0;'
    for tag in soup.find_all('img'):
        tag['style'] = 'max-width:100%;display:block;margin:15px auto;border-radius:4px;'
    for tag in soup.find_all('blockquote'):
        tag['style'] = 'border-left:3px solid #10b981;padding:10px 15px;margin:15px 0;background:#f8f9fa;color:#666;'
    for tag in soup.find_all('strong'):
        tag['style'] = 'color:#333;'

    return str(soup)


def convert_agent_to_draft(agent_article_id):
    """将Agent文章转为创作中心草稿"""
    article = db.get_agent_article(agent_article_id)
    if not article:
        raise Exception(f'Agent文章不存在: {agent_article_id}')

    # 幂等检查
    if article.get('draft_id'):
        return article['draft_id']

    content_md = article.get('content', '')
    content_wechat = markdown_to_wechat_html(content_md)

    draft_data = {
        'title': article.get('title', ''),
        'content': content_md,
        'content_wechat': content_wechat,
        'summary': article.get('summary', ''),
        'keywords': article.get('keywords', ''),
        'source_type': 'agent',
        'source_id': agent_article_id,
        'status': 'draft'
    }
    draft_id = db.insert_generated_article(draft_data)

    if draft_id:
        db.update_agent_article(agent_article_id, {'draft_id': draft_id})
        logger.info(f"Agent文章 {agent_article_id} 已转为草稿 {draft_id}")

    return draft_id


@app.route('/api/agent/articles/<int:article_id>/convert', methods=['POST'])
def agent_article_convert(article_id):
    """手动将Agent文章转为创作中心草稿"""
    try:
        draft_id = convert_agent_to_draft(article_id)
        if draft_id:
            return jsonify({'success': True, 'data': {'draft_id': draft_id}})
        return jsonify({'success': False, 'error': '转换失败'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/agent/articles/<int:article_id>/review', methods=['POST'])
def agent_article_review(article_id):
    """审核推文 - 通过后自动转为创作中心草稿"""
    data = request.json or {}
    decision = data.get('decision')
    if decision not in ('approve', 'reject'):
        return jsonify({'success': False, 'error': 'decision必须是approve或reject'})
    new_status = 'approved' if decision == 'approve' else 'rejected'
    db.update_agent_article(article_id, {'status': new_status})

    # 审核通过时自动转为创作中心草稿
    draft_id = None
    if new_status == 'approved':
        try:
            draft_id = convert_agent_to_draft(article_id)
        except Exception as e:
            logger.error(f"Agent文章转草稿失败: {e}")

    return jsonify({'success': True, 'data': {
        'status': new_status,
        'draft_id': draft_id
    }})


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


@app.route('/api/agent/evaluation/prompt', methods=['GET'])
def get_evaluation_prompt():
    """获取当前评估提示词"""
    from agent.topic_evaluator import TopicEvaluator
    return jsonify({
        'success': True,
        'data': {
            'system_prompt': TopicEvaluator.SYSTEM_PROMPT,
            'evaluation_prompt': TopicEvaluator.EVALUATION_PROMPT
        }
    })


@app.route('/api/agent/evaluation/feedback', methods=['POST'])
def submit_evaluation_feedback():
    """提交评估反馈，用于优化提示词"""
    from agent.topic_evaluator import TopicEvaluator
    data = request.json or {}
    feedback = data.get('feedback', '')

    evaluator = TopicEvaluator(db)
    success = evaluator.optimize_prompt(feedback)

    return jsonify({
        'success': success,
        'message': '反馈已收到，将用于优化评估模型'
    })


@app.route('/api/agent/evaluation/stats', methods=['GET'])
def get_evaluation_stats():
    """获取评估统计信息"""
    try:
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()

        # 总评估数
        cursor.execute('SELECT COUNT(*) FROM trending WHERE eval_at IS NOT NULL')
        total = cursor.fetchone()[0]

        # 通过/拒绝数
        cursor.execute('SELECT COUNT(*) FROM trending WHERE eval_selected = 1')
        passed = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM trending WHERE eval_selected = 0 AND eval_at IS NOT NULL')
        rejected = cursor.fetchone()[0]

        # 评级分布
        cursor.execute('SELECT eval_grade, COUNT(*) FROM trending WHERE eval_grade IS NOT NULL GROUP BY eval_grade')
        grade_dist = {row[0]: row[1] for row in cursor.fetchall()}

        # 平均分
        cursor.execute('SELECT AVG(eval_score) FROM trending WHERE eval_score IS NOT NULL')
        avg_score = cursor.fetchone()[0] or 0

        # 最近评估
        cursor.execute('''
            SELECT title, eval_score, eval_grade, eval_selected, eval_at
            FROM trending
            WHERE eval_at IS NOT NULL
            ORDER BY eval_at DESC
            LIMIT 10
        ''')
        recent = [{'title': r[0], 'score': r[1], 'grade': r[2], 'selected': bool(r[3]), 'eval_at': r[4]}
                  for r in cursor.fetchall()]

        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'total': total,
                'passed': passed,
                'rejected': rejected,
                'grade_distribution': grade_dist,
                'average_score': round(avg_score, 1),
                'recent_evaluations': recent
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==================== 文章合集管理API ====================

@app.route('/api/collections', methods=['GET'])
def get_collections():
    """获取合集列表"""
    try:
        status = request.args.get('status')
        collections = db.get_article_collections(status=status)
        return jsonify({'success': True, 'data': collections})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/collections', methods=['POST'])
def create_collection():
    """创建合集"""
    try:
        data = request.json or {}
        article_ids = data.get('article_ids', [])

        validation = db.validate_collection_articles(article_ids)
        if not validation['valid']:
            return jsonify({'success': False, 'error': validation['error']})

        collection_data = {
            'title': data.get('title', ''),
            'description': data.get('description', ''),
            'article_ids': article_ids,
            'article_count': len(article_ids),
            'cover_image': data.get('cover_image', ''),
            'status': data.get('status', 'draft')
        }
        collection_id = db.create_article_collection(collection_data)
        if collection_id:
            return jsonify({'success': True, 'data': {'id': collection_id}})
        return jsonify({'success': False, 'error': '创建失败'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/collections/<int:collection_id>', methods=['GET'])
def get_collection(collection_id):
    """获取合集详情"""
    try:
        collection = db.get_article_collection(collection_id)
        if not collection:
            return jsonify({'success': False, 'error': '合集不存在'})

        article_ids = json.loads(collection.get('article_ids', '[]'))
        articles = []
        if article_ids:
            for aid in article_ids:
                article = db.get_generated_article_by_id(aid)
                if article:
                    articles.append(article)
        collection['articles'] = articles

        return jsonify({'success': True, 'data': collection})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/collections/<int:collection_id>', methods=['PUT'])
def update_collection(collection_id):
    """更新合集"""
    try:
        data = request.json or {}
        collection = db.get_article_collection(collection_id)
        if not collection:
            return jsonify({'success': False, 'error': '合集不存在'})

        # 如果更新article_ids，需要校验
        if 'article_ids' in data:
            validation = db.validate_collection_articles(data['article_ids'])
            if not validation['valid']:
                return jsonify({'success': False, 'error': validation['error']})
            data['article_count'] = len(data['article_ids'])

        if db.update_article_collection(collection_id, data):
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': '更新失败'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/collections/<int:collection_id>', methods=['DELETE'])
def delete_collection(collection_id):
    """删除合集"""
    try:
        if db.delete_article_collection(collection_id):
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': '合集不存在'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/collections/<int:collection_id>/preview', methods=['POST'])
def preview_collection(collection_id):
    """预览合集HTML"""
    try:
        collection = db.get_article_collection(collection_id)
        if not collection:
            return jsonify({'success': False, 'error': '合集不存在'})

        article_ids = json.loads(collection.get('article_ids', '[]'))
        if not article_ids:
            return jsonify({'success': False, 'error': '合集中没有文章'})

        articles = []
        for aid in article_ids:
            article = db.get_generated_article_by_id(aid)
            if article:
                articles.append(article)

        if not articles:
            return jsonify({'success': False, 'error': '未找到合集文章'})

        # 生成合集HTML
        html_parts = [
            '<!DOCTYPE html>',
            '<html><head><meta charset="utf-8">',
            f'<title>{collection.get("title", "文章合集")}</title>',
            '<style>',
            'body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;max-width:720px;margin:0 auto;padding:20px;line-height:1.8;color:#333}',
            '.collection-header{text-align:center;padding:20px 0;border-bottom:2px solid #07c160;margin-bottom:30px}',
            '.collection-title{font-size:24px;font-weight:bold;color:#07c160;margin-bottom:10px}',
            '.collection-desc{font-size:14px;color:#666}',
            '.article-item{margin-bottom:40px;padding-bottom:30px;border-bottom:1px dashed #ddd}',
            '.article-item:last-child{border-bottom:none}',
            '.article-index{display:inline-block;background:#07c160;color:#fff;padding:2px 10px;border-radius:4px;font-size:12px;margin-bottom:10px}',
            '.article-title{font-size:20px;font-weight:bold;margin:10px 0 15px;color:#222}',
            '.article-summary{font-size:14px;color:#888;margin-bottom:15px;padding:10px;background:#f7f7f7;border-left:3px solid #07c160}',
            '.article-content{font-size:16px}',
            '</style></head><body>',
            '<div class="collection-header">',
            f'<div class="collection-title">{collection.get("title", "文章合集")}</div>',
        ]
        if collection.get('description'):
            html_parts.append(f'<div class="collection-desc">{collection["description"]}</div>')
        html_parts.append('</div>')

        for i, article in enumerate(articles, 1):
            html_parts.append('<div class="article-item">')
            html_parts.append(f'<span class="article-index">第 {i} 篇</span>')
            html_parts.append(f'<div class="article-title">{article.get("title", "")}</div>')
            if article.get('summary'):
                html_parts.append(f'<div class="article-summary">{article["summary"]}</div>')
            html_parts.append(f'<div class="article-content">{article.get("content", "")}</div>')
            html_parts.append('</div>')

        html_parts.append('</body></html>')
        html = '\n'.join(html_parts)

        return jsonify({'success': True, 'html': html})
    except Exception as e:
        logger.error(f"预览合集失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/collections/stats', methods=['GET'])
def get_collection_stats():
    """获取合集统计信息"""
    try:
        stats = db.get_collection_stats()
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/collections/<int:collection_id>/articles', methods=['GET'])
def get_collection_articles(collection_id):
    """获取合集包含的所有文章完整信息"""
    try:
        collection = db.get_article_collection(collection_id)
        if not collection:
            return jsonify({'success': False, 'error': '合集不存在'})

        article_ids = json.loads(collection.get('article_ids', '[]'))
        articles = []
        if article_ids:
            for aid in article_ids:
                article = db.get_generated_article_by_id(aid)
                if article:
                    articles.append(article)

        return jsonify({'success': True, 'data': articles})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/collections/<int:collection_id>/reorder', methods=['PUT'])
def reorder_collection(collection_id):
    """重新排序合集文章"""
    try:
        data = request.json or {}
        new_article_ids = data.get('article_ids', [])

        collection = db.get_article_collection(collection_id)
        if not collection:
            return jsonify({'success': False, 'error': '合集不存在'})

        old_article_ids = json.loads(collection.get('article_ids', '[]'))

        # 验证新数组包含原有的所有文章ID
        if set(new_article_ids) != set(old_article_ids):
            return jsonify({'success': False, 'error': '新顺序必须包含原有的所有文章ID'})

        # 更新顺序
        if db.update_article_collection(collection_id, {'article_ids': new_article_ids}):
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': '更新失败'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/collections/<int:collection_id>/export', methods=['GET'])
def export_collection(collection_id):
    """导出合集为完整HTML文件"""
    try:
        collection = db.get_article_collection(collection_id)
        if not collection:
            return jsonify({'success': False, 'error': '合集不存在'})

        article_ids = json.loads(collection.get('article_ids', '[]'))
        if not article_ids:
            return jsonify({'success': False, 'error': '合集中没有文章'})

        articles = []
        for aid in article_ids:
            article = db.get_generated_article_by_id(aid)
            if article:
                articles.append(article)

        if not articles:
            return jsonify({'success': False, 'error': '未找到合集文章'})

        # 生成完整HTML
        html_parts = [
            '<!DOCTYPE html>',
            '<html><head><meta charset="utf-8">',
            f'<title>{collection.get("title", "文章合集")}</title>',
            '<style>',
            'body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;max-width:720px;margin:0 auto;padding:20px;line-height:1.8;color:#333}',
            '.collection-header{text-align:center;padding:20px 0;border-bottom:2px solid #07c160;margin-bottom:30px}',
            '.collection-title{font-size:24px;font-weight:bold;color:#07c160;margin-bottom:10px}',
            '.collection-desc{font-size:14px;color:#666}',
            '.article-item{margin-bottom:40px;padding-bottom:30px;border-bottom:1px dashed #ddd}',
            '.article-item:last-child{border-bottom:none}',
            '.article-index{display:inline-block;background:#07c160;color:#fff;padding:2px 10px;border-radius:4px;font-size:12px;margin-bottom:10px}',
            '.article-title{font-size:20px;font-weight:bold;margin:10px 0 15px;color:#222}',
            '.article-summary{font-size:14px;color:#888;margin-bottom:15px;padding:10px;background:#f7f7f7;border-left:3px solid #07c160}',
            '.article-content{font-size:16px}',
            '</style></head><body>',
            '<div class="collection-header">',
            f'<div class="collection-title">{collection.get("title", "文章合集")}</div>',
        ]
        if collection.get('description'):
            html_parts.append(f'<div class="collection-desc">{collection["description"]}</div>')
        html_parts.append('</div>')

        for i, article in enumerate(articles, 1):
            html_parts.append('<div class="article-item">')
            html_parts.append(f'<span class="article-index">第 {i} 篇</span>')
            html_parts.append(f'<div class="article-title">{article.get("title", "")}</div>')
            if article.get('summary'):
                html_parts.append(f'<div class="article-summary">{article["summary"]}</div>')
            html_parts.append(f'<div class="article-content">{article.get("content", "")}</div>')
            html_parts.append('</div>')

        html_parts.append('</body></html>')
        html = '\n'.join(html_parts)

        # 返回可下载的HTML文件
        from flask import make_response
        response = make_response(html)
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename="{collection.get("title", "collection")}.html"'
        return response
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/collections/<int:collection_id>/publish', methods=['POST'])
def publish_collection(collection_id):
    """发布文章合集到微信公众号"""
    try:
        data = request.json or {}
        publish_now = data.get('publish_now', False)

        # 获取微信发布器实例
        publisher = get_wechat_publisher()
        result = publisher.publish_collection(collection_id, db, publish_now)

        if result['status'] in ('draft', 'published'):
            return jsonify({
                'success': True,
                'data': result
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('message', '发布失败')
            })
    except Exception as e:
        logger.error(f"发布合集失败: {e}")
        return jsonify({'success': False, 'error': str(e)})
        return jsonify({'success': False, 'error': str(e)})

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

# ==================== 微信编辑器相关接口 ====================

UPLOAD_FOLDER = 'static/uploads/wechat'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/wechat-editor-demo')
def wechat_editor_demo():
    """微信编辑器Demo页面"""
    return render_template('wechat-editor-demo.html')

@app.route('/publish-preview-test')
def publish_preview_test():
    """发布预览组件测试页面"""
    return render_template('publish-preview-test.html')

@app.route('/api/upload/wechat-image', methods=['POST'])
def upload_wechat_image():
    """微信图片上传接口（上传到微信服务器并使用缓存）"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '没有文件'})

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '文件名为空'})

        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': '不支持的文件类型'})

        # 保存到临时文件
        filename = secure_filename(file.filename)
        timestamp = int(time.time() * 1000)
        ext = filename.rsplit('.', 1)[1].lower()
        new_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, new_filename)
        file.save(filepath)

        # 上传到微信（使用缓存）
        publisher = get_wechat_publisher()
        result = publisher.upload_image_with_cache(filepath)

        if result and result.get('url'):
            return jsonify({
                'success': True,
                'data': {
                    'url': result['url'],
                    'media_id': result.get('media_id', ''),
                    'local_path': f"/static/uploads/wechat/{new_filename}",
                    'from_cache': result.get('from_cache', False)
                }
            })
        else:
            # 微信上传失败，返回本地URL作为备用
            local_url = f"/static/uploads/wechat/{new_filename}"
            return jsonify({
                'success': True,
                'data': {
                    'url': local_url,
                    'media_id': '',
                    'local_path': local_url,
                    'fallback': True
                }
            })
    except Exception as e:
        logger.error(f"图片上传失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/upload/wechat-images-batch', methods=['POST'])
def upload_wechat_images_batch():
    """批量上传图片到微信"""
    try:
        if 'files' not in request.files:
            return jsonify({'success': False, 'error': '没有文件'})

        files = request.files.getlist('files')
        if not files:
            return jsonify({'success': False, 'error': '文件列表为空'})

        # 保存所有文件到临时目录
        saved_paths = []
        for file in files:
            if file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = int(time.time() * 1000)
                ext = filename.rsplit('.', 1)[1].lower()
                new_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}.{ext}"
                filepath = os.path.join(UPLOAD_FOLDER, new_filename)
                file.save(filepath)
                saved_paths.append(filepath)

        if not saved_paths:
            return jsonify({'success': False, 'error': '没有有效的图片文件'})

        # 批量上传到微信
        publisher = get_wechat_publisher()
        results = publisher.upload_images_batch(saved_paths, use_cache=True)

        return jsonify({
            'success': True,
            'data': {
                'total': len(results),
                'succeeded': sum(1 for r in results if r['success']),
                'failed': sum(1 for r in results if not r['success']),
                'results': results
            }
        })
    except Exception as e:
        logger.error(f"批量上传图片失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ==================== 微信发布历史与监控 ====================

@app.route('/api/wechat/publish-records', methods=['GET'])
def list_wechat_publish_records():
    """获取发布历史（支持状态、时间过滤）"""
    try:
        limit = int(request.args.get('limit', 50))
        status = request.args.get('status')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        records = db.get_publish_records(
            limit=limit, status=status,
            start_date=start_date, end_date=end_date
        )

        # 统计
        stats = {
            'total': len(records),
            'published': sum(1 for r in records if r['status'] == 'published'),
            'draft': sum(1 for r in records if r['status'] == 'draft'),
            'failed': sum(1 for r in records if r['status'] == 'failed'),
            'pending': sum(1 for r in records if r['status'] == 'pending'),
        }

        return jsonify({
            'success': True,
            'data': {'records': records, 'stats': stats}
        })
    except Exception as e:
        logger.error(f"获取发布历史失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/wechat/publish-records/<int:record_id>', methods=['GET'])
def get_wechat_publish_record(record_id):
    """获取单条发布记录详情"""
    try:
        record = db.get_publish_record(record_id)
        if not record:
            return jsonify({'success': False, 'error': '发布记录不存在'})

        # 如果有publish_id，查询微信最新状态
        if record.get('status') == 'published' and record.get('result'):
            try:
                result_data = json.loads(record['result'])
                publish_id = result_data.get('publish_id')
                if publish_id:
                    publisher = get_wechat_publisher()
                    wechat_status = publisher.get_publish_status(publish_id)
                    record['wechat_status'] = wechat_status
            except Exception:
                pass

        return jsonify({'success': True, 'data': record})
    except Exception as e:
        logger.error(f"获取发布详情失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


# 异步发布任务状态存储（内存 + 数据库）
_publish_tasks = {}
_publish_tasks_lock = threading.Lock()


def _async_publish_worker(task_id: str, article_ids: list,
                         publish_type: str, collection_id: int = None):
    """后台发布任务"""
    with _publish_tasks_lock:
        _publish_tasks[task_id] = {
            'task_id': task_id,
            'status': 'running',
            'progress': 0,
            'total': len(article_ids) if article_ids else 1,
            'completed': 0,
            'results': [],
            'started_at': datetime.now().isoformat(),
            'completed_at': None,
            'error': None
        }

    try:
        if collection_id:
            # 合集发布
            publisher = get_wechat_publisher()
            result = publisher.publish_collection(
                collection_id, db, publish_now=(publish_type == 'publish')
            )
            with _publish_tasks_lock:
                _publish_tasks[task_id]['results'].append(result)
                _publish_tasks[task_id]['completed'] = 1
                _publish_tasks[task_id]['progress'] = 100
                _publish_tasks[task_id]['status'] = (
                    'success' if result['status'] in ('draft', 'published') else 'failed'
                )
        else:
            # 单文章批量发布
            publisher = get_wechat_publisher()
            total = len(article_ids)
            for i, article_id in enumerate(article_ids):
                article = db.get_generated_article_by_id(article_id)
                if not article:
                    continue
                result = publisher.publish_article(article, db, publish_type)
                with _publish_tasks_lock:
                    _publish_tasks[task_id]['results'].append(result)
                    _publish_tasks[task_id]['completed'] = i + 1
                    _publish_tasks[task_id]['progress'] = int((i + 1) / total * 100)

            with _publish_tasks_lock:
                _publish_tasks[task_id]['status'] = 'success'

        with _publish_tasks_lock:
            _publish_tasks[task_id]['completed_at'] = datetime.now().isoformat()

    except Exception as e:
        logger.error(f"异步发布任务失败 {task_id}: {e}")
        with _publish_tasks_lock:
            _publish_tasks[task_id]['status'] = 'failed'
            _publish_tasks[task_id]['error'] = str(e)
            _publish_tasks[task_id]['completed_at'] = datetime.now().isoformat()


@app.route('/api/wechat/publish/async', methods=['POST'])
def async_publish():
    """异步发布（返回task_id供轮询）"""
    try:
        data = request.json or {}
        article_ids = data.get('article_ids', [])
        collection_id = data.get('collection_id')
        publish_type = data.get('publish_type', 'draft')

        if not article_ids and not collection_id:
            return jsonify({'success': False, 'error': '请提供article_ids或collection_id'})

        task_id = uuid.uuid4().hex
        thread = threading.Thread(
            target=_async_publish_worker,
            args=(task_id, article_ids, publish_type, collection_id),
            daemon=True
        )
        thread.start()

        return jsonify({
            'success': True,
            'data': {
                'task_id': task_id,
                'status': 'running',
                'message': '发布任务已启动'
            }
        })
    except Exception as e:
        logger.error(f"启动异步发布失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/wechat/publish/status/<task_id>', methods=['GET'])
def get_async_publish_status(task_id):
    """查询异步发布任务状态"""
    try:
        with _publish_tasks_lock:
            task = _publish_tasks.get(task_id)

        if not task:
            return jsonify({'success': False, 'error': '任务不存在或已清理'})

        return jsonify({'success': True, 'data': task})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/wechat/publish-records/<int:record_id>/retry', methods=['POST'])
def retry_wechat_publish(record_id):
    """重试失败的发布（最多3次）"""
    try:
        record = db.get_publish_record(record_id)
        if not record:
            return jsonify({'success': False, 'error': '发布记录不存在'})

        if record['status'] != 'failed':
            return jsonify({'success': False, 'error': '只能重试失败的发布'})

        # 解析重试次数
        result_data = {}
        try:
            result_data = json.loads(record.get('result') or '{}')
        except Exception:
            pass

        retry_count = result_data.get('retry_count', 0)
        if retry_count >= 3:
            return jsonify({'success': False, 'error': '已达最大重试次数(3次)'})

        # 获取原文章并重试
        article_id = record.get('article_id')
        article = db.get_generated_article_by_id(article_id)
        if not article:
            return jsonify({'success': False, 'error': '原文章不存在'})

        publish_type = record.get('publish_type', 'draft')
        publisher = get_wechat_publisher()
        new_result = publisher.publish_article(article, db, publish_type)

        # 更新原记录
        new_result_data = {
            'retry_count': retry_count + 1,
            'retry_at': datetime.now().isoformat(),
            'previous_record_id': record_id,
            'new_status': new_result['status']
        }

        db.update_publish_record(record_id, {
            'result': json.dumps(new_result_data, ensure_ascii=False)
        })

        return jsonify({
            'success': True,
            'data': {
                'retry_count': retry_count + 1,
                'new_status': new_result['status'],
                'new_result': new_result
            }
        })
    except Exception as e:
        logger.error(f"重试发布失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ==================== 图片素材库管理 ====================

@app.route('/api/wechat/media-cache', methods=['GET'])
def list_media_cache():
    """查询本地缓存的图片"""
    try:
        limit = int(request.args.get('limit', 100))
        cache_list = db.get_all_media_cache(limit=limit)
        return jsonify({
            'success': True,
            'data': {
                'total': len(cache_list),
                'items': cache_list
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/wechat/media-cache/<int:cache_id>', methods=['DELETE'])
def delete_media_cache_item(cache_id):
    """删除单个缓存项"""
    try:
        if db.delete_media_cache(cache_id):
            return jsonify({'success': True, 'message': '删除成功'})
        return jsonify({'success': False, 'error': '缓存项不存在'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/wechat/media-cache/cleanup', methods=['POST'])
def cleanup_media_cache_items():
    """清理3天前的缓存"""
    try:
        data = request.json or {}
        keep_hours = data.get('keep_hours', 72)
        deleted = db.cleanup_expired_media_cache(keep_hours=keep_hours)
        return jsonify({
            'success': True,
            'data': {
                'deleted': deleted,
                'keep_hours': keep_hours
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


if __name__ == '__main__':
    print("=" * 60)
    print("InfoHub Web 管理界面")
    print("=" * 60)
    print("访问地址: http://localhost:9000")
    print("按 Ctrl+C 停止服务器")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=9000)
