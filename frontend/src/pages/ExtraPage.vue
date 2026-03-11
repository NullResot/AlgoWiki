<template>
  <section class="extra-layout">
    <article class="extra-main" v-if="activePanel === 'tricks'">
      <div class="section-title">trick技巧</div>
      <p class="meta">
        {{ auth.isManager ? "管理员提交会直接发布；支持 Markdown 与图片。" : "提交后需管理员审核通过才会对全部用户展示；支持 Markdown 与图片。" }}
      </p>

      <section class="trick-submit card" v-if="auth.isAuthenticated">
        <h4>提交 trick</h4>
        <ImageUploadHelper label="上传图片并插入 Markdown" @uploaded="onTrickImageUploaded" />
        <textarea
          class="textarea"
          v-model="trickForm.content_md"
          placeholder="使用 Markdown 编写，可直接插入图片：![说明](/wiki-assets/xxx.png)"
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
            <ImageUploadHelper label="上传图片并插入 Markdown" @uploaded="onEditTrickImageUploaded" />
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

    <article class="extra-main" v-else>
      <div class="section-title">{{ page?.title || "关于 AlgoWiki" }}</div>
      <p class="meta">{{ page?.description || "项目介绍与路线图。" }}</p>
      <section class="markdown" v-html="htmlContent"></section>
    </article>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";

import ImageUploadHelper from "../components/ImageUploadHelper.vue";
import api from "../services/api";
import { renderMarkdown } from "../services/markdown";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const route = useRoute();
const auth = useAuthStore();
const ui = useUiStore();

const activePanel = ref("tricks");
const page = ref(null);
const tricks = ref([]);
const submittingTrick = ref(false);
const savingEdit = ref(false);
const editingTrickId = ref(null);

const trickForm = reactive({
  content_md: "",
});

const editForm = reactive({
  content_md: "",
});

const trickMeta = reactive({
  count: 0,
  next: "",
  loadingMore: false,
});

const htmlContent = computed(() => renderMarkdown(page.value?.content_md || ""));

function appendMarkdown(target, snippet) {
  const next = String(snippet || "").trim();
  if (!next) return String(target || "");
  const base = String(target || "");
  return base ? `${base}\n\n${next}\n` : `${next}\n`;
}

function onTrickImageUploaded(payload) {
  trickForm.content_md = appendMarkdown(trickForm.content_md, payload?.markdown);
}

function onEditTrickImageUploaded(payload) {
  editForm.content_md = appendMarkdown(editForm.content_md, payload?.markdown);
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
  return item.author?.id === auth.user.id;
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

function resolvePanelFromRoute() {
  const queryPanel = typeof route.query.panel === "string" ? route.query.panel : "";
  if (queryPanel === "tricks" || queryPanel === "about") {
    return queryPanel;
  }
  const slug = String(route.params.slug || "").toLowerCase();
  if (slug === "about") return "about";
  return "tricks";
}

async function loadPage() {
  if (activePanel.value !== "about") return;
  page.value = null;
  try {
    const { data } = await api.get("/pages/about/");
    page.value = data;
  } catch {
    page.value = {
      title: "关于 AlgoWiki",
      description: "项目介绍与路线图。",
      content_md: "当前扩展页未配置内容。",
    };
  }
}

async function loadTricks(pageNo = 1, append = false) {
  const params = {
    page: pageNo,
    order: "created_newest",
  };
  if (auth.isManager) {
    params.include_all = 1;
  }
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
  () => [route.params.slug, route.query.panel],
  async () => {
    activePanel.value = resolvePanelFromRoute();
    if (activePanel.value === "about") {
      await loadPage();
    }
  },
  { immediate: true }
);

onMounted(async () => {
  await loadTricks();
});
</script>

<style scoped>
.extra-layout {
  display: block;
}

.extra-main {
  border: 1px solid var(--hairline);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.6);
  padding: 18px;
  box-shadow: var(--shadow-sm);
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

.trick-submit :deep(.image-upload-helper),
.trick-edit-zone :deep(.image-upload-helper) {
  margin-bottom: 2px;
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
</style>
