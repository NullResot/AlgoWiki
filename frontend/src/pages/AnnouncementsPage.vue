<template>
  <section class="announcement-page">
    <header class="announcement-page-head">
      <h1>公告</h1>
      <p>按发布时间倒序查看全部公告</p>
    </header>

    <section v-if="loading" class="card state-card">
      <p class="meta">公告加载中...</p>
    </section>

    <section v-else-if="announcements.length === 0" class="card state-card">
      <p class="meta">暂无已发布公告。</p>
    </section>

    <section v-else class="announcement-list">
      <article class="announcement-card card" v-for="item in announcements" :key="item.id">
        <header class="announcement-card-head">
          <h2>{{ item.title }}</h2>
          <div class="announcement-meta">
            <span>发布时间：{{ formatDateTime(item.created_at) }}</span>
            <span>发布者：{{ item?.created_by?.username || "system" }}</span>
          </div>
        </header>
        <section class="markdown announcement-markdown" v-html="renderMarkdown(item.content_md || '')"></section>
      </article>
    </section>
  </section>
</template>

<script setup>
import { onMounted, ref } from "vue";

import { renderMarkdown } from "../services/markdown";
import api from "../services/api";
import { useUiStore } from "../stores/ui";

const ui = useUiStore();
const loading = ref(false);
const announcements = ref([]);

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
}

onMounted(async () => {
  await loadAllAnnouncements();
});
</script>

<style scoped>
.announcement-page {
  width: min(1320px, 100%);
  margin: 0 auto;
  display: grid;
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
  padding: 22px;
}

.announcement-list {
  display: grid;
  gap: 14px;
}

.announcement-card {
  padding: 20px 22px;
}

.announcement-card-head {
  display: grid;
  gap: 8px;
  margin-bottom: 12px;
}

.announcement-card-head h2 {
  font-size: clamp(24px, 2vw, 32px);
  line-height: 1.2;
}

.announcement-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  color: #6a7486;
  font-size: 14px;
}

.announcement-markdown {
  color: #1f2532;
}

.announcement-markdown :deep(p:first-child) {
  margin-top: 0;
}

@media (max-width: 760px) {
  .announcement-page {
    gap: 12px;
  }

  .announcement-card {
    padding: 14px;
  }

  .announcement-card-head h2 {
    font-size: clamp(20px, 6vw, 26px);
  }

  .announcement-meta {
    font-size: 13px;
  }
}
</style>
