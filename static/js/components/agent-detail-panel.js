const AgentDetailPanel = (() => {
  let currentWorkflowId = null;

  function init() {
    window.addEventListener('dag-node-click', (e) => {
      showWorkflowDetail(e.detail.nodeId);
    });
  }

  async function showWorkflowDetail(workflowId) {
    currentWorkflowId = workflowId;
    const panel = document.getElementById('agent-detail-panel');
    if (!panel) return;

    const resp = await fetch(`/api/agent/workflow/${workflowId}`);
    const data = await resp.json();

    if (data.success) {
      renderDetail(panel, data.data);
      panel.classList.add('open');
    }
  }

  function renderDetail(panel, workflow) {
    panel.innerHTML = `
      <div class="detail-header">
        <h3>${workflow.topic_title}</h3>
        <button onclick="AgentDetailPanel.close()">&times;</button>
      </div>

      <div class="detail-section">
        <h4>基本信息</h4>
        <div class="detail-item">
          <span>平台：</span><strong>${workflow.platform}</strong>
        </div>
        <div class="detail-item">
          <span>当前阶段：</span><strong>${workflow.current_stage}</strong>
        </div>
        <div class="detail-item">
          <span>状态：</span><strong>${workflow.status}</strong>
        </div>
        <div class="detail-item">
          <span>重试次数：</span><strong>${workflow.retry_count}</strong>
        </div>
      </div>

      <div class="detail-section">
        <h4>阶段耗时</h4>
        ${renderStageTimeline(workflow.stages)}
      </div>

      <div class="detail-section">
        <h4>决策记录</h4>
        ${renderDecisions(workflow.decisions)}
      </div>

      ${workflow.article_id ? `
      <div class="detail-section">
        <h4>生成文章</h4>
        <div class="detail-item">
          <span>质量评分：</span><strong>${(workflow.quality_score * 100).toFixed(0)}分</strong>
        </div>
        <button onclick="AgentDetailPanel.previewArticle(${workflow.article_id})">预览文章</button>
      </div>` : ''}
    `;
  }

  function renderStageTimeline(stages) {
    if (!stages) return '<div>暂无数据</div>';
    return Object.entries(stages).map(([stage, info]) => `
      <div class="stage-timeline-item">
        <span class="stage-name">${stage}</span>
        <span class="stage-status ${info.status}">${info.status}</span>
        ${info.duration_ms ? `<span class="stage-duration">${(info.duration_ms / 1000).toFixed(1)}s</span>` : ''}
      </div>
    `).join('');
  }

  function renderDecisions(decisions) {
    if (!decisions || decisions.length === 0) return '<div>暂无决策</div>';
    return decisions.map(d => `
      <div class="decision-item">
        <div class="decision-header">
          <span class="decision-stage">${d.stage}</span>
          <span class="decision-type ${d.type}">${d.type === 'pass' ? '✓' : '⚡'}</span>
        </div>
        <div class="decision-reason">${d.reason}</div>
        ${d.action ? `<div class="decision-action">动作：${d.action}</div>` : ''}
      </div>
    `).join('');
  }

  function close() {
    const panel = document.getElementById('agent-detail-panel');
    if (panel) panel.classList.remove('open');
  }

  async function previewArticle(articleId) {
    if (window.AgentPage && window.AgentPage.preview) {
      window.AgentPage.preview(articleId);
    }
  }

  return {init, showWorkflowDetail, close, previewArticle};
})();

window.AgentDetailPanel = AgentDetailPanel;
