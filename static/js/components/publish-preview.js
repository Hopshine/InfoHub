// 发布预览与状态追踪组件
// 对接后端3 API: POST /api/collections/<id>/publish (同步发布)
(function() {
    let currentArticles = [];
    let currentCollectionId = null;

    // 初始化预览组件
    function init(containerId, collectionId) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.error('预览容器不存在:', containerId);
            return;
        }

        currentCollectionId = collectionId || null;

        container.innerHTML = `
            <div class="publish-preview-container">
                <div class="preview-header">
                    <h3>发布预览</h3>
                    <button class="close-preview-btn" onclick="PublishPreview.close()">×</button>
                </div>

                <div class="preview-content">
                    <div class="wechat-preview-wrapper">
                        <div class="wechat-phone-frame">
                            <div class="wechat-status-bar">
                                <span class="time">9:41</span>
                                <span class="icons">📶 📡 🔋</span>
                            </div>
                            <div class="wechat-header">
                                <span class="back-btn">‹</span>
                                <span class="title">图文消息</span>
                                <span class="more-btn">⋯</span>
                            </div>
                            <div class="wechat-article-list" id="wechatArticleList">
                                <!-- 文章列表将动态插入 -->
                            </div>
                        </div>
                    </div>
                </div>

                <div class="preview-actions">
                    <div class="publish-progress" id="publishProgress" style="display: none;">
                        <div class="progress-bar">
                            <div class="progress-fill" id="progressFill"></div>
                        </div>
                        <div class="progress-text" id="progressText">准备中...</div>
                    </div>

                    <div class="error-message" id="errorMessage" style="display: none;">
                        <span class="error-icon">⚠️</span>
                        <span class="error-text" id="errorText"></span>
                        <button class="retry-btn" onclick="PublishPreview.retry()">重试</button>
                    </div>

                    <div class="action-buttons" id="actionButtons">
                        <button class="btn-secondary" onclick="PublishPreview.saveDraft()">保存草稿</button>
                        <button class="btn-primary" onclick="PublishPreview.publish()">立即群发</button>
                    </div>
                </div>
            </div>
        `;
    }

    // 设置合集ID
    function setCollectionId(collectionId) {
        currentCollectionId = collectionId;
    }

    // 设置预览文章
    function setArticles(articles) {
        currentArticles = articles;
        renderArticles();
    }

    // 渲染文章列表
    function renderArticles() {
        const listContainer = document.getElementById('wechatArticleList');
        if (!listContainer || !currentArticles.length) return;

        const articlesHtml = currentArticles.map((article, index) => {
            const cover = article.cover_image || article.cover || '/static/images/default-cover.jpg';
            const title = article.title || '(无标题)';
            const summary = article.summary || article.digest || '';

            if (index === 0) {
                return `
                    <div class="wechat-article-item first-article">
                        <div class="article-cover" style="background-image: url('${cover}')"></div>
                        <div class="article-title">${title}</div>
                    </div>
                `;
            } else {
                return `
                    <div class="wechat-article-item">
                        <div class="article-info">
                            <div class="article-title">${title}</div>
                            <div class="article-summary">${summary}</div>
                        </div>
                        <div class="article-thumb" style="background-image: url('${cover}')"></div>
                    </div>
                `;
            }
        }).join('');

        listContainer.innerHTML = articlesHtml;
    }

    // 保存草稿（调用后端同步API, publish_now=false）
    async function saveDraft() {
        if (!currentCollectionId) {
            showError('缺少合集ID，无法保存草稿');
            return;
        }

        showProgress('上传图片中...', 20);
        hideError();

        try {
            // 短暂延迟展示上传进度感
            await sleep(300);
            showProgress('创建草稿中...', 60);

            const response = await fetch(`/api/collections/${currentCollectionId}/publish`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ publish_now: false })
            });

            const result = await response.json();

            if (result.success) {
                showProgress('草稿保存成功', 100);
                setTimeout(() => {
                    hideProgress();
                    const mediaId = result.data && result.data.media_id;
                    alert('草稿已保存到微信公众号后台' + (mediaId ? `\nmedia_id: ${mediaId}` : ''));
                }, 1000);
            } else {
                showError(result.error || '保存草稿失败');
            }
        } catch (error) {
            showError('网络错误: ' + error.message);
        }
    }

    // 立即群发（调用后端同步API, publish_now=true）
    async function publish() {
        if (!currentCollectionId) {
            showError('缺少合集ID，无法发布');
            return;
        }

        if (!confirm('确认立即群发这些文章吗？群发后不可撤销。')) return;

        showProgress('上传图片中...', 20);
        hideError();

        try {
            await sleep(300);
            showProgress('创建草稿中...', 50);
            await sleep(300);
            showProgress('群发中...', 80);

            const response = await fetch(`/api/collections/${currentCollectionId}/publish`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ publish_now: true })
            });

            const result = await response.json();

            if (result.success) {
                const status = result.data && result.data.status;

                if (status === 'published') {
                    showProgress('群发成功', 100);
                    setTimeout(() => {
                        alert('文章已成功群发');
                        hideProgress();
                        close();
                    }, 1500);
                } else if (status === 'draft') {
                    showProgress('已创建草稿', 100);
                    setTimeout(() => {
                        alert('已创建草稿，请在微信公众号后台手动群发');
                        hideProgress();
                    }, 1500);
                } else {
                    showError('未知发布状态: ' + status);
                }
            } else {
                showError(result.error || '发布失败');
            }
        } catch (error) {
            showError('网络错误: ' + error.message);
        }
    }

    // 短暂延时
    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // 显示进度
    function showProgress(text, percent) {
        const progressEl = document.getElementById('publishProgress');
        const fillEl = document.getElementById('progressFill');
        const textEl = document.getElementById('progressText');
        const buttonsEl = document.getElementById('actionButtons');

        if (progressEl) progressEl.style.display = 'block';
        if (fillEl) fillEl.style.width = percent + '%';
        if (textEl) textEl.textContent = text;
        if (buttonsEl) buttonsEl.style.display = 'none';
    }

    // 隐藏进度
    function hideProgress() {
        const progressEl = document.getElementById('publishProgress');
        const buttonsEl = document.getElementById('actionButtons');

        if (progressEl) progressEl.style.display = 'none';
        if (buttonsEl) buttonsEl.style.display = 'flex';
    }

    // 显示错误
    function showError(message) {
        const errorEl = document.getElementById('errorMessage');
        const errorTextEl = document.getElementById('errorText');
        const progressEl = document.getElementById('publishProgress');
        const buttonsEl = document.getElementById('actionButtons');

        if (errorEl) errorEl.style.display = 'flex';
        if (errorTextEl) errorTextEl.textContent = message;
        if (progressEl) progressEl.style.display = 'none';
        if (buttonsEl) buttonsEl.style.display = 'none';
    }

    // 隐藏错误
    function hideError() {
        const errorEl = document.getElementById('errorMessage');
        if (errorEl) errorEl.style.display = 'none';
    }

    // 重试（默认重试群发，根据场景调整）
    let lastAction = null;
    function retry() {
        hideError();
        if (lastAction === 'draft') {
            saveDraft();
        } else {
            publish();
        }
    }

    // 关闭预览
    function close() {
        const container = document.querySelector('.publish-preview-container');
        if (container) {
            const parent = container.parentElement;
            if (parent) parent.innerHTML = '';
        }
    }

    // 导出到全局
    window.PublishPreview = {
        init: init,
        setArticles: setArticles,
        setCollectionId: setCollectionId,
        saveDraft: function() { lastAction = 'draft'; saveDraft(); },
        publish: function() { lastAction = 'publish'; publish(); },
        retry: retry,
        close: close
    };
})();
