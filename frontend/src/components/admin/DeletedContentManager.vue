<template>
  <section class="manager-stack">
    <header class="section-head">
      <div>
        <h2>删除内容归档</h2>
        <p class="meta">集中查看被删除或隐藏的内容快照，便于追溯与人工核对。</p>
      </div>
      <button class="btn" type="button" @click="loadArchives">刷新归档</button>
    </header>

    <div class="toolbar toolbar--chips">
      <button
        v-for="option in typeOptions"
        :key="option.value"
        class="btn btn-mini"
        :class="{ 'btn-accent': filters.target_type === option.value }"
        type="button"
        @click="setTargetType(option.value)"
      >
        {{ option.label }}
      </button>
    </div>

    <div class="toolbar">
      <select v-model="filters.delete_action" class="select">
        <option value="">全部动作</option>
        <option value="delete">硬删除</option>
        <option value="hide">隐藏 / 软删除</option>
      </select>
      <input v-model.trim="filters.search" class="input grow" placeholder="搜索标题、内容、原作者或删除者" />
      <input v-model.trim="filters.original_author" class="input" placeholder="原作者" />
      <input v-model.trim="filters.deleted_by" class="input" placeholder="删除者" />
      <input v-model="filters.start_at" class="input" type="datetime-local" />
      <input v-model="filters.end_at" class="input" type="datetime-local" />
      <button class="btn" type="button" @click="loadArchives">筛选</button>
      <button class="btn" type="button" @click="resetFilters">重置</button>
    </div>

    <p class="meta">共 {{ meta.count }} 条归档记录</p>

    <article v-for="item in archives" :key="item.id" class="archive-card">
      <div class="archive-head">
        <div class="archive-title">
          <strong>{{ item.title || fallbackTitle(item) }}</strong>
          <div class="archive-tags">
            <span class="badge">{{ formatTargetType(item.target_type) }}</span>
            <span class="badge badge--muted">{{ formatDeleteAction(item.delete_action) }}</span>
          </div>
        </div>
        <div class="archive-meta">
          <span>#{{ item.target_id || "-" }}</span>
          <span>{{ formatDateTime(item.created_at) }}</span>
        </div>
      </div>

      <p v-if="item.summary" class="archive-summary">{{ item.summary }}</p>
      <p class="meta">
        原作者：{{ item.original_author?.username || item.original_author_name || "-" }} ·
        删除者：{{ item.deleted_by?.username || item.deleted_by_name || "-" }}
      </p>

      <details class="archive-details">
        <summary>查看快照</summary>
        <pre v-if="item.content_md" class="archive-content">{{ item.content_md }}</pre>
        <pre class="archive-json">{{ formatSnapshot(item.snapshot) }}</pre>
      </details>
    </article>

    <button v-if="meta.hasMore" class="btn" type="button" @click="loadMoreArchives">加载更多</button>
    <p v-if="!archives.length" class="meta">当前没有匹配的删除归档。</p>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import api from "../../services/api";
import { useUiStore } from "../../stores/ui";

const ui = useUiStore();

const typeOptions = [
  { value: "", label: "全部" },
  { value: "TrickEntry", label: "Trick" },
  { value: "Question", label: "问题" },
  { value: "Answer", label: "回答" },
  { value: "CompetitionNotice", label: "赛事公告" },
  { value: "CompetitionScheduleEntry", label: "锦标赛" },
  { value: "CompetitionPracticeLink", label: "补题链接" },
  { value: "Announcement", label: "站内公告" },
  { value: "IssueTicket", label: "工单" },
];

const archives = ref([]);
const meta = reactive({
  count: 0,
  page: 1,
  hasMore: false,
});

const filters = reactive({
  target_type: "",
  delete_action: "",
  search: "",
  original_author: "",
  deleted_by: "",
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
  if (filters.target_type) params.target_type = filters.target_type;
  if (filters.delete_action) params.delete_action = filters.delete_action;
  if (filters.search.trim()) params.search = filters.search.trim();
  if (filters.original_author.trim()) params.original_author = filters.original_author.trim();
  if (filters.deleted_by.trim()) params.deleted_by = filters.deleted_by.trim();
  if (filters.start_at) params.start_at = filters.start_at;
  if (filters.end_at) params.end_at = filters.end_at;
  return params;
}

async function loadArchives(page = 1, append = false) {
  try {
    const { data } = await api.get("/deleted-content-archives/", {
      params: buildParams(page),
    });
    const { results, count } = unpackListPayload(data);
    archives.value = append ? appendUniqueById(archives.value, results) : results;
    meta.count = count;
    meta.page = page;
    meta.hasMore = archives.value.length < count;
  } catch (error) {
    ui.error(getErrorText(error, "删除归档加载失败"));
  }
}

async function loadMoreArchives() {
  if (!meta.hasMore) return;
  await loadArchives(meta.page + 1, true);
}

function setTargetType(value) {
  filters.target_type = value;
  loadArchives();
}

function resetFilters() {
  filters.target_type = "";
  filters.delete_action = "";
  filters.search = "";
  filters.original_author = "";
  filters.deleted_by = "";
  filters.start_at = "";
  filters.end_at = "";
  loadArchives();
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

function formatDeleteAction(value) {
  return value === "hide" ? "隐藏" : value === "delete" ? "删除" : value || "-";
}

function formatTargetType(value) {
  return typeOptions.find((item) => item.value === value)?.label || value || "未知类型";
}

function fallbackTitle(item) {
  return `${formatTargetType(item.target_type)} #${item.target_id || "-"}`;
}

function formatSnapshot(snapshot) {
  try {
    return JSON.stringify(snapshot || {}, null, 2);
  } catch {
    return "{}";
  }
}

onMounted(() => {
  loadArchives();
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

.toolbar--chips {
  align-items: stretch;
}

.grow {
  flex: 1 1 320px;
}

.archive-card {
  display: grid;
  gap: 10px;
  padding: 14px;
  border-radius: 16px;
  background: var(--surface-soft);
  border: 1px solid var(--hairline);
}

.archive-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: start;
}

.archive-title {
  min-width: 0;
  display: grid;
  gap: 6px;
}

.archive-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.archive-meta {
  display: grid;
  gap: 4px;
  justify-items: end;
  color: var(--text-quiet);
  font-size: 13px;
  white-space: nowrap;
}

.badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  background: color-mix(in srgb, var(--accent) 12%, var(--surface));
  color: var(--text-strong);
}

.badge--muted {
  background: var(--surface);
  color: var(--text-quiet);
}

.archive-summary,
.meta {
  margin: 0;
}

.archive-summary {
  color: var(--text-soft);
  white-space: pre-wrap;
  word-break: break-word;
}

.meta {
  color: var(--text-quiet);
}

.archive-details {
  display: grid;
  gap: 8px;
}

.archive-details summary {
  cursor: pointer;
  color: var(--accent);
  font-weight: 600;
}

.archive-content,
.archive-json {
  margin: 0;
  padding: 12px;
  border-radius: 12px;
  background: var(--surface);
  border: 1px solid var(--hairline);
  white-space: pre-wrap;
  word-break: break-word;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.6;
}

@media (max-width: 720px) {
  .archive-head {
    grid-template-columns: 1fr;
    display: grid;
  }

  .archive-meta {
    justify-items: start;
    white-space: normal;
  }
}
</style>
