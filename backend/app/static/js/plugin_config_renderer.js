/**
 * Plugin Configuration UI Renderer
 * 
 * Dynamically renders plugin configuration forms based on JSON schema.
 * Supports multiple field types with validation and conditional display.
 */

/**
 * Render a complete configuration form from schema
 * @param {Object} schema - Configuration schema object
 * @param {Object} currentConfig - Current configuration values
 * @param {Function} onSave - Save callback function
 * @returns {HTMLElement} Form container element
 */
function renderPluginConfigForm(schema, currentConfig = {}, onSave = null) {
    const container = document.createElement('div');
    container.className = 'plugin-config-form';
    
    // Header
    const header = document.createElement('div');
    header.className = 'config-header mb-4';
    header.innerHTML = `
        <h4 class="mb-1">${schema.title || '插件配置'}</h4>
        ${schema.description ? `<p class="text-muted small mb-0">${schema.description}</p>` : ''}
    `;
    container.appendChild(header);
    
    // Form
    const form = document.createElement('form');
    form.id = 'plugin-config-form';
    
    // Track field dependencies for conditional rendering
    const fieldDependencies = new Map();
    
    // Render sections
    (schema.sections || []).forEach((section, sectionIndex) => {
        const sectionEl = createConfigSection(section, currentConfig, fieldDependencies);
        form.appendChild(sectionEl);
    });
    
    // Save button
    if (onSave) {
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'd-flex justify-content-end gap-2 mt-4';
        buttonContainer.innerHTML = `
            <button type="button" class="btn btn-secondary" onclick="location.reload()">
                <i class="fas fa-undo me-1"></i>重置
            </button>
            <button type="submit" class="btn btn-primary">
                <i class="fas fa-save me-1"></i>保存配置
            </button>
        `;
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            // Validate form
            const formData = collectFormData(form, schema);
            const errors = validateFormData(formData, schema);
            
            if (errors.length > 0) {
                showValidationErrors(errors);
                return;
            }
            
            // Call save callback
            try {
                await onSave(formData);
                showToast('配置保存成功', 'success');
            } catch (error) {
                showToast(`保存失败: ${error.message}`, 'danger');
            }
        });
        
        container.appendChild(buttonContainer);
    }
    
    container.appendChild(form);
    
    // Setup dependency listeners
    setupDependencyListeners(form, fieldDependencies);
    
    return container;
}

/**
 * Create a configuration section
 */
function createConfigSection(section, currentConfig, fieldDependencies) {
    const sectionEl = document.createElement('div');
    sectionEl.className = 'card mb-3 config-section';
    
    const headerClass = section.collapsed ? 'collapsed' : '';
    const collapseId = `section-${Math.random().toString(36).substr(2, 9)}`;
    
    sectionEl.innerHTML = `
        <div class="card-header ${headerClass}" data-bs-toggle="collapse" 
             data-bs-target="#${collapseId}" style="cursor: pointer;">
            <h6 class="mb-0">
                <i class="fas fa-chevron-down me-2 transition-transform"></i>
                ${section.title}
                ${section.description ? `<small class="text-muted ms-2">${section.description}</small>` : ''}
            </h6>
        </div>
        <div id="${collapseId}" class="collapse ${!section.collapsed ? 'show' : ''}">
            <div class="card-body">
                <!-- Fields will be inserted here -->
            </div>
        </div>
    `;
    
    const bodyEl = sectionEl.querySelector('.card-body');
    
    // Render fields
    (section.fields || []).forEach(field => {
        const fieldEl = createConfigField(field, currentConfig[field.key], fieldDependencies);
        bodyEl.appendChild(fieldEl);
        
        // Track dependencies
        if (field.depends_on) {
            Object.keys(field.depends_on).forEach(depKey => {
                if (!fieldDependencies.has(depKey)) {
                    fieldDependencies.set(depKey, []);
                }
                fieldDependencies.get(depKey).push({
                    fieldKey: field.key,
                    expectedValue: field.depends_on[depKey],
                    element: fieldEl
                });
            });
        }
    });
    
    // Toggle chevron rotation
    const headerEl = sectionEl.querySelector('.card-header');
    const chevronEl = headerEl.querySelector('.fa-chevron-down');
    headerEl.addEventListener('click', () => {
        setTimeout(() => {
            const isCollapsed = !sectionEl.querySelector('.collapse').classList.contains('show');
            chevronEl.style.transform = isCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)';
        }, 100);
    });
    
    return sectionEl;
}

/**
 * Create a single configuration field
 */
function createConfigField(field, currentValue, fieldDependencies) {
    const wrapperEl = document.createElement('div');
    wrapperEl.className = 'mb-3 config-field';
    wrapperEl.dataset.fieldKey = field.key;
    
    if (field.hidden) {
        wrapperEl.style.display = 'none';
    }
    
    // Label
    const labelEl = document.createElement('label');
    labelEl.className = 'form-label';
    labelEl.innerHTML = `
        ${field.label}
        ${field.required ? '<span class="text-danger">*</span>' : ''}
        ${field.description ? `<small class="text-muted d-block">${field.description}</small>` : ''}
    `;
    wrapperEl.appendChild(labelEl);
    
    // Input element based on type
    let inputEl;
    switch (field.type) {
        case 'switch':
            inputEl = createSwitchField(field, currentValue);
            break;
        case 'textarea':
            inputEl = createTextareaField(field, currentValue);
            break;
        case 'select':
            inputEl = createSelectField(field, currentValue);
            break;
        case 'slider':
            inputEl = createSliderField(field, currentValue);
            break;
        case 'color':
            inputEl = createColorField(field, currentValue);
            break;
        case 'password':
            inputEl = createPasswordField(field, currentValue);
            break;
        case 'number':
            inputEl = createNumberField(field, currentValue);
            break;
        default:
            inputEl = createTextField(field, currentValue);
    }
    
    wrapperEl.appendChild(inputEl);
    
    // Validation message container
    const errorEl = document.createElement('div');
    errorEl.className = 'invalid-feedback';
    wrapperEl.appendChild(errorEl);
    
    return wrapperEl;
}

/**
 * Create switch/toggle field
 */
function createSwitchField(field, value) {
    const checked = value !== undefined ? value : (field.default || false);
    const switchId = `switch-${field.key}`;
    
    const wrapper = document.createElement('div');
    wrapper.className = 'form-check form-switch';
    wrapper.innerHTML = `
        <input class="form-check-input" type="checkbox" 
               id="${switchId}" 
               data-field-key="${field.key}"
               ${checked ? 'checked' : ''}
               ${field.disabled ? 'disabled' : ''}>
        <label class="form-check-label" for="${switchId}">
            ${checked ? '已启用' : '未启用'}
        </label>
    `;
    
    const input = wrapper.querySelector('input');
    const label = wrapper.querySelector('label');
    
    input.addEventListener('change', (e) => {
        label.textContent = e.target.checked ? '已启用' : '未启用';
    });
    
    return wrapper;
}

/**
 * Create textarea field
 */
function createTextareaField(field, value) {
    const textarea = document.createElement('textarea');
    textarea.className = 'form-control';
    textarea.dataset.fieldKey = field.key;
    textarea.placeholder = field.placeholder || '';
    textarea.rows = field.rows || 4;
    textarea.value = value !== undefined ? value : (field.default || '');
    textarea.disabled = field.disabled;
    
    if (field.required) {
        textarea.required = true;
    }
    
    return textarea;
}

/**
 * Create select/dropdown field
 */
function createSelectField(field, value) {
    const select = document.createElement('select');
    select.className = 'form-select';
    select.dataset.fieldKey = field.key;
    select.disabled = field.disabled;
    
    if (field.required) {
        select.required = true;
    }
    
    // Add options
    (field.options || []).forEach(option => {
        const optionEl = document.createElement('option');
        optionEl.value = option.value;
        optionEl.textContent = option.label;
        optionEl.selected = option.value === (value !== undefined ? value : field.default);
        select.appendChild(optionEl);
    });
    
    return select;
}

/**
 * Create slider/range field
 */
function createSliderField(field, value) {
    const currentValue = value !== undefined ? value : (field.default || 0);
    const sliderId = `slider-${field.key}`;
    
    const wrapper = document.createElement('div');
    wrapper.innerHTML = `
        <input type="range" class="form-range" 
               id="${sliderId}"
               data-field-key="${field.key}"
               min="${field.min || 0}" 
               max="${field.max || 100}" 
               step="${field.step || 1}"
               value="${currentValue}"
               ${field.disabled ? 'disabled' : ''}>
        <div class="d-flex justify-content-between small text-muted">
            <span>${field.min || 0}</span>
            <span id="${sliderId}-value" class="fw-bold">${currentValue}</span>
            <span>${field.max || 100}</span>
        </div>
    `;
    
    const input = wrapper.querySelector('input');
    const valueDisplay = wrapper.querySelector(`#${sliderId}-value`);
    
    input.addEventListener('input', (e) => {
        valueDisplay.textContent = e.target.value;
    });
    
    return wrapper;
}

/**
 * Create color picker field
 */
function createColorField(field, value) {
    const wrapper = document.createElement('div');
    wrapper.className = 'd-flex align-items-center gap-2';
    
    const colorInput = document.createElement('input');
    colorInput.type = 'color';
    colorInput.className = 'form-control form-control-color';
    colorInput.dataset.fieldKey = field.key;
    colorInput.value = value || field.default || '#000000';
    colorInput.disabled = field.disabled;
    
    const textInput = document.createElement('input');
    textInput.type = 'text';
    textInput.className = 'form-control';
    textInput.value = colorInput.value;
    textInput.placeholder = '#000000';
    
    colorInput.addEventListener('input', (e) => {
        textInput.value = e.target.value;
    });
    
    textInput.addEventListener('input', (e) => {
        if (/^#[0-9A-F]{6}$/i.test(e.target.value)) {
            colorInput.value = e.target.value;
        }
    });
    
    wrapper.appendChild(colorInput);
    wrapper.appendChild(textInput);
    
    return wrapper;
}

/**
 * Create password field
 */
function createPasswordField(field, value) {
    const wrapper = document.createElement('div');
    wrapper.className = 'input-group';
    
    const input = document.createElement('input');
    input.type = 'password';
    input.className = 'form-control';
    input.dataset.fieldKey = field.key;
    input.placeholder = field.placeholder || '请输入密码';
    input.value = value || field.default || '';
    input.disabled = field.disabled;
    
    if (field.required) {
        input.required = true;
    }
    
    const toggleBtn = document.createElement('button');
    toggleBtn.type = 'button';
    toggleBtn.className = 'btn btn-outline-secondary';
    toggleBtn.innerHTML = '<i class="fas fa-eye"></i>';
    
    toggleBtn.addEventListener('click', () => {
        const isPassword = input.type === 'password';
        input.type = isPassword ? 'text' : 'password';
        toggleBtn.innerHTML = isPassword ? '<i class="fas fa-eye-slash"></i>' : '<i class="fas fa-eye"></i>';
    });
    
    wrapper.appendChild(input);
    wrapper.appendChild(toggleBtn);
    
    return wrapper;
}

/**
 * Create number field
 */
function createNumberField(field, value) {
    const input = document.createElement('input');
    input.type = 'number';
    input.className = 'form-control';
    input.dataset.fieldKey = field.key;
    input.placeholder = field.placeholder || '';
    input.value = value !== undefined ? value : (field.default || '');
    input.disabled = field.disabled;
    
    if (field.min !== undefined) input.min = field.min;
    if (field.max !== undefined) input.max = field.max;
    if (field.step !== undefined) input.step = field.step;
    if (field.required) input.required = true;
    
    return input;
}

/**
 * Create text field (default)
 */
function createTextField(field, value) {
    const input = document.createElement('input');
    input.type = field.type === 'email' ? 'email' : 
                 field.type === 'url' ? 'url' : 
                 field.type === 'date' ? 'date' :
                 field.type === 'time' ? 'time' : 'text';
    input.className = 'form-control';
    input.dataset.fieldKey = field.key;
    input.placeholder = field.placeholder || '';
    input.value = value !== undefined ? value : (field.default || '');
    input.disabled = field.disabled;
    input.pattern = field.pattern || '';
    
    if (field.required) {
        input.required = true;
    }
    
    return input;
}

/**
 * Collect form data into an object
 */
function collectFormData(form, schema) {
    const data = {};
    
    (schema.sections || []).forEach(section => {
        (section.fields || []).forEach(field => {
            const inputEl = form.querySelector(`[data-field-key="${field.key}"]`);
            if (!inputEl) return;
            
            let value;
            switch (field.type) {
                case 'switch':
                    value = inputEl.querySelector('input[type="checkbox"]').checked;
                    break;
                case 'slider':
                    value = parseFloat(inputEl.querySelector('input[type="range"]').value);
                    break;
                case 'color':
                    value = inputEl.querySelector('input[type="color"]').value;
                    break;
                case 'number':
                    value = parseFloat(inputEl.value);
                    break;
                default:
                    value = inputEl.value;
            }
            
            data[field.key] = value;
        });
    });
    
    return data;
}

/**
 * Validate form data against schema
 */
function validateFormData(data, schema) {
    const errors = [];
    
    (schema.sections || []).forEach(section => {
        (section.fields || []).forEach(field => {
            const value = data[field.key];
            
            // Required field check
            if (field.required && (value === undefined || value === null || value === '')) {
                errors.push({
                    key: field.key,
                    message: `${field.label} 是必填项`
                });
                return;
            }
            
            // Pattern validation
            if (field.pattern && value && typeof value === 'string') {
                const regex = new RegExp(field.pattern);
                if (!regex.test(value)) {
                    errors.push({
                        key: field.key,
                        message: field.validation_message || `${field.label} 格式不正确`
                    });
                }
            }
            
            // Range validation for numbers
            if (field.type === 'number' || field.type === 'slider') {
                const numValue = parseFloat(value);
                if (!isNaN(numValue)) {
                    if (field.min !== undefined && numValue < field.min) {
                        errors.push({
                            key: field.key,
                            message: `${field.label} 不能小于 ${field.min}`
                        });
                    }
                    if (field.max !== undefined && numValue > field.max) {
                        errors.push({
                            key: field.key,
                            message: `${field.label} 不能大于 ${field.max}`
                        });
                    }
                }
            }
        });
    });
    
    return errors;
}

/**
 * Show validation errors on form
 */
function showValidationErrors(errors) {
    // Clear previous errors
    document.querySelectorAll('.config-field .invalid-feedback').forEach(el => {
        el.textContent = '';
        el.style.display = 'none';
    });
    document.querySelectorAll('.config-field.is-invalid').forEach(el => {
        el.classList.remove('is-invalid');
    });
    
    // Show new errors
    errors.forEach(error => {
        const fieldEl = document.querySelector(`.config-field[data-field-key="${error.key}"]`);
        if (fieldEl) {
            fieldEl.classList.add('is-invalid');
            const errorEl = fieldEl.querySelector('.invalid-feedback');
            if (errorEl) {
                errorEl.textContent = error.message;
                errorEl.style.display = 'block';
            }
        }
    });
    
    // Show toast notification
    showToast(`表单验证失败：${errors.length} 个错误`, 'warning');
}

/**
 * Setup dependency listeners for conditional field display
 */
function setupDependencyListeners(form, fieldDependencies) {
    fieldDependencies.forEach((dependents, depKey) => {
        const depInput = form.querySelector(`[data-field-key="${depKey}"]`);
        if (!depInput) return;
        
        const actualInput = depInput.tagName === 'INPUT' || depInput.tagName === 'SELECT' || depInput.tagName === 'TEXTAREA' 
            ? depInput 
            : depInput.querySelector('input, select, textarea');
        
        if (actualInput) {
            actualInput.addEventListener('change', () => {
                const currentValue = actualInput.type === 'checkbox' 
                    ? actualInput.checked 
                    : actualInput.value;
                
                dependents.forEach(dependent => {
                    const shouldShow = currentValue === dependent.expectedValue;
                    dependent.element.style.display = shouldShow ? 'block' : 'none';
                });
            });
        }
    });
}

/**
 * Show toast notification
 */
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} position-fixed`;
    toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);';
    toast.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'danger' ? 'exclamation-circle' : 'info-circle'} me-2"></i>
        ${message}
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Export functions for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        renderPluginConfigForm,
        collectFormData,
        validateFormData
    };
}
