// 发布管理页面模块
let drafts = [];
let publishedRecords = [];
let currentTab = 'pending';

function render() {
    return `
        <div class="publish-container">
            <div class="publish-header">
                <h2>发布管理</h2>
                <div class="publish-tabs">
                    <button class="tab-btn active" onclick="publishPage.switchTab('pending')">待发布</button>
                    <button class="tab-btn" onclick="publishPage.switchTab('published')">已发布</button>
                </div>
            </div>

            <div id="publish-content" class="publish-content">
                <div class="loading">加载中...</div>
            </div>
        </div>
    `;
}

function init() {
    loadPendingList();
}

function switchTab(tab) {
    currentTab = tab;

    document.querySelectorAll('.publish-tabs .tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    event.target.classList.add('active');

    if (tab === 'pending') {
        loadPendingList();
    } else {
        loadPublishedList();
    }
}

async function loadPendingList() {
    const contentElement = document.getElementById('publish-content');
    contentElement.innerHTML = '<div class="loading">加载中...</div>';

    try {
        const response = await fetch('/api/drafts');
        const result = await response.json();

        if (result.success) {
            drafts = result.data || [];
            displayPendingList();
        }
    } catch (error) {
        console.error('加载待发布列表失败:', error);
        contentElement.innerHTML = '<div class="error">加载失败</div>';
    }
}

function displayPendingList() {
    const contentElement = document.getElementById('publish-content');

    if (drafts.length === 0) {
        contentElement.innerHTML = '<div class="empty-state">暂无待发布文章</div>';
        return;
    }

    const html = `
        <div class="publish-list pending-list">
            ${drafts.map(draft => `
                <div class="publish-card">
                    <div class="publish-card-header">
                        <h3 class="publish-title">${escapeHtml(draft.title || '未命名')}</h3>
                        <span class="status-tag status-pending">待发布</span>
                    </div>
                    <div class="publish-summary">${escapeHtml(getSummary(draft.content || draft.summary))}</div>
                    <div class="publish-meta">
                        <span>更新时间：${formatDate(draft.updated_at)}</span>
                        <span>ID：${draft.id}</span>
                    </div>
                    <div class="publish-actions">
                        <button class="action-btn btn-preview" onclick="publishPage.previewArticle(${draft.id})">
                            预览
                        </button>
                        <button class="action-btn btn-draft" onclick="publishPage.publishToWechat(${draft.id}, 'draft')">
                            发布到草稿箱
                        </button>
                        <button class="action-btn btn-publish" onclick="publishPage.publishToWechat(${draft.id}, 'publish')">
                            直接发布
                        </button>
                    </div>
                </div>
            `).join('')}
        </div>
    `;

    contentElement.innerHTML = html;
}

async function loadPublishedList() {
    const contentElement = document.getElementById('publish-content');
    contentElement.innerHTML = '<div class="loading">加载中...</div>';

    try {
        const response = await fetch('/api/published');
        const result = await response.json();

        if (result.success) {
            publishedRecords = result.data || [];
            displayPublishedList();
        }
    } catch (error) {
        console.error('加载发布记录失败:', error);
        contentElement.innerHTML = '<div class="error">加载失败</div>';
    }
}

function displayPublishedList() {
    const contentElement = document.getElementById('publish-content');

    if (publishedRecords.length === 0) {
        contentElement.innerHTML = '<div class="empty-state">暂无发布记录</div>';
        return;
    }

    const html = `
        <div class="publish-list published-list">
            ${publishedRecords.map(record => `
                <div class="publish-card published-card">
                    <div class="publish-card-header">
                        <h3 class="publish-title">文章 #${record.article_id}</h3>
                        <span class="status-tag status-${record.status}">${getStatusLabel(record.status)}</span>
                    </div>
                    <div class="publish-meta-grid">
                        <div class="meta-item">
                            <label>发布时间</label>
                            <span>${formatDate(record.published_at || record.created_at)}</span>
                        </div>
                        <div class="meta-item">
                            <label>发布ID</label>
                            <span>${record.id}</span>
                        </div>
                        <div class="meta-item full-width">
                            <label>结果信息</label>
                            <span>${escapeHtml(record.result || '-')}</span>
                        </div>
                    </div>
                    <div class="publish-actions">
                        <button class="action-btn btn-detail" onclick="publishPage.viewPublishDetail(${record.id})">
                            查看详情
                        </button>
                    </div>
                </div>
            `).join('')}
        </div>
    `;

    contentElement.innerHTML = html;
}

async function publishToWechat(articleId, publishType) {
    const actionText = publishType === 'draft' ? '发布到草稿箱' : '直接发布';

    if (!confirm(`确定要${actionText}吗？`)) {
        return;
    }

    const buttons = document.querySelectorAll(`button[onclick*="${articleId}"]`);
    buttons.forEach(btn => btn.disabled = true);

    try {
        const response = await fetch('/api/publish', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                article_ids: [articleId],
                publish_type: publishType
            })
        });

        const result = await response.json();

        if (result.success) {
            showStatusMessage(`${actionText}成功`, 'success');
            setTimeout(() => {
                if (currentTab === 'pending') {
                    loadPendingList();
                }
            }, 1000);
        } else {
            showStatusMessage(`${actionText}失败: ${result.error}`, 'error');
        }
    } catch (error) {
        console.error('发布失败:', error);
        showStatusMessage(`${actionText}失败`, 'error');
    } finally {
        buttons.forEach(btn => btn.disabled = false);
    }
}

async function previewArticle(articleId) {
    try {
        const response = await fetch(`/api/drafts/${articleId}`);
        const result = await response.json();

        if (result.success) {
            showPreviewModal(result.data);
        }
    } catch (error) {
        console.error('加载文章失败:', error);
        alert('加载失败');
    }
}

function showPreviewModal(article) {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content preview-modal">
            <div class="modal-header">
                <h3>${escapeHtml(article.title)}</h3>
                <span class="close" onclick="this.closest('.modal').remove()">&times;</span>
            </div>
            <div class="modal-body preview-body">
                <div class="preview-article-content">${formatContent(article.content)}</div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

function viewPublishDetail(recordId) {
    const record = publishedRecords.find(r => r.id === recordId);
    if (!record) return;

    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3>发布详情</h3>
                <span class="close" onclick="this.closest('.modal').remove()">&times;</span>
            </div>
            <div class="modal-body">
                <div class="detail-row">
                    <label>文章ID</label>
                    <span>${record.article_id}</span>
                </div>
                <div class="detail-row">
                    <label>状态</label>
                    <span class="status-tag status-${record.status}">${getStatusLabel(record.status)}</span>
                </div>
                <div class="detail-row">
                    <label>发布时间</label>
                    <span>${formatDate(record.published_at || record.created_at)}</span>
                </div>
                <div class="detail-row">
                    <label>返回结果</label>
                    <pre>${escapeHtml(record.result || '-')}</pre>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

function getStatusLabel(status) {
    const labels = {
        success: '发布成功',
        failed: '发布失败',
        pending: '处理中',
        draft: '草稿箱'
    };
    return labels[status] || status;
}

function getSummary(content) {
    if (!content) return '暂无摘要';
    const text = content.replace(/[#*`\n]/g, ' ').trim();
    return text.length > 120 ? text.substring(0, 120) + '...' : text;
}

function formatContent(content) {
    if (!content) return '<p>暂无内容</p>';
    return escapeHtml(content).replace(/\n/g, '<br>');
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

function showStatusMessage(message, type) {
    const toast = document.createElement('div');
    toast.className = `status-toast status-toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

window.publishPage = {
    switchTab,
    previewArticle,
    publishToWechat,
    viewPublishDetail
};
