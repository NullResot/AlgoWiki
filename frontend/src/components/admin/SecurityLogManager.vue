<template>
  <section class="manager-stack">
    <header class="section-head">
      <div>
        <h2>安全日志</h2>
        <p class="meta">查看登录与账号安全事件，并按时间窗口和明细条件筛选。</p>
      </div>
      <button class="btn" type="button" @click="loadAll">刷新安全日志</button>
    </header>

    <div class="toolbar">
      <select v-model="windowHours" class="select" @change="loadSummary">
        <option :value="6">最近 6 小时</option>
        <option :value="24">最近 24 小时</option>
        <option :value="72">最近 72 小时</option>
        <option :value="168">最近 7 天</option>
      </select>
      <button class="btn" type="button" :disabled="summaryLoading" @click="loadSummary">
        {{ summaryLoading ? "刷新中..." : "刷新安全概览" }}
      </button>
    </div>

    <div v-if="summary" class="summary-grid">
      <div class="summary-item">
        <strong>{{ summary.totals?.failed_events ?? 0 }}</strong>
        <span>失败事件</span>
      </div>
      <div class="summary-item">
        <strong>{{ summary.totals?.login_failed ?? 0 }}</strong>
        <span>登录失败</span>
      </div>
      <div class="summary-item">
        <strong>{{ summary.totals?.login_locked ?? 0 }}</strong>
        <span>登录锁定</span>
      </div>
      <div class="summary-item">
        <strong>{{ summary.unique?.ips ?? 0 }}</strong>
        <span>异常 IP 数</span>
      </div>
      <div class="summary-item">
        <strong>{{ summary.unique?.usernames ?? 0 }}</strong>
        <span>异常用户名数</span>
      </div>
      <div class="summary-item">
        <strong>{{ summary.totals?.all_events ?? 0 }}</strong>
        <span>总安全事件</span>
      </div>
    </div>

    <p v-if="summary?.since" class="meta">统计起点：{{ formatDateTime(summary.since) }}</p>

    <div v-if="summary?.top_failed_ips?.length" class="top-ip-list">
      <div v-for="item in summary.top_failed_ips" :key="item.ip_address" class="top-ip-row">
        <span>{{ item.ip_address }}</span>
        <div class="bar-track">
          <div class="bar-fill" :style="{ width: `${barPercent(item.count)}%` }"></div>
        </div>
        <strong>{{ item.count }}</strong>
      </div>
    </div>

    <div class="toolbar">
      <select v-model="filters.event_type" class="select" @change="loadLogs(1, false)">
        <option value="">全部事件</option>
        <option value="login_success">登录成功</option>
        <option value="login_failed">登录失败</option>
        <option value="login_locked">登录锁定</option>
        <option value="login_denied">登录拒绝</option>
        <option value="register_success">注册成功</option>
        <option value="logout">退出登录</option>
        <option value="password_changed">密码修改</option>
        <option value="user_banned">账号封禁</option>
        <option value="user_unbanned">账号解封</option>
        <option value="user_soft_deleted">账号软删除</option>
        <option value="user_reactivated">账号恢复</option>
        <option value="user_role_changed">角色变更</option>
      </select>
      <select v-model="filters.success" class="select" @change="loadLogs(1, false)">
        <option value="">全部结果</option>
        <option value="1">成功</option>
        <option value="0">失败</option>
      </select>
      <input v-model="filters.username" class="input" placeholder="用户名" @keyup.enter="loadLogs(1, false)" />
      <input v-model="filters.ip" class="input" placeholder="IP 地址" @keyup.enter="loadLogs(1, false)" />
      <input v-model="filters.detail" class="input grow" placeholder="关键词（detail）" @keyup.enter="loadLogs(1, false)" />
      <input v-model="filters.start_at" class="input" type="datetime-local" />
      <input v-model="filters.end_at" class="input" type="datetime-local" />
      <button class="btn" type="button" :disabled="logsLoading" @click="loadLogs(1, false)">
        {{ logsLoading ? "筛选中..." : "筛选" }}
      </button>
      <button class="btn" type="button" :disabled="exporting" @click="exportLogs">
        {{ exporting ? "导出中..." : "导出 CSV" }}
      </button>
      <button class="btn" type="button" :disabled="logsLoading" @click="resetFilters">重置</button>
    </div>

    <p class="meta">共 {{ meta.count }} 条安全事件</p>

    <article v-for="item in logs" :key="item.id" class="admin-row">
      <div class="row-main">
        <strong>{{ formatSecurityEventType(item.event_type) }}</strong>
        <p class="meta">
          用户 {{ item.username || item.user?.username || "匿名" }} ·
          {{ item.ip_address || "-" }} ·
          {{ item.success ? "成功" : "失败" }} ·
          {{ formatDateTime(item.created_at) }}
        </p>
        <p class="payload">{{ item.detail || "-" }}</p>
      </div>
    </article>

    <div v-if="logsLoading && !logs.length" class="loading-box">
      <SkeletonBlock :lines="3" :line-height="18" label="正在加载安全日志" />
    </div>
    <button v-if="meta.hasMore" class="btn" type="button" :disabled="logsLoading" @click="loadMoreLogs">
      {{ logsLoading ? "加载中..." : "加载更多安全日志" }}
    </button>
    <p v-if="!logsLoading && !logs.length" class="meta">当前没有匹配的安全日志。</p>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import SkeletonBlock from "../SkeletonBlock.vue";
import api from "../../services/api";
import { useUiStore } from "../../stores/ui";

const ui = useUiStore();

const windowHours = ref(24);
const summary = ref(null);
const summaryLoading = ref(false);
const logsLoading = ref(false);
const exporting = ref(false);
const logs = ref([]);

const meta = reactive({
  count: 0,
  page: 1,
  hasMore: false,
});

const filters = reactive({
  event_type: "",
  success: "",
  username: "",
  ip: "",
  detail: "",
  start_at: "",
  end_at: "",
});

const topIpMax = computed(() => {
  const rows = Array.isArray(summary.value?.top_failed_ips) ? summary.value.top_failed_ips : [];
  const max = Math.max(...rows.map((item) => Number(item.count) || 0), 0);
  return max || 1;
});

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return error?.message || fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  return fallback;
}

function unpackListPayload(data) {
  if (Array.isArray(data)) {
    return { results: data, count: data.length };
  }
  const results = Array.isArray(data?.results) ? data.results : [];
  const count = Number.isFinite(data?.count) ? data.count : results.length;
  return { results, count };
}

function appendUniqueById(baseList, extraList) {
  const existed = new Set(baseList.map((item) => item.id));
  const merged = [...baseList];
  for (const item of extraList) {
    if (!existed.has(item.id)) {
      existed.add(item.id);
      merged.push(item);
    }
  }
  return merged;
}

function buildLogParams(page = 1) {
  const params = { page };
  if (filters.event_type) params.event_type = filters.event_type;
  if (filters.success) params.success = filters.success;
  if (filters.username.trim()) params.username = filters.username.trim();
  if (filters.ip.trim()) params.ip = filters.ip.trim();
  if (filters.detail.trim()) params.detail = filters.detail.trim();
  if (filters.start_at) params.start_at = filters.start_at;
  if (filters.end_at) params.end_at = filters.end_at;
  return params;
}

async function loadSummary() {
  summaryLoading.value = true;
  try {
    const { data } = await api.get("/security-logs/summary/", {
      params: { window_hours: windowHours.value },
    });
    summary.value = data;
  } catch (error) {
    ui.error(getErrorText(error, "安全概览加载失败"));
  } finally {
    summaryLoading.value = false;
  }
}

async function loadLogs(page = 1, append = false) {
  logsLoading.value = true;
  try {
    const { data } = await api.get("/security-logs/", { params: buildLogParams(page) });
    const { results, count } = unpackListPayload(data);
    logs.value = append ? appendUniqueById(logs.value, results) : results;
    meta.count = count;
    meta.page = page;
    meta.hasMore = logs.value.length < count;
  } catch (error) {
    ui.error(getErrorText(error, "安全日志加载失败"));
  } finally {
    logsLoading.value = false;
  }
}

async function loadMoreLogs() {
  if (!meta.hasMore || logsLoading.value) return;
  await loadLogs(meta.page + 1, true);
}

async function loadAll() {
  await Promise.all([loadSummary(), loadLogs()]);
}

function resetFilters() {
  filters.event_type = "";
  filters.success = "";
  filters.username = "";
  filters.ip = "";
  filters.detail = "";
  filters.start_at = "";
  filters.end_at = "";
  loadLogs(1, false);
}

async function exportLogs() {
  if (exporting.value) return;
  exporting.value = true;
  try {
    const response = await api.get("/security-logs/export/", {
      params: buildLogParams(1),
      responseType: "blob",
    });
    const blob = new Blob([response.data], { type: "text/csv;charset=utf-8;" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `algowiki-security-${Date.now()}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
    ui.success("安全日志已导出");
  } catch (error) {
    ui.error(getErrorText(error, "导出安全日志失败"));
  } finally {
    exporting.value = false;
  }
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatSecurityEventType(value) {
  const labels = {
    login_success: "登录成功",
    login_failed: "登录失败",
    login_locked: "登录锁定",
    login_denied: "登录拒绝",
    register_success: "注册成功",
    logout: "退出登录",
    password_changed: "密码修改",
    user_banned: "账号封禁",
    user_unbanned: "账号解封",
    user_soft_deleted: "账号软删除",
    user_reactivated: "账号恢复",
    user_role_changed: "角色变更",
  };
  return labels[value] || value || "未知事件";
}

function barPercent(value) {
  return Math.round(((Number(value) || 0) / topIpMax.value) * 100);
}

onMounted(() => {
  loadAll();
});
</script>

<style scoped>
.manager-stack {
  display: grid;
  gap: 12px;
}

.section-head,
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.section-head {
  justify-content: space-between;
  align-items: start;
}

.grow {
  flex: 1 1 260px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}

.summary-item {
  display: grid;
  gap: 4px;
  padding: 12px;
  border-radius: 14px;
  background: var(--surface-soft);
  border: 1px solid var(--hairline);
}

.summary-item strong {
  font-size: 24px;
  font-variant-numeric: tabular-nums;
}

.top-ip-list {
  display: grid;
  gap: 8px;
}

.top-ip-row {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
}

.bar-track {
  height: 10px;
  border-radius: 999px;
  background: var(--surface-soft);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: inherit;
  background: var(--accent-gradient);
  transition: width var(--dur-base) var(--ease-out);
}

@media (prefers-reduced-motion: reduce) {
  .bar-fill {
    transition: none;
  }
}

.admin-row {
  padding: 12px;
  border-radius: 14px;
  background: var(--surface-soft);
  border: 1px solid var(--hairline);
}

.row-main {
  min-width: 0;
}

.meta,
.payload {
  margin: 0;
}

.meta {
  color: var(--text-quiet);
}

.payload {
  margin-top: 6px;
  color: var(--text-soft);
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 1100px) {
  .summary-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .top-ip-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
