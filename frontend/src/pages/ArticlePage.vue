<template>
  <div class="article-page-root">
    <section v-if="!embeddedMode && loadingArticle && !article" class="article-state-card card">
      <SkeletonBlock :lines="6" :line-height="20" label="正在加载条目内容" />
    </section>

    <section v-else-if="!embeddedMode && articleLoadError && !article" class="article-state-card">
      <EmptyErrorState
        tone="error"
        title="条目暂时无法加载"
        :description="articleLoadError"
        action-label="重新加载"
        @action="initPage"
      />
      <div class="article-state-back">
        <RouterLink class="btn btn-mini" :to="{ name: 'wiki' }">返回竞赛 Wiki</RouterLink>
      </div>
    </section>

    <section
      v-else-if="article"
      class="article-layout"
      :class="{
        'editor-mode': showEditor,
        'left-collapsed': leftCollapsed,
        'right-collapsed': rightCollapsed,
        'embedded-mode': embeddedMode,
      }"
    >
      <Transition name="aw-swap" mode="out-in">
        <article v-if="showEditor" key="editor" class="editor-shell">
          <header class="editor-header">
            <h2>编辑条目（{{ directPublishEdit ? "直接发布" : "提交审核" }}）</h2>
            <div class="article-actions">
              <button type="button" class="btn" :disabled="savingEdit" @click="cancelEditor">取消</button>
              <button type="button" class="btn btn-accent" :disabled="savingEdit" @click="saveArticleEdit">
                {{ savingEdit ? "提交中..." : directPublishEdit ? "保存并发布" : "提交审核" }}
              </button>
            </div>
          </header>

          <div class="editor-meta">
            <input class="input" v-model="editForm.title" placeholder="条目标题" aria-label="条目标题" />
            <textarea class="textarea" v-model="editForm.summary" placeholder="条目摘要（可选）" aria-label="条目摘要"></textarea>
            <input
              class="input"
              v-model="editReason"
              :placeholder="directPublishEdit ? '修订说明（可选）' : '修订说明（会进入审核区）'"
              aria-label="修订说明"
            />
          </div>

          <section class="editor-layout">
            <article class="editor-pane card">
              <h3>Markdown 原文</h3>
              <textarea
                class="textarea editor-textarea"
                v-model="editForm.content_md"
                placeholder="在这里编辑 Markdown 原文"
                aria-label="Markdown 正文"
              ></textarea>
            </article>
            <article class="editor-pane card">
              <h3>渲染预览</h3>
              <div ref="editorPreviewRef" class="markdown editor-preview" v-html="editorPreviewHtml"></div>
            </article>
          </section>
        </article>

        <div v-else key="reader" class="article-reader-shell">
          <aside v-if="!embeddedMode" class="side-panel side-panel--left" :class="{ collapsed: leftCollapsed }">
            <button
              type="button"
              class="side-toggle btn"
              :aria-expanded="!leftCollapsed"
              @click="leftCollapsed = !leftCollapsed"
            >
              {{ leftCollapsed ? "展开目录" : "折叠目录" }}
            </button>
            <div v-show="!leftCollapsed" class="side-content">
              <section class="panel-block panel-block--toc">
                <h3>本文目录</h3>
                <div v-for="item in tocVisibleItems" :key="item.id" class="toc-row" :style="{ paddingLeft: `${item.depth * 14}px` }">
                  <button
                    v-if="item.hasChildren"
                    class="toc-toggle"
                    type="button"
                    :aria-expanded="item.isExpanded"
                    aria-label="展开或收起子标题"
                    @click.stop="toggleTocExpand(item.id)"
                  >
                    <span class="aw-chevron" :class="{ 'is-open': item.isExpanded }" aria-hidden="true">▸</span>
                  </button>
                  <span v-else class="toc-toggle toc-toggle--placeholder"></span>
                  <a :href="`#${item.id}`" class="toc-item" @click.prevent="scrollToArticleAnchor(item.id)">{{ item.text }}</a>
                </div>
                <p v-if="!tocVisibleItems.length" class="meta">当前正文暂无子标题目录。</p>
              </section>
            </div>
          </aside>

          <article class="article-main">
            <header class="article-header">
              <h1>{{ article.title }}</h1>
              <div class="article-actions">
                <span v-if="articleCategoryLabel" class="pill">{{ articleCategoryLabel }}</span>
                <span v-if="isDemoArticle" class="pill article-demo-pill">开发环境示例</span>
                <button
                  v-if="auth.isAuthenticated && !isDemoArticle"
                  type="button"
                  class="btn"
                  :class="{ 'is-starred-btn': article.is_starred }"
                  :disabled="starring"
                  :aria-pressed="Boolean(article.is_starred)"
                  @click="toggleStar"
                >
                  <Transition name="aw-icon" mode="out-in">
                    <span :key="article.is_starred ? 'starred' : 'unstarred'">
                      {{ article.is_starred ? "★ 已收藏" : "☆ 收藏" }}
                    </span>
                  </Transition>
                  <span class="tabular-nums">({{ article.star_count }})</span>
                </button>
                <button v-if="auth.isAuthenticated && !isDemoArticle" type="button" class="btn" @click="openEditor">
                  {{ canModerateArticle ? "编辑条目" : "修改条目" }}
                </button>
                <button
                  v-if="canDeleteArticle && !isDemoArticle"
                  type="button"
                  class="btn btn-danger"
                  :disabled="deletingArticle"
                  @click="removeArticle"
                >
                  {{ deletingArticle ? "删除中..." : "删除条目" }}
                </button>
                <button
                  v-if="canModerateArticle && article.status !== 'published' && !isDemoArticle"
                  type="button"
                  class="btn btn-accent"
                  :disabled="publishingArticle"
                  @click="publishArticle"
                >
                  {{ publishingArticle ? "发布中..." : "发布" }}
                </button>
              </div>
            </header>

            <div class="article-meta-stack">
              <div class="article-meta-row">
                <ContributorsPanel :contributors="articleContributors" />
                <p class="meta article-updated-at tabular-nums">更新于 {{ formatTime(article.updated_at) }}</p>
              </div>
            </div>
            <p v-if="article.summary" class="article-summary">{{ article.summary }}</p>
            <div v-if="isDemoArticle" class="article-demo-note">
              当前正文为本地验收用演示内容，仅在开发环境兜底展示，不会写入正式站点。
            </div>
            <section ref="articleMarkdownRef" class="markdown article-markdown" v-html="renderedHtml"></section>
          </article>

          <aside class="side-panel side-panel--right" :class="{ collapsed: rightCollapsed }">
            <button
              type="button"
              class="side-toggle btn"
              :aria-expanded="!rightCollapsed"
              @click="rightCollapsed = !rightCollapsed"
            >
              {{ rightCollapsed ? `展开评论 (${comments.length})` : `收起评论 (${comments.length})` }}
            </button>
            <Transition name="aw-collapse">
              <div v-show="!rightCollapsed" class="side-content">
                <section class="panel-block">
                  <h3>评论 <span class="meta tabular-nums">({{ comments.length }})</span></h3>
                  <article class="comment" v-for="item in comments" :key="item.id">
                    <div class="comment-head">
                      <div class="meta">
                        {{ item.author.username }} · <span class="tabular-nums">{{ formatTime(item.created_at) }}</span>
                        <span v-if="item.parent" class="reply-tag">回复 {{ resolveReplyAuthor(item.parent) }}</span>
                        <span v-if="item.status === 'pending'" class="reply-tag">待审核</span>
                      </div>
                      <div class="comment-tools" v-if="auth.isAuthenticated && !isDemoArticle">
                        <button type="button" class="btn btn-mini" v-if="item.status === 'visible'" @click="startReply(item)">回复</button>
                        <button
                          type="button"
                          class="btn btn-mini btn-danger"
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
                    <Transition name="aw-collapse">
                      <p class="meta reply-banner" v-if="replyTarget">
                        正在回复 @{{ replyTarget.author.username }}
                        <button type="button" class="btn btn-mini" @click="cancelReply">取消回复</button>
                      </p>
                    </Transition>
                    <textarea
                      ref="commentInputRef"
                      class="textarea"
                      v-model="newComment"
                      placeholder="写下你的评论（Ctrl/Cmd + Enter 提交）"
                      aria-label="评论内容"
                      @keydown="handleCommentKeydown"
                    ></textarea>
                    <button
                      type="button"
                      class="btn btn-accent"
                      :disabled="submittingComment || !newComment.trim()"
                      @click="submitComment"
                    >
                      {{ submittingComment ? "提交中..." : replyTarget ? "提交回复" : "提交评论" }}
                    </button>
                  </div>
                  <p v-else-if="isDemoArticle" class="meta">演示文章的评论区为只读样本，用于本地验收布局。</p>
                  <p v-else class="meta">
                    <RouterLink class="comment-login-link" :to="{ name: 'auth', query: { redirect: route.fullPath } }">
                      登录后可发表评论
                    </RouterLink>
                  </p>
                </section>
              </div>
            </Transition>
          </aside>
        </div>
      </Transition>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import ContributorsPanel from "../components/ContributorsPanel.vue";
import EmptyErrorState from "../components/EmptyErrorState.vue";
import SkeletonBlock from "../components/SkeletonBlock.vue";
import { useMarkdownCodeCopy } from "../composables/useMarkdownCodeCopy";
import { useRequestControllers } from "../composables/useRequestControllers";
import { useUnsavedGuard } from "../composables/useUnsavedGuard";
import api, { isRequestCanceled } from "../services/api";
import { renderMarkdown } from "../services/markdown";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";
import { extractApiError, formatDate } from "../utils/format";
import { safeScrollIntoView } from "../utils/motion";

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
const requests = useRequestControllers();

const embeddedMode = computed(() => Boolean(props.embedded));
const articleId = computed(() => {
  const propId = props.id == null ? "" : String(props.id).trim();
  if (propId) return propId;
  return String(route.params.id || "");
});

const article = ref(null);
const loadingArticle = ref(false);
const articleLoadError = ref("");
const comments = ref([]);
const newComment = ref("");
const renderedHtml = ref("");
const editorPreviewHtml = ref("");
const tocTree = ref([]);
const tocExpandedIds = ref(new Set());
const showEditor = ref(false);
const savingEdit = ref(false);
const deletingArticle = ref(false);
const starring = ref(false);
const publishingArticle = ref(false);
const submittingComment = ref(false);
const deletingCommentId = ref(null);
const replyingToCommentId = ref(null);
const leftCollapsed = ref(false);
const rightCollapsed = ref(true);
const editReason = ref("");
const articleMarkdownRef = ref(null);
const editorPreviewRef = ref(null);
const commentInputRef = ref(null);
let previewDebounceTimer = null;

const editForm = reactive({
  title: "",
  summary: "",
  content_md: "",
});
const editBase = reactive({
  title: "",
  summary: "",
  content_md: "",
  updated_at: "",
});

const isEditorDirty = computed(() => {
  if (!showEditor.value) return false;
  return (
    editForm.title !== editBase.title ||
    editForm.summary !== editBase.summary ||
    editForm.content_md !== editBase.content_md ||
    Boolean(editReason.value.trim())
  );
});

const { confirmDiscard } = useUnsavedGuard(isEditorDirty, {
  guardRoute: !embeddedMode.value,
  title: "放弃未保存的条目编辑？",
  message: "当前修改尚未提交，离开后编辑内容将会丢失。",
});

useMarkdownCodeCopy(articleMarkdownRef, renderedHtml);
useMarkdownCodeCopy(editorPreviewRef, editorPreviewHtml);

const canModerateArticle = computed(() => Boolean(article.value?.can_edit));
const canDeleteArticle = computed(() => auth.isManager && Boolean(article.value?.id));
const directPublishEdit = computed(() => auth.isManager && canModerateArticle.value);
const isDemoArticle = computed(() => Boolean(article.value?.__demo));
const articleCategoryLabel = computed(() =>
  String(article.value?.category_name || "")
    .replace(/^\s*\d+(?:\.\d+)*\s*[.．、]\s*/u, "")
    .trim()
);
const articleContributors = computed(() => {
  if (Array.isArray(article.value?.contributors) && article.value.contributors.length) {
    return article.value.contributors;
  }
  if (!article.value?.author) {
    return [];
  }
  const fallbackTime = article.value?.published_at || article.value?.created_at || article.value?.updated_at || null;
  return [
    {
      user: article.value.author,
      is_creator: true,
      approved_revision_count: 0,
      first_contributed_at: fallbackTime,
      last_contributed_at: fallbackTime,
    },
  ];
});
const replyTarget = computed(() =>
  comments.value.find((item) => item.id === replyingToCommentId.value) || null
);
const tocVisibleItems = computed(() => flattenVisibleToc(tocTree.value, tocExpandedIds.value));

watch(
  () => [showEditor.value, editForm.content_md],
  ([editing, md]) => {
    if (!editing) {
      if (previewDebounceTimer) {
        window.clearTimeout(previewDebounceTimer);
        previewDebounceTimer = null;
      }
      return;
    }
    if (previewDebounceTimer) window.clearTimeout(previewDebounceTimer);
    if (!editorPreviewHtml.value) {
      editorPreviewHtml.value = renderMarkdown(md || "");
      return;
    }
    previewDebounceTimer = window.setTimeout(() => {
      editorPreviewHtml.value = renderMarkdown(md || "");
      previewDebounceTimer = null;
    }, 180);
  },
  { immediate: true }
);

onBeforeUnmount(() => {
  if (previewDebounceTimer) {
    window.clearTimeout(previewDebounceTimer);
    previewDebounceTimer = null;
  }
});

function normalizeAnchorText(text) {
  return text
    .trim()
    .toLowerCase()
    .replace(/[^\w\u4e00-\u9fa5\s-]/g, "")
    .replace(/\s+/g, "-")
    .slice(0, 64);
}

function buildRenderedContent(content, articleData = null) {
  const html = renderMarkdown(content || "");
  const parser = new DOMParser();
  const doc = parser.parseFromString(`<div id=\"__root\">${html}</div>`, "text/html");
  const root = doc.getElementById("__root");
  const headings = root ? [...root.querySelectorAll("h1, h2, h3, h4, h5, h6")] : [];

  const idMap = new Map();
  const embeddedPrefix =
    embeddedMode.value && articleData?.id ? `article-${String(articleData.id).trim()}-` : "";
  const flatTocItems = headings.map((heading) => {
    const text = heading.textContent || "";
    const base = normalizeAnchorText(text) || "section";
    const count = idMap.get(base) || 0;
    const nextCount = count + 1;
    idMap.set(base, nextCount);
    const normalizedId = nextCount === 1 ? base : `${base}-${nextCount}`;
    const id = embeddedPrefix ? `${embeddedPrefix}${normalizedId}` : normalizedId;

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

async function scrollToRouteHash() {
  if (embeddedMode.value || !route.hash) return;
  await nextTick();
  window.setTimeout(() => {
    const anchorId = decodeURIComponent(String(route.hash || "").replace(/^#/, ""));
    if (!anchorId) return;
    safeScrollIntoView(document.getElementById(anchorId), { behavior: "smooth", block: "start" });
  }, 80);
}

function scrollToArticleAnchor(anchorId) {
  if (!anchorId) return;
  safeScrollIntoView(document.getElementById(anchorId), { behavior: "smooth", block: "start" });
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
  void nodes;
  return new Set();
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
  return formatDate(value);
}

function resolveReplyAuthor(parentId) {
  const parent = comments.value.find((item) => item.id === parentId);
  return parent?.author?.username ? `@${parent.author.username}` : `#${parentId}`;
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
  buildRenderedContent(data.content_md, data);
  void scrollToRouteHash();
  syncEditForm(data);
  if (data.__demo) {
    comments.value = Array.isArray(data.demo_comments) ? data.demo_comments : [];
  }
}

async function loadArticle() {
  const id = articleId.value;
  articleLoadError.value = "";
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
  const controller = requests.replace("article");
  loadingArticle.value = true;
  try {
    const { data } = await api.get(`/articles/${id}/`, {
      signal: controller.signal,
    });
    if (!requests.isCurrent("article", controller)) return;
    applyArticleData(data);
  } catch (error) {
    if (isRequestCanceled(error) || !requests.isCurrent("article", controller)) return;
    if (props.articleData && String(props.articleData.id) === String(id)) {
      return;
    }
    const message = extractApiError(error, "条目加载失败，请稍后重试");
    articleLoadError.value = message;
    ui.error(message);
  } finally {
    if (requests.release("article", controller) || !article.value) {
      loadingArticle.value = false;
    }
  }
}

function syncEditForm(data) {
  editForm.title = data?.title || "";
  editForm.summary = data?.summary || "";
  editForm.content_md = data?.content_md || "";
  editBase.title = data?.title || "";
  editBase.summary = data?.summary || "";
  editBase.content_md = data?.content_md || "";
  editBase.updated_at = data?.updated_at || "";
}

function applyMergeConflictToEditor(error) {
  const payload = error?.response?.data;
  const merge = payload?.merge;
  if (error?.response?.status !== 409 || payload?.code !== "revision_merge_conflict" || !merge) {
    return false;
  }

  editForm.title = merge?.merged?.title ?? editForm.title;
  editForm.summary = merge?.merged?.summary ?? editForm.summary;
  editForm.content_md = merge?.merged?.content_md ?? editForm.content_md;
  editBase.title = merge?.current?.title ?? editBase.title;
  editBase.summary = merge?.current?.summary ?? editBase.summary;
  editBase.content_md = merge?.current?.content_md ?? editBase.content_md;
  editBase.updated_at = merge?.current?.updated_at ?? editBase.updated_at;
  showEditor.value = true;
  ui.error(payload?.detail || "条目已有新版本，已把合并结果放回编辑器，请处理冲突标记后重新提交。");
  return true;
}

async function loadComments() {
  const id = articleId.value;
  if (!id) {
    requests.cancel("comments");
    comments.value = [];
    return;
  }
  if (props.articleData?.__demo) {
    requests.cancel("comments");
    comments.value = Array.isArray(props.articleData.demo_comments) ? props.articleData.demo_comments : [];
    return;
  }
  const controller = requests.replace("comments");
  try {
    const { data } = await api.get("/comments/", {
      params: { article: id },
      signal: controller.signal,
    });
    if (!requests.isCurrent("comments", controller)) return;
    comments.value = data.results || data;
    if (replyingToCommentId.value && !comments.value.some((item) => item.id === replyingToCommentId.value)) {
      replyingToCommentId.value = null;
    }
  } catch (error) {
    if (isRequestCanceled(error) || !requests.isCurrent("comments", controller)) return;
    ui.error(getErrorText(error, "评论加载失败"));
  } finally {
    requests.release("comments", controller);
  }
}

function canDeleteComment(comment) {
  if (!auth.user) return false;
  return auth.isManager || comment.author.id === auth.user.id;
}

function startReply(comment) {
  replyingToCommentId.value = comment.id;
  rightCollapsed.value = false;
  nextTick(() => {
    safeScrollIntoView(commentInputRef.value, { behavior: "smooth", block: "nearest" });
    commentInputRef.value?.focus?.();
  });
}

function cancelReply() {
  replyingToCommentId.value = null;
}

function handleCommentKeydown(event) {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    submitComment();
  }
}

async function toggleStar() {
  if (!article.value || isDemoArticle.value || starring.value) return;
  starring.value = true;
  const previousStarred = Boolean(article.value.is_starred);
  const previousCount = Number(article.value.star_count || 0);
  article.value.is_starred = !previousStarred;
  article.value.star_count = previousStarred ? Math.max(0, previousCount - 1) : previousCount + 1;

  try {
    if (previousStarred) {
      await api.post(`/articles/${article.value.id}/unstar/`);
      ui.success("已取消收藏");
    } else {
      await api.post(`/articles/${article.value.id}/star/`);
      ui.success("已收藏");
    }
  } catch (error) {
    article.value.is_starred = previousStarred;
    article.value.star_count = previousCount;
    ui.error(extractApiError(error, "收藏操作失败"));
  } finally {
    starring.value = false;
  }
}

async function publishArticle() {
  if (!article.value || isDemoArticle.value || publishingArticle.value) return;
  publishingArticle.value = true;
  try {
    await api.post(`/articles/${article.value.id}/publish/`);
    ui.success("文章已发布");
    await loadArticle();
  } catch (error) {
    ui.error(extractApiError(error, "发布失败"));
  } finally {
    publishingArticle.value = false;
  }
}

async function removeArticle() {
  if (!article.value || isDemoArticle.value || !canDeleteArticle.value || deletingArticle.value) return;
  const confirmed = await ui.confirm({
    title: "删除当前条目？",
    message: `确定删除《${article.value.title}》吗？删除后将无法恢复。`,
    confirmText: "确认删除",
    cancelText: "取消",
    tone: "danger",
  });
  if (!confirmed) return;

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
    ui.error(extractApiError(error, "删除条目失败"));
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
  editorPreviewHtml.value = renderMarkdown(editForm.content_md || "");
  editReason.value = "";
  showEditor.value = true;
}

async function cancelEditor() {
  if (!(await confirmDiscard())) return;
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
      base_title: editBase.title,
      base_summary: editBase.summary,
      base_content_md: editBase.content_md,
      base_updated_at: editBase.updated_at || null,
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
    if (applyMergeConflictToEditor(error)) {
      return;
    }
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
  const confirmed = await ui.confirm({
    title: "删除这条评论？",
    message: "删除后其他用户将无法查看此评论。",
    confirmText: "删除",
    cancelText: "取消",
    tone: "danger",
  });
  if (!confirmed) return;
  deletingCommentId.value = comment.id;
  try {
    await api.delete(`/comments/${comment.id}/`);
    comments.value = comments.value.filter((item) => item.id !== comment.id);
    if (replyingToCommentId.value === comment.id) {
      replyingToCommentId.value = null;
    }
    ui.success("评论已删除");
    await loadComments();
  } catch (error) {
    ui.error(extractApiError(error, "删除评论失败"));
  } finally {
    deletingCommentId.value = null;
  }
}

function getErrorText(error, fallback = "操作失败") {
  return extractApiError(error, fallback);
}

async function initPage() {
  showEditor.value = false;
  await loadArticle();
  if (!isDemoArticle.value && article.value) {
    await loadComments();
  }
}

watch(
  () => [articleId.value, props.articleData?.updated_at, props.articleData?.content_md, props.articleData?.id],
  async (nextTuple, prevTuple) => {
    const [next, nextUpdatedAt, nextContent] = nextTuple;
    const [prev, prevUpdatedAt, prevContent] = Array.isArray(prevTuple) ? prevTuple : [];
    if (!next) {
      applyArticleData(props.articleData);
      return;
    }
    if (next === prev && nextUpdatedAt === prevUpdatedAt && nextContent === prevContent) {
      return;
    }
    if (next === prev && props.articleData) {
      applyArticleData(props.articleData);
      return;
    }
    await initPage();
  },
  { immediate: true }
);

watch(
  () => route.hash,
  () => {
    void scrollToRouteHash();
  }
);
</script>

<style scoped>
.article-page-root {
  min-width: 0;
}

.article-state-card {
  max-width: 780px;
  margin: 24px auto;
  padding: 24px;
  display: grid;
  gap: 14px;
}

.article-state-back {
  display: flex;
  justify-content: center;
}

.article-layout {
  min-width: 0;
}

.article-reader-shell {
  display: grid;
  --left-width: 260px;
  --right-width: 360px;
  grid-template-columns: var(--left-width) minmax(0, 1fr) var(--right-width);
  gap: clamp(24px, 3vw, 42px);
}

.article-layout.embedded-mode .article-reader-shell {
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

.article-layout.left-collapsed .article-reader-shell {
  --left-width: 46px;
}

.article-layout.right-collapsed .article-reader-shell {
  --right-width: 46px;
}

.is-starred-btn {
  border-color: color-mix(in srgb, var(--accent) 44%, var(--hairline));
  background: color-mix(in srgb, var(--accent) 12%, var(--surface-strong));
  color: var(--accent);
}

.reply-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.comment-login-link {
  color: var(--accent);
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 2px;
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
  font-size: 90%;
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
  font-size: clamp(42px, 5.4vw, 72px);
  line-height: 1.02;
}

.article-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.article-meta-stack {
  display: grid;
  gap: 10px;
  margin: 2px 0 12px;
}

.article-meta-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.contributors-toggle {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 42px;
  padding: 8px 14px;
  border: 1px solid color-mix(in srgb, var(--hairline) 92%, transparent);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--surface-soft) 84%, white 16%);
  color: var(--text-strong);
  font: inherit;
  cursor: pointer;
  transition: border-color 0.18s ease, background-color 0.18s ease, color 0.18s ease;
}

.contributors-toggle:hover,
.contributors-toggle.is-open {
  border-color: color-mix(in srgb, var(--accent) 38%, var(--hairline));
  background: color-mix(in srgb, var(--accent) 8%, var(--surface-soft));
}

.contributors-toggle-title {
  font-weight: 600;
}

.contributors-toggle-count,
.contributors-toggle-icon {
  color: var(--text-quiet);
}

.article-updated-at {
  margin: 0;
}

.contributors-panel {
  max-width: 760px;
  border: 1px solid color-mix(in srgb, var(--hairline) 92%, transparent);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--surface-soft) 92%, white 8%);
  padding: 12px;
}

.contributors-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(118px, 1fr));
  gap: 10px;
}

.contributors-item {
  display: grid;
  justify-items: center;
  gap: 8px;
  min-width: 0;
  padding: 14px 10px;
  border: 1px solid color-mix(in srgb, var(--hairline) 88%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--surface-strong) 76%, white 24%);
  text-align: center;
}

.contributors-item-head {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
  width: 100%;
}

.contributors-avatar {
  width: 48px;
  height: 48px;
  border-radius: 999px;
  object-fit: cover;
  background: color-mix(in srgb, var(--accent) 12%, var(--surface-soft));
  border: 1px solid color-mix(in srgb, var(--hairline) 78%, transparent);
}

.contributors-name {
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.contributors-item-meta {
  display: -webkit-box;
  min-height: 38px;
  margin: 0;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-height: 1.5;
}

.contributors-badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 2px 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent) 14%, transparent);
  color: var(--accent);
  font-size: 13px;
  font-weight: 600;
}

.article-summary {
  margin: 8px 0 16px;
  color: var(--text-soft);
  font-size: 16px;
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
  font-size: 14px;
}

.article-markdown {
  font-size: clamp(0.92rem, 0.855rem + 0.27vw, 1.04rem);
}

.article-markdown :deep(h1) {
  font-size: clamp(2rem, 3.4vw, 2.9rem);
  line-height: 1.12;
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
  .article-reader-shell,
  .article-layout.embedded-mode .article-reader-shell {
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
    font-size: 15px;
  }

  .article-header h1 {
    font-size: clamp(32px, 8.4vw, 46px);
    line-height: 1.06;
  }

  .article-markdown :deep(h1) {
    font-size: clamp(24px, 6vw, 34px);
  }

  .article-actions {
    width: 100%;
  }

  .article-meta-row {
    align-items: flex-start;
    gap: 10px;
  }

  .contributors-toggle {
    width: 100%;
    justify-content: space-between;
  }

  .contributors-panel {
    max-width: none;
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
    font-size: clamp(30px, 9vw, 38px);
  }

  .article-markdown :deep(h1) {
    font-size: clamp(22px, 7vw, 30px);
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

.article-layout {
  gap: clamp(24px, 3vw, 42px);
}

.article-layout:not(.embedded-mode) .article-main,
:global(html[data-theme="academic"]) .article-layout:not(.embedded-mode) .article-main,
:global(html[data-theme="geek"]) .article-layout:not(.embedded-mode) .article-main {
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  padding: clamp(6px, 1.2vw, 14px) 0 0;
}

.article-summary {
  max-width: 72ch;
}

.side-panel {
  padding-top: 4px;
}

.side-panel--left {
  border-right: 1px solid color-mix(in srgb, var(--hairline) 82%, transparent);
  padding-right: 16px;
}

.side-panel--right {
  border-left: 1px solid color-mix(in srgb, var(--hairline) 82%, transparent);
  padding-left: 16px;
}

.panel-block {
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  padding: 0 0 18px;
  margin-bottom: 18px;
}

.panel-block + .panel-block {
  border-top: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
  padding-top: 18px;
}

.panel-block--toc {
  padding-bottom: 0;
}

.comment {
  border: 0;
  border-bottom: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  padding: 0 0 16px;
  margin-top: 16px;
}

:global(html[data-theme="academic"]) .comment,
:global(html[data-theme="geek"]) .comment {
  background: transparent;
  box-shadow: none;
  border-width: 0 0 1px 0;
}

.comment:last-of-type {
  border-bottom: 0;
  padding-bottom: 0;
}

.comment-form {
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
}

.article-markdown :deep(table) {
  border-collapse: collapse;
  border-spacing: 0;
  border: 0;
  border-top: 2px solid color-mix(in srgb, var(--text-strong) 76%, transparent);
  border-bottom: 2px solid color-mix(in srgb, var(--text-strong) 76%, transparent);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.article-markdown :deep(th),
.article-markdown :deep(td) {
  border: 0;
  border-bottom: 1px solid color-mix(in srgb, var(--hairline-strong) 88%, transparent);
  background: transparent;
  padding: 10px 12px;
}

.article-markdown :deep(th + th),
.article-markdown :deep(td + td) {
  border-left: 1px solid color-mix(in srgb, var(--hairline) 92%, transparent);
}

.article-markdown :deep(thead th) {
  background: var(--table-head-bg);
}

.article-markdown :deep(tbody tr:nth-child(odd)),
.article-markdown :deep(tbody tr:nth-child(even)) {
  background: transparent;
}

.article-markdown :deep(img) {
  background: transparent;
  box-shadow: none;
}

@media (max-width: 1260px) {
  .side-panel {
    padding-top: 0;
  }

  .side-panel--left,
  .side-panel--right {
    border: 0;
    padding: 0;
  }
}

@media (max-width: 960px) {
  .article-layout:not(.embedded-mode) .article-main {
    padding-top: 0;
  }

  .comment-form {
    margin-top: 14px;
    padding-top: 14px;
  }
}
</style>
