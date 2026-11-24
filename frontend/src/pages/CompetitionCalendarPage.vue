<template>
  <section class="calendar-page">
    <section class="calendar-controls card">
      <div class="site-filter-toolbar">
        <div class="site-filter-grid" role="group" aria-label="比赛平台筛选">
          <button
            type="button"
            class="site-chip site-chip--all"
            :class="{ 'site-chip--active': allSitesSelected }"
            :aria-pressed="allSitesSelected"
            @click="selectAllSites"
          >
            <span class="site-chip-name">全部平台</span>
            <span class="site-chip-count tabular-nums">{{ totalContestCount }}</span>
          </button>
          <button
            v-for="item in sourceOptions"
            :key="item.key"
            type="button"
            class="site-chip"
            :class="{ 'site-chip--active': !allSitesSelected && isSiteSelected(item.key) }"
            :aria-pressed="!allSitesSelected && isSiteSelected(item.key)"
            @click="toggleSite(item.key)"
          >
            <span class="site-chip-name">{{ item.name }}</span>
            <span v-if="item.count" class="site-chip-count tabular-nums">{{ item.count }}</span>
          </button>
        </div>
        <div v-if="taxonomy.latest_sync_at" class="calendar-sync-meta meta tabular-nums">
          <span>最近同步：{{ formatDateTime(taxonomy.latest_sync_at) }}</span>
          <button type="button" class="btn btn-mini" :disabled="loadingRows" @click="refreshAll">
            {{ loadingRows ? "刷新中..." : "刷新" }}
          </button>
        </div>
      </div>
    </section>

    <SkeletonBlock
      v-if="loadingRows && !rows.length"
      :lines="6"
      :line-height="20"
      label="正在加载近期赛事日历"
    />

    <EmptyErrorState
      v-else-if="loadError && !rows.length"
      tone="error"
      title="比赛日历加载失败"
      :description="loadError"
      action-label="重新加载"
      :busy="loadingRows"
      @action="refreshAll"
    />

    <template v-else>
      <section v-if="ongoingRows.length" class="calendar-section card">
        <header class="section-head">
          <div>
            <h2 class="section-title">正在进行</h2>
            <p class="meta">按结束时间从近到远排序。</p>
          </div>
          <span class="pill tabular-nums">{{ ongoingRows.length }}</span>
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
                <td class="tabular-nums" data-label="开始时间 - 结束时间">{{ timeRange(item) }}</td>
                <td class="tabular-nums" data-label="持续时间">{{ duration(item) }}</td>
                <td data-label="跳转链接">
                  <a class="table-link" :href="resolveContestUrl(item)" target="_blank" rel="noopener noreferrer">前往比赛</a>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="calendar-section card" :class="{ 'is-loading': loadingRows }">
        <header class="section-head">
          <div>
            <h2 class="section-title">即将开始</h2>
            <p class="meta">按距离当前时间从近到远排序。</p>
          </div>
          <span class="pill tabular-nums">{{ upcomingRows.length }}</span>
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
                <td class="tabular-nums" data-label="开始时间 - 结束时间">{{ timeRange(item) }}</td>
                <td class="tabular-nums" data-label="持续时间">{{ duration(item) }}</td>
                <td data-label="跳转链接">
                  <a class="table-link" :href="resolveContestUrl(item)" target="_blank" rel="noopener noreferrer">前往比赛</a>
                </td>
              </tr>
              <tr v-if="!upcomingRows.length" class="empty-row">
                <td colspan="5">当前所选平台暂无即将开始的比赛。</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="calendar-section card" :class="{ 'is-loading': loadingRows }">
        <header class="section-head">
          <div>
            <h2 class="section-title">已经结束</h2>
            <p class="meta">按距离当前时间从近到远排序。</p>
          </div>
          <span class="pill tabular-nums">{{ finishedRows.length }}</span>
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
                <td class="tabular-nums" data-label="开始时间 - 结束时间">{{ timeRange(item) }}</td>
                <td class="tabular-nums" data-label="持续时间">{{ duration(item) }}</td>
                <td data-label="跳转链接">
                  <a class="table-link" :href="resolveContestUrl(item)" target="_blank" rel="noopener noreferrer">前往比赛</a>
                </td>
              </tr>
              <tr v-if="!finishedRows.length" class="empty-row">
                <td colspan="5">当前所选平台暂无已结束的近期比赛。</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import EmptyErrorState from "../components/EmptyErrorState.vue";
import SkeletonBlock from "../components/SkeletonBlock.vue";
import { useRequestControllers } from "../composables/useRequestControllers";
import api, { isRequestCanceled } from "../services/api";
import { useUiStore } from "../stores/ui";
import { extractApiError, formatDateTime, formatDurationZh } from "../utils/format";

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
const loadError = ref("");
const selectedSites = ref(defaultSources.map((item) => item.key));
const nowTick = ref(Date.now());
let ticker = null;
const requests = useRequestControllers();

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

async function fetchAll(path, params = {}, signal) {
  const merged = [];
  let page = 1;
  while (page) {
    const { data } = await api.get(path, { params: { ...params, page }, signal });
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

const allSitesSelected = computed(() => {
  const keys = sourceOptions.value.map((item) => item.key);
  return keys.length > 0 && keys.every((key) => selectedSites.value.includes(key));
});

const totalContestCount = computed(() =>
  Number(taxonomy.value?.count || rows.value.length || 0),
);

function duration(item) {
  const totalSeconds = Number(item?.duration_seconds || 0);
  if (totalSeconds > 0) {
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const parts = [];
    if (days) parts.push(`${days} 天`);
    if (hours) parts.push(`${hours} 小时`);
    if (minutes || !parts.length) parts.push(`${minutes} 分钟`);
    return parts.join(" ");
  }
  const byRange = formatDurationZh(item?.start_time, item?.end_time);
  if (byRange && byRange !== "-") return byRange;
  return item?.duration_label || "-";
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
  const allKeys = sourceOptions.value.map((item) => item.key);
  if (allSitesSelected.value) {
    selectedSites.value = [key];
    return;
  }
  if (selectedSites.value.includes(key)) {
    const next = selectedSites.value.filter((item) => item !== key);
    selectedSites.value = next.length ? next : allKeys;
    return;
  }
  const next = [...selectedSites.value, key];
  selectedSites.value = next.length >= allKeys.length ? allKeys : next;
}

function selectAllSites() {
  selectedSites.value = sourceOptions.value.map((item) => item.key);
}

async function loadTaxonomy() {
  const controller = requests.replace("taxonomy");
  loadingTaxonomy.value = true;
  try {
    const { data } = await api.get("/competition-calendar/taxonomy/", {
      signal: controller.signal,
    });
    if (!requests.isCurrent("taxonomy", controller)) return;
    taxonomy.value = {
      sources: Array.isArray(data?.sources) ? data.sources : defaultSources,
      count: Number(data?.count || 0),
      latest_sync_at: data?.latest_sync_at || "",
    };
  } catch (error) {
    if (isRequestCanceled(error) || !requests.isCurrent("taxonomy", controller)) return;
    taxonomy.value = {
      sources: defaultSources,
      count: 0,
      latest_sync_at: "",
    };
    ui.error(extractApiError(error, "读取比赛日历来源失败"));
  } finally {
    if (requests.release("taxonomy", controller)) {
      loadingTaxonomy.value = false;
    }
  }
}

async function loadRows() {
  const controller = requests.replace("rows");
  loadingRows.value = true;
  loadError.value = "";
  try {
    const nextRows = await fetchAll("/competition-calendar/", { order: "asc" }, controller.signal);
    if (!requests.isCurrent("rows", controller)) return;
    rows.value = nextRows;
  } catch (error) {
    if (isRequestCanceled(error) || !requests.isCurrent("rows", controller)) return;
    const msg = extractApiError(error, "读取比赛日历失败");
    loadError.value = msg;
    if (!rows.value.length) {
      ui.error(msg);
    }
  } finally {
    if (requests.release("rows", controller)) {
      loadingRows.value = false;
    }
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
  transition: opacity var(--dur-fast, 150ms) var(--ease-standard, ease);
}

.calendar-section.is-loading {
  opacity: 0.56;
  pointer-events: none;
}

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
}

.site-filter-toolbar {
  display: grid;
  gap: 10px;
}

.calendar-sync-meta {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 13px;
}

.site-filter-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.site-chip {
  border: 1px solid var(--button-border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-strong);
  padding: 12px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  transition:
    transform var(--dur-fast, 150ms) var(--ease-out, ease),
    border-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    background-color var(--dur-fast, 150ms) var(--ease-standard, ease);
}

@media (hover: hover) {
  .site-chip:hover {
    transform: translate3d(0, -1px, 0);
    border-color: color-mix(in srgb, var(--accent) 40%, var(--button-border));
  }
}

.site-chip:active {
  transform: scale(0.975);
  transition-duration: var(--dur-press, 90ms);
}

.site-chip--active {
  border-color: color-mix(in srgb, var(--accent) 62%, transparent);
  background: color-mix(in srgb, var(--accent) 18%, var(--surface-strong));
  color: var(--accent);
}

.site-chip--active:hover {
  background: color-mix(in srgb, var(--accent) 24%, var(--surface-strong));
  border-color: color-mix(in srgb, var(--accent) 78%, transparent);
}

.site-chip-name {
  font-weight: 800;
}

.site-chip-count {
  font-size: 12px;
  color: var(--text-quiet);
  font-weight: 700;
}

.site-chip--active .site-chip-count {
  color: var(--accent);
}

.table-shell {
  margin-top: 14px;
  overflow-x: auto;
  padding-top: 0;
}

.contest-table {
  width: 100%;
  border-collapse: collapse;
}

.contest-table th,
.contest-table td {
  border: 0;
  border-bottom: 1px solid color-mix(in srgb, var(--hairline-strong) 88%, transparent);
  padding: 10px 12px;
  vertical-align: top;
}

.contest-table th + th,
.contest-table td + td {
  border-left: 1px solid color-mix(in srgb, var(--hairline) 92%, transparent);
}

.contest-table thead th {
  background: var(--table-head-bg);
  text-align: left;
  font-size: 13px;
  letter-spacing: 0.04em;
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
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .section-head {
    flex-direction: column;
  }

  .calendar-sync-meta {
    justify-content: space-between;
  }

  .site-filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .site-chip--all {
    grid-column: 1 / -1;
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

  .contest-table td + td {
    border-left: 0;
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
</style>
