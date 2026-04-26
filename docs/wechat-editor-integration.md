# wangEditor 微信公众号编辑器集成文档

## 概述

本项目已集成 wangEditor v5 富文本编辑器，专门用于微信公众号文章编辑。

## 文件结构

```
static/
├── js/components/
│   └── wechat-editor.js          # 编辑器核心组件
├── css/components/
│   └── wechat-editor.css         # 微信样式
└── uploads/wechat/               # 图片上传目录

templates/
└── wechat-editor-demo.html       # Demo演示页面
```

## 快速开始

### 1. 引入依赖

在HTML中引入必要的CSS和JS文件：

```html
<!-- wangEditor CDN -->
<link href="https://unpkg.com/@wangeditor/editor@5.1.23/dist/css/style.css" rel="stylesheet">
<script src="https://unpkg.com/@wangeditor/editor@5.1.23/dist/index.js"></script>

<!-- 微信编辑器组件 -->
<link rel="stylesheet" href="/static/css/components/wechat-editor.css">
<script src="/static/js/components/wechat-editor.js"></script>
```

### 2. HTML结构

```html
<div id="toolbar-container"></div>
<div id="editor-container"></div>
<div id="preview-container"></div>
```

### 3. 初始化编辑器

```javascript
// 初始化
window.wechatEditor.init('#editor-container', '#toolbar-container');

// 监听内容变化
window.wechatEditor.onChange = function(content) {
    console.log('内容变化:', content);
};
```

## API文档

### 初始化

```javascript
wechatEditor.init(editorSelector, toolbarSelector)
```

- `editorSelector`: 编辑器容器选择器
- `toolbarSelector`: 工具栏容器选择器
- 返回: `{ editor, toolbar }` 对象

### 内容操作

#### 获取HTML内容
```javascript
const html = wechatEditor.getHtml();
```

#### 获取纯文本
```javascript
const text = wechatEditor.getText();
```

#### 设置HTML内容
```javascript
wechatEditor.setHtml('<p>Hello World</p>');
```

#### 清空内容
```javascript
wechatEditor.clear();
```

### 预览功能

```javascript
wechatEditor.togglePreview('preview-container');
```

### Markdown支持

#### 检测Markdown格式
```javascript
const isMd = wechatEditor.isMarkdown(text);
```

#### 转换Markdown为HTML
```javascript
const html = wechatEditor.convertMarkdownToHtml(markdown);
```

### 销毁编辑器

```javascript
wechatEditor.destroy();
```

## 功能特性

### 1. 工具栏配置

已配置的工具栏按钮：
- 标题选择（H1-H6）
- 文本格式：加粗、斜体、下划线、删除线
- 颜色：文字颜色、背景色
- 字体：字号、字体、行高
- 列表：无序列表、有序列表
- 对齐：左对齐、居中、右对齐
- 插入：链接、图片
- 操作：撤销、重做

### 2. 图片上传

- 上传接口：`/api/upload/wechat-image`
- 支持格式：png, jpg, jpeg, gif, webp
- 最大文件：5MB
- 最多数量：10张
- 上传目录：`static/uploads/wechat/`

上传成功后返回格式：
```json
{
    "success": true,
    "data": {
        "url": "/static/uploads/wechat/xxx.jpg",
        "alt": "原文件名",
        "href": "/static/uploads/wechat/xxx.jpg"
    }
}
```

### 3. Markdown自动转换

粘贴Markdown格式文本时自动转换为HTML，支持：
- 标题：`# ## ###`
- 加粗：`**text**` 或 `__text__`
- 斜体：`*text*` 或 `_text_`
- 链接：`[text](url)`
- 代码：`` `code` ``
- 列表：`- item` 或 `1. item`

### 4. 微信公众号样式

预览时自动应用微信公众号样式：
- 最大宽度：677px
- 字体：系统默认字体
- 字号：16px
- 行高：1.75
- H2标题带绿色左边框
- 图片自动居中
- 响应式适配

## 使用示例

### 在创作中心集成

```javascript
// 在 creation.js 中替换 textarea
function render() {
    return `
        <div class="creation-editor">
            <div id="wechat-toolbar"></div>
            <div id="wechat-editor"></div>
        </div>
    `;
}

function init() {
    // 初始化编辑器
    window.wechatEditor.init('#wechat-editor', '#wechat-toolbar');
    
    // 监听变化
    window.wechatEditor.onChange = function(content) {
        currentDraft.content = content;
    };
}

function saveDraft() {
    const content = window.wechatEditor.getHtml();
    // 保存逻辑...
}
```

## Demo页面

访问 `http://localhost:9000/wechat-editor-demo` 查看完整演示。

Demo功能：
- 获取HTML内容
- 预览微信样式
- 清空编辑器
- 测试Markdown粘贴

## 注意事项

1. **CDN依赖**：使用unpkg CDN，确保网络可访问
2. **图片存储**：上传的图片存储在本地，生产环境建议使用OSS
3. **内容安全**：编辑器内容需要进行XSS过滤
4. **浏览器兼容**：支持现代浏览器，IE不支持

## 后续优化

- [ ] 添加图片压缩功能
- [ ] 支持图片拖拽上传
- [ ] 集成微信样式模板库
- [ ] 添加内容自动保存
- [ ] 支持导出为Markdown
- [ ] 添加字数统计
- [ ] 支持多人协作编辑

## 技术栈

- wangEditor v5.1.23
- Flask (后端)
- 原生JavaScript (无框架依赖)
