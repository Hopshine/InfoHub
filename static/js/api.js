// API调用封装模块

/**
 * 统一API调用封装
 * 提供所有后端API端点的封装方法，统一错误处理和Loading状态管理
 */

// ==================== 基础请求封装 ====================

/**
 * 基础fetch封装
 * @param {string} url - 请求URL
 * @param {Object} options - fetch选项
 * @returns {Promise} 返回Promise
 */
async function request(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error('API请求失败:', url, error);
        throw error;
    }
}

// ==================== API对象 ====================

const API = {
    // ==================== 统计信息 ====================
    stats: {
        /**
         * 获取统计信息
         * @returns {Promise} 返回统计数据
         */
        get: () => request('/api/stats')
    },

    // ==================== 文章管理 ====================
    articles: {
        /**
         * 获取文章列表
         * @param {number} page - 页码
         * @param {number} limit - 每页数量
         * @returns {Promise} 返回文章列表
         */
        list: (page = 1, limit = 20) => request(`/api/articles?page=${page}&limit=${limit}`),

        /**
         * 获取单篇文章详情
         * @param {number} id - 文章ID
         * @returns {Promise} 返回文章详情
         */
        get: (id) => request(`/api/article/${id}`),

        /**
         * 删除单篇文章
         * @param {number} id - 文章ID
         * @returns {Promise} 返回删除结果
         */
        delete: (id) => request(`/api/article/${id}`, { method: 'DELETE' }),

        /**
         * 批量删除文章
         * @param {Array<number>} ids - 文章ID数组
         * @returns {Promise} 返回删除结果
         */
        deleteBatch: (ids) => request('/api/articles/delete', {
            method: 'POST',
            body: JSON.stringify({ article_ids: ids })
        })
    },

    // ==================== 内容分析 ====================
    analyze: {
        /**
         * 分析单篇文章
         * @param {number} id - 文章ID
         * @returns {Promise} 返回分析结果
         */
        single: (id) => request(`/api/analyze/${id}`, { method: 'POST' }),

        /**
         * 批量分析文章
         * @param {number} limit - 分析数量限制
         * @returns {Promise} 返回批量分析结果
         */
        batch: (limit = 10) => request('/api/analyze/batch', {
            method: 'POST',
            body: JSON.stringify({ limit })
        })
    },

    // ==================== 内容采集 ====================
    collect: {
        /**
         * 采集单个URL
         * @param {string} url - 文章URL
         * @returns {Promise} 返回采集结果
         */
        url: (url) => request('/api/collect/url', {
            method: 'POST',
            body: JSON.stringify({ url })
        }),

        /**
         * 批量采集URL
         * @param {Array<string>} urls - URL数组
         * @returns {Promise} 返回批量采集结果
         */
        batch: (urls) => request('/api/collect/batch', {
            method: 'POST',
            body: JSON.stringify({ urls })
        }),

        /**
         * 搜索采集
         * @param {string} keyword - 搜索关键词
         * @param {number} count - 采集数量
         * @returns {Promise} 返回搜索采集结果
         */
        search: (keyword, count = 10) => request('/api/collect/search', {
            method: 'POST',
            body: JSON.stringify({ keyword, max_results: count })
        })
    },

    // ==================== 爬虫任务 ====================
    crawl: {
        /**
         * 启动爬虫任务
         * @param {Object} config - 爬虫配置
         * @returns {Promise} 返回任务ID
         */
        start: (config) => request('/api/crawl/start', {
            method: 'POST',
            body: JSON.stringify(config)
        }),

        /**
         * 获取任务进度
         * @param {string} jobId - 任务ID
         * @returns {Promise} 返回任务进度
         */
        progress: (jobId) => request(`/api/crawl/progress/${jobId}`),

        /**
         * 取消任务
         * @param {string} jobId - 任务ID
         * @returns {Promise} 返回取消结果
         */
        cancel: (jobId) => request(`/api/crawl/cancel/${jobId}`, { method: 'POST' }),

        /**
         * 获取任务流式进度（SSE）
         * @param {string} jobId - 任务ID
         * @param {Function} onMessage - 消息回调
         * @param {Function} onError - 错误回调
         * @returns {EventSource} 返回EventSource对象
         */
        stream: (jobId, onMessage, onError) => {
            const eventSource = new EventSource(`/api/crawl/stream/${jobId}`);
            eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (onMessage) onMessage(data);
                } catch (e) {
                    console.error('解析SSE消息失败:', e);
                }
            };
            eventSource.onerror = (error) => {
                console.error('SSE连接错误:', error);
                eventSource.close();
                if (onError) onError(error);
            };
            return eventSource;
        }
    },

    // ==================== 热点监控 ====================
    trending: {
        /**
         * 获取热点数据
         * @returns {Promise} 返回热点数据
         */
        get: () => request('/api/trending'),

        /**
         * 刷新热点数据
         * @returns {Promise} 返回刷新结果
         */
        refresh: () => request('/api/trending/refresh', { method: 'POST' }),

        /**
         * 获取监控状态
         * @returns {Promise} 返回监控状态
         */
        status: () => request('/api/trending/status'),

        /**
         * 采集热点文章到文章库
         * @param {Array<Object>} items - 热点条目数组
         * @returns {Promise} 返回采集结果
         */
        collect: (items) => request('/api/trending/collect', {
            method: 'POST',
            body: JSON.stringify({ ids: items })
        })
    },

    // ==================== 文章生成 ====================
    generate: {
        /**
         * 生成文章
         * @param {Object} config - 生成配置
         * @returns {Promise} 返回生成结果
         */
        article: (config) => request('/api/generate', {
            method: 'POST',
            body: JSON.stringify(config)
        })
    },

    // ==================== 文章发布 ====================
    publish: {
        /**
         * 发布文章
         * @param {Object} config - 发布配置
         * @returns {Promise} 返回发布结果
         */
        article: (config) => request('/api/publish', {
            method: 'POST',
            body: JSON.stringify(config)
        })
    },

    // ==================== 草稿和已发布 ====================
    drafts: {
        /**
         * 获取草稿列表
         * @returns {Promise} 返回草稿列表
         */
        list: () => request('/api/drafts')
    },

    published: {
        /**
         * 获取已发布列表
         * @returns {Promise} 返回已发布列表
         */
        list: () => request('/api/published')
    },

    // ==================== 账号管理 ====================
    accounts: {
        /**
         * 获取账号列表
         * @returns {Promise} 返回账号列表
         */
        list: () => request('/api/accounts'),

        /**
         * 添加账号
         * @param {Object} account - 账号信息
         * @returns {Promise} 返回添加结果
         */
        add: (account) => request('/api/accounts', {
            method: 'POST',
            body: JSON.stringify(account)
        }),

        /**
         * 更新账号
         * @param {number} id - 账号ID
         * @param {Object} account - 账号信息
         * @returns {Promise} 返回更新结果
         */
        update: (id, account) => request(`/api/accounts/${id}`, {
            method: 'PUT',
            body: JSON.stringify(account)
        }),

        /**
         * 删除账号
         * @param {number} id - 账号ID
         * @returns {Promise} 返回删除结果
         */
        delete: (id) => request(`/api/accounts/${id}`, { method: 'DELETE' })
    },

    // ==================== 工作流管理 ====================
    workflow: {
        /**
         * 启动工作流
         * @param {Object} config - 工作流配置
         * @returns {Promise} 返回启动结果
         */
        start: (config) => request('/api/workflow/start', {
            method: 'POST',
            body: JSON.stringify(config)
        }),

        /**
         * 获取待审核任务
         * @returns {Promise} 返回待审核任务列表
         */
        pending: () => request('/api/workflow/pending'),

        /**
         * 提交审核决策
         * @param {string} threadId - 线程ID
         * @param {string} decision - 决策（approve/reject）
         * @returns {Promise} 返回提交结果
         */
        review: (threadId, decision) => request('/api/workflow/review', {
            method: 'POST',
            body: JSON.stringify({ thread_id: threadId, decision })
        }),

        /**
         * 获取工作流可视化数据
         * @returns {Promise} 返回可视化数据
         */
        visualization: () => request('/api/workflow/visualization')
    }
};

// ==================== 带Loading的API调用包装器 ====================

/**
 * 带Loading状态的API调用
 * @param {Function} apiCall - API调用函数
 * @param {string} loadingContainerId - Loading容器ID（可选）
 * @param {string} loadingMessage - Loading提示文本
 * @returns {Promise} 返回API调用结果
 */
async function apiWithLoading(apiCall, loadingContainerId = null, loadingMessage = '加载中...') {
    if (loadingContainerId && typeof showLoading === 'function') {
        showLoading(loadingContainerId, loadingMessage);
    }

    try {
        const result = await apiCall();
        return result;
    } catch (error) {
        if (typeof showToast === 'function') {
            showToast(`请求失败: ${error.message}`, 'error');
        }
        throw error;
    } finally {
        if (loadingContainerId && typeof hideLoading === 'function') {
            hideLoading(loadingContainerId);
        }
    }
}

// ==================== 导出 ====================

// 兼容模块化和全局使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { API, apiWithLoading };
}
