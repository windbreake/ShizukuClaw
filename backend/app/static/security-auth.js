/**
 * Shizuku 两层安全认证系统
 * 提供弹窗式密码输入和确认
 */

class SecurityAuth {
    constructor() {
        this.level1SessionId = null;
        this.level2SessionId = null;
        this.securityLevel = 0;  // 0=沙箱, 1=工作模式, 2=全局管理
    }

    /**
     * 显示 Level 1 认证弹窗 (工作模式)
     */
    async showLevel1Dialog() {
        return new Promise((resolve, reject) => {
            const dialog = document.createElement('div');
            dialog.id = 'level1-auth-modal';
            dialog.className = 'security-modal';
            dialog.innerHTML = `
                <div class="modal-overlay"></div>
                <div class="modal-content">
                    <div class="modal-header">
                        🔐 工作模式认证 (Level 1)
                    </div>
                    <div class="modal-body">
                        <p class="modal-description">
                            您正在请求进入 <strong>工作模式</strong>。
                            此模式允许对 workspace 目录进行文件操作。
                        </p>

                        <div class="form-group">
                            <label for="l1-password">工作模式密码:</label>
                            <input 
                                type="password" 
                                id="l1-password" 
                                class="form-input" 
                                placeholder="输入工作模式密码" 
                                autocomplete="off"
                            />
                        </div>

                        <div class="risk-warning">
                            ⚠️ <strong>风险提示:</strong> 
                            此模式下的代码将能够访问 workspace 目录内的文件。
                            请确保您信任要执行的代码。
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" id="l1-cancel">取消</button>
                        <button class="btn btn-primary" id="l1-confirm">进入工作模式</button>
                    </div>
                </div>
            `;

            document.body.appendChild(dialog);
            this._addSecurityModalStyles();

            const inputField = document.getElementById('l1-password');
            const confirmBtn = document.getElementById('l1-confirm');
            const cancelBtn = document.getElementById('l1-cancel');

            inputField.focus();

            const clearDialog = () => {
                dialog.remove();
            };

            confirmBtn.onclick = async () => {
                const password = inputField.value;
                if (!password) {
                    alert('请输入密码');
                    return;
                }

                try {
                    const response = await fetch('/api/security/authenticate/level1', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ password })
                    });

                    if (response.ok) {
                        const data = await response.json();
                        this.level1SessionId = data.session_id;
                        this.securityLevel = 1;
                        clearDialog();
                        resolve(true);
                    } else {
                        alert('密码错误，请重试');
                        inputField.value = '';
                        inputField.focus();
                    }
                } catch (err) {
                    alert(`认证失败: ${err.message}`);
                    reject(err);
                }
            };

            cancelBtn.onclick = () => {
                clearDialog();
                resolve(false);
            };

            inputField.onkeypress = (e) => {
                if (e.key === 'Enter') confirmBtn.click();
            };
        });
    }

    /**
     * 显示 Level 2 认证弹窗 (全局管理模式)
     */
    async showLevel2Dialog() {
        if (!this.level1SessionId) {
            alert('必须先完成 Level 1 认证');
            return false;
        }

        return new Promise((resolve, reject) => {
            const dialog = document.createElement('div');
            dialog.id = 'level2-auth-modal';
            dialog.className = 'security-modal';
            dialog.innerHTML = `
                <div class="modal-overlay"></div>
                <div class="modal-content">
                    <div class="modal-header">
                        🚨 全局管理模式认证 (Level 2)
                    </div>
                    <div class="modal-body">
                        <div class="alert alert-danger">
                            <strong>⚠️ 重大风险警告:</strong>
                            <p>
                                您正在请求进入 <strong style="color: red;">全局管理模式</strong>。
                                此模式下的代码将能够：
                            </p>
                            <ul style="margin-left: 20px;">
                                <li>访问整个系统文件系统</li>
                                <li>执行任意系统命令</li>
                                <li>修改系统配置</li>
                                <li>导致系统安全漏洞</li>
                            </ul>
                            <p><strong>仅在您完全信任要执行的代码时才启用此模式。</strong></p>
                        </div>

                        <div class="form-group">
                            <label for="l2-password">全局管理密码:</label>
                            <input 
                                type="password" 
                                id="l2-password" 
                                class="form-input" 
                                placeholder="输入全局管理密码" 
                                autocomplete="off"
                            />
                        </div>

                        <div class="form-group">
                            <label for="l2-checkbox" class="checkbox-label">
                                <input 
                                    type="checkbox" 
                                    id="l2-checkbox" 
                                    class="form-checkbox"
                                />
                                <span>我已知晓其风险并开启该模式</span>
                            </label>
                        </div>

                        <div class="form-group">
                            <label for="l2-text-input">请输入文本框内容确认:</label>
                            <div class="confirm-text-container">
                                <span class="required-text">我已知晓其风险并开启该模式</span>
                            </div>
                            <input 
                                type="text" 
                                id="l2-text-input" 
                                class="form-input" 
                                placeholder="请完整输入上方文本以确认" 
                                autocomplete="off"
                            />
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" id="l2-cancel">取消</button>
                        <button class="btn btn-danger" id="l2-confirm" disabled>启用全局管理模式</button>
                    </div>
                </div>
            `;

            document.body.appendChild(dialog);
            this._addSecurityModalStyles();

            const passwordInput = document.getElementById('l2-password');
            const checkbox = document.getElementById('l2-checkbox');
            const textInput = document.getElementById('l2-text-input');
            const confirmBtn = document.getElementById('l2-confirm');
            const cancelBtn = document.getElementById('l2-cancel');

            passwordInput.focus();

            // 需要满足三个条件才能启用确认按钮
            const updateConfirmBtn = () => {
                const isCheckboxChecked = checkbox.checked;
                const isTextMatches = textInput.value === '我已知晓其风险并开启该模式';
                const hasPassword = passwordInput.value.length > 0;
                
                confirmBtn.disabled = !(isCheckboxChecked && isTextMatches && hasPassword);
            };

            passwordInput.oninput = updateConfirmBtn;
            checkbox.onchange = updateConfirmBtn;
            textInput.oninput = updateConfirmBtn;

            const clearDialog = () => {
                dialog.remove();
            };

            confirmBtn.onclick = async () => {
                if (confirmBtn.disabled) {
                    alert('请满足所有条件');
                    return;
                }

                try {
                    const response = await fetch('/api/security/authenticate/level2', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            session_id: this.level1SessionId,
                            password: passwordInput.value
                        })
                    });

                    if (response.ok) {
                        const data = await response.json();
                        this.level2SessionId = data.session_id;
                        this.securityLevel = 2;
                        clearDialog();
                        resolve(true);
                    } else {
                        alert('认证失败，请检查密码和条件');
                    }
                } catch (err) {
                    alert(`认证失败: ${err.message}`);
                    reject(err);
                }
            };

            cancelBtn.onclick = () => {
                clearDialog();
                resolve(false);
            };

            passwordInput.onkeypress = (e) => {
                if (e.key === 'Enter' && !confirmBtn.disabled) confirmBtn.click();
            };
        });
    }

    /**
     * 执行代码 (带安全级别)
     */
    async executeCode(code, language = 'python', securityLevel = 0) {
        const sessionId = securityLevel === 1 ? this.level1SessionId : 
                          securityLevel === 2 ? this.level2SessionId : null;

        if ((securityLevel === 1 || securityLevel === 2) && !sessionId) {
            alert(`需要 Level ${securityLevel} 认证会话`);
            return null;
        }

        try {
            const response = await fetch('/api/security/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code,
                    language,
                    security_level: securityLevel,
                    session_id: sessionId
                })
            });

            if (response.ok) {
                return await response.json();
            } else {
                const error = await response.json();
                alert(`执行失败: ${error.error}`);
                return null;
            }
        } catch (err) {
            alert(`执行错误: ${err.message}`);
            return null;
        }
    }

    /**
     * 添加 CSS 样式
     */
    _addSecurityModalStyles() {
        if (document.getElementById('security-modal-styles')) return;

        const style = document.createElement('style');
        style.id = 'security-modal-styles';
        style.textContent = `
            .security-modal {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                z-index: 10000;
                display: flex;
                align-items: center;
                justify-content: center;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }

            .security-modal .modal-overlay {
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.6);
                z-index: -1;
            }

            .security-modal .modal-content {
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                max-width: 520px;
                width: 90%;
                max-height: 80vh;
                overflow-y: auto;
                z-index: 1;
            }

            .security-modal .modal-header {
                padding: 20px 24px;
                border-bottom: 1px solid #e5e7eb;
                font-size: 18px;
                font-weight: 600;
                color: #1f2937;
            }

            .security-modal .modal-body {
                padding: 24px;
            }

            .security-modal .modal-description {
                margin: 0 0 16px;
                color: #6b7280;
                font-size: 14px;
                line-height: 1.6;
            }

            .security-modal .form-group {
                margin-bottom: 16px;
            }

            .security-modal .form-group label {
                display: block;
                margin-bottom: 8px;
                font-weight: 500;
                color: #374151;
                font-size: 14px;
            }

            .security-modal .form-input {
                width: 100%;
                padding: 10px 12px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                font-size: 14px;
                font-family: inherit;
                transition: all 0.3s ease;
                box-sizing: border-box;
            }

            .security-modal .form-input:focus {
                outline: none;
                border-color: #3b82f6;
                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
            }

            .security-modal .form-input:disabled {
                background-color: #f3f4f6;
                color: #9ca3af;
                cursor: not-allowed;
            }

            .security-modal .checkbox-label {
                display: flex;
                align-items: center;
                font-weight: 400;
                color: #374151;
                cursor: pointer;
                user-select: none;
            }

            .security-modal .form-checkbox {
                margin-right: 8px;
                cursor: pointer;
                accent-color: #ef4444;
            }

            .security-modal .risk-warning {
                padding: 12px 16px;
                background: #fef2f2;
                border-left: 4px solid #fca5a5;
                border-radius: 4px;
                font-size: 14px;
                color: #7f1d1d;
                margin: 16px 0;
            }

            .security-modal .alert {
                padding: 16px;
                border-radius: 6px;
                margin-bottom: 16px;
                font-size: 14px;
            }

            .security-modal .alert-danger {
                background: #fee2e2;
                border: 1px solid #fca5a5;
                color: #7f1d1d;
            }

            .security-modal .alert ul {
                margin: 8px 0;
                padding-left: 20px;
            }

            .security-modal .alert li {
                margin: 4px 0;
            }

            .security-modal .confirm-text-container {
                padding: 10px 12px;
                background: #f3f4f6;
                border-radius: 6px;
                border: 1px dashed #d1d5db;
                font-family: 'Monaco', 'Courier New', monospace;
                font-size: 13px;
                color: #374151;
                margin-bottom: 8px;
                word-break: break-all;
            }

            .security-modal .required-text {
                font-weight: 500;
                color: #1f2937;
            }

            .security-modal .modal-footer {
                padding: 16px 24px;
                border-top: 1px solid #e5e7eb;
                display: flex;
                justify-content: flex-end;
                gap: 12px;
            }

            .security-modal .btn {
                padding: 10px 16px;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.3s ease;
                font-family: inherit;
            }

            .security-modal .btn-secondary {
                background: #e5e7eb;
                color: #374151;
            }

            .security-modal .btn-secondary:hover {
                background: #d1d5db;
            }

            .security-modal .btn-primary {
                background: #3b82f6;
                color: white;
            }

            .security-modal .btn-primary:hover:not(:disabled) {
                background: #2563eb;
            }

            .security-modal .btn-danger {
                background: #ef4444;
                color: white;
            }

            .security-modal .btn-danger:hover:not(:disabled) {
                background: #dc2626;
            }

            .security-modal .btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
        `;

        document.head.appendChild(style);
    }
}

// 导出全局实例
window.SecurityAuth = new SecurityAuth();
