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

    <SkeletonBlock
      v-if="loading && !announcements.length"
      :lines="5"
      :line-height="18"
      label="正在加载公告"
    />

    <EmptyErrorState
      v-else-if="loadError && !announcements.length"
      tone="error"
      title="公告加载失败"
      :description="loadError"
      action-label="重新加载"
      :busy="loading"
      @action="loadAllAnnouncements"
    />

    <EmptyErrorState
      v-else-if="announcements.length === 0"
      title="暂无公告"
      description="当前没有生效中的站内公告，后续发布后将显示在这里。"
    />

    <section v-else ref="listRef" class="announcement-list" :class="{ 'is-loading': loading }">
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
            <span class="tabular-nums">ID #{{ item.id }}</span>
            <span class="tabular-nums">发布时间：{{ formatDateTime(item.created_at) }}</span>
            <span>发布者：{{ item?.created_by?.username || "官方发布" }}</span>
          </div>
        </header>

        <p v-if="item.summary" class="announcement-summary">{{ item.summary }}</p>
        <section class="markdown announcement-markdown" v-html="item._renderedHtml"></section>
      </article>
    </section>
  </section>
</template>

<script setup>
import { nextTick, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import EmptyErrorState from "../components/EmptyErrorState.vue";
import SkeletonBlock from "../components/SkeletonBlock.vue";
import { useMarkdownCodeCopy } from "../composables/useMarkdownCodeCopy";
import { useRequestControllers } from "../composables/useRequestControllers";
import api, { isRequestCanceled } from "../services/api";
import { renderMarkdown } from "../services/markdown";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";
import { extractApiError, formatDateTime } from "../utils/format";
import { safeScrollIntoView } from "../utils/motion";

const route = useRoute();
const auth = useAuthStore();
const ui = useUiStore();
const requests = useRequestControllers();

const listRef = ref(null);
const loading = ref(false);
const loadError = ref("");
const announcements = ref([]);
const focusedAnnouncementId = ref(null);
const hasInitialized = ref(false);

useMarkdownCodeCopy(listRef, announcements);

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
  safeScrollIntoView(element, { behavior: "smooth", block: "start" });
}

async function loadAllAnnouncements() {
  const controller = requests.replace("announcements");
  loading.value = true;
  loadError.value = "";
  try {
    const rows = [];
    let page = 1;
    while (page) {
      const { data } = await api.get("/announcements/", {
        params: { page },
        signal: controller.signal,
      });
      if (!requests.isCurrent("announcements", controller)) return;
      if (Array.isArray(data)) {
        rows.push(...data);
        break;
      }
      const items = Array.isArray(data?.results) ? data.results : [];
      rows.push(...items);
      page = nextPageFromUrl(data?.next);
    }

    announcements.value = rows
      .sort((a, b) => {
        const priorityDelta = Number(b.priority || 0) - Number(a.priority || 0);
        if (priorityDelta !== 0) return priorityDelta;
        const aTs = Date.parse(a?.created_at || "");
        const bTs = Date.parse(b?.created_at || "");
        return (Number.isNaN(bTs) ? 0 : bTs) - (Number.isNaN(aTs) ? 0 : aTs);
      })
      .map((item) => ({
        ...item,
        _renderedHtml: renderMarkdown(item.content_md || ""),
      }));
  } catch (error) {
    if (isRequestCanceled(error) || !requests.isCurrent("announcements", controller)) {
      return;
    }
    const msg = extractApiError(error, "公告加载失败，请稍后重试");
    loadError.value = msg;
    if (!announcements.value.length) {
      ui.error(msg);
    }
  } finally {
    if (requests.release("announcements", controller)) {
      loading.value = false;
    }
  }

  await focusAnnouncementFromRoute();
}

watch(
  () => auth.isManager,
  async () => {
    if (!hasInitialized.value) return;
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
  hasInitialized.value = true;
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
  transition: opacity var(--dur-fast, 150ms) var(--ease-standard, ease);
}

.announcement-list.is-loading {
  opacity: 0.56;
  pointer-events: none;
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

.announcement-card--focused,
.announcement-card--focused:first-child {
  padding: 20px 20px 20px 18px;
  margin: 6px 0;
  border-radius: var(--radius-md);
  border: 1px solid color-mix(in srgb, var(--accent) 34%, var(--hairline));
  border-left: 4px solid var(--accent);
  background: color-mix(in srgb, var(--accent) 5%, var(--surface));
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
  background: color-mix(in srgb, var(--danger, #e11d48) 14%, var(--surface-strong));
  color: color-mix(in srgb, var(--danger, #e11d48) 84%, var(--text-strong));
}

.level-pill--important {
  background: color-mix(in srgb, #f59e0b 15%, var(--surface-strong));
  color: color-mix(in srgb, #f59e0b 78%, var(--text-strong));
}

.level-pill--normal {
  background: color-mix(in srgb, var(--success, #16a34a) 14%, var(--surface-strong));
  color: color-mix(in srgb, var(--success, #16a34a) 82%, var(--text-strong));
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
