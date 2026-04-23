<template>
  <section class="assistant-admin">
    <header class="assistant-admin-head">
      <div>
        <h2>AI 助手设置</h2>
        <p class="meta">管理站内问答机器人、模型配置、密钥状态和最近调用统计。</p>
      </div>
      <div class="assistant-admin-actions">
        <button class="btn" type="button" :disabled="loading" @click="loadAll">
          {{ loading ? "刷新中..." : "刷新" }}
        </button>
        <button v-if="auth.isSuperAdmin" class="btn btn-accent" type="button" @click="startCreate">
          新建配置
        </button>
      </div>
    </header>

    <section class="assistant-stats-grid">
      <article class="assistant-stat card">
        <strong>{{ stats.totals?.last_24h_requests ?? 0 }}</strong>
        <span>近 24 小时请求</span>
      </article>
      <article class="assistant-stat card">
        <strong>{{ successRate }}</strong>
        <span>近 24 小时成功率</span>
      </article>
      <article class="assistant-stat card">
        <strong>{{ stats.totals?.last_24h_tokens ?? 0 }}</strong>
        <span>近 24 小时 tokens</span>
      </article>
      <article class="assistant-stat card">
        <strong>{{ stats.totals?.last_7d_requests ?? 0 }}</strong>
        <span>近 7 天请求</span>
      </article>
    </section>

    <section v-if="auth.isSuperAdmin" class="assistant-editor card">
      <div class="assistant-editor-head">
        <div>
          <h3>{{ editingId ? "编辑配置" : "新建配置" }}</h3>
          <p class="meta">只有超级管理员可以修改提供商、模型和 API Key。</p>
        </div>
        <button v-if="editingId" class="btn" type="button" @click="resetForm">取消编辑</button>
      </div>

      <div class="assistant-form-grid">
        <input v-model.trim="form.label" class="input" placeholder="配置名称，例如：DeepSeek 正式环境" />
        <input v-model.trim="form.assistant_name" class="input" placeholder="助手名称，例如：AlgoWiki 助手" />
        <select v-model="form.provider" class="select">
          <option value="deepseek">DeepSeek</option>
        </select>
        <input v-model.trim="form.model_name" class="input" placeholder="模型名称，例如：deepseek-chat" />
        <input v-model.trim="form.base_url" class="input form-span" placeholder="Base URL，例如：https://api.deepseek.com" />
        <input
          v-model.trim="form.api_key_input"
          class="input form-span"
          type="password"
          autocomplete="new-password"
          placeholder="API Key：仅输入新值时才会覆盖，页面不会回显旧 Key"
        />
      </div>

      <div class="assistant-form-grid assistant-form-grid--compact">
        <label>
          <span>Temperature</span>
          <input v-model.number="form.temperature" class="input" type="number" min="0" max="2" step="0.1" />
        </label>
        <label>
          <span>最大输出 tokens</span>
          <input v-model.number="form.max_output_tokens" class="input" type="number" min="128" step="64" />
        </label>
        <label>
          <span>超时秒数</span>
          <input v-model.number="form.request_timeout_seconds" class="input" type="number" min="5" max="120" />
        </label>
        <label>
          <span>每日请求上限</span>
          <input v-model.number="form.daily_request_limit" class="input" type="number" min="0" />
        </label>
        <label>
          <span>每日 token 上限</span>
          <input v-model.number="form.daily_token_limit" class="input" type="number" min="0" />
        </label>
      </div>

      <div class="assistant-switch-row">
        <label class="switch-line">
          <input v-model="form.is_enabled" type="checkbox" />
          <span>启用该配置</span>
        </label>
        <label class="switch-line">
          <input v-model="form.is_default" type="checkbox" />
          <span>设为默认配置</span>
        </label>
        <label class="switch-line">
          <input v-model="form.show_launcher" type="checkbox" />
          <span>显示右下角入口</span>
        </label>
      </div>

      <textarea
        v-model="form.welcome_message"
        class="textarea"
        placeholder="欢迎语，留空将使用默认值"
      ></textarea>
      <textarea
        v-model="form.teaser_message"
        class="textarea assistant-textarea assistant-textarea--compact"
        placeholder="入口气泡提示语，留空将使用默认值"
      ></textarea>
      <textarea
        v-model="suggestedQuestionsText"
        class="textarea assistant-textarea assistant-textarea--compact"
        placeholder="推荐问题，每行一个"
      ></textarea>
      <textarea
        v-model="form.system_prompt"
        class="textarea assistant-textarea"
        placeholder="系统提示词（留空使用内置默认提示）"
      ></textarea>

      <div class="assistant-editor-actions">
        <button class="btn btn-accent" type="button" :disabled="saving" @click="saveConfig">
          {{ saving ? "保存中..." : editingId ? "保存配置" : "创建配置" }}
        </button>
      </div>
    </section>

    <section class="assistant-config-list">
      <article v-for="item in configs" :key="item.id" class="assistant-config card">
        <div class="assistant-config-top">
          <div>
            <div class="assistant-config-title-row">
              <h3>{{ item.label }}</h3>
              <span v-if="item.is_default" class="pill">默认</span>
              <span v-if="!item.is_enabled" class="pill pill--muted">停用</span>
            </div>
            <p class="meta">{{ item.assistant_name }} · {{ item.provider_label }} · {{ item.model_name }}</p>
          </div>
          <div class="assistant-config-actions" v-if="auth.isSuperAdmin">
            <button class="btn btn-mini" type="button" @click="startEdit(item)">编辑</button>
            <button class="btn btn-mini" type="button" :disabled="item.is_default" @click="setDefault(item)">设为默认</button>
            <button class="btn btn-mini" type="button" @click="testConnection(item)">测试连接</button>
            <button class="btn btn-mini" type="button" @click="removeConfig(item)">删除</button>
          </div>
        </div>

        <div class="assistant-config-grid">
          <div>
            <span class="assistant-config-label">Base URL</span>
            <strong>{{ item.base_url }}</strong>
          </div>
          <div>
            <span class="assistant-config-label">API Key</span>
            <strong>{{ item.has_api_key ? item.api_key_masked : "未配置" }}</strong>
          </div>
          <div>
            <span class="assistant-config-label">右下角入口</span>
            <strong>{{ item.show_launcher ? "显示" : "隐藏" }}</strong>
          </div>
          <div>
            <span class="assistant-config-label">温度 / tokens</span>
            <strong>{{ item.temperature }} / {{ item.max_output_tokens }}</strong>
          </div>
          <div>
            <span class="assistant-config-label">最近测试</span>
            <strong>{{ formatTestStatus(item) }}</strong>
          </div>
          <div>
            <span class="assistant-config-label">更新时间</span>
            <strong>{{ formatDateTime(item.updated_at) }}</strong>
          </div>
        </div>

        <p v-if="item.last_test_message" class="meta assistant-config-note">最近测试结果：{{ item.last_test_message }}</p>
        <p class="meta assistant-config-note">入口气泡：{{ item.teaser_message || "使用默认值" }}</p>
        <p class="meta assistant-config-note">推荐问题：{{ (item.suggested_questions || []).join(" / ") || "未设置" }}</p>

        <div class="assistant-usage-row">
          <span>近 24 小时请求 {{ perConfigStat(item.id).last_24h_requests }}</span>
          <span>成功 {{ perConfigStat(item.id).last_24h_success }}</span>
          <span>tokens {{ perConfigStat(item.id).last_24h_tokens }}</span>
          <span>近 7 天请求 {{ perConfigStat(item.id).last_7d_requests }}</span>
        </div>
      </article>

      <p v-if="!configs.length" class="meta">当前还没有 AI 模型配置。</p>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import api from "../../services/api";
import { useAuthStore } from "../../stores/auth";
import { useUiStore } from "../../stores/ui";

const auth = useAuthStore();
const ui = useUiStore();

const loading = ref(false);
const saving = ref(false);
const editingId = ref(null);
const configs = ref([]);
const stats = ref({
  totals: {
    last_24h_requests: 0,
    last_24h_success: 0,
    last_24h_tokens: 0,
    last_7d_requests: 0,
    last_7d_tokens: 0,
  },
  per_config: [],
});

const form = reactive({
  label: "",
  assistant_name: "AlgoWiki 助手",
  provider: "deepseek",
  base_url: "https://api.deepseek.com",
  model_name: "deepseek-chat",
  api_key_input: "",
  is_enabled: true,
  is_default: false,
  show_launcher: true,
  temperature: 0.3,
  max_output_tokens: 1024,
  request_timeout_seconds: 30,
  welcome_message: "",
  teaser_message: "",
  suggested_questions: [],
  system_prompt: "",
  daily_request_limit: 0,
  daily_token_limit: 0,
});

const suggestedQuestionsText = ref("");

const successRate = computed(() => {
  const total = Number(stats.value.totals?.last_24h_requests || 0);
  const success = Number(stats.value.totals?.last_24h_success || 0);
  if (!total) return "0%";
  return `${Math.round((success / total) * 100)}%`;
});

function resetForm() {
  editingId.value = null;
  form.label = "";
  form.assistant_name = "AlgoWiki 助手";
  form.provider = "deepseek";
  form.base_url = "https://api.deepseek.com";
  form.model_name = "deepseek-chat";
  form.api_key_input = "";
  form.is_enabled = true;
  form.is_default = false;
  form.show_launcher = true;
  form.temperature = 0.3;
  form.max_output_tokens = 1024;
  form.request_timeout_seconds = 30;
  form.welcome_message = "";
  form.teaser_message = "";
  form.suggested_questions = [];
  form.system_prompt = "";
  form.daily_request_limit = 0;
  form.daily_token_limit = 0;
  suggestedQuestionsText.value = "";
}

function startCreate() {
  resetForm();
}

function startEdit(item) {
  editingId.value = item.id;
  form.label = item.label || "";
  form.assistant_name = item.assistant_name || "AlgoWiki 助手";
  form.provider = item.provider || "deepseek";
  form.base_url = item.base_url || "https://api.deepseek.com";
  form.model_name = item.model_name || "deepseek-chat";
  form.api_key_input = "";
  form.is_enabled = Boolean(item.is_enabled);
  form.is_default = Boolean(item.is_default);
  form.show_launcher = Boolean(item.show_launcher);
  form.temperature = Number(item.temperature ?? 0.3);
  form.max_output_tokens = Number(item.max_output_tokens ?? 1024);
  form.request_timeout_seconds = Number(item.request_timeout_seconds ?? 30);
  form.welcome_message = item.welcome_message || "";
  form.teaser_message = item.teaser_message || "";
  form.suggested_questions = Array.isArray(item.suggested_questions) ? item.suggested_questions : [];
  form.system_prompt = item.system_prompt || "";
  form.daily_request_limit = Number(item.daily_request_limit || 0);
  form.daily_token_limit = Number(item.daily_token_limit || 0);
  suggestedQuestionsText.value = form.suggested_questions.join("\n");
}

function buildPayload() {
  return {
    label: form.label.trim(),
    assistant_name: form.assistant_name.trim(),
    provider: form.provider,
    base_url: form.base_url.trim(),
    model_name: form.model_name.trim(),
    api_key_input: form.api_key_input.trim(),
    is_enabled: Boolean(form.is_enabled),
    is_default: Boolean(form.is_default),
    show_launcher: Boolean(form.show_launcher),
    temperature: Number(form.temperature || 0),
    max_output_tokens: Number(form.max_output_tokens || 0),
    request_timeout_seconds: Number(form.request_timeout_seconds || 0),
    welcome_message: form.welcome_message,
    teaser_message: form.teaser_message,
    suggested_questions: suggestedQuestionsText.value
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter(Boolean)
      .slice(0, 6),
    system_prompt: form.system_prompt,
    daily_request_limit: Number(form.daily_request_limit || 0),
    daily_token_limit: Number(form.daily_token_limit || 0),
  };
}

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return error?.message || fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  const parts = [];
  for (const [field, value] of Object.entries(payload)) {
    if (Array.isArray(value)) {
      parts.push(`${field}: ${value.join("，")}`);
    } else if (typeof value === "string") {
      parts.push(`${field}: ${value}`);
    }
  }
  return parts.join("；") || fallback;
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

function formatTestStatus(item) {
  if (!item.last_tested_at) return "未测试";
  return item.last_test_success ? `成功 · ${formatDateTime(item.last_tested_at)}` : `失败 · ${formatDateTime(item.last_tested_at)}`;
}

function perConfigStat(id) {
  return (
    stats.value.per_config?.find((item) => Number(item.id) === Number(id)) || {
      last_24h_requests: 0,
      last_24h_success: 0,
      last_24h_tokens: 0,
      last_7d_requests: 0,
    }
  );
}

async function loadAll() {
  loading.value = true;
  try {
    const [configResponse, statsResponse] = await Promise.all([
      api.get("/assistant-configs/"),
      api.get("/assistant-configs/stats/"),
    ]);
    configs.value = Array.isArray(configResponse.data?.results)
      ? configResponse.data.results
      : Array.isArray(configResponse.data)
      ? configResponse.data
      : [];
    stats.value = statsResponse.data || stats.value;
  } catch (error) {
    ui.error(getErrorText(error, "AI 设置加载失败"));
  } finally {
    loading.value = false;
  }
}

async function saveConfig() {
  saving.value = true;
  try {
    const payload = buildPayload();
    if (editingId.value) {
      await api.patch(`/assistant-configs/${editingId.value}/`, payload);
      ui.success("AI 配置已更新");
    } else {
      await api.post("/assistant-configs/", payload);
      ui.success("AI 配置已创建");
    }
    resetForm();
    await loadAll();
  } catch (error) {
    ui.error(getErrorText(error, "保存 AI 配置失败"));
  } finally {
    saving.value = false;
  }
}

async function setDefault(item) {
  try {
    await api.post(`/assistant-configs/${item.id}/set-default/`);
    ui.success("默认模型配置已切换");
    await loadAll();
  } catch (error) {
    ui.error(getErrorText(error, "切换默认配置失败"));
  }
}

async function testConnection(item) {
  try {
    const { data } = await api.post(`/assistant-configs/${item.id}/test-connection/`);
    ui.success(data?.detail || "连接测试成功");
    await loadAll();
  } catch (error) {
    ui.error(getErrorText(error, "连接测试失败"));
    await loadAll();
  }
}

async function removeConfig(item) {
  if (!window.confirm(`确认删除 AI 配置「${item.label}」？`)) return;
  try {
    await api.delete(`/assistant-configs/${item.id}/`);
    ui.success("AI 配置已删除");
    if (editingId.value === item.id) {
      resetForm();
    }
    await loadAll();
  } catch (error) {
    ui.error(getErrorText(error, "删除 AI 配置失败"));
  }
}

onMounted(() => {
  loadAll();
});
</script>

<style scoped>
.assistant-admin {
  display: grid;
  gap: 16px;
}

.assistant-admin-head,
.assistant-editor-head,
.assistant-config-top,
.assistant-admin-actions,
.assistant-config-actions,
.assistant-editor-actions,
.assistant-switch-row,
.assistant-usage-row {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
}

.assistant-stats-grid,
.assistant-config-grid,
.assistant-form-grid {
  display: grid;
  gap: 12px;
}

.assistant-stats-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.assistant-stat {
  padding: 16px;
  display: grid;
  gap: 6px;
}

.assistant-stat strong {
  font-size: 26px;
}

.assistant-editor,
.assistant-config {
  padding: 16px;
  display: grid;
  gap: 14px;
}

.assistant-form-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.assistant-form-grid--compact {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.assistant-form-grid label {
  display: grid;
  gap: 6px;
}

.assistant-form-grid label span,
.assistant-config-label {
  color: var(--text-quiet);
  font-size: 12px;
}

.form-span {
  grid-column: 1 / -1;
}

.assistant-textarea {
  min-height: 140px;
}

.assistant-textarea--compact {
  min-height: 96px;
}

.assistant-config-list {
  display: grid;
  gap: 14px;
}

.assistant-config-title-row {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.assistant-config-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.assistant-config-grid > div {
  display: grid;
  gap: 4px;
}

.assistant-config-note,
.assistant-usage-row {
  color: var(--text-soft);
}

.pill--muted {
  background: color-mix(in srgb, var(--text-soft) 16%, transparent);
}

@media (max-width: 980px) {
  .assistant-stats-grid,
  .assistant-config-grid,
  .assistant-form-grid--compact {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .assistant-stats-grid,
  .assistant-config-grid,
  .assistant-form-grid,
  .assistant-form-grid--compact {
    grid-template-columns: 1fr;
  }
}
</style>
