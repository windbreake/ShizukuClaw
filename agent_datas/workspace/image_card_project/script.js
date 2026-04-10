// DOM Elements
const imageModal = document.getElementById('imageModal');
const modalImage = document.getElementById('modal-image');
const closeBtn = document.querySelector('.close-modal');
const errorImage = document.querySelector('.error-image');
const actionButtons = document.querySelectorAll('.action-btn');
const links = document.querySelectorAll('.link');

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    initializeData();
});

// Initialize Event Listeners
function initializeEventListeners() {
    // Image Modal Events
    if (errorImage) {
        errorImage.addEventListener('click', openImageModal);
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', closeImageModal);
    }

    // Click outside modal to close
    if (imageModal) {
        imageModal.addEventListener('click', function(e) {
            if (e.target === imageModal) {
                closeImageModal();
            }
        });
    }

    // Action Button Events
    actionButtons.forEach(btn => {
        btn.addEventListener('click', handleActionButton);
    });

    // Link Events
    links.forEach(link => {
        link.addEventListener('click', handleLinkClick);
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', handleKeyboardShortcuts);
}

// Image Modal Functions
function openImageModal() {
    const img = errorImage.querySelector('img');
    if (img) {
        modalImage.src = img.src;
        imageModal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeImageModal() {
    imageModal.classList.remove('active');
    document.body.style.overflow = 'auto';
}

// Action Button Handler
function handleActionButton(e) {
    const btn = e.currentTarget;
    const action = btn.dataset.action;

    switch(action) {
        case 'copy-request-id':
            copyRequestID();
            break;
        case 'retry':
            showNotification('重试中...', 'info');
            setTimeout(() => showNotification('API 请求重新发送', 'success'), 1000);
            break;
        case 'view-docs':
            openDocumentation();
            break;
        case 'contact-support':
            contactSupport();
            break;
    }
}

// Copy Request ID to Clipboard
function copyRequestID() {
    const requestId = document.querySelector('.detail-item .value')?.textContent || 'req_12345';
    
    if (navigator.clipboard) {
        navigator.clipboard.writeText(requestId).then(() => {
            showNotification('请求 ID 已复制', 'success');
        }).catch(() => {
            fallbackCopy(requestId);
        });
    } else {
        fallbackCopy(requestId);
    }
}

// Fallback Copy Function
function fallbackCopy(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    
    try {
        document.execCommand('copy');
        showNotification('请求 ID 已复制', 'success');
    } catch(e) {
        showNotification('复制失败', 'error');
    }
    
    document.body.removeChild(textarea);
}

// Open Documentation
function openDocumentation() {
    const docsUrl = 'https://developer.aliyun.com/docs/';
    window.open(docsUrl, '_blank');
    showNotification('正在打开文档...', 'info');
}

// Contact Support
function contactSupport() {
    const email = 'support@aliyun.com';
    window.location.href = `mailto:${email}?subject=API%20错误%20-%20InvalidApiKey&body=请求%20ID:%20req_12345`;
    showNotification('打开邮件客户端...', 'info');
}

// Link Handler
function handleLinkClick(e) {
    const href = e.currentTarget.href;
    if (href && href !== '#') {
        e.preventDefault();
        window.open(href, '_blank');
        showNotification('打开链接中...', 'info');
    }
}

// Keyboard Shortcuts
function handleKeyboardShortcuts(e) {
    // ESC to close modal
    if (e.key === 'Escape') {
        closeImageModal();
    }
    
    // Ctrl+C to copy request ID
    if (e.ctrlKey && e.key === 'c') {
        const hasSelection = window.getSelection().toString().length > 0;
        if (!hasSelection && imageModal.classList.contains('active') === false) {
            // Only copy if no text is selected and modal is not open
            copyRequestID();
        }
    }
}

// Notification System
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <i class="fas fa-${getNotificationIcon(type)}"></i>
            <span>${message}</span>
        </div>
    `;

    // Add styles if not already added
    if (!document.getElementById('notification-styles')) {
        const style = document.createElement('style');
        style.id = 'notification-styles';
        style.textContent = `
            .notification {
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 15px 20px;
                border-radius: 8px;
                color: white;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                z-index: 10000;
                animation: slideInRight 0.3s ease;
                max-width: 300px;
            }

            .notification-success {
                background: #34c759;
            }

            .notification-error {
                background: #ff3b30;
            }

            .notification-info {
                background: #0084ff;
            }

            .notification-warning {
                background: #ff9500;
            }

            @keyframes slideInRight {
                from {
                    transform: translateX(400px);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }

            @keyframes slideOutRight {
                from {
                    transform: translateX(0);
                    opacity: 1;
                }
                to {
                    transform: translateX(400px);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(style);
    }

    document.body.appendChild(notification);

    // Auto remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 3000);
}

// Get Notification Icon
function getNotificationIcon(type) {
    const icons = {
        'success': 'check-circle',
        'error': 'exclamation-circle',
        'info': 'info-circle',
        'warning': 'warning'
    };
    return icons[type] || 'info-circle';
}

// Initialize Data
function initializeData() {
    // You can add dynamic data loading here
    console.log('Image Card Project Initialized');

    // Set current timestamp
    const now = new Date();
    const timeStr = now.toLocaleString('zh-CN');

    // Update status information if elements exist
    updateStatusDisplay();
}

// Update Status Display
function updateStatusDisplay() {
    const statusItems = document.querySelectorAll('.status-item');
    
    if (statusItems.length > 0) {
        // Add animation when page loads
        statusItems.forEach((item, index) => {
            item.style.animation = `fadeIn 0.5s ease ${index * 0.1}s both`;
        });
    }

    // Add animation styles if not present
    if (!document.getElementById('animation-styles')) {
        const style = document.createElement('style');
        style.id = 'animation-styles';
        style.textContent = `
            @keyframes fadeIn {
                from {
                    opacity: 0;
                    transform: translateY(10px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
        `;
        document.head.appendChild(style);
    }
}

// Export functions for external use
window.ImageCardProject = {
    openImageModal,
    closeImageModal,
    copyRequestID,
    showNotification,
    openDocumentation,
    contactSupport
};
