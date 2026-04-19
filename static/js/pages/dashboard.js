const DashboardPage = (() => {
  const PLATFORM_NAMES = {
    weibo: '🔴 微博热搜',
    zhihu: '🔵 知乎热榜',
    baidu: '🟢 百度热搜',
    douyin: '🟣 抖音热榜'
  };

  let currentPlatform = 'all';
  let trendingData = {};
  let collectQueue = []; // 采集任务队列
  let isCollecting = false;

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
            <button class="btn btn-primary btn-sm" id="collect-all-btn" onclick="DashboardPage.collectAll()">
              📥 一键采集
            </button>
            <div id="collect-progress-bar" class="collect-progress-bar" style="display:none;">
              <div class="collect-progress-track">
                <div class="collect-progress-fill" id="collect-progress-fill"></div>
              </div>
              <span class="collect-progress-text" id="collect-progress-text">0/0</span>
              <div class="collect-progress-tooltip" id="collect-progress-tooltip">
                <div class="tooltip-title">采集详情</div>
                <div class="tooltip-body" id="collect-tooltip-body"></div>
              </div>
            </div>
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
    html += `<button class="btn btn-text btn-sm" id="collect-btn-${platform}" onclick="event.stopPropagation();DashboardPage.collectPlatform('${platform}')" title="采集该平台热点文章到文章库">📥 采集入库</button>`;
    html += `<div class="collect-mini-progress" id="collect-mini-${platform}" style="display:none;">
      <div class="mini-progress-track"><div class="mini-progress-fill" id="mini-fill-${platform}"></div></div>
      <span class="mini-progress-text" id="mini-text-${platform}"></span>
    </div>`;
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
    const platforms = Object.keys(PLATFORM_NAMES);
    platforms.forEach(p => addToQueue(p));
    processQueue();
  }

  async function collectPlatform(platform) {
    addToQueue(platform);
    processQueue();
  }

  function addToQueue(platform) {
    if (collectQueue.find(t => t.platform === platform && t.status !== 'done' && t.status !== 'error')) return;
    collectQueue.push({
      platform,
      name: PLATFORM_NAMES[platform] || platform,
      status: 'pending', // pending | running | done | error
      result: null
    });
    renderProgress();
  }

  async function processQueue() {
    if (isCollecting) return;
    isCollecting = true;

    while (true) {
      const task = collectQueue.find(t => t.status === 'pending');
      if (!task) break;

      task.status = 'running';
      renderProgress();

      try {
        const resp = await fetch('/api/trending/collect', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ platform: task.platform })
        });
        const data = await resp.json();

        if (data.success) {
          task.status = 'done';
          task.result = data.data;
        } else {
          task.status = 'error';
          task.result = { error: data.error || '采集失败' };
        }
      } catch (e) {
        task.status = 'error';
        task.result = { error: e.message };
      }

      renderProgress();
    }

    isCollecting = false;

    // 5秒后自动清理已完成的队列
    setTimeout(() => {
      collectQueue = collectQueue.filter(t => t.status !== 'done' && t.status !== 'error');
      renderProgress();
    }, 8000);
  }

  function renderProgress() {
    const bar = document.getElementById('collect-progress-bar');
    const fill = document.getElementById('collect-progress-fill');
    const text = document.getElementById('collect-progress-text');
    const tooltipBody = document.getElementById('collect-tooltip-body');
    const btn = document.getElementById('collect-all-btn');

    if (!bar) return;

    if (collectQueue.length === 0) {
      bar.style.display = 'none';
      if (btn) { btn.disabled = false; btn.textContent = '📥 一键采集'; }
      // 隐藏所有平台mini进度
      Object.keys(PLATFORM_NAMES).forEach(p => {
        const mini = document.getElementById(`collect-mini-${p}`);
        if (mini) mini.style.display = 'none';
        const pbtn = document.getElementById(`collect-btn-${p}`);
        if (pbtn) { pbtn.style.display = ''; pbtn.disabled = false; }
      });
      return;
    }

    bar.style.display = 'flex';
    if (btn) { btn.disabled = true; btn.textContent = '采集中...'; }

    const done = collectQueue.filter(t => t.status === 'done').length;
    const error = collectQueue.filter(t => t.status === 'error').length;
    const total = collectQueue.length;
    const finished = done + error;
    const percent = total > 0 ? Math.round((finished / total) * 100) : 0;

    fill.style.width = percent + '%';
    fill.className = 'collect-progress-fill' + (error > 0 ? ' has-error' : '') + (finished === total ? ' completed' : '');
    text.textContent = `${finished}/${total}`;

    // 更新tooltip详情
    tooltipBody.innerHTML = collectQueue.map(t => {
      const icon = t.status === 'done' ? '✅' : t.status === 'error' ? '❌' : t.status === 'running' ? '⏳' : '⏸️';
      let detail = '';
      if (t.status === 'done' && t.result) {
        detail = `成功${t.result.collected || 0} 跳过${t.result.skipped || 0} 失败${t.result.failed || 0}`;
      } else if (t.status === 'error' && t.result) {
        detail = t.result.error || '未知错误';
      } else if (t.status === 'running') {
        detail = '采集中...';
      } else {
        detail = '等待中';
      }
      return `<div class="tooltip-row">
        <span class="tooltip-icon">${icon}</span>
        <span class="tooltip-name">${t.name}</span>
        <span class="tooltip-detail">${detail}</span>
      </div>`;
    }).join('');

    // 更新每个平台的mini进度
    collectQueue.forEach(t => {
      const mini = document.getElementById(`collect-mini-${t.platform}`);
      const miniFill = document.getElementById(`mini-fill-${t.platform}`);
      const miniText = document.getElementById(`mini-text-${t.platform}`);
      const pbtn = document.getElementById(`collect-btn-${t.platform}`);

      if (mini) {
        mini.style.display = 'inline-flex';
        if (pbtn) pbtn.style.display = 'none';
      }
      if (miniFill) {
        const w = t.status === 'done' ? '100%' : t.status === 'running' ? '60%' : '0%';
        miniFill.style.width = w;
        miniFill.className = 'mini-progress-fill' + (t.status === 'done' ? ' done' : '') + (t.status === 'error' ? ' error' : '');
      }
      if (miniText) {
        miniText.textContent = t.status === 'done' ? `✅ ${t.result?.collected || 0}篇`
          : t.status === 'error' ? '❌'
          : t.status === 'running' ? '⏳'
          : '⏸️';
      }
    });
  }

  return {
    render,
    init,
    switchPlatform,
    openLink,
    refresh,
    collectAll,
    collectPlatform,
  };
})();

if (typeof window !== 'undefined') {
  window.DashboardPage = DashboardPage;
}
