<template>
  <section
    v-if="article"
    class="article-layout"
    :class="{
      'editor-mode': showEditor,
      'left-collapsed': leftCollapsed,
      'right-collapsed': rightCollapsed,
      'embedded-mode': embeddedMode,
    }"
  >
    <article v-if="showEditor" class="editor-shell">
      <header class="editor-header">
        <h2>编辑条目（{{ directPublishEdit ? "直接发布" : "提交审核" }}）</h2>
        <div class="article-actions">
          <button class="btn" @click="cancelEditor">取消</button>
          <button class="btn btn-accent" :disabled="savingEdit" @click="saveArticleEdit">
            {{ savingEdit ? "提交中..." : directPublishEdit ? "保存并发布" : "提交审核" }}
          </button>
        </div>
      </header>

      <div class="editor-meta">
        <input class="input" v-model="editForm.title" placeholder="条目标题" />
        <textarea class="textarea" v-model="editForm.summary" placeholder="条目摘要（可选）"></textarea>
        <input class="input" v-model="editReason" :placeholder="directPublishEdit ? '修订说明（可选）' : '修订说明（会进入审核区）'" />
      </div>

      <section class="editor-layout">
        <article class="editor-pane card">
          <h3>Markdown 原文</h3>
          <ImageUploadHelper label="上传图片并插入 Markdown" @uploaded="onEditorImageUploaded" />
          <textarea
            class="textarea editor-textarea"
            v-model="editForm.content_md"
            placeholder="在这里编辑 Markdown 原文"
          ></textarea>
        </article>
        <article class="editor-pane card">
          <h3>渲染预览</h3>
          <div class="markdown editor-preview" v-html="editorPreviewHtml"></div>
        </article>
      </section>
    </article>

    <template v-else>
      <aside v-if="!embeddedMode" class="side-panel side-panel--left" :class="{ collapsed: leftCollapsed }">
        <button class="side-toggle btn" @click="leftCollapsed = !leftCollapsed">
          {{ leftCollapsed ? "展开目录" : "折叠目录" }}
        </button>
        <div v-show="!leftCollapsed" class="side-content">
          <section class="panel-block panel-block--toc">
            <h3>分类目录</h3>
            <div v-for="item in tocVisibleItems" :key="item.id" class="toc-row" :style="{ paddingLeft: `${item.depth * 14}px` }">
              <button
                v-if="item.hasChildren"
                class="toc-toggle"
                type="button"
                @click.stop="toggleTocExpand(item.id)"
              >
                {{ item.isExpanded ? "▾" : "▸" }}
              </button>
              <span v-else class="toc-toggle toc-toggle--placeholder"></span>
              <a :href="`#${item.id}`" class="toc-item">{{ item.text }}</a>
            </div>
            <p v-if="!tocVisibleItems.length" class="meta">当前正文暂无子标题目录。</p>
          </section>
        </div>
      </aside>

      <article class="article-main">
        <header class="article-header">
          <h1>{{ article.title }}</h1>
          <div class="article-actions">
            <span class="pill">{{ article.category_name }}</span>
            <span v-if="isDemoArticle" class="pill article-demo-pill">开发环境示例</span>
            <button v-if="auth.isAuthenticated && !isDemoArticle" class="btn" @click="toggleStar">
              {{ article.is_starred ? "取消收藏" : "收藏" }} ({{ article.star_count }})
            </button>
            <button v-if="auth.isAuthenticated && !isDemoArticle" class="btn" @click="openEditor">
              {{ canModerateArticle ? "编辑条目" : "修改条目" }}
            </button>
            <button
              v-if="canDeleteArticle && !isDemoArticle"
              class="btn"
              :disabled="deletingArticle"
              @click="removeArticle"
            >
              {{ deletingArticle ? "删除中..." : "删除条目" }}
            </button>
            <button
              v-if="canModerateArticle && article.status !== 'published' && !isDemoArticle"
              class="btn"
              @click="publishArticle"
            >
              发布
            </button>
          </div>
        </header>

        <p class="meta">作者 {{ article.author.username }} · 更新于 {{ formatTime(article.updated_at) }}</p>
        <p v-if="article.summary" class="article-summary">{{ article.summary }}</p>
        <div v-if="isDemoArticle" class="article-demo-note">
          当前正文为本地验收用演示内容，仅在开发环境兜底展示，不会写入正式站点。
        </div>
        <section class="markdown article-markdown" v-html="renderedHtml"></section>
      </article>

      <aside class="side-panel side-panel--right" :class="{ collapsed: rightCollapsed }">
        <button class="side-toggle btn" @click="rightCollapsed = !rightCollapsed">
          {{ rightCollapsed ? "展开互动" : "折叠互动" }}
        </button>
        <div v-show="!rightCollapsed" class="side-content">
          <section class="panel-block">
            <h3>评论</h3>
            <article class="comment" v-for="item in comments" :key="item.id">
              <div class="comment-head">
                <div class="meta">
                  {{ item.author.username }} · {{ formatTime(item.created_at) }}
                  <span v-if="item.parent" class="reply-tag">回复 #{{ item.parent }}</span>
                  <span v-if="item.status === 'pending'" class="reply-tag">待审核</span>
                </div>
                <div class="comment-tools" v-if="auth.isAuthenticated && !isDemoArticle">
                  <button class="btn btn-mini" v-if="item.status === 'visible'" @click="startReply(item)">回复</button>
                  <button
                    class="btn btn-mini"
                    v-if="canDeleteComment(item)"
                    :disabled="deletingCommentId === item.id"
                    @click="removeComment(item)"
                  >
                    {{ deletingCommentId === item.id ? "处理中..." : "删除" }}
                  </button>
                </div>
              </div>
              <p>{{ item.content }}</p>
            </article>
            <p v-if="!comments.length" class="meta">暂无评论</p>

            <div v-if="auth.isAuthenticated && !isDemoArticle" class="comment-form">
              <p class="meta" v-if="replyTarget">
                当前回复：#{{ replyTarget.id }} {{ replyTarget.author.username }}
                <button class="btn btn-mini" @click="cancelReply">取消回复</button>
              </p>
              <textarea class="textarea" v-model="newComment" placeholder="写下你的评论"></textarea>
              <button class="btn btn-accent" :disabled="submittingComment" @click="submitComment">
                {{ submittingComment ? "提交中..." : replyTarget ? "提交回复" : "提交评论" }}
              </button>
            </div>
            <p v-else-if="isDemoArticle" class="meta">演示文章的评论区为只读样本，用于本地验收布局。</p>
            <p v-else class="meta">登录后可发表评论。</p>
          </section>
        </div>
      </aside>
    </template>
  </section>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import ImageUploadHelper from "../components/ImageUploadHelper.vue";
import api from "../services/api";
import { renderMarkdown } from "../services/markdown";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const route = useRoute();
const props = defineProps({
  id: {
    type: [String, Number],
    default: "",
  },
  articleData: {
    type: Object,
    default: null,
  },
  embedded: {
    type: Boolean,
    default: false,
  },
});
const emit = defineEmits(["deleted"]);
const auth = useAuthStore();
const ui = useUiStore();
const router = useRouter();

const embeddedMode = computed(() => Boolean(props.embedded));
const articleId = computed(() => {
  const propId = props.id == null ? "" : String(props.id).trim();
  if (propId) return propId;
  return String(route.params.id || "");
});

const article = ref(null);
const comments = ref([]);
const newComment = ref("");
const renderedHtml = ref("");
const tocTree = ref([]);
const tocExpandedIds = ref(new Set());
const showEditor = ref(false);
const savingEdit = ref(false);
const deletingArticle = ref(false);
const submittingComment = ref(false);
const deletingCommentId = ref(null);
const replyingToCommentId = ref(null);
const leftCollapsed = ref(false);
const rightCollapsed = ref(true);
const editReason = ref("");

const editForm = reactive({
  title: "",
  summary: "",
  content_md: "",
});

const canModerateArticle = computed(() => Boolean(article.value?.can_edit));
const canDeleteArticle = computed(() => auth.isManager && Boolean(article.value?.id));
const directPublishEdit = computed(() => auth.isManager && canModerateArticle.value);
const isDemoArticle = computed(() => Boolean(article.value?.__demo));
const replyTarget = computed(() =>
  comments.value.find((item) => item.id === replyingToCommentId.value) || null
);
const editorPreviewHtml = computed(() => renderMarkdown(editForm.content_md || ""));
const tocVisibleItems = computed(() => flattenVisibleToc(tocTree.value, tocExpandedIds.value));

function appendMarkdown(target, snippet) {
  const next = String(snippet || "").trim();
  if (!next) return String(target || "");
  const base = String(target || "");
  return base ? `${base}\n\n${next}\n` : `${next}\n`;
}

function onEditorImageUploaded(payload) {
  editForm.content_md = appendMarkdown(editForm.content_md, payload?.markdown);
}

function normalizeAnchorText(text) {
  return text
    .trim()
    .toLowerCase()
    .replace(/[^\w\u4e00-\u9fa5\s-]/g, "")
    .replace(/\s+/g, "-")
    .slice(0, 64);
}

function buildRenderedContent(content) {
  const html = renderMarkdown(content || "");
  const parser = new DOMParser();
  const doc = parser.parseFromString(`<div id=\"__root\">${html}</div>`, "text/html");
  const root = doc.getElementById("__root");
  const headings = root ? [...root.querySelectorAll("h1, h2, h3, h4, h5, h6")] : [];

  const idMap = new Map();
  const flatTocItems = headings.map((heading) => {
    const text = heading.textContent || "";
    const base = normalizeAnchorText(text) || "section";
    const count = idMap.get(base) || 0;
    const nextCount = count + 1;
    idMap.set(base, nextCount);
    const id = nextCount === 1 ? base : `${base}-${nextCount}`;

    heading.id = id;
    return {
      id,
      text,
      level: Number(heading.tagName[1]),
    };
  });

  tocTree.value = pruneOverviewToc(buildTocTree(flatTocItems));
  tocExpandedIds.value = collectDefaultExpandedIds(tocTree.value);
  renderedHtml.value = root ? root.innerHTML : html;
}

function buildTocTree(items) {
  const roots = [];
  const stack = [];

  for (const item of items) {
    const node = {
      id: item.id,
      text: item.text,
      level: item.level,
      children: [],
    };

    while (stack.length && stack[stack.length - 1].level >= node.level) {
      stack.pop();
    }

    if (stack.length) {
      stack[stack.length - 1].children.push(node);
    } else {
      roots.push(node);
    }

    stack.push(node);
  }

  return roots;
}

function flattenVisibleToc(nodes, expandedIds, depth = 0, output = []) {
  for (const node of nodes) {
    const hasChildren = node.children.length > 0;
    const isExpanded = expandedIds.has(node.id);
    output.push({
      id: node.id,
      text: node.text,
      depth,
      hasChildren,
      isExpanded,
    });
    if (hasChildren && isExpanded) {
      flattenVisibleToc(node.children, expandedIds, depth + 1, output);
    }
  }
  return output;
}

function collectDefaultExpandedIds(nodes) {
  const expanded = new Set();
  const walk = (list) => {
    for (const node of list) {
      // Default expanded to second-level headings: expand h1 only.
      if (node.level === 1 && node.children.length) {
        expanded.add(node.id);
      }
      if (node.children.length) {
        walk(node.children);
      }
    }
  };
  walk(nodes);
  return expanded;
}

function normalizeTocText(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "")
    .replace(/[【】\[\]()（）:：·,，.!！?？"']/g, "");
}

function isOverviewNode(node) {
  const text = normalizeTocText(node?.text);
  const childCount = Array.isArray(node?.children) ? node.children.length : 0;
  const overviewKeywords = [
    "欢迎来到algowiki",
    "welcometoalgowiki",
    "文章全览",
    "目录全览",
    "全文目录",
  ];
  if (overviewKeywords.some((keyword) => text.includes(keyword))) {
    return true;
  }
  const chapterKeywords = [
    "阅前须知",
    "学术诚信",
    "常见术语",
    "竞赛概念",
    "比赛介绍",
    "关键网站",
    "代码工具",
    "阶段任务",
    "关于训练",
    "结语与致谢",
  ];
  const normalizedChildren = (node?.children || []).map((item) => normalizeTocText(item?.text));
  const matchedChapterCount = chapterKeywords.filter((item) =>
    normalizedChildren.some((child) => child.includes(normalizeTocText(item)))
  ).length;
  if (childCount >= 6 && matchedChapterCount >= 4) {
    return true;
  }
  // If a root title is an AlgoWiki welcome heading and also carries a long chapter tree,
  // treat it as overview block and hide it from TOC.
  return text.includes("algowiki") && text.includes("欢迎") && childCount >= 3;
}

function pruneOverviewToc(nodes) {
  return nodes
    .filter((node) => !isOverviewNode(node))
    .map((node) => ({
      ...node,
      children: pruneOverviewToc(node.children || []),
    }));
}

function toggleTocExpand(id) {
  const next = new Set(tocExpandedIds.value);
  if (next.has(id)) {
    next.delete(id);
  } else {
    next.add(id);
  }
  tocExpandedIds.value = next;
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function applyArticleData(data) {
  if (!data) {
    article.value = null;
    comments.value = [];
    renderedHtml.value = "";
    tocTree.value = [];
    tocExpandedIds.value = new Set();
    syncEditForm(null);
    return;
  }
  article.value = data;
  buildRenderedContent(data.content_md);
  syncEditForm(data);
  if (data.__demo) {
    comments.value = Array.isArray(data.demo_comments) ? data.demo_comments : [];
  }
}

async function loadArticle() {
  const id = articleId.value;
  if (!id) {
    applyArticleData(props.articleData);
    return;
  }
  if (props.articleData && String(props.articleData.id) === String(id)) {
    applyArticleData(props.articleData);
    if (props.articleData.__demo) {
      return;
    }
  }
  try {
    const { data } = await api.get(`/articles/${id}/`);
    applyArticleData(data);
  } catch (error) {
    if (props.articleData && String(props.articleData.id) === String(id)) {
      return;
    }
    ui.error(getErrorText(error, "条目加载失败"));
  }
}

function syncEditForm(data) {
  editForm.title = data?.title || "";
  editForm.summary = data?.summary || "";
  editForm.content_md = data?.content_md || "";
}

async function loadComments() {
  const id = articleId.value;
  if (!id) {
    comments.value = [];
    return;
  }
  if (props.articleData?.__demo) {
    comments.value = Array.isArray(props.articleData.demo_comments) ? props.articleData.demo_comments : [];
    return;
  }
  try {
    const { data } = await api.get("/comments/", {
      params: { article: id },
    });
    comments.value = data.results || data;
    if (replyingToCommentId.value && !comments.value.some((item) => item.id === replyingToCommentId.value)) {
      replyingToCommentId.value = null;
    }
  } catch (error) {
    ui.error(getErrorText(error, "评论加载失败"));
  }
}

function canDeleteComment(comment) {
  if (!auth.user) return false;
  return auth.isManager || comment.author.id === auth.user.id;
}

function startReply(comment) {
  replyingToCommentId.value = comment.id;
}

function cancelReply() {
  replyingToCommentId.value = null;
}

async function toggleStar() {
  if (!article.value || isDemoArticle.value) return;

  try {
    if (article.value.is_starred) {
      await api.post(`/articles/${article.value.id}/unstar/`);
      article.value.is_starred = false;
      article.value.star_count = Math.max(0, article.value.star_count - 1);
      ui.success("已取消收藏");
    } else {
      await api.post(`/articles/${article.value.id}/star/`);
      article.value.is_starred = true;
      article.value.star_count += 1;
      ui.success("已收藏");
    }
  } catch (error) {
    ui.error(getErrorText(error, "收藏操作失败"));
  }
}

async function publishArticle() {
  if (!article.value || isDemoArticle.value) return;
  try {
    await api.post(`/articles/${article.value.id}/publish/`);
    ui.success("文章已发布");
    await loadArticle();
  } catch (error) {
    ui.error(getErrorText(error, "发布失败"));
  }
}

async function removeArticle() {
  if (!article.value || isDemoArticle.value || !canDeleteArticle.value || deletingArticle.value) return;
  if (!window.confirm("确认删除这个条目？删除后不可恢复。")) return;

  const currentId = article.value.id;
  const category = article.value.category;
  deletingArticle.value = true;
  try {
    await api.delete(`/articles/${currentId}/`);
    ui.success("条目已删除");
    if (embeddedMode.value) {
      article.value = null;
      emit("deleted", currentId);
      return;
    }
    const query = category ? { category: String(category) } : {};
    await router.push({ name: "wiki", query });
  } catch (error) {
    ui.error(getErrorText(error, "删除条目失败"));
  } finally {
    deletingArticle.value = false;
  }
}

function openEditor() {
  if (!auth.isAuthenticated) {
    ui.info("请先登录后再修改条目");
    return;
  }
  if (isDemoArticle.value) {
    ui.info("当前是开发环境演示文章，不能直接修改。");
    return;
  }
  if (!article.value) return;
  syncEditForm(article.value);
  editReason.value = "";
  showEditor.value = true;
}

function cancelEditor() {
  showEditor.value = false;
  if (article.value) {
    syncEditForm(article.value);
  }
  editReason.value = "";
}

async function saveArticleEdit() {
  if (!article.value || isDemoArticle.value) return;
  if (!editForm.title.trim() || !editForm.content_md.trim()) {
    ui.info("请填写标题和正文");
    return;
  }

  savingEdit.value = true;
  try {
    const payload = {
      article: article.value.id,
      proposed_title: editForm.title.trim(),
      proposed_summary: editForm.summary.trim(),
      proposed_content_md: editForm.content_md,
      reason: editReason.value.trim(),
    };
    const { data } = await api.post("/revisions/", payload);
    showEditor.value = false;
    editReason.value = "";
    if (data?.status === "pending") {
      ui.success("修改已提交到审核区，审核通过后生效");
    } else {
      ui.success("修改已发布");
      await loadArticle();
    }
  } catch (error) {
    ui.error(getErrorText(error, "提交失败"));
  } finally {
    savingEdit.value = false;
  }
}

async function submitComment() {
  if (!newComment.value.trim()) {
    ui.info("请输入评论内容");
    return;
  }
  if (!article.value || isDemoArticle.value) return;
  submittingComment.value = true;
  try {
    const payload = {
      article: article.value.id,
      content: newComment.value,
    };
    if (replyingToCommentId.value) {
      payload.parent = replyingToCommentId.value;
    }
    const { data } = await api.post("/comments/", payload);
    newComment.value = "";
    replyingToCommentId.value = null;
    if (data?.status === "pending") {
      ui.success("评论已提交，等待审核");
    } else {
      ui.success("评论已发布");
    }
    await loadComments();
  } catch (error) {
    ui.error(getErrorText(error, "评论提交失败"));
  } finally {
    submittingComment.value = false;
  }
}

async function removeComment(comment) {
  if (isDemoArticle.value) return;
  if (!canDeleteComment(comment)) return;
  if (!window.confirm("确认删除这条评论？")) return;
  deletingCommentId.value = comment.id;
  try {
    await api.delete(`/comments/${comment.id}/`);
    if (replyingToCommentId.value === comment.id) {
      replyingToCommentId.value = null;
    }
    ui.success("评论已删除");
    await loadComments();
  } catch (error) {
    ui.error(getErrorText(error, "删除评论失败"));
  } finally {
    deletingCommentId.value = null;
  }
}

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return fallback;
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

async function initPage() {
  showEditor.value = false;
  await loadArticle();
  if (!isDemoArticle.value) {
    await loadComments();
  }
}

watch(
  () => [articleId.value, props.articleData?.updated_at, props.articleData?.content_md, props.articleData?.id],
  async (nextTuple, prevTuple) => {
    const [next] = nextTuple;
    const [prev] = Array.isArray(prevTuple) ? prevTuple : [];
    if (!next) {
      applyArticleData(props.articleData);
      return;
    }
    if (next === prev) return;
    await initPage();
  },
  { immediate: true }
);
</script>

<style scoped>
.article-layout {
  display: grid;
  --left-width: 260px;
  --right-width: 360px;
  grid-template-columns: var(--left-width) minmax(0, 1fr) var(--right-width);
  gap: 20px;
}

.article-layout.embedded-mode {
  grid-template-columns: minmax(0, 1fr) var(--right-width);
}

.article-layout.embedded-mode .article-main {
  grid-column: 1;
  grid-row: 1;
}

.article-layout.embedded-mode .side-panel--right {
  grid-column: 2;
  grid-row: 1;
}

.article-layout.editor-mode {
  display: block;
}

.editor-shell {
  display: grid;
  gap: 12px;
}

.editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.editor-header h2 {
  font-size: clamp(26px, 3.8vw, 38px);
}

.editor-meta {
  display: grid;
  gap: 8px;
}

.editor-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
}

.editor-pane {
  padding: 12px;
}

.editor-pane h3 {
  margin-bottom: 8px;
  font-size: 20px;
}

.editor-textarea {
  min-height: calc(100vh - 290px);
}

.editor-preview {
  max-height: calc(100vh - 290px);
  overflow: auto;
}

.article-layout.left-collapsed {
  --left-width: 46px;
}

.article-layout.right-collapsed {
  --right-width: 46px;
}

.side-panel {
  align-self: start;
  position: sticky;
  top: 94px;
  max-height: calc(100vh - 108px);
  overflow: auto;
}

.side-panel--left {
  grid-column: 1;
  grid-row: 1;
  border-right: 1px solid var(--hairline);
  padding-right: 12px;
}

.side-panel--right {
  grid-column: 3;
  grid-row: 1;
  border-left: 1px solid var(--hairline);
  padding-left: 12px;
}

.side-content {
  margin-top: 10px;
}

.side-panel.collapsed {
  overflow: visible;
}

.side-toggle {
  width: 100%;
}

.side-panel.collapsed .side-toggle {
  width: 36px;
  min-height: 112px;
  padding: 8px;
  writing-mode: vertical-rl;
  text-orientation: mixed;
  line-height: 1.2;
}

.side-panel--left.collapsed .side-toggle {
  margin-left: auto;
}

.side-panel--right.collapsed .side-toggle {
  margin-right: auto;
}

.panel-block h3 {
  margin-bottom: 10px;
  font-size: 22px;
}

.toc-item {
  display: block;
  color: var(--text-strong);
  font-size: 15px;
  line-height: 1.35;
  padding: 4px 8px;
  border-radius: 8px;
  transition: background-color 0.18s ease, color 0.18s ease;
}

.toc-item:hover {
  background: color-mix(in srgb, var(--accent) 10%, transparent);
  color: var(--accent);
}

.toc-row {
  display: flex;
  align-items: center;
  gap: 3px;
  margin: 5px 0;
}

.toc-toggle {
  width: 18px;
  height: 18px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--text-quiet);
  font-size: 13px;
  line-height: 1;
  padding: 0;
  cursor: pointer;
}

.toc-toggle:hover {
  background: var(--accent-soft);
}

.toc-toggle--placeholder {
  display: inline-block;
  cursor: default;
}

.article-main {
  min-width: 0;
  grid-column: 2;
  grid-row: 1;
}

.article-layout:not(.embedded-mode) .article-main {
  border: 1px solid var(--hairline);
  border-radius: var(--radius-lg);
  background: var(--surface);
  padding: clamp(16px, 2.2vw, 28px);
  box-shadow: var(--shadow-sm);
}

.article-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.article-header h1 {
  font-size: clamp(34px, 5vw, 54px);
}

.article-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.article-summary {
  margin: 8px 0 16px;
  color: var(--text-soft);
  font-size: 18px;
}

.article-demo-pill {
  background: color-mix(in srgb, var(--accent) 14%, var(--surface-strong));
}

.article-demo-note {
  margin: 0 0 16px;
  border: 1px dashed color-mix(in srgb, var(--accent) 36%, transparent);
  border-radius: calc(var(--radius-sm) + 2px);
  background: color-mix(in srgb, var(--accent) 7%, var(--surface-soft));
  color: var(--text-soft);
  padding: 10px 12px;
  font-size: 15px;
}

.article-markdown {
  font-size: clamp(1.02rem, 0.95rem + 0.3vw, 1.16rem);
}

.panel-block {
  border: 1px solid var(--hairline);
  border-radius: var(--radius-md);
  background: var(--surface);
  padding: 12px;
  margin-bottom: 12px;
  box-shadow: var(--shadow-sm);
}

.panel-block--toc {
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  padding: 0 0 10px;
}

.comment {
  border: 1px solid var(--hairline);
  border-radius: calc(var(--radius-sm) + 2px);
  background: var(--surface-soft);
  padding: 10px 12px;
  margin-top: 10px;
}

.comment-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.comment-tools {
  display: inline-flex;
  gap: 6px;
}

.btn-mini {
  min-height: 28px;
  padding: 4px 10px;
  font-size: 13px;
}

.reply-tag {
  margin-left: 6px;
  color: var(--text-quiet);
}

.comment:first-of-type {
  margin-top: 0;
}

.comment p {
  margin: 6px 0 0;
  font-size: 16px;
  line-height: 1.58;
}

.comment-form,
.panel-block {
  display: grid;
  gap: 8px;
}

:global(html[data-theme="academic"]) .article-layout:not(.embedded-mode) .article-main {
  background: var(--surface-strong);
  box-shadow: var(--card-shadow);
}

:global(html[data-theme="academic"]) .toc-item {
  font-family: var(--font-reading);
  letter-spacing: 0.01em;
}

:global(html[data-theme="academic"]) .comment {
  background: var(--surface-strong);
}

:global(html[data-theme="geek"]) .article-layout:not(.embedded-mode) .article-main,
:global(html[data-theme="geek"]) .comment {
  border-width: 2px;
}

:global(html[data-theme="geek"]) .article-demo-note {
  border-width: 2px;
}

:global(html[data-theme="geek"]) .toc-item,
:global(html[data-theme="geek"]) .panel-block h3 {
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

:global(html[data-theme="geek"]) .comment {
  box-shadow: var(--shadow-sm);
}

@media (max-width: 1260px) {
  .article-layout,
  .article-layout.embedded-mode {
    grid-template-columns: 1fr;
    gap: 14px;
  }

  .article-layout.embedded-mode .article-main,
  .article-layout.embedded-mode .side-panel--right {
    grid-column: auto;
    grid-row: auto;
  }

  .editor-layout {
    grid-template-columns: 1fr;
  }

  .editor-textarea {
    min-height: 340px;
  }

  .editor-preview {
    max-height: none;
  }

  .side-panel {
    position: static;
    max-height: none;
    overflow: visible;
    border: 0;
    padding: 0;
  }

  .side-panel--left,
  .side-panel--right,
  .article-main {
    grid-column: auto;
    grid-row: auto;
  }

  .side-content {
    margin-top: 8px;
  }

  .side-panel.collapsed .side-toggle {
    width: auto;
    min-height: 0;
    padding: 9px 14px;
    writing-mode: horizontal-tb;
  }

  .side-panel--left.collapsed .side-toggle,
  .side-panel--right.collapsed .side-toggle {
    margin: 0;
  }
}

@media (max-width: 960px) {
  .article-layout,
  .article-layout.embedded-mode {
    gap: 12px;
  }

  .toc-item {
    font-size: 15px;
  }

  .article-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .article-markdown {
    font-size: 17px;
  }

  .article-header h1 {
    font-size: clamp(26px, 8.4vw, 34px);
    line-height: 1.14;
  }

  .article-actions {
    width: 100%;
  }

  .side-panel--right {
    border-left: 0;
    padding-left: 0;
  }

  .comment-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .comment-tools {
    flex-wrap: wrap;
  }
}

@media (max-width: 620px) {
  .article-layout,
  .article-layout.embedded-mode {
    gap: 10px;
  }

  .article-header {
    gap: 10px;
  }

  .article-header h1 {
    font-size: clamp(24px, 9vw, 30px);
  }

  .article-actions {
    gap: 6px;
  }

  .panel-block {
    padding: 10px;
  }

  .panel-block h3 {
    font-size: 20px;
  }

  .comment p {
    font-size: 15px;
  }
}

</style>
