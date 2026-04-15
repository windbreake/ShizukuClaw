<template>
  <section class="monitoring-page">
    <header class="monitoring-header">
      <h1>系统监控面板</h1>
      <p>迁移自 legacy monitoring.html，保留监控指标、日志面板与命令执行。</p>
    </header>

    <div class="monitoring-stats-grid">
      <article class="panel stat-card" v-for="item in statCards" :key="item.label">
        <p class="stat-label">{{ item.label }}</p>
        <p class="stat-value">{{ item.value }}</p>
      </article>
    </div>

    <div class="monitoring-chart-grid">
      <article class="panel">
        <h2>CPU 使用率历史</h2>
        <div class="history-bars">
          <div
            v-for="(value, idx) in cpuHistory"
            :key="`cpu-${idx}`"
            class="history-bar cpu"
            :style="{ height: `${value}%` }"
            :title="`${value.toFixed(1)}%`"
          />
        </div>
      </article>
      <article class="panel">
        <h2>内存使用率历史</h2>
        <div class="history-bars">
          <div
            v-for="(value, idx) in memoryHistory"
            :key="`memory-${idx}`"
            class="history-bar memory"
            :style="{ height: `${value}%` }"
            :title="`${value.toFixed(1)}%`"
          />
        </div>
      </article>
    </div>

    <article class="panel token-panel">
      <h2>Token 使用统计</h2>
      <div class="token-bars">
        <div class="token-row">
          <span>输入 Token</span>
          <div class="token-track">
            <div class="token-fill in" :style="tokenStyles.input" />
          </div>
          <b>{{ stats.token_stats.input_tokens }}</b>
        </div>
        <div class="token-row">
          <span>输出 Token</span>
          <div class="token-track">
            <div class="token-fill out" :style="tokenStyles.output" />
          </div>
          <b>{{ stats.token_stats.output_tokens }}</b>
        </div>
        <div class="token-row">
          <span>总 Token</span>
          <div class="token-track">
            <div class="token-fill total" :style="tokenStyles.total" />
          </div>
          <b>{{ stats.token_stats.total_tokens }}</b>
        </div>
      </div>
    </article>

    <article class="panel system-info-panel">
      <h2>系统信息</h2>
      <div class="system-info-grid">
        <p><strong>CPU:</strong> {{ stats.system_info.cpu || "-" }}</p>
        <p><strong>核心数:</strong> {{ stats.system_info.cpu_count || "-" }}</p>
        <p><strong>总内存:</strong> {{ formatBytes(stats.system_info.total_memory) }}</p>
        <p><strong>已用内存:</strong> {{ formatBytes(stats.system_info.used_memory) }}</p>
        <p><strong>Python版本:</strong> {{ stats.system_info.python_version || "-" }}</p>
        <p><strong>平台:</strong> {{ stats.system_info.platform || "-" }}</p>
      </div>
    </article>

    <article class="panel unified-console-panel">
      <div class="unified-console-title">
        <h2>统一日志面板（系统日志 + 终端命令行）</h2>
        <span>自动刷新: 3 秒</span>
      </div>
      <div class="unified-console-toolbar">
        <input
          v-model="cmdInput"
          class="console-input"
          type="text"
          placeholder="输入终端命令，例如: dir /b"
          @keydown.enter.prevent="runUnifiedCommand"
        />
        <button type="button" class="btn" @click="runUnifiedCommand">执行命令</button>
        <button type="button" class="btn ghost" @click="refreshUnifiedConsole(true)">刷新日志</button>
        <button type="button" class="btn ghost" @click="clearUnifiedConsole">清空面板</button>
      </div>
      <pre class="unified-console">{{ unifiedConsole }}</pre>
    </article>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";

type TokenStats = {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
};

type SystemInfo = {
  cpu: string;
  cpu_count: number;
  total_memory: number;
  used_memory: number;
  python_version: string;
  platform: string;
};

type MonitoringData = {
  cpu_percent: number;
  memory_percent: number;
  uptime: number;
  token_stats: TokenStats;
  system_info: SystemInfo;
};

const stats = reactive<MonitoringData>({
  cpu_percent: 0,
  memory_percent: 0,
  uptime: 0,
  token_stats: {
    input_tokens: 0,
    output_tokens: 0,
    total_tokens: 0
  },
  system_info: {
    cpu: "",
    cpu_count: 0,
    total_memory: 0,
    used_memory: 0,
    python_version: "",
    platform: ""
  }
});

const cpuHistory = ref<number[]>([]);
const memoryHistory = ref<number[]>([]);
const unifiedConsole = ref("[INFO] 统一日志面板初始化中...");
const cmdInput = ref("");
const lastLogSnapshot = ref("");

let monitorTimer: number | null = null;
let consoleTimer: number | null = null;

const formatUptime = (seconds: number): string => {
  const hours = Math.floor(seconds / 3600)
    .toString()
    .padStart(2, "0");
  const minutes = Math.floor((seconds % 3600) / 60)
    .toString()
    .padStart(2, "0");
  const secs = Math.floor(seconds % 60)
    .toString()
    .padStart(2, "0");
  return `${hours}:${minutes}:${secs}`;
};

const formatBytes = (bytes: number): string => {
  if (!bytes) {
    return "-";
  }
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
};

const statCards = computed(() => [
  { label: "CPU 使用率", value: `${stats.cpu_percent.toFixed(1)}%` },
  { label: "内存使用率", value: `${stats.memory_percent.toFixed(1)}%` },
  {
    label: "Token 总消耗",
    value: `${stats.token_stats.total_tokens} (${stats.token_stats.input_tokens}↑ / ${stats.token_stats.output_tokens}↓)`
  },
  { label: "运行时间", value: formatUptime(stats.uptime) }
]);

const tokenStyles = computed(() => {
  const max = Math.max(
    stats.token_stats.input_tokens,
    stats.token_stats.output_tokens,
    stats.token_stats.total_tokens,
    1
  );
  return {
    input: { width: `${(stats.token_stats.input_tokens / max) * 100}%` },
    output: { width: `${(stats.token_stats.output_tokens / max) * 100}%` },
    total: { width: `${(stats.token_stats.total_tokens / max) * 100}%` }
  };
});

const pushHistory = (history: number[], value: number) => {
  history.push(value);
  if (history.length > 20) {
    history.shift();
  }
};

const appendConsoleLine = (text: string) => {
  const now = new Date().toLocaleTimeString();
  unifiedConsole.value += `\n[${now}] ${text}`;
  if (unifiedConsole.value.length > 120000) {
    unifiedConsole.value = unifiedConsole.value.slice(-100000);
  }
};

const clearUnifiedConsole = () => {
  unifiedConsole.value = "[INFO] 面板已清空，等待新日志...";
  lastLogSnapshot.value = "";
};

const refreshUnifiedConsole = async (forceFull = false) => {
  try {
    const response = await fetch("/api/logs");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const current = (await response.text()) || "";

    if (!current.trim()) {
      return;
    }

    if (forceFull || !lastLogSnapshot.value) {
      appendConsoleLine("[SYSTEM] 已载入系统日志快照");
      const lines = current.split("\n").slice(-25);
      lines.forEach((line) => {
        if (line.trim()) {
          appendConsoleLine(`[LOG] ${line}`);
        }
      });
      lastLogSnapshot.value = current;
      return;
    }

    if (current.startsWith(lastLogSnapshot.value)) {
      const added = current.slice(lastLogSnapshot.value.length);
      const lines = added.split("\n").filter((line) => line.trim());
      lines.forEach((line) => appendConsoleLine(`[LOG] ${line}`));
    } else if (current !== lastLogSnapshot.value) {
      appendConsoleLine("[SYSTEM] 日志文件发生轮转或截断，已重新同步");
      const lines = current.split("\n").slice(-25);
      lines.forEach((line) => {
        if (line.trim()) {
          appendConsoleLine(`[LOG] ${line}`);
        }
      });
    }

    lastLogSnapshot.value = current;
  } catch (error) {
    const message = error instanceof Error ? error.message : "未知错误";
    appendConsoleLine(`[ERROR] 拉取系统日志失败: ${message}`);
  }
};

const decodeHtmlLikeText = (text: string): string => {
  return text
    .replace(/^<pre>/i, "")
    .replace(/<\/pre>$/i, "")
    .replace(/<br\s*\/?\s*>/gi, "\n")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
};

const runUnifiedCommand = async () => {
  const cmd = cmdInput.value.trim();
  if (!cmd) {
    appendConsoleLine("[WARN] 请输入命令后再执行");
    return;
  }

  appendConsoleLine(`[CMD] ${cmd}`);
  try {
    const response = await fetch("/api/exec_cmd", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ cmd })
    });
    const html = await response.text();
    const text = decodeHtmlLikeText(html);
    text
      .split("\n")
      .slice(0, 80)
      .forEach((line) => appendConsoleLine(`[OUT] ${line}`));
  } catch (error) {
    const message = error instanceof Error ? error.message : "未知错误";
    appendConsoleLine(`[ERROR] 命令执行失败: ${message}`);
  } finally {
    cmdInput.value = "";
    await refreshUnifiedConsole(false);
  }
};

const fetchMonitoringData = async () => {
  try {
    const response = await fetch("/api/monitoring");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = (await response.json()) as Partial<MonitoringData>;
    stats.cpu_percent = data.cpu_percent ?? 0;
    stats.memory_percent = data.memory_percent ?? 0;
    stats.uptime = data.uptime ?? 0;
    stats.token_stats.input_tokens = data.token_stats?.input_tokens ?? 0;
    stats.token_stats.output_tokens = data.token_stats?.output_tokens ?? 0;
    stats.token_stats.total_tokens = data.token_stats?.total_tokens ?? 0;
    stats.system_info.cpu = data.system_info?.cpu ?? "";
    stats.system_info.cpu_count = data.system_info?.cpu_count ?? 0;
    stats.system_info.total_memory = data.system_info?.total_memory ?? 0;
    stats.system_info.used_memory = data.system_info?.used_memory ?? 0;
    stats.system_info.python_version = data.system_info?.python_version ?? "";
    stats.system_info.platform = data.system_info?.platform ?? "";

    pushHistory(cpuHistory.value, stats.cpu_percent);
    pushHistory(memoryHistory.value, stats.memory_percent);
  } catch (error) {
    const message = error instanceof Error ? error.message : "未知错误";
    appendConsoleLine(`[ERROR] 获取监控数据失败: ${message}`);
  }
};

onMounted(() => {
  void fetchMonitoringData();
  void refreshUnifiedConsole(true);
  monitorTimer = window.setInterval(() => {
    void fetchMonitoringData();
  }, 2000);
  consoleTimer = window.setInterval(() => {
    void refreshUnifiedConsole(false);
  }, 3000);
});

onUnmounted(() => {
  if (monitorTimer !== null) {
    window.clearInterval(monitorTimer);
  }
  if (consoleTimer !== null) {
    window.clearInterval(consoleTimer);
  }
});
</script>