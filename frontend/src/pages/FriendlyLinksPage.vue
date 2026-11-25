<template>
  <section class="friendly-page" :class="{ 'friendly-page--embedded': embedded }">
    <header v-if="!embedded" class="friendly-head">
      <h1>友链</h1>
      <p>第一列展示网站名称，第二列展示主要作用，点击即可跳转。</p>
    </header>

    <section v-if="auth.isManager" ref="publishCardRef" class="card publish-card">
      <div class="publish-head">
        <h2>{{ editingId ? "修改友链" : "友链管理" }}</h2>
        <button
          type="button"
          class="btn btn-sm"
          :class="{ 'btn-accent': !showPublish && !editingId }"
          :aria-expanded="showPublish || Boolean(editingId)"
          @click="togglePublishPanel"
        >
          {{ showPublish || editingId ? "收起表单" : "＋ 发布友链" }}
        </button>
      </div>

      <Transition name="aw-collapse">
        <form v-if="showPublish || editingId" class="publish-form" @submit.prevent="submitLink">
          <div class="publish-grid">
            <input class="input" v-model.trim="form.name" placeholder="友链名称" />
            <input class="input" v-model.trim="form.url" placeholder="跳转链接（https://...）" />
          </div>
          <textarea class="textarea" v-model.trim="form.description" placeholder="主要作用（支持 Markdown）"></textarea>
          <div v-if="form.description" class="markdown-preview">
            <p class="meta">预览</p>
            <section class="markdown" v-html="previewHtml"></section>
          </div>
          <div class="publish-grid">
            <input class="input" v-model.number="form.order" type="number" min="0" placeholder="排序（越小越靠前）" />
            <label class="switch-line">
              <input type="checkbox" v-model="form.is_enabled" />
              <span>启用显示</span>
            </label>
          </div>
          <div class="publish-actions">
            <button class="btn btn-accent" type="submit" :disabled="saving">
              {{ saving ? "提交中..." : editingId ? "保存修改" : "发布友链" }}
            </button>
            <button v-if="editingId" class="btn" type="button" :disabled="saving" @click="cancelEdit">
              取消修改
            </button>
          </div>
        </form>
      </Transition>
    </section>

    <section class="card links-board">
      <div class="links-head links-row">
        <div>友链名称</div>
        <div>主要作用</div>
      </div>

      <SkeletonBlock
        v-if="loading && !links.length"
        :lines="4"
        :line-height="18"
        label="正在加载友链"
        class="board-state"
      />
      <EmptyErrorState
        v-else-if="loadError && !links.length"
        tone="error"
        title="友链加载失败"
        :description="loadError"
        action-label="重新加载"
        :busy="loading"
        class="board-state"
        @action="loadLinks"
      />
      <EmptyErrorState
        v-else-if="links.length === 0"
        title="暂无友链"
        description="管理员添加启用的网站链接后，将展示在此列表。"
        class="board-state"
      />

      <div v-else ref="boardListRef" class="links-list" :class="{ 'is-loading': loading }">
        <article
          v-for="item in links"
          :key="item.id"
          class="links-row link-item"
          :class="{ 'link-item--disabled': !item.is_enabled }"
        >
          <div class="name-col">
            <a
              class="friendly-anchor"
              :href="normalizeUrl(item.url)"
              target="_blank"
              rel="noopener noreferrer"
            >
              <h3>{{ item.name }}</h3>
              <p class="friendly-anchor-domain">{{ formatDomain(item.url) }}</p>
            </a>
          </div>
          <div class="desc-col">
            <section class="desc-markdown markdown" v-html="item._renderedDescription"></section>
            <div v-if="auth.isManager" class="manager-tools">
              <span class="meta">{{ item.is_enabled ? "已启用" : "已禁用" }}</span>
              <button type="button" class="btn btn-mini" :disabled="busyId === item.id" @click="startEdit(item)">
                编辑
              </button>
              <button type="button" class="btn btn-mini" :disabled="busyId === item.id" @click="toggleEnabled(item)">
                {{ busyId === item.id ? "处理中..." : item.is_enabled ? "禁用" : "启用" }}
              </button>
              <button type="button" class="btn btn-mini btn-danger" :disabled="busyId === item.id" @click="removeLink(item)">
                删除
              </button>
            </div>
          </div>
        </article>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";

import EmptyErrorState from "../components/EmptyErrorState.vue";
import SkeletonBlock from "../components/SkeletonBlock.vue";
import { useMarkdownCodeCopy } from "../composables/useMarkdownCodeCopy";
import { useRequestControllers } from "../composables/useRequestControllers";
import api, { isRequestCanceled } from "../services/api";
import { renderMarkdown } from "../services/markdown";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";
import { extractApiError } from "../utils/format";
import { safeScrollIntoView } from "../utils/motion";

const auth = useAuthStore();
const ui = useUiStore();
const requests = useRequestControllers();

defineProps({
  embedded: {
    type: Boolean,
    default: false,
  },
});

const loading = ref(false);
const loadError = ref("");
const saving = ref(false);
const busyId = ref(null);
const editingId = ref(null);
const showPublish = ref(false);
const hasInitialized = ref(false);
const links = ref([]);
const publishCardRef = ref(null);
const boardListRef = ref(null);

useMarkdownCodeCopy(boardListRef, links);

const form = reactive({
  name: "",
  description: "",
  url: "",
  order: 0,
  is_enabled: true,
});

const previewHtml = computed(() =>
  form.description ? renderMarkdown(form.description) : "",
);

function normalizeUrl(url) {
  const value = String(url || "").trim();
  if (!value) return "";
  if (/^[a-z][a-z\d+\-.]*:\/\//i.test(value)) return value;
  return `https://${value}`;
}

function resetForm() {
  editingId.value = null;
  form.name = "";
  form.description = "";
  form.url = "";
  form.order = 0;
  form.is_enabled = true;
}

function cancelEdit() {
  resetForm();
  showPublish.value = false;
}

function togglePublishPanel() {
  if (editingId.value) {
    cancelEdit();
    return;
  }
  showPublish.value = !showPublish.value;
}

function applyForm(item) {
  editingId.value = item.id;
  showPublish.value = true;
  form.name = item.name || "";
  form.description = item.description || "";
  form.url = item.url || "";
  form.order = Number(item.order || 0);
  form.is_enabled = Boolean(item.is_enabled);
}

function scrollPublishCardIntoView() {
  const element = publishCardRef.value;
  if (!(element instanceof HTMLElement)) return;
  safeScrollIntoView(element, { behavior: "smooth", block: "start" });
}

function startEdit(item) {
  applyForm(item);
  nextTick(scrollPublishCardIntoView);
}

function formatDomain(url) {
  try {
    const parsed = new URL(normalizeUrl(url));
    return parsed.host;
  } catch {
    return url || "-";
  }
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

function hydrateLinkRow(item) {
  return {
    ...item,
    _renderedDescription: renderMarkdown(item?.description || ""),
  };
}

async function loadLinks() {
  const controller = requests.replace("friendly-links");
  loading.value = true;
  loadError.value = "";
  try {
    const rows = [];
    let page = 1;
    const params = auth.isManager ? { include_disabled: 1 } : {};
    while (page) {
      const { data } = await api.get("/friendly-links/", {
        params: { ...params, page },
        signal: controller.signal,
      });
      if (!requests.isCurrent("friendly-links", controller)) return;
      if (Array.isArray(data)) {
        rows.push(...data);
        break;
      }
      rows.push(...(Array.isArray(data?.results) ? data.results : []));
      page = nextPageFromUrl(data?.next);
    }
    links.value = rows.map(hydrateLinkRow);
  } catch (error) {
    if (isRequestCanceled(error) || !requests.isCurrent("friendly-links", controller)) return;
    const msg = extractApiError(error, "友链加载失败，请稍后重试");
    loadError.value = msg;
    if (!links.value.length) {
      ui.error(msg);
    }
  } finally {
    if (requests.release("friendly-links", controller)) {
      loading.value = false;
    }
  }
}

async function submitLink() {
  if (!auth.isManager) {
    ui.error("仅管理员可发布友链");
    return;
  }
  if (!form.name || !form.description || !form.url) {
    ui.info("请填写名称、主要作用和链接");
    return;
  }
  saving.value = true;
  try {
    const payload = {
      name: form.name,
      description: form.description,
      url: normalizeUrl(form.url),
      order: Number.isFinite(Number(form.order)) ? Number(form.order) : 0,
      is_enabled: Boolean(form.is_enabled),
    };
    if (editingId.value) {
      await api.patch(`/friendly-links/${editingId.value}/`, payload);
      ui.success("友链已更新");
    } else {
      await api.post("/friendly-links/", payload);
      ui.success("友链已发布");
    }
    resetForm();
    showPublish.value = false;
    await loadLinks();
  } catch (error) {
    ui.error(extractApiError(error, "友链提交失败"));
  } finally {
    saving.value = false;
  }
}

async function toggleEnabled(item) {
  if (!auth.isManager || busyId.value === item.id) return;
  busyId.value = item.id;
  try {
    const nextEnabled = !item.is_enabled;
    await api.patch(`/friendly-links/${item.id}/`, { is_enabled: nextEnabled });
    item.is_enabled = nextEnabled;
    ui.success(nextEnabled ? "友链已启用" : "友链已禁用");
  } catch (error) {
    ui.error(extractApiError(error, "状态更新失败"));
  } finally {
    busyId.value = null;
  }
}

async function removeLink(item) {
  if (!auth.isManager || busyId.value === item.id) return;
  const confirmed = await ui.confirm({
    title: "删除友链",
    message: `确认删除友链“${item.name}”吗？此操作不可撤销。`,
    confirmText: "确认删除",
    cancelText: "保留",
    tone: "danger",
  });
  if (!confirmed) return;

  busyId.value = item.id;
  try {
    await api.delete(`/friendly-links/${item.id}/`);
    if (editingId.value === item.id) {
      cancelEdit();
    }
    links.value = links.value.filter((row) => row.id !== item.id);
    ui.success("友链已删除");
  } catch (error) {
    ui.error(extractApiError(error, "删除失败"));
  } finally {
    busyId.value = null;
  }
}

watch(
  () => auth.isManager,
  async () => {
    if (!hasInitialized.value) return;
    await loadLinks();
  }
);

onMounted(async () => {
  await loadLinks();
  hasInitialized.value = true;
});
</script>

<style scoped>
.friendly-page {
  width: min(1320px, 100%);
  margin: 0 auto;
  display: grid;
  gap: 14px;
}

.friendly-head h1 {
  font-size: clamp(34px, 3.2vw, 48px);
}

.friendly-head p {
  margin: 6px 0 0;
  color: var(--muted);
}

.publish-card {
  padding: 16px;
  display: grid;
  gap: 12px;
}

.publish-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.publish-form {
  display: grid;
  gap: 10px;
}

.publish-card :deep(.image-upload-helper) {
  margin-bottom: -2px;
}

.publish-card h2 {
  font-size: 24px;
}

.publish-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.switch-line {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px;
}

.publish-actions {
  display: flex;
  gap: 8px;
}

.markdown-preview {
  border-radius: 12px;
  border: 1px solid var(--hairline);
  background: var(--surface-soft);
  padding: 10px 12px;
}

.links-board {
  overflow: hidden;
}

.links-row {
  display: grid;
  grid-template-columns: minmax(220px, 0.26fr) minmax(0, 1fr);
  gap: 0;
}

.links-head {
  font-size: 20px;
  font-weight: 700;
  border-bottom: 1px solid var(--hairline);
  background: var(--surface-strong);
}

.links-head > div {
  padding: 12px 16px;
}

.links-head > div:first-child {
  border-right: 1px solid var(--hairline);
}

.board-state {
  padding: 14px 16px;
}

.links-list {
  transition: opacity var(--dur-fast, 150ms) var(--ease-standard, ease);
}

.links-list.is-loading {
  opacity: 0.56;
  pointer-events: none;
}

.link-item {
  border-bottom: 1px solid var(--hairline);
  transition: background-color var(--dur-fast, 150ms) var(--ease-standard, ease);
}

.link-item--disabled {
  opacity: 0.65;
}

.link-item:last-child {
  border-bottom: 0;
}

@media (hover: hover) {
  .link-item:hover {
    background: color-mix(in srgb, var(--accent) 6%, var(--surface-strong));
  }
}

.name-col,
.desc-col {
  padding: 14px 16px;
}

.name-col {
  border-right: 1px solid var(--hairline);
}

.friendly-anchor {
  display: grid;
  gap: 6px;
  color: var(--link);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.friendly-anchor:visited {
  color: var(--link-visited);
}

.friendly-anchor h3 {
  font-size: 24px;
  margin-bottom: 4px;
}

.friendly-anchor-domain {
  margin: 0;
  color: inherit;
  opacity: 0.88;
}

.desc-markdown {
  margin: 0;
  line-height: 1.68;
  color: var(--text);
}

.desc-markdown :deep(p:first-child) {
  margin-top: 0;
}

.desc-markdown :deep(p:last-child) {
  margin-bottom: 0;
}

.manager-tools {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.btn-mini {
  min-height: 30px;
  padding: 5px 10px;
  font-size: 13px;
}

@media (max-width: 960px) {
  .publish-grid {
    grid-template-columns: 1fr;
  }

  .links-row {
    grid-template-columns: 1fr;
  }

  .links-head {
    display: none;
  }

  .name-col {
    border-right: 0;
    border-bottom: 1px solid var(--hairline);
    padding-bottom: 8px;
  }

  .desc-col {
    padding-top: 8px;
  }
}
.publish-card,
.links-board {
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  backdrop-filter: none;
}

.publish-card {
  padding: 18px 0;
  border-top: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
}

.links-board {
  padding: 12px 0 0;
  border-top: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
}

.links-head {
  padding: 0 0 12px;
  border-bottom: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
}

.links-row {
  padding: 14px 0;
  border-bottom: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
}
</style>
