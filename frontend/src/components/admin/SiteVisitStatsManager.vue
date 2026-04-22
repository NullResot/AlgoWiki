<template>
  <section class="manager-stack">
    <header class="section-head">
      <div>
        <h2>网站访问量</h2>
        <p class="meta">仅统计站内页面访问量（PV），用于超级管理员查看今日、本周、本月与累计访问趋势。</p>
      </div>
      <button class="btn" type="button" :disabled="loading" @click="loadStats">
        {{ loading ? "刷新中..." : "刷新访问量" }}
      </button>
    </header>

    <div v-if="stats" class="summary-grid">
      <div class="summary-item">
        <strong>{{ formatCount(stats.today) }}</strong>
        <span>今日访问量</span>
      </div>
      <div class="summary-item">
        <strong>{{ formatCount(stats.week) }}</strong>
        <span>本周访问量</span>
      </div>
      <div class="summary-item">
        <strong>{{ formatCount(stats.month) }}</strong>
        <span>本月访问量</span>
      </div>
      <div class="summary-item summary-item--accent">
        <strong>{{ formatCount(stats.total) }}</strong>
        <span>累计访问量</span>
      </div>
    </div>

    <p v-if="stats?.generated_at" class="meta">统计生成时间：{{ formatDateTime(stats.generated_at) }}</p>

    <div v-if="stats?.recent_days?.length" class="trend-card">
      <div class="trend-head">
        <strong>近 7 日访问量</strong>
        <span class="meta">按自然日聚合</span>
      </div>
      <div class="trend-list">
        <div v-for="item in stats.recent_days" :key="item.date" class="trend-row">
          <span class="trend-date">{{ item.date }}</span>
          <div class="bar-track">
            <div class="bar-fill" :style="{ width: `${barPercent(item.page_views)}%` }"></div>
          </div>
          <strong>{{ formatCount(item.page_views) }}</strong>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

import api from "../../services/api";
import { useUiStore } from "../../stores/ui";

const ui = useUiStore();
const loading = ref(false);
const stats = ref(null);

const maxRecentDayViews = computed(() => {
  const rows = Array.isArray(stats.value?.recent_days) ? stats.value.recent_days : [];
  return Math.max(...rows.map((item) => Number(item.page_views) || 0), 1);
});

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return error?.message || fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  return fallback;
}

async function loadStats() {
  loading.value = true;
  try {
    const { data } = await api.get("/site-visits/stats/");
    stats.value = data;
  } catch (error) {
    ui.error(getErrorText(error, "访问量统计加载失败"));
  } finally {
    loading.value = false;
  }
}

function formatCount(value) {
  return new Intl.NumberFormat("zh-CN").format(Number(value || 0));
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

function barPercent(value) {
  const max = Number(maxRecentDayViews.value || 1);
  const current = Number(value || 0);
  if (max <= 0 || current <= 0) return 0;
  return Math.max(8, Math.min(100, Math.round((current / max) * 100)));
}

onMounted(() => {
  loadStats();
});
</script>

<style scoped>
.manager-stack {
  display: grid;
  gap: 12px;
}

.section-head {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: start;
  justify-content: space-between;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-item {
  display: grid;
  gap: 6px;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid var(--hairline);
  background: var(--surface-soft);
}

.summary-item strong {
  font-size: 28px;
  line-height: 1;
}

.summary-item span {
  color: var(--text-quiet);
}

.summary-item--accent {
  background: color-mix(in srgb, var(--accent) 10%, var(--surface-soft));
}

.trend-card {
  display: grid;
  gap: 12px;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid var(--hairline);
  background: var(--surface-soft);
}

.trend-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
}

.trend-list {
  display: grid;
  gap: 10px;
}

.trend-row {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
}

.trend-date {
  color: var(--text-quiet);
  font-size: 13px;
}

.bar-track {
  position: relative;
  overflow: hidden;
  height: 10px;
  border-radius: 999px;
  background: var(--surface);
  border: 1px solid var(--hairline);
}

.bar-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--accent), color-mix(in srgb, var(--accent) 65%, white));
}

.meta {
  margin: 0;
  color: var(--text-quiet);
}

@media (max-width: 960px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .trend-row {
    grid-template-columns: 1fr;
  }
}
</style>
