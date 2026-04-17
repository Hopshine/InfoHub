// SPA路由系统

/**
 * InfoHub SPA应用主入口
 * 负责路由管理、页面切换、导航高亮
 */

// ==================== 全局状态 ====================

const AppState = {
    currentRoute: null,
    currentModule: null,
    loadingElement: null,
    mainContent: null
};

// ==================== 路由配置 ====================

const Routes = {
    '/dashboard': {
        name: '热点监控',
        module: 'dashboard',
        loader: () => loadDashboardModule()
    },
    '/content': {
        name: '内容库',
        module: 'content',
        loader: () => loadContentModule()
    },
    '/analysis': {
        name: 'AI分析',
        module: 'analysis',
        loader: () => loadAnalysisModule()
    },
    '/creation': {
        name: '创作中心',
        module: 'creation',
        loader: () => loadCreationModule()
    },
    '/publish': {
        name: '发布管理',
        module: 'publish',
        loader: () => loadPublishModule()
    },
    '/settings': {
        name: '系统设置',
        module: 'settings',
        loader: () => loadSettingsModule()
    }
};

// ==================== 应用初始化 ====================

/**
 * 应用初始化
 */
function initApp() {
    AppState.loadingElement = document.getElementById('loading-container');
    AppState.mainContent = document.getElementById('main-content');

    // 监听hash变化
    window.addEventListener('hashchange', handleRouteChange);

    // 监听导航点击
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', handleNavClick);
    });

    // 初始路由
    const hash = window.location.hash || '#/dashboard';
    window.location.hash = hash;
    handleRouteChange();
}

/**
 * 处理路由变化
 */
function handleRouteChange() {
    const hash = window.location.hash.slice(1) || '/dashboard';
    const route = Routes[hash];

    if (!route) {
        console.error('未找到路由:', hash);
        loadNotFoundPage();
        return;
    }

    AppState.currentRoute = hash;
    updateNavigation(hash);
    loadPage(route);
}

/**
 * 处理导航点击
 */
function handleNavClick(event) {
    const navItem = event.currentTarget;
    const href = navItem.getAttribute('href');

    if (href && href.startsWith('#/')) {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });
        navItem.classList.add('active');
    }
}

/**
 * 更新导航高亮
 */
function updateNavigation(route) {
    document.querySelectorAll('.nav-item').forEach(item => {
        const href = item.getAttribute('href');
        if (href === `#${route}`) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
}

/**
 * 加载页面
 */
async function loadPage(route) {
    try {
        showLoading();
        await route.loader();
        hideLoading();
    } catch (error) {
        console.error('加载页面失败:', error);
        showError('页面加载失败，请刷新重试');
    }
}

/**
 * 显示加载状态
 */
function showLoading() {
    if (AppState.loadingElement) {
        AppState.loadingElement.style.display = 'flex';
    }
}

/**
 * 隐藏加载状态
 */
function hideLoading() {
    if (AppState.loadingElement) {
        AppState.loadingElement.style.display = 'none';
    }
}

/**
 * 显示错误信息
 */
function showError(message) {
    if (AppState.mainContent) {
        AppState.mainContent.innerHTML = `
            <div class="error-container" style="text-align:center;padding:60px 20px;">
                <div style="font-size:48px;margin-bottom:20px;">⚠️</div>
                <h2 style="color:#ff4d4f;margin-bottom:12px;">加载失败</h2>
                <p style="color:#8c8c8c;margin-bottom:24px;">${escapeHtml(message)}</p>
                <button class="btn btn-primary" onclick="location.reload()">刷新页面</button>
            </div>
        `;
    }
    hideLoading();
}

/**
 * 404页面
 */
function loadNotFoundPage() {
    if (AppState.mainContent) {
        AppState.mainContent.innerHTML = `
            <div class="error-container" style="text-align:center;padding:60px 20px;">
                <div style="font-size:48px;margin-bottom:20px;">🔍</div>
                <h2 style="color:#8c8c8c;margin-bottom:12px;">页面未找到</h2>
                <p style="color:#8c8c8c;margin-bottom:24px;">您访问的页面不存在</p>
                <button class="btn btn-primary" onclick="window.location.hash='#/dashboard'">返回首页</button>
            </div>
        `;
    }
    hideLoading();
}

// ==================== 页面模块加载器 ====================

/**
 * 加载热点监控模块
 */
async function loadDashboardModule() {
    if (typeof window.DashboardPage !== 'undefined' && typeof window.DashboardPage.render === 'function') {
        AppState.mainContent.innerHTML = window.DashboardPage.render();
        if (typeof window.DashboardPage.init === 'function') {
            await window.DashboardPage.init();
        }
    } else {
        AppState.mainContent.innerHTML = `
            <div class="error-container" style="text-align:center;padding:60px 20px;">
                <div style="font-size:48px;margin-bottom:20px;">⚠️</div>
                <h2 style="color:#ff4d4f;margin-bottom:12px;">模块加载失败</h2>
                <p style="color:#8c8c8c;margin-bottom:24px;">热点监控模块未正确加载</p>
                <button class="btn btn-primary" onclick="location.reload()">刷新页面</button>
            </div>
        `;
    }
}

/**
 * 加载内容库模块
 */
async function loadContentModule() {
    if (typeof window.ContentPage !== 'undefined' && typeof window.ContentPage.render === 'function') {
        AppState.mainContent.innerHTML = window.ContentPage.render();
        if (typeof window.ContentPage.init === 'function') {
            await window.ContentPage.init();
        }
    } else {
        AppState.mainContent.innerHTML = `
            <div class="error-container" style="text-align:center;padding:60px 20px;">
                <div style="font-size:48px;margin-bottom:20px;">⚠️</div>
                <h2 style="color:#ff4d4f;margin-bottom:12px;">模块加载失败</h2>
                <p style="color:#8c8c8c;margin-bottom:24px;">内容库模块未正确加载</p>
                <button class="btn btn-primary" onclick="location.reload()">刷新页面</button>
            </div>
        `;
    }
}

/**
 * 加载AI分析模块
 */
async function loadAnalysisModule() {
    if (typeof window.analysisPage !== 'undefined' && typeof window.analysisPage.render === 'function') {
        AppState.mainContent.innerHTML = window.analysisPage.render();
        if (typeof window.analysisPage.init === 'function') {
            await window.analysisPage.init();
        }
    } else {
        AppState.mainContent.innerHTML = `
            <div class="error-container" style="text-align:center;padding:60px 20px;">
                <div style="font-size:48px;margin-bottom:20px;">⚠️</div>
                <h2 style="color:#ff4d4f;margin-bottom:12px;">模块加载失败</h2>
                <p style="color:#8c8c8c;margin-bottom:24px;">AI分析模块未正确加载</p>
                <button class="btn btn-primary" onclick="location.reload()">刷新页面</button>
            </div>
        `;
    }
}

/**
 * 加载创作中心模块
 */
async function loadCreationModule() {
    if (typeof window.creationPage !== 'undefined' && typeof window.creationPage.render === 'function') {
        AppState.mainContent.innerHTML = window.creationPage.render();
        if (typeof window.creationPage.init === 'function') {
            await window.creationPage.init();
        }
    } else {
        AppState.mainContent.innerHTML = `
            <div class="error-container" style="text-align:center;padding:60px 20px;">
                <div style="font-size:48px;margin-bottom:20px;">⚠️</div>
                <h2 style="color:#ff4d4f;margin-bottom:12px;">模块加载失败</h2>
                <p style="color:#8c8c8c;margin-bottom:24px;">创作中心模块未正确加载</p>
                <button class="btn btn-primary" onclick="location.reload()">刷新页面</button>
            </div>
        `;
    }
}

/**
 * 加载发布管理模块
 */
async function loadPublishModule() {
    if (typeof window.publishPage !== 'undefined' && typeof window.publishPage.render === 'function') {
        AppState.mainContent.innerHTML = window.publishPage.render();
        if (typeof window.publishPage.init === 'function') {
            await window.publishPage.init();
        }
    } else {
        AppState.mainContent.innerHTML = `
            <div class="error-container" style="text-align:center;padding:60px 20px;">
                <div style="font-size:48px;margin-bottom:20px;">⚠️</div>
                <h2 style="color:#ff4d4f;margin-bottom:12px;">模块加载失败</h2>
                <p style="color:#8c8c8c;margin-bottom:24px;">发布管理模块未正确加载</p>
                <button class="btn btn-primary" onclick="location.reload()">刷新页面</button>
            </div>
        `;
    }
}

/**
 * 加载系统设置模块
 */
async function loadSettingsModule() {
    if (typeof window.settingsPage !== 'undefined' && typeof window.settingsPage.init === 'function') {
        window.settingsPage.init();
    } else {
        AppState.mainContent.innerHTML = `
            <div class="error-container" style="text-align:center;padding:60px 20px;">
                <div style="font-size:48px;margin-bottom:20px;">⚠️</div>
                <h2 style="color:#ff4d4f;margin-bottom:12px;">模块加载失败</h2>
                <p style="color:#8c8c8c;margin-bottom:24px;">系统设置模块未正确加载</p>
                <button class="btn btn-primary" onclick="location.reload()">刷新页面</button>
            </div>
        `;
    }
}

// ==================== 辅助函数 ====================

/**
 * 动态加载JS脚本
 */
function loadScript(src) {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = src;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

/**
 * 加载文章数据
 */
async function loadArticlesData() {
    try {
        const [statsResult, articlesResult] = await Promise.all([
            API.stats.get(),
            API.articles.list(1, 20)
        ]);

        if (statsResult.success) {
            document.getElementById('total-articles').textContent = statsResult.data.total || 0;
            document.getElementById('analyzed-articles').textContent = statsResult.data.analyzed || 0;
            document.getElementById('pending-articles').textContent = statsResult.data.pending || 0;
            document.getElementById('categories-count').textContent = Object.keys(statsResult.data.categories || {}).length;

            // 更新分类过滤器
            const categoryFilter = document.getElementById('category-filter');
            categoryFilter.innerHTML = '<option value="">全部分类</option>';
            Object.entries(statsResult.data.categories || {}).forEach(([cat, count]) => {
                categoryFilter.innerHTML += `<option value="${escapeHtml(cat)}">${escapeHtml(cat)} (${count})</option>`;
            });
        }

        if (articlesResult.success) {
            renderArticlesList(articlesResult.data.articles);
        }
    } catch (error) {
        console.error('加载文章数据失败:', error);
        showToast('加载数据失败', 'error');
    }
}

/**
 * 渲染文章列表
 */
function renderArticlesList(articles) {
    const listElement = document.getElementById('articles-list');
    if (!articles || articles.length === 0) {
        listElement.innerHTML = '<div class="empty-state">暂无文章数据</div>';
        return;
    }

    let html = '<div class="articles-grid">';
    articles.forEach(article => {
        html += `
            <div class="article-card">
                <h3 class="article-title">${escapeHtml(article.title)}</h3>
                <div class="article-meta">
                    <span>${article.account_name || '未知来源'}</span>
                    <span>${formatDate(article.publish_time)}</span>
                </div>
                <div class="article-actions">
                    <button class="btn btn-sm" onclick="viewArticle(${article.id})">查看</button>
                    <button class="btn btn-sm btn-success" onclick="analyzeArticle(${article.id})">分析</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteArticle(${article.id})">删除</button>
                </div>
            </div>
        `;
    });
    html += '</div>';
    listElement.innerHTML = html;
}

/**
 * 加载待分析文章
 */
async function loadUnanalyzedArticles() {
    try {
        const result = await API.articles.list(1, 50);
        if (result.success) {
            const unanalyzed = result.data.articles.filter(a => !a.analysis);
            const listElement = document.getElementById('unanalyzed-list');
            if (unanalyzed.length === 0) {
                listElement.innerHTML = '<div class="empty-state">暂无待分析文章</div>';
            } else {
                renderArticlesList(unanalyzed);
            }
        }
    } catch (error) {
        console.error('加载待分析文章失败:', error);
    }
}

/**
 * 加载参考文章列表
 */
async function loadReferenceArticles() {
    try {
        const result = await API.articles.list(1, 100);
        if (result.success) {
            const select = document.getElementById('reference-articles');
            select.innerHTML = result.data.articles.map(a =>
                `<option value="${a.id}">${escapeHtml(a.title)}</option>`
            ).join('');
        }
    } catch (error) {
        console.error('加载参考文章失败:', error);
    }
}

/**
 * 加载已发布文章
 */
async function loadPublishedArticles() {
    try {
        const result = await API.publish.published();
        const listElement = document.getElementById('published-list');
        if (result.success && result.data.length > 0) {
            let html = '<div class="published-grid">';
            result.data.forEach(item => {
                html += `
                    <div class="published-card">
                        <h3>${escapeHtml(item.title)}</h3>
                        <div class="published-meta">
                            <span>公众号: ${escapeHtml(item.account_name)}</span>
                            <span>发布时间: ${formatDate(item.publish_time)}</span>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
            listElement.innerHTML = html;
        } else {
            listElement.innerHTML = '<div class="empty-state">暂无已发布文章</div>';
        }
    } catch (error) {
        console.error('加载已发布文章失败:', error);
        document.getElementById('published-list').innerHTML = '<div class="empty-state">加载失败</div>';
    }
}

// ==================== 页面加载时初始化 ====================

document.addEventListener('DOMContentLoaded', initApp);
