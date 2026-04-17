const DashboardPage = (() => {
  const PLATFORM_NAMES = {
    weibo: '🔴 微博热搜',
    zhihu: '🔵 知乎热榜',
    baidu: '🟢 百度热搜',
    douyin: '🟣 抖音热榜'
  };

  let currentPlatform = 'all';
  let trendingData = {};

  function render() {
    return `
      <div class="dashboard-container">
        <div class="dashboard-header">
          <div class="dashboard-title">
            <h2>热点监控</h2>
            <div class="dashboard-status">
              <span id="last-update">上次更新：加载中...</span>
              <span id="scheduler-status" class="status-badge">检查中...</span>
            </div>
          </div>
          <div class="dashboard-actions">
            <button class="btn btn-secondary btn-sm" onclick="DashboardPage.refresh()">
              🔄 立即刷新
            </button>
            <button class="btn btn-primary btn-sm" onclick="DashboardPage.collectAll()">
              📥 一键采集
            </button>
          </div>
        </div>

        <div class="platform-tabs">
          <button class="platform-tab ${currentPlatform === 'all' ? 'active' : ''}"
                  onclick="DashboardPage.switchPlatform('all')">
            全部平台
          </button>
          <button class="platform-tab ${currentPlatform === 'weibo' ? 'active' : ''}"
                  onclick="DashboardPage.switchPlatform('weibo')">
            ${PLATFORM_NAMES.weibo}
          </button>
          <button class="platform-tab ${currentPlatform === 'zhihu' ? 'active' : ''}"
                  onclick="DashboardPage.switchPlatform('zhihu')">
            ${PLATFORM_NAMES.zhihu}
          </button>
          <button class="platform-tab ${currentPlatform === 'baidu' ? 'active' : ''}"
                  onclick="DashboardPage.switchPlatform('baidu')">
            ${PLATFORM_NAMES.baidu}
          </button>
          <button class="platform-tab ${currentPlatform === 'douyin' ? 'active' : ''}"
                  onclick="DashboardPage.switchPlatform('douyin')">
            ${PLATFORM_NAMES.douyin}
          </button>
        </div>

        <div id="trending-content" class="trending-content">
          <div class="loading-spinner"></div>
        </div>
      </div>
    `;
  }

  async function init() {
    // 确保DOM已渲染后再加载数据
    await new Promise(resolve => setTimeout(resolve, 0));
    await loadTrending();
  }

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
      const container = document.getElementById('trending-content');
      if (container) {
        container.innerHTML =
          '<div class="empty-state"><div class="empty-state-title">加载失败</div><div class="empty-state-description">请刷新重试</div></div>';
      }
    }
  }

  function updateStatus(data) {
    const lastUpdate = document.getElementById('last-update');
    const badge = document.getElementById('scheduler-status');

    if (!lastUpdate || !badge) return;

    if (data.last_update) {
      const d = new Date(data.last_update);
      lastUpdate.textContent = `上次更新：${d.toLocaleString('zh-CN')}`;
    } else {
      lastUpdate.textContent = '上次更新：尚未采集';
    }

    if (data.scheduler && data.scheduler.running) {
      badge.textContent = '监控中';
      badge.className = 'status-badge status-success';
    } else {
      badge.textContent = '已停止';
      badge.className = 'status-badge status-error';
    }
  }

  function renderTrending() {
    const container = document.getElementById('trending-content');
    if (!container) return;

    const platforms = currentPlatform === 'all'
      ? Object.keys(PLATFORM_NAMES)
      : [currentPlatform];

    let html = '';
    for (const plat of platforms) {
      const items = trendingData[plat] || [];
      html += renderPanel(plat, items);
    }

    if (!html) {
      html = '<div class="empty-state"><div class="empty-state-title">暂无热点数据</div><div class="empty-state-description">点击"立即刷新"开始采集</div></div>';
    }
    container.innerHTML = html;
  }

  function renderPanel(platform, items) {
    const name = PLATFORM_NAMES[platform] || platform;
    let html = `<div class="trending-panel">`;
    html += `<div class="trending-panel-header platform-${platform}">`;
    html += `<span class="trending-panel-title">${name}</span>`;
    html += `<div class="trending-panel-actions">`;
    html += `<span class="trending-item-count">${items.length} 条</span>`;
    html += `<button class="btn btn-text btn-sm" onclick="event.stopPropagation();DashboardPage.collectPlatform('${platform}')" title="采集该平台热点文章到文章库">📥 采集入库</button>`;
    html += `</div>`;
    html += `</div>`;
    html += `<div class="trending-grid">`;

    items.forEach((item, idx) => {
      html += `<div class="trending-card" onclick="DashboardPage.openLink('${escapeHtml(item.url)}')">`;
      html += `<div class="trending-rank">${idx + 1}</div>`;
      html += `<div class="trending-card-content">`;
      html += `<div class="trending-title">${escapeHtml(item.title)}</div>`;
      if (item.hot_value) {
        html += `<div class="trending-meta">`;
        html += `<span class="trending-hot">🔥 ${formatHotValue(item.hot_value)}</span>`;
        html += `</div>`;
      }
      html += `</div>`;
      html += `</div>`;
    });

    html += `</div></div>`;
    return html;
  }

  function formatHotValue(val) {
    if (!val) return '';
    const num = parseInt(val);
    if (num >= 100000000) return (num / 100000000).toFixed(1) + '亿';
    if (num >= 10000) return (num / 10000).toFixed(1) + '万';
    return num.toString();
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function switchPlatform(platform) {
    currentPlatform = platform;
    const tabs = document.querySelectorAll('.platform-tab');
    tabs.forEach(tab => tab.classList.remove('active'));
    event.target.classList.add('active');
    renderTrending();
  }

  function openLink(url) {
    if (url && url !== 'undefined') {
      window.open(url, '_blank');
    }
  }

  async function refresh() {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = '刷新中...';

    try {
      const resp = await fetch('/api/trending/refresh', { method: 'POST' });
      const data = await resp.json();

      if (data.success) {
        await loadTrending();
        btn.textContent = '✓ 已刷新';
        setTimeout(() => {
          btn.disabled = false;
          btn.textContent = '🔄 立即刷新';
        }, 2000);
      } else {
        throw new Error(data.error || '刷新失败');
      }
    } catch (e) {
      alert('刷新失败: ' + e.message);
      btn.disabled = false;
      btn.textContent = '🔄 立即刷新';
    }
  }

  async function collectAll() {
    if (!confirm('确定要采集所有平台的热点文章吗？这可能需要较长时间。')) {
      return;
    }

    showCollectProgress('all', '全部平台');

    try {
      const resp = await fetch('/api/trending/collect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform: 'all' })
      });
      const data = await resp.json();

      if (data.success) {
        updateCollectProgress('all', data.data);
      } else {
        throw new Error(data.error || '采集失败');
      }
    } catch (e) {
      hideCollectProgress();
      alert('采集失败: ' + e.message);
    }
  }

  async function collectPlatform(platform) {
    const name = PLATFORM_NAMES[platform] || platform;
    if (!confirm(`确定要采集 ${name} 的热点文章吗？`)) {
      return;
    }

    showCollectProgress(platform, name);

    try {
      const resp = await fetch('/api/trending/collect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform })
      });
      const data = await resp.json();

      if (data.success) {
        updateCollectProgress(platform, data.data);
      } else {
        throw new Error(data.error || '采集失败');
      }
    } catch (e) {
      hideCollectProgress();
      alert('采集失败: ' + e.message);
    }
  }

  function showCollectProgress(platform, name) {
    const overlay = document.createElement('div');
    overlay.id = 'collect-overlay';
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal-content">
        <div class="modal-header">
          <h3>采集进度</h3>
        </div>
        <div class="modal-body" id="collect-progress-body">
          <div class="loading-spinner"></div>
          <p style="text-align:center;margin-top:16px;">正在采集 ${name}...</p>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
  }

  function updateCollectProgress(platform, result) {
    const body = document.getElementById('collect-progress-body');
    const name = PLATFORM_NAMES[platform] || platform;

    body.innerHTML = `
      <div class="collect-result-success">
        <div class="collect-result-icon">✅</div>
        <div class="collect-result-title">${name} 采集完成</div>
      </div>
      <div class="collect-stats">
        <div class="collect-stat-item">
          <div class="collect-stat-value">${result.collected || 0}</div>
          <div class="collect-stat-label">成功采集</div>
        </div>
        <div class="collect-stat-item">
          <div class="collect-stat-value">${result.analyzed || 0}</div>
          <div class="collect-stat-label">已分析</div>
        </div>
        <div class="collect-stat-item">
          <div class="collect-stat-value">${result.skipped || 0}</div>
          <div class="collect-stat-label">已跳过</div>
        </div>
        <div class="collect-stat-item">
          <div class="collect-stat-value">${result.failed || 0}</div>
          <div class="collect-stat-label">失败</div>
        </div>
      </div>
      ${result.articles && result.articles.length > 0 ? `
        <div class="collect-article-list">
          ${result.articles.slice(0, 10).map(a =>
            `<div class="collect-article-item">✓ ${escapeHtml(a.title)}</div>`
          ).join('')}
          ${result.articles.length > 10 ? `<div class="collect-article-item" style="color:var(--color-gray-500);">...还有 ${result.articles.length - 10} 篇</div>` : ''}
        </div>
      ` : ''}
      <button class="btn btn-primary" onclick="DashboardPage.hideCollectProgress()" style="margin-top:16px;width:100%;">关闭</button>
    `;
  }

  function hideCollectProgress() {
    const overlay = document.getElementById('collect-overlay');
    if (overlay) overlay.remove();
  }

  return {
    render,
    init,
    switchPlatform,
    openLink,
    refresh,
    collectAll,
    collectPlatform,
    hideCollectProgress
  };
})();

if (typeof window !== 'undefined') {
  window.DashboardPage = DashboardPage;
}
