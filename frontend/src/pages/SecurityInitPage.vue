<template>
  <section class="security-init-page">
    <div class="security-card">
      <div v-if="!successVisible" class="security-form-wrap">
        <header class="security-header">
          <h1>安全系统初始化</h1>
          <p>设置两层密码以保护系统安全</p>
        </header>

        <div v-if="status.message" :class="['security-status', status.type]">
          {{ status.message }}
        </div>

        <form class="security-form" @submit.prevent="submitForm">
          <section>
            <h3 class="security-section-title">第一层：工作模式密码</h3>
            <p class="security-section-desc">用于启用文件操作和 workspace 访问权限。</p>

            <label>
              工作模式密码
              <input v-model="form.level1Password" type="password" placeholder="至少 8 个字符" autocomplete="off" />
              <span class="security-help">请牢记此密码，忘记后无法恢复</span>
            </label>
            <div class="strength-indicator">
              <div :class="['strength-bar', getStrengthClass(form.level1Password)]" />
            </div>

            <label>
              确认工作模式密码
              <input v-model="form.level1Confirm" type="password" placeholder="再次输入密码" autocomplete="off" />
            </label>
          </section>

          <div class="security-separator" />

          <section>
            <h3 class="security-section-title">第二层：全局管理密码</h3>
            <p class="security-section-desc">用于启用全局系统访问，风险更高，请设置为更强的密码。</p>

            <label>
              全局管理密码
              <input
                v-model="form.level2Password"
                type="password"
                placeholder="至少 8 个字符，建议 12+ 个"
                autocomplete="off"
              />
              <span class="security-help">此密码权限最高，请设置强密码</span>
            </label>
            <div class="strength-indicator">
              <div :class="['strength-bar', getStrengthClass(form.level2Password)]" />
            </div>

            <label>
              确认全局管理密码
              <input v-model="form.level2Confirm" type="password" placeholder="再次输入密码" autocomplete="off" />
            </label>
          </section>

          <div class="security-warning">
            <strong>重要提示：</strong>
            不要在代码中、版本控制系统中或任何文档中保存这些密码。定期更改密码以维护系统安全。
          </div>

          <div class="security-actions">
            <button type="button" class="btn ghost" :disabled="submitting" @click="cancelInit">取消</button>
            <button type="submit" class="btn" :disabled="submitting">
              {{ submitting ? "初始化中..." : "初始化安全系统" }}
            </button>
          </div>
        </form>
      </div>

      <div v-else class="security-success">
        <div class="security-success-icon">已完成</div>
        <h2>初始化成功</h2>
        <p>安全系统已配置完成。现在可以使用两层密码保护系统。</p>
        <p class="security-countdown">系统将在 {{ countdown }} 秒后自动返回...</p>
        <button type="button" class="btn" @click="goBackToSystem">返回系统</button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onUnmounted, reactive, ref } from "vue";

const form = reactive({
  level1Password: "",
  level1Confirm: "",
  level2Password: "",
  level2Confirm: ""
});

const submitting = ref(false);
const successVisible = ref(false);
const countdown = ref(3);
const status = reactive<{ type: "success" | "error"; message: string }>({
  type: "error",
  message: ""
});

let countdownTimer: number | null = null;

const showStatus = (message: string, type: "success" | "error" = "error") => {
  status.message = message;
  status.type = type;
};

const calculateStrength = (password: string): number => {
  let strength = 0;
  if (password.length >= 8) {
    strength += 20;
  }
  if (password.length >= 12) {
    strength += 20;
  }
  if (/[a-z]/.test(password)) {
    strength += 15;
  }
  if (/[A-Z]/.test(password)) {
    strength += 15;
  }
  if (/[0-9]/.test(password)) {
    strength += 15;
  }
  if (/[^a-zA-Z0-9]/.test(password)) {
    strength += 15;
  }
  return Math.min(strength, 100);
};

const getStrengthClass = (password: string): "weak" | "medium" | "strong" | "" => {
  if (!password) {
    return "";
  }
  const strength = calculateStrength(password);
  if (strength < 50) {
    return "weak";
  }
  if (strength < 80) {
    return "medium";
  }
  return "strong";
};

const goBackToSystem = () => {
  window.location.href = "/sandbox";
};

const cancelInit = () => {
  window.close();
  window.location.href = "/sandbox";
};

const validateForm = (): boolean => {
  if (form.level1Password.length < 8) {
    showStatus("工作模式密码至少需要 8 个字符");
    return false;
  }
  if (form.level1Password !== form.level1Confirm) {
    showStatus("工作模式密码不匹配");
    return false;
  }
  if (form.level2Password.length < 8) {
    showStatus("全局管理密码至少需要 8 个字符");
    return false;
  }
  if (form.level2Password !== form.level2Confirm) {
    showStatus("全局管理密码不匹配");
    return false;
  }
  if (form.level1Password === form.level2Password) {
    showStatus("两层密码不应相同，为了安全请设置不同的密码");
    return false;
  }
  return true;
};

const showSuccess = () => {
  successVisible.value = true;
  status.message = "";
  countdown.value = 3;

  if (countdownTimer !== null) {
    window.clearInterval(countdownTimer);
  }

  countdownTimer = window.setInterval(() => {
    countdown.value -= 1;
    if (countdown.value <= 0) {
      if (countdownTimer !== null) {
        window.clearInterval(countdownTimer);
      }
      goBackToSystem();
    }
  }, 1000);
};

const submitForm = async () => {
  if (!validateForm()) {
    return;
  }

  submitting.value = true;
  showStatus("");
  try {
    const response = await fetch("/api/security/config/set-passwords", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        level1_password: form.level1Password,
        level2_password: form.level2Password
      })
    });

    const data = (await response.json()) as { ok?: boolean; error?: string };
    if (!response.ok || !data.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    showSuccess();
  } catch (error) {
    const message = error instanceof Error ? error.message : "未知错误";
    showStatus(`初始化失败: ${message}`);
  } finally {
    submitting.value = false;
  }
};

onUnmounted(() => {
  if (countdownTimer !== null) {
    window.clearInterval(countdownTimer);
  }
});
</script>