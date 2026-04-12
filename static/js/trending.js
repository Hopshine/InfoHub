// 热点监控页面JS
const PLATFORM_NAMES = {
    weibo: '🔴 微博热搜',
    zhihu: '🔵 知乎热榜',
    baidu: '🟢 百度热搜',
    douyin: '🟣 抖音热榜'
};

let currentPlatform = 'all';
let trendingData = {};

// 页面加载
document.addEventListener('DOMContentLoaded', () => {
    loadTrending();
});

async function loadTrending() {
    try {
        const resp = await fetch('/api/trending');
        const data = await resp.json();
        if (data.success) {
            trendingData = data.data.trending;
            updateStatus(data.data);
            renderTrending();
        }
    } catch (e) {
        document.getElementById('trending-content').innerHTML =
            '<div class="empty-state">加载失败，请刷新重试</div>';
    }
}

function updateStatus(data) {
    const lastUpdate = document.getElementById('last-update');
    const badge = document.getElementById('scheduler-status');

    if (data.last_update) {
        const d = new Date(data.last_update);
        lastUpdate.textContent = `上次更新：${d.toLocaleString('zh-CN')}`;
    } else {
        lastUpdate.textContent = '上次更新：尚未采集';
    }

    if (data.scheduler && data.scheduler.running) {
        badge.textContent = '监控中';
        badge.className = 'status-badge';
    } else {
        badge.textContent = '已停止';
        badge.className = 'status-badge error';
    }
}

function renderTrending() {
    const container = document.getElementById('trending-content');
    const platforms = currentPlatform === 'all'
        ? Object.keys(PLATFORM_NAMES)
        : [currentPlatform];

    let html = '';
    for (const plat of platforms) {
        const items = trendingData[plat] || [];
        html += renderPanel(plat, items);
    }

    if (!html) {
        html = '<div class="empty-state">暂无热点数据，点击"立即刷新"开始采集</div>';
    }
    container.innerHTML = html;
}

function renderPanel(platform, items) {
    const name = PLATFORM_NAMES[platform] || platform;
    let html = `<div class="trending-panel">`;
    html += `<div class="panel-header ${platform}">`;
    html += `<span>${name}</span>`;
    html += `<div class="panel-header-actions">`;
    html += `<span class="item-count">${items.length} 条</span>`;
    html += `<button class="btn-collect" onclick="event.stopPropagation();collectPlatform('${platform}')" title="采集该平台热点文章到文章库">📥 采集入库</button>`;
    html += `</div>`;
    html += `</div>`;
    html += `<div class="trending-list">`;

    if (items.length === 0) {
        html += '<div class="empty-state">暂无数据</div>';
    } else {
        for (const item of items) {
            const rank = item.rank_num || item.rank;
            const rankClass = rank <= 3 ? ` top${rank}` : '';
            const url = item.url || '#';
            const label = item.label
                ? `<span class="item-label">${item.label}</span>` : '';
            const hotText = item.hot_value
                ? `<div class="item-hot">${formatHot(item.hot_value)}</div>` : '';

            html += `<a class="trending-item" href="${url}" target="_blank" rel="noopener">`;
            html += `<span class="item-rank${rankClass}">${rank}</span>`;
            html += `<div class="item-info">`;
            html += `<div class="item-title">${escapeHtml(item.title)}</div>`;
            html += hotText;
            html += `</div>`;
            html += label;
            html += `</a>`;
        }
    }

    html += `</div></div>`;
    return html;
}

function switchPlatform(platform) {
    currentPlatform = platform;
    document.querySelectorAll('.platform-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.platform === platform);
    });
    renderTrending();
}

async function refreshAll() {
    const btn = document.querySelector('.trending-status-bar .btn');
    btn.textContent = '⏳ 刷新中...';
    btn.disabled = true;

    try {
        const resp = await fetch('/api/trending/refresh', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        });
        const data = await resp.json();
        if (data.success) {
            await loadTrending();
        } else {
            alert('刷新失败: ' + (data.error || '未知错误'));
        }
    } catch (e) {
        alert('刷新失败: ' + e.message);
    } finally {
        btn.textContent = '🔄 立即刷新';
        btn.disabled = false;
    }
}

function formatHot(value) {
    if (typeof value === 'string') return value;
    const num = parseInt(value);
    if (isNaN(num)) return value;
    if (num >= 10000) return (num / 10000).toFixed(1) + '万';
    return num.toLocaleString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== 采集入库 ====================

async function collectPlatform(platform) {
    const name = PLATFORM_NAMES[platform] || platform;
    const count = trendingData[platform] ? trendingData[platform].length : 0;
    if (count === 0) {
        alert('该平台暂无热点数据');
        return;
    }

    if (!confirm(`确定要将${name}的热点文章采集入库吗？\n将尝试采集${count}条热点对应的新闻原文。`)) {
        return;
    }

    // 找到对应按钮并更新状态
    const btns = document.querySelectorAll('.btn-collect');
    let targetBtn = null;
    btns.forEach(btn => {
        if (btn.onclick && btn.onclick.toString().includes(platform)) {
            targetBtn = btn;
        }
    });

    // 显示采集进度浮层
    showCollectProgress(platform, count);

    try {
        const resp = await fetch('/api/trending/collect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                platform: platform,
                analyze: true
            })
        });
        const data = await resp.json();

        if (data.success) {
            const r = data.data;
            showCollectResult(platform, r);
        } else {
            hideCollectProgress();
            alert('采集失败: ' + (data.error || '未知错误'));
        }
    } catch (e) {
        hideCollectProgress();
        alert('采集失败: ' + e.message);
    }
}

function showCollectProgress(platform, total) {
    // 移除旧的浮层
    hideCollectProgress();

    const name = PLATFORM_NAMES[platform] || platform;
    const overlay = document.createElement('div');
    overlay.id = 'collect-overlay';
    overlay.innerHTML = `
        <div class="collect-progress-box">
            <div class="collect-progress-header">
                <span>📥 正在采集 ${name}</span>
            </div>
            <div class="collect-progress-body">
                <div class="collect-spinner"></div>
                <p>正在采集 ${total} 条热点对应的新闻原文...</p>
                <p style="font-size:0.85em;color:#8c8c8c;">采集过程可能需要几分钟，请耐心等待</p>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
}

function showCollectResult(platform, result) {
    const overlay = document.getElementById('collect-overlay');
    if (!overlay) return;

    const name = PLATFORM_NAMES[platform] || platform;
    const box = overlay.querySelector('.collect-progress-box');
    box.innerHTML = `
        <div class="collect-progress-header success">
            <span>✅ ${name} 采集完成</span>
        </div>
        <div class="collect-progress-body">
            <div class="collect-stats">
                <div class="collect-stat">
                    <div class="collect-stat-value">${result.collected}</div>
                    <div class="collect-stat-label">成功采集</div>
                </div>
                <div class="collect-stat">
                    <div class="collect-stat-value">${result.analyzed || 0}</div>
                    <div class="collect-stat-label">已分析</div>
                </div>
                <div class="collect-stat">
                    <div class="collect-stat-value">${result.skipped}</div>
                    <div class="collect-stat-label">已跳过</div>
                </div>
                <div class="collect-stat">
                    <div class="collect-stat-value">${result.failed}</div>
                    <div class="collect-stat-label">失败</div>
                </div>
            </div>
            ${result.articles && result.articles.length > 0 ? `
                <div class="collect-article-list">
                    ${result.articles.slice(0, 10).map(a =>
                        `<div class="collect-article-item">✓ ${escapeHtml(a.title)}</div>`
                    ).join('')}
                    ${result.articles.length > 10 ? `<div class="collect-article-item" style="color:#8c8c8c;">...还有 ${result.articles.length - 10} 篇</div>` : ''}
                </div>
            ` : ''}
            <button class="btn btn-primary" onclick="hideCollectProgress()" style="margin-top:16px;">关闭</button>
        </div>
    `;
}

function hideCollectProgress() {
    const overlay = document.getElementById('collect-overlay');
    if (overlay) overlay.remove();
}
