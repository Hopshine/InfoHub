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
    html += `<span class="item-count">${items.length} 条</span>`;
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
