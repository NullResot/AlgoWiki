<template>
  <section class="wiki-layout">
    <aside class="wiki-toc">
      <section class="wiki-toc-block">
        <div class="wiki-toc-section-head wiki-toc-section-head--primary">
          <span class="wiki-toc-title-wrap">
            <span class="wiki-toc-title-icon" aria-hidden="true"></span>
            <span>当前章节目录</span>
          </span>
          <span class="toc-count">{{ chapterTocVisibleItems.length }}</span>
        </div>
        <div
          v-if="chapterTocVisibleItems.length"
          ref="chapterTocListRef"
          class="toc-chapter-list"
        >
          <div
            v-for="node in chapterTocVisibleItems"
            :key="node.id"
            class="toc-sub-row toc-sub-row--chapter"
            :class="[
              tocLevelClass(node),
              {
                'toc-sub-row--active': node.anchorId === activeChapterAnchorId,
                'toc-sub-row--branch': node.hasChildren,
                'toc-sub-row--root': node.depth === 0,
              },
            ]"
            :style="{ '--toc-indent': `${node.depth * 16}px` }"
            :data-anchor-id="node.anchorId"
          >
            <button
              v-if="node.hasChildren"
              class="toc-toggle"
              type="button"
              @click.stop="toggleTocExpand(node.id)"
            >
              {{ node.isExpanded ? "⌄" : "›" }}
            </button>
            <span v-else class="toc-toggle toc-toggle--placeholder"></span>
            <button
              class="toc-sub-link"
              type="button"
              @click="handleTocNodeClick(node)"
            >
              {{ node.text }}
            </button>
          </div>
        </div>
        <p v-else class="meta">当前章节暂无子目录。</p>
      </section>
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
            <input
              class="input"
              v-model="createForm.title"
              placeholder="文章标题"
            />
            <select class="select" v-model="createForm.category">
              <option value="">选择分类</option>
              <option
                v-for="item in categories"
                :key="item.id"
                :value="item.id"
              >
                {{ formatCategoryLabel(item.name) }}
              </option>
            </select>
          </div>
          <textarea
            class="textarea"
            v-model="createForm.summary"
            placeholder="摘要"
          ></textarea>
          <textarea
            class="textarea"
            v-model="createForm.content_md"
            placeholder="Markdown 正文"
          ></textarea>
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
          <ArticlePage
            :id="item.id"
            :article-data="item"
            :embedded="true"
            @deleted="handleEmbeddedArticleDeleted"
          />
        </div>
        <p v-if="usingDemoArticles" class="chapter-demo-tip">
          当前展示的是开发环境演示正文，用于验收主题、表格和代码块样式。
        </p>
        <p v-if="!chapterArticles.length" class="meta">
          当前章节暂无可展示内容。
        </p>
      </section>
    </main>
  </section>
</template>

<script setup>
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
} from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { useRequestControllers } from "../composables/useRequestControllers";
import api from "../services/api";
import { isRequestCanceled } from "../services/api";
import {
  DEMO_WIKI_CATEGORY,
  buildDemoWikiArticle,
} from "../content/demoContent";
import ArticlePage from "./ArticlePage.vue";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const ui = useUiStore();
const requests = useRequestControllers();

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
  category:
    typeof route.query.category === "string" ? route.query.category : "",
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
  if (currentCategory.value)
    return formatCategoryLabel(currentCategory.value.name);
  return "全部条目";
});

const usingDemoCategory = computed(
  () => Boolean(import.meta.env.DEV) && !categories.value.length,
);
const effectiveCategories = computed(() =>
  usingDemoCategory.value ? [DEMO_WIKI_CATEGORY] : categories.value,
);
const usingDemoArticles = computed(
  () => Boolean(import.meta.env.DEV) && !articles.value.length,
);
const currentCategory = computed(
  () =>
    effectiveCategories.value.find((item) => isCategoryActive(item)) || null,
);

const chapterCategories = computed(() => {
  return effectiveCategories.value
    .filter((item) => item?.slug && !item.parent && item.is_visible !== false)
    .sort(sortCategories);
});

const chapterArticles = computed(() => {
  if (articles.value.length) {
    return [...articles.value].sort((left, right) => {
      const orderDelta =
        Number(left.display_order || 0) - Number(right.display_order || 0);
      if (orderDelta !== 0) return orderDelta;
      return Number(left.id || 0) - Number(right.id || 0);
    });
  }
  if (!usingDemoArticles.value) {
    return [];
  }
  return [buildDemoWikiArticle(currentCategory.value || DEMO_WIKI_CATEGORY)];
});
const chapterTocTree = computed(() =>
  buildChapterTocTree(chapterArticles.value),
);
const chapterTocExpandedIds = ref(new Set());
const activeChapterAnchorId = ref("");
const chapterTocListRef = ref(null);
const PAGE_SCROLL_TOP_OFFSET = 92;
const PAGE_SCROLL_REVEAL_PADDING = 20;
const PAGE_SCROLL_BOTTOM_PADDING = 20;
const TOC_SCROLL_EDGE_GAP = 16;
let chapterScrollRafId = 0;
let chapterActiveLockUntil = 0;
let chapterLastScrollY = 0;
let chapterLastTocScrollTs = 0;
let chapterRapidScrollUntil = 0;
let chapterHeadingOffsetList = [];
let chapterHeadingOffsetMap = new Map();
const chapterTocVisibleItems = computed(() =>
  flattenVisibleChapterToc(chapterTocTree.value, chapterTocExpandedIds.value),
);
const categoryDirectoryExpandedIds = ref(new Set());
const categoryDirectoryTree = computed(() =>
  buildCategoryDirectoryTree(effectiveCategories.value),
);
const categoryDirectoryVisibleItems = computed(() =>
  flattenVisibleCategoryDirectory(
    categoryDirectoryTree.value,
    categoryDirectoryExpandedIds.value,
  ),
);

async function loadCategories() {
  const controller = requests.replace("categories");
  try {
    const { data } = await api.get("/categories/", {
      signal: controller.signal,
    });
    if (!requests.isCurrent("categories", controller)) return;
    categories.value = data.results || data;
  } catch (error) {
    if (
      isRequestCanceled(error) ||
      !requests.isCurrent("categories", controller)
    )
      return;
    try {
      const summary = await loadSummaryFallback(controller.signal);
      if (!requests.isCurrent("categories", controller)) return;
      categories.value = summary.categories || [];
      if (!fallbackNotices.categories) {
        ui.info("分类接口异常，已使用降级数据");
        fallbackNotices.categories = true;
      }
    } catch (fallbackError) {
      notifyLoadError(
        fallbackError,
        "分类加载失败，请确认后端服务已启动并执行 migrate",
      );
    }
  } finally {
    requests.release("categories", controller);
  }
}

function applyQueryToState() {
  filters.category =
    typeof route.query.category === "string" ? route.query.category : "";
}

function buildParams() {
  const params = {};
  if (filters.category) params.category = filters.category;
  return params;
}

async function loadArticles() {
  const controller = requests.replace("articles");
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
        signal: controller.signal,
      });
      if (!requests.isCurrent("articles", controller)) return;
      const pageItems = data.results || data;
      items.push(...pageItems);
      totalCount = Number.isFinite(data?.count) ? data.count : items.length;

      if (!Array.isArray(data?.results) || !data?.next) break;
      const nextPage = Number(
        new URL(data.next, window.location.origin).searchParams.get("page") ||
          "0",
      );
      if (!nextPage || nextPage === page) break;
      page = nextPage;
    }

    articles.value = items;
    pagination.count = totalCount || items.length;
  } catch (error) {
    if (isRequestCanceled(error) || !requests.isCurrent("articles", controller))
      return;
    try {
      const summary = await loadSummaryFallback(controller.signal);
      if (!requests.isCurrent("articles", controller)) return;
      const fallbackItems = filterFallbackArticles(
        summary.featured_articles || [],
      );
      articles.value = fallbackItems;
      pagination.count = fallbackItems.length;
      if (!fallbackNotices.articles) {
        ui.info("条目接口异常，已使用降级数据");
        fallbackNotices.articles = true;
      }
    } catch (fallbackError) {
      notifyLoadError(
        fallbackError,
        "条目加载失败，请确认后端服务已启动并执行 migrate",
      );
    }
  } finally {
    requests.release("articles", controller);
  }
}

async function loadSummaryFallback(signal) {
  if (fallbackSummary.value) return fallbackSummary.value;
  const { data } = await api.get("/home/summary/", { signal });
  fallbackSummary.value = data;
  return data;
}

function sortCategories(a, b) {
  const orderDelta = Number(a?.order || 0) - Number(b?.order || 0);
  if (orderDelta !== 0) return orderDelta;
  return String(a?.name || "").localeCompare(
    String(b?.name || ""),
    "zh-Hans-CN",
  );
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

function normalizeAnchorText(text) {
  return String(text || "")
    .trim()
    .toLowerCase()
    .replace(/[^\w\u4e00-\u9fa5\s-]/g, "")
    .replace(/\s+/g, "-")
    .slice(0, 64);
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

function normalizeHeadingAnchorId(text, articleId, counts) {
  const base = normalizeAnchorText(text) || "section";
  const count = counts.get(base) || 0;
  const nextCount = count + 1;
  counts.set(base, nextCount);
  const normalizedId = nextCount === 1 ? base : `${base}-${nextCount}`;
  return `article-${articleId}-${normalizedId}`;
}

function buildHeadingTree(items, articleId) {
  const root = {
    id: `a-${articleId}-root`,
    level: 1,
    text: "",
    anchorId: `chapter-article-${articleId}`,
    children: [],
  };
  const stack = [root];
  const headingIdCounts = new Map();

  for (const item of items) {
    const node = {
      id: `a-${articleId}-h-${item.index}`,
      text: item.text,
      level: item.level,
      anchorId: normalizeHeadingAnchorId(item.text, articleId, headingIdCounts),
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
  return chapterItems.flatMap((item) =>
    buildHeadingTree(parseArticleHeadingLines(item.content_md), item.id),
  );
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

function flattenAllChapterNodes(nodes, output = []) {
  for (const node of nodes) {
    output.push(node);
    if (node.children.length) {
      flattenAllChapterNodes(node.children, output);
    }
  }
  return output;
}

function buildDefaultExpandedIds(tree) {
  const expanded = new Set();

  function walk(nodes, depth = 0) {
    for (const node of nodes) {
      if (node.children.length && depth < 2) {
        expanded.add(node.id);
      }
      if (node.children.length) {
        walk(node.children, depth + 1);
      }
    }
  }

  walk(tree);
  return expanded;
}

function buildCategoryDirectoryTree(list) {
  const visible = [...list]
    .filter((item) => item?.is_visible !== false)
    .sort(sortCategories);
  const nodesById = new Map(
    visible.map((item) => [
      item.id,
      {
        id: `category-${item.id}`,
        categoryId: item.id,
        slug: item.slug,
        text: item.name,
        parent: item.parent,
        children: [],
      },
    ]),
  );
  const roots = [];
  for (const item of visible) {
    const node = nodesById.get(item.id);
    if (!node) continue;
    const parentNode = item.parent ? nodesById.get(item.parent) : null;
    if (parentNode) {
      parentNode.children.push(node);
    } else {
      roots.push(node);
    }
  }
  return roots;
}

function flattenVisibleCategoryDirectory(
  nodes,
  expandedIds,
  depth = 0,
  output = [],
) {
  for (const node of nodes) {
    const hasChildren = node.children.length > 0;
    const isExpanded = expandedIds.has(node.id);
    const isActive = isCategoryActive({ id: node.categoryId, slug: node.slug });
    output.push({
      id: node.id,
      text: node.text,
      depth,
      hasChildren,
      isExpanded,
      isActive,
      categoryId: node.categoryId,
      slug: node.slug,
    });
    if (hasChildren && isExpanded) {
      flattenVisibleCategoryDirectory(
        node.children,
        expandedIds,
        depth + 1,
        output,
      );
    }
  }
  return output;
}

function buildDefaultCategoryExpandedIds(tree) {
  const expanded = new Set();
  const activeCategoryId = currentCategory.value?.id || null;

  function walk(nodes) {
    let branchHasActive = false;
    for (const node of nodes) {
      const childHasActive = walk(node.children || []);
      const isActive =
        activeCategoryId &&
        Number(node.categoryId) === Number(activeCategoryId);
      if (
        node.children.length &&
        (depthShouldExpand(node, node.children) || childHasActive || isActive)
      ) {
        expanded.add(node.id);
      }
      if (isActive || childHasActive) {
        branchHasActive = true;
      }
    }
    return branchHasActive;
  }

  walk(tree);
  return expanded;
}

function depthShouldExpand(node) {
  return !node.parent;
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
  if (node.hasChildren && !isTocExpanded(node.id)) {
    const next = new Set(chapterTocExpandedIds.value);
    next.add(node.id);
    chapterTocExpandedIds.value = next;
  }
  chapterActiveLockUntil = Date.now() + 1100;
  chapterLastTocScrollTs = 0;
  chapterLastScrollY = typeof window !== "undefined" ? window.scrollY : 0;
  activeChapterAnchorId.value = node.anchorId;
  scrollToAnchor(node.anchorId);
}

function scrollToAnchor(anchorId) {
  if (!anchorId) return;
  const node = document.getElementById(anchorId);
  if (!node) return;
  const prefersReducedMotion =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const safeTop = PAGE_SCROLL_TOP_OFFSET + PAGE_SCROLL_REVEAL_PADDING;
  const targetTop = Math.max(
    0,
    window.scrollY + node.getBoundingClientRect().top - safeTop,
  );
  window.scrollTo({
    top: targetTop,
    behavior: prefersReducedMotion ? "auto" : "smooth",
  });

  // 双 rAF 后执行可见性校正，保证标题完整露出，而不是只露边。
  window.requestAnimationFrame(() => {
    window.requestAnimationFrame(() => {
      const rect = node.getBoundingClientRect();
      const viewportBottom = window.innerHeight - PAGE_SCROLL_BOTTOM_PADDING;
      let delta = 0;
      if (rect.top < safeTop) {
        delta = rect.top - safeTop;
      } else if (rect.bottom > viewportBottom) {
        delta = rect.bottom - viewportBottom;
      }
      if (Math.abs(delta) > 1) {
        window.scrollBy({ top: delta, behavior: "auto" });
      }
      rebuildChapterHeadingOffsets();
      scheduleActiveAnchorSync();
    });
  });
}

function isCompactViewport() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function")
    return false;
  return window.matchMedia("(max-width: 900px)").matches;
}

function escapeAttributeSelector(value) {
  return String(value || "")
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"');
}

function rebuildChapterHeadingOffsets() {
  if (typeof window === "undefined") {
    chapterHeadingOffsetList = [];
    chapterHeadingOffsetMap = new Map();
    return;
  }
  const allNodes = flattenAllChapterNodes(chapterTocTree.value);
  const headingItems = allNodes
    .map((node) => ({
      anchorId: node.anchorId,
      element: document.getElementById(node.anchorId),
    }))
    .filter((item) => item.element);
  const scrollY = window.scrollY || 0;
  const nextList = [];
  const nextMap = new Map();
  for (const item of headingItems) {
    const top = item.element.getBoundingClientRect().top + scrollY;
    nextList.push({ anchorId: item.anchorId, top });
    nextMap.set(item.anchorId, top);
  }
  nextList.sort((left, right) => left.top - right.top);
  chapterHeadingOffsetList = nextList;
  chapterHeadingOffsetMap = nextMap;
}

function findHeadingIndexByTop(targetTop) {
  let low = 0;
  let high = chapterHeadingOffsetList.length - 1;
  let answer = -1;
  while (low <= high) {
    const middle = (low + high) >> 1;
    if (chapterHeadingOffsetList[middle].top <= targetTop) {
      answer = middle;
      low = middle + 1;
    } else {
      high = middle - 1;
    }
  }
  return answer;
}

function pickActiveAnchorFromViewport() {
  if (!chapterHeadingOffsetList.length) return "";

  const currentScrollY = typeof window !== "undefined" ? window.scrollY : 0;
  const activationTop =
    currentScrollY +
    PAGE_SCROLL_TOP_OFFSET +
    Math.min(220, Math.max(120, window.innerHeight * 0.28));
  const scrollingDown = currentScrollY >= chapterLastScrollY;
  const scrollDelta = Math.abs(currentScrollY - chapterLastScrollY);
  if (scrollDelta > Math.max(window.innerHeight * 0.22, 170)) {
    chapterRapidScrollUntil = Date.now() + 220;
  }
  chapterLastScrollY = currentScrollY;

  const candidateIndex = findHeadingIndexByTop(activationTop);
  if (candidateIndex < 0) {
    return chapterHeadingOffsetList[0]?.anchorId || "";
  }

  let nextAnchorId = chapterHeadingOffsetList[candidateIndex]?.anchorId || "";
  const currentAnchorId = activeChapterAnchorId.value;
  const currentTop = chapterHeadingOffsetMap.get(currentAnchorId);
  if (
    Number.isFinite(currentTop) &&
    Math.abs(currentTop - activationTop) < 56
  ) {
    return currentAnchorId;
  }

  if (!scrollingDown && candidateIndex > 0) {
    const currentCandidateTop = chapterHeadingOffsetList[candidateIndex].top;
    const previousCandidateTop =
      chapterHeadingOffsetList[candidateIndex - 1].top;
    if (
      activationTop - previousCandidateTop < 26 &&
      currentCandidateTop - activationTop > 26
    ) {
      nextAnchorId = chapterHeadingOffsetList[candidateIndex - 1].anchorId;
    }
  }

  return nextAnchorId;
}

function syncActiveAnchorByViewport() {
  if (Date.now() < chapterActiveLockUntil) return;
  const nextAnchorId = pickActiveAnchorFromViewport();
  if (!nextAnchorId || nextAnchorId === activeChapterAnchorId.value) return;
  activeChapterAnchorId.value = nextAnchorId;
}

function scheduleActiveAnchorSync() {
  if (chapterScrollRafId) return;
  chapterScrollRafId = window.requestAnimationFrame(() => {
    chapterScrollRafId = 0;
    syncActiveAnchorByViewport();
  });
}

function ensureActiveTocItemInView(anchorId) {
  if (!anchorId || isCompactViewport()) return;
  const container = chapterTocListRef.value;
  if (!container) return;
  const row = container.querySelector(
    `[data-anchor-id="${escapeAttributeSelector(anchorId)}"]`,
  );
  if (!row) return;

  const viewTop = container.scrollTop;
  const viewBottom = viewTop + container.clientHeight;
  const rowTop = row.offsetTop;
  const rowBottom = rowTop + row.offsetHeight;
  const above = rowTop < viewTop + TOC_SCROLL_EDGE_GAP;
  const below = rowBottom > viewBottom - TOC_SCROLL_EDGE_GAP;
  if (!above && !below) return;

  const now = Date.now();
  const rapidScrolling = now < chapterRapidScrollUntil;
  if (!rapidScrolling && now - chapterLastTocScrollTs < 60) return;
  chapterLastTocScrollTs = now;

  const prefersReducedMotion =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const centeredTop = rowTop - (container.clientHeight - row.offsetHeight) / 2;
  const nextTop =
    above || below ? Math.max(0, centeredTop) : container.scrollTop;

  container.scrollTo({
    top: nextTop,
    behavior: prefersReducedMotion || rapidScrolling ? "auto" : "smooth",
  });
}

function stopChapterScrollSync() {
  if (typeof window !== "undefined") {
    window.removeEventListener("scroll", scheduleActiveAnchorSync);
    window.removeEventListener("resize", handleChapterViewportResize);
  }
  if (chapterScrollRafId) {
    window.cancelAnimationFrame(chapterScrollRafId);
    chapterScrollRafId = 0;
  }
}

function handleChapterViewportResize() {
  rebuildChapterHeadingOffsets();
  scheduleActiveAnchorSync();
}

function startChapterScrollSync() {
  stopChapterScrollSync();
  chapterLastScrollY = typeof window !== "undefined" ? window.scrollY : 0;
  chapterLastTocScrollTs = 0;
  chapterRapidScrollUntil = 0;
  rebuildChapterHeadingOffsets();
  if (!chapterHeadingOffsetList.length) return;

  if (typeof window !== "undefined") {
    window.addEventListener("scroll", scheduleActiveAnchorSync, {
      passive: true,
    });
    window.addEventListener("resize", handleChapterViewportResize, {
      passive: true,
    });
  }

  scheduleActiveAnchorSync();
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

async function selectCategory(node) {
  if (!node) return;
  filters.category = node.slug || String(node.categoryId || "");
  await syncRoute();
}

function toggleCategoryExpand(id) {
  if (!id) return;
  const next = new Set(categoryDirectoryExpandedIds.value);
  if (next.has(id)) {
    next.delete(id);
  } else {
    next.add(id);
  }
  categoryDirectoryExpandedIds.value = next;
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
      const matchedCategory = categories.value.find(
        (item) => item.slug === filters.category,
      );
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
  if (isRequestCanceled(error)) {
    return;
  }
  const payload = error?.response?.data;
  const isSchemaOutdated =
    payload &&
    typeof payload === "object" &&
    payload.code === "schema_outdated";
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

onBeforeUnmount(() => {
  stopChapterScrollSync();
});

watch(
  () => chapterTocTree.value,
  async (tree) => {
    chapterTocExpandedIds.value = buildDefaultExpandedIds(chapterTocTree.value);
    activeChapterAnchorId.value = tree[0]?.anchorId || "";
    await nextTick();
    startChapterScrollSync();
  },
  { immediate: true },
);

watch(
  () => activeChapterAnchorId.value,
  (anchorId) => {
    ensureActiveTocItemInView(anchorId);
  },
);

watch(
  () => [categoryDirectoryTree.value, currentCategory.value?.id],
  () => {
    categoryDirectoryExpandedIds.value = buildDefaultCategoryExpandedIds(
      categoryDirectoryTree.value,
    );
  },
  { immediate: true, deep: true },
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
  },
);

watch(
  () => currentCategory.value?.id,
  (value) => {
    if (!value) return;
    if (!createForm.category) {
      createForm.category = value;
    }
  },
  { immediate: true },
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
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--surface-strong) 82%, white 18%),
    var(--surface) 30%
  );
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
  transition:
    background-color 0.18s ease,
    color 0.18s ease,
    transform 0.18s ease;
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
  transition:
    background-color 0.18s ease,
    color 0.18s ease,
    transform 0.18s ease;
}

.toc-sub-link:hover {
  background: color-mix(in srgb, var(--accent) 10%, transparent);
  color: var(--accent);
  transform: translateX(2px);
}

.wiki-directory {
  display: grid;
  gap: 8px;
  padding-top: 14px;
  border-top: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
}

.wiki-directory-list {
  display: grid;
  gap: 2px;
}

.wiki-directory-row--active .wiki-directory-link {
  background: color-mix(in srgb, var(--accent) 11%, var(--surface-strong));
  color: var(--accent);
  font-weight: 700;
}

.wiki-directory-link {
  font-size: 14px;
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

.wiki-toc {
  gap: 18px;
}

.wiki-toc-block {
  display: grid;
  gap: 12px;
}

.wiki-toc-section-head,
.wiki-toc-section-head--primary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--text-soft);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: none;
}

.wiki-toc-title-wrap {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  color: var(--text-strong);
}

.wiki-toc-title-icon {
  position: relative;
  width: 16px;
  height: 12px;
  color: var(--text-quiet);
  flex: 0 0 auto;
}

.wiki-toc-title-icon::before {
  content: "";
  position: absolute;
  left: 0;
  top: 1px;
  width: 100%;
  height: 2px;
  border-radius: 999px;
  background: currentColor;
  box-shadow:
    0 5px 0 currentColor,
    0 10px 0 currentColor;
}

.toc-count {
  min-width: 34px;
  height: 34px;
  padding: 0 10px;
  background: color-mix(in srgb, var(--surface-strong) 96%, white 4%);
  color: var(--text-quiet);
  font-size: 14px;
  font-weight: 700;
}

.toc-chapter-list {
  display: grid;
  gap: 4px;
  max-height: calc(100vh - 240px);
  overflow: auto;
  padding-right: 2px;
}

.toc-sub-row--chapter {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  padding-left: var(--toc-indent, 0);
}

.toc-sub-row--chapter .toc-toggle {
  width: 22px;
  height: 22px;
  flex: 0 0 22px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--text-quiet);
  font-size: 20px;
  line-height: 1;
}

.toc-sub-row--chapter .toc-toggle:hover {
  background: color-mix(in srgb, var(--accent) 8%, transparent);
  color: var(--text-strong);
}

.toc-sub-row--chapter .toc-toggle--placeholder {
  opacity: 0;
}

.toc-sub-row--chapter .toc-sub-link {
  width: 100%;
  padding: 9px 14px;
  border-radius: 14px;
  background: transparent;
  color: var(--text-soft);
  font-size: 14px;
  font-weight: 500;
  line-height: 1.45;
  transition:
    background-color 0.18s ease,
    color 0.18s ease;
}

.toc-sub-row--chapter .toc-sub-link:hover {
  background: color-mix(in srgb, var(--surface-strong) 88%, white 12%);
  color: var(--text-strong);
  transform: none;
}

.toc-sub-row--chapter.toc-sub-row--root .toc-sub-link {
  padding-top: 12px;
  padding-bottom: 12px;
  background: color-mix(in srgb, var(--surface-strong) 94%, white 6%);
  color: var(--text-strong);
  font-size: 15px;
  font-weight: 800;
}

.toc-sub-row--active .toc-sub-link,
.toc-sub-row--active.toc-sub-row--root .toc-sub-link,
.wiki-directory-row--active .wiki-directory-link {
  background: color-mix(in srgb, var(--accent) 10%, white 90%);
  color: var(--accent);
  font-weight: 700;
}

.toc-level-1 .toc-sub-link,
.toc-level-2 .toc-sub-link,
.toc-level-3 .toc-sub-link,
.toc-level-4 .toc-sub-link,
.toc-level-5 .toc-sub-link,
.toc-level-6 .toc-sub-link {
  color: var(--text-soft);
}

.toc-sub-row--root.toc-level-1 .toc-sub-link {
  color: var(--text-strong);
}

.wiki-directory {
  gap: 10px;
  padding-top: 18px;
  border-top: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
}

.wiki-directory-list {
  display: grid;
  gap: 3px;
}

.wiki-directory-row {
  padding-left: var(--toc-indent, 0);
}

.wiki-directory-link {
  padding: 8px 12px;
  border-radius: 12px;
  font-size: 14px;
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
