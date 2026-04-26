/**
 * Agent DAG 可视化核心
 * 水平分层布局：scan -> evaluate -> [workflows by stage] -> compose
 */
const AgentDAGVisualizer = (() => {

  const NODE_W = 120;
  const NODE_H = 60;
  const LAYER_GAP = 200;
  const NODE_GAP = 100;
  const PAD = 50;

  const STAGE_ORDER = ['collecting', 'analyzing', 'writing', 'checking', 'completed'];

  const COLORS = {
    scan:       '#10b981',
    evaluate:   '#3b82f6',
    collecting: '#f59e0b',
    analyzing:  '#8b5cf6',
    writing:    '#ec4899',
    checking:   '#06b6d4',
    completed:  '#10b981',
    failed:     '#ef4444',
    compose:    '#6366f1',
    workflow:   '#6b7280'
  };

  let containerInitialized = false;
  let lastRenderTime = 0;
  const MIN_RENDER_INTERVAL = 2000;

  // 视口变换状态
  let viewportTransform = { x: 0, y: 0, scale: 1 };
  let isDragging = false;
  let dragStart = { x: 0, y: 0 };
  let dragStartTransform = { x: 0, y: 0 };

  function initContainer(container) {
    if (containerInitialized) return;
    containerInitialized = true;

    // 添加控制按钮
    const controls = document.createElement('div');
    controls.className = 'dag-controls';
    controls.innerHTML = `
      <button class="dag-control-btn" id="dag-zoom-in" title="放大">+</button>
      <button class="dag-control-btn" id="dag-zoom-out" title="缩小">−</button>
      <button class="dag-control-btn" id="dag-reset" title="重置视图">⊙</button>
      <button class="dag-control-btn" id="dag-fit" title="适应画布">⊡</button>
    `;
    container.appendChild(controls);

    // 绑定控制按钮事件
    document.getElementById('dag-zoom-in').addEventListener('click', () => zoomBy(1.2));
    document.getElementById('dag-zoom-out').addEventListener('click', () => zoomBy(0.8));
    document.getElementById('dag-reset').addEventListener('click', resetView);
    document.getElementById('dag-fit').addEventListener('click', fitToView);
  }

  function render(container, statusData) {
    if (!container) return;

    // 初始化容器
    initContainer(container);

    // 限制渲染频率，避免闪烁（改为10秒）
    const now = Date.now();
    if (now - lastRenderTime < MIN_RENDER_INTERVAL) {
      console.log('[DAG] Skip render: too soon');
      return;
    }
    lastRenderTime = now;

    const workflows = statusData.workflows || [];
    const compose = statusData.compose || {};

    const graph = buildGraph(workflows, compose, statusData);
    computeHorizontalLayout(graph);
    renderSVG(container, graph);
  }

  function getStageIndex(stage) {
    const idx = STAGE_ORDER.indexOf(stage);
    return idx >= 0 ? idx : 0;
  }

  function buildGraph(workflows, compose, statusData) {
    const nodes = [];
    const edges = [];

    // Layer 0: scan节点
    nodes.push({ id: 'scan', type: 'scan', layer: 0, row: 0, data: statusData });

    // Layer 1: evaluate节点
    nodes.push({ id: 'evaluate', type: 'evaluate', layer: 1, row: 0, data: statusData });
    edges.push({ from: 'scan', to: 'evaluate' });

    // Layer 2-6: 每个workflow的各个阶段节点
    workflows.forEach((wf, wfIdx) => {
      const wfId = wf.id || `wf-${wfIdx}`;
      const stages = ['collecting', 'analyzing', 'writing', 'checking', 'completed'];

      // 找到当前workflow到达的最远stage
      const currentStageIdx = stages.indexOf(wf.current_stage);
      const maxStageIdx = currentStageIdx >= 0 ? currentStageIdx : 0;

      // 为每个已经过的stage创建节点
      for (let stageIdx = 0; stageIdx <= maxStageIdx; stageIdx++) {
        const stage = stages[stageIdx];
        const nodeId = `${wfId}-${stage}`;
        const isCurrentStage = stageIdx === maxStageIdx;

        nodes.push({
          id: nodeId,
          type: 'workflow',
          layer: 2 + stageIdx,
          row: wfIdx,
          data: {
            ...wf,
            current_stage: stage,
            status: isCurrentStage ? wf.status : 'completed'
          }
        });

        // 连接到前一个节点
        if (stageIdx === 0) {
          edges.push({ from: 'evaluate', to: nodeId });
        } else {
          const prevNodeId = `${wfId}-${stages[stageIdx - 1]}`;
          edges.push({ from: prevNodeId, to: nodeId });
        }
      }

      // 如果workflow已完成，连接到compose
      if (wf.status === 'completed') {
        const lastNodeId = `${wfId}-completed`;
        edges.push({ from: lastNodeId, to: 'compose' });
      }
    });

    // 最后一层: compose节点
    const composeLayer = 2 + 5; // 2 + stages.length
    nodes.push({ id: 'compose', type: 'compose', layer: composeLayer, row: 0, data: compose });

    return { nodes, edges };
  }

  function computeHorizontalLayout(graph) {
    const layers = {};
    graph.nodes.forEach(n => {
      if (!layers[n.layer]) layers[n.layer] = [];
      layers[n.layer].push(n);
    });

    Object.keys(layers).forEach(layerKey => {
      const layer = layers[layerKey];
      const layerIdx = Number(layerKey);
      const x = layerIdx * LAYER_GAP + PAD;
      layer.forEach((node, i) => {
        node.px = x;
        node.py = i * NODE_GAP + PAD;
      });
    });

    return graph;
  }

  let lastRenderData = null;

  function renderSVG(container, layout) {
    const width = Math.max(...layout.nodes.map(n => n.px)) + NODE_W + PAD;
    const height = Math.max(...layout.nodes.map(n => n.py)) + NODE_H + PAD;

    // 生成数据指纹，只有数据变化时才重新渲染
    const dataFingerprint = JSON.stringify(layout.nodes.map(n => ({
      id: n.id,
      px: n.px,
      py: n.py,
      stage: n.data?.current_stage,
      status: n.data?.status
    })));

    if (dataFingerprint === lastRenderData) {
      return; // 数据没变化，跳过渲染
    }
    lastRenderData = dataFingerprint;

    let svg = container.querySelector('svg');

    // 首次渲染：创建完整SVG结构
    if (!svg) {
      svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('width', '100%');
      svg.setAttribute('height', '100%');
      svg.setAttribute('class', 'agent-dag-svg');
      svg.style.cursor = 'grab';

      const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
      const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
      marker.setAttribute('id', 'dag-arrow');
      marker.setAttribute('markerWidth', '10');
      marker.setAttribute('markerHeight', '10');
      marker.setAttribute('refX', '9');
      marker.setAttribute('refY', '3');
      marker.setAttribute('orient', 'auto');
      marker.setAttribute('markerUnits', 'strokeWidth');
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', 'M0,0 L0,6 L9,3 z');
      path.setAttribute('fill', '#4b5563');
      marker.appendChild(path);
      defs.appendChild(marker);
      svg.appendChild(defs);

      // 创建viewport容器用于变换
      const viewport = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      viewport.setAttribute('id', 'dag-viewport');
      svg.appendChild(viewport);

      const edgesGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      edgesGroup.setAttribute('id', 'dag-edges');
      viewport.appendChild(edgesGroup);

      const nodesGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      nodesGroup.setAttribute('id', 'dag-nodes');
      viewport.appendChild(nodesGroup);

      container.appendChild(svg);

      // 绑定交互事件
      setupInteractions(svg, viewport);

      // 初始化视图：居中显示
      const containerRect = container.getBoundingClientRect();
      viewportTransform.x = (containerRect.width - width) / 2;
      viewportTransform.y = 50;
      applyTransform(viewport);
    }

    const viewport = svg.querySelector('#dag-viewport');
    const edgesGroup = viewport.querySelector('#dag-edges');
    const nodesGroup = viewport.querySelector('#dag-nodes');

    // 更新边
    edgesGroup.innerHTML = '';
    layout.edges.forEach(edge => {
      const line = createEdgeElement(edge, layout.nodes);
      if (line) edgesGroup.appendChild(line);
    });

    // 更新节点
    const existingNodes = new Map();
    Array.from(nodesGroup.children).forEach(g => {
      const id = g.getAttribute('data-id');
      if (id) existingNodes.set(id, g);
    });

    layout.nodes.forEach(node => {
      let nodeGroup = existingNodes.get(node.id);
      if (!nodeGroup) {
        nodeGroup = createNodeElement(node);
        nodesGroup.appendChild(nodeGroup);
      } else {
        updateNodeElement(nodeGroup, node);
      }
      existingNodes.delete(node.id);
    });

    existingNodes.forEach(g => g.remove());
  }

  // 交互功能
  function setupInteractions(svg, viewport) {
    // 拖拽
    svg.addEventListener('mousedown', (e) => {
      if (e.button !== 0) return; // 只响应左键
      isDragging = true;
      dragStart = { x: e.clientX, y: e.clientY };
      dragStartTransform = { x: viewportTransform.x, y: viewportTransform.y };
      svg.style.cursor = 'grabbing';
      e.preventDefault();
    });

    svg.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      const dx = e.clientX - dragStart.x;
      const dy = e.clientY - dragStart.y;
      viewportTransform.x = dragStartTransform.x + dx;
      viewportTransform.y = dragStartTransform.y + dy;
      applyTransform(viewport);
    });

    svg.addEventListener('mouseup', () => {
      isDragging = false;
      svg.style.cursor = 'grab';
    });

    svg.addEventListener('mouseleave', () => {
      isDragging = false;
      svg.style.cursor = 'grab';
    });

    // 缩放
    svg.addEventListener('wheel', (e) => {
      e.preventDefault();
      const rect = svg.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      zoomAt(mouseX, mouseY, delta, viewport);
    });
  }

  function applyTransform(viewport) {
    const { x, y, scale } = viewportTransform;
    viewport.setAttribute('transform', `translate(${x}, ${y}) scale(${scale})`);
  }

  function zoomBy(factor, viewport) {
    const svg = document.querySelector('.agent-dag-svg');
    if (!svg) return;
    viewport = viewport || svg.querySelector('#dag-viewport');
    if (!viewport) return;

    const rect = svg.getBoundingClientRect();
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    zoomAt(centerX, centerY, factor, viewport);
  }

  function zoomAt(x, y, factor, viewport) {
    const oldScale = viewportTransform.scale;
    const newScale = Math.max(0.1, Math.min(3, oldScale * factor));

    if (newScale === oldScale) return;

    const scaleChange = newScale / oldScale;
    viewportTransform.x = x - (x - viewportTransform.x) * scaleChange;
    viewportTransform.y = y - (y - viewportTransform.y) * scaleChange;
    viewportTransform.scale = newScale;

    applyTransform(viewport);
  }

  function resetView() {
    const svg = document.querySelector('.agent-dag-svg');
    const viewport = svg?.querySelector('#dag-viewport');
    if (!viewport) return;

    const container = svg.parentElement;
    const containerRect = container.getBoundingClientRect();

    viewportTransform.x = containerRect.width / 2 - 500;
    viewportTransform.y = 50;
    viewportTransform.scale = 1;
    applyTransform(viewport);
  }

  function fitToView() {
    const svg = document.querySelector('.agent-dag-svg');
    const viewport = svg?.querySelector('#dag-viewport');
    if (!viewport) return;

    const container = svg.parentElement;
    const containerRect = container.getBoundingClientRect();
    const bbox = viewport.getBBox();

    const scaleX = containerRect.width / (bbox.width + 100);
    const scaleY = containerRect.height / (bbox.height + 100);
    const scale = Math.min(scaleX, scaleY, 1);

    viewportTransform.scale = scale;
    viewportTransform.x = (containerRect.width - bbox.width * scale) / 2 - bbox.x * scale;
    viewportTransform.y = (containerRect.height - bbox.height * scale) / 2 - bbox.y * scale;
    applyTransform(viewport);
  }

  function createNodeElement(node) {
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.setAttribute('transform', `translate(${node.px}, ${node.py})`);
    g.setAttribute('class', node.data?.status === 'running' ? 'dag-node dag-node-active' : 'dag-node');
    g.setAttribute('data-id', node.id);
    g.setAttribute('data-type', node.type);
    g.style.cursor = 'pointer';
    g.onclick = () => AgentDAGVisualizer.showDetail(node.id);

    const color = getNodeColor(node);
    const label = getNodeLabel(node);
    const subLabel = getNodeSubLabel(node);

    // 矩形
    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rect.setAttribute('width', NODE_W);
    rect.setAttribute('height', NODE_H);
    rect.setAttribute('rx', '8');
    rect.setAttribute('fill', color);
    rect.setAttribute('fill-opacity', '0.15');
    rect.setAttribute('stroke', color);
    rect.setAttribute('stroke-width', '2');
    g.appendChild(rect);

    // 主标签
    const text1 = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text1.setAttribute('x', NODE_W / 2);
    text1.setAttribute('y', NODE_H / 2 - 2);
    text1.setAttribute('text-anchor', 'middle');
    text1.setAttribute('fill', '#e5e7eb');
    text1.setAttribute('font-size', '12');
    text1.setAttribute('font-weight', '500');
    text1.textContent = label;
    g.appendChild(text1);

    // 副标签
    if (subLabel) {
      const text2 = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text2.setAttribute('x', NODE_W / 2);
      text2.setAttribute('y', NODE_H / 2 + 16);
      text2.setAttribute('text-anchor', 'middle');
      text2.setAttribute('fill', '#9ca3af');
      text2.setAttribute('font-size', '10');
      text2.textContent = subLabel;
      g.appendChild(text2);
    }

    // Tooltip
    const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    title.textContent = buildTooltipText(node);
    g.appendChild(title);

    return g;
  }

  function updateNodeElement(g, node) {
    g.setAttribute('transform', `translate(${node.px}, ${node.py})`);
    g.setAttribute('class', node.data?.status === 'running' ? 'dag-node dag-node-active' : 'dag-node');

    const color = getNodeColor(node);
    const label = getNodeLabel(node);
    const subLabel = getNodeSubLabel(node);

    const rect = g.querySelector('rect');
    if (rect) {
      rect.setAttribute('fill', color);
      rect.setAttribute('stroke', color);
    }

    const texts = g.querySelectorAll('text');
    if (texts[0]) texts[0].textContent = label;
    if (texts[1]) texts[1].textContent = subLabel;

    const title = g.querySelector('title');
    if (title) title.textContent = buildTooltipText(node);
  }

  function createEdgeElement(edge, nodes) {
    const from = nodes.find(n => n.id === edge.from);
    const to = nodes.find(n => n.id === edge.to);
    if (from && to) {
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', from.px + NODE_W);
      line.setAttribute('y1', from.py + NODE_H / 2);
      line.setAttribute('x2', to.px);
      line.setAttribute('y2', to.py + NODE_H / 2);
      line.setAttribute('stroke', '#4b5563');
      line.setAttribute('stroke-width', '2');
      line.setAttribute('marker-end', 'url(#dag-arrow)');
      return line;
    }
    return null;
  }

  function buildTooltipText(node) {
    const lines = [];
    if (node.type === 'workflow') {
      const d = node.data || {};
      if (d.topic_title) lines.push(d.topic_title);
      lines.push(`平台: ${d.platform || '-'}`);
      lines.push(`阶段: ${d.current_stage || '-'}`);
      lines.push(`状态: ${d.status || '-'}`);
      if (d.retry_count > 0) lines.push(`重试: ${d.retry_count}次`);
      if (d.quality_score) lines.push(`评分: ${Math.round(d.quality_score * 100)}分`);
    } else if (node.type === 'scan') {
      lines.push('热点扫描');
    } else if (node.type === 'evaluate') {
      lines.push('价值评估');
    } else if (node.type === 'compose') {
      lines.push('汇总输出');
    }
    return lines.join('\n');
  }

  function getNodeColor(node) {
    if (node.type === 'workflow') {
      if (node.data?.status === 'failed') return COLORS.failed;
      if (node.data?.status === 'completed') return COLORS.completed;
      return COLORS[node.data?.current_stage] || COLORS.workflow;
    }
    return COLORS[node.type] || COLORS.workflow;
  }

  function getNodeLabel(node) {
    if (node.type === 'scan') return '热点扫描';
    if (node.type === 'evaluate') return '价值评估';
    if (node.type === 'compose') return '汇总输出';
    const title = node.data?.topic_title || node.data?.title || node.id;
    return truncateLabel(String(title), 7);
  }

  function getNodeSubLabel(node) {
    if (node.type === 'workflow') {
      const stage = node.data?.current_stage || '';
      const status = node.data?.status || '';

      // 阶段中文映射
      const stageMap = {
        'collecting': '采集',
        'analyzing': '分析',
        'writing': '生成',
        'checking': '检查',
        'completed': '完成'
      };

      // 状态后缀映射
      const statusSuffix = {
        'running': '中',
        'completed': '完成',
        'failed': '失败',
        'waiting': '等待',
        'blocked': '阻塞'
      };

      const stageCN = stageMap[stage] || stage;
      const suffix = statusSuffix[status] || '';

      return escapeHtml(stageCN + suffix);
    }
    if (node.type === 'scan' && node.data?.count != null) return `${node.data.count}条`;
    if (node.type === 'evaluate' && node.data?.count != null) return `${node.data.count}条`;
    if (node.type === 'compose') return escapeHtml(node.data?.status || '');
    return '';
  }

  function renderNode(node) {
    const color = getNodeColor(node);
    const label = getNodeLabel(node);
    const subLabel = getNodeSubLabel(node);
    const isActive = node.data?.status === 'running';
    const nodeClass = isActive ? 'dag-node dag-node-active' : 'dag-node';

    // 构建tooltip内容
    let tooltipLines = [];
    if (node.type === 'workflow') {
      const d = node.data || {};
      tooltipLines.push(d.topic_title || '');
      tooltipLines.push(`平台: ${d.platform || '-'}`);
      tooltipLines.push(`阶段: ${d.current_stage || '-'}`);
      tooltipLines.push(`状态: ${d.status || '-'}`);
      if (d.retry_count > 0) tooltipLines.push(`重试: ${d.retry_count}次`);
      if (d.quality_score) tooltipLines.push(`评分: ${Math.round(d.quality_score * 100)}分`);
    } else if (node.type === 'scan') {
      tooltipLines.push('热点扫描');
      if (node.data?.count) tooltipLines.push(`扫描到 ${node.data.count} 条热点`);
    } else if (node.type === 'evaluate') {
      tooltipLines.push('价值评估');
      if (node.data?.count) tooltipLines.push(`筛选出 ${node.data.count} 个话题`);
    } else if (node.type === 'compose') {
      tooltipLines.push('汇总输出');
      tooltipLines.push(`状态: ${node.data?.status || 'pending'}`);
    }
    const tooltipText = tooltipLines.join('&#10;');

    return `
      <g transform="translate(${node.px}, ${node.py})"
         class="${nodeClass}"
         data-id="${escapeAttr(node.id)}"
         data-type="${node.type}"
         style="cursor:pointer;"
         onclick="AgentDAGVisualizer.showDetail('${escapeAttr(node.id)}')"
         onmouseenter="AgentDAGVisualizer.showTooltip(evt, '${escapeAttr(node.id)}')"
         onmouseleave="AgentDAGVisualizer.hideTooltip()">
        <rect width="${NODE_W}" height="${NODE_H}" rx="8"
              fill="${color}" fill-opacity="0.15"
              stroke="${color}" stroke-width="2"/>
        <text x="${NODE_W / 2}" y="${NODE_H / 2 - 2}" text-anchor="middle"
              fill="#e5e7eb" font-size="12" font-weight="500">${label}</text>
        ${subLabel ? `<text x="${NODE_W / 2}" y="${NODE_H / 2 + 16}" text-anchor="middle"
              fill="#9ca3af" font-size="10">${subLabel}</text>` : ''}
        <title>${tooltipText}</title>
      </g>
    `;
  }

  function renderEdge(edge, nodes) {
    const from = nodes.find(n => n.id === edge.from);
    const to = nodes.find(n => n.id === edge.to);
    if (!from || !to) return '';

    const x1 = from.px + NODE_W;
    const y1 = from.py + NODE_H / 2;
    const x2 = to.px;
    const y2 = to.py + NODE_H / 2;

    const dx = (x2 - x1) * 0.5;
    return `<path d="M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}"
                  fill="none" stroke="#4b5563" stroke-width="2"
                  marker-end="url(#dag-arrow)"/>`;
  }

  function showDetail(nodeId) {
    console.log('[DAG] Node clicked:', nodeId);

    // 特殊节点：scan和evaluate
    if (nodeId === 'scan' || nodeId === 'evaluate') {
      window.dispatchEvent(new CustomEvent('dag-node-click', { detail: { nodeId: nodeId, stage: nodeId } }));
      return;
    }

    // workflow节点（格式：wf_xxxxx-stage 或 wf-xxxxx-stage），提取真实的workflow ID和stage
    let realId = nodeId;
    let stage = null;

    const lastDashIdx = nodeId.lastIndexOf('-');
    if (lastDashIdx > 0 && (nodeId.startsWith('wf_') || nodeId.startsWith('wf-'))) {
      const possibleStage = nodeId.substring(lastDashIdx + 1);
      if (['collecting', 'analyzing', 'planning', 'writing', 'checking', 'completed', 'failed'].includes(possibleStage)) {
        realId = nodeId.substring(0, lastDashIdx);
        stage = possibleStage;
      }
    }

    console.log('[DAG] Extracted ID:', realId, 'stage:', stage);
    window.dispatchEvent(new CustomEvent('dag-node-click', { detail: { nodeId: realId, stage: stage } }));
  }

  function showTooltip() {}
  function hideTooltip() {}

  function escapeHtml(text) {
    if (text == null) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
  }

  function truncateLabel(text, maxLen) {
    const str = String(text || '');
    if (str.length <= maxLen) return escapeHtml(str);
    return escapeHtml(str.substring(0, maxLen) + '...');
  }

  function escapeAttr(text) {
    return String(text == null ? '' : text)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  return { render, showDetail, showTooltip, hideTooltip };
})();

if (typeof window !== 'undefined') {
  window.AgentDAGVisualizer = AgentDAGVisualizer;
}
