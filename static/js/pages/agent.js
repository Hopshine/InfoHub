const AgentPage = (() => {
  let statusTimer = null;
  let currentHistoryTab = 'published';
  let articles = [];
  let historyArticles = [];
  let prompts = [];
  let scheduleRunning = false;

  const PIPELINE_STEPS = [
    { key: 'fetch', label: '抓取', icon: '📡' },
    { key: 'filter', label: '筛选', icon: '🔍' },
    { key: 'analyze', label: '分析', icon: '🧠' },
    { key: 'generate', label: '生成', icon: '✍️' },
    { key: 'review', label: '审核', icon: '👁️' },
    { key: 'format', label: '排版', icon: '📐' },
    { key: 'publish', label: '发布', icon: '📤' }
  ];

  function render() {
    return `
      <div class="agent-container">
        <div class="agent-header">
          <h2>野望Agent</h2>
          <div class="agent-actions">
            <button class="btn btn-primary btn-sm" id="agent-run-btn" onclick="AgentPage.manualRun()">
              手动运行
            </button>
            <div class="agent-toggle">
              <span>定时</span>
              <div class="agent-toggle-switch" id="agent-schedule-toggle"
                   onclick="AgentPage.toggleSchedule()"></div>
            </div>
            <button class="btn btn-secondary btn-sm" onclick="AgentPage.openSettings()">
              设置
            </button>
          </div>
        </div>

        <div class="agent-status-card" id="agent-status-card">
          <div class="agent-status-row">
            <div class="agent-status-info">
              <span>上次运行：<strong id="agent-last-run">--</strong></span>
              <span>状态：<strong id="agent-current-status">空闲</strong></span>
            </div>
            <div class="agent-stats-summary" id="agent-stats-summary"></div>
          </div>
          <div class="agent-pipeline" id="agent-pipeline"></div>
        </div>

        <div class="agent-section">
          <div class="agent-section-header">
            <h3>待审核推文</h3>
          </div>
          <div class="agent-article-grid" id="agent-draft-list">
            <div class="loading-spinner"></div>
          </div>
        </div>

        <div class="agent-section">
          <div class="agent-section-header">
            <h3>历史记录</h3>
            <div class="agent-tabs">
              <button class="agent-tab active" onclick="AgentPage.switchHistory('published')">已发布</button>
              <button class="agent-tab" onclick="AgentPage.switchHistory('rejected')">已拒绝</button>
              <button class="agent-tab" onclick="AgentPage.switchHistory('all')">全部</button>
            </div>
          </div>
          <div class="agent-history-list" id="agent-history-list"></div>
        </div>
      </div>

      <div id="agent-settings-modal" style="display:none;"></div>
      <div id="agent-preview-modal" style="display:none;"></div>
    `;
  }

  async function init() {
    await Promise.all([loadStatus(), loadDrafts(), loadHistory(), loadScheduleStatus()]);
  }

  function startPolling() {
    stopPolling();
    statusTimer = setInterval(async () => {
      await loadStatus();
    }, 3000);
  }

  function stopPolling() {
    if (statusTimer) {
      clearInterval(statusTimer);
      statusTimer = null;
    }
  }

  async function loadStatus() {
    try {
      const resp = await fetch('/api/agent/status');
      const data = await resp.json();
      if (data.success) {
        renderStatus(data.data);
        if (data.data.status === 'running') {
          if (!statusTimer) startPolling();
        } else {
          stopPolling();
        }
      }
    } catch (e) {
      console.error('加载Agent状态失败:', e);
    }
  }

  function renderStatus(data) {
    const lastRun = document.getElementById('agent-last-run');
    const curStatus = document.getElementById('agent-current-status');
    const summary = document.getElementById('agent-stats-summary');

    if (lastRun) {
      lastRun.textContent = data.last_run
        ? new Date(data.last_run).toLocaleString('zh-CN')
        : '从未运行';
    }
    if (curStatus) {
      curStatus.textContent = data.status === 'running' ? '运行中' : '空闲';
      curStatus.style.color = data.status === 'running' ? 'var(--color-primary)' : '';
    }
    if (summary && data.stats) {
      const s = data.stats;
      summary.innerHTML = `
        <span>扫描 <strong>${s.scanned || 0}</strong> 条</span>
        <span>筛选 <strong>${s.filtered || 0}</strong> 条</span>
        <span>生成 <strong>${s.generated || 0}</strong> 篇</span>
      `;
    }
    renderPipeline(data.pipeline || []);
  }

  function renderPipeline(pipelineData) {
    const container = document.getElementById('agent-pipeline');
    if (!container) return;

    const html = PIPELINE_STEPS.map((step, i) => {
      const stepData = pipelineData.find(p => p.key === step.key) || {};
      const state = stepData.state || 'pending';
      const count = stepData.count != null ? stepData.count : '';
      const arrow = i < PIPELINE_STEPS.length - 1
        ? '<div class="pipeline-arrow">→</div>' : '';
      return `
        <div class="pipeline-node ${state}">
          <div class="pipeline-icon">${step.icon}</div>
          <div class="pipeline-label">${step.label}</div>
          ${count !== '' ? `<div class="pipeline-count">${count}</div>` : ''}
        </div>
        ${arrow}
      `;
    }).join('');

    container.innerHTML = html;
  }

  async function loadDrafts() {
    try {
      const resp = await fetch('/api/agent/articles?status=draft');
      const data = await resp.json();
      if (data.success) {
        articles = data.data || [];
        renderDrafts();
      }
    } catch (e) {
      const el = document.getElementById('agent-draft-list');
      if (el) el.innerHTML = '<div class="empty-state"><div class="empty-state-title">加载失败</div></div>';
    }
  }

  function renderDrafts() {
    const el = document.getElementById('agent-draft-list');
    if (!el) return;

    if (articles.length === 0) {
      el.innerHTML = '<div class="empty-state"><div class="empty-state-title">暂无待审核推文</div></div>';
      return;
    }

    el.innerHTML = articles.map(a => {
      const scoreClass = a.quality_score >= 0.8 ? 'score-high'
        : a.quality_score >= 0.6 ? 'score-mid' : 'score-low';
      const scoreText = a.quality_score != null ? (a.quality_score * 10).toFixed(1) : '--';
      return `
        <div class="agent-article-card">
          <div class="agent-article-title">${escapeHtml(a.title)}</div>
          <div class="agent-article-meta">
            ${a.source_platform ? `<span>${escapeHtml(a.source_platform)}</span>` : ''}
            <span class="agent-score ${scoreClass}">${scoreText}分</span>
          </div>
          ${a.summary ? `<div class="agent-article-summary">${escapeHtml(a.summary)}</div>` : ''}
          <div class="agent-article-actions">
            <button class="btn btn-sm btn-secondary" onclick="AgentPage.preview(${a.id})">预览</button>
            <button class="btn btn-sm btn-primary" onclick="AgentPage.reviewArticle(${a.id}, 'approved')">通过</button>
            <button class="btn btn-sm" style="color:#dc2626;" onclick="AgentPage.reviewArticle(${a.id}, 'rejected')">拒绝</button>
          </div>
        </div>
      `;
    }).join('');
  }

  async function loadHistory() {
    try {
      const status = currentHistoryTab === 'all' ? '' : currentHistoryTab;
      const resp = await fetch(`/api/agent/articles?status=${status}`);
      const data = await resp.json();
      if (data.success) {
        historyArticles = (data.data || []).filter(a => a.status !== 'draft');
        renderHistory();
      }
    } catch (e) {
      console.error('加载历史记录失败:', e);
    }
  }

  function renderHistory() {
    const el = document.getElementById('agent-history-list');
    if (!el) return;

    const filtered = currentHistoryTab === 'all'
      ? historyArticles
      : historyArticles.filter(a => a.status === currentHistoryTab);

    if (filtered.length === 0) {
      el.innerHTML = '<div class="empty-state"><div class="empty-state-title">暂无记录</div></div>';
      return;
    }

    el.innerHTML = filtered.map(a => {
      const badge = a.status === 'published'
        ? '<span class="badge badge-published">已发布</span>'
        : '<span class="badge badge-rejected">已拒绝</span>';
      const time = a.updated_at ? new Date(a.updated_at).toLocaleString('zh-CN') : '';
      return `
        <div class="agent-history-item">
          <div>
            <span style="font-weight:500;">${escapeHtml(a.title)}</span>
            ${badge}
          </div>
          <span style="color:var(--color-gray-500);font-size:var(--font-size-xs);">${time}</span>
        </div>
      `;
    }).join('');
  }

  function switchHistory(tab) {
    currentHistoryTab = tab;
    document.querySelectorAll('.agent-tabs .agent-tab').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    renderHistory();
  }

  async function manualRun() {
    const btn = document.getElementById('agent-run-btn');
    if (btn) { btn.disabled = true; btn.textContent = '运行中...'; }
    try {
      const resp = await fetch('/api/agent/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await resp.json();
      if (data.success) {
        startPolling();
        await loadStatus();
      } else {
        alert('运行失败: ' + (data.error || '未知错误'));
      }
    } catch (e) {
      alert('运行失败: ' + e.message);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '手动运行'; }
    }
  }

  async function loadScheduleStatus() {
    try {
      const resp = await fetch('/api/agent/schedule/status');
      const data = await resp.json();
      if (data.success) {
        scheduleRunning = data.data.running || false;
        const toggle = document.getElementById('agent-schedule-toggle');
        if (toggle) {
          toggle.classList.toggle('active', scheduleRunning);
        }
      }
    } catch (e) {
      console.error('加载调度状态失败:', e);
    }
  }

  async function toggleSchedule() {
    const action = scheduleRunning ? 'stop' : 'start';
    try {
      const resp = await fetch(`/api/agent/schedule/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await resp.json();
      if (data.success) {
        scheduleRunning = !scheduleRunning;
        const toggle = document.getElementById('agent-schedule-toggle');
        if (toggle) toggle.classList.toggle('active', scheduleRunning);
      } else {
        alert('操作失败: ' + (data.error || ''));
      }
    } catch (e) {
      alert('操作失败: ' + e.message);
    }
  }

  async function reviewArticle(id, action) {
    try {
      const resp = await fetch(`/api/agent/articles/${id}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action })
      });
      const data = await resp.json();
      if (data.success) {
        await Promise.all([loadDrafts(), loadHistory()]);
      } else {
        alert('操作失败: ' + (data.error || ''));
      }
    } catch (e) {
      alert('操作失败: ' + e.message);
    }
  }

  async function preview(id) {
    try {
      const article = articles.find(a => a.id === id);
      if (!article) return;

      let previewTab = 'wechat';
      const modal = document.getElementById('agent-preview-modal');
      modal.style.display = '';
      modal.innerHTML = renderPreviewModal(article, previewTab);
      modal.querySelector('.agent-preview-overlay').onclick = (e) => {
        if (e.target === e.currentTarget) closePreview();
      };
    } catch (e) {
      alert('预览失败: ' + e.message);
    }
  }

  function renderPreviewModal(article, tab) {
    const content = tab === 'wechat'
      ? (article.content_wechat || article.content || '')
      : (article.content_zhihu || article.content || '');
    const rendered = renderMarkdown(content);
    return `
      <div class="agent-preview-overlay">
        <div class="agent-preview-panel">
          <div class="agent-preview-header">
            <h3>${escapeHtml(article.title)}</h3>
            <div class="agent-preview-tabs">
              <button class="agent-tab ${tab === 'wechat' ? 'active' : ''}"
                      onclick="AgentPage.switchPreviewTab(${article.id}, 'wechat')">公众号版</button>
              <button class="agent-tab ${tab === 'zhihu' ? 'active' : ''}"
                      onclick="AgentPage.switchPreviewTab(${article.id}, 'zhihu')">知乎版</button>
            </div>
            <button class="modal-close" onclick="AgentPage.closePreview()">✕</button>
          </div>
          <div class="agent-preview-body">${rendered}</div>
          <div class="agent-preview-actions">
            <button class="btn btn-primary btn-sm" onclick="AgentPage.reviewArticle(${article.id}, 'approved');AgentPage.closePreview();">通过</button>
            <button class="btn btn-sm" style="color:#dc2626;" onclick="AgentPage.reviewArticle(${article.id}, 'rejected');AgentPage.closePreview();">拒绝</button>
          </div>
        </div>
      </div>
    `;
  }

  function switchPreviewTab(id, tab) {
    const article = articles.find(a => a.id === id);
    if (!article) return;
    const modal = document.getElementById('agent-preview-modal');
    modal.innerHTML = renderPreviewModal(article, tab);
    modal.querySelector('.agent-preview-overlay').onclick = (e) => {
      if (e.target === e.currentTarget) closePreview();
    };
  }

  function closePreview() {
    const modal = document.getElementById('agent-preview-modal');
    if (modal) { modal.style.display = 'none'; modal.innerHTML = ''; }
  }

  async function openSettings() {
    await loadPrompts();
    const modal = document.getElementById('agent-settings-modal');
    modal.style.display = '';
    renderSettingsModal();
  }

  function closeSettings() {
    const modal = document.getElementById('agent-settings-modal');
    if (modal) { modal.style.display = 'none'; modal.innerHTML = ''; }
  }

  async function loadPrompts() {
    try {
      const resp = await fetch('/api/agent/prompts');
      const data = await resp.json();
      if (data.success) prompts = data.data || [];
    } catch (e) {
      console.error('加载Prompt失败:', e);
    }
  }

  function renderSettingsModal() {
    const modal = document.getElementById('agent-settings-modal');
    modal.innerHTML = `
      <div class="agent-modal-overlay" onclick="if(event.target===this)AgentPage.closeSettings()">
        <div class="agent-modal">
          <div class="agent-modal-header">
            <h3>Agent 设置</h3>
            <button class="modal-close" onclick="AgentPage.closeSettings()">✕</button>
          </div>
          <div class="agent-modal-body">
            <div class="agent-modal-section">
              <h4>Prompt 管理</h4>
              <div class="agent-prompt-list" id="agent-prompt-list">
                ${prompts.map(p => `
                  <div class="agent-prompt-item ${p.is_active ? 'active-prompt' : ''}">
                    <div>
                      <strong>${escapeHtml(p.name)}</strong>
                      ${p.is_active ? '<span class="badge badge-green" style="margin-left:4px;">当前</span>' : ''}
                    </div>
                    <div class="agent-prompt-actions">
                      ${!p.is_active ? `<button class="btn btn-sm btn-primary" onclick="AgentPage.activatePrompt(${p.id})">激活</button>` : ''}
                      <button class="btn btn-sm btn-secondary" onclick="AgentPage.editPrompt(${p.id})">编辑</button>
                      <button class="btn btn-sm" style="color:#dc2626;" onclick="AgentPage.deletePrompt(${p.id})">删除</button>
                    </div>
                  </div>
                `).join('')}
              </div>
              <button class="btn btn-sm btn-secondary" style="margin-top:var(--spacing-sm);" onclick="AgentPage.showPromptForm()">新建 Prompt</button>
              <div id="agent-prompt-form-area"></div>
            </div>
            <div class="agent-modal-section">
              <h4>调度配置</h4>
              <div class="agent-schedule-form">
                <label>运行间隔（分钟）</label>
                <input type="number" class="input" id="agent-schedule-interval" value="60" min="5" style="width:80px;">
                <button class="btn btn-sm btn-primary" onclick="AgentPage.saveSchedule()">保存</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  function showPromptForm(promptId) {
    const existing = promptId ? prompts.find(p => p.id === promptId) : null;
    const area = document.getElementById('agent-prompt-form-area');
    if (!area) return;
    area.innerHTML = `
      <div class="agent-prompt-form">
        <input type="text" class="input" id="prompt-form-name" placeholder="Prompt名称"
               value="${existing ? escapeHtml(existing.name) : ''}">
        <textarea class="input" id="prompt-form-content" placeholder="Prompt内容">${existing ? escapeHtml(existing.content) : ''}</textarea>
        <div style="display:flex;gap:var(--spacing-xs);">
          <button class="btn btn-sm btn-primary" onclick="AgentPage.savePrompt(${promptId || 'null'})">${existing ? '更新' : '创建'}</button>
          <button class="btn btn-sm btn-secondary" onclick="document.getElementById('agent-prompt-form-area').innerHTML=''">取消</button>
        </div>
      </div>
    `;
  }

  function editPrompt(id) {
    showPromptForm(id);
  }

  async function savePrompt(id) {
    const name = document.getElementById('prompt-form-name').value.trim();
    const content = document.getElementById('prompt-form-content').value.trim();
    if (!name || !content) { alert('请填写名称和内容'); return; }

    try {
      const url = id ? `/api/agent/prompts/${id}` : '/api/agent/prompts';
      const method = id ? 'PUT' : 'POST';
      const resp = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, content })
      });
      const data = await resp.json();
      if (data.success) {
        await loadPrompts();
        renderSettingsModal();
      } else {
        alert('保存失败: ' + (data.error || ''));
      }
    } catch (e) {
      alert('保存失败: ' + e.message);
    }
  }

  async function deletePrompt(id) {
    if (!confirm('确定删除此Prompt？')) return;
    try {
      const resp = await fetch(`/api/agent/prompts/${id}`, { method: 'DELETE' });
      const data = await resp.json();
      if (data.success) {
        await loadPrompts();
        renderSettingsModal();
      } else {
        alert('删除失败: ' + (data.error || ''));
      }
    } catch (e) {
      alert('删除失败: ' + e.message);
    }
  }

  async function activatePrompt(id) {
    try {
      const resp = await fetch(`/api/agent/prompts/${id}/activate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await resp.json();
      if (data.success) {
        await loadPrompts();
        renderSettingsModal();
      } else {
        alert('激活失败: ' + (data.error || ''));
      }
    } catch (e) {
      alert('激活失败: ' + e.message);
    }
  }

  async function saveSchedule() {
    const interval = document.getElementById('agent-schedule-interval').value;
    alert('调度间隔已设置为 ' + interval + ' 分钟');
  }

  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function renderMarkdown(text) {
    if (!text) return '';
    if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
      return DOMPurify.sanitize(marked.parse(text));
    }
    return escapeHtml(text).replace(/\n/g, '<br>');
  }

  return {
    render, init, manualRun, toggleSchedule,
    switchHistory, reviewArticle, preview,
    switchPreviewTab, closePreview,
    openSettings, closeSettings,
    showPromptForm, editPrompt, savePrompt,
    deletePrompt, activatePrompt, saveSchedule
  };
})();

if (typeof window !== 'undefined') {
  window.AgentPage = AgentPage;
}
