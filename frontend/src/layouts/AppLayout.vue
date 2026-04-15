<template>
  <div class="app-shell">
    <header class="topbar">
      <span class="logo">ShizukuClaw</span>
      <nav class="nav-links">
        <RouterLink to="/">首页</RouterLink>
        <RouterLink to="/chat-sandbox">沙箱聊天</RouterLink>
        <RouterLink to="/config-editor">配置编辑</RouterLink>
        <RouterLink to="/db-management">数据库</RouterLink>
        <RouterLink to="/diagnosis">诊断</RouterLink>
        <RouterLink to="/adapter-console">网关控制台</RouterLink>
        <RouterLink to="/adapter-logs">网关日志</RouterLink>
        <RouterLink to="/security-init">安全初始化</RouterLink>
        <RouterLink to="/logs">日志</RouterLink>
        <RouterLink to="/monitoring">监控</RouterLink>
      </nav>
    </header>
    <main class="page-content">
      <slot />
    </main>
  </div>
</template>
