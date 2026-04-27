// 创作中心页面模块
(function() {
let currentDraft = null;
let drafts = [];
let collections = [];
let selectedDrafts = new Set();
let currentView = 'drafts';
let draggedItem = null;
let currentCollection = null;
let collectionArticles = [];

function render() {
    return `
        <div class="creation-container">
            <div class="creation-layout">
                <div class="creation-sidebar">
                    <div class="collection-tabs">
                        <div class="collection-tab ${currentView === 'drafts' ? 'active' : ''}"
                             data-view="drafts"
                             onclick="creationPage.switchView('drafts', this)">
                            草稿列表
                        </div>
                        <div class="collection-tab ${currentView === 'collections' ? 'active' : ''}"
                             data-view="collections"
                             onclick="creationPage.switchView('collections', this)">
                            合集管理
                        </div>
                    </div>

                    <div class="sidebar-header">
                        <h3 id="sidebar-title">草稿列表</h3>
                        <button class="btn btn-primary btn-sm" onclick="creationPage.handleNewAction()">
                            <span id="new-btn-text">新建</span>
                        </button>
                    </div>

                    <div id="batch-toolbar" class="batch-toolbar" style="display: none;">
                        <span class="selected-count">已选择 <strong id="selected-count">0</strong> 篇</span>
                        <div class="batch-actions">
                            <button class="btn btn-sm btn-primary" onclick="creationPage.createCollectionFromSelection()">
                                创建合集
                            </button>
                            <button class="btn btn-sm" onclick="creationPage.clearSelection()">
                                取消选择
                            </button>
                        </div>
                    </div>

                    <div id="content-list" class="drafts-list">
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
                            <div id="wechat-toolbar"></div>
                            <div id="wechat-editor" style="height: 500px; overflow-y: auto;"></div>
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

        <!-- 合集创建/编辑模态框 -->
        <div id="collection-modal" class="modal" style="display: none;">
            <div class="modal-content">
                <div class="modal-header">
                    <h3 id="collection-modal-title">创建合集</h3>
                    <span class="close" onclick="creationPage.closeCollectionModal()">&times;</span>
                </div>
                <div class="modal-body">
                    <form class="collection-form" id="collection-form" onsubmit="return false;">
                        <div class="form-group">
                            <label>合集标题 *</label>
                            <input type="text" id="collection-title" placeholder="请输入合集标题" required>
                        </div>
                        <div class="form-group">
                            <label>合集描述</label>
                            <textarea id="collection-desc" placeholder="请输入合集描述（可选）"></textarea>
                        </div>
                        <div class="form-group">
                            <label>封面图片URL</label>
                            <input type="text" id="collection-cover" placeholder="请输入封面图片URL（可选）">
                        </div>
                        <div class="form-group">
                            <label>合集文章（拖拽调整顺序，2-8篇）*</label>
                            <div id="collection-articles-list" class="collection-articles">
                                <div class="empty-state">暂未选择文章</div>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px;">
                                <span class="form-hint" id="article-count-hint">已选择 0 篇（需2-8篇）</span>
                                <button type="button" class="btn btn-sm" onclick="creationPage.openArticleSelector()">添加文章</button>
                            </div>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button class="btn" onclick="creationPage.closeCollectionModal()">取消</button>
                    <button class="btn btn-primary" onclick="creationPage.saveCollection()">保存</button>
                </div>
            </div>
        </div>

        <!-- 文章选择弹窗 -->
        <div id="article-selector-modal" class="modal" style="display: none;">
            <div class="modal-content">
                <div class="modal-header">
                    <h3>选择文章</h3>
                    <span class="close" onclick="creationPage.closeArticleSelector()">&times;</span>
                </div>
                <div class="modal-body">
                    <div id="draft-selector-list" class="draft-select-list">
                        <div class="loading">加载中...</div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn" onclick="creationPage.closeArticleSelector()">取消</button>
                    <button class="btn btn-primary" onclick="creationPage.confirmArticleSelection()">确认</button>
                </div>
            </div>
        </div>
    `;
}

function init() {
    loadDrafts();
    loadCollections();

    // 初始化wangEditor
    if (window.wechatEditor) {
        window.wechatEditor.init('#wechat-editor', '#wechat-toolbar');

        // 监听内容变化
        window.wechatEditor.onChange = function(content) {
            if (currentDraft) {
                currentDraft.content_wechat = content;
            }
        };
    }

    setupAutoSave();
}

function switchView(view, el) {
    currentView = view;
    selectedDrafts.clear();

    const sidebarTitle = document.getElementById('sidebar-title');
    const newBtnText = document.getElementById('new-btn-text');
    const batchToolbar = document.getElementById('batch-toolbar');

    if (view === 'drafts') {
        sidebarTitle.textContent = '草稿列表';
        newBtnText.textContent = '新建';
        displayDrafts();
    } else {
        sidebarTitle.textContent = '合集管理';
        newBtnText.textContent = '新建合集';
        batchToolbar.style.display = 'none';
        displayCollections();
    }

    if (el) {
        document.querySelectorAll('.collection-tab').forEach(tab => tab.classList.remove('active'));
        el.classList.add('active');
    }
}

function handleNewAction() {
    if (currentView === 'drafts') {
        newDraft();
    } else {
        openCollectionModal();
    }
}

async function loadCollections() {
    try {
        const response = await fetch('/api/collections');
        const result = await response.json();

        if (result.success) {
            collections = result.data || [];
            if (currentView === 'collections') {
                displayCollections();
            }
        }
    } catch (error) {
        console.error('加载合集失败:', error);
    }
}

function displayCollections() {
    const listElement = document.getElementById('content-list');
    listElement.className = 'collections-list';

    if (collections.length === 0) {
        listElement.innerHTML = '<div class="empty-state">暂无合集</div>';
        return;
    }

    const html = collections.map(collection => `
        <div class="collection-item">
            <div class="collection-title">${escapeHtml(collection.title)}</div>
            <div class="collection-desc">${escapeHtml(collection.description || '暂无描述')}</div>
            <div class="collection-meta">
                <span>${collection.article_count || 0} 篇文章</span>
                <span class="collection-status ${collection.status || 'draft'}">
                    ${collection.status === 'published' ? '已发布' : '草稿'}
                </span>
            </div>
            <div class="collection-actions">
                <button class="btn btn-sm" onclick="creationPage.editCollection(${collection.id})">编辑</button>
                <button class="btn btn-sm btn-success" onclick="creationPage.publishCollection(${collection.id})">
                    ${collection.status === 'published' ? '取消发布' : '发布'}
                </button>
                <button class="btn btn-sm btn-danger" onclick="creationPage.deleteCollection(${collection.id})">删除</button>
            </div>
        </div>
    `).join('');

    listElement.innerHTML = html;
}

async function loadDrafts() {
    const listElement = document.getElementById('content-list');
    listElement.className = 'drafts-list';
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
    const listElement = document.getElementById('content-list');
    listElement.className = 'drafts-list';

    if (drafts.length === 0) {
        listElement.innerHTML = '<div class="empty-state">暂无草稿</div>';
        updateBatchToolbar();
        return;
    }

    const html = drafts.map(draft => {
        const isSelected = selectedDrafts.has(draft.id);
        const source = draft.source_type || 'manual';
        return `
        <div class="draft-item ${currentDraft && currentDraft.id === draft.id ? 'active' : ''} ${isSelected ? 'selected' : ''}"
             onclick="creationPage.loadDraft(${draft.id})">
            <input type="checkbox" class="draft-checkbox"
                   ${isSelected ? 'checked' : ''}
                   onclick="event.stopPropagation(); creationPage.toggleDraftSelection(${draft.id})">
            <div class="draft-content">
                <div class="draft-title">${escapeHtml(draft.title || '未命名')}</div>
                <div class="draft-meta">
                    <span class="draft-source-tag ${source}">${source === 'agent' ? 'Agent' : '手动'}</span>
                    <span class="draft-date">${formatDate(draft.updated_at)}</span>
                    <button class="btn-icon" onclick="event.stopPropagation(); creationPage.deleteDraft(${draft.id})">
                        <span>×</span>
                    </button>
                </div>
            </div>
        </div>
    `;}).join('');

    listElement.innerHTML = html;
    updateBatchToolbar();
}

function toggleDraftSelection(draftId) {
    if (selectedDrafts.has(draftId)) {
        selectedDrafts.delete(draftId);
    } else {
        selectedDrafts.add(draftId);
    }
    displayDrafts();
}

function clearSelection() {
    selectedDrafts.clear();
    displayDrafts();
}

function updateBatchToolbar() {
    const toolbar = document.getElementById('batch-toolbar');
    const countElement = document.getElementById('selected-count');
    if (!toolbar) return;

    if (selectedDrafts.size > 0 && currentView === 'drafts') {
        toolbar.style.display = 'flex';
        countElement.textContent = selectedDrafts.size;
    } else {
        toolbar.style.display = 'none';
    }
}

function createCollectionFromSelection() {
    if (selectedDrafts.size < 2) {
        alert('请至少选择2篇文章');
        return;
    }
    if (selectedDrafts.size > 8) {
        alert('合集最多包含8篇文章');
        return;
    }

    const selectedIds = Array.from(selectedDrafts);
    collectionArticles = drafts.filter(d => selectedIds.includes(d.id));
    openCollectionModal();
}

// 合集弹窗管理
function openCollectionModal(collection) {
    currentCollection = collection || null;
    const modal = document.getElementById('collection-modal');
    const title = document.getElementById('collection-modal-title');

    if (collection) {
        title.textContent = '编辑合集';
        document.getElementById('collection-title').value = collection.title || '';
        document.getElementById('collection-desc').value = collection.description || '';
        document.getElementById('collection-cover').value = collection.cover_image || '';
        collectionArticles = (collection.articles || []).slice();
    } else {
        title.textContent = '创建合集';
        document.getElementById('collection-title').value = '';
        document.getElementById('collection-desc').value = '';
        document.getElementById('collection-cover').value = '';
    }

    renderCollectionArticles();
    modal.style.display = 'flex';
}

function closeCollectionModal() {
    document.getElementById('collection-modal').style.display = 'none';
    currentCollection = null;
    collectionArticles = [];
}

function renderCollectionArticles() {
    const container = document.getElementById('collection-articles-list');
    const hint = document.getElementById('article-count-hint');
    const count = collectionArticles.length;

    hint.textContent = `已选择 ${count} 篇（需2-8篇）`;
    hint.className = 'form-hint' + ((count < 2 || count > 8) ? ' error' : '');

    if (count === 0) {
        container.innerHTML = '<div class="empty-state">暂未选择文章</div>';
        return;
    }

    const html = collectionArticles.map((article, index) => {
        const utf8Bytes = encodeURIComponent(article.title || '').replace(/%[A-F\d]{2}/g, 'x').length;
        const isOver = utf8Bytes > 64;
        return `
        <div class="collection-article-item"
             draggable="true"
             data-index="${index}"
             ondragstart="creationPage.handleDragStart(event, ${index})"
             ondragover="creationPage.handleDragOver(event)"
             ondragleave="creationPage.handleDragLeave(event)"
             ondrop="creationPage.handleDrop(event, ${index})"
             ondragend="creationPage.handleDragEnd(event)">
            <span class="drag-handle">⋮⋮</span>
            <span class="article-order">${index + 1}</span>
            <div class="article-title-edit-wrap">
                <input type="text"
                       class="article-title-edit ${isOver ? 'title-too-long' : ''}"
                       value="${escapeHtml(article.title || '未命名')}"
                       maxlength="21"
                       placeholder="标题（最多21个汉字）"
                       oninput="creationPage.onArticleTitleChange(${index}, this)"
                       onclick="event.stopPropagation()">
                <span class="title-byte-hint ${isOver ? 'over' : ''}" id="title-hint-${index}">UTF-8 ${utf8Bytes}/64字节</span>
            </div>
            <button class="article-remove" onclick="creationPage.removeArticleFromCollection(${index})">×</button>
        </div>
    `}).join('');

    container.innerHTML = html;
}

// 拖拽排序
function handleDragStart(e, index) {
    draggedItem = index;
    e.currentTarget.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
}

function onArticleTitleChange(index, input) {
    const newTitle = input.value.trim();
    if (collectionArticles[index]) {
        collectionArticles[index].title = newTitle;
    }
    // 实时更新字节数提示
    const utf8Bytes = new Blob([newTitle]).size;
    const hint = document.getElementById(`title-hint-${index}`);
    if (hint) {
        hint.textContent = `UTF-8 ${utf8Bytes}/64字节`;
        hint.classList.toggle('over', utf8Bytes > 64);
        input.classList.toggle('title-too-long', utf8Bytes > 64);
    }
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    e.currentTarget.classList.add('drag-over');
    return false;
}

function handleDragLeave(e) {
    e.currentTarget.classList.remove('drag-over');
}

function handleDrop(e, targetIndex) {
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.classList.remove('drag-over');

    if (draggedItem === null || draggedItem === targetIndex) {
        return false;
    }

    const item = collectionArticles.splice(draggedItem, 1)[0];
    collectionArticles.splice(targetIndex, 0, item);
    renderCollectionArticles();
    return false;
}

function handleDragEnd(e) {
    document.querySelectorAll('.collection-article-item').forEach(item => {
        item.classList.remove('dragging', 'drag-over');
    });
    draggedItem = null;
}

function removeArticleFromCollection(index) {
    collectionArticles.splice(index, 1);
    renderCollectionArticles();
}

// 文章选择器
let tempSelectedArticles = new Set();

function openArticleSelector() {
    tempSelectedArticles = new Set(collectionArticles.map(a => a.id));
    document.getElementById('article-selector-modal').style.display = 'flex';
    renderDraftSelector();
}

function closeArticleSelector() {
    document.getElementById('article-selector-modal').style.display = 'none';
}

function renderDraftSelector() {
    const container = document.getElementById('draft-selector-list');

    if (drafts.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无草稿</div>';
        return;
    }

    const html = drafts.map(draft => {
        const isSelected = tempSelectedArticles.has(draft.id);
        const source = draft.source || 'manual';
        return `
            <div class="draft-select-item ${isSelected ? 'selected' : ''}"
                 onclick="creationPage.toggleTempSelection(${draft.id})">
                <input type="checkbox" ${isSelected ? 'checked' : ''} onclick="event.stopPropagation()">
                <div style="flex: 1; min-width: 0;">
                    <div class="draft-title">${escapeHtml(draft.title || '未命名')}</div>
                    <div class="draft-meta">
                        <span class="draft-source-tag ${source}">${source === 'agent' ? 'Agent' : '手动'}</span>
                        <span>${formatDate(draft.updated_at)}</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = html;
}

function toggleTempSelection(draftId) {
    if (tempSelectedArticles.has(draftId)) {
        tempSelectedArticles.delete(draftId);
    } else {
        if (tempSelectedArticles.size >= 8) {
            alert('合集最多包含8篇文章');
            return;
        }
        tempSelectedArticles.add(draftId);
    }
    renderDraftSelector();
}

function confirmArticleSelection() {
    const selectedIds = Array.from(tempSelectedArticles);
    const existing = collectionArticles.filter(a => selectedIds.includes(a.id));
    const existingIds = new Set(existing.map(a => a.id));
    const newArticles = drafts.filter(d => selectedIds.includes(d.id) && !existingIds.has(d.id));

    collectionArticles = [...existing, ...newArticles];
    closeArticleSelector();
    renderCollectionArticles();
}

async function saveCollection() {
    const title = document.getElementById('collection-title').value.trim();
    const description = document.getElementById('collection-desc').value.trim();
    const cover_image = document.getElementById('collection-cover').value.trim();

    if (!title) {
        alert('请输入合集标题');
        return;
    }

    if (collectionArticles.length < 2 || collectionArticles.length > 8) {
        alert('合集必须包含2-8篇文章');
        return;
    }

    const articleIds = collectionArticles.map(a => a.id);
    const payload = { title, description, cover_image, article_ids: articleIds };

    try {
        const url = currentCollection
            ? `/api/collections/${currentCollection.id}`
            : '/api/collections';
        const method = currentCollection ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (result.success) {
            showToast(currentCollection ? '更新成功' : '创建成功', 'success');
            closeCollectionModal();
            selectedDrafts.clear();
            await loadCollections();
            if (currentView === 'drafts') {
                displayDrafts();
            }
        } else {
            alert('保存失败: ' + (result.error || '未知错误'));
        }
    } catch (error) {
        console.error('保存合集失败:', error);
        alert('保存失败');
    }
}

async function editCollection(collectionId) {
    try {
        const response = await fetch(`/api/collections/${collectionId}`);
        const result = await response.json();

        if (result.success) {
            const collection = result.data;

            // 切换到编辑器视图
            currentCollection = collection;
            currentView = 'collection-editor';

            // 隐藏侧边栏列表，显示编辑器
            document.querySelector('.creation-sidebar').style.display = 'none';
            document.querySelector('.creation-main').style.width = '100%';

            // 渲染合集编辑器界面
            renderCollectionEditorView(collection);
        } else {
            alert('加载合集失败');
        }
    } catch (error) {
        console.error('加载合集失败:', error);
        alert('加载合集失败');
    }
}

function renderCollectionEditorView(collection) {
    const mainArea = document.querySelector('.creation-main');

    mainArea.innerHTML = `
        <div class="collection-editor-header">
            <button class="btn" onclick="creationPage.exitCollectionEditor()">
                ← 返回合集列表
            </button>
            <h2>编辑合集：${escapeHtml(collection.title)}</h2>
            <div class="header-actions">
                <button class="btn btn-success" onclick="creationPage.saveCollectionContent()">保存</button>
                <button class="btn btn-primary" onclick="creationPage.publishCollection(${collection.id})">发布到微信</button>
            </div>
        </div>

        <div class="collection-editor-body">
            <!-- 左侧：文章列表 -->
            <div class="collection-articles-panel">
                <h3>合集文章 (${collection.articles?.length || 0}篇)</h3>
                <div id="collection-editor-articles" class="collection-editor-articles-list">
                    ${renderCollectionArticlesList(collection.articles || [])}
                </div>
                <button class="btn btn-sm" onclick="creationPage.openArticleSelector()">+ 添加文章</button>
            </div>

            <!-- 右侧：富文本编辑器 -->
            <div class="collection-content-panel">
                <div class="collection-meta-editor">
                    <div class="form-group">
                        <label>合集标题</label>
                        <input type="text" id="collection-editor-title" class="form-control"
                               value="${escapeHtml(collection.title)}" placeholder="请输入合集标题">
                    </div>

                    <div class="form-group">
                        <label>合集描述</label>
                        <textarea id="collection-editor-desc" class="form-control" rows="2"
                                  placeholder="请输入合集描述">${escapeHtml(collection.description || '')}</textarea>
                    </div>

                    <div class="form-group">
                        <label>封面图片</label>
                        <div class="cover-upload-area">
                            <input type="file" id="collection-cover-upload" accept="image/*"
                                   style="display:none" onchange="creationPage.handleCoverUpload(event)">
                            <div class="cover-preview" id="collection-cover-preview">
                                ${collection.cover_image ?
                                    `<img src="${collection.cover_image}" alt="封面">` :
                                    '<div class="cover-placeholder">点击上传封面图片</div>'}
                            </div>
                            <button class="btn btn-sm" onclick="document.getElementById('collection-cover-upload').click()">
                                上传封面
                            </button>
                        </div>
                    </div>
                </div>

                <div class="collection-content-editor">
                    <div class="editor-toolbar-wrapper">
                        <div id="collection-wechat-toolbar"></div>
                        <button class="btn btn-sm btn-ai" onclick="creationPage.openAIAssistant()">
                            ✨ AI辅助写作
                        </button>
                    </div>
                    <div id="collection-wechat-editor" style="height: 600px; overflow-y: auto;"></div>
                </div>
            </div>
        </div>
    `;

    // 初始化富文本编辑器
    setTimeout(() => {
        if (window.wechatEditor) {
            window.wechatEditor.destroy?.();
            window.wechatEditor.init('#collection-wechat-editor', '#collection-wechat-toolbar');

            // 加载合集内容
            if (collection.content) {
                window.wechatEditor.setHtml(collection.content);
            }
        }
    }, 100);
}

function renderCollectionArticlesList(articles) {
    if (!articles || articles.length === 0) {
        return '<div class="empty-state">暂无文章</div>';
    }

    return articles.map((article, index) => `
        <div class="collection-article-card" data-id="${article.id}">
            <div class="article-order-badge">${index + 1}</div>
            <div class="article-info">
                <div class="article-title-small">${escapeHtml(article.title || '未命名')}</div>
                <div class="article-meta-small">${article.created_at || ''}</div>
            </div>
            <div class="article-actions-small">
                <button class="btn-icon" onclick="creationPage.previewArticle(${article.id})" title="预览">
                    👁
                </button>
                <button class="btn-icon" onclick="creationPage.removeArticleFromCollectionEditor(${index})" title="移除">
                    ×
                </button>
            </div>
        </div>
    `).join('');
}

function exitCollectionEditor() {
    // 恢复侧边栏和主区域布局
    document.querySelector('.creation-sidebar').style.display = '';
    document.querySelector('.creation-main').style.width = '';

    // 切换回合集列表视图
    currentView = 'collections';
    currentCollection = null;

    // 重新渲染原始界面
    render();
    init();
    switchView('collections');
}

async function saveCollectionContent() {
    if (!currentCollection) return;

    const title = document.getElementById('collection-editor-title')?.value.trim();
    const description = document.getElementById('collection-editor-desc')?.value.trim();
    const content = window.wechatEditor?.getHtml() || '';

    if (!title) {
        alert('请输入合集标题');
        return;
    }

    try {
        const response = await fetch(`/api/collections/${currentCollection.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title,
                description,
                content,
                cover_image: currentCollection.cover_image || '',
                articles: collectionArticles.map(a => a.id)
            })
        });

        const result = await response.json();
        if (result.success) {
            showToast('保存成功', 'success');
            currentCollection = result.data;
        } else {
            alert('保存失败: ' + (result.error || '未知错误'));
        }
    } catch (error) {
        console.error('保存失败:', error);
        alert('保存失败');
    }
}

async function handleCoverUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
        alert('请选择图片文件');
        return;
    }

    const formData = new FormData();
    formData.append('image', file);

    try {
        const response = await fetch('/api/upload/wechat-image', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();
        if (result.success && result.url) {
            currentCollection.cover_image = result.url;
            document.getElementById('collection-cover-preview').innerHTML =
                `<img src="${result.url}" alt="封面">`;
            showToast('封面上传成功', 'success');
        } else {
            alert('上传失败: ' + (result.error || '未知错误'));
        }
    } catch (error) {
        console.error('上传失败:', error);
        alert('上传失败');
    }
}

function openAIAssistant() {
    // TODO: 实现AI辅助写作功能
    alert('AI辅助写作功能开发中...');
}

async function deleteCollection(collectionId) {
    if (!confirm('确定要删除这个合集吗？')) return;

    try {
        const response = await fetch(`/api/collections/${collectionId}`, { method: 'DELETE' });
        const result = await response.json();

        if (result.success) {
            showToast('删除成功', 'success');
            await loadCollections();
        } else {
            alert('删除失败: ' + (result.error || '未知错误'));
        }
    } catch (error) {
        console.error('删除合集失败:', error);
        alert('删除失败');
    }
}

async function publishCollection(collectionId) {
    const collection = collections.find(c => c.id === collectionId);
    const willPublish = collection && collection.status !== 'published';
    const confirmMsg = willPublish ? '确定要发布这个合集吗？' : '确定要取消发布吗？';

    if (!confirm(confirmMsg)) return;

    try {
        const response = await fetch(`/api/collections/${collectionId}/publish`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ publish_now: willPublish })
        });

        const result = await response.json();

        if (result.success) {
            showToast(willPublish ? '发布成功' : '已取消发布', 'success');
            await loadCollections();
        } else {
            alert('操作失败: ' + (result.error || '未知错误'));
        }
    } catch (error) {
        console.error('发布合集失败:', error);
        alert('操作失败');
    }
}

// 原有草稿编辑逻辑
function newDraft() {
    currentDraft = {
        id: null,
        title: '',
        content: '',
        content_wechat: ''
    };
    document.getElementById('article-title').value = '';
    if (window.wechatEditor) {
        window.wechatEditor.clear();
    }
    if (currentView === 'drafts') {
        displayDrafts();
    }
}

async function loadDraft(draftId) {
    try {
        const response = await fetch(`/api/drafts/${draftId}`);
        const result = await response.json();

        if (result.success) {
            currentDraft = result.data;
            document.getElementById('article-title').value = currentDraft.title || '';
            if (window.wechatEditor) {
                window.wechatEditor.setHtml(currentDraft.content_wechat || currentDraft.content || '');
            }
            displayDrafts();
        }
    } catch (error) {
        console.error('加载草稿失败:', error);
        alert('加载草稿失败');
    }
}

async function saveDraft() {
    const title = document.getElementById('article-title').value.trim();
    const content_wechat = window.wechatEditor ? window.wechatEditor.getHtml() : '';
    const content = window.wechatEditor ? window.wechatEditor.getText() : '';

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
            body: JSON.stringify({ title, content, content_wechat })
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
            selectedDrafts.delete(draftId);
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

            const content = result.data.content || '';
            if (window.wechatEditor) {
                if (window.wechatEditor.isMarkdown(content)) {
                    const html = window.wechatEditor.convertMarkdownToHtml(content);
                    window.wechatEditor.setHtml(html);
                } else {
                    window.wechatEditor.setHtml(content);
                }
            }

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

        const title = document.getElementById('article-title').value;
        const content = window.wechatEditor ? window.wechatEditor.getHtml() : '';

        document.getElementById('preview-title').textContent = title || '标题预览';
        document.getElementById('preview-content').innerHTML = `<div class="wechat-article">${content}</div>`;
    } else {
        editorPanel.style.display = 'block';
        previewPanel.style.display = 'none';
        toggleText.textContent = '预览';
    }
}

function setupAutoSave() {
    let autoSaveTimer;

    const triggerAutoSave = () => {
        clearTimeout(autoSaveTimer);
        autoSaveTimer = setTimeout(() => {
            if (currentDraft && currentDraft.id) {
                saveDraft();
            }
        }, 3000);
    };

    const titleEl = document.getElementById('article-title');
    if (titleEl) {
        titleEl.addEventListener('input', triggerAutoSave);
    }

    // 监听wangEditor变化
    if (window.wechatEditor) {
        const originalOnChange = window.wechatEditor.onChange;
        window.wechatEditor.onChange = function(content) {
            if (currentDraft) {
                currentDraft.content_wechat = content;
            }
            if (originalOnChange) originalOnChange(content);
            triggerAutoSave();
        };
    }
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
    switchView,
    handleNewAction,
    newDraft,
    loadDraft,
    saveDraft,
    deleteDraft,
    toggleDraftSelection,
    clearSelection,
    createCollectionFromSelection,
    openCollectionModal,
    closeCollectionModal,
    editCollection,
    deleteCollection,
    publishCollection,
    saveCollection,
    openArticleSelector,
    closeArticleSelector,
    toggleTempSelection,
    confirmArticleSelection,
    removeArticleFromCollection,
    handleDragStart,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    handleDragEnd,
    onArticleTitleChange,
    generateFromHotspot,
    selectHotspot,
    closeHotspotModal,
    togglePreview
};

})();
