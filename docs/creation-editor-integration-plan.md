# 创作中心编辑器集成方案

## 目标

将wangEditor富文本编辑器集成到创作中心（creation.js），替换现有的textarea编辑器。

## 当前状态

### 现有编辑器结构（creation.js）

```javascript
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
```

### 需要修改的功能点

1. **init()** - 初始化时创建wangEditor实例
2. **loadDraft()** - 加载草稿时设置编辑器内容
3. **saveDraft()** - 保存时获取编辑器HTML内容
4. **togglePreview()** - 预览时使用微信样式
5. **generateFromHotspot()** - 生成内容后设置到编辑器

## 集成步骤

### 1. 修改HTML结构

```javascript
function render() {
    return `
        <div class="creation-editor">
            <div class="editor-panel" id="editor-panel">
                <input type="text" id="article-title" class="article-title-input" placeholder="请输入标题...">
                <!-- 替换textarea为wangEditor容器 -->
                <div id="wechat-toolbar"></div>
                <div id="wechat-editor" style="height: 500px; overflow-y: auto;"></div>
            </div>
            <div class="preview-panel" id="preview-panel" style="display: none;">
                <h2 id="preview-title" class="preview-title">标题预览</h2>
                <div id="preview-content" class="preview-content"></div>
            </div>
        </div>
    `;
}
```

### 2. 修改init()函数

```javascript
function init() {
    loadDrafts();
    loadCollections();
    
    // 初始化wangEditor
    window.wechatEditor.init('#wechat-editor', '#wechat-toolbar');
    
    // 监听内容变化
    window.wechatEditor.onChange = function(content) {
        if (currentDraft) {
            currentDraft.content_wechat = content;
        }
    };
    
    setupAutoSave();
}
```

### 3. 修改loadDraft()函数

```javascript
async function loadDraft(draftId) {
    try {
        const response = await fetch(`/api/drafts/${draftId}`);
        const result = await response.json();

        if (result.success) {
            currentDraft = result.data;
            document.getElementById('article-title').value = currentDraft.title || '';
            
            // 设置wangEditor内容
            window.wechatEditor.setHtml(currentDraft.content_wechat || currentDraft.content || '');
            
            displayDrafts();
            updatePreview();
        }
    } catch (error) {
        console.error('加载草稿失败:', error);
        alert('加载草稿失败');
    }
}
```

### 4. 修改saveDraft()函数

```javascript
async function saveDraft() {
    const title = document.getElementById('article-title').value.trim();
    
    // 从wangEditor获取HTML内容
    const content_wechat = window.wechatEditor.getHtml();
    const content = window.wechatEditor.getText(); // 纯文本用于搜索

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
            body: JSON.stringify({ 
                title, 
                content,           // 纯文本
                content_wechat     // HTML格式
            })
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
```

### 5. 修改togglePreview()函数

```javascript
function togglePreview() {
    const editorPanel = document.getElementById('editor-panel');
    const previewPanel = document.getElementById('preview-panel');
    const toggleText = document.getElementById('preview-toggle-text');

    if (previewPanel.style.display === 'none') {
        editorPanel.style.display = 'none';
        previewPanel.style.display = 'block';
        toggleText.textContent = '编辑';
        
        // 使用微信样式预览
        const title = document.getElementById('article-title').value;
        const content = window.wechatEditor.getHtml();
        
        document.getElementById('preview-title').textContent = title || '标题预览';
        document.getElementById('preview-content').innerHTML = `<div class="wechat-article">${content}</div>`;
    } else {
        editorPanel.style.display = 'block';
        previewPanel.style.display = 'none';
        toggleText.textContent = '预览';
    }
}
```

### 6. 修改newDraft()函数

```javascript
function newDraft() {
    currentDraft = {
        id: null,
        title: '',
        content: '',
        content_wechat: ''
    };
    document.getElementById('article-title').value = '';
    
    // 清空wangEditor
    window.wechatEditor.clear();
    
    displayDrafts();
}
```

### 7. 修改selectHotspot()函数

```javascript
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
            
            // 设置到wangEditor
            const content = result.data.content || '';
            if (window.wechatEditor.isMarkdown(content)) {
                const html = window.wechatEditor.convertMarkdownToHtml(content);
                window.wechatEditor.setHtml(html);
            } else {
                window.wechatEditor.setHtml(content);
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
```

### 8. 删除旧的Markdown渲染函数

```javascript
// 删除以下函数，因为wangEditor已经处理
// function renderMarkdown(text) { ... }
// function updatePreview() { ... }
```

## 数据库字段

需要确保drafts表包含以下字段：

```sql
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    content TEXT,              -- 纯文本，用于搜索
    content_wechat TEXT,       -- HTML格式，用于编辑器
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 后端API调整

### GET /api/drafts/:id

返回格式：
```json
{
    "success": true,
    "data": {
        "id": 1,
        "title": "标题",
        "content": "纯文本内容",
        "content_wechat": "<p>HTML内容</p>",
        "created_at": "2024-01-01 12:00:00",
        "updated_at": "2024-01-01 12:00:00"
    }
}
```

### POST/PUT /api/drafts

请求格式：
```json
{
    "title": "标题",
    "content": "纯文本内容",
    "content_wechat": "<p>HTML内容</p>"
}
```

## 联调检查清单

- [ ] 新建草稿时编辑器正常显示
- [ ] 输入内容后能正常保存
- [ ] 加载已有草稿时内容正确显示
- [ ] 图片上传功能正常
- [ ] Markdown粘贴自动转换
- [ ] 预览功能显示微信样式
- [ ] 基于热点生成内容正确显示
- [ ] 自动保存功能正常
- [ ] 切换草稿时编辑器内容正确更新

## 注意事项

1. **向后兼容**：旧草稿可能只有`content`字段，需要兼容处理
2. **自动保存**：setupAutoSave()需要监听wangEditor的onChange事件
3. **性能**：大量HTML内容时注意保存频率
4. **XSS防护**：后端需要对content_wechat进行安全过滤

## 前端2需要配合的工作

1. 确保草稿列表API返回`content_wechat`字段
2. 草稿保存API支持接收`content_wechat`字段
3. 数据库表结构包含`content_wechat`字段
4. 测试草稿的CRUD操作

## 联调时间安排

等待前端2完成草稿列表功能后，进行以下联调：
1. 草稿创建和保存
2. 草稿加载和编辑
3. 图片上传测试
4. 预览功能测试
5. 热点生成测试
