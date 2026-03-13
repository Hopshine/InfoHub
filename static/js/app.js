// 全局变量
let currentPage = 1;
let allArticles = [];
let statsData = {};
let currentJobId = null;
let sseSource = null;

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', function() {
    loadStats();
    loadArticles();
});

// 加载统计信息
async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const result = await response.json();

        if (result.success) {
            statsData = result.data;
            updateStatsDisplay();
            updateCategoryFilter();
        }
    } catch (error) {
        console.error('加载统计信息失败:', error);
    }
}

// 更新统计显示
function updateStatsDisplay() {
    document.getElementById('total-articles').textContent = statsData.total || 0;
    document.getElementById('analyzed-articles').textContent = statsData.analyzed || 0;
    document.getElementById('pending-articles').textContent = statsData.pending || 0;
    document.getElementById('categories-count').textContent =
        Object.keys(statsData.categories || {}).length;
}

// 更新分类过滤器
function updateCategoryFilter() {
    const select = document.getElementById('category-filter');
    select.innerHTML = '<option value="">全部分类</option>';

    if (statsData.categories) {
        Object.keys(statsData.categories).forEach(category => {
            const option = document.createElement('option');
            option.value = category;
            option.textContent = `${category} (${statsData.categories[category]})`;
            select.appendChild(option);
        });
    }
}

// 加载文章列表
async function loadArticles(page = 1) {
    const listElement = document.getElementById('articles-list');
    listElement.innerHTML = '<div class="loading">加载中...</div>';

    try {
        const response = await fetch(`/api/articles?page=${page}&limit=20`);
        const result = await response.json();

        if (result.success) {
            allArticles = result.data.articles;
            currentPage = page;
            displayArticles(allArticles);
            updatePagination(result.data);
        }
    } catch (error) {
        console.error('加载文章失败:', error);
        listElement.innerHTML = '<div class="loading">加载失败，请重试</div>';
    }
}

// 显示文章列表
function displayArticles(articles) {
    const listElement = document.getElementById('articles-list');

    if (articles.length === 0) {
        listElement.innerHTML = '<div class="loading">暂无文章</div>';
        return;
    }

    listElement.innerHTML = articles.map(article => `
        <div class="article-item" onclick="showArticleDetail(${article.id})">
            <div class="article-header">
                <div class="article-title">${escapeHtml(article.title)}</div>
                <span class="article-status ${article.analysis ? 'status-analyzed' : 'status-pending'}">
                    ${article.analysis ? '已分析' : '待分析'}
                </span>
            </div>
            <div class="article-meta">
                <span>📱 ${escapeHtml(article.account_name || '未知')}</span>
                <span>📅 ${article.publish_time || '未知'}</span>
                ${article.category ? `<span>🏷️ ${escapeHtml(article.category)}</span>` : ''}
            </div>
            ${article.summary ? `
                <div class="article-summary">${escapeHtml(article.summary)}</div>
            ` : ''}
            ${article.keywords ? `
                <div class="article-tags">
                    ${article.keywords.split(',').map(k =>
                        `<span class="tag">${escapeHtml(k.trim())}</span>`
                    ).join('')}
                </div>
            ` : ''}
        </div>
    `).join('');
}

// 更新分页信息
function updatePagination(data) {
    document.getElementById('page-info').textContent = `第 ${data.page} 页`;
}

// 过滤文章
function filterArticles() {
    const searchText = document.getElementById('search-input').value.toLowerCase();
    const category = document.getElementById('category-filter').value;

    const filtered = allArticles.filter(article => {
        const matchSearch = !searchText ||
            article.title.toLowerCase().includes(searchText) ||
            (article.summary && article.summary.toLowerCase().includes(searchText));

        const matchCategory = !category || article.category === category;

        return matchSearch && matchCategory;
    });

    displayArticles(filtered);
}

// 显示文章详情
async function showArticleDetail(articleId) {
    try {
        const response = await fetch(`/api/article/${articleId}`);
        const result = await response.json();

        if (result.success) {
            const article = result.data;
            const detailHtml = `
                <h2>${escapeHtml(article.title)}</h2>

                <div class="detail-meta">
                    <p><strong>公众号:</strong> ${escapeHtml(article.account_name || '未知')}</p>
                    <p><strong>作者:</strong> ${escapeHtml(article.author || '未知')}</p>
                    <p><strong>发布时间:</strong> ${article.publish_time || '未知'}</p>
                    ${article.category ? `<p><strong>分类:</strong> ${escapeHtml(article.category)}</p>` : ''}
                    ${article.keywords ? `<p><strong>关键词:</strong> ${escapeHtml(article.keywords)}</p>` : ''}
                </div>

                ${article.summary ? `
                    <div class="detail-section">
                        <h3>📝 摘要</h3>
                        <p>${escapeHtml(article.summary)}</p>
                    </div>
                ` : ''}

                ${article.analysis ? `
                    <div class="detail-section">
                        <h3>🔍 深度分析</h3>
                        <p style="white-space: pre-wrap;">${escapeHtml(article.analysis)}</p>
                    </div>
                ` : ''}

                ${article.content ? `
                    <div class="detail-section">
                        <h3>📄 文章内容</h3>
                        <p style="white-space: pre-wrap;">${escapeHtml(article.content.substring(0, 1000))}${article.content.length > 1000 ? '...' : ''}</p>
                    </div>
                ` : ''}

                ${!article.analysis ? `
                    <button class="btn btn-success" onclick="analyzeArticle(${article.id})">
                        🤖 立即分析
                    </button>
                ` : ''}

                <p style="margin-top: 20px; color: #666;">
                    <a href="${article.url}" target="_blank" style="color: #667eea;">查看原文 →</a>
                </p>
            `;

            document.getElementById('article-detail').innerHTML = detailHtml;
            document.getElementById('article-modal').style.display = 'block';
        }
    } catch (error) {
        console.error('加载文章详情失败:', error);
        alert('加载失败，请重试');
    }
}

// 关闭模态框
function closeModal() {
    document.getElementById('article-modal').style.display = 'none';
}

// 分析单篇文章
async function analyzeArticle(articleId) {
    if (!confirm('确定要分析这篇文章吗？这将调用Claude API并产生费用。')) {
        return;
    }

    const btn = event.target;
    btn.disabled = true;
    btn.textContent = '分析中...';

    try {
        const response = await fetch(`/api/analyze/${articleId}`, {
            method: 'POST'
        });
        const result = await response.json();

        if (result.success) {
            alert('分析完成！');
            closeModal();
            refreshData();
        } else {
            alert('分析失败: ' + result.error);
        }
    } catch (error) {
        console.error('分析失败:', error);
        alert('分析失败，请重试');
    } finally {
        btn.disabled = false;
        btn.textContent = '🤖 立即分析';
    }
}

// 批量分析
async function analyzeBatch() {
    const limit = prompt('请输入要分析的文章数量（建议不超过10篇）:', '5');

    if (!limit || isNaN(limit) || limit <= 0) {
        return;
    }

    if (!confirm(`确定要分析 ${limit} 篇文章吗？这将调用Claude API并产生费用。`)) {
        return;
    }

    const btn = event.target;
    btn.disabled = true;
    btn.textContent = '分析中...';

    try {
        const response = await fetch('/api/analyze/batch', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ limit: parseInt(limit) })
        });
        const result = await response.json();

        if (result.success) {
            const success = result.data.filter(r => r.success).length;
            const failed = result.data.filter(r => !r.success).length;
            alert(`批量分析完成！\n成功: ${success} 篇\n失败: ${failed} 篇`);
            refreshData();
        } else {
            alert('批量分析失败: ' + result.error);
        }
    } catch (error) {
        console.error('批量分析失败:', error);
        alert('批量分析失败，请重试');
    } finally {
        btn.disabled = false;
        btn.textContent = '🤖 批量分析';
    }
}

// 显示分类统计
function showCategories() {
    if (!statsData.categories || Object.keys(statsData.categories).length === 0) {
        alert('暂无分类数据');
        return;
    }

    const maxCount = Math.max(...Object.values(statsData.categories));
    const chartHtml = Object.entries(statsData.categories)
        .sort((a, b) => b[1] - a[1])
        .map(([category, count]) => {
            const width = (count / maxCount) * 100;
            return `
                <div class="category-item">
                    <div class="category-name">${escapeHtml(category)}</div>
                    <div class="category-bar" style="width: ${width}%"></div>
                    <div class="category-count">${count}</div>
                </div>
            `;
        }).join('');

    document.getElementById('categories-chart').innerHTML = chartHtml;
    document.getElementById('categories-modal').style.display = 'block';
}

// 关闭分类统计模态框
function closeCategoriesModal() {
    document.getElementById('categories-modal').style.display = 'none';
}

// 刷新数据
function refreshData() {
    loadStats();
    loadArticles(currentPage);
}

// 上一页
function prevPage() {
    if (currentPage > 1) {
        loadArticles(currentPage - 1);
    }
}

// 下一页
function nextPage() {
    loadArticles(currentPage + 1);
}

// HTML转义
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 点击模态框外部关闭
window.onclick = function(event) {
    const articleModal = document.getElementById('article-modal');
    const categoriesModal = document.getElementById('categories-modal');
    const collectModal = document.getElementById('collect-modal');

    if (event.target === articleModal) {
        closeModal();
    }
    if (event.target === categoriesModal) {
        closeCategoriesModal();
    }
    if (event.target === collectModal) {
        closeCollectModal();
    }
}

// ==================== 采集功能 ====================

// 显示采集模态框
function showCollectModal() {
    document.getElementById('collect-modal').style.display = 'block';
    document.getElementById('collect-result').innerHTML = '';
    document.getElementById('collect-result').className = 'collect-result';
    // 重置进度
    const progressDiv = document.getElementById('crawl-progress');
    progressDiv.style.display = 'none';
    document.getElementById('cancel-crawl-btn').style.display = '';
    document.getElementById('progress-step').style.color = '';
}

// 关闭采集模态框
function closeCollectModal() {
    document.getElementById('collect-modal').style.display = 'none';
    // 关闭SSE连接
    if (sseSource) {
        sseSource.close();
        sseSource = null;
    }
}

// 切换采集标签页
function switchCollectTab(tab) {
    // 隐藏所有标签页
    document.querySelectorAll('.collect-tab-content').forEach(el => {
        el.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(el => {
        el.classList.remove('active');
    });

    // 显示选中的标签页
    if (tab === 'url') {
        document.getElementById('collect-url-tab').classList.add('active');
        document.querySelectorAll('.tab-btn')[0].classList.add('active');
    } else if (tab === 'batch') {
        document.getElementById('collect-batch-tab').classList.add('active');
        document.querySelectorAll('.tab-btn')[1].classList.add('active');
    } else if (tab === 'search') {
        document.getElementById('collect-search-tab').classList.add('active');
        document.querySelectorAll('.tab-btn')[2].classList.add('active');
    }

    // 清空结果
    document.getElementById('collect-result').innerHTML = '';
}

// 采集单个URL（使用新爬虫引擎）
async function collectSingleUrl() {
    const url = document.getElementById('single-url-input').value.trim();

    if (!url) {
        showCollectResult('请输入URL', 'error');
        return;
    }

    if (!url.startsWith('http')) {
        showCollectResult('请输入有效的URL', 'error');
        return;
    }

    startCrawlJob('single_url', { url: url });
}

// 批量采集URL（使用新爬虫引擎）
async function collectBatchUrls() {
    const textarea = document.getElementById('batch-urls-input');
    const urls = textarea.value.split('\n')
        .map(line => line.trim())
        .filter(line => line && line.startsWith('http'));

    if (urls.length === 0) {
        showCollectResult('请输入至少一个URL', 'error');
        return;
    }

    startCrawlJob('batch_url', { urls: urls });
}

// 搜索并采集（使用新爬虫引擎）
async function collectFromSearch() {
    const keyword = document.getElementById('search-keyword-input').value.trim();
    const maxResults = parseInt(document.getElementById('search-max-input').value) || 5;

    if (!keyword) {
        showCollectResult('请输入搜索关键词', 'error');
        return;
    }

    startCrawlJob('search', { keyword: keyword, max_results: maxResults });
}

// 显示采集结果
function showCollectResult(message, type) {
    const resultDiv = document.getElementById('collect-result');
    resultDiv.innerHTML = `<p>${message}</p>`;
    resultDiv.className = `collect-result ${type}`;
}

// ==================== 爬虫任务管理 ====================

// 启动采集任务
async function startCrawlJob(jobType, params) {
    const resultDiv = document.getElementById('collect-result');
    const progressDiv = document.getElementById('crawl-progress');

    resultDiv.innerHTML = '';
    resultDiv.className = 'collect-result';
    progressDiv.style.display = 'block';
    document.getElementById('progress-step').textContent = '提交任务中...';
    document.getElementById('progress-count').textContent = '0/0';
    document.getElementById('progress-bar').style.width = '0%';
    document.getElementById('progress-items').innerHTML = '';

    try {
        const response = await fetch('/api/crawl/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job_type: jobType, ...params })
        });

        const result = await response.json();

        if (result.success) {
            currentJobId = result.data.job_id;
            startSSE(currentJobId);
        } else {
            progressDiv.style.display = 'none';
            showCollectResult('任务提交失败: ' + result.error, 'error');
        }
    } catch (error) {
        progressDiv.style.display = 'none';
        showCollectResult('任务提交失败: ' + error.message, 'error');
    }
}

// 启动SSE实时进度
function startSSE(jobId) {
    if (sseSource) {
        sseSource.close();
    }

    sseSource = new EventSource('/api/crawl/stream/' + jobId);

    sseSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            updateProgress(data);

            if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
                sseSource.close();
                sseSource = null;
                onCrawlComplete(data);
            }
        } catch (e) {
            console.error('SSE解析错误:', e);
        }
    };

    sseSource.onerror = function() {
        sseSource.close();
        sseSource = null;
        // 降级为轮询
        pollProgress(jobId);
    };
}

// 轮询进度（SSE失败时的降级方案）
async function pollProgress(jobId) {
    const poll = async () => {
        try {
            const response = await fetch('/api/crawl/progress/' + jobId);
            const result = await response.json();

            if (result.success) {
                updateProgress(result.data);
                const status = result.data.status;
                if (status === 'completed' || status === 'failed' || status === 'cancelled') {
                    onCrawlComplete(result.data);
                    return;
                }
            }
        } catch (e) {
            console.error('轮询错误:', e);
        }
        setTimeout(poll, 1000);
    };
    poll();
}

// 更新进度UI
function updateProgress(data) {
    const stepEl = document.getElementById('progress-step');
    const countEl = document.getElementById('progress-count');
    const barEl = document.getElementById('progress-bar');
    const itemsEl = document.getElementById('progress-items');

    if (data.current_step) {
        stepEl.textContent = data.current_step;
    }

    if (data.total > 0) {
        countEl.textContent = data.completed + '/' + data.total;
        const pct = data.progress_pct || Math.round(data.completed / data.total * 100);
        barEl.style.width = pct + '%';
    }

    // 显示最新的结果项
    if (data.items && data.items.length > 0) {
        itemsEl.innerHTML = data.items.map(item => {
            if (item.success) {
                return '<div class="progress-item success">✓ ' + escapeHtml(item.title) + '</div>';
            } else {
                return '<div class="progress-item error">✗ ' + escapeHtml(item.title) +
                       (item.error ? ' (' + escapeHtml(item.error) + ')' : '') + '</div>';
            }
        }).join('');
        // 滚动到底部
        itemsEl.scrollTop = itemsEl.scrollHeight;
    }
}

// 采集完成回调
function onCrawlComplete(data) {
    const progressDiv = document.getElementById('crawl-progress');
    const cancelBtn = document.getElementById('cancel-crawl-btn');
    cancelBtn.style.display = 'none';

    const stepEl = document.getElementById('progress-step');
    if (data.status === 'completed') {
        stepEl.textContent = '采集完成';
        stepEl.style.color = '#48bb78';
    } else if (data.status === 'cancelled') {
        stepEl.textContent = '已取消';
        stepEl.style.color = '#ed8936';
    } else {
        stepEl.textContent = '采集失败';
        stepEl.style.color = '#e53e3e';
    }

    // 显示汇总
    const resultDiv = document.getElementById('collect-result');
    resultDiv.innerHTML = '<p>成功: ' + (data.succeeded || 0) +
                          ' | 失败: ' + (data.failed || 0) +
                          ' | 跳过: ' + ((data.completed || 0) - (data.succeeded || 0) - (data.failed || 0)) + '</p>';
    resultDiv.className = 'collect-result ' + (data.succeeded > 0 ? 'success' : 'error');

    currentJobId = null;
    setTimeout(() => refreshData(), 1000);
}

// 取消采集
async function cancelCrawl() {
    if (!currentJobId) return;

    try {
        const response = await fetch('/api/crawl/cancel/' + currentJobId, {
            method: 'POST'
        });
        const result = await response.json();
        if (!result.success) {
            console.error('取消失败:', result.error);
        }
    } catch (error) {
        console.error('取消失败:', error);
    }
}
