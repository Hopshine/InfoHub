const AgentDetailPanel = (() => {
  let currentWorkflowId = null;

  function init() {
    window.addEventListener('dag-node-click', (e) => {
      showWorkflowDetail(e.detail.nodeId, e.detail.stage);
    });
  }

  async function showWorkflowDetail(workflowId, stage) {
    currentWorkflowId = workflowId;
    const panel = document.getElementById('agent-detail-panel');
    console.log('[DetailPanel] Panel element:', panel, 'stage:', stage);

    if (!panel) {
      console.error('Detail panel element not found');
      return;
    }

    // 特殊处理：scan、collect、analyze、select节点
    if (workflowId === 'scan' || workflowId === 'collect' || workflowId === 'analyze' || workflowId === 'select') {
      try {
        const resp = await fetch(`/api/agent/status/detailed`);
        const data = await resp.json();
        if (data.success) {
          renderSystemNodeDetail(panel, workflowId, data.data);
          panel.classList.add('open');
        }
      } catch (err) {
        console.error('Failed to load system node detail:', err);
      }
      return;
    }

    // workflow节点
    try {
      const resp = await fetch(`/api/agent/workflow/${workflowId}`);
      const data = await resp.json();

      console.log('Workflow detail response:', data);

      if (data.success) {
        console.log('[DetailPanel] Rendering detail for stage:', stage);
        renderDetail(panel, data.data, stage);
        console.log('[DetailPanel] Adding open class...');
        panel.classList.add('open');
        console.log('[DetailPanel] Panel classes:', panel.className);
      } else {
        panel.innerHTML = `
          <div class="detail-header">
            <h3>加载失败</h3>
            <button onclick="AgentDetailPanel.close()">&times;</button>
          </div>
          <div class="detail-section">
            <p style="color: #ef4444;">${data.error || '未知错误'}</p>
          </div>
        `;
        panel.classList.add('open');
      }
    } catch (err) {
      console.error('Failed to load workflow detail:', err);
      panel.innerHTML = `
        <div class="detail-header">
          <h3>加载失败</h3>
          <button onclick="AgentDetailPanel.close()">&times;</button>
        </div>
        <div class="detail-section">
          <p style="color: #ef4444;">网络错误: ${err.message}</p>
        </div>
      `;
      panel.classList.add('open');
    }
  }

  function renderSystemNodeDetail(panel, nodeType, agentData) {
    const stages = agentData.stages || {};
    const tasks = agentData.tasks || {};
    const llmLogs = agentData.llm_logs || [];

    if (nodeType === 'scan') {
      const scanStage = stages['scan'] || {};
      const scanTasks = Object.values(tasks).filter(t => t.stage === 'scan');
      const scanLogs = llmLogs.filter(log => log.stage === 'scan');

      let platformResults = '';
      scanTasks.forEach(task => {
        const platform = task.task_name || task.task_key || '未知平台';
        const isDone = task.status === 'completed';
        const isFailed = task.status === 'failed';
        const isRunning = !isDone && !isFailed;
        const statusIcon = isDone ? '✓' : isFailed ? '✗' : '⏳';
        const borderColor = isDone ? '#10b981' : isFailed ? '#ef4444' : '#f59e0b';
        const statusColor = isDone ? '#10b981' : isFailed ? '#ef4444' : '#f59e0b';

        let output = {};
        try {
          output = task.output_data ? JSON.parse(task.output_data) : {};
        } catch (e) {}

        const count = output.count || 0;
        const saved = output.saved || 0;
        const platformName = output.platform || platform;

        platformResults += `
          <div style="padding: 8px; border-left: 3px solid ${borderColor}; margin-bottom: 8px; background: #1f2937;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <strong style="color: #f3f4f6;">${platformName}</strong>
              <span style="color: ${statusColor};">${statusIcon} ${isDone ? `采集${count}条 / 新增${saved}条` : isFailed ? '失败' : '扫描中...'}</span>
            </div>
            ${task.error_message || task.error ? `<div style="color: #ef4444; font-size: 12px; margin-top: 4px;">${task.error_message || task.error}</div>` : ''}
          </div>
        `;
      });

      panel.innerHTML = `
        <div class="detail-header">
          <h3>扫描热点 <span style="color: #10b981; font-size: 14px;">[4个平台]</span></h3>
          <button onclick="AgentDetailPanel.close()">&times;</button>
        </div>

        <div class="detail-section">
          <h4>扫描结果</h4>
          <div class="detail-item">
            <span>总计：</span><strong>${scanStage.total || 0}条热点</strong>
          </div>
          <div class="detail-item">
            <span>状态：</span><strong>${scanStage.status || '未知'}</strong>
          </div>
        </div>

        <div class="detail-section">
          <h4>平台详情</h4>
          ${platformResults || '<p style="color: #9ca3af;">暂无数据</p>'}
        </div>

        ${scanLogs.length > 0 ? `
        <div class="detail-section">
          <h4>LLM调用日志 (${scanLogs.length}条)</h4>
          ${renderLLMLogs(scanLogs)}
        </div>` : ''}
      `;
    } else if (nodeType === 'collect') {
      const collectStage = stages['collect'] || {};
      const collectTasks = Object.values(tasks).filter(t => t.stage === 'collect');
      const collectLogs = llmLogs.filter(log => log.stage === 'collect');

      let passCount = 0, failCount = 0, pendingCount = 0;
      let topicList = '';

      collectTasks.forEach((task, idx) => {
        const title = task.task_name || '未知话题';
        let output = {};
        let hasOutput = false;
        try {
          if (task.output_data) { output = JSON.parse(task.output_data); hasOutput = true; }
        } catch (e) {}

        let selected = false, statusText = '', statusColor = '', borderColor = '';
        if (!hasOutput || task.status === 'running') {
          pendingCount++;
          statusText = '⏳ 处理中'; statusColor = '#f59e0b'; borderColor = '#f59e0b';
        } else {
          selected = output.selected === true;
          if (selected) { passCount++; statusText = '✓ 通过'; statusColor = '#10b981'; borderColor = '#10b981'; }
          else { failCount++; statusText = '✗ 拒绝'; statusColor = '#ef4444'; borderColor = '#ef4444'; }
        }

        let scoreDetails = '';
        if (output.scores) {
          scoreDetails = `
            <div style="margin-top: 8px; padding: 10px; background: #1f2937; border-radius: 6px; border: 1px solid #374151;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <div>
                  <span style="color: #f3f4f6; font-weight: 600; font-size: 14px;">总分: ${output.total_score || 0}/100</span>
                  <span style="margin-left: 8px; padding: 2px 8px; background: ${output.grade === 'S' ? '#8b5cf6' : output.grade === 'A' ? '#3b82f6' : output.grade === 'B' ? '#10b981' : '#6b7280'}; color: white; border-radius: 4px; font-size: 12px; font-weight: 600;">${output.grade || 'C'}级</span>
                </div>
                <span style="color: ${statusColor}; font-weight: 600;">${statusText}</span>
              </div>
              ${output.summary ? `<div style="color: #d1d5db; font-size: 12px; margin-bottom: 8px; padding: 6px; background: #111827; border-radius: 4px; border-left: 3px solid #3b82f6;">${escapeHtml(output.summary)}</div>` : ''}
              <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; font-size: 11px;">
                ${Object.entries(output.scores).map(([key, val]) => `
                  <div style="padding: 6px; background: #111827; border-radius: 4px; border-left: 2px solid #60a5fa;">
                    <div style="color: #60a5fa; font-weight: 600; margin-bottom: 2px;">${key}: ${val.score}分</div>
                    <div style="color: #9ca3af; font-size: 10px;">${val.reason}</div>
                  </div>
                `).join('')}
              </div>
            </div>`;
        } else if (!hasOutput) {
          scoreDetails = `<div style="color: #f59e0b; font-size: 12px; margin-top: 6px; padding: 6px; background: #1f2937; border-radius: 4px;">⏳ 采集评估中...</div>`;
        }

        topicList += `
          <div style="padding: 10px; border-left: 3px solid ${borderColor}; margin-bottom: 8px; background: linear-gradient(135deg, #111827 0%, #1f2937 100%); border-radius: 6px;">
            <div style="color: #f3f4f6; font-weight: 500; font-size: 13px; margin-bottom: 4px;">
              <span style="color: #9ca3af; margin-right: 6px;">${idx + 1}.</span>${escapeHtml(title)}
            </div>
            ${scoreDetails}
          </div>`;
      });

      const total = collectTasks.length;
      const passRate = total > 0 ? Math.round((passCount / total) * 100) : 0;

      panel.innerHTML = `
        <div class="detail-header" style="background: linear-gradient(135deg, #1f2937 0%, #111827 100%); border-bottom: 2px solid #374151;">
          <h3 style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 20px;">📥</span> 采集+评估
            <span style="color: #10b981; font-size: 14px; font-weight: 500;">[${total}个话题]</span>
          </h3>
          <button onclick="AgentDetailPanel.close()" style="background: #374151; color: #f3f4f6; border: none; border-radius: 6px; width: 32px; height: 32px; cursor: pointer; font-size: 20px; line-height: 1;">&times;</button>
        </div>
        <div style="padding: 12px 16px; background: linear-gradient(135deg, #1f2937 0%, #111827 100%); border-bottom: 1px solid #374151;">
          <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 10px;">
            <div style="background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%); padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #3b82f6;">
              <div style="color: #93c5fd; font-size: 11px; margin-bottom: 2px;">话题总数</div>
              <div style="color: #fff; font-size: 22px; font-weight: 700;">${total}</div>
            </div>
            <div style="background: linear-gradient(135deg, #065f46 0%, #047857 100%); padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #10b981;">
              <div style="color: #6ee7b7; font-size: 11px; margin-bottom: 2px;">✓ 通过</div>
              <div style="color: #fff; font-size: 22px; font-weight: 700;">${passCount}</div>
            </div>
            <div style="background: linear-gradient(135deg, #991b1b 0%, #b91c1c 100%); padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #ef4444;">
              <div style="color: #fca5a5; font-size: 11px; margin-bottom: 2px;">✗ 拒绝</div>
              <div style="color: #fff; font-size: 22px; font-weight: 700;">${failCount}</div>
            </div>
            <div style="background: linear-gradient(135deg, #92400e 0%, #b45309 100%); padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #f59e0b;">
              <div style="color: #fcd34d; font-size: 11px; margin-bottom: 2px;">⏳ 处理中</div>
              <div style="color: #fff; font-size: 22px; font-weight: 700;">${pendingCount}</div>
            </div>
          </div>
          <div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 11px;">
              <span style="color: #9ca3af;">通过率</span>
              <span style="color: #10b981; font-weight: 600;">${passRate}%</span>
            </div>
            <div style="background: #374151; height: 6px; border-radius: 3px; overflow: hidden;">
              <div style="background: linear-gradient(90deg, #10b981 0%, #059669 100%); height: 100%; width: ${passRate}%; transition: width 0.3s;"></div>
            </div>
          </div>
        </div>
        <div style="padding: 8px 16px 0;">
          <div style="margin-bottom: 8px; color: #f3f4f6; font-size: 13px; font-weight: 600;">📋 话题列表</div>
          <div style="overflow-y: auto; max-height: calc(100vh - 320px);">
            ${topicList || '<p style="color: #9ca3af; text-align: center; padding: 20px;">暂无数据</p>'}
          </div>
        </div>
        ${collectLogs.length > 0 ? `<div class="detail-section"><h4>LLM调用日志 (${collectLogs.length}条)</h4>${renderLLMLogs(collectLogs)}</div>` : ''}
      `;
    } else if (nodeType === 'analyze') {
      const analyzeStage = stages['analyze'] || {};
      panel.innerHTML = `
        <div class="detail-header">
          <h3>🧠 分析评估</h3>
          <button onclick="AgentDetailPanel.close()">&times;</button>
        </div>
        <div class="detail-section">
          <div class="detail-item"><span>总计：</span><strong>${analyzeStage.total || 0}条</strong></div>
          <div class="detail-item"><span>通过：</span><strong style="color:#10b981">${analyzeStage.completed || 0}条</strong></div>
          <div class="detail-item"><span>状态：</span><strong>${analyzeStage.status || '未知'}</strong></div>
        </div>`;
    } else if (nodeType === 'select') {
      const selectStage = stages['select'] || {};
      panel.innerHTML = `
        <div class="detail-header">
          <h3>🎯 精选话题</h3>
          <button onclick="AgentDetailPanel.close()">&times;</button>
        </div>
        <div class="detail-section">
          <div class="detail-item"><span>候选：</span><strong>${selectStage.total || 0}条</strong></div>
          <div class="detail-item"><span>精选：</span><strong style="color:#10b981">${selectStage.completed || 0}条</strong></div>
          <p style="color:#9ca3af; font-size:13px; margin-top:8px;">按评估总分排序，取Top 10进入写作阶段。</p>
        </div>`;
    }
  }

  function renderDetail(panel, workflow, stage) {
    const title = workflow.topic_title || '未知话题';
    const platform = workflow.platform || '未知';

    // 阶段中文映射
    const stageNameMap = {
      'collecting': '采集',
      'analyzing': '分析',
      'planning': '策划',
      'writing': '生成',
      'checking': '检查',
      'completed': '完成'
    };
    const stageName = stageNameMap[stage] || stage || '全部';

    // 根据stage过滤LLM日志
    let filteredLogs = workflow.llm_logs || [];
    if (stage && stage !== 'completed') {
      filteredLogs = filteredLogs.filter(log => log.stage === stage);
    }

    // 根据stage显示对应的输入输出
    let stageContent = '';

    if (stage === 'collecting') {
      stageContent = `
        <div class="detail-section">
          <h4>采集阶段</h4>
          <div class="detail-item">
            <span>输入：</span><strong>话题"${escapeHtml(title)}"</strong>
          </div>
          ${workflow.collect_result ? `
          <div class="detail-item">
            <span>输出：</span>
            <details open>
              <summary>采集结果</summary>
              <pre>${escapeHtml(JSON.stringify(workflow.collect_result, null, 2))}</pre>
            </details>
          </div>` : '<p style="color: #9ca3af;">暂无采集结果</p>'}
        </div>
      `;
    } else if (stage === 'analyzing') {
      const collectResult = workflow.collect_result || {};
      const analysisResult = workflow.analysis_result || {};

      stageContent = `
        <div class="detail-section">
          <h4>分析阶段</h4>
          ${Object.keys(collectResult).length > 0 ? `
          <div class="detail-item">
            <span>输入：</span>
            <details>
              <summary>采集内容 (${(collectResult.content || '').length}字)</summary>
              <div style="padding: 12px; background: #1f2937; border-radius: 6px; max-height: 200px; overflow-y: auto;">
                <div style="color: #d1d5db; font-size: 13px; line-height: 1.6; white-space: pre-wrap;">${escapeHtml((collectResult.content || '').substring(0, 1000))}${(collectResult.content || '').length > 1000 ? '...' : ''}</div>
              </div>
            </details>
          </div>` : ''}
          ${Object.keys(analysisResult).length > 0 ? `
          <div class="detail-item">
            <span>输出：</span>
            <details open>
              <summary>分析结果</summary>
              <div style="padding: 12px; background: #1f2937; border-radius: 6px;">
                ${analysisResult.summary ? `
                <div style="margin-bottom: 12px;">
                  <strong style="color: #10b981; display: block; margin-bottom: 6px;">摘要：</strong>
                  <div style="color: #d1d5db; font-size: 13px; line-height: 1.6;">${escapeHtml(analysisResult.summary)}</div>
                </div>` : ''}
                ${analysisResult.keywords ? `
                <div style="margin-bottom: 12px;">
                  <strong style="color: #10b981; display: block; margin-bottom: 6px;">关键词：</strong>
                  <div style="color: #d1d5db; font-size: 13px;">${escapeHtml(analysisResult.keywords)}</div>
                </div>` : ''}
                ${analysisResult.category ? `
                <div style="margin-bottom: 12px;">
                  <strong style="color: #10b981; display: block; margin-bottom: 6px;">分类：</strong>
                  <div style="color: #d1d5db; font-size: 13px;">${escapeHtml(analysisResult.category)}</div>
                </div>` : ''}
                ${analysisResult.sentiment ? `
                <div style="margin-bottom: 12px;">
                  <strong style="color: #10b981; display: block; margin-bottom: 6px;">情感倾向：</strong>
                  <div style="color: #d1d5db; font-size: 13px;">${escapeHtml(analysisResult.sentiment)}</div>
                </div>` : ''}
                ${analysisResult.key_points && Array.isArray(analysisResult.key_points) ? `
                <div>
                  <strong style="color: #10b981; display: block; margin-bottom: 6px;">要点：</strong>
                  <ul style="margin: 0; padding-left: 20px; color: #d1d5db; font-size: 13px; line-height: 1.8;">
                    ${analysisResult.key_points.map(p => `<li>${escapeHtml(p)}</li>`).join('')}
                  </ul>
                </div>` : ''}
                ${!analysisResult.summary && !analysisResult.keywords && !analysisResult.category ? `
                <pre style="color: #9ca3af; font-size: 12px; margin: 0;">${escapeHtml(JSON.stringify(analysisResult, null, 2))}</pre>
                ` : ''}
              </div>
            </details>
          </div>` : '<p style="color: #9ca3af;">暂无分析结果</p>'}
        </div>
      `;
    } else if (stage === 'planning') {
      stageContent = `
        <div class="detail-section">
          <h4>策划阶段</h4>
          ${workflow.analysis_result ? `
          <div class="detail-item">
            <span>输入：</span>
            <details>
              <summary>分析结果</summary>
              <pre>${escapeHtml(JSON.stringify(workflow.analysis_result, null, 2))}</pre>
            </details>
          </div>` : ''}
          ${workflow.plan_result ? `
          <div class="detail-item">
            <span>输出：</span>
            <details open>
              <summary>策划结果</summary>
              <pre>${escapeHtml(JSON.stringify(workflow.plan_result, null, 2))}</pre>
            </details>
          </div>` : '<p style="color: #9ca3af;">暂无策划结果</p>'}
        </div>
      `;
    } else if (stage === 'writing') {
      stageContent = `
        <div class="detail-section">
          <h4>生成阶段</h4>
          ${workflow.plan_result ? `
          <div class="detail-item">
            <span>输入：</span>
            <details>
              <summary>策划结果</summary>
              <pre>${escapeHtml(JSON.stringify(workflow.plan_result, null, 2))}</pre>
            </details>
          </div>` : ''}
          ${workflow.article ? `
          <div class="detail-item">
            <span>输出：</span>
            <details open>
              <summary>生成文章</summary>
              <div style="padding: 12px; background: #f9fafb; border-radius: 4px; line-height: 1.8;">
                <h5 style="margin: 0 0 8px 0; color: #111827;">${escapeHtml(workflow.article.title || '')}</h5>
                <div style="color: #4b5563; font-size: 14px;">${escapeHtml((workflow.article.content || '').substring(0, 500))}${workflow.article.content?.length > 500 ? '...' : ''}</div>
              </div>
            </details>
          </div>` : '<p style="color: #9ca3af;">暂无文章</p>'}
        </div>
      `;
    } else if (stage === 'checking') {
      stageContent = `
        <div class="detail-section">
          <h4>检查阶段</h4>
          ${workflow.article ? `
          <div class="detail-item">
            <span>输入：</span>
            <details>
              <summary>文章内容</summary>
              <div style="padding: 12px; background: #f9fafb; border-radius: 4px;">
                <h5 style="margin: 0 0 8px 0;">${escapeHtml(workflow.article.title || '')}</h5>
                <div style="color: #4b5563; font-size: 14px;">${escapeHtml((workflow.article.content || '').substring(0, 300))}...</div>
              </div>
            </details>
          </div>` : ''}
          <div class="detail-item">
            <span>输出：</span>
            <strong style="color: ${workflow.quality_score >= 0.7 ? '#10b981' : '#ef4444'};">
              质量评分 ${workflow.quality_score ? (workflow.quality_score * 100).toFixed(0) : '0'}分
            </strong>
          </div>
        </div>
      `;
    } else {
      // completed或无stage，显示全部
      stageContent = `
        ${workflow.collect_result || workflow.analysis_result || workflow.plan_result ? `
        <div class="detail-section">
          <h4>阶段结果</h4>
          ${workflow.collect_result ? `<details><summary>采集结果</summary><pre>${escapeHtml(JSON.stringify(workflow.collect_result, null, 2))}</pre></details>` : ''}
          ${workflow.analysis_result ? `<details><summary>分析结果</summary><pre>${escapeHtml(JSON.stringify(workflow.analysis_result, null, 2))}</pre></details>` : ''}
          ${workflow.plan_result ? `<details><summary>策划结果</summary><pre>${escapeHtml(JSON.stringify(workflow.plan_result, null, 2))}</pre></details>` : ''}
        </div>` : ''}
      `;
    }

    panel.innerHTML = `
      <div class="detail-header">
        <h3>${escapeHtml(title)} <span style="color: #10b981; font-size: 14px;">[${stageName}]</span></h3>
        <button onclick="AgentDetailPanel.close()">&times;</button>
      </div>

      <div class="detail-section">
        <h4>基本信息</h4>
        <div class="detail-item">
          <span>平台：</span><strong>${escapeHtml(platform)}</strong>
        </div>
        <div class="detail-item">
          <span>当前阶段：</span><strong>${escapeHtml(workflow.current_stage || '未知')}</strong>
        </div>
        <div class="detail-item">
          <span>状态：</span><strong>${escapeHtml(workflow.status || '未知')}</strong>
        </div>
      </div>

      ${stageContent}

      ${workflow.decisions && workflow.decisions.length > 0 ? `
      <div class="detail-section">
        <h4>决策记录</h4>
        ${renderDecisions(workflow.decisions)}
      </div>` : ''}

      ${filteredLogs.length > 0 ? `
      <div class="detail-section">
        <h4>LLM调用日志 (${filteredLogs.length}条)</h4>
        ${renderLLMLogs(filteredLogs)}
      </div>` : ''}

      ${workflow.article_id && stage === 'completed' ? `
      <div class="detail-section">
        <h4>最终文章</h4>
        <div class="detail-item">
          <span>文章ID：</span><strong>${workflow.article_id}</strong>
        </div>
        ${workflow.quality_score ? `
        <div class="detail-item">
          <span>质量评分：</span><strong>${(workflow.quality_score * 100).toFixed(0)}分</strong>
        </div>` : ''}
        <button class="btn btn-primary btn-sm" onclick="AgentDetailPanel.previewArticle(${workflow.article_id})">预览文章</button>
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

  function renderLLMLogs(logs) {
    if (!logs || logs.length === 0) return '<div>暂无日志</div>';
    return logs.map((log, idx) => `
      <details class="llm-log-item">
        <summary>
          <span class="llm-log-stage">${log.stage || '未知阶段'}</span>
          <span class="llm-log-model">${log.model}</span>
          <span class="llm-log-duration">${log.duration_ms}ms</span>
          <span class="llm-log-tokens">${log.tokens?.total_tokens || 0} tokens</span>
        </summary>
        <div class="llm-log-content">
          <div class="llm-log-section">
            <strong>提示词：</strong>
            <pre>${escapeHtml(log.prompt)}</pre>
          </div>
          <div class="llm-log-section">
            <strong>响应：</strong>
            <pre>${escapeHtml(log.response)}</pre>
          </div>
          ${log.metadata && Object.keys(log.metadata).length > 0 ? `
          <div class="llm-log-section">
            <strong>元数据：</strong>
            <pre>${JSON.stringify(log.metadata, null, 2)}</pre>
          </div>` : ''}
        </div>
      </details>
    `).join('');
  }

  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
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
