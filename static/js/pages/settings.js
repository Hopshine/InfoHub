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

                <!-- AI参数配置 -->
                <div class="settings-section">
                    <div class="section-header">
                        <h2>AI参数配置</h2>
                    </div>
                    <div class="config-card">
                        <div class="form-group">
                            <label>模型选择</label>
                            <select class="form-control">
                                <option>GPT-4</option>
                                <option>GPT-3.5</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>温度参数</label>
                            <input type="range" min="0" max="1" step="0.1" value="0.7" class="form-control">
                        </div>
                        <button class="btn btn-primary">保存配置</button>
                    </div>
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

})();
