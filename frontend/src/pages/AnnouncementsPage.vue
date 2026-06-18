<template>
  <section class="announcement-page">
    <header class="announcement-page-head">
      <div>
        <h1>公告</h1>
        <p>按优先级和发布时间查看当前有效的站内公告。</p>
      </div>
      <RouterLink v-if="auth.isManager" class="btn btn-accent" :to="{ name: 'manage-announcements' }">
        管理公告
      </RouterLink>
    </header>

    <section v-if="loading" class="state-card">
      <p class="meta">公告加载中...</p>
    </section>

    <section v-else-if="announcements.length === 0" class="state-card">
      <p class="meta">暂无公告。</p>
    </section>

    <section v-else class="announcement-list">
      <article
        v-for="item in announcements"
        :id="getAnnouncementElementId(item.id)"
        :key="item.id"
        class="announcement-card"
        :class="{ 'announcement-card--focused': focusedAnnouncementId === item.id }"
      >
        <header class="announcement-card-head">
          <div class="announcement-title-row">
            <h2>{{ item.title }}</h2>
            <div class="pill-row">
              <span v-if="focusedAnnouncementId === item.id" class="focus-pill">当前公告</span>
              <span class="level-pill" :class="`level-pill--${item.level || 'normal'}`">{{ levelLabel(item.level) }}</span>
            </div>
          </div>
          <div class="announcement-meta">
            <span>ID #{{ item.id }}</span>
            <span>发布时间：{{ formatDateTime(item.created_at) }}</span>
            <span>发布者：{{ item?.created_by?.username || "system" }}</span>
          </div>
        </header>

        <p v-if="item.summary" class="announcement-summary">{{ item.summary }}</p>
        <section class="markdown announcement-markdown" v-html="renderMarkdown(item.content_md || '')"></section>
      </article>
    </section>
  </section>
</template>

<script setup>
import { nextTick, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import api from "../services/api";
import { renderMarkdown } from "../services/markdown";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const route = useRoute();
const auth = useAuthStore();
const ui = useUiStore();
const loading = ref(false);
const announcements = ref([]);
const focusedAnnouncementId = ref(null);

function getErrorText(error, fallback = "操作失败") {
  return error?.response?.data?.detail || error?.message || fallback;
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

function normalizeAnnouncementId(value) {
  const parsed = Number(String(value || "").trim());
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function getAnnouncementElementId(id) {
  return `announcement-${id}`;
}

function levelLabel(value) {
  const labels = {
    emergency: "紧急公告",
    important: "重要公告",
    normal: "普通公告",
    low: "低优先级",
  };
  return labels[value] || "普通公告";
}

async function focusAnnouncementFromRoute() {
  const targetId = normalizeAnnouncementId(route.query.announcement);
  focusedAnnouncementId.value = targetId;
  if (!targetId || !announcements.value.some((item) => item.id === targetId)) {
    return;
  }
  await nextTick();
  const element = document.getElementById(getAnnouncementElementId(targetId));
  if (!element) return;
  element.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function loadAllAnnouncements() {
  loading.value = true;
  try {
    const rows = [];
    let page = 1;
    while (page) {
      const { data } = await api.get("/announcements/", { params: { page } });
      if (Array.isArray(data)) {
        rows.push(...data);
        break;
      }
      const items = Array.isArray(data?.results) ? data.results : [];
      rows.push(...items);
      page = nextPageFromUrl(data?.next);
    }

    announcements.value = rows.sort((a, b) => {
      const priorityDelta = Number(b.priority || 0) - Number(a.priority || 0);
      if (priorityDelta !== 0) return priorityDelta;
      const aTs = Date.parse(a?.created_at || "");
      const bTs = Date.parse(b?.created_at || "");
      return (Number.isNaN(bTs) ? 0 : bTs) - (Number.isNaN(aTs) ? 0 : aTs);
    });
  } catch (error) {
    announcements.value = [];
    ui.error(getErrorText(error, "公告加载失败"));
  } finally {
    loading.value = false;
  }

  await focusAnnouncementFromRoute();
}

watch(
  () => auth.isManager,
  async () => {
    await loadAllAnnouncements();
  }
);

watch(
  () => route.query.announcement,
  async () => {
    await focusAnnouncementFromRoute();
  }
);

onMounted(async () => {
  await loadAllAnnouncements();
});
</script>

<style scoped>
.announcement-page {
  width: min(1120px, 100%);
  margin: 0 auto;
  display: grid;
  gap: 20px;
}

.announcement-page-head {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: 16px;
}

.announcement-page-head h1 {
  font-size: clamp(34px, 3.2vw, 48px);
  line-height: 1.12;
}

.announcement-page-head p {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 15px;
}

.state-card {
  padding: 16px 0;
  border-top: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
}

.announcement-list {
  display: grid;
  gap: 0;
}

.announcement-card {
  padding: 22px 0;
  border-top: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
  scroll-margin-top: 110px;
}

.announcement-card:first-child {
  padding-top: 0;
  border-top: 0;
}

.announcement-card--focused {
  border-color: color-mix(in srgb, var(--accent) 34%, transparent);
}

.announcement-card-head {
  display: grid;
  gap: 10px;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--hairline);
}

.announcement-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.announcement-title-row h2 {
  font-size: clamp(24px, 2vw, 32px);
  line-height: 1.2;
}

.pill-row,
.announcement-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
}

.announcement-meta {
  color: var(--text-quiet);
  font-size: 14px;
}

.focus-pill,
.level-pill {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: var(--surface-soft);
  color: var(--text-soft);
  font-size: 13px;
  font-weight: 700;
}

.focus-pill {
  background: color-mix(in srgb, var(--accent) 12%, var(--surface-strong));
  color: var(--accent);
}

.level-pill--emergency {
  background: rgba(244, 63, 94, 0.12);
  color: #b42318;
}

.level-pill--important {
  background: rgba(245, 158, 11, 0.13);
  color: #8a5b08;
}

.level-pill--normal {
  background: rgba(34, 197, 94, 0.11);
  color: #16794c;
}

.announcement-summary {
  margin: 0 0 12px;
  color: var(--muted);
  font-size: 15px;
  line-height: 1.7;
}

.announcement-markdown {
  color: var(--text);
  font-size: clamp(1.02rem, 0.98rem + 0.18vw, 1.1rem);
}

.announcement-markdown :deep(p:first-child) {
  margin-top: 0;
}

:global(html[data-theme="academic"]) .announcement-markdown {
  font-family: var(--font-reading);
}

@media (max-width: 760px) {
  .announcement-page {
    gap: 12px;
  }

  .announcement-page-head,
  .announcement-title-row {
    flex-direction: column;
    align-items: stretch;
  }

  .announcement-page-head .btn {
    width: 100%;
  }

  .announcement-card {
    padding: 18px 0;
  }

  .announcement-title-row h2 {
    font-size: clamp(20px, 6vw, 26px);
  }

  .announcement-meta {
    font-size: 13px;
  }
}
</style>
