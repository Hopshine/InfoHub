// 系统设置页
(function() {

let currentAccountId = null;

// 页面初始化
function initSettingsPage() {
    const content = `
        <div class="settings-container">
            <div class="settings-header">
                <h1>系统设置</h1>
            </div>

            <div class="settings-content">
                <!-- 公众号管理 -->
                <div class="settings-section">
                    <div class="section-header">
                        <h2>公众号管理</h2>
                        <button class="btn btn-primary" onclick="settingsPage.showAccountForm()">添加公众号</button>
                    </div>
                    <div id="accounts-list" class="accounts-list">
                        <div class="loading">加载中...</div>
                    </div>
                </div>

                <!-- 公众号表单 -->
                <div id="account-form" class="account-form" style="display:none;">
                    <div class="form-header">
                        <h3 id="form-title">添加公众号</h3>
                        <button class="btn-close" onclick="settingsPage.hideAccountForm()">×</button>
                    </div>
                    <div class="form-body">
                        <input type="hidden" id="account-id">

                        <div class="form-group">
                            <label>公众号名称 *</label>
                            <input type="text" id="account-name" class="form-control" placeholder="请输入公众号名称">
                        </div>

                        <div class="form-group">
                            <label>AppID *</label>
                            <input type="text" id="account-appid" class="form-control" placeholder="请输入AppID">
                        </div>

                        <div class="form-group">
                            <label>AppSecret *</label>
                            <input type="password" id="account-secret" class="form-control" placeholder="请输入AppSecret">
                        </div>

                        <div class="form-group">
                            <label>关键词</label>
                            <input type="text" id="account-keywords" class="form-control" placeholder="多个关键词用逗号分隔">
                        </div>

                        <div class="form-group">
                            <label>风格偏好</label>
                            <select id="account-style" class="form-control">
                                <option value="news">新闻</option>
                                <option value="casual">轻松</option>
                                <option value="professional">专业</option>
                                <option value="humorous">幽默</option>
                            </select>
                        </div>

                        <div class="form-group">
                            <label>自定义提示词</label>
                            <textarea id="account-prompt" class="form-control" rows="4" placeholder="可选，用于自定义AI生成风格"></textarea>
                        </div>

                        <div class="form-actions">
                            <button class="btn btn-secondary" onclick="settingsPage.hideAccountForm()">取消</button>
                            <button class="btn btn-primary" onclick="settingsPage.saveAccount()">保存</button>
                        </div>
                    </div>
                </div>

                <!-- AI模型渠道管理 -->
                <div class="settings-section">
                    <div class="section-header">
                        <h2>AI模型渠道管理</h2>
                        <button class="btn btn-primary btn-sm" onclick="SettingsPage.showProviderForm()">➕ 添加渠道</button>
                    </div>
                    <div id="providers-container"></div>
                    <div id="bindings-container" style="margin-top:24px;"></div>
                </div>

                <!-- 采集规则配置 -->
                <div class="settings-section">
                    <div class="section-header">
                        <h2>采集规则配置</h2>
                    </div>
                    <div class="config-card">
                        <div class="form-group">
                            <label>采集频率（分钟）</label>
                            <input type="number" class="form-control" value="30" min="5">
                        </div>
                        <div class="form-group">
                            <label>最大采集数量</label>
                            <input type="number" class="form-control" value="100" min="10">
                        </div>
                        <button class="btn btn-primary">保存配置</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    document.getElementById('main-content').innerHTML = content;
    loadAccounts();
    loadProviders();
}

// 加载公众号列表
async function loadAccounts() {
    try {
        const resp = await fetch('/api/accounts');
        const data = await resp.json();

        if (data.success) {
            const listDiv = document.getElementById('accounts-list');
            if (data.data.length === 0) {
                listDiv.innerHTML = '<div class="empty-state">暂无公众号配置</div>';
                return;
            }

            listDiv.innerHTML = data.data.map(acc => `
                <div class="account-card">
                    <div class="account-info">
                        <div class="account-name">${escapeHtml(acc.name)}</div>
                        <div class="account-detail">AppID: ${escapeHtml(acc.app_id)}</div>
                        <div class="account-detail">风格: ${acc.style_preference || 'news'}</div>
                        <div class="account-detail">关键词: ${escapeHtml(acc.topic_keywords || '无')}</div>
                    </div>
                    <div class="account-actions">
                        <button class="btn btn-sm" onclick="settingsPage.editAccount(${acc.id})">编辑</button>
                        <button class="btn btn-sm btn-danger" onclick="settingsPage.deleteAccount(${acc.id})">删除</button>
                    </div>
                </div>
            `).join('');
        }
    } catch (e) {
        console.error('加载公众号失败:', e);
        document.getElementById('accounts-list').innerHTML = '<div class="error-state">加载失败，请重试</div>';
    }
}

// 显示公众号表单
function showAccountForm() {
    currentAccountId = null;
    document.getElementById('form-title').textContent = '添加公众号';
    document.getElementById('account-form').style.display = 'block';
    document.getElementById('account-id').value = '';
    document.getElementById('account-name').value = '';
    document.getElementById('account-appid').value = '';
    document.getElementById('account-secret').value = '';
    document.getElementById('account-keywords').value = '';
    document.getElementById('account-style').value = 'news';
    document.getElementById('account-prompt').value = '';
}

// 隐藏公众号表单
function hideAccountForm() {
    document.getElementById('account-form').style.display = 'none';
    currentAccountId = null;
}

// 保存公众号
async function saveAccount() {
    const id = document.getElementById('account-id').value;
    const data = {
        name: document.getElementById('account-name').value,
        app_id: document.getElementById('account-appid').value,
        app_secret: document.getElementById('account-secret').value,
        topic_keywords: document.getElementById('account-keywords').value,
        style_preference: document.getElementById('account-style').value,
        custom_prompt: document.getElementById('account-prompt').value
    };

    if (!data.name || !data.app_id || !data.app_secret) {
        alert('请填写必填项');
        return;
    }

    try {
        const url = id ? `/api/accounts/${id}` : '/api/accounts';
        const method = id ? 'PUT' : 'POST';

        const resp = await fetch(url, {
            method: method,
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        const result = await resp.json();

        if (result.success) {
            alert('保存成功');
            hideAccountForm();
            loadAccounts();
        } else {
            alert('保存失败: ' + result.error);
        }
    } catch (e) {
        alert('保存失败: ' + e.message);
    }
}

// 编辑公众号
async function editAccount(accountId) {
    try {
        const resp = await fetch('/api/accounts');
        const data = await resp.json();
        const account = data.data.find(a => a.id === accountId);

        if (account) {
            currentAccountId = accountId;
            document.getElementById('form-title').textContent = '编辑公众号';
            document.getElementById('account-id').value = account.id;
            document.getElementById('account-name').value = account.name;
            document.getElementById('account-appid').value = account.app_id;
            document.getElementById('account-secret').value = account.app_secret;
            document.getElementById('account-keywords').value = account.topic_keywords || '';
            document.getElementById('account-style').value = account.style_preference || 'news';
            document.getElementById('account-prompt').value = account.custom_prompt || '';
            document.getElementById('account-form').style.display = 'block';
        }
    } catch (e) {
        alert('加载失败: ' + e.message);
    }
}

// 删除公众号
async function deleteAccount(accountId) {
    if (!confirm('确定删除此公众号配置？')) return;

    try {
        const resp = await fetch(`/api/accounts/${accountId}`, {method: 'DELETE'});
        const data = await resp.json();

        if (data.success) {
            alert('删除成功');
            loadAccounts();
        } else {
            alert('删除失败: ' + data.error);
        }
    } catch (e) {
        alert('删除失败: ' + e.message);
    }
}

// HTML转义
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== LLM渠道管理 ====================

let _providers = [];

async function loadProviders() {
    try {
        const resp = await fetch('/api/llm/providers');
        const data = await resp.json();
        if (data.success) {
            _providers = data.data || [];
            renderProviders();
            renderBindings();
        }
    } catch (e) {
        console.error('加载渠道失败:', e);
    }
}

function renderProviders() {
    const container = document.getElementById('providers-container');
    if (!container) return;
    if (_providers.length === 0) {
        container.innerHTML = '<div class="empty-state" style="padding:24px;text-align:center;color:#6b7280;">暂无模型渠道，请添加</div>';
        return;
    }
    container.innerHTML = _providers.map(p => `
        <div class="provider-card ${p.is_default ? 'provider-default' : ''}" style="border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin-bottom:12px;${p.is_default ? 'border-color:#10b981;background:#f0fdf4;' : ''}">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <div>
                    <strong>${escapeHtml(p.name)}</strong>
                    <span style="margin-left:8px;font-size:12px;padding:2px 8px;border-radius:4px;background:#f3f4f6;color:#6b7280;">${p.provider_type}</span>
                    ${p.is_default ? '<span style="margin-left:8px;font-size:12px;padding:2px 8px;border-radius:4px;background:#d1fae5;color:#059669;">默认</span>' : ''}
                </div>
                <div style="font-size:13px;color:#6b7280;">${escapeHtml(p.default_model)}</div>
            </div>
            <div style="display:flex;gap:8px;margin-top:8px;">
                <button class="btn btn-text btn-sm" onclick="SettingsPage.testProvider(${p.id})">🔍 测试</button>
                <button class="btn btn-text btn-sm" onclick="SettingsPage.editProvider(${p.id})">✏️ 编辑</button>
                ${!p.is_default ? `<button class="btn btn-text btn-sm" onclick="SettingsPage.setDefault(${p.id})">⭐ 默认</button>` : ''}
                <button class="btn btn-text btn-sm" style="color:#ef4444;" onclick="SettingsPage.deleteProvider(${p.id})">🗑️ 删除</button>
            </div>
        </div>
    `).join('');
}

function renderBindings() {
    const container = document.getElementById('bindings-container');
    if (!container || _providers.length === 0) {
        if (container) container.innerHTML = '';
        return;
    }
    const options = _providers.filter(p => p.is_active).map(p =>
        `<option value="${p.id}">${escapeHtml(p.name)} (${p.default_model})</option>`
    ).join('');

    container.innerHTML = `
        <h3 style="margin-bottom:12px;">功能模型绑定</h3>
        <div style="display:flex;flex-direction:column;gap:12px;">
            <div style="display:flex;align-items:center;gap:12px;">
                <label style="min-width:100px;font-weight:600;">内容分析</label>
                <select id="bind-content-analysis" class="form-control" style="flex:1;">
                    <option value="">使用默认渠道</option>${options}
                </select>
            </div>
            <div style="display:flex;align-items:center;gap:12px;">
                <label style="min-width:100px;font-weight:600;">文章生成</label>
                <select id="bind-article-generation" class="form-control" style="flex:1;">
                    <option value="">使用默认渠道</option>${options}
                </select>
            </div>
            <button class="btn btn-primary btn-sm" onclick="SettingsPage.saveBindings()" style="align-self:flex-start;">保存绑定</button>
        </div>
    `;
    loadBindingValues();
}

async function loadBindingValues() {
    try {
        const resp = await fetch('/api/llm/bindings');
        const data = await resp.json();
        if (data.success) {
            (data.data || []).forEach(b => {
                const sel = document.getElementById('bind-' + b.function_key);
                if (sel) sel.value = b.provider_id || '';
            });
        }
    } catch (e) {}
}

function showProviderForm(provider) {
    const isEdit = !!provider;
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:1000;';
    overlay.innerHTML = `
        <div style="background:#fff;border-radius:12px;max-width:500px;width:90%;max-height:90vh;overflow-y:auto;">
            <div style="padding:16px 24px;border-bottom:1px solid #e5e7eb;display:flex;justify-content:space-between;align-items:center;">
                <h3 style="margin:0;">${isEdit ? '编辑渠道' : '添加渠道'}</h3>
                <button style="background:none;border:none;font-size:20px;cursor:pointer;color:#6b7280;" onclick="this.closest('.modal-overlay').remove()">×</button>
            </div>
            <div style="padding:24px;">
                <div class="form-group"><label>渠道名称 *</label><input type="text" id="prov-name" class="form-control" value="${isEdit ? escapeHtml(provider.name) : ''}" placeholder="如：Anthropic主力"></div>
                <div class="form-group"><label>提供商类型</label>
                    <select id="prov-type" class="form-control" onchange="SettingsPage.onTypeChange()">
                        <option value="anthropic" ${isEdit && provider.provider_type === 'anthropic' ? 'selected' : ''}>Anthropic</option>
                        <option value="openai" ${isEdit && provider.provider_type === 'openai' ? 'selected' : ''}>OpenAI兼容</option>
                        <option value="ollama" ${isEdit && provider.provider_type === 'ollama' ? 'selected' : ''}>Ollama</option>
                    </select>
                </div>
                <div class="form-group"><label>API地址</label><input type="text" id="prov-url" class="form-control" value="${isEdit ? escapeHtml(provider.base_url || '') : ''}" placeholder="留空使用官方默认"></div>
                <div class="form-group" id="prov-key-group"><label>API密钥</label><input type="password" id="prov-key" class="form-control" value="${isEdit ? (provider.api_key || '') : ''}" placeholder="Ollama可留空"></div>
                <div class="form-group"><label>模型名称 *</label><input type="text" id="prov-model" class="form-control" value="${isEdit ? escapeHtml(provider.default_model) : ''}" placeholder="如：claude-sonnet-4-6"></div>
                <div class="form-group"><label>最大Token</label><input type="number" id="prov-tokens" class="form-control" value="${isEdit ? provider.max_tokens : 4000}"></div>
                <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px;">
                    <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">取消</button>
                    <button class="btn btn-primary" onclick="SettingsPage.saveProvider(${isEdit ? provider.id : 'null'})">${isEdit ? '保存' : '添加'}</button>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
    onTypeChange();
}

function onTypeChange() {
    const type = document.getElementById('prov-type');
    const keyGroup = document.getElementById('prov-key-group');
    const urlInput = document.getElementById('prov-url');
    if (!type) return;
    if (type.value === 'ollama') {
        if (keyGroup) keyGroup.style.display = 'none';
        if (urlInput && !urlInput.value) urlInput.value = 'http://localhost:11434/v1';
    } else {
        if (keyGroup) keyGroup.style.display = '';
        if (urlInput && urlInput.value === 'http://localhost:11434/v1') urlInput.value = '';
    }
}

async function saveProvider(id) {
    const data = {
        name: document.getElementById('prov-name').value.trim(),
        provider_type: document.getElementById('prov-type').value,
        base_url: document.getElementById('prov-url').value.trim(),
        api_key: document.getElementById('prov-key')?.value || '',
        default_model: document.getElementById('prov-model').value.trim(),
        max_tokens: parseInt(document.getElementById('prov-tokens').value) || 4000
    };
    if (!data.name || !data.default_model) { alert('名称和模型不能为空'); return; }
    try {
        const url = id ? `/api/llm/providers/${id}` : '/api/llm/providers';
        const resp = await fetch(url, { method: id ? 'PUT' : 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) });
        const result = await resp.json();
        if (result.success) {
            document.querySelector('.modal-overlay')?.remove();
            loadProviders();
        } else { alert('保存失败: ' + result.error); }
    } catch (e) { alert('保存失败: ' + e.message); }
}

async function editProvider(id) {
    const p = _providers.find(x => x.id === id);
    if (p) showProviderForm(p);
}

async function testProvider(id) {
    const btn = event.target;
    btn.disabled = true; btn.textContent = '测试中...';
    try {
        const resp = await fetch(`/api/llm/providers/${id}/test`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const result = await resp.json();
        alert(result.success ? `连接成功 (${result.data.elapsed}秒)` : '连接失败: ' + result.error);
    } catch (e) { alert('测试失败: ' + e.message); }
    btn.disabled = false; btn.textContent = '🔍 测试';
}

async function deleteProvider(id) {
    if (!confirm('确定删除该渠道吗？')) return;
    try {
        const resp = await fetch(`/api/llm/providers/${id}`, { method: 'DELETE' });
        const result = await resp.json();
        if (result.success) { loadProviders(); } else { alert('删除失败: ' + result.error); }
    } catch (e) { alert('删除失败: ' + e.message); }
}

async function setDefault(id) {
    try {
        const resp = await fetch(`/api/llm/providers/${id}/default`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const result = await resp.json();
        if (result.success) loadProviders();
    } catch (e) { alert('设置失败: ' + e.message); }
}

async function saveBindings() {
    const bindings = [
        { function_key: 'content_analysis', provider_id: parseInt(document.getElementById('bind-content-analysis')?.value) || null },
        { function_key: 'article_generation', provider_id: parseInt(document.getElementById('bind-article-generation')?.value) || null }
    ].filter(b => b.provider_id);
    try {
        const resp = await fetch('/api/llm/bindings', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(bindings) });
        const result = await resp.json();
        alert(result.success ? '绑定已保存' : '保存失败: ' + result.error);
    } catch (e) { alert('保存失败: ' + e.message); }
}

// 导出公共接口
window.settingsPage = {
    render: initSettingsPage,
    init: initSettingsPage,
    showAccountForm,
    hideAccountForm,
    saveAccount,
    editAccount,
    deleteAccount
};

window.SettingsPage = {
    showProviderForm: () => showProviderForm(null),
    editProvider,
    testProvider,
    deleteProvider,
    setDefault,
    saveProvider,
    saveBindings,
    onTypeChange
};

})();
