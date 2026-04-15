<template>
  <section class="logs-page">
    <header class="logs-header">
      <h1>日志展示</h1>
      <p>迁移自 legacy logs.html，支持轮询刷新与 SSE 实时追加。</p>
    </header>

    <article class="panel logs-actions">
      <button type="button" class="btn" :disabled="loading" @click="refreshLog">
        {{ loading ? "刷新中..." : "刷新日志" }}
      </button>
      <button type="button" class="btn ghost" @click="clearLog">清空显示</button>
      <span class="logs-hint">自动刷新: 2 秒</span>
    </article>

    <article class="panel logs-content-panel">
      <h2>日志内容</h2>
      <pre class="logs-content">{{ logContent }}</pre>
    </article>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";

const logContent = ref("");
const loading = ref(false);

let refreshTimer: number | null = null;
let streamSource: EventSource | null = null;

const appendLogLine = (line: string) => {
  const suffix = line.endsWith("\n") ? line : `${line}\n`;
  logContent.value += suffix;
  if (logContent.value.length > 200000) {
    logContent.value = logContent.value.slice(-150000);
  }
};

const refreshLog = async () => {
  loading.value = true;
  try {
    const response = await fetch("/api/logs");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    logContent.value = await response.text();
  } catch (error) {
    const message = error instanceof Error ? error.message : "未知错误";
    appendLogLine(`[ERROR] 获取日志失败: ${message}`);
  } finally {
    loading.value = false;
  }
};

const clearLog = () => {
  logContent.value = "";
};

onMounted(() => {
  refreshLog();
  refreshTimer = window.setInterval(() => {
    void refreshLog();
  }, 2000);

  streamSource = new EventSource("/stream_logs");
  streamSource.onmessage = (event) => {
    appendLogLine(event.data);
  };
  streamSource.onerror = () => {
    appendLogLine("[WARN] SSE 连接异常，继续使用轮询模式");
  };
});

onUnmounted(() => {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
  }
  if (streamSource) {
    streamSource.close();
  }
});
</script>