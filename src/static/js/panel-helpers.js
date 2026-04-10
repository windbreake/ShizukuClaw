/**
 * 控制面板助手函数
 * 提供统一的 API 调用、错误处理和缺省数据
 */

// 统一的 API 调用包装
async function callPanelApi(url, options = {}) {
    const defaultOptions = {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
        timeout: 5000
    };
    const mergedOptions = { ...defaultOptions, ...options };
    
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), mergedOptions.timeout);
        
        const response = await fetch(url, {
            ...mergedOptions,
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok && response.status !== 404) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error(`API call failed: ${url}`, error);
        return { code: -1, message: error.message, data: null, success: false };
    }
}

// 为空内容渲染占位符
function renderEmptyState(container, options = {}) {
    const {
        icon = 'fa-inbox',
        title = '暂无数据',
        message = '这里现在还没有任何内容',
        action = null
    } = options;
    
    if (typeof container === 'string') {
        container = document.getElementById(container);
    }
    
    if (!container) return;
    
    let html = `
        <div class="text-center py-5">
            <div class="mb-3">
                <i class="fas ${icon} fa-3x text-muted opacity-50"></i>
            </div>
            <h5 class="text-muted">${title}</h5>
            <p class="text-muted small">${message}</p>
    `;
    
    if (action) {
        html += `
            <div class="mt-3">
                <button class="btn btn-sm btn-outline-primary">${action.label}</button>
            </div>
        `;
    }
    
    html += '</div>';
    container.innerHTML = html;
}

// 任务管理 - 改进版
async function loadTaskManager_Enhanced() {
    try {
        const res = await callPanelApi('/api/systems/tasks');
        const tasks = (res.code === 0 && Array.isArray(res.data)) ? res.data : [];
        
        const body = document.getElementById('tasks-body');
        const badge = document.getElementById('task-count-badge');
        
        if (badge) badge.textContent = tasks.length;
        if (!body) return;
        
        if (!tasks.length) {
            body.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center text-muted py-4">
                        <div class="mb-2">
                            <i class="fas fa-tasks fa-2x opacity-50"></i>
                        </div>
                        <div class="small">暂无任务 - 点击上方创建新任务</div>
                    </td>
                </tr>
            `;
            return;
        }
        
        body.innerHTML = tasks.map(task => `
            <tr>
                <td>${escapeHtml(task.name || '')}</td>
                <td><span class="badge bg-light text-dark border">${escapeHtml(task.task_type || 'one_time')}</span></td>
                <td><span class="badge ${task.status === 'completed' ? 'bg-success' : task.status === 'failed' ? 'bg-danger' : 'bg-secondary'}">${escapeHtml(task.status || 'pending')}</span></td>
                <td class="small text-muted">${escapeHtml(task.next_run_time || task.scheduled_time || '-')}</td>
                <td><button class="btn btn-sm btn-outline-danger" onclick="deleteTaskById('${escapeHtml(task.id)}')"><i class="fas fa-trash"></i></button></td>
            </tr>
        `).join('');
    } catch (e) {
        console.error('Failed to load tasks:', e);
        const body = document.getElementById('tasks-body');
        if (body) {
            body.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center text-danger py-4 small">
                        加载失败: ${escapeHtml(e.message)}
                    </td>
                </tr>
            `;
        }
    }
}

// MCP 管理 - 改进版
async function loadMcpManager_Enhanced() {
    try {
        const res = await callPanelApi('/api/systems/mcp');
        const servers = (res.code === 0 && Array.isArray(res.data)) ? res.data : [];
        
        const container = document.getElementById('mcp-servers-list');
        if (!container) return;

        if (!servers.length) {
            container.innerHTML = `
                <div class="alert alert-info alert-dismissible fade show" role="alert">
                    <i class="fas fa-info-circle me-2"></i>
                    <strong>暂无 MCP 服务器</strong>
                    <p class="small mt-2 mb-0">
                        点击下方"快速创建"或从市场安装服务器，扩展系统能力。
                    </p>
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            `;
            return;
        }

        container.innerHTML = servers.map(server => `
            <div class="card mb-2">
                <div class="card-body p-3">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h6 class="mb-1">${escapeHtml(server.name || 'MCP Server')}</h6>
                            <small class="text-muted">${escapeHtml(server.description || '')}</small>
                        </div>
                        <span class="badge bg-success">运行中</span>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.error('Failed to load MCP servers:', e);
        const container = document.getElementById('mcp-servers-list');
        if (container) {
            container.innerHTML = `<div class="alert alert-warning small">加载 MCP 服务器失败: ${escapeHtml(e.message)}</div>`;
        }
    }
}

// 知识库 - 改进版
async function loadKnowledgeManager_Enhanced() {
    try {
        const res = await callPanelApi('/api/systems/knowledge');
        const items = (res.code === 0 && Array.isArray(res.data)) ? res.data : [];
        
        const body = document.getElementById('knowledge-body');
        if (!body) return;

        if (!items.length) {
            body.innerHTML = `
                <div class="text-center py-5">
                    <i class="fas fa-book fa-3x text-muted opacity-50 mb-3 d-block"></i>
                    <h6 class="text-muted">知识库为空</h6>
                    <small class="text-muted">导入文档或手动添加知识条目来建立知识库</small>
                </div>
            `;
            return;
        }

        body.innerHTML = items.map(item => `
            <div class="card mb-2">
                <div class="card-header py-2">
                    <div class="d-flex justify-content-between align-items-center">
                        <span class="small fw-bold">${escapeHtml(item.title || 'Entry')}</span>
                        <button class="btn btn-xs btn-outline-danger" onclick="deleteKnowledgeEntryById('${escapeHtml(item.id)}')">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.error('Failed to load knowledge:', e);
        const body = document.getElementById('knowledge-body');
        if (body) {
            body.innerHTML = `<div class="alert alert-warning small">加载失败: ${escapeHtml(e.message)}</div>`;
        }
    }
}

// 插件管理 - 改进版 (使用 loadPluginStatus 现有逻辑)
async function loadPluginStatus_Safe() {
    try {
        const res = await callPanelApi('/api/systems/plugins');
        const plugins = (res.code === 0 && Array.isArray(res.data)) ? res.data : [];
        
        const container = document.getElementById('plugin-cards-container');
        if (!container) return;

        if (!plugins.length) {
            container.innerHTML = `
                <div class="text-center py-5">
                    <i class="fas fa-puzzle-piece fa-3x text-muted opacity-50 mb-3 d-block"></i>
                    <h6 class="text-muted">暂无插件</h6>
                    <small class="text-muted">上传或安装插件来扩展功能</small>
                </div>
            `;
            return;
        }

        renderPluginCards(plugins);
    } catch (e) {
        console.error('Failed to load plugins:', e);
        const container = document.getElementById('plugin-cards-container');
        if (container) {
            container.innerHTML = `<div class="alert alert-warning small">加载插件失败: ${escapeHtml(e.message)}</div>`;
        }
    }
}

// 技能管理 - 改进版
async function loadSkillStatus_Safe() {
    try {
        const res = await callPanelApi('/api/systems/skills');
        const skills = (res.code === 0 && Array.isArray(res.data)) ? res.data : [];
        
        const container = document.getElementById('skill-cards-container');
        if (!container) return;

        if (!skills.length) {
            container.innerHTML = `
                <div class="text-center py-5">
                    <i class="fas fa-wand-magic-sparkles fa-3x text-muted opacity-50 mb-3 d-block"></i>
                    <h6 class="text-muted">暂无技能</h6>
                    <small class="text-muted">上传或从市场安装技能来增强功能</small>
                </div>
            `;
            return;
        }

        renderSkillCards(skills);
    } catch (e) {
        console.error('Failed to load skills:', e);
        const container = document.getElementById('skill-cards-container');
        if (container) {
            container.innerHTML = `<div class="alert alert-warning small">加载技能失败: ${escapeHtml(e.message)}</div>`;
        }
    }
}

// 指令管理 - 改进版
async function loadInstructionManager_Enhanced() {
    try {
        const res = await callPanelApi('/api/systems/instructions');
        const instructions = (res.code === 0 && Array.isArray(res.data)) ? res.data : [];
        
        const body = document.getElementById('instructions-body');
        if (!body) return;

        if (!instructions.length) {
            body.innerHTML = `
                <div class="text-center py-5">
                    <i class="fas fa-scroll fa-3x text-muted opacity-50 mb-3 d-block"></i>
                    <h6 class="text-muted">暂无自定义指令</h6>
                    <small class="text-muted">添加自定义指令来定制系统行为</small>
                </div>
            `;
            return;
        }

        body.innerHTML = instructions.map(instr => `
            <div class="card mb-2">
                <div class="card-body p-3">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h6 class="mb-1 text-monospace small">${escapeHtml(instr.name || 'instruction')}</h6>
                            <small class="text-muted">${escapeHtml(instr.description || '')}</small>
                        </div>
                        <button class="btn btn-xs btn-outline-danger">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.error('Failed to load instructions:', e);
        const body = document.getElementById('instructions-body');
        if (body) {
            body.innerHTML = `<div class="alert alert-warning small">加载失败: ${escapeHtml(e.message)}</div>`;
        }
    }
}

// 导出这些函数供 HTML 中使用
if (typeof window !== 'undefined') {
    window.panelHelpers = {
        callPanelApi,
        renderEmptyState,
        loadTaskManager_Enhanced,
        loadMcpManager_Enhanced,
        loadKnowledgeManager_Enhanced,
        loadPluginStatus_Safe,
        loadSkillStatus_Safe,
        loadInstructionManager_Enhanced
    };
}
