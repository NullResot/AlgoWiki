<template>
  <section class="search-page">
    <header class="search-head">
      <div>
        <p class="search-kicker">GLOBAL SEARCH</p>
        <h1>全站搜索</h1>
        <p class="search-subtitle">
          搜索竞赛 Wiki、Trick、赛事、文档与动态<span v-if="auth.isManager">；管理员可同时检索管理内容</span>。
        </p>
      </div>
      <form class="search-form" role="search" @submit.prevent="submitSearch">
        <div class="search-input-wrap">
          <input
            ref="searchInputRef"
            v-model="searchInput"
            class="input search-input"
            type="text"
            enterkeyhint="search"
            autocomplete="off"
            placeholder="输入关键词、标题或内容 ID"
            aria-label="全站搜索关键词"
          />
          <button
            v-if="searchInput"
            type="button"
            class="search-clear-btn"
            aria-label="清空搜索词"
            @click="clearSearchInput"
          >
            ×
          </button>
        </div>
        <button
          class="btn btn-accent"
          type="submit"
          :disabled="loading || !normalizeQuery(searchInput)"
        >
          {{ loading ? "搜索中..." : "搜索" }}
        </button>
      </form>
    </header>

    <section v-if="query" class="search-state" aria-live="polite">
      <span v-if="loading && !groupsWithHits.length">正在搜索“{{ query }}”...</span>
      <span v-else-if="loading">正在更新“{{ query }}”的搜索结果...</span>
      <span v-else-if="errorMessage">{{ errorMessage }}</span>
      <span v-else>{{ resultSummary }}</span>
    </section>

    <nav
      v-if="scopeTabs.length > 1"
      class="scope-tabs"
      role="tablist"
      aria-label="搜索结果分类"
    >
      <button
        v-for="tab in scopeTabs"
        :key="tab.key"
        type="button"
        role="tab"
        class="scope-tab"
        :class="{ 'scope-tab--active': activeScope === tab.key }"
        :aria-selected="activeScope === tab.key"
        @click="selectScope(tab.key)"
      >
        <span>{{ tab.label }}</span>
        <strong class="tabular-nums">{{ tab.count }}</strong>
      </button>
    </nav>

    <section v-if="!query" class="empty-panel">
      <h2>输入关键词后开始搜索</h2>
      <p>可以输入文章标题、动态 ID、赛事名称或 Trick 关键词。</p>
    </section>

    <SkeletonBlock
      v-else-if="loading && !groupsWithHits.length"
      :lines="5"
      :line-height="18"
      label="正在检索全站内容"
    />

    <EmptyErrorState
      v-else-if="errorMessage && !loading"
      tone="error"
      title="搜索服务暂时不可用"
      :description="errorMessage"
      action-label="重新搜索"
      :busy="loading"
      @action="loadSearch"
    />

    <EmptyErrorState
      v-else-if="!loading && !errorMessage && !groupsWithHits.length"
      title="没有找到匹配结果"
      description="可以换一个更短的关键词，或使用内容 ID 直接检索。"
    />

    <section v-else class="search-results" :class="{ 'is-loading': loading }">
      <article v-for="group in visibleGroups" :key="group.key" class="result-group">
        <header class="result-group-head">
          <div>
            <h2>{{ group.label }}</h2>
            <p class="tabular-nums">
              {{ group.count_is_lower_bound ? `至少 ${group.count}` : `共 ${group.count}` }}
              条结果，当前显示前 {{ group.results.length }} 条。
            </p>
          </div>
        </header>

        <RouterLink
          v-for="item in group.results"
          :key="`${group.key}-${item.type}-${item.id}`"
          class="result-row"
          :to="item.url || '/'"
        >
          <div class="result-main">
            <div class="result-title-line">
              <span class="result-type">{{ item.type_label || item.type }}</span>
              <strong>
                <template
                  v-for="(seg, idx) in highlightSegments(item.title, query)"
                  :key="idx"
                >
                  <mark v-if="seg.match" class="search-mark">{{ seg.text }}</mark>
                  <template v-else>{{ seg.text }}</template>
                </template>
              </strong>
              <span class="result-id tabular-nums">#{{ item.id }}</span>
            </div>
            <p v-if="item.summary" class="result-summary">
              <template
                v-for="(seg, idx) in highlightSegments(item.summary, query)"
                :key="idx"
              >
                <mark v-if="seg.match" class="search-mark">{{ seg.text }}</mark>
                <template v-else>{{ seg.text }}</template>
              </template>
            </p>
            <div class="result-meta-line">
              <span v-if="item.location_label">位置：{{ item.location_label }}</span>
              <span v-if="item.author?.username">作者：{{ item.author.username }}</span>
              <span v-if="item.status_label">{{ item.status_label }}</span>
              <span v-if="formatDate(item.updated_at || item.created_at)">
                {{ formatDate(item.updated_at || item.created_at) }}
              </span>
              <span
                v-for="meta in displayMeta(item)"
                :key="`${item.type}-${item.id}-${meta.label}`"
              >
                {{ meta.label }}：{{ meta.value }}
              </span>
            </div>
          </div>
          <span class="result-arrow" aria-hidden="true">›</span>
        </RouterLink>

        <div v-if="hasMoreInGroup(group)" class="result-group-more">
          <button
            type="button"
            class="btn btn-sm"
            :disabled="Boolean(loadingMoreGroup)"
            @click="loadMoreForGroup(group)"
          >
            {{ loadingMoreGroup === group.key ? "正在加载更多..." : "查看更多结果" }}
          </button>
        </div>
      </article>
    </section>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import EmptyErrorState from "../components/EmptyErrorState.vue";
import SkeletonBlock from "../components/SkeletonBlock.vue";
import { useRequestControllers } from "../composables/useRequestControllers";
import api, { isRequestCanceled } from "../services/api";
import { useAuthStore } from "../stores/auth";
import { formatDate } from "../utils/format";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const requests = useRequestControllers();

const searchInputRef = ref(null);
const searchInput = ref("");
const query = ref("");
const groups = ref([]);
const loading = ref(false);
const errorMessage = ref("");
const activeScope = ref("all");
const loadingMoreGroup = ref("");
const currentLimit = ref(8);
const exhaustedGroups = reactive({});

const groupsWithHits = computed(() =>
  groups.value.filter((group) => Number(group.count || 0) > 0 || group.results?.length),
);

const visibleGroups = computed(() => {
  if (activeScope.value === "all") {
    return groupsWithHits.value;
  }
  return groupsWithHits.value.filter((group) => group.key === activeScope.value);
});

const scopeTabs = computed(() => {
  if (!groupsWithHits.value.length) return [];
  return [
    {
      key: "all",
      label: "全部",
      count: groupsWithHits.value.reduce((sum, group) => sum + Number(group.count || 0), 0),
    },
    ...groupsWithHits.value.map((group) => ({
      key: group.key,
      label: group.label,
      count: Number(group.count || 0),
    })),
  ];
});

const resultSummary = computed(() => {
  const total = scopeTabs.value.find((item) => item.key === "all")?.count || 0;
  if (!total) return `没有找到“${query.value}”的匹配结果。`;
  return `找到 ${total} 条与“${query.value}”相关的结果。`;
});

function normalizeQuery(value) {
  return String(value || "").trim();
}

function escapeRegExp(value) {
  return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlightSegments(text, keyword) {
  const raw = String(text || "");
  const needle = normalizeQuery(keyword);
  if (!raw || !needle || needle.length > 48) {
    return [{ text: raw, match: false }];
  }
  const tokens = needle.split(/\s+/).filter(Boolean).slice(0, 4);
  if (!tokens.length) return [{ text: raw, match: false }];
  const pattern = new RegExp(`(${tokens.map(escapeRegExp).join("|")})`, "ig");
  const parts = raw.split(pattern);
  const tokenSet = new Set(tokens.map((t) => t.toLowerCase()));
  return parts
    .filter((part) => part.length > 0)
    .map((part) => ({
      text: part,
      match: tokenSet.has(part.toLowerCase()),
    }));
}

async function clearSearchInput() {
  searchInput.value = "";
  await nextTick();
  searchInputRef.value?.focus();
}

async function submitSearch() {
  const nextQuery = normalizeQuery(searchInput.value);
  if (!nextQuery) return;
  await router.push({ name: "search", query: { q: nextQuery } });
}

async function selectScope(key) {
  if (activeScope.value === key) return;
  activeScope.value = key;
  if (!query.value) return;
  await router.replace({
    name: "search",
    query: {
      q: query.value,
      ...(key !== "all" ? { scope: key } : {}),
    },
  });
}

function hasMoreInGroup(group) {
  if (!group || exhaustedGroups[group.key]) return false;
  const shown = Array.isArray(group.results) ? group.results.length : 0;
  const total = Number(group.count || 0);
  if (group.count_is_lower_bound) return shown >= currentLimit.value;
  return total > shown;
}

async function loadMoreForGroup(group) {
  if (!group || !query.value || loadingMoreGroup.value) return;
  const prevLen = group.results?.length || 0;
  const nextLimit = Math.min(50, Math.max(prevLen + 10, currentLimit.value + 10));
  loadingMoreGroup.value = group.key;
  const controller = requests.replace("search-more");
  try {
    const { data } = await api.get("/search/", {
      params: { q: query.value, limit: nextLimit },
      signal: controller.signal,
    });
    if (!requests.isCurrent("search-more", controller)) return;
    currentLimit.value = nextLimit;
    const nextGroups = Array.isArray(data?.groups) ? data.groups : [];
    const updatedGroup = nextGroups.find((item) => item.key === group.key);
    if (!updatedGroup || (updatedGroup.results?.length || 0) <= prevLen) {
      exhaustedGroups[group.key] = true;
    }
    groups.value = nextGroups;
  } catch (error) {
    if (!isRequestCanceled(error)) {
      exhaustedGroups[group.key] = true;
    }
  } finally {
    if (requests.release("search-more", controller)) {
      loadingMoreGroup.value = "";
    }
  }
}

async function loadSearch() {
  const nextQuery = normalizeQuery(route.query.q);
  query.value = nextQuery;
  searchInput.value = nextQuery;
  errorMessage.value = "";
  currentLimit.value = 8;
  Object.keys(exhaustedGroups).forEach((key) => delete exhaustedGroups[key]);

  if (!nextQuery) {
    requests.cancel("search");
    groups.value = [];
    activeScope.value = "all";
    loading.value = false;
    return;
  }

  const controller = requests.replace("search");
  loading.value = true;
  try {
    const { data } = await api.get("/search/", {
      params: { q: nextQuery, limit: 8 },
      signal: controller.signal,
    });
    if (!requests.isCurrent("search", controller)) return;
    groups.value = Array.isArray(data?.groups) ? data.groups : [];
    const routeScope = typeof route.query.scope === "string" ? route.query.scope : "all";
    const matched = groups.value.some((g) => g.key === routeScope && (Number(g.count || 0) > 0 || g.results?.length));
    activeScope.value = matched ? routeScope : "all";
  } catch (error) {
    if (isRequestCanceled(error) || !requests.isCurrent("search", controller)) return;
    groups.value = [];
    errorMessage.value = "搜索暂时不可用，请稍后重试。";
  } finally {
    if (requests.release("search", controller)) {
      loading.value = false;
    }
  }
}

function formatMetaValue(value) {
  if (Array.isArray(value)) {
    return value.filter(Boolean).join("、");
  }
  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }
  if (value === null || value === undefined || value === "") {
    return "";
  }
  if (typeof value === "object") {
    return "";
  }
  return String(value);
}

function metaLabel(key) {
  const labels = {
    category: "分类",
    views: "阅读",
    keywords: "关键词",
    terms: "标签",
    series: "系列",
    year: "年份",
    stage: "阶段",
    event_date: "日期",
    start_time: "开始时间",
    source: "来源",
    role: "角色",
    is_banned: "封禁",
    phone: "手机号",
    featured: "精选",
    likes: "点赞",
    comments: "评论",
    priority: "优先级",
    slug: "标识",
    target_type: "对象",
    target_id: "对象 ID",
    deleted_by: "删除人",
  };
  return labels[key] || key;
}

function displayMeta(item) {
  const meta = item?.meta && typeof item.meta === "object" ? item.meta : {};
  return Object.entries(meta)
    .map(([key, value]) => ({
      label: metaLabel(key),
      value: formatMetaValue(value),
    }))
    .filter((entry) => entry.value)
    .slice(0, 4);
}

onMounted(() => {
  if (!normalizeQuery(route.query.q)) {
    nextTick(() => searchInputRef.value?.focus());
  }
});

watch(
  () => route.query.q,
  () => {
    loadSearch();
  },
  { immediate: true },
);
</script>

<style scoped>
.search-page {
  width: min(1120px, calc(100vw - 32px));
  margin: 0 auto;
  padding: clamp(28px, 4vw, 56px) 0 72px;
  display: grid;
  gap: 22px;
}

.search-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 460px);
  align-items: end;
  gap: 24px;
}

.search-kicker {
  margin: 0 0 8px;
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.search-head h1 {
  margin: 0;
  color: var(--text-strong);
  font-family: var(--font-display);
  font-size: clamp(34px, 5vw, 56px);
  line-height: 1;
}

.search-subtitle {
  max-width: 680px;
  margin: 12px 0 0;
  color: var(--text-soft);
  font-size: 15px;
  line-height: 1.8;
}

.search-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
}

.search-input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.search-input {
  width: 100%;
  padding-right: 36px;
}

.search-clear-btn {
  position: absolute;
  right: 8px;
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 999px;
  background: color-mix(in srgb, var(--text-quiet) 14%, transparent);
  color: var(--text-soft);
  font-size: 16px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition:
    background-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    color var(--dur-fast, 150ms) var(--ease-standard, ease),
    transform var(--dur-press, 90ms) var(--ease-out, ease);
}

.search-clear-btn:hover {
  background: color-mix(in srgb, var(--text-quiet) 24%, transparent);
  color: var(--text-strong);
}

.search-clear-btn:active {
  transform: scale(0.92);
}

.search-state {
  color: var(--text-soft);
  font-size: 14px;
}

.scope-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.scope-tab {
  border: 1px solid var(--hairline);
  border-radius: 999px;
  background: var(--surface-soft);
  color: var(--text-soft);
  padding: 8px 12px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  cursor: pointer;
  transition:
    border-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    background-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    color var(--dur-fast, 150ms) var(--ease-standard, ease),
    transform var(--dur-press, 90ms) var(--ease-out, ease);
}

.scope-tab:hover {
  border-color: color-mix(in srgb, var(--accent) 26%, var(--hairline));
  color: var(--text-strong);
}

.scope-tab:active {
  transform: scale(0.97);
}

.scope-tab strong {
  color: var(--text-strong);
  font-size: 12px;
}

.scope-tab--active {
  color: var(--accent);
  border-color: color-mix(in srgb, var(--accent) 36%, var(--hairline));
  background: color-mix(in srgb, var(--accent) 10%, var(--surface-strong));
}

.scope-tab--active strong {
  color: var(--accent);
}

.empty-panel {
  border: 1px dashed var(--hairline-strong);
  border-radius: 16px;
  padding: 28px;
  background: color-mix(in srgb, var(--surface-soft) 82%, transparent);
}

.empty-panel h2 {
  margin: 0 0 8px;
  color: var(--text-strong);
  font-size: 20px;
}

.empty-panel p {
  margin: 0;
  color: var(--text-soft);
  line-height: 1.7;
}

.search-results {
  display: grid;
  gap: 28px;
  transition: opacity var(--dur-fast, 150ms) var(--ease-standard, ease);
}

.search-results.is-loading {
  opacity: 0.56;
  pointer-events: none;
}

.search-mark {
  background: color-mix(in srgb, var(--accent) 18%, transparent);
  color: var(--accent);
  border-radius: 4px;
  padding: 0 3px;
  font-weight: 700;
}

.result-group-more {
  display: flex;
  justify-content: flex-start;
  padding-top: 4px;
}

.result-group {
  display: grid;
  gap: 10px;
}

.result-group-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--hairline);
}

.result-group-head h2 {
  margin: 0;
  color: var(--text-strong);
  font-size: 21px;
}

.result-group-head p {
  margin: 5px 0 0;
  color: var(--text-quiet);
  font-size: 13px;
}

.result-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  align-items: center;
  border: 1px solid var(--hairline);
  border-radius: 14px;
  padding: 15px 16px;
  background: var(--surface-strong);
  color: inherit;
  text-decoration: none;
  transition:
    border-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    transform var(--dur-fast, 150ms) var(--ease-out, ease),
    box-shadow var(--dur-fast, 150ms) var(--ease-standard, ease);
}

@media (hover: hover) {
  .result-row:hover {
    transform: translate3d(0, -1px, 0);
    border-color: color-mix(in srgb, var(--accent) 28%, var(--hairline));
    box-shadow: var(--shadow-sm);
  }

  .result-row:hover .result-arrow {
    transform: translate3d(3px, 0, 0);
  }
}

.result-main {
  min-width: 0;
  display: grid;
  gap: 7px;
}

.result-title-line {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.result-title-line strong {
  color: var(--text-strong);
  font-size: 16px;
  line-height: 1.5;
}

.result-type {
  border-radius: 999px;
  background: var(--pill-bg);
  color: var(--pill-text);
  font-size: 12px;
  font-weight: 700;
  padding: 4px 8px;
}

.result-id {
  color: var(--text-quiet);
  font-size: 12px;
}

.result-summary {
  margin: 0;
  color: var(--text-soft);
  font-size: 14px;
  line-height: 1.7;
}

.result-meta-line {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  color: var(--text-quiet);
  font-size: 12px;
}

.result-arrow {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  display: inline-grid;
  place-items: center;
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 10%, transparent);
  font-size: 22px;
  line-height: 1;
  transition: transform var(--dur-fast, 150ms) var(--ease-out, ease);
}

@media (max-width: 860px) {
  .search-page {
    width: min(100%, calc(100vw - 24px));
    padding-top: 24px;
  }

  .search-head {
    grid-template-columns: 1fr;
    align-items: start;
  }

  .search-form {
    grid-template-columns: 1fr;
  }

  .result-row {
    grid-template-columns: 1fr;
  }

  .result-arrow {
    display: none;
  }
}
</style>
