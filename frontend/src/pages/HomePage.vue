<template>
  <section class="dashboard-page">
    <header class="dashboard-header">
      <div>
        <p class="dashboard-eyebrow">Legacy -> Vue3</p>
        <h1>控制中心 Dashboard</h1>
        <p>已迁移 legacy 控制面板的首页模块，后续页面将按清单逐个替换。</p>
      </div>
    </header>

    <div class="quick-grid">
      <article v-for="action in quickActions" :key="action.title" class="quick-card">
        <h3>{{ action.title }}</h3>
        <p>{{ action.description }}</p>
      </article>
    </div>

    <div class="stats-layout">
      <article class="panel resource-panel">
        <div class="panel-header">
          <h2>实时资源流</h2>
          <span class="pill success">Running</span>
        </div>
        <div class="mock-chart" role="img" aria-label="资源趋势图占位图" />
      </article>

      <article class="panel summary-panel">
        <h2>系统摘要</h2>
        <ul>
          <li>
            <span>CPU Load</span>
            <b class="pill danger">34%</b>
          </li>
          <li>
            <span>RAM Usage</span>
            <b class="pill primary">62%</b>
          </li>
          <li>
            <span>Total Tokens</span>
            <b>128,032</b>
          </li>
          <li>
            <span>OS</span>
            <b>Windows</b>
          </li>
        </ul>
      </article>
    </div>

    <article class="panel migration-panel">
      <h2>静态页迁移清单</h2>
      <div class="migration-list">
        <div v-for="page in migrationPages" :key="page.name" class="migration-item">
          <span>{{ page.name }}</span>
          <span :class="['status-tag', page.status]">{{ page.label }}</span>
        </div>
      </div>
    </article>
  </section>
</template>

<script setup lang="ts">
import { storeToRefs } from "pinia";
import { useAppStore } from "../store/app";

type MigrationPage = {
  name: string;
  status: "done" | "todo";
  label: string;
};

const appStore = useAppStore();
const { counter } = storeToRefs(appStore);

const increment = () => {
  appStore.increment();
};

const quickActions = [
  { title: "快速对话", description: "进入沙箱测试环境" },
  { title: "系统诊断", description: "运行自检程序" },
  { title: "配置中心", description: "修改核心参数" },
  { title: "查看日志", description: "定位线上问题" }
];

const migrationPages: MigrationPage[] = [
  { name: "control_panel.html (Dashboard)", status: "done", label: "已迁移" },
  { name: "chat-sandbox.html", status: "done", label: "已迁移" },
  { name: "config_editor.html", status: "done", label: "已迁移" },
  { name: "db_management.html", status: "done", label: "已迁移" },
  { name: "diagnosis.html", status: "done", label: "已迁移" },
  { name: "logs.html", status: "done", label: "已迁移" },
  { name: "monitoring.html", status: "done", label: "已迁移" },
  { name: "adapter_console.html", status: "done", label: "已迁移" },
  { name: "adapter_logs.html", status: "done", label: "已迁移" },
  { name: "security-init.html", status: "done", label: "已迁移" }
];
</script>
