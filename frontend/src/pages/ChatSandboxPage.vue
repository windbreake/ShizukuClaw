<template>
  <section class="sandbox-page">
    <header class="sandbox-header">
      <h1>沙箱聊天</h1>
      <p>已迁移 chat-sandbox.html 核心结构，后续接入真实对话 API 与审批流程。</p>
    </header>

    <div class="sandbox-layout">
      <article class="panel sandbox-chat">
        <div class="chat-title">会话窗口</div>
        <div class="chat-messages">
          <div class="message bot">你好，我是沙箱助手。请输入你的任务需求。</div>
          <div class="message user">请帮我分析当前前端迁移进度。</div>
          <div class="message bot">已完成 Dashboard 与 Sandbox 基础页面迁移，下一步建议迁移配置和日志模块。</div>
        </div>
        <div class="chat-input">
          <textarea v-model="message" placeholder="输入消息，后续将对接 API..." />
          <button type="button" class="btn" @click="sendMock">发送</button>
        </div>
      </article>

      <article class="panel sandbox-side">
        <h2>工作模式</h2>
        <div class="mode-row">
          <span>当前模式</span>
          <b class="pill primary">Safe</b>
        </div>

        <h2>快捷动作</h2>
        <div class="quick-actions-grid">
          <button type="button" class="btn ghost">运行诊断</button>
          <button type="button" class="btn ghost">查看日志</button>
          <button type="button" class="btn ghost">打开配置</button>
          <button type="button" class="btn ghost">刷新状态</button>
        </div>

        <h2>审批队列</h2>
        <div class="approval-placeholder">暂无待审批项目</div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from "vue";

const message = ref("");

const sendMock = () => {
  message.value = "";
};
</script>
