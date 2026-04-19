const ContentPage = (() => {
  let currentPage = 1;
  let currentLimit = 20;
  let allArticles = [];
  let selectedArticles = new Set();
  let statsData = {};
  let _resizeTimer = null;

  function render() {
    return `
      <div class="content-container">
        <div class="content-header">
          <h2>内容库</h2>
          <div class="content-stats" id="content-stats">
            <span class="content-stat-item">文章 <strong id="stat-total">0</strong></span>
            <span class="content-stat-item">已分析 <strong id="stat-analyzed">0</strong></span>
            <span class="content-stat-item">待分析 <strong id="stat-pending">0</strong></span>
          </div>
        </div>

        <div class="content-toolbar">
          <div class="content-search">
            <input type="text" class="input content-search-input" id="content-search"
                   placeholder="搜索文章标题或摘要..." oninput="ContentPage.filter()">
            <select class="select content-category-select" id="content-category"
                    onchange="ContentPage.filter()">
              <option value="">全部分类</option>
            </select>
          </div>
          <div class="content-toolbar-actions">
            <label class="content-select-all">
              <input type="checkbox" id="content-select-all"
                     onchange="ContentPage.toggleSelectAll()">
              <span>全选</span>
            </label>
          </div>
        </div>

        <div id="content-bulk-bar" class="content-bulk-bar" style="display:none;">
          <span id="content-selected-count">已选择 0 篇</span>
          <div class="content-bulk-actions">
            <button class="btn btn-sm btn-secondary" onclick="ContentPage.bulkAnalyze()">批量分析</button>
            <button class="btn btn-sm" style="color:#dc2626;" onclick="ContentPage.bulkDelete()">批量删除</button>
            <button class="btn btn-sm btn-text" onclick="ContentPage.clearSelection()">取消选择</button>
          </div>
        </div>

        <div id="content-list" class="content-list">
          <div class="loading-spinner"></div>
        </div>

        <div class="content-pagination" id="content-pagination">
          <button class="btn btn-sm btn-secondary" onclick="ContentPage.prevPage()">上一页</button>
          <span id="content-page-info">第 1/1 页</span>
          <button class="btn btn-sm btn-secondary" onclick="ContentPage.nextPage()">下一页</button>
        </div>
      </div>

      <div id="content-detail-modal" class="modal-overlay" style="display:none;"
           onclick="if(event.target===this)ContentPage.closeDetail()">
        <div class="content-detail-panel">
          <div class="content-detail-header">
            <h3>文章详情</h3>
            <button class="modal-close" onclick="ContentPage.closeDetail()">✕</button>
          </div>
          <div class="content-detail-body" id="content-detail-body"></div>
        </div>
      </div>
    `;
  }

  async function init() {
    await Promise.all([loadStats(), loadArticles()]);
    // 窗口大小变化时重新计算每页数量
    window.addEventListener('resize', () => {
      clearTimeout(_resizeTimer);
      _resizeTimer = setTimeout(() => loadArticles(currentPage), 300);
    });
  }

  async function loadStats() {
    try {
      const resp = await fetch('/api/stats');
      const data = await resp.json();
      if (data.success) {
        statsData = data.data;
        document.getElementById('stat-total').textContent = statsData.total || 0;
        document.getElementById('stat-analyzed').textContent = statsData.analyzed || 0;
        document.getElementById('stat-pending').textContent = statsData.pending || 0;
        updateCategoryFilter();
      }
    } catch (e) {
      console.error('加载统计失败:', e);
    }
  }

  function updateCategoryFilter() {
    const sel = document.getElementById('content-category');
    sel.innerHTML = '<option value="">全部分类</option>';
    if (statsData.categories) {
      Object.entries(statsData.categories).forEach(([cat, count]) => {
        const opt = document.createElement('option');
        opt.value = cat;
        opt.textContent = `${cat} (${count})`;
        sel.appendChild(opt);
      });
    }
  }

  async function loadArticles(page = 1) {
    const list = document.getElementById('content-list');
    list.innerHTML = '<div class="loading-spinner"></div>';

    // 动态计算每页数量，填满可用屏幕空间
    const containerWidth = list.offsetWidth || 1200;
    const cardMinWidth = 320;
    const gap = 24;
    const cols = Math.floor((containerWidth + gap) / (cardMinWidth + gap)) || 1;

    // 根据可用高度计算行数
    const mainContent = document.getElementById('main-content');
    const listTop = list.getBoundingClientRect().top;
    const availableHeight = window.innerHeight - listTop - 80; // 80px留给分页器
    const cardHeight = 180; // 卡片估算高度
    const rows = Math.max(2, Math.floor(availableHeight / (cardHeight + gap)));
    const limit = cols * rows;

    try {
      const resp = await fetch(`/api/articles?page=${page}&limit=${limit}`);
      const data = await resp.json();
      if (data.success) {
        allArticles = data.data.articles;
        currentPage = page;
        currentLimit = limit;
        displayArticles(allArticles);
        updatePagination(data.data);
      }
    } catch (e) {
      list.innerHTML = '<div class="empty-state"><div class="empty-state-title">加载失败</div></div>';
    }
  }

  function displayArticles(articles) {
    const list = document.getElementById('content-list');

    if (articles.length === 0) {
      list.innerHTML = '<div class="empty-state"><div class="empty-state-title">暂无文章</div></div>';
      return;
    }

    list.innerHTML = articles.map(article => {
      const sourceInfo = getSourceInfo(article);
      const preview = !article.summary ? getPreview(article.content, 80) : '';
      const time = formatTime(article.created_at || article.publish_time);
      const fullContent = article.content || article.summary || '';

      return `
        <div class="content-card">
          <div class="content-card-checkbox">
            <input type="checkbox" class="content-checkbox"
                   data-id="${article.id}"
                   onchange="ContentPage.toggleSelect(${article.id})"
                   ${selectedArticles.has(article.id) ? 'checked' : ''}>
          </div>
          <div class="content-card-body" onclick="ContentPage.showDetail(${article.id})">
            <div class="content-card-header">
              <div class="content-card-title">${escapeHtml(article.title)}</div>
              <div class="content-card-badges">
                ${sourceInfo ? `<span class="badge badge-source badge-${sourceInfo.cls}">${sourceInfo.label}</span>` : ''}
                <span class="badge ${article.analysis ? 'badge-green' : 'badge-gray'}">
                  ${article.analysis ? '已分析' : '待分析'}
                </span>
              </div>
            </div>
            <div class="content-card-meta">
              ${article.account_name ? `<span>${escapeHtml(article.account_name)}</span>` : ''}
              ${time ? `<span>${time}</span>` : ''}
              ${article.category ? `<span class="badge badge-gray">${escapeHtml(article.category)}</span>` : ''}
            </div>
            ${preview ? `<div class="content-card-preview">${escapeHtml(preview)}</div>` : ''}
            ${article.summary ? `<div class="content-card-summary">${escapeHtml(article.summary)}</div>` : ''}
            ${article.keywords ? `
              <div class="content-card-tags">
                ${article.keywords.split(',').slice(0, 5).map(k =>
                  `<span class="badge badge-gray">${escapeHtml(k.trim())}</span>`
                ).join('')}
              </div>
            ` : ''}
            <div class="content-card-hover-detail">
              <div class="hover-detail-title">完整内容</div>
              <div class="hover-detail-content">${escapeHtml(fullContent.substring(0, 500))}${fullContent.length > 500 ? '...' : ''}</div>
              ${article.analysis ? `
                <div class="hover-detail-section">
                  <div class="hover-detail-label">AI分析</div>
                  <div class="hover-detail-text">${escapeHtml(article.analysis.substring(0, 200))}${article.analysis.length > 200 ? '...' : ''}</div>
                </div>
              ` : ''}
            </div>
          </div>
        </div>`;
    }).join('');

    updateBulkBar();
  }

  function updatePagination(data) {
    const totalPages = Math.ceil(data.total / data.limit) || 1;
    document.getElementById('content-page-info').textContent =
      `第 ${data.page}/${totalPages} 页 (共${data.total}篇)`;
  }

  function filter() {
    const search = document.getElementById('content-search').value.toLowerCase();
    const category = document.getElementById('content-category').value;

    const filtered = allArticles.filter(a => {
      const matchSearch = !search ||
        a.title.toLowerCase().includes(search) ||
        (a.summary && a.summary.toLowerCase().includes(search));
      const matchCat = !category || a.category === category;
      return matchSearch && matchCat;
    });

    displayArticles(filtered);
  }

  async function showDetail(articleId) {
    try {
      const resp = await fetch(`/api/article/${articleId}`);
      const data = await resp.json();
      if (!data.success) return;

      const article = data.data;
      const sourceInfo = getSourceInfo(article);
      const time = formatTime(article.created_at || article.publish_time);

      document.getElementById('content-detail-body').innerHTML = `
        <div class="detail-title">${escapeHtml(article.title)}</div>
        <div class="detail-meta">
          ${article.account_name ? `<span>${escapeHtml(article.account_name)}</span>` : ''}
          ${sourceInfo ? `<span class="badge badge-source badge-${sourceInfo.cls}">${sourceInfo.label}</span>` : ''}
          ${time ? `<span>${time}</span>` : ''}
          ${article.category ? `<span class="badge badge-gray">${escapeHtml(article.category)}</span>` : ''}
        </div>
        ${article.keywords ? `
          <div class="detail-tags">
            ${article.keywords.split(',').map(k =>
              `<span class="badge badge-gray">${escapeHtml(k.trim())}</span>`
            ).join('')}
          </div>
        ` : ''}
        ${article.summary ? `
          <div class="detail-section">
            <div class="detail-section-title">摘要</div>
            <div class="detail-section-content">${escapeHtml(article.summary)}</div>
          </div>
        ` : ''}
        ${article.analysis ? `
          <div class="detail-section">
            <div class="detail-section-title">深度分析</div>
            <div class="detail-section-content">${renderMarkdown(article.analysis)}</div>
          </div>
        ` : ''}
        ${article.content ? `
          <div class="detail-section">
            <div class="detail-section-title">文章内容</div>
            <div class="detail-section-content">${escapeHtml(article.content.substring(0, 2000))}${article.content.length > 2000 ? '\n\n...(内容已截断)' : ''}</div>
          </div>
        ` : ''}
        <div class="detail-actions">
          ${!article.analysis ? `<button class="btn btn-primary btn-sm" onclick="ContentPage.analyzeArticle(${article.id})">立即分析</button>` : ''}
          <button class="btn btn-sm" style="color:#dc2626;" onclick="ContentPage.deleteArticle(${article.id})">删除文章</button>
          ${article.url ? `<a href="${article.url}" target="_blank" class="btn btn-secondary btn-sm" style="text-decoration:none;">查看原文</a>` : ''}
        </div>
      `;

      document.getElementById('content-detail-modal').style.display = 'flex';
    } catch (e) {
      alert('加载详情失败');
    }
  }

  function closeDetail() {
    document.getElementById('content-detail-modal').style.display = 'none';
  }

  async function analyzeArticle(articleId) {
    if (!confirm('确定要分析这篇文章吗？')) return;
    try {
      const resp = await fetch(`/api/analyze/${articleId}`, { method: 'POST' });
      const data = await resp.json();
      if (data.success) {
        alert('分析完成');
        closeDetail();
        refreshData();
      } else {
        alert('分析失败: ' + data.error);
      }
    } catch (e) {
      alert('分析失败: ' + e.message);
    }
  }

  async function deleteArticle(articleId) {
    if (!confirm('确定要删除这篇文章吗？此操作不可恢复。')) return;
    try {
      const resp = await fetch(`/api/article/${articleId}`, { method: 'DELETE' });
      const data = await resp.json();
      if (data.success) {
        alert('删除成功');
        closeDetail();
        refreshData();
      } else {
        alert('删除失败: ' + data.error);
      }
    } catch (e) {
      alert('删除失败: ' + e.message);
    }
  }

  function toggleSelect(articleId) {
    if (selectedArticles.has(articleId)) {
      selectedArticles.delete(articleId);
    } else {
      selectedArticles.add(articleId);
    }
    updateBulkBar();
    updateSelectAllState();
  }

  function toggleSelectAll() {
    const cb = document.getElementById('content-select-all');
    const boxes = document.querySelectorAll('.content-checkbox');
    if (cb.checked) {
      boxes.forEach(b => {
        selectedArticles.add(parseInt(b.dataset.id));
        b.checked = true;
      });
    } else {
      selectedArticles.clear();
      boxes.forEach(b => b.checked = false);
    }
    updateBulkBar();
  }

  function updateSelectAllState() {
    const boxes = document.querySelectorAll('.content-checkbox');
    const all = boxes.length > 0 && Array.from(boxes).every(b => b.checked);
    document.getElementById('content-select-all').checked = all;
  }

  function updateBulkBar() {
    const bar = document.getElementById('content-bulk-bar');
    const count = document.getElementById('content-selected-count');
    if (selectedArticles.size > 0) {
      bar.style.display = 'flex';
      count.textContent = `已选择 ${selectedArticles.size} 篇`;
    } else {
      bar.style.display = 'none';
    }
  }

  function clearSelection() {
    selectedArticles.clear();
    document.querySelectorAll('.content-checkbox').forEach(b => b.checked = false);
    document.getElementById('content-select-all').checked = false;
    updateBulkBar();
  }

  async function bulkDelete() {
    if (selectedArticles.size === 0) return;
    if (!confirm(`确定要删除选中的 ${selectedArticles.size} 篇文章吗？`)) return;
    try {
      const resp = await fetch('/api/articles/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ article_ids: Array.from(selectedArticles) })
      });
      const data = await resp.json();
      if (data.success) {
        alert(`成功删除 ${data.data.deleted_count} 篇文章`);
        clearSelection();
        refreshData();
      } else {
        alert('删除失败: ' + data.error);
      }
    } catch (e) {
      alert('删除失败: ' + e.message);
    }
  }

  async function bulkAnalyze() {
    if (selectedArticles.size === 0) return;
    if (!confirm(`确定要分析选中的 ${selectedArticles.size} 篇文章吗？`)) return;
    let ok = 0, fail = 0;
    for (const id of selectedArticles) {
      try {
        const resp = await fetch(`/api/analyze/${id}`, { method: 'POST' });
        const data = await resp.json();
        data.success ? ok++ : fail++;
      } catch (e) { fail++; }
    }
    alert(`批量分析完成\n成功: ${ok}\n失败: ${fail}`);
    clearSelection();
    refreshData();
  }

  function prevPage() {
    if (currentPage > 1) loadArticles(currentPage - 1);
  }

  function nextPage() {
    loadArticles(currentPage + 1);
  }

  function refreshData() {
    loadStats();
    loadArticles(currentPage);
  }

  function getSourceInfo(article) {
    const source = (article.source || '').toLowerCase();
    const account = (article.account_name || '').toLowerCase();
    if (source === 'wechat' || account.includes('微信')) return { label: '微信', cls: 'wechat' };
    if (source === 'weibo' || account === '微博') return { label: '微博', cls: 'weibo' };
    if (source === 'zhihu' || account === '知乎') return { label: '知乎', cls: 'zhihu' };
    if (source === 'baidu' || account.includes('百度')) return { label: '百度', cls: 'baidu' };
    if (source === 'douyin' || account.includes('抖音')) return { label: '抖音', cls: 'douyin' };
    if (source && source !== 'manual') return { label: source, cls: 'default' };
    return null;
  }

  function formatTime(timeStr) {
    if (!timeStr) return '';
    try {
      const d = new Date(timeStr);
      if (isNaN(d.getTime())) return timeStr;
      const diff = Date.now() - d;
      if (diff < 3600000) return Math.max(1, Math.floor(diff / 60000)) + '分钟前';
      if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前';
      if (diff < 604800000) return Math.floor(diff / 86400000) + '天前';
      return (d.getMonth() + 1) + '月' + d.getDate() + '日';
    } catch (e) { return timeStr; }
  }

  function getPreview(content, maxLen) {
    if (!content) return '';
    const text = content.replace(/\n+/g, ' ').replace(/\s+/g, ' ').trim();
    return text.length > maxLen ? text.substring(0, maxLen) + '...' : text;
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
    return escapeHtml(text);
  }

  return {
    render, init, filter, showDetail, closeDetail,
    analyzeArticle, deleteArticle,
    toggleSelect, toggleSelectAll, clearSelection,
    bulkDelete, bulkAnalyze,
    prevPage, nextPage
  };
})();

if (typeof window !== 'undefined') {
  window.ContentPage = ContentPage;
}
