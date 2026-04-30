<template>
  <section class="adapter-console-page">
    <header class="adapter-console-header">
      <h1>Adapter Gateway Console</h1>
      <p>OpenAI Chat Completion 兼容的 FastAPI 接口。</p>
    </header>

    <div class="adapter-console-grid">
      <article class="panel">
        <h2>主要接口</h2>
        <ul class="endpoint-list">
          <li><strong>GET</strong> <code>/v1/models</code></li>
          <li><strong>POST</strong> <code>/v1/chat/completions</code></li>
          <li><strong>GET</strong> <code>/health</code></li>
        </ul>
        <p class="adapter-note">可通过任何 OpenAI 兼容客户端直连（NapCat、AstrBot、NoneBot 等）。</p>
      </article>

      <article class="panel">
        <h2>链接</h2>
        <div class="adapter-links">
          <a class="btn ghost" href="/v1/models" target="_blank" rel="noopener noreferrer">查看模型列表</a>
          <a class="btn ghost" href="/docs" target="_blank" rel="noopener noreferrer">Swagger 文档</a>
        </div>
        <p class="adapter-note">默认监听端口来自 data/config.json 中的 unified_api 设置。</p>
      </article>
    </div>
  </section>
</template>