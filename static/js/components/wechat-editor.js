// 微信公众号富文本编辑器组件
(function() {
    let editor = null;
    let toolbar = null;
    let currentContent = '';

    // 初始化编辑器
    function init(containerId, toolbarId) {
        const editorConfig = {
            placeholder: '请输入内容...',
            onChange(editor) {
                currentContent = editor.getHtml();
                handleContentChange();
            },
            MENU_CONF: {}
        };

        // 配置图片上传
        editorConfig.MENU_CONF['uploadImage'] = {
            server: '/api/upload/wechat-image',
            fieldName: 'file',
            maxFileSize: 5 * 1024 * 1024,
            maxNumberOfFiles: 10,
            allowedFileTypes: ['image/*'],

            onBeforeUpload(file) {
                return file;
            },

            onProgress(progress) {
                console.log('上传进度:', progress);
            },

            onSuccess(file, res) {
                console.log('上传成功:', res);
            },

            onFailed(file, res) {
                alert('图片上传失败');
            },

            onError(file, err, res) {
                alert('图片上传错误: ' + err.message);
            },

            customInsert(res, insertFn) {
                if (res.success && res.data && res.data.url) {
                    insertFn(res.data.url, res.data.alt || '', res.data.href || '');
                }
            }
        };

        // 工具栏配置
        const toolbarConfig = {
            toolbarKeys: [
                'headerSelect',
                '|',
                'bold',
                'italic',
                'underline',
                'through',
                '|',
                'color',
                'bgColor',
                '|',
                'fontSize',
                'fontFamily',
                'lineHeight',
                '|',
                'bulletedList',
                'numberedList',
                '|',
                'justifyLeft',
                'justifyCenter',
                'justifyRight',
                '|',
                'insertLink',
                'uploadImage',
                '|',
                'undo',
                'redo'
            ]
        };

        editor = window.wangEditor.createEditor({
            selector: containerId,
            config: editorConfig,
            mode: 'default'
        });

        toolbar = window.wangEditor.createToolbar({
            editor,
            selector: toolbarId,
            config: toolbarConfig,
            mode: 'default'
        });

        setupPasteHandler();

        return { editor, toolbar };
    }

    // 设置粘贴处理器
    function setupPasteHandler() {
        if (!editor) return;

        const editorDom = editor.getEditableContainer();
        if (!editorDom) return;

        editorDom.addEventListener('paste', (e) => {
            const clipboardData = e.clipboardData || window.clipboardData;
            const pastedText = clipboardData.getData('text/plain');

            if (isMarkdown(pastedText)) {
                e.preventDefault();
                const html = convertMarkdownToHtml(pastedText);
                editor.dangerouslyInsertHtml(html);
            }
        });
    }

    // 检测是否为Markdown格式
    function isMarkdown(text) {
        const markdownPatterns = [
            /^#{1,6}\s/m,
            /\*\*.*?\*\*/,
            /\*.*?\*/,
            /\[.*?\]\(.*?\)/,
            /^[-*+]\s/m,
            /^\d+\.\s/m,
            /^>\s/m,
            /`.*?`/,
            /```[\s\S]*?```/
        ];

        return markdownPatterns.some(pattern => pattern.test(text));
    }

    // Markdown转HTML
    function convertMarkdownToHtml(markdown) {
        let html = markdown
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
        html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
        html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

        html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
        html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');
        html = html.replace(/_(.+?)_/g, '<em>$1</em>');

        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');

        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

        html = html.replace(/^[-*+]\s(.+)$/gim, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

        html = html.replace(/^\d+\.\s(.+)$/gim, '<li>$1</li>');

        html = html.replace(/\n\n/g, '</p><p>');
        html = html.replace(/\n/g, '<br>');

        if (!html.startsWith('<')) {
            html = '<p>' + html + '</p>';
        }

    // 内容变化回调
    function handleContentChange() {
        if (window.wechatEditor.onChange) {
            window.wechatEditor.onChange(currentContent);
        }
    }

    // 获取HTML内容
    function getHtml() {
        return editor ? editor.getHtml() : '';
    }

    // 获取纯文本
    function getText() {
        return editor ? editor.getText() : '';
    }

    // 设置HTML内容
    function setHtml(html) {
        if (editor) {
            editor.setHtml(html || '');
        }
    }

    // 清空内容
    function clear() {
        if (editor) {
            editor.clear();
        }
    }

    // 切换预览模式
    function togglePreview(previewContainerId) {
        const previewEl = document.getElementById(previewContainerId);
        if (!previewEl) return;

        const html = getHtml();
        previewEl.innerHTML = wrapWechatStyle(html);
    }

    // 包装微信公众号样式
    function wrapWechatStyle(html) {
        return `<div class="wechat-article">${html}</div>`;
    }

    // 销毁编辑器
    function destroy() {
        if (editor) {
            editor.destroy();
            editor = null;
        }
        if (toolbar) {
            toolbar = null;
        }
    }

    window.wechatEditor = {
        init,
        getHtml,
        getText,
        setHtml,
        clear,
        togglePreview,
        destroy,
        convertMarkdownToHtml,
        isMarkdown,
        onChange: null
    };
})();

