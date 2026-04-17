from flask import Flask, render_template, jsonify, request, Response
import sys
import os
import json
import time

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage.database import Database
from analyzer.content_analyzer import ContentAnalyzer
from collector.wechat_collector_v2 import WeChatCollectorV2
from collector.sogou_enhanced import SogouWeixinCollector
from config import Config
from crawler.job_manager import JobManager
from crawler.engine import CrawlEngine
from collector.trending_scheduler import TrendingScheduler
from collector.hotnews_article_collector import HotNewsArticleCollector
from generator.article_generator import ArticleGenerator
from publisher.wechat_publisher import WeChatPublisher
from generator.workflow_manager import WorkflowManager
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
        analyzer = ContentAnalyzer()
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

        limit = int(request.json.get('limit', 10))
        unanalyzed = db.get_unanalyzed_articles(limit=limit)

        analyzer = ContentAnalyzer()
        results = []

        for article in unanalyzed:
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
            except Exception as e:
                results.append({
                    'id': article['id'],
                    'title': article['title'],
                    'success': False,
                    'error': str(e)
                })

        return jsonify({
            'success': True,
            'data': results
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
        for news in news_list[:count]:
            article_id = article_generator.generate_and_save(db, news, style)
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


if __name__ == '__main__':
    print("=" * 60)
    print("InfoHub Web 管理界面")
    print("=" * 60)
    print("访问地址: http://localhost:9000")
    print("按 Ctrl+C 停止服务器")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=9000)
