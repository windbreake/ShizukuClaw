<template>
  <section class="diagnosis-page">
    <header class="diagnosis-header">
      <h1>服务诊断</h1>
      <p>迁移自 legacy diagnosis.html，执行服务自检并展示诊断输出。</p>
    </header>

    <article class="panel diagnosis-actions">
      <button type="button" class="btn" :disabled="loading" @click="runDiagnosis">
        {{ loading ? "诊断中..." : "运行诊断" }}
      </button>
      <button type="button" class="btn ghost" :disabled="loading" @click="clearResult">清空结果</button>
    </article>

    <article class="panel diagnosis-result-panel">
      <h2>诊断结果</h2>
      <div class="diagnosis-result" v-html="resultHtml" />
    </article>
  </section>
</template>

<script setup lang="ts">
import { ref } from "vue";

const loading = ref(false);
const resultHtml = ref('点击"运行诊断"按钮开始诊断...');

const runDiagnosis = async () => {
  loading.value = true;
  resultHtml.value = "正在运行诊断...";
  try {
    const response = await fetch("/api/diagnosis");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    resultHtml.value = await response.text();
  } catch (error) {
    const message = error instanceof Error ? error.message : "未知错误";
    resultHtml.value = `诊断执行失败: ${message}`;
  } finally {
    loading.value = false;
  }
};

const clearResult = () => {
  resultHtml.value = "";
};
</script>