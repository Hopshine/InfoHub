const AgentPage = (() => {
  let statusTimer = null;
  let currentHistoryTab = 'approved';
  let articles = [];
  let historyArticles = [];
  let prompts = [];
  let scheduleRunning = false;

  const PIPELINE_STEPS = [
    { key: 'scan', label: '扫描', icon: '📡' },
    { key: 'collect', label: '采集', icon: '📥' },
    { key: 'analyze', label: '分析评估', icon: '🧠' },
    { key: 'select', label: '精选', icon: '🎯' },
    { key: 'write', label: '生成', icon: '✍️' }
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
          <div id="agent-dag-container" class="agent-dag-container"></div>
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
              <button class="agent-tab active" onclick="AgentPage.switchHistory('approved')">已通过</button>
              <button class="agent-tab" onclick="AgentPage.switchHistory('published')">已发布</button>
              <button class="agent-tab" onclick="AgentPage.switchHistory('rejected')">已拒绝</button>
              <button class="agent-tab" onclick="AgentPage.switchHistory('all')">全部</button>
            </div>
          </div>
          <div class="agent-history-list" id="agent-history-list"></div>
        </div>
      </div>

      <div id="agent-detail-panel" class="agent-detail-panel"></div>

      <div id="agent-settings-modal" style="display:none;"></div>
      <div id="agent-preview-modal" style="display:none;"></div>
    `;
  }

  async function init() {
    await Promise.all([loadStatus(), loadDrafts(), loadHistory(), loadScheduleStatus()]);
    if (typeof AgentDetailPanel !== 'undefined') {
      AgentDetailPanel.init();
    }
  }

  function startPolling() {
    stopPolling();
    statusTimer = setInterval(async () => {
      await loadStatus();
    }, 1500); // 1.5秒轮询一次，更及时
  }

  function stopPolling() {
    if (statusTimer) {
      clearInterval(statusTimer);
      statusTimer = null;
    }
  }

  async function loadStatus() {
    try {
      const resp = await fetch('/api/agent/status/detailed');
      const data = await resp.json();
      if (data.success) {
        window._lastAgentData = data.data;
        renderStatus(data.data);

        // 更新运行按钮状态
        const btn = document.getElementById('agent-run-btn');
        if (btn) {
          btn.disabled = data.data.running;
          btn.textContent = data.data.running ? '运行中...' : '手动运行';
        }

        // 统计摘要
        const statsSummary = document.getElementById('agent-stats-summary');
        if (statsSummary && typeof AgentFlowVisualizer !== 'undefined') {
          AgentFlowVisualizer.renderStatsSummary(statsSummary, data.data);
        }

        // DAG可视化 - 有batch_id时渲染workflow DAG
        const dagContainer = document.getElementById('agent-dag-container');
        if (dagContainer && typeof AgentDAGVisualizer !== 'undefined') {
          if (data.data.batch_id) {
            try {
              const workflowResp = await fetch(`/api/agent/workflows/${data.data.batch_id}`);
              const workflowData = await workflowResp.json();
              if (workflowData.success) {
                AgentDAGVisualizer.render(dagContainer, workflowData.data);
              }
            } catch (e) {
              console.error('加载workflow数据失败:', e);
            }
          } else if (data.data.running) {
            // Agent刚启动，还没有batch_id，显示加载中
            if (!dagContainer.querySelector('svg')) {
              dagContainer.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:200px;color:#9ca3af;">Agent运行中，等待数据...</div>';
            }
          }
        }

        if (data.data.running) {
          if (!statusTimer) startPolling();
          await loadDrafts();
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

    if (lastRun) {
      lastRun.textContent = data.started_at
        ? new Date(data.started_at).toLocaleString('zh-CN')
        : '从未运行';
    }
    if (curStatus) {
      curStatus.textContent = data.running ? '运行中' : '空闲';
      curStatus.style.color = data.running ? 'var(--color-primary)' : '';
    }
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
      const scoreText = a.quality_score != null ? Math.round(a.quality_score * 100) : '--';
      return `
        <div class="agent-article-card">
          <div class="agent-article-title">${escapeHtml(a.title)}</div>
          <div class="agent-article-meta">
            ${a.platform ? `<span>${escapeHtml(a.platform)}</span>` : ''}
            <span class="agent-score ${scoreClass}" onclick="AgentPage.showScoreDetail(${a.id})" style="cursor:pointer;" title="点击查看评分详情">${scoreText}分</span>
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
      let badge = '';
      let actions = '';
      let publishInfo = '';

      if (a.status === 'published') {
        const platformMap = {
          'wechat': '微信公众号',
          'xiaohongshu': '小红书',
          'zhihu': '知乎',
          'weibo': '微博'
        };
        const platformName = platformMap[a.publish_platform] || a.publish_platform || '未知平台';
        badge = `<span class="badge badge-published">已发布 · ${platformName}</span>`;

        publishInfo = a.publish_url ? `
          <div style="margin-top:4px;">
            <a href="${a.publish_url}" target="_blank" style="color:var(--color-primary);font-size:12px;text-decoration:none;">
              查看发布链接 →
            </a>
          </div>
        ` : '';

        actions = `
          <button class="btn btn-sm btn-secondary" onclick="AgentPage.preview(${a.id})">查看</button>
          ${a.publish_url ? `<button class="btn btn-sm" onclick="window.open('${a.publish_url}', '_blank')">访问</button>` : ''}
        `;
      } else if (a.status === 'approved') {
        badge = '<span class="badge badge-success">已通过</span>';
        actions = `
          <button class="btn btn-sm btn-secondary" onclick="AgentPage.preview(${a.id})">预览</button>
          <button class="btn btn-sm btn-primary" onclick="AgentPage.publishArticle(${a.id})">发布</button>
          <button class="btn btn-sm" onclick="AgentPage.revertToDraft(${a.id})">撤回</button>
        `;
      } else if (a.status === 'rejected') {
        badge = '<span class="badge badge-rejected">已拒绝</span>';
        actions = `
          <button class="btn btn-sm btn-secondary" onclick="AgentPage.preview(${a.id})">查看</button>
          <button class="btn btn-sm" onclick="AgentPage.revertToDraft(${a.id})">重新审核</button>
        `;
      }

      const time = a.updated_at ? new Date(a.updated_at).toLocaleString('zh-CN') :
                   (a.published_at ? new Date(a.published_at).toLocaleString('zh-CN') : '');
      return `
        <div class="agent-history-item">
          <div style="flex:1;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
              <span style="font-weight:500;">${escapeHtml(a.title)}</span>
              ${badge}
            </div>
            <span style="color:var(--color-gray-500);font-size:var(--font-size-xs);">${time}</span>
            ${publishInfo}
          </div>
          <div style="display:flex;gap:8px;">
            ${actions}
          </div>
        </div>
      `;
    }).join('');
  }

  async function switchHistory(tab) {
    currentHistoryTab = tab;
    document.querySelectorAll('.agent-tabs .agent-tab').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    await loadHistory();
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
        // 立即开始轮询
        startPolling();
        // 延迟500ms再加载状态，让后端有时间初始化
        setTimeout(() => loadStatus(), 500);
      } else {
        alert('运行失败: ' + (data.error || '未知错误'));
        if (btn) { btn.disabled = false; btn.textContent = '手动运行'; }
      }
    } catch (e) {
      alert('运行失败: ' + e.message);
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
      // 转换action为后端期望的decision格式
      const decision = action === 'approved' ? 'approve' : action === 'rejected' ? 'reject' : action;
      const resp = await fetch(`/api/agent/articles/${id}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision })
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

  async function publishArticle(id) {
    // 显示发布平台选择弹窗
    const article = historyArticles.find(a => a.id === id);
    if (!article) return;

    const modal = document.createElement('div');
    modal.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.8);display:flex;align-items:center;justify-content:center;z-index:10000;';
    modal.innerHTML = `
      <div style="background:#1a1a1a;border-radius:8px;padding:24px;max-width:500px;width:90%;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
          <h3 style="margin:0;">选择发布平台</h3>
          <button onclick="this.closest('[style*=fixed]').remove()" style="background:none;border:none;color:#888;font-size:24px;cursor:pointer;">&times;</button>
        </div>
        <div style="margin-bottom:16px;">
          <div style="font-weight:500;margin-bottom:8px;">文章标题</div>
          <div style="color:#888;font-size:14px;">${escapeHtml(article.title)}</div>
        </div>
        <div style="margin-bottom:24px;">
          <div style="font-weight:500;margin-bottom:12px;">发布到</div>
          <div style="display:grid;gap:12px;">
            <label style="display:flex;align-items:center;padding:12px;border:1px solid #333;border-radius:6px;cursor:pointer;">
              <input type="radio" name="platform" value="wechat" checked style="margin-right:8px;">
              <span>微信公众号</span>
            </label>
            <label style="display:flex;align-items:center;padding:12px;border:1px solid #333;border-radius:6px;cursor:pointer;">
              <input type="radio" name="platform" value="xiaohongshu" style="margin-right:8px;">
              <span>小红书</span>
            </label>
            <label style="display:flex;align-items:center;padding:12px;border:1px solid #333;border-radius:6px;cursor:pointer;">
              <input type="radio" name="platform" value="zhihu" style="margin-right:8px;">
              <span>知乎</span>
            </label>
            <label style="display:flex;align-items:center;padding:12px;border:1px solid #333;border-radius:6px;cursor:pointer;">
              <input type="radio" name="platform" value="weibo" style="margin-right:8px;">
              <span>微博</span>
            </label>
          </div>
        </div>
        <div style="display:flex;gap:12px;justify-content:flex-end;">
          <button class="btn btn-secondary" onclick="this.closest('[style*=fixed]').remove()">取消</button>
          <button class="btn btn-primary" onclick="AgentPage.confirmPublish(${id})">确认发布</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
  }

  async function confirmPublish(id) {
    const modal = document.querySelector('[style*="z-index:10000"]');
    const platform = modal.querySelector('input[name="platform"]:checked')?.value;
    if (!platform) {
      alert('请选择发布平台');
      return;
    }

    try {
      const resp = await fetch(`/api/agent/articles/${id}/publish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform })
      });
      const data = await resp.json();
      if (data.success) {
        modal.remove();
        alert('发布成功！');
        await loadHistory();
      } else {
        alert('发布失败: ' + (data.error || ''));
      }
    } catch (e) {
      alert('发布失败: ' + e.message);
    }
  }

  async function revertToDraft(id) {
    if (!confirm('确认撤回到待审核状态？')) return;
    try {
      const resp = await fetch(`/api/agent/articles/${id}/revert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
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

  async function showScoreDetail(articleId) {
    const article = articles.find(a => a.id === articleId);
    if (!article || !article.quality_detail) {
      alert('无评分详情');
      return;
    }

    try {
      const detail = typeof article.quality_detail === 'string'
        ? JSON.parse(article.quality_detail)
        : article.quality_detail;

      const detailsHtml = detail.details.map(d => `
        <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #333;">
          <span>${d.item}</span>
          <span style="color:${d.score >= 15 ? '#10b981' : d.score >= 8 ? '#f59e0b' : '#ef4444'};">${d.score}分</span>
        </div>
        <div style="color:#888;font-size:12px;padding:4px 0 8px 0;">${d.reason}</div>
      `).join('');

      const metricsHtml = `
        <div style="margin-top:16px;padding-top:16px;border-top:1px solid #333;">
          <div style="font-weight:600;margin-bottom:8px;">指标统计</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:13px;">
            <div>标题长度: ${detail.metrics.title_length}字</div>
            <div>内容长度: ${detail.metrics.content_length}字</div>
            <div>段落数: ${detail.metrics.paragraph_count}段</div>
            <div>关键词数: ${detail.metrics.keyword_count}个</div>
            <div>摘要长度: ${detail.metrics.summary_length}字</div>
            <div>句子数: ${detail.metrics.sentence_count || 0}句</div>
          </div>
        </div>
      `;

      const modal = document.createElement('div');
      modal.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.8);display:flex;align-items:center;justify-content:center;z-index:10000;';
      modal.innerHTML = `
        <div style="background:#1a1a1a;border-radius:8px;padding:24px;max-width:600px;width:90%;max-height:80vh;overflow-y:auto;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
            <h3 style="margin:0;">质量评分详情</h3>
            <button onclick="this.closest('[style*=fixed]').remove()" style="background:none;border:none;color:#888;font-size:24px;cursor:pointer;">&times;</button>
          </div>
          <div style="font-size:32px;font-weight:700;color:#10b981;text-align:center;margin:16px 0;">
            ${Math.round(detail.final_score * 100)}分
          </div>
          <div style="text-align:center;color:#888;margin-bottom:24px;">总分: ${detail.total_score}/100</div>
          ${detailsHtml}
          ${metricsHtml}
        </div>
      `;
      document.body.appendChild(modal);
      modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
    } catch (e) {
      console.error('解析评分详情失败:', e);
      alert('评分详情格式错误');
    }
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
    deletePrompt, activatePrompt, saveSchedule,
    showScoreDetail, publishArticle, revertToDraft,
    confirmPublish
  };
})();

if (typeof window !== 'undefined') {
  window.AgentPage = AgentPage;
}
