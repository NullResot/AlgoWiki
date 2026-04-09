<template>
  <section class="extra-layout">
    <article class="extra-main" v-if="isTricksPanel">
      <div class="section-title">trick技巧</div>
      <p class="meta">
        {{
          auth.isManager
            ? "管理员提交会直接发布；支持 Markdown 文本，不提供图片上传。"
            : "提交后需管理员审核通过才会对全部用户展示；支持 Markdown 文本，不提供图片上传。"
        }}
      </p>

      <section class="trick-submit card" v-if="auth.isAuthenticated">
        <h4>提交 trick</h4>
        <textarea
          class="textarea"
          v-model="trickForm.content_md"
          placeholder="使用 Markdown 编写 trick 内容"
        ></textarea>
        <button class="btn btn-accent" :disabled="submittingTrick" @click="submitTrick">
          {{ submittingTrick ? "提交中..." : "提交 trick" }}
        </button>
      </section>
      <p v-else class="meta">登录后可提交 trick。</p>

      <section class="trick-list card">
        <article class="trick-item" v-for="item in tricks" :key="item.id">
          <div class="trick-meta-row">
            <span>发布者：{{ item.author?.username || "-" }}</span>
            <span>发布时间：{{ formatTime(item.created_at) }}</span>
          </div>

          <div class="trick-action-row" v-if="canEditTrick(item) || canDeleteTrick(item) || canModerateTrick(item)">
            <span class="trick-status" v-if="showStatus(item)">状态：{{ statusText(item.status) }}</span>
            <button class="btn btn-mini" v-if="canEditTrick(item)" @click="startEditTrick(item)">
              {{ editingTrickId === item.id ? "取消编辑" : "编辑" }}
            </button>
            <button class="btn btn-mini" v-if="canDeleteTrick(item)" @click="deleteTrick(item)">删除</button>
            <button class="btn btn-mini" v-if="canModerateTrick(item)" @click="setTrickStatus(item, 'approved')">通过</button>
            <button class="btn btn-mini" v-if="canModerateTrick(item)" @click="setTrickStatus(item, 'rejected')">拒绝</button>
          </div>

          <div v-if="editingTrickId === item.id" class="trick-edit-zone">
            <textarea class="textarea" v-model="editForm.content_md"></textarea>
            <button class="btn btn-accent" :disabled="savingEdit" @click="saveEditTrick(item)">
              {{ savingEdit ? "保存中..." : "保存修改" }}
            </button>
          </div>

          <div v-else class="markdown trick-markdown" v-html="renderMarkdown(item.content_md || '')"></div>
        </article>

        <p v-if="!tricks.length" class="meta">暂无 trick 记录。</p>

        <div class="table-foot" v-if="trickMeta.next">
          <button class="btn" :disabled="trickMeta.loadingMore" @click="loadMoreTricks">
            {{ trickMeta.loadingMore ? "加载中..." : "加载更多" }}
          </button>
        </div>
      </section>
    </article>

    <article v-else class="extra-main extra-main--page">
      <header class="extra-head">
        <div class="extra-head-copy">
          <div class="section-title">{{ page?.title || fallbackPageTitle }}</div>
          <p class="meta">{{ page?.description || fallbackPageDescription }}</p>
        </div>
        <div v-if="canEditPage" class="extra-head-actions">
          <button type="button" class="btn" @click="togglePageEditor">
            {{ showPageEditor ? "收起编辑" : "编辑页面" }}
          </button>
        </div>
      </header>

      <section v-if="canEditPage && showPageEditor" class="page-editor card">
        <div class="page-editor-grid">
          <input v-model.trim="pageForm.title" class="input" placeholder="页面标题" />
          <input v-model.trim="pageForm.description" class="input" placeholder="页面简介" />
        </div>
        <textarea
          v-model="pageForm.content_md"
          class="textarea"
          placeholder="使用 Markdown 编写页面内容"
        ></textarea>
        <div class="trick-action-row">
          <button type="button" class="btn btn-accent" :disabled="savingPage" @click="savePage">
            {{ savingPage ? "保存中..." : "保存页面" }}
          </button>
          <button type="button" class="btn" :disabled="savingPage" @click="resetPageEditor">重置</button>
        </div>
      </section>

      <section class="markdown page-markdown" v-html="htmlContent"></section>
    </article>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";

import api from "../services/api";
import { renderMarkdown } from "../services/markdown";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const props = defineProps({
  slug: {
    type: String,
    default: "",
  },
});

const route = useRoute();
const auth = useAuthStore();
const ui = useUiStore();

const page = ref(null);
const pageExists = ref(false);
const tricks = ref([]);
const submittingTrick = ref(false);
const savingEdit = ref(false);
const savingPage = ref(false);
const editingTrickId = ref(null);
const showPageEditor = ref(false);

const trickForm = reactive({
  content_md: "",
});

const editForm = reactive({
  content_md: "",
});

const pageForm = reactive({
  title: "",
  description: "",
  content_md: "",
});

const trickMeta = reactive({
  count: 0,
  next: "",
  loadingMore: false,
});

const currentPageSlug = computed(() => {
  const propSlug = String(props.slug || "").trim().toLowerCase();
  if (propSlug) return propSlug;
  const routeSlug = String(route.params.slug || "").trim().toLowerCase();
  return routeSlug || "about";
});

const isTricksPanel = computed(() => currentPageSlug.value === "tricks");
const canEditPage = computed(() => !isTricksPanel.value && auth.isManager);
const fallbackPageTitle = computed(() => titleFromSlug(currentPageSlug.value));
const fallbackPageDescription = computed(() =>
  currentPageSlug.value === "about" ? "项目介绍与路线图。" : "当前页面暂未填写简介。"
);
const htmlContent = computed(() => renderMarkdown(page.value?.content_md || ""));

function titleFromSlug(slug) {
  if (slug === "about") return "关于 AlgoWiki";
  return String(slug || "新页面")
    .split(/[-_]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function statusText(status) {
  const map = {
    pending: "待审核",
    approved: "已通过",
    rejected: "已拒绝",
  };
  return map[status] || status || "-";
}

function showStatus(item) {
  return canEditTrick(item) || auth.isManager;
}

function canEditTrick(item) {
  if (!auth.user) return false;
  return auth.isManager || item.author?.id === auth.user.id;
}

function canDeleteTrick(item) {
  return canEditTrick(item);
}

function canModerateTrick(item) {
  return auth.isManager && item.status === "pending";
}

function nextPageFromUrl(url, fallback = 2) {
  if (!url) return fallback;
  try {
    return Number(new URL(url, window.location.origin).searchParams.get("page") || String(fallback));
  } catch {
    return fallback;
  }
}

function unpackListPayload(data, currentLength = 0) {
  if (Array.isArray(data)) {
    return { results: data, count: currentLength + data.length, next: "" };
  }
  return {
    results: Array.isArray(data?.results) ? data.results : [],
    count: Number.isFinite(data?.count) ? data.count : currentLength,
    next: typeof data?.next === "string" ? data.next : "",
  };
}

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  return fallback;
}

function applyPageToForm(item) {
  pageForm.title = item?.title || fallbackPageTitle.value;
  pageForm.description = item?.description || "";
  pageForm.content_md = item?.content_md || "";
}

async function loadPage() {
  if (isTricksPanel.value) return;
  page.value = null;
  pageExists.value = false;
  try {
    const { data } = await api.get(`/pages/${currentPageSlug.value}/`);
    page.value = data;
    pageExists.value = true;
    applyPageToForm(data);
  } catch {
    page.value = {
      title: fallbackPageTitle.value,
      description: fallbackPageDescription.value,
      content_md: "",
    };
    applyPageToForm(page.value);
  }
}

function resetPageEditor() {
  applyPageToForm(page.value);
}

function togglePageEditor() {
  showPageEditor.value = !showPageEditor.value;
  if (showPageEditor.value) {
    resetPageEditor();
  }
}

async function savePage() {
  if (!canEditPage.value) return;
  const title = String(pageForm.title || "").trim();
  if (!title) {
    ui.info("请填写页面标题");
    return;
  }

  savingPage.value = true;
  try {
    let data;
    const payload = {
      title,
      description: String(pageForm.description || "").trim(),
      content_md: pageForm.content_md || "",
      access_level: "public",
      is_enabled: true,
    };

    if (pageExists.value) {
      ({ data } = await api.patch(`/pages/${currentPageSlug.value}/`, payload));
    } else {
      ({ data } = await api.post("/pages/", {
        ...payload,
        slug: currentPageSlug.value,
      }));
      pageExists.value = true;
    }

    page.value = data;
    applyPageToForm(data);
    showPageEditor.value = false;
    ui.success("页面已更新");
  } catch (error) {
    ui.error(getErrorText(error, "页面保存失败"));
  } finally {
    savingPage.value = false;
  }
}

async function loadTricks(pageNo = 1, append = false) {
  const params = {
    page: pageNo,
    order: "created_newest",
  };
  const { data } = await api.get("/tricks/", { params });
  const parsed = unpackListPayload(data, tricks.value.length);
  tricks.value = append ? [...tricks.value, ...parsed.results] : parsed.results;
  trickMeta.count = parsed.count;
  trickMeta.next = parsed.next;
}

async function loadMoreTricks() {
  if (!trickMeta.next || trickMeta.loadingMore) return;
  trickMeta.loadingMore = true;
  try {
    await loadTricks(nextPageFromUrl(trickMeta.next), true);
  } finally {
    trickMeta.loadingMore = false;
  }
}

function startEditTrick(item) {
  if (editingTrickId.value === item.id) {
    editingTrickId.value = null;
    editForm.content_md = "";
    return;
  }
  editingTrickId.value = item.id;
  editForm.content_md = item.content_md || "";
}

async function saveEditTrick(item) {
  if (!canEditTrick(item)) return;
  const content = editForm.content_md.trim();
  if (!content) {
    ui.info("内容不能为空");
    return;
  }
  if (savingEdit.value) return;

  savingEdit.value = true;
  try {
    await api.patch(`/tricks/${item.id}/`, {
      content_md: content,
    });
    editingTrickId.value = null;
    editForm.content_md = "";
    ui.success(auth.isManager ? "已更新 trick" : "已提交修改，等待审核");
    await loadTricks(1, false);
  } catch (error) {
    ui.error(getErrorText(error, "保存失败"));
  } finally {
    savingEdit.value = false;
  }
}

async function deleteTrick(item) {
  if (!canDeleteTrick(item)) return;
  if (!window.confirm("确认删除该 trick？")) return;
  try {
    await api.delete(`/tricks/${item.id}/`);
    ui.success("已删除");
    if (editingTrickId.value === item.id) {
      editingTrickId.value = null;
      editForm.content_md = "";
    }
    await loadTricks(1, false);
  } catch (error) {
    ui.error(getErrorText(error, "删除失败"));
  }
}

async function setTrickStatus(item, status) {
  if (!canModerateTrick(item)) return;
  try {
    await api.post(`/tricks/${item.id}/set-status/`, { status });
    ui.success(status === "approved" ? "已通过审核" : "已拒绝");
    await loadTricks(1, false);
  } catch (error) {
    ui.error(getErrorText(error, "审核操作失败"));
  }
}

async function submitTrick() {
  if (!auth.isAuthenticated) {
    ui.info("请先登录后再提交 trick");
    return;
  }
  if (submittingTrick.value) return;

  const content = trickForm.content_md.trim();
  if (!content) {
    ui.info("请填写 Markdown 内容");
    return;
  }

  submittingTrick.value = true;
  try {
    const { data } = await api.post("/tricks/", { content_md: content });
    trickForm.content_md = "";
    if (data?.status === "pending") {
      ui.success("trick 提交成功，等待审核");
    } else {
      ui.success("trick 已发布");
    }
    await loadTricks(1, false);
  } catch (error) {
    ui.error(getErrorText(error, "trick 提交失败"));
  } finally {
    submittingTrick.value = false;
  }
}

watch(
  () => currentPageSlug.value,
  async () => {
    showPageEditor.value = false;
    if (isTricksPanel.value) {
      if (!tricks.value.length) {
        await loadTricks();
      }
      return;
    }
    await loadPage();
  },
  { immediate: true }
);

onMounted(async () => {
  if (isTricksPanel.value && !tricks.value.length) {
    await loadTricks();
  }
});
</script>

<style scoped>
.extra-layout {
  display: block;
}

.extra-main {
  border: 1px solid var(--hairline);
  border-radius: 16px;
  background: var(--surface);
  padding: 18px;
  box-shadow: var(--shadow-sm);
}

.extra-main--page {
  display: grid;
  gap: 14px;
}

.extra-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.extra-head-copy {
  min-width: 0;
}

.extra-head-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.page-editor {
  padding: 14px;
  display: grid;
  gap: 10px;
}

.page-editor-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.page-markdown {
  min-width: 0;
}

.page-markdown :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 10px;
}

.trick-submit {
  margin-top: 12px;
  padding: 14px;
  display: grid;
  gap: 8px;
}

.trick-submit h4 {
  margin: 0;
  font-size: 20px;
}

.trick-list {
  margin-top: 12px;
  padding: 10px;
  display: grid;
  gap: 10px;
}

.trick-item {
  border-bottom: 1px solid var(--hairline);
  padding: 8px 0 12px;
}

.trick-item:last-child {
  border-bottom: 0;
}

.trick-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 8px;
}

.trick-action-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.trick-status {
  font-size: 12px;
  color: var(--muted);
  margin-right: 4px;
}

.trick-edit-zone {
  display: grid;
  gap: 8px;
}

.trick-markdown {
  max-width: 100%;
}

.trick-markdown :deep(img) {
  max-width: 100%;
  border-radius: 8px;
  height: auto;
}

.table-foot {
  margin-top: 6px;
}

@media (max-width: 720px) {
  .extra-main {
    padding: 14px;
  }

  .extra-head {
    flex-direction: column;
  }

  .extra-head-actions,
  .extra-head-actions .btn {
    width: 100%;
  }

  .page-editor-grid {
    grid-template-columns: 1fr;
  }

  .trick-submit,
  .trick-list {
    padding: 12px;
  }
}

@media (max-width: 560px) {
  .trick-meta-row {
    display: grid;
    gap: 4px;
  }

  .trick-action-row {
    gap: 6px;
  }

  .trick-action-row .btn {
    flex: 1 1 calc(50% - 6px);
  }
}

.trick-submit,
.trick-list,
.page-editor {
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  backdrop-filter: none;
  padding: 18px 0;
}

.trick-submit,
.page-editor,
.page-markdown,
.trick-list {
  border-top: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
}

.trick-item {
  padding: 18px 0;
  border-bottom: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
}

.trick-item:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.page-markdown {
  padding-top: 18px;
}
</style>
