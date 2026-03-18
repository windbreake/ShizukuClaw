// 动画控制
document.addEventListener('DOMContentLoaded', () => {
    // 页面加载时的淡入
    document.querySelector('#content').classList.add('fade-in');
    
    // Tab 切换动画优化
    const tabs = document.querySelectorAll('[data-bs-toggle="pill"]');
    tabs.forEach(tab => {
        tab.addEventListener('show.bs.tab', (e) => {
            const target = document.querySelector(e.target.dataset.bsTarget);
            target.classList.add('fade-in');
            setTimeout(() => target.classList.remove('fade-in'), 300);
        });
    });
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
