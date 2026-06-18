<template>
  <section class="announcement-manager">
    <header class="section-head manager-head">
      <div>
        <h2>公告管理</h2>
        <p class="meta">发布、定时、撤回和归档站内公告，控制首页、公告页、弹窗和顶部横幅的展示。</p>
      </div>
      <div class="head-actions">
        <button class="btn" type="button" :disabled="loading" @click="loadAll">
          {{ loading ? "刷新中..." : "刷新" }}
        </button>
        <button class="btn btn-accent" type="button" @click="openCreateModal">新建公告</button>
      </div>
    </header>

    <section class="stats-grid">
      <article v-for="item in statCards" :key="item.key" class="stat-card">
        <strong>{{ item.value }}</strong>
        <span>{{ item.label }}</span>
      </article>
    </section>

    <div class="toolbar">
      <input v-model="filters.search" class="input grow" placeholder="搜索标题、摘要或正文" @keyup.enter="loadAnnouncements" />
      <select v-model="filters.status" class="select">
        <option value="">全部状态</option>
        <option value="published">发布中</option>
        <option value="scheduled">定时</option>
        <option value="draft">草稿</option>
        <option value="withdrawn">已撤回</option>
        <option value="expired">已过期</option>
        <option value="archived">已归档</option>
      </select>
      <select v-model="filters.level" class="select">
        <option value="">全部等级</option>
        <option v-for="item in levelOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
      </select>
      <select v-model="filters.audience" class="select">
        <option value="">全部受众</option>
        <option v-for="item in audienceOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
      </select>
      <button class="btn" type="button" @click="loadAnnouncements">筛选</button>
      <button class="btn" type="button" @click="resetFilters">重置</button>
    </div>

    <section class="notice-help">
      <strong>操作说明</strong>
      <span>撤回会立即停止展示但保留记录；归档会从运营列表默认隐藏，可恢复；删除会进入删除内容归档，通常只在误建或合规清理时使用。</span>
    </section>

    <section class="announcement-list">
      <article v-for="item in filteredAnnouncements" :key="item.id" class="announcement-row">
        <div class="row-main">
          <div class="row-title">
            <strong>{{ item.title }}</strong>
            <span class="status-pill" :class="`status-pill--${item.status || 'draft'}`">{{ statusLabel(item.status) }}</span>
            <span class="level-pill" :class="`level-pill--${item.level || 'normal'}`">{{ levelLabel(item.level) }}</span>
          </div>
          <p class="summary">{{ item.summary || summarizeText(item.content_md, 120) || "无摘要" }}</p>
          <div class="meta-list">
            <span>ID #{{ item.id }}</span>
            <span>受众：{{ audienceLabel(item.target_audience) }}</span>
            <span>阅读：{{ item.read_count ?? 0 }}</span>
            <span>开始：{{ formatDateTime(item.start_at) }}</span>
            <span v-if="item.end_at">结束：{{ formatDateTime(item.end_at) }}</span>
          </div>
          <div class="surface-list">
            <span :class="{ muted: !item.show_on_home }">首页</span>
            <span :class="{ muted: !item.show_in_list }">公告页</span>
            <span :class="{ muted: !item.show_as_popup }">弹窗</span>
            <span :class="{ muted: !item.show_as_banner }">横幅</span>
            <span :class="{ muted: !item.send_notification }">通知</span>
            <span :class="{ muted: !item.requires_ack }">需确认</span>
          </div>
        </div>

        <div class="row-actions">
          <button class="btn btn-mini" type="button" @click="openPreview(item)">预览</button>
          <button class="btn btn-mini" type="button" @click="openEditModal(item)">编辑</button>
          <button
            v-if="item.status === 'archived'"
            class="btn btn-mini"
            type="button"
            :disabled="actingId === item.id"
            @click="runAnnouncementAction(item, 'restore-archive', '恢复归档公告')"
          >
            恢复
          </button>
          <button
            v-else-if="item.is_published"
            class="btn btn-mini"
            type="button"
            :disabled="actingId === item.id"
            @click="runAnnouncementAction(item, 'withdraw', '撤回公告')"
          >
            撤回
          </button>
          <button
            v-else
            class="btn btn-mini"
            type="button"
            :disabled="actingId === item.id"
            @click="runAnnouncementAction(item, 'publish', '发布公告')"
          >
            发布
          </button>
          <button
            v-if="item.status !== 'archived'"
            class="btn btn-mini"
            type="button"
            :disabled="actingId === item.id"
            @click="runAnnouncementAction(item, 'archive', '归档公告')"
          >
            归档
          </button>
          <button class="btn btn-mini danger" type="button" :disabled="actingId === item.id" @click="deleteAnnouncement(item)">
            删除
          </button>
        </div>
      </article>
    </section>

    <p v-if="!filteredAnnouncements.length && !loading" class="meta">当前没有匹配的公告。</p>

    <div v-if="showEditor" class="modal-backdrop" @click.self="closeEditor">
      <section class="announcement-editor" role="dialog" aria-modal="true" aria-label="公告编辑器">
        <header class="editor-head">
          <div>
            <p class="eyebrow">{{ editorMode === 'create' ? 'CREATE' : `ANNOUNCEMENT #${form.id}` }}</p>
            <h3>{{ editorMode === "create" ? "新建公告" : "编辑公告" }}</h3>
          </div>
          <button class="btn btn-mini" type="button" @click="closeEditor">关闭</button>
        </header>

        <div class="editor-tabs">
          <button type="button" :class="{ active: editorTab === 'edit' }" @click="editorTab = 'edit'">编辑</button>
          <button type="button" :class="{ active: editorTab === 'preview' }" @click="editorTab = 'preview'">预览</button>
        </div>

        <section v-if="editorTab === 'edit'" class="editor-body">
          <label class="field span-2">
            <span>标题</span>
            <input v-model.trim="form.title" class="input" maxlength="220" placeholder="公告标题" />
          </label>
          <label class="field span-2">
            <span>摘要</span>
            <input v-model.trim="form.summary" class="input" maxlength="300" placeholder="显示在首页和列表中的简短说明，可留空" />
          </label>
          <label class="field span-2">
            <span>正文 Markdown</span>
            <textarea v-model="form.content_md" class="textarea content-editor" placeholder="支持 Markdown、链接、代码块和公式"></textarea>
          </label>

          <label class="field">
            <span>等级</span>
            <select v-model="form.level" class="select">
              <option v-for="item in levelOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>
          <label class="field">
            <span>受众</span>
            <select v-model="form.target_audience" class="select">
              <option v-for="item in audienceOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>
          <label class="field">
            <span>优先级</span>
            <input v-model.number="form.priority" class="input" type="number" min="0" step="1" />
          </label>
          <label class="field">
            <span>发布状态</span>
            <select v-model="form.is_published" class="select">
              <option :value="true">发布</option>
              <option :value="false">草稿</option>
            </select>
          </label>
          <label class="field">
            <span>开始时间</span>
            <input v-model="form.start_at" class="input" type="datetime-local" />
          </label>
          <label class="field">
            <span>结束时间</span>
            <input v-model="form.end_at" class="input" type="datetime-local" />
          </label>

          <section class="switch-panel span-2">
            <h4>展示位置</h4>
            <div class="switch-grid">
              <label v-for="item in surfaceOptions" :key="item.key" class="switch-line">
                <input v-model="form[item.key]" type="checkbox" />
                <span>{{ item.label }}</span>
              </label>
            </div>
          </section>

          <section class="switch-panel span-2">
            <h4>触达与确认</h4>
            <div class="switch-grid">
              <label class="switch-line">
                <input v-model="form.send_notification" type="checkbox" />
                <span>发布时发送站内通知</span>
              </label>
              <label class="switch-line">
                <input v-model="form.requires_ack" type="checkbox" />
                <span>弹窗按钮显示“我已知晓”</span>
              </label>
            </div>
          </section>
        </section>

        <section v-else class="preview-body">
          <div class="preview-meta">
            <span>{{ levelLabel(form.level) }}</span>
            <span>{{ audienceLabel(form.target_audience) }}</span>
            <span>{{ form.is_published ? "发布" : "草稿" }}</span>
          </div>
          <h3>{{ form.title || "未填写标题" }}</h3>
          <p v-if="form.summary" class="summary">{{ form.summary }}</p>
          <div class="markdown preview-markdown" v-html="previewHtml"></div>
        </section>

        <footer class="editor-actions">
          <button class="btn" type="button" :disabled="saving" @click="closeEditor">取消</button>
          <button class="btn btn-accent" type="button" :disabled="saving" @click="saveAnnouncement">
            {{ saving ? "保存中..." : "保存公告" }}
          </button>
        </footer>
      </section>
    </div>

    <div v-if="previewItem" class="modal-backdrop" @click.self="previewItem = null">
      <section class="preview-modal" role="dialog" aria-modal="true" aria-label="公告预览">
        <header class="editor-head">
          <div>
            <p class="eyebrow">PREVIEW</p>
            <h3>{{ previewItem.title }}</h3>
          </div>
          <button class="btn btn-mini" type="button" @click="previewItem = null">关闭</button>
        </header>
        <div class="preview-meta">
          <span>{{ statusLabel(previewItem.status) }}</span>
          <span>{{ levelLabel(previewItem.level) }}</span>
          <span>{{ audienceLabel(previewItem.target_audience) }}</span>
        </div>
        <p v-if="previewItem.summary" class="summary">{{ previewItem.summary }}</p>
        <div class="markdown preview-markdown" v-html="renderMarkdown(previewItem.content_md || '')"></div>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import api from "../../services/api";
import { renderMarkdown } from "../../services/markdown";
import { useUiStore } from "../../stores/ui";

const ui = useUiStore();

const loading = ref(false);
const saving = ref(false);
const actingId = ref(null);
const announcements = ref([]);
const stats = ref({});
const showEditor = ref(false);
const editorMode = ref("create");
const editorTab = ref("edit");
const previewItem = ref(null);

const filters = reactive({
  search: "",
  status: "",
  level: "",
  audience: "",
});

const form = reactive(defaultForm());

const levelOptions = [
  { value: "emergency", label: "紧急" },
  { value: "important", label: "重要" },
  { value: "normal", label: "普通" },
  { value: "low", label: "低优先级" },
];

const audienceOptions = [
  { value: "all", label: "全部访客" },
  { value: "logged_in", label: "登录用户" },
  { value: "school", label: "学校/管理员" },
  { value: "admin", label: "仅管理员" },
];

const surfaceOptions = [
  { key: "show_on_home", label: "首页最新公告" },
  { key: "show_in_list", label: "公告列表页" },
  { key: "show_as_popup", label: "站内弹窗" },
  { key: "show_as_banner", label: "顶部横幅" },
];

const statCards = computed(() => [
  { key: "published", label: "发布中", value: stats.value.published ?? 0 },
  { key: "scheduled", label: "定时", value: stats.value.scheduled ?? 0 },
  { key: "draft", label: "草稿", value: stats.value.draft ?? 0 },
  { key: "archived", label: "归档", value: stats.value.archived ?? 0 },
  { key: "emergency", label: "紧急", value: stats.value.emergency ?? 0 },
]);

const filteredAnnouncements = computed(() => {
  const keyword = filters.search.trim().toLowerCase();
  return announcements.value.filter((item) => {
    if (filters.status && item.status !== filters.status) return false;
    if (filters.level && item.level !== filters.level) return false;
    if (filters.audience && item.target_audience !== filters.audience) return false;
    if (!keyword) return true;
    return [item.title, item.summary, item.content_md]
      .some((value) => String(value || "").toLowerCase().includes(keyword));
  });
});

const previewHtml = computed(() => renderMarkdown(form.content_md || ""));

function defaultForm() {
  return {
    id: null,
    title: "",
    summary: "",
    content_md: "",
    level: "normal",
    target_audience: "all",
    priority: 0,
    is_published: true,
    show_on_home: true,
    show_in_list: true,
    show_as_popup: true,
    show_as_banner: false,
    send_notification: true,
    requires_ack: false,
    start_at: toDateTimeLocal(new Date()),
    end_at: "",
  };
}

function resetForm() {
  Object.assign(form, defaultForm());
}

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return error?.message || fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  const firstValue = Object.values(payload)[0];
  if (Array.isArray(firstValue) && firstValue.length) return String(firstValue[0]);
  if (typeof firstValue === "string") return firstValue;
  return fallback;
}

function unpackListPayload(data) {
  if (Array.isArray(data)) return { results: data, count: data.length };
  const results = Array.isArray(data?.results) ? data.results : [];
  const count = Number.isFinite(data?.count) ? data.count : results.length;
  return { results, count };
}

function nextPageFromUrl(value) {
  if (!value) return null;
  try {
    const parsed = new URL(value, window.location.origin);
    const page = Number(parsed.searchParams.get("page"));
    return Number.isFinite(page) && page > 0 ? page : null;
  } catch {
    return null;
  }
}

function toDateTimeLocal(value) {
  if (!value) return "";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const offset = date.getTimezoneOffset();
  const local = new Date(date.getTime() - offset * 60 * 1000);
  return local.toISOString().slice(0, 16);
}

function fromDateTimeLocal(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
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

function markdownToPlainText(value) {
  const html = renderMarkdown(value || "");
  if (typeof DOMParser !== "undefined") {
    const doc = new DOMParser().parseFromString(html, "text/html");
    return (doc.body.textContent || "").trim();
  }
  return html.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

function summarizeText(value, limit = 96) {
  const text = markdownToPlainText(value).replace(/\n+/g, " ").replace(/\s+/g, " ").trim();
  if (text.length <= limit) return text;
  return `${text.slice(0, limit)}...`;
}

function statusLabel(value) {
  const labels = {
    published: "发布中",
    scheduled: "定时",
    draft: "草稿",
    withdrawn: "已撤回",
    expired: "已过期",
    archived: "已归档",
  };
  return labels[value] || value || "未知";
}

function levelLabel(value) {
  return levelOptions.find((item) => item.value === value)?.label || value || "普通";
}

function audienceLabel(value) {
  return audienceOptions.find((item) => item.value === value)?.label || value || "全部访客";
}

async function loadStats() {
  const { data } = await api.get("/announcements/stats/");
  stats.value = data || {};
}

async function loadAnnouncements() {
  const rows = [];
  let page = 1;
  while (page) {
    const { data } = await api.get("/announcements/", { params: { all: 1, page } });
    if (Array.isArray(data)) {
      rows.push(...data);
      break;
    }
    const { results } = unpackListPayload(data);
    rows.push(...results);
    page = nextPageFromUrl(data?.next);
  }
  announcements.value = rows.sort((a, b) => {
    const aTs = Date.parse(a.updated_at || a.created_at || "");
    const bTs = Date.parse(b.updated_at || b.created_at || "");
    return (Number.isNaN(bTs) ? 0 : bTs) - (Number.isNaN(aTs) ? 0 : aTs);
  });
}

async function loadAll() {
  loading.value = true;
  try {
    await Promise.all([loadStats(), loadAnnouncements()]);
  } catch (error) {
    ui.error(getErrorText(error, "公告管理数据加载失败"));
  } finally {
    loading.value = false;
  }
}

function resetFilters() {
  filters.search = "";
  filters.status = "";
  filters.level = "";
  filters.audience = "";
}

function openCreateModal() {
  resetForm();
  editorMode.value = "create";
  editorTab.value = "edit";
  showEditor.value = true;
}

function openEditModal(item) {
  Object.assign(form, {
    id: item.id,
    title: item.title || "",
    summary: item.summary || "",
    content_md: item.content_md || "",
    level: item.level || "normal",
    target_audience: item.target_audience || "all",
    priority: Number(item.priority || 0),
    is_published: Boolean(item.is_published),
    show_on_home: Boolean(item.show_on_home),
    show_in_list: Boolean(item.show_in_list),
    show_as_popup: Boolean(item.show_as_popup),
    show_as_banner: Boolean(item.show_as_banner),
    send_notification: Boolean(item.send_notification),
    requires_ack: Boolean(item.requires_ack),
    start_at: toDateTimeLocal(item.start_at),
    end_at: toDateTimeLocal(item.end_at),
  });
  editorMode.value = "edit";
  editorTab.value = "edit";
  showEditor.value = true;
}

function closeEditor() {
  showEditor.value = false;
}

function openPreview(item) {
  previewItem.value = item;
}

function buildPayload() {
  return {
    title: form.title.trim(),
    summary: form.summary.trim(),
    content_md: form.content_md,
    level: form.level,
    target_audience: form.target_audience,
    priority: Number(form.priority || 0),
    is_published: Boolean(form.is_published),
    show_on_home: Boolean(form.show_on_home),
    show_in_list: Boolean(form.show_in_list),
    show_as_popup: Boolean(form.show_as_popup),
    show_as_banner: Boolean(form.show_as_banner),
    send_notification: Boolean(form.send_notification),
    requires_ack: Boolean(form.requires_ack),
    start_at: fromDateTimeLocal(form.start_at) || new Date().toISOString(),
    end_at: fromDateTimeLocal(form.end_at),
  };
}

async function saveAnnouncement() {
  if (!form.title.trim() || !form.content_md.trim()) {
    ui.info("请填写公告标题和正文内容");
    return;
  }
  saving.value = true;
  try {
    const payload = buildPayload();
    if (editorMode.value === "create") {
      await api.post("/announcements/", payload);
      ui.success("公告已创建");
    } else {
      await api.patch(`/announcements/${form.id}/`, payload);
      ui.success("公告已保存");
    }
    showEditor.value = false;
    await loadAll();
  } catch (error) {
    ui.error(getErrorText(error, "公告保存失败"));
  } finally {
    saving.value = false;
  }
}

async function runAnnouncementAction(item, action, label) {
  if (!item?.id) return;
  const confirmText = `${label}「${item.title}」？`;
  if (!window.confirm(confirmText)) return;
  actingId.value = item.id;
  try {
    await api.post(`/announcements/${item.id}/${action}/`);
    ui.success(`${label}完成`);
    await loadAll();
  } catch (error) {
    ui.error(getErrorText(error, `${label}失败`));
  } finally {
    actingId.value = null;
  }
}

async function deleteAnnouncement(item) {
  if (!item?.id) return;
  if (!window.confirm(`确认删除公告「${item.title}」？删除会进入删除内容归档，普通页面不可见。`)) return;
  actingId.value = item.id;
  try {
    await api.delete(`/announcements/${item.id}/`);
    ui.success("公告已删除");
    await loadAll();
  } catch (error) {
    ui.error(getErrorText(error, "公告删除失败"));
  } finally {
    actingId.value = null;
  }
}

onMounted(() => {
  loadAll();
});
</script>

<style scoped>
.announcement-manager {
  display: grid;
  gap: 14px;
}

.manager-head,
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
}

.head-actions,
.row-actions,
.editor-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.grow {
  flex: 1 1 260px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 10px;
}

.stat-card,
.notice-help,
.announcement-row,
.announcement-editor,
.preview-modal {
  border: 1px solid var(--hairline);
  border-radius: 18px;
  background: var(--surface-strong);
  box-shadow: var(--shadow-sm);
}

.stat-card {
  display: grid;
  gap: 4px;
  padding: 14px;
}

.stat-card strong {
  color: var(--text-strong);
  font-size: 28px;
  line-height: 1;
}

.stat-card span,
.notice-help span,
.summary,
.meta-list,
.surface-list {
  color: var(--muted);
  font-size: 13px;
}

.notice-help {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  align-items: center;
  padding: 12px 14px;
}

.announcement-list {
  display: grid;
  gap: 10px;
}

.announcement-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  padding: 16px;
}

.row-main {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.row-title {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.row-title strong {
  color: var(--text-strong);
  font-size: 17px;
}

.meta-list,
.surface-list,
.preview-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
}

.surface-list span,
.preview-meta span,
.status-pill,
.level-pill {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 9px;
  border-radius: 999px;
  border: 1px solid var(--hairline);
  background: var(--surface-soft);
  color: var(--text);
  font-size: 12px;
  font-weight: 700;
}

.surface-list .muted {
  opacity: 0.45;
}

.status-pill--published,
.level-pill--normal {
  color: #16794c;
  background: rgba(34, 197, 94, 0.11);
}

.status-pill--scheduled,
.level-pill--important {
  color: #8a5b08;
  background: rgba(245, 158, 11, 0.13);
}

.status-pill--archived,
.status-pill--withdrawn,
.status-pill--draft,
.status-pill--expired,
.level-pill--low {
  color: var(--text-soft);
}

.level-pill--emergency {
  color: #b42318;
  background: rgba(244, 63, 94, 0.12);
}

.danger {
  color: #b42318;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 70;
  display: grid;
  place-items: center;
  padding: 20px;
  background: color-mix(in srgb, var(--text-strong) 30%, transparent);
}

.announcement-editor,
.preview-modal {
  width: min(920px, 100%);
  max-height: min(86vh, 880px);
  overflow: auto;
  padding: 18px;
}

.editor-head {
  display: flex;
  gap: 14px;
  align-items: start;
  justify-content: space-between;
  margin-bottom: 14px;
}

.editor-head h3 {
  margin: 0;
  font-size: 24px;
}

.eyebrow {
  margin: 0 0 4px;
  color: var(--muted);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.editor-tabs {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  margin-bottom: 14px;
  border: 1px solid var(--hairline);
  border-radius: 12px;
  background: var(--surface-soft);
}

.editor-tabs button {
  min-height: 34px;
  padding: 0 14px;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: var(--text-soft);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.editor-tabs button.active {
  background: var(--surface-strong);
  color: var(--accent);
  box-shadow: var(--shadow-sm);
}

.editor-body {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.field {
  display: grid;
  gap: 6px;
  color: var(--text-soft);
  font-size: 13px;
  font-weight: 700;
}

.span-2 {
  grid-column: 1 / -1;
}

.content-editor {
  min-height: 220px;
}

.switch-panel {
  display: grid;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--hairline);
  border-radius: 14px;
  background: var(--surface-soft);
}

.switch-panel h4 {
  margin: 0;
  font-size: 14px;
}

.switch-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 8px;
}

.switch-line {
  display: flex;
  gap: 8px;
  align-items: center;
  color: var(--text);
  font-size: 14px;
  font-weight: 600;
}

.editor-actions {
  justify-content: flex-end;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--hairline);
}

.preview-body {
  display: grid;
  gap: 12px;
}

.preview-body h3 {
  margin: 0;
  font-size: 28px;
}

.preview-markdown {
  padding-top: 10px;
  border-top: 1px solid var(--hairline);
}

@media (max-width: 760px) {
  .announcement-row {
    grid-template-columns: 1fr;
  }

  .row-actions {
    justify-content: flex-start;
  }

  .editor-body {
    grid-template-columns: 1fr;
  }

  .modal-backdrop {
    padding: 10px;
  }
}
</style>
