<template>
  <section class="manager-stack">
    <header class="section-head">
      <div>
        <h2>验证码管理</h2>
        <p class="meta">查看 Turnstile、人机验证、二次验证配置状态和验证码审计日志。</p>
      </div>
      <button class="btn" type="button" :disabled="loading" @click="loadAll">
        {{ loading ? "刷新中..." : "刷新验证码状态" }}
      </button>
    </header>

    <section v-if="overview" class="status-panel" :class="`status-panel--${configStatus}`">
      <div>
        <p class="eyebrow">CONFIGURATION</p>
        <h3>{{ statusTitle }}</h3>
        <p class="meta">
          网页端只显示配置是否存在，不显示任何密钥内容。密钥仍需在服务器环境文件中维护。
        </p>
      </div>
      <span class="status-pill">{{ statusLabel }}</span>
    </section>

    <div v-if="configIssues.length" class="issue-list">
      <p class="issue-title">需要处理</p>
      <p v-for="issue in configIssues" :key="issue" class="issue-item">{{ issue }}</p>
    </div>

    <div v-if="config" class="config-grid">
      <div class="config-card">
        <span>总开关</span>
        <strong>{{ config.enabled ? "已开启" : "未开启" }}</strong>
        <p class="meta">CAPTCHA_ENABLED</p>
      </div>
      <div class="config-card">
        <span>登录用户也验证</span>
        <strong>{{ config.required_for_authenticated_users ? "是" : "否" }}</strong>
        <p class="meta">CAPTCHA_REQUIRED_FOR_AUTHENTICATED_USERS</p>
      </div>
      <div class="config-card">
        <span>Turnstile site key</span>
        <strong>{{ config.turnstile?.site_key_configured ? "已配置" : "缺失" }}</strong>
        <p class="meta">前端渲染必需</p>
      </div>
      <div class="config-card">
        <span>Turnstile secret key</span>
        <strong>{{ config.turnstile?.secret_key_configured ? "已配置" : "缺失" }}</strong>
        <p class="meta">后端校验必需</p>
      </div>
      <div class="config-card">
        <span>二次验证</span>
        <strong>{{ config.secondary?.enabled ? "已开启" : "未开启" }}</strong>
        <p class="meta">{{ config.secondary?.provider || "geetest" }}</p>
      </div>
      <div class="config-card">
        <span>Token 有效期</span>
        <strong>{{ config.token_ttl_seconds || 300 }} 秒</strong>
        <p class="meta">CAPTCHA_TOKEN_TTL</p>
      </div>
    </div>

    <div class="toolbar">
      <select v-model="windowHours" class="select">
        <option :value="6">最近 6 小时</option>
        <option :value="24">最近 24 小时</option>
        <option :value="72">最近 72 小时</option>
        <option :value="168">最近 7 天</option>
      </select>
      <button class="btn" type="button" :disabled="summaryLoading" @click="loadSummary">
        {{ summaryLoading ? "刷新中..." : "刷新统计" }}
      </button>
    </div>

    <div v-if="summary" class="summary-grid">
      <div class="summary-item">
        <strong>{{ summary.totals?.all ?? 0 }}</strong>
        <span>验证请求</span>
      </div>
      <div class="summary-item">
        <strong>{{ summary.totals?.success ?? 0 }}</strong>
        <span>成功</span>
      </div>
      <div class="summary-item">
        <strong>{{ summary.totals?.failed ?? 0 }}</strong>
        <span>失败</span>
      </div>
      <div class="summary-item">
        <strong>{{ successRate }}%</strong>
        <span>成功率</span>
      </div>
      <div class="summary-item">
        <strong>{{ summary.totals?.turnstile_success ?? 0 }}</strong>
        <span>Turnstile 通过</span>
      </div>
      <div class="summary-item">
        <strong>{{ summary.totals?.secondary_success ?? 0 }}</strong>
        <span>二次验证通过</span>
      </div>
    </div>

    <div v-if="summary" class="insight-grid">
      <section class="insight-card">
        <h3>场景分布</h3>
        <div v-if="summary.by_scene?.length" class="mini-list">
          <div v-for="item in summary.by_scene" :key="item.scene" class="mini-row">
            <span>{{ sceneLabel(item.scene) }}</span>
            <strong>{{ item.count }}</strong>
          </div>
        </div>
        <p v-else class="meta">暂无数据。</p>
      </section>

      <section class="insight-card">
        <h3>失败原因</h3>
        <div v-if="summary.by_error_code?.length" class="mini-list">
          <div v-for="item in summary.by_error_code" :key="item.error_code || 'unknown'" class="mini-row">
            <span>{{ formatErrorCode(item.error_code) }}</span>
            <strong>{{ item.count }}</strong>
          </div>
        </div>
        <p v-else class="meta">暂无失败记录。</p>
      </section>

      <section class="insight-card">
        <h3>失败 IP</h3>
        <div v-if="summary.top_failed_ips?.length" class="mini-list">
          <div v-for="item in summary.top_failed_ips" :key="item.ip_address" class="mini-row">
            <span>{{ item.ip_address }}</span>
            <strong>{{ item.count }}</strong>
          </div>
        </div>
        <p v-else class="meta">暂无异常 IP。</p>
      </section>
    </div>

    <section v-if="summary?.recent_failures?.length" class="recent-failures">
      <h3>最近失败</h3>
      <article v-for="item in summary.recent_failures" :key="item.id" class="failure-row">
        <strong>{{ sceneLabel(item.scene) }} · {{ formatErrorCode(item.error_code) }}</strong>
        <p class="meta">
          {{ item.user__username || "anonymous" }} · {{ item.ip_address || "-" }} ·
          {{ item.target_type || "-" }} · {{ formatDateTime(item.created_at) }}
        </p>
        <p class="payload">{{ formatErrorMessage(item.error_message) }}</p>
      </article>
    </section>

    <div class="toolbar">
      <select v-model="filters.scene" class="select">
        <option value="">全部场景</option>
        <option v-for="item in sceneOptions" :key="item.key" :value="item.key">
          {{ item.label }}
        </option>
      </select>
      <select v-model="filters.result" class="select">
        <option value="">全部结果</option>
        <option value="success">success</option>
        <option value="failed">failed</option>
      </select>
      <select v-model="filters.error_code" class="select">
        <option value="">全部错误</option>
        <option value="CAPTCHA_REQUIRED">CAPTCHA_REQUIRED</option>
        <option value="CAPTCHA_INVALID">CAPTCHA_INVALID</option>
        <option value="CAPTCHA_RATE_LIMITED">CAPTCHA_RATE_LIMITED</option>
        <option value="CAPTCHA_PROVIDER_ERROR">CAPTCHA_PROVIDER_ERROR</option>
        <option value="CAPTCHA_DUPLICATED">CAPTCHA_DUPLICATED</option>
      </select>
      <input v-model="filters.user" class="input" placeholder="用户 ID / 用户名" />
      <input v-model="filters.ip" class="input" placeholder="IP 地址" />
      <input v-model="filters.target_type" class="input" placeholder="目标类型" />
      <input v-model="filters.search" class="input grow" placeholder="错误信息 / UA / target hash" />
      <input v-model="filters.start_at" class="input" type="datetime-local" />
      <input v-model="filters.end_at" class="input" type="datetime-local" />
      <button class="btn" type="button" @click="loadLogs">筛选</button>
      <button class="btn" type="button" @click="exportLogs">导出 CSV</button>
      <button class="btn" type="button" @click="resetFilters">重置</button>
    </div>

    <p class="meta">共 {{ meta.count }} 条验证码日志</p>

    <article v-for="item in logs" :key="item.id" class="admin-row">
      <div class="row-main">
        <strong>{{ sceneLabel(item.scene) }} · {{ item.result }}</strong>
        <p class="meta">
          {{ item.user?.username || "anonymous" }} · {{ item.ip_address || "-" }} ·
          {{ item.target_type || "-" }} · {{ formatDateTime(item.created_at) }}
        </p>
        <p class="payload">
          {{ formatErrorCode(item.error_code) || "无错误" }} ·
          Turnstile={{ item.turnstile_success ? "pass" : "no" }} ·
          Secondary={{ item.secondary_success ? "pass" : "no" }}
        </p>
        <p v-if="item.error_message" class="payload">{{ formatErrorMessage(item.error_message) }}</p>
      </div>
    </article>

    <button v-if="meta.hasMore" class="btn" type="button" @click="loadMoreLogs">加载更多验证码日志</button>
    <p v-if="!logs.length" class="meta">当前没有匹配的验证码日志。</p>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import api from "../../services/api";
import { useUiStore } from "../../stores/ui";

const ui = useUiStore();

const loading = ref(false);
const summaryLoading = ref(false);
const overview = ref(null);
const summary = ref(null);
const logs = ref([]);
const windowHours = ref(24);

const meta = reactive({
  count: 0,
  page: 1,
  hasMore: false,
});

const filters = reactive({
  scene: "",
  result: "",
  error_code: "",
  user: "",
  ip: "",
  target_type: "",
  search: "",
  start_at: "",
  end_at: "",
});

const config = computed(() => overview.value?.config || summary.value?.config || null);
const configStatus = computed(() => config.value?.status || "unknown");
const configIssues = computed(() => config.value?.issues || []);
const sceneMap = computed(() => config.value?.scene_labels || {});
const sceneOptions = computed(() =>
  Object.entries(sceneMap.value).map(([key, label]) => ({ key, label }))
);

const statusLabel = computed(() => {
  if (configStatus.value === "ok") return "配置正常";
  if (configStatus.value === "disabled") return "未启用";
  if (configStatus.value === "misconfigured") return "配置缺失";
  return "未知";
});

const statusTitle = computed(() => {
  if (configStatus.value === "ok") return "验证码服务可以正常工作";
  if (configStatus.value === "disabled") return "验证码服务当前未启用";
  if (configStatus.value === "misconfigured") return "验证码服务配置不完整";
  return "验证码状态未知";
});

const successRate = computed(() => {
  const total = Number(summary.value?.totals?.all || 0);
  if (!total) return 0;
  return Math.round((Number(summary.value?.totals?.success || 0) / total) * 100);
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
  if (filters.scene) params.scene = filters.scene;
  if (filters.result) params.result = filters.result;
  if (filters.error_code) params.error_code = filters.error_code;
  if (filters.user.trim()) params.user = filters.user.trim();
  if (filters.ip.trim()) params.ip = filters.ip.trim();
  if (filters.target_type.trim()) params.target_type = filters.target_type.trim();
  if (filters.search.trim()) params.search = filters.search.trim();
  if (filters.start_at) params.start_at = filters.start_at;
  if (filters.end_at) params.end_at = filters.end_at;
  return params;
}

async function loadOverview() {
  const { data } = await api.get("/admin/captcha/overview/");
  overview.value = data || null;
}

async function loadSummary() {
  summaryLoading.value = true;
  try {
    const { data } = await api.get("/captcha-audit-logs/summary/", {
      params: { window_hours: windowHours.value },
    });
    summary.value = data || null;
    if (data?.config) {
      overview.value = { ...(overview.value || {}), config: data.config };
    }
  } catch (error) {
    ui.error(getErrorText(error, "验证码统计加载失败"));
  } finally {
    summaryLoading.value = false;
  }
}

async function loadLogs(page = 1, append = false) {
  try {
    const { data } = await api.get("/captcha-audit-logs/", { params: buildLogParams(page) });
    const { results, count } = unpackListPayload(data);
    logs.value = append ? appendUniqueById(logs.value, results) : results;
    meta.count = count;
    meta.page = page;
    meta.hasMore = logs.value.length < count;
  } catch (error) {
    ui.error(getErrorText(error, "验证码日志加载失败"));
  }
}

async function loadMoreLogs() {
  if (!meta.hasMore) return;
  await loadLogs(meta.page + 1, true);
}

async function loadAll() {
  loading.value = true;
  try {
    await Promise.all([loadOverview(), loadSummary(), loadLogs()]);
  } catch (error) {
    ui.error(getErrorText(error, "验证码管理数据加载失败"));
  } finally {
    loading.value = false;
  }
}

function resetFilters() {
  filters.scene = "";
  filters.result = "";
  filters.error_code = "";
  filters.user = "";
  filters.ip = "";
  filters.target_type = "";
  filters.search = "";
  filters.start_at = "";
  filters.end_at = "";
  loadLogs();
}

async function exportLogs() {
  try {
    const response = await api.get("/captcha-audit-logs/export/", {
      params: buildLogParams(1),
      responseType: "blob",
    });
    const blob = new Blob([response.data], { type: "text/csv;charset=utf-8;" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `algowiki-captcha-${Date.now()}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
    ui.success("验证码日志已导出");
  } catch (error) {
    ui.error(getErrorText(error, "导出验证码日志失败"));
  }
}

function sceneLabel(value) {
  return sceneMap.value?.[value] || value || "未知场景";
}

function formatErrorCode(value) {
  const labels = {
    CAPTCHA_REQUIRED: "缺少验证码",
    CAPTCHA_INVALID: "验证码无效",
    CAPTCHA_RATE_LIMITED: "触发频控",
    CAPTCHA_PROVIDER_ERROR: "服务商异常",
    CAPTCHA_DUPLICATED: "重复使用",
  };
  return labels[value] || value || "";
}

function formatErrorMessage(value) {
  if (!value) return "-";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
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

.status-panel {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
  border: 1px solid var(--hairline);
  border-radius: 16px;
  padding: 14px;
  background: var(--surface-soft);
}

.status-panel--ok {
  border-color: color-mix(in srgb, #16a34a 32%, var(--hairline));
}

.status-panel--misconfigured {
  border-color: color-mix(in srgb, #dc2626 38%, var(--hairline));
  background: color-mix(in srgb, #fee2e2 35%, var(--surface-soft));
}

.status-panel--disabled {
  border-color: color-mix(in srgb, #d97706 32%, var(--hairline));
}

.status-panel h3,
.insight-card h3,
.recent-failures h3 {
  margin: 0;
  color: var(--text-strong);
}

.eyebrow {
  margin: 0 0 4px;
  color: var(--accent);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.status-pill {
  white-space: nowrap;
  border-radius: 999px;
  padding: 7px 10px;
  background: var(--surface);
  color: var(--text-strong);
  border: 1px solid var(--hairline);
  font-size: 13px;
  font-weight: 800;
}

.issue-list {
  display: grid;
  gap: 6px;
  border: 1px solid rgba(220, 38, 38, 0.22);
  border-radius: 14px;
  padding: 12px;
  background: rgba(254, 226, 226, 0.55);
}

.issue-title {
  margin: 0;
  color: #991b1b;
  font-weight: 800;
}

.issue-item {
  margin: 0;
  color: #7f1d1d;
}

.config-grid,
.summary-grid,
.insight-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 10px;
}

.config-card,
.summary-item,
.insight-card {
  display: grid;
  gap: 5px;
  border: 1px solid var(--hairline);
  border-radius: 14px;
  background: var(--surface-soft);
  padding: 12px;
}

.config-card span,
.summary-item span {
  color: var(--text-soft);
  font-size: 13px;
}

.config-card strong,
.summary-item strong {
  color: var(--text-strong);
  font-size: 23px;
}

.mini-list,
.recent-failures {
  display: grid;
  gap: 8px;
}

.mini-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  border-bottom: 1px solid var(--hairline);
  padding-bottom: 7px;
}

.mini-row:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}

.failure-row,
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

@media (max-width: 720px) {
  .status-panel {
    display: grid;
  }
}
</style>
