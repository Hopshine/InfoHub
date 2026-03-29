// 全局变量
let currentPage = 1;
let allArticles = [];
let statsData = {};
let currentJobId = null;
let sseSource = null;
let selectedArticles = new Set();

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', function() {
    loadStats();
    loadArticles();
    loadSidebarTrending();
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
        <div class="article-item">
            <div class="article-checkbox">
                <input type="checkbox"
                       class="article-select-checkbox"
                       data-article-id="${article.id}"
                       onchange="toggleArticleSelection(${article.id})"
                       ${selectedArticles.has(article.id) ? 'checked' : ''}>
            </div>
            <div class="article-content" onclick="showArticleDetail(${article.id})">
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
        </div>
    `).join('');

    updateBulkActionsBar();
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
                        <div class="markdown-body">${renderMarkdown(article.analysis)}</div>
                    </div>
                ` : ''}

                ${article.content ? `
                    <div class="detail-section">
                        <h3>📄 文章内容</h3>
                        <p style="white-space: pre-wrap;">${escapeHtml(article.content.substring(0, 1000))}${article.content.length > 1000 ? '...' : ''}</p>
                    </div>
                ` : ''}

                <div class="detail-actions">
                    ${!article.analysis ? `
                        <button class="btn btn-success" onclick="analyzeArticle(${article.id})">
                            🤖 立即分析
                        </button>
                    ` : ''}
                    <button class="btn btn-danger" onclick="deleteArticle(${article.id})">
                        🗑️ 删除文章
                    </button>
                </div>

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

// ==================== 多选与批量操作 ====================

// 切换文章选择
function toggleArticleSelection(articleId) {
    if (selectedArticles.has(articleId)) {
        selectedArticles.delete(articleId);
    } else {
        selectedArticles.add(articleId);
    }
    updateBulkActionsBar();
    updateSelectAllCheckbox();
}

// 全选/取消全选
function toggleSelectAll() {
    const checkbox = document.getElementById('select-all-checkbox');
    const checkboxes = document.querySelectorAll('.article-select-checkbox');

    if (checkbox.checked) {
        checkboxes.forEach(cb => {
            const articleId = parseInt(cb.dataset.articleId);
            selectedArticles.add(articleId);
            cb.checked = true;
        });
    } else {
        selectedArticles.clear();
        checkboxes.forEach(cb => cb.checked = false);
    }

    updateBulkActionsBar();
}

// 更新全选复选框状态
function updateSelectAllCheckbox() {
    const checkbox = document.getElementById('select-all-checkbox');
    const checkboxes = document.querySelectorAll('.article-select-checkbox');
    const allChecked = checkboxes.length > 0 && Array.from(checkboxes).every(cb => cb.checked);
    checkbox.checked = allChecked;
}

// 更新批量操作栏
function updateBulkActionsBar() {
    const bar = document.getElementById('bulk-actions-bar');
    const count = document.getElementById('selected-count');

    if (selectedArticles.size > 0) {
        bar.style.display = 'block';
        count.textContent = `已选择 ${selectedArticles.size} 篇文章`;
    } else {
        bar.style.display = 'none';
    }
}

// 清除选择
function clearSelection() {
    selectedArticles.clear();
    document.querySelectorAll('.article-select-checkbox').forEach(cb => cb.checked = false);
    document.getElementById('select-all-checkbox').checked = false;
    updateBulkActionsBar();
}

// 批量删除
async function bulkDelete() {
    if (selectedArticles.size === 0) {
        alert('请先选择要删除的文章');
        return;
    }

    if (!confirm(`确定要删除选中的 ${selectedArticles.size} 篇文章吗？此操作不可恢复。`)) {
        return;
    }

    try {
        const response = await fetch('/api/articles/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ article_ids: Array.from(selectedArticles) })
        });

        const result = await response.json();

        if (result.success) {
            alert(`成功删除 ${result.data.deleted_count} 篇文章`);
            clearSelection();
            refreshData();
        } else {
            alert('删除失败: ' + result.error);
        }
    } catch (error) {
        console.error('删除失败:', error);
        alert('删除失败，请重试');
    }
}

// 批量分析选中文章
async function bulkAnalyze() {
    if (selectedArticles.size === 0) {
        alert('请先选择要分析的文章');
        return;
    }

    if (!confirm(`确定要分析选中的 ${selectedArticles.size} 篇文章吗？这将调用Claude API并产生费用。`)) {
        return;
    }

    const articleIds = Array.from(selectedArticles);
    let successCount = 0;
    let failCount = 0;

    for (const articleId of articleIds) {
        try {
            const response = await fetch(`/api/analyze/${articleId}`, {
                method: 'POST'
            });
            const result = await response.json();

            if (result.success) {
                successCount++;
            } else {
                failCount++;
            }
        } catch (error) {
            console.error(`分析文章 ${articleId} 失败:`, error);
            failCount++;
        }
    }

    alert(`批量分析完成！\n成功: ${successCount} 篇\n失败: ${failCount} 篇`);
    clearSelection();
    refreshData();
}

// 删除单篇文章
async function deleteArticle(articleId) {
    if (!confirm('确定要删除这篇文章吗？此操作不可恢复。')) {
        return;
    }

    try {
        const response = await fetch(`/api/article/${articleId}`, {
            method: 'DELETE'
        });
        const result = await response.json();

        if (result.success) {
            alert('删除成功');
            closeModal();
            refreshData();
        } else {
            alert('删除失败: ' + result.error);
        }
    } catch (error) {
        console.error('删除失败:', error);
        alert('删除失败，请重试');
    }
}

// 渲染Markdown
function renderMarkdown(text) {
    if (!text) return '';
    if (typeof marked === 'undefined' || typeof DOMPurify === 'undefined') {
        return escapeHtml(text);
    }
    const html = marked.parse(text);
    return DOMPurify.sanitize(html);
}

// ==================== 首页热点侧边栏 ====================

let sidebarTrendingData = {};
let currentSidebarPlatform = 'weibo';

async function loadSidebarTrending() {
    try {
        const resp = await fetch('/api/trending');
        const data = await resp.json();
        if (data.success) {
            sidebarTrendingData = data.data.trending || {};
            renderSidebarTrending();
        }
    } catch (e) {
        const list = document.getElementById('sidebar-trending-list');
        if (list) list.innerHTML = '<div style="padding:20px;color:#a0aec0;text-align:center;">加载失败</div>';
    }
}

function switchSidebarTab(platform) {
    currentSidebarPlatform = platform;
    document.querySelectorAll('#sidebar-tabs .sidebar-tab').forEach(tab => {
        tab.classList.toggle('active', tab.textContent.includes(
            {weibo:'微博',zhihu:'知乎',baidu:'百度',douyin:'抖音'}[platform]
        ));
    });
    renderSidebarTrending();
}

function renderSidebarTrending() {
    const list = document.getElementById('sidebar-trending-list');
    if (!list) return;

    const items = sidebarTrendingData[currentSidebarPlatform] || [];

    if (items.length === 0) {
        list.innerHTML = '<div style="padding:20px;color:#a0aec0;text-align:center;">暂无数据</div>';
        return;
    }

    list.innerHTML = items.slice(0, 15).map(item => {
        const rank = item.rank_num || item.rank;
        const rankClass = rank <= 3 ? ` top${rank}` : '';
        const url = item.url || '#';
        return `<a class="sidebar-item" href="${url}" target="_blank" rel="noopener">
            <span class="sidebar-rank${rankClass}">${rank}</span>
            <span class="sidebar-title">${escapeHtml(item.title)}</span>
        </a>`;
    }).join('');
}

// ==================== 生成文章功能 ====================

function showGenerateModal() {
    document.getElementById('generate-modal').style.display = 'block';
}

function closeGenerateModal() {
    document.getElementById('generate-modal').style.display = 'none';
    document.getElementById('generate-result').innerHTML = '';
}

async function generateArticles() {
    const count = parseInt(document.getElementById('generate-count').value) || 5;
    const style = document.getElementById('generate-style').value;
    const resultDiv = document.getElementById('generate-result');

    resultDiv.innerHTML = '<div class="loading">生成中...</div>';

    try {
        const resp = await fetch('/api/generate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({count, style})
        });
        const data = await resp.json();

        if (data.success) {
            resultDiv.innerHTML = `<div class="success">✓ 成功生成 ${data.data.generated} 篇文章</div>`;
            setTimeout(() => closeGenerateModal(), 2000);
        } else {
            resultDiv.innerHTML = `<div class="error">✗ ${data.error}</div>`;
        }
    } catch (e) {
        resultDiv.innerHTML = `<div class="error">✗ ${e.message}</div>`;
    }
}

// ==================== 发布管理功能 ====================

function showPublishModal() {
    document.getElementById('publish-modal').style.display = 'block';
    loadDrafts();
}

function closePublishModal() {
    document.getElementById('publish-modal').style.display = 'none';
}

function switchPublishTab(tab) {
    document.querySelectorAll('.publish-tabs .tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.textContent.includes(tab === 'drafts' ? '草稿' : '发布'));
    });
    document.querySelectorAll('.publish-tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`publish-${tab}-tab`).classList.add('active');

    if (tab === 'drafts') loadDrafts();
    else loadPublished();
}

async function loadDrafts() {
    const listDiv = document.getElementById('drafts-list');
    listDiv.innerHTML = '<div class="loading">加载中...</div>';

    try {
        const resp = await fetch('/api/drafts');
        const data = await resp.json();

        if (data.success && data.data.length > 0) {
            listDiv.innerHTML = data.data.map(article => `
                <div class="draft-item" style="border:1px solid #e2e8f0;padding:15px;margin:10px 0;border-radius:8px;">
                    <h4>${escapeHtml(article.title)}</h4>
                    <p style="color:#718096;font-size:0.9em;">${escapeHtml(article.summary || '').substring(0, 100)}</p>
                    <div style="margin-top:10px;">
                        <button class="btn btn-sm btn-success" onclick="publishArticle(${article.id}, 'draft')">发布到草稿箱</button>
                        <button class="btn btn-sm btn-primary" onclick="publishArticle(${article.id}, 'publish')">直接发布</button>
                    </div>
                </div>
            `).join('');
        } else {
            listDiv.innerHTML = '<div style="padding:20px;text-align:center;color:#a0aec0;">暂无草稿</div>';
        }
    } catch (e) {
        listDiv.innerHTML = `<div class="error">加载失败: ${e.message}</div>`;
    }
}

async function loadPublished() {
    const listDiv = document.getElementById('published-list');
    listDiv.innerHTML = '<div class="loading">加载中...</div>';

    try {
        const resp = await fetch('/api/published');
        const data = await resp.json();

        if (data.success && data.data.length > 0) {
            listDiv.innerHTML = data.data.map(record => `
                <div class="publish-item" style="border:1px solid #e2e8f0;padding:15px;margin:10px 0;border-radius:8px;">
                    <div><strong>文章ID:</strong> ${record.article_id}</div>
                    <div><strong>状态:</strong> <span class="badge badge-${record.status}">${record.status}</span></div>
                    <div><strong>发布时间:</strong> ${record.published_at || record.created_at}</div>
                    <div style="color:#718096;font-size:0.9em;margin-top:5px;">${escapeHtml(record.result)}</div>
                </div>
            `).join('');
        } else {
            listDiv.innerHTML = '<div style="padding:20px;text-align:center;color:#a0aec0;">暂无发布记录</div>';
        }
    } catch (e) {
        listDiv.innerHTML = `<div class="error">加载失败: ${e.message}</div>`;
    }
}

async function publishArticle(articleId, publishType) {
    if (!confirm(`确定要${publishType === 'draft' ? '发布到草稿箱' : '直接发布'}吗？`)) return;

    try {
        const resp = await fetch('/api/publish', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({article_ids: [articleId], publish_type: publishType})
        });
        const data = await resp.json();

        if (data.success) {
            alert('发布成功！');
            loadDrafts();
        } else {
            alert('发布失败: ' + data.error);
        }
    } catch (e) {
        alert('发布失败: ' + e.message);
    }
}

// ==================== 公众号管理 ====================

function showAccountModal() {
    document.getElementById('account-modal').style.display = 'block';
    loadAccounts();
}

function closeAccountModal() {
    document.getElementById('account-modal').style.display = 'none';
    hideAccountForm();
}

function showAccountForm() {
    document.getElementById('account-form').style.display = 'block';
    document.getElementById('account-id').value = '';
    document.getElementById('account-name').value = '';
    document.getElementById('account-appid').value = '';
    document.getElementById('account-secret').value = '';
    document.getElementById('account-keywords').value = '';
    document.getElementById('account-style').value = 'news';
    document.getElementById('account-prompt').value = '';
}

function hideAccountForm() {
    document.getElementById('account-form').style.display = 'none';
}

async function loadAccounts() {
    try {
        const resp = await fetch('/api/accounts');
        const data = await resp.json();

        if (data.success) {
            const listDiv = document.getElementById('accounts-list');
            if (data.data.length === 0) {
                listDiv.innerHTML = '<div style="padding:20px;text-align:center;color:#a0aec0;">暂无公众号配置</div>';
                return;
            }

            listDiv.innerHTML = data.data.map(acc => `
                <div style="border:1px solid #e2e8f0;padding:15px;margin:10px 0;border-radius:8px;">
                    <div style="display:flex;justify-content:space-between;align-items:start;">
                        <div style="flex:1;">
                            <div style="font-weight:bold;font-size:1.1em;margin-bottom:8px;">${escapeHtml(acc.name)}</div>
                            <div style="color:#718096;font-size:0.9em;">AppID: ${escapeHtml(acc.app_id)}</div>
                            <div style="color:#718096;font-size:0.9em;">风格: ${acc.style_preference || 'news'}</div>
                            <div style="color:#718096;font-size:0.9em;">关键词: ${escapeHtml(acc.topic_keywords || '无')}</div>
                        </div>
                        <div>
                            <button class="btn btn-sm" onclick="editAccount(${acc.id})">编辑</button>
                            <button class="btn btn-sm btn-danger" onclick="deleteAccount(${acc.id})">删除</button>
                        </div>
                    </div>
                </div>
            `).join('');
        }
    } catch (e) {
        console.error('加载公众号失败:', e);
    }
}

async function saveAccount() {
    const id = document.getElementById('account-id').value;
    const data = {
        name: document.getElementById('account-name').value,
        app_id: document.getElementById('account-appid').value,
        app_secret: document.getElementById('account-secret').value,
        topic_keywords: document.getElementById('account-keywords').value,
        style_preference: document.getElementById('account-style').value,
        custom_prompt: document.getElementById('account-prompt').value
    };

    if (!data.name || !data.app_id || !data.app_secret) {
        alert('请填写必填项');
        return;
    }

    try {
        const url = id ? `/api/accounts/${id}` : '/api/accounts';
        const method = id ? 'PUT' : 'POST';

        const resp = await fetch(url, {
            method: method,
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        const result = await resp.json();

        if (result.success) {
            alert('保存成功');
            hideAccountForm();
            loadAccounts();
        } else {
            alert('保存失败: ' + result.error);
        }
    } catch (e) {
        alert('保存失败: ' + e.message);
    }
}

async function editAccount(accountId) {
    try {
        const resp = await fetch('/api/accounts');
        const data = await resp.json();
        const account = data.data.find(a => a.id === accountId);

        if (account) {
            document.getElementById('account-id').value = account.id;
            document.getElementById('account-name').value = account.name;
            document.getElementById('account-appid').value = account.app_id;
            document.getElementById('account-secret').value = account.app_secret;
            document.getElementById('account-keywords').value = account.topic_keywords || '';
            document.getElementById('account-style').value = account.style_preference || 'news';
            document.getElementById('account-prompt').value = account.custom_prompt || '';
            document.getElementById('account-form').style.display = 'block';
        }
    } catch (e) {
        alert('加载失败: ' + e.message);
    }
}

async function deleteAccount(accountId) {
    if (!confirm('确定删除此公众号配置？')) return;

    try {
        const resp = await fetch(`/api/accounts/${accountId}`, {method: 'DELETE'});
        const data = await resp.json();

        if (data.success) {
            alert('删除成功');
            loadAccounts();
        } else {
            alert('删除失败: ' + data.error);
        }
    } catch (e) {
        alert('删除失败: ' + e.message);
    }
}

// ==================== 智能工作流 ====================

async function startWorkflow(hotnewsId, parallel = true) {
    try {
        const resp = await fetch('/api/workflow/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({hotnews_id: hotnewsId, parallel: parallel})
        });
        const data = await resp.json();

        if (data.success) {
            alert(`工作流启动成功，处理了 ${data.data.length} 个公众号`);
            loadPendingReviews();
        } else {
            alert('启动失败: ' + data.error);
        }
    } catch (e) {
        alert('启动失败: ' + e.message);
    }
}

async function loadPendingReviews() {
    try {
        const resp = await fetch('/api/workflow/pending');
        const data = await resp.json();

        if (data.success && data.data.length > 0) {
            console.log('待审核任务:', data.data);
        }
    } catch (e) {
        console.error('加载待审核任务失败:', e);
    }
}

async function submitReview(threadId, decision) {
    try {
        const resp = await fetch('/api/workflow/review', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({thread_id: threadId, decision: decision})
        });
        const data = await resp.json();

        if (data.success) {
            alert('审核提交成功');
            loadPendingReviews();
        } else {
            alert('提交失败: ' + data.error);
        }
    } catch (e) {
        alert('提交失败: ' + e.message);
    }
}
