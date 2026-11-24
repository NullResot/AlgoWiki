<template>
  <section class="manager-stack">
    <header class="section-head">
      <div>
        <h2>操作日志</h2>
        <p class="meta">检索站内操作事件，支持按类型、用户、目标和时间范围筛选。</p>
      </div>
      <button class="btn" type="button" :disabled="loading" @click="loadEvents(1, false)">
        {{ loading ? "刷新中..." : "刷新日志" }}
      </button>
    </header>

    <div class="toolbar">
      <select v-model="filters.event_type" class="select" @change="loadEvents(1, false)">
        <option value="">全部类型</option>
        <option value="star">收藏 (star)</option>
        <option value="comment">评论 (comment)</option>
        <option value="issue">工单 (issue)</option>
        <option value="revision">修订 (revision)</option>
        <option value="announcement">公告 (announcement)</option>
        <option value="admin">管理操作 (admin)</option>
      </select>
      <input v-model="filters.user" class="input" placeholder="用户 ID / 用户名" @keyup.enter="loadEvents(1, false)" />
      <input v-model="filters.target_type" class="input" placeholder="目标类型，如 Article" @keyup.enter="loadEvents(1, false)" />
      <input v-model="filters.search" class="input grow" placeholder="检索 payload 关键词" @keyup.enter="loadEvents(1, false)" />
      <input v-model="filters.start_at" class="input" type="datetime-local" />
      <input v-model="filters.end_at" class="input" type="datetime-local" />
      <button class="btn" type="button" :disabled="loading" @click="loadEvents(1, false)">筛选</button>
      <button class="btn" type="button" :disabled="exporting" @click="exportEvents">
        {{ exporting ? "导出中..." : "导出 CSV" }}
      </button>
      <button class="btn" type="button" :disabled="loading" @click="resetFilters">重置</button>
    </div>

    <p class="meta">共 {{ meta.count }} 条日志</p>

    <div v-if="loading && !events.length" class="loading-box">
      <SkeletonBlock :lines="4" :line-height="18" label="正在加载操作日志" />
    </div>
    <template v-else>
      <article v-for="item in events" :key="item.id" class="admin-row">
        <div class="row-main">
          <strong>{{ formatEventType(item.event_type) }} · {{ item.target_type }} #{{ item.target_id }}</strong>
          <p class="meta">{{ item.user?.username || "匿名" }} · {{ formatDateTime(item.created_at) }}</p>
          <p class="payload">{{ renderPayload(item.payload) }}</p>
        </div>
      </article>

      <button v-if="meta.hasMore" class="btn" type="button" :disabled="loading" @click="loadMoreEvents">
        {{ loading ? "加载中..." : "加载更多日志" }}
      </button>
      <p v-if="!events.length" class="meta">当前没有匹配的日志。</p>
    </template>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import SkeletonBlock from "../SkeletonBlock.vue";
import api from "../../services/api";
import { useUiStore } from "../../stores/ui";

const ui = useUiStore();

const loading = ref(false);
const exporting = ref(false);
const events = ref([]);
const meta = reactive({
  count: 0,
  page: 1,
  hasMore: false,
});

const filters = reactive({
  event_type: "",
  user: "",
  target_type: "",
  search: "",
  start_at: "",
  end_at: "",
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

function buildParams(page = 1) {
  const params = { page };
  if (filters.event_type) params.event_type = filters.event_type;
  if (filters.user.trim()) params.user = filters.user.trim();
  if (filters.target_type.trim()) params.target_type = filters.target_type.trim();
  if (filters.search.trim()) params.search = filters.search.trim();
  if (filters.start_at) params.start_at = filters.start_at;
  if (filters.end_at) params.end_at = filters.end_at;
  return params;
}

async function loadEvents(page = 1, append = false) {
  loading.value = true;
  try {
    const { data } = await api.get("/events/", { params: buildParams(page) });
    const { results, count } = unpackListPayload(data);
    events.value = append ? appendUniqueById(events.value, results) : results;
    meta.count = count;
    meta.page = page;
    meta.hasMore = events.value.length < count;
  } catch (error) {
    ui.error(getErrorText(error, "日志加载失败"));
  } finally {
    loading.value = false;
  }
}

async function loadMoreEvents() {
  if (!meta.hasMore || loading.value) return;
  await loadEvents(meta.page + 1, true);
}

function resetFilters() {
  filters.event_type = "";
  filters.user = "";
  filters.target_type = "";
  filters.search = "";
  filters.start_at = "";
  filters.end_at = "";
  loadEvents(1, false);
}

async function exportEvents() {
  if (exporting.value) return;
  exporting.value = true;
  try {
    const response = await api.get("/events/export/", {
      params: buildParams(1),
      responseType: "blob",
    });
    const blob = new Blob([response.data], { type: "text/csv;charset=utf-8;" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `algowiki-events-${Date.now()}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
    ui.success("操作日志已导出");
  } catch (error) {
    ui.error(getErrorText(error, "导出操作日志失败"));
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

function formatEventType(value) {
  const labels = {
    star: "收藏",
    comment: "评论",
    issue: "工单",
    revision: "修订",
    announcement: "公告",
    admin: "管理操作",
  };
  return labels[value] || value || "未知事件";
}

function renderPayload(payload) {
  if (!payload || typeof payload !== "object") return "{}";
  const parts = Object.entries(payload).map(([key, value]) => {
    const nextValue = typeof value === "string" ? value : JSON.stringify(value);
    return `${key}=${nextValue}`;
  });
  return parts.join(" | ") || "{}";
}

onMounted(() => {
  loadEvents();
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
</style>
