/**
 * Plugin UI Extensions Loader
 * 
 * Dynamically loads and renders UI extensions from plugins.
 * Ensures safe integration without modifying core system.
 */

class PluginUILoader {
    constructor() {
        this.extensions = null;
        this.loaded = false;
    }
    
    /**
     * Initialize and load all plugin UI extensions
     */
    async initialize() {
        if (this.loaded) return;
        
        try {
            console.log('[PluginUI] ===== Plugin UI Loader initializing =====');
            
            // Load all extensions
            await this.loadExtensions();
            
            // Render different UI components
            await this.renderMenuItems();
            await this.renderSettingSections();
            await this.renderWidgets();
            await this.registerPages();
            await this.registerModals();
            
            // Hook into native Bootstrap tab system: hide all plugin panes when a native tab is shown
            this._hookTabSystem();
            
            this.loaded = true;
            console.log('[PluginUI] ===== UI extensions loaded successfully =====');
        } catch (error) {
            console.error('[PluginUI] Failed to load UI extensions:', error);
        }
    }
    
    /**
     * Hook into the native Bootstrap tab/pill system.
     * When a native (non-plugin) tab is activated, hide all plugin tab panes.
     */
    _hookTabSystem() {
        document.addEventListener('shown.bs.tab', (e) => {
            var targetId = e.target.id || '';
            // Only react to native tab links (IDs starting with 'v-', not plugin ones)
            if (targetId.startsWith('v-') && !targetId.startsWith('v-plugin-')) {
                console.log('[PluginUI] Native tab shown: ' + targetId + ', hiding plugin panes');
                var pluginPanes = document.querySelectorAll('#v-pills-tabContent .tab-pane[id^="tab-plugin-"]');
                pluginPanes.forEach(function(pane) {
                    pane.classList.remove('show', 'active');
                });
            }
        });
    }
    
    /**
     * Load all UI extensions from API
     */
    async loadExtensions() {
        console.log('[PluginUI] Fetching /api/plugins/ui-extensions ...');
        const response = await fetch('/api/plugins/ui-extensions');
        const data = await response.json();
        console.log('[PluginUI] API response success=' + data.success + ', extensions keys:', Object.keys(data.extensions || {}));
        
        if (data.success) {
            this.extensions = data.extensions;
        } else {
            throw new Error(data.error || 'Failed to load extensions');
        }
    }
    
    /**
     * Render menu items in the navigation
     */
    async renderMenuItems() {
        if (!this.extensions || !this.extensions.menu_items) {
            console.log('[PluginUI] No extensions or menu_items found, skipping menu render');
            return;
        }
        
        const menuItems = this.extensions.menu_items;
        console.log('[PluginUI] Got ' + menuItems.length + ' menu items:', menuItems.map(function(m) { return m.id; }));
        if (menuItems.length === 0) return;
        
        // Find the main navigation container - support ShizukuClaw's structure
        const navContainer = document.querySelector('#v-pills-tab') || 
                            document.querySelector('#main-nav') || 
                            document.querySelector('.sidebar-nav') ||
                            document.querySelector('[data-role="navigation"]') ||
                            document.querySelector('.nav.flex-column');
        
        if (!navContainer) {
            console.warn('[PluginUI] Navigation container not found');
            return;
        }
        
        console.log(`[PluginUI] Rendering ${menuItems.length} menu items`);
        
        // Group items by parent
        const rootItems = menuItems.filter(item => !item.parent_id);
        const childItems = menuItems.filter(item => item.parent_id);
        
        // For ShizukuClaw: Create a "插件页面" nav-group to contain all plugin menus
        const pluginGroup = this.createPluginGroup(rootItems, childItems);
        
        // Insert before "系统运维中心" or at the end
        const opsGroup = document.querySelector('#ops-nav-group');
        if (opsGroup) {
            navContainer.insertBefore(pluginGroup, opsGroup);
        } else {
            navContainer.appendChild(pluginGroup);
        }
        
        console.log('[PluginUI] Plugin menu group added successfully');
    }
    
    /**
     * Create a "插件页面" nav-group containing all plugin menu items
     */
    createPluginGroup(rootItems, childItems) {
        const group = document.createElement('div');
        group.className = 'nav-group';
        group.id = 'plugins-nav-group';
        
        // Create header - match ShizukuClaw structure
        const header = document.createElement('div');
        header.className = 'nav-group-header';
        
        // Label (div, not a link) - clickable to toggle submenu
        const label = document.createElement('div');
        label.className = 'nav-link nav-group-label';
        label.setAttribute('data-bs-toggle', 'collapse');
        label.setAttribute('data-bs-target', '#plugins-submenu');
        label.setAttribute('aria-expanded', 'false');
        label.setAttribute('role', 'button');
        label.style.cursor = 'pointer';
        label.innerHTML = '<i class="fas fa-puzzle-piece fa-fw"></i> 插件页面';
        
        // Toggle button
        const toggleBtn = document.createElement('button');
        toggleBtn.className = 'nav-submenu-toggle';
        toggleBtn.type = 'button';
        toggleBtn.setAttribute('data-bs-toggle', 'collapse');
        toggleBtn.setAttribute('data-bs-target', '#plugins-submenu');
        toggleBtn.setAttribute('aria-expanded', 'false');
        toggleBtn.setAttribute('aria-controls', 'plugins-submenu');
        toggleBtn.title = '展开/收起插件子导航';
        toggleBtn.innerHTML = '<i class="fas fa-chevron-down"></i>';
        
        header.appendChild(label);
        header.appendChild(toggleBtn);
        
        // Create submenu
        const submenu = document.createElement('div');
        submenu.className = 'collapse nav-submenu';
        submenu.id = 'plugins-submenu';
        
        // Add root items (with their children)
        rootItems.forEach(item => {
            const children = childItems.filter(child => child.parent_id === item.id);
            
            if (children.length > 0) {
                // Create nav-group for this plugin (nested)
                const pluginNavGroup = this.createPluginNavGroup(item, children);
                submenu.appendChild(pluginNavGroup);
            } else {
                // Simple link
                const link = this.createSimpleLink(item);
                submenu.appendChild(link);
            }
        });
        
        group.appendChild(header);
        group.appendChild(submenu);
        
        return group;
    }
    
    /**
     * Create a nav-group for a plugin with submenu (nested structure)
     * This creates a collapsible item inside the "插件页面" submenu
     */
    createPluginNavGroup(parentItem, children) {
        // Don't create another nav-group! Just create a link with nested children
        const container = document.createElement('div');
        container.className = 'plugin-menu-item';
        
        const parentId = parentItem.id.split('.').pop();
        const submenuId = `plugin-${parentId}-submenu`;
        
        // Parent link (not a nav-group header)
        const parentLink = document.createElement('a');
        parentLink.className = 'nav-link';
        parentLink.href = parentItem.url || '#';
        parentLink.innerHTML = `<i class="${parentItem.icon}"></i> ${parentItem.label}`;
        parentLink.setAttribute('data-bs-toggle', 'collapse');
        parentLink.setAttribute('data-bs-target', `#${submenuId}`);
        parentLink.setAttribute('aria-expanded', 'false');
        
        if (parentItem.url) {
            parentLink.addEventListener('click', (e) => {
                // Don't prevent default - let Bootstrap handle collapse
                // But also navigate to the page
                setTimeout(() => {
                    this.navigateToPluginPage(parentItem.url, parentItem.label);
                }, 100);
            });
        }
        
        container.appendChild(parentLink);
        
        // Submenu for children
        if (children.length > 0) {
            const submenu = document.createElement('div');
            submenu.className = 'collapse nav-submenu';
            submenu.id = submenuId;
            submenu.style.paddingLeft = '1.5rem'; // Indent children
            
            children.forEach(child => {
                const link = document.createElement('a');
                link.className = 'nav-link nav-sub-link';
                link.href = child.url || '#';
                link.innerHTML = `<i class="${child.icon}"></i> ${child.label}`;
                
                if (child.url) {
                    link.addEventListener('click', (e) => {
                        e.preventDefault();
                        this.navigateToPluginPage(child.url, child.label);
                    });
                }
                
                submenu.appendChild(link);
            });
            
            container.appendChild(submenu);
        }
        
        return container;
    }
    
    /**
     * Create a simple nav-link
     */
    createSimpleLink(item, isChild = false) {
        const link = document.createElement('a');
        // Use correct classes: nav-link for parent, nav-link nav-sub-link for children
        link.className = isChild ? 'nav-link nav-sub-link' : 'nav-link';
        link.href = item.url || '#';
        link.innerHTML = `<i class="${item.icon}"></i> ${item.label}`;
        
        const idSuffix = item.id.split('.').pop();
        link.id = `v-plugin-${idSuffix}-tab`;
        
        if (item.url) {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                this.navigateToPluginPage(item.url, item.label);
            });
        }
        
        return link;
    }
    
    /**
     * Navigate to a plugin page
     */
    navigateToPluginPage(url, title) {
        console.log(`[PluginUI] Navigating to: ${url} (${title})`);
        
        // Find content area
        const contentArea = document.querySelector('#v-pills-tabContent');
        if (!contentArea) {
            console.error('[PluginUI] Content area not found, opening in new tab');
            window.open(url, '_blank');
            return;
        }
        
        // Deactivate ALL existing tab panes (important!)
        const allPanes = contentArea.querySelectorAll('.tab-pane');
        console.log(`[PluginUI] Found ${allPanes.length} existing tab panes, deactivating all`);
        allPanes.forEach(pane => {
            pane.classList.remove('show', 'active');
        });
        
        // Generate tab ID
        const tabId = 'tab-plugin-' + url.replace(/[^a-zA-Z0-9]/g, '-');
        
        // Find or create tab pane
        let tabPane = document.getElementById(tabId);
        
        if (!tabPane) {
            console.log(`[PluginUI] Creating new tab pane: ${tabId}`);
            
            // Create new tab pane with proper structure
            tabPane = document.createElement('div');
            tabPane.className = 'tab-pane fade';  // Must have fade but NOT show/active initially
            tabPane.id = tabId;
            tabPane.setAttribute('role', 'tabpanel');
            
            // Add loading state
            tabPane.innerHTML = `
                <div class="container-fluid p-4">
                    <div class="text-center py-5">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">加载中...</span>
                        </div>
                        <p class="mt-2 text-muted">正在加载插件内容...</p>
                    </div>
                </div>
            `;
            
            // Append to content area
            contentArea.appendChild(tabPane);
            console.log(`[PluginUI] Tab pane added to DOM`);
            
            // Load content via fetch (async)
            this.loadPluginContent(url, tabPane);
        } else {
            console.log(`[PluginUI] Reusing existing tab pane: ${tabId}`);
        }
        
        // NOW activate this tab (after it's in the DOM)
        // Small delay to ensure DOM is ready
        setTimeout(() => {
            tabPane.classList.add('show', 'active');
            console.log(`[PluginUI] Activated tab: ${tabId}`);
        }, 50);
    }
    
    /**
     * Load plugin content from URL
     */
    async loadPluginContent(url, container) {
        try {
            console.log(`[PluginUI] Fetching: ${url}`);
            
            const response = await fetch(url);
            console.log(`[PluginUI] Response status: ${response.status}`);
            
            if (!response.ok) {
                console.error(`[PluginUI] Server returned ${response.status}`);
                const isPluginPage = url.startsWith('/plugins/');
                if (isPluginPage) {
                    container.innerHTML = '<div class="container-fluid p-4"><div class="alert alert-danger"><h5><i class="fas fa-exclamation-triangle me-2"></i>加载失败</h5><p>HTTP ' + response.status + '</p><p class="small">URL: ' + url + '</p><p class="small text-muted">请检查后端服务是否重启</p></div></div>';
                } else {
                    container.innerHTML = '<div class="container-fluid p-4"><div class="alert alert-warning"><i class="fas fa-info-circle me-2"></i>页面加载失败: HTTP ' + response.status + '</div></div>';
                }
                return;
            }
            
            const html = await response.text();
            
            // Parse into a temporary div to separate scripts from content
            const temp = document.createElement('div');
            temp.innerHTML = html;
            
            // Extract and remove script tags, execute via Function()
            const scripts = temp.querySelectorAll('script');
            scripts.forEach(function(s) {
                var code = (s.textContent || s.innerText || '').trim();
                if (code) {
                    try {
                        (new Function(code))();
                    } catch (execErr) {
                        console.error('[PluginUI] Script execution error:', execErr);
                    }
                }
                s.parentNode && s.parentNode.removeChild(s);
            });
            
            // Inject remaining content (without script tags) wrapped in container
            container.innerHTML = '<div class="container-fluid p-4">' + temp.innerHTML + '</div>';
            
            // Register onclick handlers for server-rendered plugin pages
            this._registerPluginHandlers();
            
            console.log('[PluginUI] Content loaded successfully');
            
        } catch (error) {
            console.error('[PluginUI] Failed to load content:', error);
            container.innerHTML = '<div class="container-fluid p-4"><div class="alert alert-danger"><i class="fas fa-exclamation-triangle me-2"></i>加载插件内容失败: ' + error.message + '</div></div>';
        }
    }
    
    /**
     * Register onclick handlers for server-rendered plugin pages.
     * Functions are idempotent — can be called multiple times safely.
     */
    _registerPluginHandlers() {
        if (this._handlersRegistered) return;
        this._handlersRegistered = true;
        
        // Store page filter
        window._aFilter = function() {
            var s = (document.getElementById('plugin-search')||{}).value||'';
            var c = (document.getElementById('category-filter')||{}).value||'';
            var cards = document.querySelectorAll('#plugin-list .col-lg-4');
            s = s.toLowerCase();
            cards.forEach(function(card) {
                var text = (card.textContent||'').toLowerCase();
                var match = !s || text.indexOf(s) !== -1;
                if (match && c) {
                    var tags = card.querySelectorAll('.badge');
                    var tagMatch = !c || Array.from(tags).some(function(t) { return t.textContent.trim() === c; });
                    match = tagMatch;
                }
                card.style.display = match ? '' : 'none';
            });
        };
        
        // Install plugin
        window._aInstall = function(slug, repo) {
            if (!repo) { alert('无仓库地址'); return; }
            if (!confirm('确定要安装 ' + slug + ' ?\n\n' + repo)) return;
            fetch('/api/plugins/astrbot_compatibility/install', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body: JSON.stringify({plugin_name:slug, repo_url:repo})
            }).then(function(r){return r.json();}).then(function(d) {
                alert(d.success ? '安装成功！' : '安装失败: '+(d.error||''));
            });
        };
        
        // Reload plugin
        window._aReload = function(name) {
            fetch('/api/plugins/astrbot_compatibility/reload', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body: JSON.stringify({plugin_name:name})
            }).then(function(r){return r.json();}).then(function(d) {
                alert(d.success ? '重载成功' : '重载失败: '+d.error);
                location.reload();
            });
        };
        
        // Unload plugin
        window._aUnload = function(name) {
            if (!confirm('确定要卸载 ' + name + ' ?')) return;
            fetch('/api/plugins/astrbot_compatibility/unload', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body: JSON.stringify({plugin_name:name})
            }).then(function(r){return r.json();}).then(function(d) {
                alert(d.success ? '卸载成功' : '卸载失败: '+d.error);
                location.reload();
            });
        };
    }
    
    /**
     * Create a menu item element
     */
    createMenuItem(item, isChild = false) {
        const li = document.createElement('li');
        li.className = isChild ? 'nav-item-sub' : 'nav-item';
        
        const link = document.createElement('a');
        link.className = 'nav-link';
        link.href = item.url || '#';
        link.innerHTML = `<i class="${item.icon}"></i> ${item.label}`;
        
        if (item.action) {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                this.executeAction(item.action);
            });
        }
        
        li.appendChild(link);
        return li;
    }
    
    /**
     * Render setting sections in the settings page
     */
    async renderSettingSections() {
        if (!this.extensions || !this.extensions.setting_sections) return;
        
        const sections = this.extensions.setting_sections;
        if (sections.length === 0) return;
        
        // Find settings container
        const settingsContainer = document.querySelector('#plugin-settings-container') ||
                                 document.querySelector('[data-role="plugin-settings"]');
        
        if (!settingsContainer) {
            console.warn('[PluginUI] Settings container not found');
            return;
        }
        
        // Sort sections by order
        sections.sort((a, b) => a.order - b.order);
        
        // Render each section
        sections.forEach(section => {
            const sectionEl = this.createSettingSection(section);
            settingsContainer.appendChild(sectionEl);
        });
    }
    
    /**
     * Create a setting section element
     */
    createSettingSection(section) {
        const card = document.createElement('div');
        card.className = 'card mb-3 plugin-setting-section';
        card.dataset.sectionId = section.id;
        
        card.innerHTML = `
            <div class="card-header">
                <h6 class="mb-0">${section.title}</h6>
                ${section.description ? `<small class="text-muted">${section.description}</small>` : ''}
            </div>
            <div class="card-body">
                <form class="plugin-settings-form" data-section="${section.id}">
                    <!-- Fields will be rendered here -->
                </form>
            </div>
        `;
        
        const form = card.querySelector('form');
        
        // Render fields using the config renderer
        if (section.fields && section.fields.length > 0) {
            const schema = {
                title: section.title,
                sections: [{
                    title: '',
                    fields: section.fields
                }]
            };
            
            // Use the existing config renderer
            if (typeof renderPluginConfigForm === 'function') {
                const formEl = renderPluginConfigForm(schema, {}, async (formData) => {
                    await this.savePluginSettings(section.id, formData);
                });
                form.innerHTML = '';
                form.appendChild(formEl);
            }
        }
        
        return card;
    }
    
    /**
     * Save plugin settings
     */
    async savePluginSettings(sectionId, formData) {
        try {
            // Extract plugin name from section ID (format: plugin_name.section_id)
            const parts = sectionId.split('.');
            const pluginName = parts[0];
            
            const response = await fetch('/api/plugins/config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    plugin_name: pluginName,
                    config: formData
                })
            });
            
            const data = await response.json();
            if (data.success) {
                showToast('设置保存成功', 'success');
            } else {
                showToast(`保存失败: ${data.error}`, 'danger');
            }
        } catch (error) {
            console.error('Failed to save settings:', error);
            showToast('保存设置失败', 'danger');
        }
    }
    
    /**
     * Render widgets in dashboard or other positions
     */
    async renderWidgets() {
        if (!this.extensions || !this.extensions.widgets) return;
        
        const widgets = this.extensions.widgets;
        if (widgets.length === 0) return;
        
        // Group widgets by position
        const widgetsByPosition = {};
        widgets.forEach(widget => {
            if (!widgetsByPosition[widget.position]) {
                widgetsByPosition[widget.position] = [];
            }
            widgetsByPosition[widget.position].push(widget);
        });
        
        // Render widgets for each position
        for (const [position, positionWidgets] of Object.entries(widgetsByPosition)) {
            await this.renderWidgetsInPosition(position, positionWidgets);
        }
    }
    
    /**
     * Render widgets in a specific position
     */
    async renderWidgetsInPosition(position, widgets) {
        // Find container for this position
        const container = document.querySelector(`[data-widget-position="${position}"]`) ||
                         document.querySelector(`#${position}-widgets`) ||
                         document.querySelector(`.${position}-widgets`);
        
        if (!container) {
            console.warn(`[PluginUI] Widget container for position '${position}' not found`);
            return;
        }
        
        // Sort widgets by order
        widgets.sort((a, b) => a.order - b.order);
        
        // Render each widget
        for (const widget of widgets) {
            const widgetEl = await this.createWidget(widget);
            container.appendChild(widgetEl);
        }
    }
    
    /**
     * Create a widget element
     */
    async createWidget(widget) {
        const card = document.createElement('div');
        card.className = `card widget widget-${widget.widget_type}`;
        card.dataset.widgetId = widget.id;
        
        // Fetch data if data_source is provided
        let data = null;
        if (widget.data_source) {
            try {
                const response = await fetch(widget.data_source);
                data = await response.json();
            } catch (error) {
                console.error(`Failed to fetch widget data:`, error);
            }
        }
        
        // Render based on widget type
        let content = '';
        switch (widget.widget_type) {
            case 'stats':
                content = this.renderStatsWidget(widget, data);
                break;
            case 'chart':
                content = this.renderChartWidget(widget, data);
                break;
            case 'table':
                content = this.renderTableWidget(widget, data);
                break;
            default:
                content = this.renderCardWidget(widget, data);
        }
        
        card.innerHTML = `
            <div class="card-header">
                <h6 class="mb-0">${widget.title}</h6>
            </div>
            <div class="card-body">
                ${content}
            </div>
        `;
        
        // Setup auto-refresh if configured
        if (widget.refresh_interval) {
            setInterval(async () => {
                const refreshData = await this.fetchWidgetData(widget.data_source);
                this.updateWidgetContent(card, widget, refreshData);
            }, widget.refresh_interval * 1000);
        }
        
        return card;
    }
    
    /**
     * Render stats widget
     */
    renderStatsWidget(widget, data) {
        const items = widget.config.items || [];
        
        return `
            <div class="row">
                ${items.map(item => `
                    <div class="col-md-4 mb-3">
                        <div class="stat-item text-center">
                            <i class="${item.icon} fa-2x text-${item.color || 'primary'} mb-2"></i>
                            <h3 class="mb-1">${item.value}</h3>
                            <p class="text-muted mb-0">${item.label}</p>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }
    
    /**
     * Render chart widget (placeholder)
     */
    renderChartWidget(widget, data) {
        return '<div class="chart-placeholder">Chart rendering coming soon...</div>';
    }
    
    /**
     * Render table widget (placeholder)
     */
    renderTableWidget(widget, data) {
        return '<div class="table-placeholder">Table rendering coming soon...</div>';
    }
    
    /**
     * Render card widget (default)
     */
    renderCardWidget(widget, data) {
        return '<p>Custom widget content</p>';
    }
    
    /**
     * Fetch widget data
     */
    async fetchWidgetData(dataSource) {
        if (!dataSource) return null;
        
        try {
            const response = await fetch(dataSource);
            return await response.json();
        } catch (error) {
            console.error('Failed to fetch widget data:', error);
            return null;
        }
    }
    
    /**
     * Update widget content with new data
     */
    updateWidgetContent(widgetEl, widget, data) {
        // Implementation depends on widget type
        // This is a simplified version
        console.log('Updating widget:', widget.id, data);
    }
    
    /**
     * Register plugin pages with the router
     */
    async registerPages() {
        if (!this.extensions || !this.extensions.pages) return;
        
        const pages = this.extensions.pages;
        if (pages.length === 0) return;
        
        // Register pages with the frontend router
        pages.forEach(page => {
            this.registerPageRoute(page);
        });
    }
    
    /**
     * Register a single page route
     */
    registerPageRoute(page) {
        // This would integrate with your frontend routing system
        // For now, we'll just log it
        console.log(`[PluginUI] Registered page route: ${page.route}`);
        
        // In a real implementation, you would:
        // 1. Add route to your router (Vue Router, React Router, etc.)
        // 2. Create a component that renders the page content
        // 3. Handle authentication and permissions
    }
    
    /**
     * Register modals
     */
    async registerModals() {
        if (!this.extensions || !this.extensions.modals) return;
        
        const modals = this.extensions.modals;
        if (modals.length === 0) return;
        
        // Create modal elements in the DOM
        modals.forEach(modal => {
            this.createModalElement(modal);
        });
    }
    
    /**
     * Create a modal element
     */
    createModalElement(modal) {
        const modalHtml = `
            <div class="modal fade" id="modal-${modal.id}" tabindex="-1">
                <div class="modal-dialog modal-${modal.size}">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">${modal.title}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        ${modal.content || ''}
                        <div class="modal-footer">
                            ${(modal.buttons || []).map(btn => `
                                <button type="button" class="btn ${btn.class}" 
                                        onclick="${btn.action === 'close' ? 'hideModal(\'' + modal.id + '\')' : btn.action}">
                                    ${btn.label}
                                </button>
                            `).join('')}
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }
    
    /**
     * Execute a custom action
     */
    executeAction(action) {
        if (typeof window[action] === 'function') {
            window[action]();
        } else {
            console.warn(`[PluginUI] Action '${action}' not found`);
        }
    }
}

// Global helper functions
window.hideModal = function(modalId) {
    const modalEl = document.getElementById(`modal-${modalId}`);
    if (modalEl) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) {
            modal.hide();
        }
    }
};

// Create global instance
window.pluginUILoader = new PluginUILoader();

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.pluginUILoader.initialize();
    });
} else {
    window.pluginUILoader.initialize();
}
