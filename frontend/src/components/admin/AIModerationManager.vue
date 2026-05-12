<template>
  <section class="ai-moderation">
    <header class="manager-head">
      <div>
        <h2>AI 审核管理</h2>
        <p class="meta">
          用 AI 自动审核评论、问题、回答和工单。安全内容可自动通过，违规内容可自动驳回，疑似内容保留给人工审核。
        </p>
      </div>
      <div class="head-actions">
        <button class="btn" type="button" :disabled="loading" @click="loadAll">
          {{ loading ? "刷新中..." : "刷新" }}
        </button>
        <button v-if="auth.isSuperAdmin" class="btn" type="button" :disabled="testing" @click="testConnection">
          {{ testing ? "测试中..." : "测试连接" }}
        </button>
        <button class="btn btn-accent" type="button" :disabled="saving" @click="saveConfig">
          {{ saving ? "保存中..." : "保存配置" }}
        </button>
      </div>
    </header>

    <section class="stats-grid">
      <article class="stat-card">
        <strong>{{ stats.last_24h?.total ?? 0 }}</strong>
        <span>24 小时审核</span>
      </article>
      <article class="stat-card">
        <strong>{{ stats.last_24h?.approved ?? 0 }}</strong>
        <span>24 小时通过</span>
      </article>
      <article class="stat-card">
        <strong>{{ stats.last_24h?.rejected ?? 0 }}</strong>
        <span>24 小时驳回</span>
      </article>
      <article class="stat-card">
        <strong>{{ stats.last_7d?.tokens ?? 0 }}</strong>
        <span>7 天 tokens</span>
      </article>
    </section>

    <section class="config-grid">
      <article class="panel">
        <div class="panel-title">
          <h3>基础开关</h3>
          <span :class="['status-pill', form.is_enabled ? 'status-pill--on' : '']">
            {{ form.is_enabled ? "已启用" : "未启用" }}
          </span>
        </div>
        <p class="hint">全局启用、模型、API Key 和用量限制仅超级管理员可修改。</p>

        <div class="switch-list">
          <label class="switch-line">
            <input v-model="form.is_enabled" type="checkbox" :disabled="!auth.isSuperAdmin" />
            <span>启用 AI 自动审核</span>
          </label>
          <label class="switch-line">
            <input v-model="form.comment_enabled" type="checkbox" />
            <span>审核评论</span>
          </label>
          <label class="switch-line">
            <input v-model="form.question_enabled" type="checkbox" />
            <span>审核问题</span>
          </label>
          <label class="switch-line">
            <input v-model="form.answer_enabled" type="checkbox" />
            <span>审核回答</span>
          </label>
          <label class="switch-line">
            <input v-model="form.ticket_enabled" type="checkbox" />
            <span>审核工单</span>
          </label>
        </div>

        <div class="form-grid">
          <label>
            <span>配置名称</span>
            <input v-model.trim="form.label" class="input" />
          </label>
          <label>
            <span>疑似内容</span>
            <select v-model="form.suspicious_action" class="select">
              <option value="pending">保留人工审核</option>
              <option value="approve">直接通过</option>
              <option value="reject">直接驳回</option>
            </select>
          </label>
          <label>
            <span>AI 失败时</span>
            <select v-model="form.failure_action" class="select" :disabled="!auth.isSuperAdmin">
              <option value="pending">保留人工审核</option>
              <option value="approve">直接通过</option>
            </select>
          </label>
        </div>
      </article>

      <article class="panel">
        <div class="panel-title">
          <h3>模型配置</h3>
          <span class="status-pill">{{ form.has_api_key ? "已配置 Key" : "未配置 Key" }}</span>
        </div>
        <p class="hint">普通管理员只能查看模型信息，不能修改模型、Base URL 或 API Key。</p>

        <div class="form-grid">
          <label>
            <span>提供商</span>
            <select v-model="form.provider" class="select" :disabled="!auth.isSuperAdmin">
              <option value="deepseek">DeepSeek</option>
            </select>
          </label>
          <label>
            <span>模型</span>
            <input v-model.trim="form.model_name" class="input" :disabled="!auth.isSuperAdmin" />
          </label>
          <label class="span-2">
            <span>Base URL</span>
            <input v-model.trim="form.base_url" class="input" :disabled="!auth.isSuperAdmin" />
          </label>
          <label class="span-2">
            <span>API Key</span>
            <input
              v-model.trim="form.api_key_input"
              class="input"
              type="password"
              autocomplete="new-password"
              :disabled="!auth.isSuperAdmin"
              :placeholder="form.has_api_key ? '已保存，输入新值才会覆盖' : '请输入 API Key'"
            />
          </label>
          <label>
            <span>Temperature</span>
            <input v-model.number="form.temperature" class="input" type="number" step="0.1" min="0" max="2" :disabled="!auth.isSuperAdmin" />
          </label>
          <label>
            <span>输出 tokens</span>
            <input v-model.number="form.max_output_tokens" class="input" type="number" min="128" max="4096" :disabled="!auth.isSuperAdmin" />
          </label>
          <label>
            <span>超时秒数</span>
            <input v-model.number="form.request_timeout_seconds" class="input" type="number" min="5" max="120" :disabled="!auth.isSuperAdmin" />
          </label>
          <label>
            <span>输入截断字数</span>
            <input v-model.number="form.max_input_chars" class="input" type="number" min="500" max="20000" />
          </label>
        </div>
      </article>

      <article class="panel panel-wide">
        <div class="panel-title">
          <h3>审核规则</h3>
          <span class="status-pill">管理员可改</span>
        </div>
        <div class="rules-grid">
          <label>
            <span>白名单关键词</span>
            <textarea v-model="whitelistText" class="textarea" placeholder="每行一个。命中后直接通过。"></textarea>
          </label>
          <label>
            <span>黑名单关键词</span>
            <textarea v-model="blacklistText" class="textarea" placeholder="每行一个。命中后直接驳回。"></textarea>
          </label>
          <label>
            <span>禁止域名</span>
            <textarea v-model="blockedDomainsText" class="textarea" placeholder="例如 example.com，每行一个。"></textarea>
          </label>
          <label>
            <span>补充规则</span>
            <textarea v-model="form.supplemental_rules" class="textarea textarea-tall" placeholder="写给 AI 的站内审核规则，例如禁止广告、禁止无关内容、哪些内容必须人工复核。"></textarea>
          </label>
        </div>

        <div class="form-grid form-grid-bottom">
          <label>
            <span>新用户严格天数</span>
            <input v-model.number="form.new_user_strict_days" class="input" type="number" min="0" />
          </label>
          <label>
            <span>低提交数阈值</span>
            <input v-model.number="form.new_user_strict_max_items" class="input" type="number" min="0" />
          </label>
          <label class="span-2">
            <span>驳回通知模板</span>
            <input v-model.trim="form.reject_notice_template" class="input" placeholder="支持 {reason} 占位符" />
          </label>
        </div>

        <div class="switch-list switch-list-inline">
          <label class="switch-line">
            <input v-model="form.auto_approve_safe" type="checkbox" />
            <span>safe 内容自动通过</span>
          </label>
          <label class="switch-line">
            <input v-model="form.auto_reject_unsafe" type="checkbox" />
            <span>reject 内容自动驳回</span>
          </label>
        </div>
      </article>
    </section>

    <section class="panel">
      <div class="panel-title">
        <h3>审核记录</h3>
        <div class="filters">
          <select v-model="filters.target_type" class="select compact" @change="loadRecords">
            <option value="">全部类型</option>
            <option value="comment">评论</option>
            <option value="question">问题</option>
            <option value="answer">回答</option>
            <option value="ticket">工单</option>
          </select>
          <select v-model="filters.decision" class="select compact" @change="loadRecords">
            <option value="">全部结果</option>
            <option value="approve">通过</option>
            <option value="reject">驳回</option>
            <option value="manual">人工</option>
            <option value="error">错误</option>
            <option value="skipped">跳过</option>
          </select>
          <input v-model.trim="filters.author" class="input compact" placeholder="用户名" @keyup.enter="loadRecords" />
          <button class="btn btn-mini" type="button" @click="loadRecords">筛选</button>
        </div>
      </div>

      <div class="records-table">
        <div class="records-row records-head">
          <span>时间</span>
          <span>类型</span>
          <span>用户</span>
          <span>结果</span>
          <span>风险</span>
          <span>说明</span>
          <span>耗时</span>
        </div>
        <div v-for="record in records" :key="record.id" class="records-row">
          <span>{{ formatDateTime(record.created_at) }}</span>
          <span>{{ targetTypeLabel(record.target_type) }} #{{ record.target_id }}</span>
          <span>{{ record.author?.username || "-" }}</span>
          <span :class="['decision', `decision-${record.decision}`]">{{ decisionLabel(record.decision) }}</span>
          <span>{{ riskLabel(record.risk_level) }}</span>
          <span class="summary" :title="record.summary || record.error_message">
            {{ record.summary || record.error_message || "-" }}
          </span>
          <span>{{ record.response_ms || 0 }}ms</span>
        </div>
      </div>

      <p v-if="!records.length" class="empty">暂无 AI 审核记录。</p>
    </section>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import api from "../../services/api";
import { useAuthStore } from "../../stores/auth";
import { useUiStore } from "../../stores/ui";

const auth = useAuthStore();
const ui = useUiStore();

const loading = ref(false);
const saving = ref(false);
const testing = ref(false);
const records = ref([]);
const stats = ref({
  last_24h: { total: 0, approved: 0, rejected: 0, manual: 0, errors: 0, tokens: 0 },
  last_7d: { total: 0, approved: 0, rejected: 0, manual: 0, errors: 0, tokens: 0 },
});

const form = reactive({
  id: null,
  label: "默认 AI 审核配置",
  provider: "deepseek",
  base_url: "https://api.deepseek.com",
  model_name: "deepseek-chat",
  has_api_key: false,
  api_key_input: "",
  is_enabled: false,
  comment_enabled: true,
  question_enabled: true,
  answer_enabled: true,
  ticket_enabled: true,
  auto_approve_safe: true,
  auto_reject_unsafe: true,
  suspicious_action: "pending",
  failure_action: "pending",
  temperature: 0,
  max_output_tokens: 512,
  request_timeout_seconds: 20,
  daily_request_limit: 0,
  daily_token_limit: 0,
  max_input_chars: 4000,
  new_user_strict_days: 7,
  new_user_strict_max_items: 3,
  supplemental_rules: "",
  reject_notice_template: "内容未通过 AI 审核：{reason}。请修改后重新提交。",
});

const whitelistText = ref("");
const blacklistText = ref("");
const blockedDomainsText = ref("");

const filters = reactive({
  target_type: "",
  decision: "",
  author: "",
});

function listToText(value) {
  return Array.isArray(value) ? value.join("\n") : "";
}

function textToList(value) {
  return String(value || "")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 200);
}

function applyConfig(data) {
  form.id = data.id;
  form.label = data.label || "默认 AI 审核配置";
  form.provider = data.provider || "deepseek";
  form.base_url = data.base_url || "https://api.deepseek.com";
  form.model_name = data.model_name || "deepseek-chat";
  form.has_api_key = Boolean(data.has_api_key);
  form.api_key_input = "";
  form.is_enabled = Boolean(data.is_enabled);
  form.comment_enabled = Boolean(data.comment_enabled);
  form.question_enabled = Boolean(data.question_enabled);
  form.answer_enabled = Boolean(data.answer_enabled);
  form.ticket_enabled = Boolean(data.ticket_enabled);
  form.auto_approve_safe = Boolean(data.auto_approve_safe);
  form.auto_reject_unsafe = Boolean(data.auto_reject_unsafe);
  form.suspicious_action = data.suspicious_action || "pending";
  form.failure_action = data.failure_action || "pending";
  form.temperature = Number(data.temperature ?? 0);
  form.max_output_tokens = Number(data.max_output_tokens || 512);
  form.request_timeout_seconds = Number(data.request_timeout_seconds || 20);
  form.daily_request_limit = Number(data.daily_request_limit || 0);
  form.daily_token_limit = Number(data.daily_token_limit || 0);
  form.max_input_chars = Number(data.max_input_chars || 4000);
  form.new_user_strict_days = Number(data.new_user_strict_days || 7);
  form.new_user_strict_max_items = Number(data.new_user_strict_max_items || 3);
  form.supplemental_rules = data.supplemental_rules || "";
  form.reject_notice_template = data.reject_notice_template || "内容未通过 AI 审核：{reason}。请修改后重新提交。";
  whitelistText.value = listToText(data.whitelist_keywords);
  blacklistText.value = listToText(data.blacklist_keywords);
  blockedDomainsText.value = listToText(data.blocked_domains);
}

function buildPayload() {
  const payload = {
    label: form.label,
    comment_enabled: form.comment_enabled,
    question_enabled: form.question_enabled,
    answer_enabled: form.answer_enabled,
    ticket_enabled: form.ticket_enabled,
    auto_approve_safe: form.auto_approve_safe,
    auto_reject_unsafe: form.auto_reject_unsafe,
    suspicious_action: form.suspicious_action,
    max_input_chars: Number(form.max_input_chars || 4000),
    new_user_strict_days: Number(form.new_user_strict_days || 0),
    new_user_strict_max_items: Number(form.new_user_strict_max_items || 0),
    whitelist_keywords: textToList(whitelistText.value),
    blacklist_keywords: textToList(blacklistText.value),
    blocked_domains: textToList(blockedDomainsText.value),
    supplemental_rules: form.supplemental_rules,
    reject_notice_template: form.reject_notice_template,
  };
  if (auth.isSuperAdmin) {
    Object.assign(payload, {
      provider: form.provider,
      base_url: form.base_url,
      model_name: form.model_name,
      api_key_input: form.api_key_input,
      is_enabled: form.is_enabled,
      failure_action: form.failure_action,
      temperature: Number(form.temperature || 0),
      max_output_tokens: Number(form.max_output_tokens || 512),
      request_timeout_seconds: Number(form.request_timeout_seconds || 20),
      daily_request_limit: Number(form.daily_request_limit || 0),
      daily_token_limit: Number(form.daily_token_limit || 0),
    });
  }
  return payload;
}

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return error?.message || fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  const parts = [];
  for (const [field, value] of Object.entries(payload)) {
    if (Array.isArray(value)) {
      parts.push(`${field}: ${value.join("；")}`);
    } else if (typeof value === "string") {
      parts.push(`${field}: ${value}`);
    }
  }
  return parts.join("；") || fallback;
}

async function loadConfig() {
  const { data } = await api.get("/ai-moderation-configs/current/");
  applyConfig(data);
}

async function loadStats() {
  const { data } = await api.get("/ai-moderation-configs/stats/");
  stats.value = data || stats.value;
}

async function loadRecords() {
  const params = {};
  if (filters.target_type) params.target_type = filters.target_type;
  if (filters.decision) params.decision = filters.decision;
  if (filters.author) params.author = filters.author;
  const { data } = await api.get("/ai-moderation-records/", { params });
  records.value = Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
}

async function loadAll() {
  loading.value = true;
  try {
    await Promise.all([loadConfig(), loadStats(), loadRecords()]);
  } catch (error) {
    ui.error(getErrorText(error, "AI 审核配置加载失败"));
  } finally {
    loading.value = false;
  }
}

async function saveConfig() {
  saving.value = true;
  try {
    const { data } = await api.patch("/ai-moderation-configs/current/", buildPayload());
    applyConfig(data);
    ui.success("AI 审核配置已保存");
    await Promise.all([loadStats(), loadRecords()]);
  } catch (error) {
    ui.error(getErrorText(error, "AI 审核配置保存失败"));
  } finally {
    saving.value = false;
  }
}

async function testConnection() {
  testing.value = true;
  try {
    const { data } = await api.post("/ai-moderation-configs/test-connection/");
    ui.success(data?.detail || "AI 审核连接测试成功");
  } catch (error) {
    ui.error(getErrorText(error, "AI 审核连接测试失败"));
  } finally {
    testing.value = false;
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

function targetTypeLabel(value) {
  return { comment: "评论", question: "问题", answer: "回答", ticket: "工单" }[value] || value || "-";
}

function decisionLabel(value) {
  return { approve: "通过", reject: "驳回", manual: "人工", error: "错误", skipped: "跳过" }[value] || value || "-";
}

function riskLabel(value) {
  return { safe: "安全", suspicious: "疑似", reject: "违规", error: "错误" }[value] || value || "-";
}

onMounted(() => {
  loadAll();
});
</script>

<style scoped>
.ai-moderation {
  display: grid;
  gap: 16px;
}

.manager-head,
.panel-title,
.head-actions,
.filters {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.manager-head {
  align-items: flex-start;
}

.manager-head h2,
.panel h3 {
  margin: 0;
}

.head-actions,
.filters {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.stats-grid,
.config-grid,
.form-grid,
.rules-grid {
  display: grid;
  gap: 12px;
}

.stats-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.config-grid {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}

.panel-wide {
  grid-column: 1 / -1;
}

.stat-card,
.panel {
  border: 1px solid var(--hairline);
  border-radius: 18px;
  background: var(--surface-strong);
  box-shadow: var(--shadow-sm);
  padding: 16px;
}

.stat-card {
  display: grid;
  gap: 4px;
}

.stat-card strong {
  font-size: 28px;
}

.stat-card span,
.hint,
.empty {
  color: var(--text-quiet);
}

.hint {
  margin: 8px 0 14px;
  font-size: 13px;
}

.status-pill {
  border-radius: 999px;
  background: var(--surface);
  color: var(--text-soft);
  font-size: 12px;
  font-weight: 700;
  padding: 5px 9px;
}

.status-pill--on {
  background: color-mix(in srgb, var(--accent) 14%, var(--surface));
  color: var(--accent);
}

.switch-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 14px;
}

.switch-list-inline {
  flex-direction: row;
  flex-wrap: wrap;
  margin: 14px 0 0;
}

.switch-line {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--text-strong);
  font-weight: 700;
}

.form-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.form-grid-bottom {
  margin-top: 12px;
}

.rules-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.form-grid label,
.rules-grid label {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.form-grid label span,
.rules-grid label span {
  color: var(--text-soft);
  font-size: 13px;
  font-weight: 700;
}

.span-2 {
  grid-column: span 2;
}

.input,
.select,
.textarea {
  width: 100%;
  border: 1px solid var(--hairline);
  border-radius: 12px;
  background: var(--surface);
  color: var(--text-strong);
  font: inherit;
  outline: none;
  padding: 10px 12px;
}

.input:focus,
.select:focus,
.textarea:focus {
  border-color: color-mix(in srgb, var(--accent) 45%, var(--hairline));
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 12%, transparent);
}

.input:disabled,
.select:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.textarea {
  min-height: 120px;
  resize: vertical;
}

.textarea-tall {
  min-height: 160px;
}

.compact {
  max-width: 160px;
}

.records-table {
  display: grid;
  gap: 8px;
  margin-top: 14px;
  overflow-x: auto;
}

.records-row {
  display: grid;
  grid-template-columns: 150px 110px 100px 72px 72px minmax(220px, 1fr) 70px;
  gap: 10px;
  align-items: center;
  min-width: 840px;
  border: 1px solid var(--hairline);
  border-radius: 12px;
  padding: 10px 12px;
}

.records-head {
  border-color: transparent;
  background: var(--surface);
  color: var(--text-soft);
  font-size: 13px;
  font-weight: 800;
}

.summary {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.decision {
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  padding: 4px 8px;
  text-align: center;
}

.decision-approve {
  background: #e8f7ee;
  color: #17843d;
}

.decision-reject,
.decision-error {
  background: #feecec;
  color: #c72828;
}

.decision-manual {
  background: #fff4dc;
  color: #9a6200;
}

.decision-skipped {
  background: #eef0f3;
  color: #606b78;
}

@media (max-width: 980px) {
  .manager-head,
  .panel-title {
    align-items: stretch;
    flex-direction: column;
  }

  .head-actions,
  .filters {
    justify-content: flex-start;
  }

  .stats-grid,
  .config-grid,
  .rules-grid {
    grid-template-columns: 1fr;
  }

  .span-2 {
    grid-column: auto;
  }
}
</style>
