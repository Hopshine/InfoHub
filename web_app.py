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

app = Flask(__name__)

# 初始化组件 - 优先使用demo.db（如果存在）
db_path = 'data/demo.db' if os.path.exists('data/demo.db') else Config.DATABASE_PATH
db = Database(db_path)
print(f"使用数据库: {db_path}")

# 初始化任务管理器
job_manager = JobManager(db)

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

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

@app.route('/api/analyze/<int:article_id>', methods=['POST'])
def analyze_article(article_id):
    """分析单篇文章"""
    try:
        # 检查API Key
        if not Config.ANTHROPIC_API_KEY:
            return jsonify({'success': False, 'error': '未配置ANTHROPIC_API_KEY'})

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
        analyzer = ContentAnalyzer(Config.ANTHROPIC_API_KEY)
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
        if not Config.ANTHROPIC_API_KEY:
            return jsonify({'success': False, 'error': '未配置ANTHROPIC_API_KEY'})

        limit = int(request.json.get('limit', 10))
        unanalyzed = db.get_unanalyzed_articles(limit=limit)

        analyzer = ContentAnalyzer(Config.ANTHROPIC_API_KEY)
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


if __name__ == '__main__':
    print("=" * 60)
    print("InfoHub Web 管理界面")
    print("=" * 60)
    print("访问地址: http://localhost:5000")
    print("按 Ctrl+C 停止服务器")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)
