<template>
  <section class="calendar-page">
    <section class="calendar-controls card">
      <div class="controls-head">
        <div>
          <h2 class="section-title">来源筛选</h2>
          <p class="meta">点击分类后只显示对应平台的比赛，表格会实时重新分组与排序。</p>
        </div>
        <div class="control-actions">
          <button type="button" class="btn" :disabled="loadingRows || loadingTaxonomy" @click="refreshAll">
            {{ loadingRows || loadingTaxonomy ? "刷新中..." : "刷新列表" }}
          </button>
          <button type="button" class="btn" @click="selectAllSites">全选</button>
          <button type="button" class="btn" @click="clearSites">清空</button>
        </div>
      </div>

      <div class="site-filter-grid">
        <button
          v-for="item in sourceOptions"
          :key="item.key"
          type="button"
          class="site-chip"
          :class="{ 'site-chip--active': isSiteSelected(item.key) }"
          @click="toggleSite(item.key)"
        >
          <span class="site-chip-name">{{ item.name }}</span>
        </button>
      </div>
    </section>

    <section class="calendar-section card">
      <header class="section-head">
        <div>
          <h2 class="section-title">正在进行</h2>
          <p class="meta">如果当前没有进行中的比赛，表格会保持为空。</p>
        </div>
        <span class="pill">{{ ongoingRows.length }}</span>
      </header>
      <div class="table-shell">
        <table class="contest-table">
          <thead>
            <tr>
              <th>比赛网站</th>
              <th>比赛名字</th>
              <th>开始时间 - 结束时间</th>
              <th>持续时间</th>
              <th>跳转链接</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in ongoingRows" :key="rowKey(item)">
              <td data-label="比赛网站">
                <span class="site-badge">{{ siteLabel(item.source_site) }}</span>
              </td>
              <td data-label="比赛名字">
                <div class="title-cell">
                  <strong>{{ item.title }}</strong>
                  <span v-if="item.organizer" class="meta">{{ item.organizer }}</span>
                </div>
              </td>
              <td data-label="开始时间 - 结束时间">{{ timeRange(item) }}</td>
              <td data-label="持续时间">{{ duration(item) }}</td>
              <td data-label="跳转链接">
                <a class="table-link" :href="resolveContestUrl(item)" target="_blank" rel="noopener noreferrer">前往比赛</a>
              </td>
            </tr>
            <tr v-if="!ongoingRows.length" class="empty-row">
              <td colspan="5">当前没有正在进行中的比赛。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="calendar-section card">
      <header class="section-head">
        <div>
          <h2 class="section-title">即将开始</h2>
          <p class="meta">按距离当前时间从近到远排序。</p>
        </div>
        <span class="pill">{{ upcomingRows.length }}</span>
      </header>
      <div class="table-shell">
        <table class="contest-table">
          <thead>
            <tr>
              <th>比赛网站</th>
              <th>比赛名字</th>
              <th>开始时间 - 结束时间</th>
              <th>持续时间</th>
              <th>跳转链接</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in upcomingRows" :key="rowKey(item)">
              <td data-label="比赛网站">
                <span class="site-badge">{{ siteLabel(item.source_site) }}</span>
              </td>
              <td data-label="比赛名字">
                <div class="title-cell">
                  <strong>{{ item.title }}</strong>
                  <span v-if="item.organizer" class="meta">{{ item.organizer }}</span>
                </div>
              </td>
              <td data-label="开始时间 - 结束时间">{{ timeRange(item) }}</td>
              <td data-label="持续时间">{{ duration(item) }}</td>
              <td data-label="跳转链接">
                <a class="table-link" :href="resolveContestUrl(item)" target="_blank" rel="noopener noreferrer">前往比赛</a>
              </td>
            </tr>
            <tr v-if="!upcomingRows.length" class="empty-row">
              <td colspan="5">当前没有符合筛选条件的待开始比赛。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="calendar-section card">
      <header class="section-head">
        <div>
          <h2 class="section-title">已经结束</h2>
          <p class="meta">按距离当前时间从近到远排序。</p>
        </div>
        <span class="pill">{{ finishedRows.length }}</span>
      </header>
      <div class="table-shell">
        <table class="contest-table">
          <thead>
            <tr>
              <th>比赛网站</th>
              <th>比赛名字</th>
              <th>开始时间 - 结束时间</th>
              <th>持续时间</th>
              <th>跳转链接</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in finishedRows" :key="rowKey(item)">
              <td data-label="比赛网站">
                <span class="site-badge">{{ siteLabel(item.source_site) }}</span>
              </td>
              <td data-label="比赛名字">
                <div class="title-cell">
                  <strong>{{ item.title }}</strong>
                  <span v-if="item.organizer" class="meta">{{ item.organizer }}</span>
                </div>
              </td>
              <td data-label="开始时间 - 结束时间">{{ timeRange(item) }}</td>
              <td data-label="持续时间">{{ duration(item) }}</td>
              <td data-label="跳转链接">
                <a class="table-link" :href="resolveContestUrl(item)" target="_blank" rel="noopener noreferrer">前往比赛</a>
              </td>
            </tr>
            <tr v-if="!finishedRows.length" class="empty-row">
              <td colspan="5">当前没有可展示的已结束比赛。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import api from "../services/api";
import { useUiStore } from "../stores/ui";

const ui = useUiStore();

const defaultSources = [
  { key: "codeforces", name: "Codeforces", count: 0 },
  { key: "atcoder", name: "AtCoder", count: 0 },
  { key: "nowcoder", name: "牛客", count: 0 },
  { key: "luogu", name: "洛谷", count: 0 },
];

const taxonomy = ref({
  sources: defaultSources,
  count: 0,
  latest_sync_at: "",
});
const rows = ref([]);
const loadingRows = ref(false);
const loadingTaxonomy = ref(false);
const selectedSites = ref(defaultSources.map((item) => item.key));
const nowTick = ref(Date.now());
let ticker = null;

function extractRows(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.results)) return payload.results;
  return [];
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

async function fetchAll(path, params = {}) {
  const merged = [];
  let page = 1;
  while (page) {
    const { data } = await api.get(path, { params: { ...params, page } });
    if (Array.isArray(data)) {
      merged.push(...data);
      break;
    }
    merged.push(...extractRows(data));
    page = nextPageFromUrl(data?.next);
  }
  return merged;
}

function getErrorText(error, fallback = "加载失败") {
  const payload = error?.response?.data;
  if (!payload) return fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload?.detail === "string") return payload.detail;
  return fallback;
}

const sourceOptions = computed(() => {
  const map = new Map(defaultSources.map((item) => [item.key, { ...item }]));
  for (const item of Array.isArray(taxonomy.value?.sources) ? taxonomy.value.sources : []) {
    if (!map.has(item.key)) continue;
    map.set(item.key, {
      ...map.get(item.key),
      count: Number(item.count || 0),
      name: item.name || map.get(item.key).name,
    });
  }
  return [...map.values()];
});

const filteredRows = computed(() => {
  const selected = new Set(selectedSites.value);
  return rows.value.filter((item) => selected.has(item.source_site));
});

function toTimeMs(value) {
  const parsed = new Date(value || "");
  return Number.isNaN(parsed.getTime()) ? 0 : parsed.getTime();
}

const ongoingRows = computed(() => {
  const now = nowTick.value;
  return filteredRows.value
    .filter((item) => {
      const start = toTimeMs(item.start_time);
      const end = toTimeMs(item.end_time);
      return start && end && start <= now && now < end;
    })
    .sort((a, b) => toTimeMs(a.end_time) - toTimeMs(b.end_time));
});

const upcomingRows = computed(() => {
  const now = nowTick.value;
  return filteredRows.value
    .filter((item) => {
      const start = toTimeMs(item.start_time);
      return start > now;
    })
    .sort((a, b) => toTimeMs(a.start_time) - toTimeMs(b.start_time));
});

const finishedRows = computed(() => {
  const now = nowTick.value;
  return filteredRows.value
    .filter((item) => {
      const end = toTimeMs(item.end_time);
      return end && end <= now;
    })
    .sort((a, b) => toTimeMs(b.end_time) - toTimeMs(a.end_time));
});

function rowKey(item) {
  return `${item.source_site}-${item.source_id}`;
}

function siteLabel(siteKey) {
  return sourceOptions.value.find((item) => item.key === siteKey)?.name || siteKey || "-";
}

function duration(item) {
  if (item?.duration_label) return item.duration_label;
  const totalSeconds = Number(item?.duration_seconds || 0);
  if (!totalSeconds) return "-";
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const parts = [];
  if (days) parts.push(`${days}d`);
  if (hours || days) parts.push(`${hours}h`);
  parts.push(`${minutes}m`);
  return parts.join(" ");
}

function formatDateTime(value) {
  const date = new Date(value || "");
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function timeRange(item) {
  if (item?.time_range_label) return item.time_range_label;
  return `${formatDateTime(item?.start_time)} - ${formatDateTime(item?.end_time)}`;
}

function resolveContestUrl(item) {
  const fallbackUrl = String(item?.url || "").trim();
  if (item?.source_site !== "codeforces") {
    return fallbackUrl;
  }

  const contestId = String(item?.source_id || "").trim();
  if (!contestId) {
    return fallbackUrl;
  }

  const path = toTimeMs(item?.start_time) > nowTick.value ? "contests" : "contest";
  return `https://codeforces.com/${path}/${encodeURIComponent(contestId)}`;
}

function isSiteSelected(key) {
  return selectedSites.value.includes(key);
}

function toggleSite(key) {
  if (!key) return;
  selectedSites.value = [key];
}

function selectAllSites() {
  selectedSites.value = sourceOptions.value.map((item) => item.key);
}

function clearSites() {
  selectedSites.value = [];
}

async function loadTaxonomy() {
  loadingTaxonomy.value = true;
  try {
    const { data } = await api.get("/competition-calendar/taxonomy/");
    taxonomy.value = {
      sources: Array.isArray(data?.sources) ? data.sources : defaultSources,
      count: Number(data?.count || 0),
      latest_sync_at: data?.latest_sync_at || "",
    };
  } catch (error) {
    taxonomy.value = {
      sources: defaultSources,
      count: 0,
      latest_sync_at: "",
    };
    ui.error(getErrorText(error, "读取比赛日历来源失败"));
  } finally {
    loadingTaxonomy.value = false;
  }
}

async function loadRows() {
  loadingRows.value = true;
  try {
    rows.value = await fetchAll("/competition-calendar/", { order: "asc" });
  } catch (error) {
    rows.value = [];
    ui.error(getErrorText(error, "读取比赛日历失败"));
  } finally {
    loadingRows.value = false;
  }
}

async function refreshAll() {
  await Promise.all([loadTaxonomy(), loadRows()]);
}

function startClock() {
  stopClock();
  ticker = window.setInterval(() => {
    nowTick.value = Date.now();
  }, 60000);
}

function stopClock() {
  if (ticker) {
    window.clearInterval(ticker);
    ticker = null;
  }
}

onMounted(async () => {
  startClock();
  await refreshAll();
});

onBeforeUnmount(() => {
  stopClock();
});
</script>

<style scoped>
.calendar-page {
  width: min(1440px, 100%);
  margin: 0 auto;
  display: grid;
  gap: 16px;
}

.calendar-controls,
.calendar-section {
  padding: 16px;
}

.controls-head,
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.control-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.site-filter-grid {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.site-chip {
  border: 1px solid var(--button-border);
  border-radius: var(--radius-md);
  background: var(--surface-strong);
  color: var(--text-strong);
  padding: 14px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  box-shadow: var(--shadow-sm);
  transition:
    transform 0.18s ease,
    border-color 0.18s ease,
    background-color 0.18s ease,
    box-shadow 0.18s ease;
}

.site-chip:hover {
  transform: translateY(-1px);
}

.site-chip--active {
  border-color: transparent;
  background: color-mix(in srgb, var(--accent) 10%, var(--surface-strong));
  box-shadow: var(--accent-shadow);
}

.site-chip-name {
  font-weight: 700;
}

.table-shell {
  margin-top: 14px;
  overflow-x: auto;
}

.contest-table {
  width: 100%;
  border-collapse: collapse;
}

.contest-table th,
.contest-table td {
  border: 1px solid var(--hairline-strong);
  padding: 10px 12px;
  vertical-align: top;
}

.contest-table thead th {
  background: var(--table-head-bg);
  text-align: left;
  font-size: 13px;
  letter-spacing: 0.04em;
}

.contest-table tbody tr:nth-child(odd) {
  background: var(--content-table-row);
}

.contest-table tbody tr:nth-child(even) {
  background: var(--content-table-row-alt);
}

.contest-table tbody tr:hover {
  background: color-mix(in srgb, var(--accent) 6%, transparent);
}

.site-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 92px;
  padding: 6px 10px;
  border-radius: 999px;
  background: var(--pill-bg);
  color: var(--pill-text);
  font-size: 13px;
  font-weight: 700;
}

.title-cell {
  display: grid;
  gap: 4px;
}

.title-cell strong {
  color: var(--text-strong);
  line-height: 1.45;
}

.table-link {
  color: var(--link);
  text-decoration: underline;
  text-underline-offset: 2px;
  white-space: nowrap;
}

.table-link:visited {
  color: var(--link-visited);
}

.empty-row td {
  text-align: center;
  color: var(--text-quiet);
  background: var(--surface-soft);
}

@media (max-width: 1100px) {
  .site-filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .controls-head,
  .section-head {
    flex-direction: column;
  }

  .control-actions {
    width: 100%;
  }

  .control-actions .btn {
    width: 100%;
  }

  .site-filter-grid {
    grid-template-columns: 1fr;
  }

  .contest-table thead {
    display: none;
  }

  .contest-table,
  .contest-table tbody {
    display: grid;
    gap: 10px;
  }

  .contest-table tr {
    display: grid;
    gap: 8px;
    padding: 12px;
    border: 1px solid var(--panel-border);
    border-radius: var(--radius-md);
    background: var(--surface-strong);
  }

  .contest-table td {
    border: 0;
    padding: 0;
    display: grid;
    grid-template-columns: minmax(94px, 110px) minmax(0, 1fr);
    gap: 10px;
  }

  .contest-table td::before {
    content: attr(data-label);
    color: var(--text-quiet);
    font-size: 12px;
    font-weight: 700;
  }

  .empty-row td {
    display: block;
    text-align: left;
  }

  .empty-row td::before {
    display: none;
  }
}
.calendar-controls,
.calendar-section {
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  backdrop-filter: none;
}

.calendar-controls {
  padding: 0 0 18px;
}

.calendar-section {
  padding: 18px 0 0;
  border-top: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
}

.section-head {
  padding-bottom: 12px;
  border-bottom: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
}

.site-chip {
  background: transparent;
  box-shadow: none;
}

.table-shell {
  padding-top: 0;
}

.contest-table {
  border-collapse: collapse;
}

.contest-table tr {
  border: 0;
  border-radius: 0;
  background: transparent;
  padding: 0;
}

.contest-table th,
.contest-table td {
  border: 0;
  border-bottom: 1px solid color-mix(in srgb, var(--hairline-strong) 88%, transparent);
  padding: 10px 12px;
}

.contest-table th + th,
.contest-table td + td {
  border-left: 1px solid color-mix(in srgb, var(--hairline) 92%, transparent);
}

.contest-table thead th {
  background: color-mix(in srgb, var(--surface-soft) 72%, white 28%);
}

.contest-table tbody tr:nth-child(odd),
.contest-table tbody tr:nth-child(even) {
  background: transparent;
}
</style>
