// AI分析页面模块
let currentJobId = null;
let sseSource = null;
let selectedArticles = new Set();

function render() {
    return `
        <div class="analysis-container">
            <div class="analysis-header">
                <h2>AI分析队列</h2>
                <div class="analysis-actions">
                    <button class="btn btn-primary" onclick="analysisPage.selectAll()">全选</button>
                    <button class="btn btn-primary" onclick="analysisPage.deselectAll()">取消全选</button>
                    <button class="btn btn-success" onclick="analysisPage.startBatchAnalysis()">
                        批量分析 (<span id="selected-count">0</span>)
                    </button>
                </div>
            </div>

            <div class="analysis-filters">
                <select id="analysis-category-filter" onchange="analysisPage.filterArticles()">
                    <option value="">全部分类</option>
                </select>
                <select id="analysis-status-filter" onchange="analysisPage.filterArticles()">
                    <option value="pending">待分析</option>
                    <option value="analyzing">分析中</option>
                    <option value="completed">已完成</option>
                    <option value="failed">失败</option>
                </select>
            </div>

            <div id="analysis-progress" class="analysis-progress" style="display: none;">
                <div class="progress-info">
                    <span id="progress-text">准备中...</span>
                    <span id="progress-percent">0%</span>
                </div>
                <div class="progress-bar">
                    <div id="progress-fill" class="progress-fill"></div>
                </div>
            </div>

            <div id="analysis-queue" class="analysis-queue">
                <div class="loading">加载中...</div>
            </div>

            <div id="analysis-results" class="analysis-results" style="display: none;">
                <h3>分析结果</h3>
                <div id="results-content"></div>
            </div>
        </div>
    `;
}

function init() {
    loadPendingArticles();
    updateSelectedCount();
}

async function loadPendingArticles() {
    const queueElement = document.getElementById('analysis-queue');
    queueElement.innerHTML = '<div class="loading">加载中...</div>';

    try {
        const response = await fetch('/api/articles?status=pending&limit=100');
        const result = await response.json();

        if (result.success) {
            displayQueue(result.data.articles);
            updateCategoryFilter(result.data.articles);
        }
    } catch (error) {
        console.error('加载待分析文章失败:', error);
        queueElement.innerHTML = '<div class="error">加载失败，请重试</div>';
    }
}

function displayQueue(articles) {
    const queueElement = document.getElementById('analysis-queue');

    if (!articles || articles.length === 0) {
        queueElement.innerHTML = '<div class="empty-state">暂无待分析文章</div>';
        return;
    }

    const html = `
        <table class="analysis-table">
            <thead>
                <tr>
                    <th width="40"><input type="checkbox" id="select-all-checkbox" onchange="analysisPage.toggleSelectAll(this)"></th>
                    <th>标题</th>
                    <th>来源</th>
                    <th>分类</th>
                    <th>发布时间</th>
                    <th>状态</th>
                    <th>操作</th>
                </tr>
            </thead>
            <tbody>
                ${articles.map(article => `
                    <tr data-id="${article.id}">
                        <td><input type="checkbox" class="article-checkbox" value="${article.id}" onchange="analysisPage.toggleArticle(${article.id})"></td>
                        <td class="article-title">${escapeHtml(article.title)}</td>
                        <td>${getSourceBadge(article)}</td>
                        <td>${article.category || '未分类'}</td>
                        <td>${formatDate(article.published_at)}</td>
                        <td><span class="status-badge status-${article.analysis_status || 'pending'}">${getStatusText(article.analysis_status)}</span></td>
                        <td>
                            <button class="btn btn-sm" onclick="analysisPage.analyzeOne(${article.id})">分析</button>
                            <button class="btn btn-sm" onclick="analysisPage.viewArticle(${article.id})">查看</button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;

    queueElement.innerHTML = html;
}

function updateCategoryFilter(articles) {
    const select = document.getElementById('analysis-category-filter');
    const categories = new Set();

    articles.forEach(article => {
        if (article.category) categories.add(article.category);
    });

    select.innerHTML = '<option value="">全部分类</option>';
    Array.from(categories).sort().forEach(cat => {
        select.innerHTML += `<option value="${cat}">${cat}</option>`;
    });
}

function getSourceBadge(article) {
    const source = (article.source || '').toLowerCase();
    const badges = {
        'weibo': '<span class="source-badge weibo">微博</span>',
        'zhihu': '<span class="source-badge zhihu">知乎</span>',
        'toutiao': '<span class="source-badge toutiao">头条</span>',
        'baidu': '<span class="source-badge baidu">百度</span>'
    };
    return badges[source] || `<span class="source-badge">${article.source}</span>`;
}

function getStatusText(status) {
    const texts = {
        'pending': '待分析',
        'analyzing': '分析中',
        'completed': '已完成',
        'failed': '失败'
    };
    return texts[status] || '未知';
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function toggleSelectAll(checkbox) {
    const checkboxes = document.querySelectorAll('.article-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = checkbox.checked;
        const id = parseInt(cb.value);
        if (checkbox.checked) {
            selectedArticles.add(id);
        } else {
            selectedArticles.delete(id);
        }
    });
    updateSelectedCount();
}

function toggleArticle(id) {
    if (selectedArticles.has(id)) {
        selectedArticles.delete(id);
    } else {
        selectedArticles.add(id);
    }
    updateSelectedCount();
}

function updateSelectedCount() {
    const countElement = document.getElementById('selected-count');
    if (countElement) {
        countElement.textContent = selectedArticles.size;
    }
}

function selectAll() {
    const checkboxes = document.querySelectorAll('.article-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = true;
        selectedArticles.add(parseInt(cb.value));
    });
    document.getElementById('select-all-checkbox').checked = true;
    updateSelectedCount();
}

function deselectAll() {
    const checkboxes = document.querySelectorAll('.article-checkbox');
    checkboxes.forEach(cb => cb.checked = false);
    document.getElementById('select-all-checkbox').checked = false;
    selectedArticles.clear();
    updateSelectedCount();
}

async function startBatchAnalysis() {
    if (selectedArticles.size === 0) {
        alert('请先选择要分析的文章');
        return;
    }

    const progressDiv = document.getElementById('analysis-progress');
    progressDiv.style.display = 'block';

    try {
        const response = await fetch('/api/analyze/batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ article_ids: Array.from(selectedArticles) })
        });

        const result = await response.json();

        if (result.success) {
            currentJobId = result.data.job_id;
            connectSSE(currentJobId);
        } else {
            alert('启动分析失败: ' + result.error);
            progressDiv.style.display = 'none';
        }
    } catch (error) {
        console.error('批量分析失败:', error);
        alert('启动分析失败');
        progressDiv.style.display = 'none';
    }
}

function connectSSE(jobId) {
    if (sseSource) {
        sseSource.close();
    }

    sseSource = new EventSource(`/api/analyze/progress/${jobId}`);

    sseSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        updateProgress(data);

        if (data.status === 'completed' || data.status === 'failed') {
            sseSource.close();
            sseSource = null;
            setTimeout(() => {
                loadPendingArticles();
                selectedArticles.clear();
                updateSelectedCount();
            }, 2000);
        }
    };

    sseSource.onerror = function() {
        console.error('SSE连接错误');
        sseSource.close();
        sseSource = null;
    };
}

function updateProgress(data) {
    const progressText = document.getElementById('progress-text');
    const progressPercent = document.getElementById('progress-percent');
    const progressFill = document.getElementById('progress-fill');

    const percent = Math.round((data.processed / data.total) * 100);

    progressText.textContent = `已处理 ${data.processed}/${data.total} 篇`;
    progressPercent.textContent = `${percent}%`;
    progressFill.style.width = `${percent}%`;

    if (data.status === 'completed') {
        progressText.textContent = '分析完成！';
        progressFill.classList.add('completed');
    } else if (data.status === 'failed') {
        progressText.textContent = '分析失败';
        progressFill.classList.add('failed');
    }
}

async function analyzeOne(articleId) {
    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ article_id: articleId })
        });

        const result = await response.json();

        if (result.success) {
            alert('分析已启动');
            loadPendingArticles();
        } else {
            alert('分析失败: ' + result.error);
        }
    } catch (error) {
        console.error('分析失败:', error);
        alert('分析失败');
    }
}

async function viewArticle(articleId) {
    try {
        const response = await fetch(`/api/articles/${articleId}`);
        const result = await response.json();

        if (result.success) {
            showArticleModal(result.data);
        }
    } catch (error) {
        console.error('加载文章失败:', error);
    }
}

function showArticleModal(article) {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content">
            <span class="close" onclick="this.parentElement.parentElement.remove()">&times;</span>
            <h2>${escapeHtml(article.title)}</h2>
            <div class="article-meta">
                <span>来源: ${article.source}</span>
                <span>分类: ${article.category || '未分类'}</span>
                <span>发布时间: ${formatDate(article.published_at)}</span>
            </div>
            <div class="article-content">
                ${article.content || '无内容'}
            </div>
            ${article.ai_summary ? `
                <div class="article-analysis">
                    <h3>AI分析</h3>
                    <p>${article.ai_summary}</p>
                </div>
            ` : ''}
        </div>
    `;
    document.body.appendChild(modal);
}

function filterArticles() {
    const category = document.getElementById('analysis-category-filter').value;
    const status = document.getElementById('analysis-status-filter').value;

    loadPendingArticles();
}

window.analysisPage = {
    toggleSelectAll,
    toggleArticle,
    selectAll,
    deselectAll,
    startBatchAnalysis,
    analyzeOne,
    viewArticle,
    filterArticles
};
