// 创作中心页面模块
(function() {
let currentDraft = null;
let drafts = [];

function render() {
    return `
        <div class="creation-container">
            <div class="creation-layout">
                <div class="creation-sidebar">
                    <div class="sidebar-header">
                        <h3>草稿列表</h3>
                        <button class="btn btn-primary btn-sm" onclick="creationPage.newDraft()">新建</button>
                    </div>
                    <div id="drafts-list" class="drafts-list">
                        <div class="loading">加载中...</div>
                    </div>
                </div>

                <div class="creation-main">
                    <div class="creation-toolbar">
                        <button class="btn btn-primary" onclick="creationPage.generateFromHotspot()">
                            基于热点生成
                        </button>
                        <button class="btn btn-success" onclick="creationPage.saveDraft()">保存草稿</button>
                        <button class="btn" onclick="creationPage.togglePreview()">
                            <span id="preview-toggle-text">预览</span>
                        </button>
                    </div>

                    <div class="creation-editor">
                        <div class="editor-panel" id="editor-panel">
                            <input type="text" id="article-title" class="article-title-input" placeholder="请输入标题...">
                            <textarea id="article-content" class="article-content-input" placeholder="请输入内容（支持Markdown）..."></textarea>
                        </div>

                        <div class="preview-panel" id="preview-panel" style="display: none;">
                            <h2 id="preview-title" class="preview-title">标题预览</h2>
                            <div id="preview-content" class="preview-content"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 热点选择模态框 -->
        <div id="hotspot-modal" class="modal" style="display: none;">
            <div class="modal-content">
                <div class="modal-header">
                    <h3>选择热点话题</h3>
                    <span class="close" onclick="creationPage.closeHotspotModal()">&times;</span>
                </div>
                <div class="modal-body">
                    <div id="hotspots-list" class="hotspots-list">
                        <div class="loading">加载中...</div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function init() {
    loadDrafts();
    setupAutoSave();
}

async function loadDrafts() {
    const listElement = document.getElementById('drafts-list');
    listElement.innerHTML = '<div class="loading">加载中...</div>';

    try {
        const response = await fetch('/api/drafts');
        const result = await response.json();

        if (result.success) {
            drafts = result.data || [];
            displayDrafts();
        }
    } catch (error) {
        console.error('加载草稿失败:', error);
        listElement.innerHTML = '<div class="error">加载失败</div>';
    }
}

function displayDrafts() {
    const listElement = document.getElementById('drafts-list');

    if (drafts.length === 0) {
        listElement.innerHTML = '<div class="empty-state">暂无草稿</div>';
        return;
    }

    const html = drafts.map(draft => `
        <div class="draft-item ${currentDraft && currentDraft.id === draft.id ? 'active' : ''}"
             onclick="creationPage.loadDraft(${draft.id})">
            <div class="draft-title">${escapeHtml(draft.title || '未命名')}</div>
            <div class="draft-meta">
                <span class="draft-date">${formatDate(draft.updated_at)}</span>
                <button class="btn-icon" onclick="event.stopPropagation(); creationPage.deleteDraft(${draft.id})">
                    <span>×</span>
                </button>
            </div>
        </div>
    `).join('');

    listElement.innerHTML = html;
}

function newDraft() {
    currentDraft = {
        id: null,
        title: '',
        content: ''
    };
    document.getElementById('article-title').value = '';
    document.getElementById('article-content').value = '';
    displayDrafts();
}

async function loadDraft(draftId) {
    try {
        const response = await fetch(`/api/drafts/${draftId}`);
        const result = await response.json();

        if (result.success) {
            currentDraft = result.data;
            document.getElementById('article-title').value = currentDraft.title || '';
            document.getElementById('article-content').value = currentDraft.content || '';
            displayDrafts();
            updatePreview();
        }
    } catch (error) {
        console.error('加载草稿失败:', error);
        alert('加载草稿失败');
    }
}

async function saveDraft() {
    const title = document.getElementById('article-title').value.trim();
    const content = document.getElementById('article-content').value.trim();

    if (!title && !content) {
        alert('请输入标题或内容');
        return;
    }

    try {
        const url = currentDraft && currentDraft.id
            ? `/api/drafts/${currentDraft.id}`
            : '/api/drafts';

        const method = currentDraft && currentDraft.id ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, content })
        });

        const result = await response.json();

        if (result.success) {
            currentDraft = result.data;
            await loadDrafts();
            showToast('保存成功', 'success');
        } else {
            alert('保存失败: ' + result.error);
        }
    } catch (error) {
        console.error('保存草稿失败:', error);
        alert('保存失败');
    }
}

async function deleteDraft(draftId) {
    if (!confirm('确定要删除这个草稿吗？')) return;

    try {
        const response = await fetch(`/api/drafts/${draftId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            if (currentDraft && currentDraft.id === draftId) {
                newDraft();
            }
            await loadDrafts();
            showToast('删除成功', 'success');
        } else {
            alert('删除失败: ' + result.error);
        }
    } catch (error) {
        console.error('删除草稿失败:', error);
        alert('删除失败');
    }
}

function generateFromHotspot() {
    document.getElementById('hotspot-modal').style.display = 'flex';
    loadHotspots();
}

async function loadHotspots() {
    const listElement = document.getElementById('hotspots-list');
    listElement.innerHTML = '<div class="loading">加载中...</div>';

    try {
        const response = await fetch('/api/trending');
        const result = await response.json();

        if (result.success && result.data.trending) {
            // 将trending对象转换为数组
            const hotspotsArray = [];
            Object.keys(result.data.trending).forEach(platform => {
                const items = result.data.trending[platform];
                if (Array.isArray(items)) {
                    items.forEach(item => {
                        hotspotsArray.push({
                            ...item,
                            platform: platform
                        });
                    });
                }
            });
            displayHotspots(hotspotsArray.slice(0, 20));
        }
    } catch (error) {
        console.error('加载热点失败:', error);
        listElement.innerHTML = '<div class="error">加载失败</div>';
    }
}

function displayHotspots(hotspots) {
    const listElement = document.getElementById('hotspots-list');

    if (!hotspots || hotspots.length === 0) {
        listElement.innerHTML = '<div class="empty-state">暂无热点</div>';
        return;
    }

    const html = hotspots.map((item, index) => `
        <div class="hotspot-item" onclick="creationPage.selectHotspot(${item.id})">
            <div class="hotspot-rank">${index + 1}</div>
            <div class="hotspot-info">
                <div class="hotspot-title">${escapeHtml(item.title)}</div>
                <div class="hotspot-meta">
                    <span class="hotspot-source">${item.source}</span>
                    <span class="hotspot-heat">${formatHeat(item.heat)}</span>
                </div>
            </div>
        </div>
    `).join('');

    listElement.innerHTML = html;
}

async function selectHotspot(hotspotId) {
    closeHotspotModal();

    const btn = event.target.closest('button') || document.querySelector('.creation-toolbar .btn-primary');
    if (btn) {
        btn.disabled = true;
        btn.textContent = '生成中...';
    }

    try {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ hotnews_ids: [hotspotId], count: 1 })
        });

        const result = await response.json();

        if (result.success) {
            document.getElementById('article-title').value = result.data.title || '';
            document.getElementById('article-content').value = result.data.content || '';
            updatePreview();
            showToast('生成成功', 'success');
        } else {
            alert('生成失败: ' + result.error);
        }
    } catch (error) {
        console.error('生成文章失败:', error);
        alert('生成失败');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = '基于热点生成';
        }
    }
}

function closeHotspotModal() {
    document.getElementById('hotspot-modal').style.display = 'none';
}

function togglePreview() {
    const editorPanel = document.getElementById('editor-panel');
    const previewPanel = document.getElementById('preview-panel');
    const toggleText = document.getElementById('preview-toggle-text');

    if (previewPanel.style.display === 'none') {
        editorPanel.style.display = 'none';
        previewPanel.style.display = 'block';
        toggleText.textContent = '编辑';
        updatePreview();
    } else {
        editorPanel.style.display = 'block';
        previewPanel.style.display = 'none';
        toggleText.textContent = '预览';
    }
}

function updatePreview() {
    const title = document.getElementById('article-title').value;
    const content = document.getElementById('article-content').value;

    document.getElementById('preview-title').textContent = title || '标题预览';
    document.getElementById('preview-content').innerHTML = renderMarkdown(content);
}

function renderMarkdown(text) {
    if (!text) return '<p class="empty-preview">内容预览</p>';

    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>')
        .replace(/^(.+)$/gim, '<p>$1</p>');
}

function setupAutoSave() {
    let autoSaveTimer;
    const inputs = ['article-title', 'article-content'];

    inputs.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('input', () => {
                clearTimeout(autoSaveTimer);
                autoSaveTimer = setTimeout(() => {
                    if (currentDraft && currentDraft.id) {
                        saveDraft();
                    }
                }, 3000);
            });
        }
    });
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now - date;

    if (diff < 60000) return '刚刚';
    if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前';
    if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前';

    return date.toLocaleDateString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatHeat(heat) {
    if (!heat) return '-';
    if (heat >= 10000) return (heat / 10000).toFixed(1) + 'w';
    return heat.toString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('show');
    }, 10);

    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 2000);
}

window.creationPage = {
    render,
    init,
    newDraft,
    loadDraft,
    saveDraft,
    deleteDraft,
    generateFromHotspot,
    selectHotspot,
    closeHotspotModal,
    togglePreview
};

})();
