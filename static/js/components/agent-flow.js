/**
 * Agent动态流程可视化
 * 只显示已执行到的节点，支持展开查看详情和LLM I/O
 */
const AgentFlowVisualizer = (() => {

  const STAGE_META = {
    scan:     { label: '热点扫描', icon: '📡' },
    evaluate: { label: '价值评估', icon: '🔍' },
    collect:  { label: '内容采集', icon: '📥' },
    analyze:  { label: '深度分析', icon: '🧠' },
    plan:     { label: '创意策划', icon: '💡' },
    write:    { label: '推文生成', icon: '✍️' },
    check:    { label: '质量检查', icon: '👁️' },
    retry_scan:    { label: '扩大搜索', icon: '🔄' },
    retry_analyze: { label: '重新分析', icon: '🔄' },
    retry_write:   { label: '重新生成', icon: '🔄' },
  };

  const DECISION_STAGE_MAP = {
    'scan': 'scan',
    'evaluate': 'evaluate',
    'collect': 'collect',
    'analyze': 'analyze',
    'plan': 'plan',
    'write': 'write',
    'check': 'check',
    'optimize': 'check'
  };

  let expandedStage = null;

  function render(container, statusData) {
    if (!container) return;

    const stages = statusData.stages || {};
    const tasks = statusData.tasks || {};
    const nodes = statusData.nodes || {};
    const decisions = statusData.decisions || [];

    // 只显示有数据的节点（动态生成）
    const activeStages = [];
    const stageOrder = ['scan', 'evaluate', 'collect', 'analyze', 'plan', 'write', 'check'];

    for (const key of stageOrder) {
      const sd = stages[key] || {};
      const nd = nodes[key] || {};
      const status = sd.status || nd.status || 'pending';

      if (status !== 'pending' || statusData.running) {
        const total = sd.total_tasks || nd.count || 0;
        // completed: 优先stages数据，否则如果节点已完成则completed=total
        const completed = sd.completed_tasks != null ? sd.completed_tasks
          : (status === 'completed' ? total : 0);
        const failed = sd.failed_tasks || 0;

        // 收集该stage的tasks
        const stageTasks = [];
        if (typeof tasks === 'object') {
          for (const [tid, task] of Object.entries(tasks)) {
            if (task.stage === key) {
              stageTasks.push(task);
            }
          }
        }

        activeStages.push({
          key, status, total, completed, failed,
          tasks: stageTasks,
          meta: STAGE_META[key] || { label: key, icon: '⚙️' }
        });
      }

      // 如果当前节点还在pending且pipeline在运行，不显示后续节点
      if ((stages[key]?.status || nodes[key]?.status) === 'pending' && statusData.running) {
        break;
      }
    }

    // 检查是否有retry节点
    for (const key of Object.keys(stages)) {
      if (key.startsWith('retry_') && !activeStages.find(s => s.key === key)) {
        const sd = stages[key];
        activeStages.push({
          key,
          status: sd.status || 'running',
          total: sd.total_tasks || 0,
          completed: sd.completed_tasks || 0,
          failed: sd.failed_tasks || 0,
          tasks: [],
          meta: STAGE_META[key] || { label: key, icon: '🔄' }
        });
      }
    }

    if (activeStages.length === 0 && !statusData.running) {
      container.innerHTML = '<div style="color:#6b7280;text-align:center;padding:24px;">点击"手动运行"启动Agent</div>';
      return;
    }

    container.innerHTML = `
      <div class="dflow-timeline">
        ${activeStages.map((stage, i) => {
          const stageHtml = renderStageNode(stage, i, activeStages.length, tasks);
          // 找到该stage之后的决策节点
          const stageDecisions = decisions.filter(d => d.stage === stage.key);
          const decisionHtml = stageDecisions.map(d => renderDecisionNode(d)).join('');
          return stageHtml + decisionHtml;
        }).join('')}
      </div>
    `;
  }

  function renderStageNode(stage, index, total, allTasks) {
    const { key, status, total: taskTotal, completed, failed, tasks, meta } = stage;
    const isExpanded = expandedStage === key;
    const statusIcon = status === 'completed' ? '✅' : status === 'running' ? '⏳' : status === 'failed' ? '❌' : '⏸️';
    const statusClass = `dflow-node-${status}`;

    const connector = index < total - 1
      ? `<div class="dflow-connector ${status === 'completed' ? 'done' : status === 'running' ? 'active' : ''}"></div>`
      : '';

    // 任务详情
    let tasksHtml = '';
    if (isExpanded && tasks.length > 0) {
      tasksHtml = `<div class="dflow-tasks">
        ${tasks.map(t => renderTaskCard(t)).join('')}
      </div>`;
    } else if (isExpanded && taskTotal > 0) {
      tasksHtml = `<div class="dflow-tasks"><div style="color:#6b7280;padding:8px;">共${taskTotal}个任务</div></div>`;
    }

    const countText = taskTotal > 0 ? `${completed}/${taskTotal}${failed > 0 ? ` <span style="color:#ef4444;">${failed}失败</span>` : ''}` : '';

    return `
      <div class="dflow-step">
        <div class="dflow-node ${statusClass}" onclick="AgentFlowVisualizer.toggleStage('${key}')">
          <div class="dflow-node-header">
            <span class="dflow-icon">${meta.icon}</span>
            <span class="dflow-status-icon">${statusIcon}</span>
          </div>
          <div class="dflow-label">${meta.label}</div>
          ${countText ? `<div class="dflow-count">${countText}</div>` : ''}
        </div>
        ${tasksHtml}
        ${connector}
      </div>
    `;
  }

  function renderTaskCard(task) {
    const statusIcon = task.status === 'completed' ? '✅' : task.status === 'running' ? '⏳' : task.status === 'failed' ? '❌' : '⏸️';
    const duration = task.duration_ms ? `${(task.duration_ms / 1000).toFixed(1)}s` : (task.duration ? `${task.duration.toFixed(1)}s` : '');
    const llmCount = task.llm_calls || task.llm_call_ids?.length || 0;

    return `
      <div class="dflow-task ${task.status === 'failed' ? 'dflow-task-failed' : ''}">
        <div class="dflow-task-header">
          <span>${statusIcon}</span>
          <span class="dflow-task-name">${escapeHtml(task.input_summary || task.name || task.id || '')}</span>
          ${duration ? `<span class="dflow-task-duration">${duration}</span>` : ''}
        </div>
        ${task.output_summary ? `<div class="dflow-task-output">${escapeHtml(task.output_summary)}</div>` : ''}
        ${task.error ? `<div class="dflow-task-error">${escapeHtml(task.error)}</div>` : ''}
        ${llmCount > 0 ? `<div class="dflow-task-llm" onclick="event.stopPropagation();AgentFlowVisualizer.showLLMModal('${task.id || task.task_id}')">🤖 ${llmCount}次LLM调用</div>` : ''}
      </div>
    `;
  }

  function renderDecisionNode(decision) {
    const isPass = decision.type === 'pass' || !decision.action;
    const cls = isPass ? 'dflow-decision-pass' : 'dflow-decision-adjust';
    const icon = isPass ? '✓' : '⚡';
    const connector = `<div class="dflow-connector done"></div>`;

    return `
      ${connector}
      <div class="dflow-step">
        <div class="dflow-decision ${cls}" onclick="AgentFlowVisualizer.showDecisionDetail(${JSON.stringify(decision).replace(/"/g, '&quot;')})">
          <span class="dflow-decision-icon">${icon}</span>
        </div>
      </div>
    `;
  }

  function showDecisionDetail(decision) {
    const modal = document.createElement('div');
    modal.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.85);display:flex;align-items:center;justify-content:center;z-index:10000;';
    modal.innerHTML = `
      <div style="background:#1a1a1a;border-radius:8px;padding:24px;max-width:500px;width:90%;">
        <div style="display:flex;justify-content:space-between;margin-bottom:16px;">
          <h3 style="margin:0;">决策详情</h3>
          <button onclick="this.closest('[style*=fixed]').remove()" style="background:none;border:none;color:#888;font-size:24px;cursor:pointer;">&times;</button>
        </div>
        <div style="margin-bottom:12px;">
          <div style="color:#888;font-size:11px;">阶段</div>
          <div style="font-weight:600;">${decision.stage || ''}</div>
        </div>
        <div style="margin-bottom:12px;">
          <div style="color:#888;font-size:11px;">判断</div>
          <div>${decision.decision || ''}</div>
        </div>
        <div style="margin-bottom:12px;">
          <div style="color:#888;font-size:11px;">原因</div>
          <div style="color:#d1d5db;">${decision.reason || ''}</div>
        </div>
        ${decision.action ? `
        <div style="margin-bottom:12px;">
          <div style="color:#888;font-size:11px;">执行动作</div>
          <div style="color:#f59e0b;font-weight:600;">${decision.action}</div>
        </div>` : ''}
        <div style="color:#6b7280;font-size:11px;">${decision.timestamp || ''}</div>
      </div>
    `;
    document.body.appendChild(modal);
    modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
  }

  function toggleStage(key) {
    expandedStage = expandedStage === key ? null : key;
    const container = document.getElementById('agent-flow-container');
    if (container && window._lastAgentData) {
      render(container, window._lastAgentData);
    }
  }

  async function showLLMModal(taskId) {
    try {
      const resp = await fetch(`/api/agent/llm-logs/${taskId}`);
      const data = await resp.json();
      const logs = data.success ? (data.data || []) : [];

      const modal = document.createElement('div');
      modal.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.85);display:flex;align-items:center;justify-content:center;z-index:10000;';

      if (logs.length === 0) {
        modal.innerHTML = `
          <div style="background:#1a1a1a;border-radius:8px;padding:24px;max-width:600px;width:90%;">
            <div style="display:flex;justify-content:space-between;margin-bottom:16px;">
              <h3 style="margin:0;">LLM调用日志</h3>
              <button onclick="this.closest('[style*=fixed]').remove()" style="background:none;border:none;color:#888;font-size:24px;cursor:pointer;">&times;</button>
            </div>
            <div style="color:#6b7280;text-align:center;padding:24px;">暂无LLM调用记录</div>
          </div>`;
      } else {
        modal.innerHTML = `
          <div style="background:#1a1a1a;border-radius:8px;padding:24px;max-width:800px;width:90%;max-height:80vh;overflow-y:auto;">
            <div style="display:flex;justify-content:space-between;margin-bottom:16px;">
              <h3 style="margin:0;">LLM调用日志 (${logs.length}次)</h3>
              <button onclick="this.closest('[style*=fixed]').remove()" style="background:none;border:none;color:#888;font-size:24px;cursor:pointer;">&times;</button>
            </div>
            ${logs.map((log, i) => `
              <div style="border:1px solid #333;border-radius:6px;padding:12px;margin-bottom:12px;">
                <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                  <span style="color:#10b981;font-weight:600;">${escapeHtml(log.model || 'unknown')}</span>
                  <span style="color:#6b7280;font-size:12px;">${log.duration_ms ? log.duration_ms + 'ms' : ''} | ${log.total_tokens || 0} tokens</span>
                </div>
                <div style="margin-bottom:8px;">
                  <div style="color:#888;font-size:11px;margin-bottom:4px;">PROMPT</div>
                  <div style="background:#111;padding:8px;border-radius:4px;font-size:12px;max-height:150px;overflow-y:auto;white-space:pre-wrap;word-break:break-word;">${escapeHtml((log.prompt || '').substring(0, 500))}${(log.prompt || '').length > 500 ? '...' : ''}</div>
                </div>
                <div>
                  <div style="color:#888;font-size:11px;margin-bottom:4px;">RESPONSE</div>
                  <div style="background:#111;padding:8px;border-radius:4px;font-size:12px;max-height:150px;overflow-y:auto;white-space:pre-wrap;word-break:break-word;">${escapeHtml((log.response || '').substring(0, 500))}${(log.response || '').length > 500 ? '...' : ''}</div>
                </div>
              </div>
            `).join('')}
          </div>`;
      }

      document.body.appendChild(modal);
      modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
    } catch (e) {
      alert('加载LLM日志失败: ' + e.message);
    }
  }

  function renderStatsSummary(container, statusData) {
    if (!container) return;
    const stages = statusData.stages || {};
    const nodes = statusData.nodes || {};
    const tasks = statusData.tasks || {};
    const llmLogs = statusData.llm_logs || {};
    const summary = statusData.summary || {};

    const totalTasks = summary.total_tasks || Object.keys(tasks).length || 0;
    const completedTasks = summary.completed || 0;
    const failedTasks = summary.failed || 0;
    const llmCalls = summary.total_llm_calls || (Array.isArray(llmLogs) ? llmLogs.length : Object.keys(llmLogs).length) || 0;
    const totalTokens = summary.total_tokens || 0;

    // 从nodes获取计数
    const scanCount = nodes.scan?.count || stages.scan?.total_tasks || 0;
    const evalCount = nodes.evaluate?.count || stages.evaluate?.total_tasks || 0;
    const writeCount = nodes.write?.count || stages.write?.completed_tasks || statusData.articles_generated || 0;

    container.innerHTML = `
      <span>扫描 <strong>${scanCount}</strong> 条</span>
      <span>筛选 <strong>${evalCount}</strong> 条</span>
      <span>生成 <strong>${writeCount}</strong> 篇</span>
      ${llmCalls > 0 ? `<span>LLM <strong>${llmCalls}</strong> 次</span>` : ''}
      ${totalTokens > 0 ? `<span>Tokens <strong>${totalTokens}</strong></span>` : ''}
    `;
  }

  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  return { render, renderStatsSummary, toggleStage, showLLMModal, showDecisionDetail };
})();

if (typeof window !== 'undefined') {
  window.AgentFlowVisualizer = AgentFlowVisualizer;
}
