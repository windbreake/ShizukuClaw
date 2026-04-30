// 动画控制
document.addEventListener('DOMContentLoaded', () => {
    // 页面加载时的淡入
    document.querySelector('#content').classList.add('fade-in');
    
    // Tab 切换动画优化
    const tabs = document.querySelectorAll('[data-bs-toggle="pill"]');
    tabs.forEach(tab => {
        tab.addEventListener('show.bs.tab', (e) => {
            if (e.target.dataset.bsTarget) {
                const target = document.querySelector(e.target.dataset.bsTarget);
                if (target) {
                    target.classList.add('fade-in');
                    setTimeout(() => target.classList.remove('fade-in'), 300);
                }
            }
        });
    });
    
    // 初始化数据库页面的角色选择器
    if (typeof loadPersonaOptionsForDatabase === 'function') {
        loadPersonaOptionsForDatabase();
    }
    
    // 监听数据库标签页切换，切换时加载角色列表
    const databaseTab = document.querySelector('[data-bs-target="#v-database"]');
    if (databaseTab) {
        databaseTab.addEventListener('shown.bs.tab', () => {
            if (typeof loadPersonaOptionsForDatabase === 'function') {
                loadPersonaOptionsForDatabase();
            }
        });
    }
});

// 通用工具函数
function showToast(message, type = 'info') {
    // 假设 toastr 已加载
    if (typeof toastr !== 'undefined') {
        toastr[type](message);
    } else {
        alert(message);
    }
}
