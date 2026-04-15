<template>
  <section class="db-page">
    <header class="db-header">
      <h1>数据库管理</h1>
      <p>迁移自 legacy db_management.html，支持记录查询与删除操作。</p>
    </header>

    <article class="panel db-actions">
      <div class="db-actions-left">
        <input v-model.number="deleteCount" type="number" min="1" placeholder="N" />
        <button type="button" class="btn danger" :disabled="loading" @click="deleteFirstN">
          删除前 N 条记录
        </button>
      </div>
      <div class="db-actions-right">
        <button type="button" class="btn ghost" :disabled="loading" @click="clearAll">
          清空所有记录
        </button>
        <button type="button" class="btn" :disabled="loading" @click="refreshRecords">
          {{ loading ? "刷新中..." : "刷新记录" }}
        </button>
      </div>
    </article>

    <div v-if="status.message" :class="['db-status', status.type]">
      {{ status.message }}
    </div>

    <article class="panel db-table-panel">
      <h2>数据记录</h2>
      <div class="db-table-wrap">
        <table class="db-table">
          <thead>
            <tr>
              <th>#</th>
              <th>记录详情</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(record, index) in records" :key="getRecordKey(record, index)">
              <td>{{ index + 1 }}</td>
              <td>
                <pre class="db-record-json">{{ stringifyRecord(record) }}</pre>
              </td>
              <td>
                <button
                  type="button"
                  class="btn danger small"
                  :disabled="loading"
                  @click="deleteRecord(record)"
                >
                  删除
                </button>
              </td>
            </tr>
            <tr v-if="records.length === 0">
              <td colspan="3" class="db-empty">暂无记录</td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";

type RecordValue = Record<string, unknown> | unknown[];

const records = ref<RecordValue[]>([]);
const deleteCount = ref<number | null>(null);
const loading = ref(false);
const status = reactive<{ type: "success" | "error"; message: string }>({
  type: "success",
  message: ""
});

const setStatus = (type: "success" | "error", message: string) => {
  status.type = type;
  status.message = message;
};

const stringifyRecord = (record: RecordValue): string => {
  try {
    return JSON.stringify(record, null, 2);
  } catch {
    return String(record);
  }
};

const getRecordId = (record: RecordValue): number | null => {
  if (Array.isArray(record)) {
    const value = record[0];
    if (typeof value === "number") {
      return value;
    }
    if (typeof value === "string" && value.trim()) {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    }
    return null;
  }

  const maybeId = (record as { id?: unknown }).id;
  if (typeof maybeId === "number") {
    return maybeId;
  }
  if (typeof maybeId === "string" && maybeId.trim()) {
    const parsed = Number(maybeId);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const getRecordKey = (record: RecordValue, index: number): string => {
  const id = getRecordId(record);
  return id === null ? `row-${index}` : `id-${id}`;
};

const refreshRecords = async () => {
  loading.value = true;
  try {
    const response = await fetch("/api/records?limit=200&offset=0");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = (await response.json()) as RecordValue[];
    records.value = Array.isArray(data) ? data : [];
    setStatus("success", `已加载 ${records.value.length} 条记录`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "未知错误";
    setStatus("error", `加载记录失败: ${message}`);
  } finally {
    loading.value = false;
  }
};

const deleteRecord = async (record: RecordValue) => {
  const id = getRecordId(record);
  if (id === null) {
    setStatus("error", "当前记录无法识别 ID，无法删除");
    return;
  }
  if (!window.confirm(`确认删除 ID=${id} ?`)) {
    return;
  }

  loading.value = true;
  try {
    const response = await fetch("/api/delete_record", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ id })
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    setStatus("success", `已删除记录 ID=${id}`);
    await refreshRecords();
  } catch (error) {
    const message = error instanceof Error ? error.message : "未知错误";
    setStatus("error", `删除记录失败: ${message}`);
  } finally {
    loading.value = false;
  }
};

const clearAll = async () => {
  if (!window.confirm("确认清空所有聊天记录？")) {
    return;
  }

  loading.value = true;
  try {
    const response = await fetch("/api/clear_records", {
      method: "POST"
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    setStatus("success", "已清空所有记录");
    await refreshRecords();
  } catch (error) {
    const message = error instanceof Error ? error.message : "未知错误";
    setStatus("error", `清空记录失败: ${message}`);
  } finally {
    loading.value = false;
  }
};

const deleteFirstN = async () => {
  const n = deleteCount.value;
  if (!n || n < 1) {
    setStatus("error", "请输入有效 N");
    return;
  }

  loading.value = true;
  try {
    const response = await fetch("/api/delete_first_n", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ n })
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    setStatus("success", `已删除前 ${n} 条记录`);
    deleteCount.value = null;
    await refreshRecords();
  } catch (error) {
    const message = error instanceof Error ? error.message : "未知错误";
    setStatus("error", `删除前 N 条记录失败: ${message}`);
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  void refreshRecords();
});
</script>