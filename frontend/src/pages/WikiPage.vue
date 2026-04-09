<template>
  <section class="wiki-layout">
    <aside class="wiki-toc">
      <div class="wiki-toc-section-head">
        <span>当前章节目录</span>
        <span class="toc-count">{{ chapterTocVisibleItems.length }}</span>
      </div>
      <div v-if="currentCategory || chapterTocVisibleItems.length" class="toc-chapter-list">
        <div class="toc-chapter-entry toc-chapter-entry--active">
          <div class="toc-chapter-row">
            <span class="toc-toggle toc-toggle--placeholder"></span>
            <div class="toc-link toc-link--active toc-link--static">
              {{ formatCategoryLabel(currentCategory?.name) || currentThemeName }}
            </div>
          </div>

          <div class="toc-children toc-children--current">
            <div
              v-for="node in chapterTocVisibleItems"
              :key="node.id"
              class="toc-sub-row"
              :class="tocLevelClass(node)"
              :style="{ '--toc-indent': `${node.depth * 18}px` }"
            >
              <button
                v-if="node.hasChildren"
                class="toc-toggle"
                type="button"
                @click.stop="toggleTocExpand(node.id)"
              >
                {{ node.isExpanded ? "▾" : "▸" }}
              </button>
              <span v-else class="toc-toggle toc-toggle--placeholder"></span>
              <button class="toc-sub-link" type="button" @click="handleTocNodeClick(node)">
                {{ node.text }}
              </button>
            </div>
            <p v-if="!chapterTocVisibleItems.length" class="meta">当前章节暂无子目录。</p>
          </div>
        </div>
      </div>
      <p v-else class="meta">当前章节暂无子目录。</p>
    </aside>

    <main class="wiki-main">
      <header class="wiki-head">
        <p class="head-line">{{ summaryLine }}</p>
      </header>

      <section v-if="auth.isSchoolOrHigher" class="publish-zone">
        <button class="collapse-btn" @click="showPublish = !showPublish">
          {{ showPublish ? "收起发布面板" : "展开快速发布" }}
        </button>
        <div v-if="showPublish" class="publish-panel">
          <div class="publish-row">
            <input class="input" v-model="createForm.title" placeholder="文章标题" />
            <select class="select" v-model="createForm.category">
              <option value="">选择分类</option>
              <option v-for="item in categories" :key="item.id" :value="item.id">{{ formatCategoryLabel(item.name) }}</option>
            </select>
          </div>
          <textarea class="textarea" v-model="createForm.summary" placeholder="摘要"></textarea>
          <textarea class="textarea" v-model="createForm.content_md" placeholder="Markdown 正文"></textarea>
          <button class="btn btn-accent" @click="createArticle">发布</button>
        </div>
      </section>

      <section class="chapter-view">
        <div
          v-for="item in chapterArticles"
          :key="item.id"
          class="chapter-article-block"
          :id="`chapter-article-${item.id}`"
        >
          <ArticlePage :id="item.id" :article-data="item" :embedded="true" @deleted="handleEmbeddedArticleDeleted" />
        </div>
        <p v-if="usingDemoArticles" class="chapter-demo-tip">
          当前展示的是开发环境演示正文，用于验收主题、表格和代码块样式。
        </p>
        <p v-if="!chapterArticles.length" class="meta">当前章节暂无可展示内容。</p>
      </section>
    </main>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import api from "../services/api";
import { DEMO_WIKI_CATEGORY, buildDemoWikiArticle } from "../content/demoContent";
import ArticlePage from "./ArticlePage.vue";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const ui = useUiStore();

const categories = ref([]);
const articles = ref([]);
const showPublish = ref(false);
const syncingRoute = ref(false);
const fallbackSummary = ref(null);
const schemaErrorShown = ref(false);
const fallbackNotices = reactive({
  categories: false,
  articles: false,
});

const filters = reactive({
  category: typeof route.query.category === "string" ? route.query.category : "",
});

const pagination = reactive({
  count: 0,
});

const createForm = reactive({
  title: "",
  category: "",
  summary: "",
  content_md: "",
});

function formatCategoryLabel(value) {
  return String(value || "")
    .replace(/^\s*\d+(?:\.\d+)*\s*[.．、]\s*/u, "")
    .trim();
}

const summaryLine = computed(() => {
  if (filters.category) {
    const activeCategory = currentCategory.value;
    if (activeCategory) {
      return `当前展示“${formatCategoryLabel(activeCategory.name)}”章节完整内容`;
    }
  }
  return "选择左侧章节后，右侧直接展示全文与互动功能";
});

const currentThemeName = computed(() => {
  if (currentCategory.value) return formatCategoryLabel(currentCategory.value.name);
  return "全部条目";
});

const usingDemoCategory = computed(() => Boolean(import.meta.env.DEV) && !categories.value.length);
const effectiveCategories = computed(() => (usingDemoCategory.value ? [DEMO_WIKI_CATEGORY] : categories.value));
const usingDemoArticles = computed(() => Boolean(import.meta.env.DEV) && !articles.value.length);
const currentCategory = computed(() => effectiveCategories.value.find((item) => isCategoryActive(item)) || null);

const chapterCategories = computed(() => {
  return effectiveCategories.value
    .filter((item) => item?.slug && !item.parent && item.is_visible !== false)
    .sort(sortCategories);
});

const chapterArticles = computed(() => {
  if (articles.value.length) {
    return [...articles.value].sort((left, right) => {
      const orderDelta = Number(left.display_order || 0) - Number(right.display_order || 0);
      if (orderDelta !== 0) return orderDelta;
      return Number(left.id || 0) - Number(right.id || 0);
    });
  }
  if (!usingDemoArticles.value) {
    return [];
  }
  return [buildDemoWikiArticle(currentCategory.value || DEMO_WIKI_CATEGORY)];
});
const chapterTocTree = computed(() => buildChapterTocTree(chapterArticles.value));
const chapterTocExpandedIds = ref(new Set());
const chapterTocVisibleItems = computed(() =>
  flattenVisibleChapterToc(chapterTocTree.value, chapterTocExpandedIds.value)
);

async function loadCategories() {
  try {
    const { data } = await api.get("/categories/");
    categories.value = data.results || data;
  } catch (error) {
    try {
      const summary = await loadSummaryFallback();
      categories.value = summary.categories || [];
      if (!fallbackNotices.categories) {
        ui.info("分类接口异常，已使用降级数据");
        fallbackNotices.categories = true;
      }
    } catch (fallbackError) {
      notifyLoadError(fallbackError, "分类加载失败，请确认后端服务已启动并执行 migrate");
    }
  }
}

function applyQueryToState() {
  filters.category = typeof route.query.category === "string" ? route.query.category : "";
}

function buildParams() {
  const params = {};
  if (filters.category) params.category = filters.category;
  return params;
}

async function loadArticles() {
  try {
    const params = buildParams();
    const items = [];
    let page = 1;
    let totalCount = 0;

    while (true) {
      const { data } = await api.get("/articles/", {
        params: {
          ...params,
          page,
          order: "display",
        },
      });
      const pageItems = data.results || data;
      items.push(...pageItems);
      totalCount = Number.isFinite(data?.count) ? data.count : items.length;

      if (!Array.isArray(data?.results) || !data?.next) break;
      const nextPage = Number(new URL(data.next, window.location.origin).searchParams.get("page") || "0");
      if (!nextPage || nextPage === page) break;
      page = nextPage;
    }

    articles.value = items;
    pagination.count = totalCount || items.length;
  } catch (error) {
    try {
      const summary = await loadSummaryFallback();
      const fallbackItems = filterFallbackArticles(summary.featured_articles || []);
      articles.value = fallbackItems;
      pagination.count = fallbackItems.length;
      if (!fallbackNotices.articles) {
        ui.info("条目接口异常，已使用降级数据");
        fallbackNotices.articles = true;
      }
    } catch (fallbackError) {
      notifyLoadError(fallbackError, "条目加载失败，请确认后端服务已启动并执行 migrate");
    }
  }
}

async function loadSummaryFallback() {
  if (fallbackSummary.value) return fallbackSummary.value;
  const { data } = await api.get("/home/summary/");
  fallbackSummary.value = data;
  return data;
}

function sortCategories(a, b) {
  const orderDelta = Number(a?.order || 0) - Number(b?.order || 0);
  if (orderDelta !== 0) return orderDelta;
  return String(a?.name || "").localeCompare(String(b?.name || ""), "zh-Hans-CN");
}

function stripInlineMarkdown(text) {
  return String(text || "")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "[图片]")
    .trim();
}

function parseArticleHeadingLines(contentMd) {
  const lines = String(contentMd || "").split(/\r?\n/);
  const items = [];
  let index = 0;
  for (const line of lines) {
    const match = line.match(/^(#{1,6})\s+(.+)$/);
    if (!match) continue;
    const level = match[1].length;
    if (level < 2) continue;
    const text = stripInlineMarkdown(match[2]);
    if (!text) continue;
    index += 1;
    items.push({ level, text, index });
  }
  return items;
}

function buildHeadingTree(items, articleId) {
  const root = { id: `a-${articleId}-root`, level: 1, text: "", anchorId: `chapter-article-${articleId}`, children: [] };
  const stack = [root];

  for (const item of items) {
    const node = {
      id: `a-${articleId}-h-${item.index}`,
      text: item.text,
      level: item.level,
      anchorId: `chapter-article-${articleId}`,
      children: [],
    };

    while (stack.length && stack[stack.length - 1].level >= node.level) {
      stack.pop();
    }

    const parent = stack[stack.length - 1] || root;
    parent.children.push(node);
    stack.push(node);
  }

  return root.children;
}

function buildChapterTocTree(chapterItems) {
  return chapterItems.map((item) => ({
    id: `article-${item.id}`,
    text: item.title,
    level: 1,
    anchorId: `chapter-article-${item.id}`,
    children: buildHeadingTree(parseArticleHeadingLines(item.content_md), item.id),
  }));
}

function findTocNodeById(nodes, targetId) {
  for (const node of nodes) {
    if (node.id === targetId) return node;
    if (node.children?.length) {
      const nested = findTocNodeById(node.children, targetId);
      if (nested) return nested;
    }
  }
  return null;
}

function collectDescendantIds(node, bucket = new Set()) {
  for (const child of node?.children || []) {
    bucket.add(child.id);
    if (child.children?.length) collectDescendantIds(child, bucket);
  }
  return bucket;
}

function flattenVisibleChapterToc(nodes, expandedIds, depth = 0, output = []) {
  for (const node of nodes) {
    const hasChildren = node.children.length > 0;
    const isExpanded = expandedIds.has(node.id);
    output.push({
      id: node.id,
      text: node.text,
      depth,
      hasChildren,
      isExpanded,
      anchorId: node.anchorId,
    });
    if (hasChildren && isExpanded) {
      flattenVisibleChapterToc(node.children, expandedIds, depth + 1, output);
    }
  }
  return output;
}

function buildDefaultExpandedIds(tree) {
  return new Set();
}

function isTocExpanded(id) {
  if (!id) return false;
  return chapterTocExpandedIds.value.has(id);
}

function toggleTocExpand(id) {
  if (!id) return;
  const next = new Set(chapterTocExpandedIds.value);
  if (next.has(id)) {
    next.delete(id);
    const node = findTocNodeById(chapterTocTree.value, id);
    if (node) {
      const descendants = collectDescendantIds(node);
      descendants.forEach((descendantId) => next.delete(descendantId));
    }
  } else {
    next.add(id);
  }
  chapterTocExpandedIds.value = next;
}

function handleTocNodeClick(node) {
  if (!node) return;
  if (node.hasChildren) {
    toggleTocExpand(node.id);
    return;
  }
  scrollToAnchor(node.anchorId);
}

function scrollToAnchor(anchorId) {
  if (!anchorId) return;
  const node = document.getElementById(anchorId);
  if (!node) return;
  node.scrollIntoView({ behavior: "smooth", block: "start" });
}

function tocLevelClass(node) {
  const depth = Number(node?.depth || 0);
  const level = Math.min(6, Math.max(1, depth + 1));
  return `toc-level-${level}`;
}

function isCategoryActive(item) {
  if (!filters.category) return false;
  return filters.category === String(item.id) || filters.category === item.slug;
}

function ensureDefaultCategory() {
  if (filters.category) return false;
  const firstChapter = chapterCategories.value[0];
  if (!firstChapter) return false;
  filters.category = firstChapter.slug || String(firstChapter.id);
  return true;
}

function filterFallbackArticles(source) {
  let items = [...source];
  if (filters.category) {
    let categoryId = null;
    if (/^\d+$/.test(filters.category)) {
      categoryId = Number(filters.category);
    } else {
      const matchedCategory = categories.value.find((item) => item.slug === filters.category);
      if (matchedCategory) categoryId = matchedCategory.id;
    }
    if (categoryId !== null) {
      items = items.filter((item) => Number(item.category) === categoryId);
    }
  }
  return items;
}

async function syncRoute() {
  syncingRoute.value = true;
  await router.replace({
    name: "wiki",
    query: {
      ...(filters.category ? { category: filters.category } : {}),
    },
  });
  syncingRoute.value = false;
}

async function createArticle() {
  if (!createForm.title || !createForm.category || !createForm.content_md) {
    ui.info("请填写标题、分类和正文");
    return;
  }

  try {
    await api.post("/articles/", {
      title: createForm.title,
      category: Number(createForm.category),
      summary: createForm.summary,
      content_md: createForm.content_md,
    });

    createForm.title = "";
    createForm.category = "";
    createForm.summary = "";
    createForm.content_md = "";
    showPublish.value = false;
    ui.success("条目发布成功");
    await loadArticles();
  } catch (error) {
    ui.error(getErrorText(error, "条目发布失败"));
  }
}

async function handleEmbeddedArticleDeleted() {
  await loadArticles();
}

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) {
    if (error?.message) return `${fallback}（${error.message}）`;
    return fallback;
  }
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload)) return payload.join("；");
  if (typeof payload === "object") {
    const parts = [];
    for (const [field, value] of Object.entries(payload)) {
      if (Array.isArray(value)) {
        parts.push(`${field}: ${value.join("，")}`);
      } else if (typeof value === "string") {
        parts.push(`${field}: ${value}`);
      }
    }
    if (parts.length) return parts.join("；");
  }
  return fallback;
}

function notifyLoadError(error, fallback) {
  const payload = error?.response?.data;
  const isSchemaOutdated = payload && typeof payload === "object" && payload.code === "schema_outdated";
  if (isSchemaOutdated) {
    if (schemaErrorShown.value) return;
    schemaErrorShown.value = true;
  }
  ui.error(getErrorText(error, fallback));
}

onMounted(async () => {
  await loadCategories();
  applyQueryToState();
  if (ensureDefaultCategory()) {
    await syncRoute();
  }
  await loadArticles();
});

watch(
  () => chapterTocTree.value,
  () => {
    chapterTocExpandedIds.value = buildDefaultExpandedIds(chapterTocTree.value);
  },
  { immediate: true }
);

watch(
  () => route.fullPath,
  async () => {
    if (syncingRoute.value) return;
    applyQueryToState();
    if (ensureDefaultCategory()) {
      await syncRoute();
    }
    await loadArticles();
  }
);

watch(
  () => currentCategory.value?.id,
  (value) => {
    if (!value) return;
    if (!createForm.category) {
      createForm.category = value;
    }
  },
  { immediate: true }
);
</script>

<style scoped>
.wiki-layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 32px;
}

.wiki-toc {
  align-self: start;
  position: sticky;
  top: 94px;
  border: 1px solid var(--hairline);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, color-mix(in srgb, var(--surface-strong) 82%, white 18%), var(--surface) 30%);
  padding: 18px 16px;
  box-shadow: var(--shadow-sm);
  display: grid;
  gap: 14px;
}

.wiki-toc-head {
  display: grid;
  gap: 6px;
}

.wiki-toc h3 {
  margin: 0;
  font-size: 22px;
}

.wiki-toc-kicker {
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.wiki-toc-desc {
  margin: 0;
  line-height: 1.6;
}

.wiki-toc-meta {
  display: grid;
  gap: 8px;
}

.wiki-toc-meta-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid color-mix(in srgb, var(--hairline) 86%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--surface-strong) 92%, transparent);
  padding: 9px 12px;
  font-size: 13px;
  color: var(--text-quiet);
}

.wiki-toc-meta-item strong {
  color: var(--text-strong);
  font-size: 14px;
  font-weight: 700;
}

.topic-name {
  color: var(--accent);
  font-weight: 600;
}

.wiki-toc-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: var(--text-quiet);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.toc-count {
  display: inline-flex;
  min-width: 28px;
  height: 28px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent) 12%, var(--surface-strong));
  color: var(--accent);
  font-size: 12px;
}

.wiki-head .head-line {
  margin: 8px 0 16px;
  color: var(--muted);
  font-size: 17px;
}

.publish-zone {
  margin-bottom: 14px;
}

.collapse-btn {
  border: 0;
  background: transparent;
  color: var(--accent);
  padding: 0;
  font-size: 15px;
}

.publish-panel {
  margin-top: 8px;
  border: 1px solid var(--hairline);
  border-radius: var(--radius-md);
  padding: 12px;
  background: var(--surface);
  box-shadow: var(--shadow-sm);
}

.publish-row {
  display: grid;
  grid-template-columns: 1fr 220px;
  gap: 10px;
  margin-bottom: 8px;
}

.publish-panel .textarea {
  margin-bottom: 8px;
}

.publish-panel :deep(.image-upload-helper) {
  margin-bottom: 6px;
}

.chapter-view {
  margin-top: 10px;
}

.chapter-article-block {
  margin-bottom: 14px;
}

.chapter-article-block:last-child {
  margin-bottom: 0;
}

.chapter-demo-tip {
  margin-top: 10px;
  border: 1px dashed color-mix(in srgb, var(--accent) 36%, transparent);
  border-radius: calc(var(--radius-sm) + 2px);
  background: color-mix(in srgb, var(--accent) 7%, var(--surface-soft));
  color: var(--text-soft);
  padding: 10px 12px;
}

.chapter-view :deep(.article-main) {
  border: 1px solid var(--hairline);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  background: var(--surface);
  box-shadow: var(--shadow-sm);
}

.toc-chapter-list {
  display: grid;
  gap: 8px;
  max-height: calc(100vh - 360px);
  overflow: auto;
  padding-right: 4px;
}

.toc-chapter-entry {
  border: 1px solid transparent;
  border-radius: 14px;
  background: color-mix(in srgb, var(--surface-strong) 90%, transparent);
  padding: 8px;
}

.toc-chapter-entry--active {
  border-color: color-mix(in srgb, var(--accent) 24%, transparent);
  background: color-mix(in srgb, var(--accent) 7%, var(--surface-strong));
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent) 10%, transparent);
}

.toc-chapter-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.toc-link {
  display: inline-flex;
  align-items: center;
  width: 100%;
  color: var(--text-strong);
  font-size: 14px;
  font-weight: 700;
  line-height: 1.4;
  padding: 8px 10px;
  border-radius: 10px;
  transition: background-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.toc-link:hover {
  background: color-mix(in srgb, var(--accent) 10%, transparent);
  color: var(--accent);
  transform: translateX(2px);
}

.toc-link--active {
  background: color-mix(in srgb, var(--accent) 11%, var(--surface-strong));
  color: var(--accent);
}

.toc-link--static {
  cursor: default;
  pointer-events: none;
}

.toc-children {
  margin-top: 6px;
  padding-top: 4px;
  border-top: 1px dashed color-mix(in srgb, var(--hairline) 88%, transparent);
}

.toc-children--current {
  margin-top: 8px;
}

.toc-sub-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 2px 0;
  padding-left: var(--toc-indent, 0);
}

.toc-sub-link {
  border: 0;
  background: transparent;
  color: var(--text-soft);
  font-size: 13px;
  text-align: left;
  width: 100%;
  padding: 6px 10px;
  cursor: pointer;
  line-height: 1.45;
  border-radius: 10px;
  transition: background-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.toc-sub-link:hover {
  background: color-mix(in srgb, var(--accent) 10%, transparent);
  color: var(--accent);
  transform: translateX(2px);
}

.toc-toggle {
  width: 22px;
  height: 22px;
  border: 1px solid transparent;
  border-radius: 7px;
  background: color-mix(in srgb, var(--surface-soft) 92%, transparent);
  color: var(--text-quiet);
  font-size: 13px;
  line-height: 1;
  padding: 0;
  cursor: pointer;
}

.toc-toggle:hover {
  border-color: color-mix(in srgb, var(--accent) 18%, transparent);
  background: color-mix(in srgb, var(--accent) 10%, var(--surface-strong));
}

.toc-toggle--placeholder {
  cursor: default;
  border-color: transparent;
  background: transparent;
}

.toc-level-1 .toc-sub-link {
  color: var(--text-strong);
  font-weight: 600;
}

.toc-level-2 .toc-sub-link {
  color: color-mix(in srgb, var(--accent) 82%, var(--text) 18%);
}

.toc-level-3 .toc-sub-link {
  color: color-mix(in srgb, var(--accent) 66%, var(--text) 34%);
}

.toc-level-4 .toc-sub-link {
  color: color-mix(in srgb, var(--accent) 52%, var(--text) 48%);
}

.toc-level-5 .toc-sub-link {
  color: color-mix(in srgb, var(--accent) 38%, var(--text) 62%);
}

.toc-level-6 .toc-sub-link {
  color: color-mix(in srgb, var(--accent) 24%, var(--text) 76%);
}

:global(html[data-theme="academic"]) .wiki-toc {
  background: var(--surface-strong);
  box-shadow: var(--card-shadow);
}

:global(html[data-theme="academic"]) .wiki-toc-meta-item,
:global(html[data-theme="academic"]) .toc-chapter-entry {
  background: color-mix(in srgb, var(--surface-strong) 95%, transparent);
}

:global(html[data-theme="academic"]) .toc-link,
:global(html[data-theme="academic"]) .toc-sub-link {
  font-family: var(--font-reading);
}

:global(html[data-theme="geek"]) .wiki-toc {
  border-width: 2px;
}

:global(html[data-theme="geek"]) .wiki-toc-meta-item,
:global(html[data-theme="geek"]) .toc-chapter-entry,
:global(html[data-theme="geek"]) .toc-toggle {
  border-width: 2px;
}

:global(html[data-theme="geek"]) .chapter-demo-tip {
  border-width: 2px;
}

:global(html[data-theme="geek"]) .wiki-toc h3,
:global(html[data-theme="geek"]) .wiki-toc-kicker,
:global(html[data-theme="geek"]) .toc-link {
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

@media (max-width: 1200px) {
  .wiki-layout {
    grid-template-columns: 1fr;
  }

  .wiki-toc {
    position: static;
    order: 2;
    gap: 12px;
  }
}

@media (max-width: 900px) {
  .wiki-layout {
    gap: 14px;
  }

  .wiki-toc {
    padding: 14px;
  }

  .toc-chapter-list {
    max-height: none;
  }

  .publish-row {
    grid-template-columns: 1fr;
  }

  .article-title {
    font-size: 22px;
  }

  .article-title-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .chapter-view :deep(.article-layout.embedded-mode) {
    border: 1px solid var(--hairline);
    border-radius: var(--radius-md);
    padding: 12px;
    background: var(--surface);
    box-shadow: var(--shadow-sm);
  }

  .chapter-view :deep(.article-layout.embedded-mode .article-main) {
    border: 0;
    border-radius: 0;
    padding: 0;
    background: transparent;
    box-shadow: none;
  }

  .chapter-view :deep(.article-layout.embedded-mode .side-panel--right) {
    border-top: 1px solid var(--hairline);
    padding-top: 12px;
  }
}

@media (max-width: 620px) {
  .chapter-view :deep(.article-layout.embedded-mode) {
    padding: 10px;
  }

  .chapter-view :deep(.article-layout.embedded-mode .side-panel--right) {
    padding-top: 10px;
  }
}

@media (max-width: 620px) {
  .wiki-head .head-line {
    font-size: 16px;
  }
}
.wiki-layout {
  gap: clamp(28px, 3vw, 46px);
  align-items: start;
}

.wiki-main {
  min-width: 0;
}

.wiki-toc,
:global(html[data-theme="academic"]) .wiki-toc,
:global(html[data-theme="geek"]) .wiki-toc {
  border: 0;
  border-right: 1px solid color-mix(in srgb, var(--hairline) 82%, transparent);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  padding: 8px 18px 0 0;
}

.wiki-toc-head {
  gap: 4px;
}

.wiki-toc-meta {
  gap: 6px;
  padding-bottom: 14px;
  border-bottom: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
}

.wiki-toc-meta-item,
.toc-chapter-entry,
.toc-chapter-entry--active,
:global(html[data-theme="academic"]) .wiki-toc-meta-item,
:global(html[data-theme="academic"]) .toc-chapter-entry,
:global(html[data-theme="geek"]) .wiki-toc-meta-item,
:global(html[data-theme="geek"]) .toc-chapter-entry {
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  padding: 0;
}

.wiki-toc-meta-item {
  justify-content: flex-start;
  gap: 10px;
}

.wiki-toc-meta-item strong {
  font-size: 13px;
}

.toc-chapter-list {
  gap: 2px;
  padding-right: 8px;
}

.toc-link {
  border-radius: 0 10px 10px 0;
  padding: 6px 8px;
}

.toc-link--active {
  background: color-mix(in srgb, var(--accent) 9%, transparent);
}

.toc-children {
  border-top: 0;
  margin-top: 4px;
  padding-top: 0;
}

.toc-sub-row {
  margin: 0;
}

.toc-sub-link {
  border-radius: 0 10px 10px 0;
  padding: 5px 8px;
}

.publish-zone {
  margin-bottom: 22px;
  padding-bottom: 18px;
  border-bottom: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
}

.publish-panel {
  margin-top: 12px;
  border: 0;
  border-top: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
  border-radius: 0;
  padding: 16px 0 0;
  background: transparent;
  box-shadow: none;
}

.chapter-view {
  margin-top: 0;
}

.chapter-article-block {
  margin-bottom: 0;
  padding: 28px 0;
  border-top: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
}

.chapter-article-block:first-child {
  padding-top: 0;
  border-top: 0;
}

.chapter-view :deep(.article-layout.embedded-mode) {
  gap: clamp(18px, 2vw, 28px);
}

.chapter-view :deep(.article-main) {
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  padding: 0;
}

.chapter-view :deep(.article-layout.embedded-mode .side-panel--right) {
  border-left: 1px solid color-mix(in srgb, var(--hairline) 82%, transparent);
  padding-left: 18px;
}

@media (max-width: 1200px) {
  .wiki-toc {
    border-right: 0;
    padding: 0;
  }
}

@media (max-width: 900px) {
  .publish-zone {
    margin-bottom: 16px;
    padding-bottom: 14px;
  }

  .wiki-toc {
    padding: 0;
  }

  .chapter-view :deep(.article-layout.embedded-mode),
  .chapter-view :deep(.article-layout.embedded-mode .article-main) {
    border: 0;
    border-radius: 0;
    background: transparent;
    box-shadow: none;
    padding: 0;
  }

  .chapter-view :deep(.article-layout.embedded-mode .side-panel--right) {
    border-top: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
    border-left: 0;
    padding-left: 0;
    padding-top: 14px;
  }
}
</style>
