<template>
  <section class="wiki-layout">
    <aside class="wiki-toc">
      <h3>分类目录</h3>
      <p class="meta">专题：<span class="topic-name">【打破信息差】</span></p>
      <p class="meta">当前主题：{{ currentThemeName }}</p>
      <p class="meta">结果总数：{{ pagination.count }}</p>
      <div class="toc-chapter-list">
        <div v-for="item in chapterCategories" :key="item.slug || item.id" class="toc-chapter-entry">
          <div class="toc-chapter-row">
            <button
              v-if="isCategoryActive(item) && chapterTocVisibleItems.length"
              class="toc-toggle"
              type="button"
              @click.stop="toggleTocExpand(activeCategoryNodeId)"
            >
              {{ isTocExpanded(activeCategoryNodeId) ? "▾" : "▸" }}
            </button>
            <span v-else class="toc-toggle toc-toggle--placeholder"></span>
            <RouterLink
              class="toc-link"
              :class="{ 'toc-link--active': isCategoryActive(item) }"
              :to="{ name: 'wiki', query: { category: item.slug || String(item.id) } }"
            >
              {{ item.name }}
            </RouterLink>
          </div>

          <div
            v-if="isCategoryActive(item) && isTocExpanded(activeCategoryNodeId)"
            class="toc-children"
          >
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
          </div>
        </div>
      </div>
      <p v-if="!chapterCategories.length" class="meta">暂无章节目录。</p>
    </aside>

    <main class="wiki-main">
      <header class="wiki-head">
        <p class="head-line">{{ summaryLine }}</p>
      </header>

      <div class="toolbar">
        <input
          class="input"
          v-model="filters.search"
          placeholder="搜索标题或摘要"
          @keyup.enter="applyFilters"
        />
        <button class="btn btn-accent" @click="applyFilters">搜索</button>
        <button
          class="btn"
          :disabled="!chapterArticles.length || exportingChapterPdf"
          @click="exportCurrentViewPdf"
        >
          {{ exportingChapterPdf ? "准备中..." : "导出 PDF" }}
        </button>
        <button
          class="btn"
          :disabled="!chapterArticles.length || exportingChapterMarkdownBundle"
          @click="exportCurrentViewMarkdownBundle"
        >
          {{ exportingChapterMarkdownBundle ? "导出中..." : "导出 Markdown 包" }}
        </button>
      </div>

      <section v-if="auth.isSchoolOrHigher" class="publish-zone">
        <button class="collapse-btn" @click="showPublish = !showPublish">
          {{ showPublish ? "收起发布面板" : "展开快速发布" }}
        </button>
        <div v-if="showPublish" class="publish-panel">
          <div class="publish-row">
            <input class="input" v-model="createForm.title" placeholder="文章标题" />
            <select class="select" v-model="createForm.category">
              <option value="">选择分类</option>
              <option v-for="item in categories" :key="item.id" :value="item.id">{{ item.name }}</option>
            </select>
          </div>
          <textarea class="textarea" v-model="createForm.summary" placeholder="摘要"></textarea>
          <ImageUploadHelper label="上传图片并插入 Markdown" @uploaded="onCreateImageUploaded" />
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
          <ArticlePage :id="item.id" :embedded="true" @deleted="handleEmbeddedArticleDeleted" />
        </div>
        <p v-if="!chapterArticles.length" class="meta">当前章节暂无可展示内容。</p>
      </section>
    </main>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import api from "../services/api";
import ImageUploadHelper from "../components/ImageUploadHelper.vue";
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
const exportingChapterPdf = ref(false);
const exportingChapterMarkdownBundle = ref(false);
const fallbackNotices = reactive({
  categories: false,
  articles: false,
});

const filters = reactive({
  search: typeof route.query.search === "string" ? route.query.search : "",
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

function appendMarkdown(target, snippet) {
  const next = String(snippet || "").trim();
  if (!next) return String(target || "");
  const base = String(target || "");
  return base ? `${base}\n\n${next}\n` : `${next}\n`;
}

function onCreateImageUploaded(payload) {
  createForm.content_md = appendMarkdown(createForm.content_md, payload?.markdown);
}

const summaryLine = computed(() => {
  if (filters.category) {
    const activeCategory = currentCategory.value;
    if (activeCategory) {
      return `当前展示“${activeCategory.name}”章节完整内容`;
    }
  }
  if (filters.search) {
    return `按关键词“${filters.search}”定位章节并展示正文`;
  }
  return "选择左侧章节后，右侧直接展示全文与互动功能";
});

const currentThemeName = computed(() => {
  if (currentCategory.value) return currentCategory.value.name;
  return filters.search ? "搜索结果" : "全部条目";
});

const currentCategory = computed(() => categories.value.find((item) => isCategoryActive(item)) || null);

const chapterCategories = computed(() => {
  const topVisible = categories.value
    .filter((item) => item?.slug && !item.parent && item.is_visible !== false)
    .sort(sortCategories);
  const xcpcChapters = topVisible.filter((item) => String(item.slug).startsWith("xcpc-"));
  return xcpcChapters.length ? xcpcChapters : topVisible;
});

const chapterArticles = computed(() => [...articles.value]);
const activeCategoryNodeId = computed(() => {
  const id = currentCategory.value?.id;
  if (id == null) return "";
  return `chapter-${id}`;
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
  filters.search = typeof route.query.search === "string" ? route.query.search : "";
  filters.category = typeof route.query.category === "string" ? route.query.category : "";
}

function buildParams() {
  const params = {};
  if (filters.search) params.search = filters.search;
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

function splitSearchTokens(text) {
  return String(text || "")
    .split(/[\s\u3000\.,，。:：/\\-]+/g)
    .map((item) => item.trim())
    .filter(Boolean);
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
  const expanded = new Set();
  const activeId = activeCategoryNodeId.value;
  if (activeId) expanded.add(activeId);
  return expanded;
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
  if (filters.search || filters.category) return false;
  const firstChapter = chapterCategories.value[0];
  if (!firstChapter) return false;
  filters.category = firstChapter.slug || String(firstChapter.id);
  return true;
}

function filterFallbackArticles(source) {
  let items = [...source];
  const tokens = splitSearchTokens(filters.search);
  if (tokens.length) {
    items = items.filter((item) => {
      const haystack = `${item.title || ""}\n${item.summary || ""}`.toLowerCase();
      return tokens.every((token) => haystack.includes(token.toLowerCase()));
    });
  }
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
      ...(filters.search ? { search: filters.search } : {}),
      ...(filters.category ? { category: filters.category } : {}),
    },
  });
  syncingRoute.value = false;
}

async function applyFilters() {
  await syncRoute();
  await loadArticles();
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

function sanitizeExportName(value, fallback = "wiki-export") {
  const cleaned = String(value || "")
    .replace(/[\\/:*?"<>|]+/g, "_")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 80);
  return cleaned || fallback;
}

function downloadBlob(response, fallbackFilename) {
  const contentType = response?.headers?.["content-type"] || "application/octet-stream";
  const disposition = response?.headers?.["content-disposition"] || "";
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  const asciiMatch = disposition.match(/filename=\"?([^\";]+)\"?/i);
  const filenameRaw = utf8Match?.[1] || asciiMatch?.[1] || fallbackFilename;
  const filename = decodeURIComponent(filenameRaw).trim() || fallbackFilename;

  const blob = new Blob([response.data], { type: contentType });
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

async function exportCurrentViewPdf() {
  if (!chapterArticles.value.length || exportingChapterPdf.value) return;
  exportingChapterPdf.value = true;
  try {
    const response = await api.get("/articles/export-collection-pdf/", {
      params: buildParams(),
      responseType: "arraybuffer",
    });
    downloadBlob(response, `${sanitizeExportName(currentThemeName.value, "wiki-export")}.pdf`);
    ui.success("PDF 导出完成");
  } catch (error) {
    ui.error(getErrorText(error, "导出 PDF 失败"));
  } finally {
    exportingChapterPdf.value = false;
  }
}

async function exportCurrentViewMarkdownBundle() {
  if (!chapterArticles.value.length || exportingChapterMarkdownBundle.value) return;
  exportingChapterMarkdownBundle.value = true;
  try {
    const response = await api.get("/articles/export-collection-markdown-bundle/", {
      params: buildParams(),
      responseType: "arraybuffer",
    });
    downloadBlob(response, `${sanitizeExportName(currentThemeName.value, "wiki-export")}.zip`);
    ui.success("Markdown 包导出完成");
  } catch (error) {
    ui.error(getErrorText(error, "导出 Markdown 包失败"));
  } finally {
    exportingChapterMarkdownBundle.value = false;
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
  () => [activeCategoryNodeId.value, chapterTocTree.value],
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
</script>

<style scoped>
.wiki-layout {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 32px;
}

.wiki-toc {
  align-self: start;
  position: sticky;
  top: 94px;
}

.wiki-toc h3 {
  margin-bottom: 10px;
  font-size: 22px;
}

.topic-name {
  color: var(--accent);
  font-weight: 600;
}

.wiki-head .head-line {
  margin: 8px 0 16px;
  color: var(--muted);
  font-size: 17px;
}

.toolbar {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) auto auto auto;
  gap: 10px;
  margin-bottom: 12px;
  align-items: center;
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
  border-radius: 12px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.55);
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

.chapter-view :deep(.article-main) {
  border: 1px solid var(--hairline);
  border-radius: 14px;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.52);
  box-shadow: var(--shadow-sm);
}

.toc-chapter-list {
  margin-top: 8px;
}

.toc-chapter-entry {
  margin-bottom: 6px;
}

.toc-chapter-row {
  display: flex;
  align-items: center;
  gap: 2px;
}

.toc-link {
  display: inline-block;
  color: var(--accent);
  font-size: 15px;
}

.toc-link--active {
  font-weight: 700;
  text-decoration: underline;
}

.toc-children {
  margin-top: 4px;
}

.toc-sub-row {
  display: flex;
  align-items: center;
  gap: 2px;
  margin: 4px 0;
  padding-left: var(--toc-indent, 0);
}

.toc-sub-link {
  border: 0;
  background: transparent;
  color: #384356;
  font-size: 14px;
  text-align: left;
  padding: 0;
  cursor: pointer;
  line-height: 1.45;
}

.toc-sub-link:hover {
  color: var(--accent);
}

.toc-toggle {
  width: 18px;
  height: 18px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: #6b7789;
  font-size: 13px;
  line-height: 1;
  padding: 0;
  cursor: pointer;
}

.toc-toggle:hover {
  background: rgba(140, 156, 180, 0.15);
}

.toc-toggle--placeholder {
  cursor: default;
}

.toc-level-1 .toc-sub-link {
  color: #1f2a44;
  font-weight: 600;
}

.toc-level-2 .toc-sub-link {
  color: #2b4ea2;
}

.toc-level-3 .toc-sub-link {
  color: #2b6b9d;
}

.toc-level-4 .toc-sub-link {
  color: #415f8d;
}

.toc-level-5 .toc-sub-link {
  color: #5a4f8d;
}

.toc-level-6 .toc-sub-link {
  color: #7b4f8d;
}

@media (max-width: 1200px) {
  .wiki-layout {
    grid-template-columns: 1fr;
  }

  .wiki-toc {
    position: static;
    order: 2;
  }
}

@media (max-width: 900px) {
  .wiki-layout {
    gap: 14px;
  }

  .toolbar {
    grid-template-columns: 1fr 1fr;
  }

  .toolbar .input {
    grid-column: 1 / -1;
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
}

@media (max-width: 620px) {
  .toolbar {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 620px) {
  .wiki-head .head-line {
    font-size: 16px;
  }
}
</style>
