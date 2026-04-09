<template>
  <section class="friendly-page">
    <header class="friendly-head">
      <h1>友链</h1>
      <p>第一列展示网站名称，第二列展示主要作用，点击即可跳转。</p>
    </header>

    <section v-if="auth.isManager" ref="publishCardRef" class="card publish-card">
      <h2>{{ editingId ? "修改友链" : "发布友链" }}</h2>
      <div class="publish-grid">
        <input class="input" v-model.trim="form.name" placeholder="友链名称" />
        <input class="input" v-model.trim="form.url" placeholder="跳转链接（https://...）" />
      </div>
      <textarea class="textarea" v-model.trim="form.description" placeholder="主要作用（支持 Markdown）"></textarea>
      <div class="markdown-preview">
        <p class="meta">预览</p>
        <section class="markdown" v-html="renderMarkdown(form.description || '')"></section>
      </div>
      <div class="publish-grid">
        <input class="input" v-model.number="form.order" type="number" min="0" placeholder="排序（越小越靠前）" />
        <label class="switch-line">
          <input type="checkbox" v-model="form.is_enabled" />
          <span>启用显示</span>
        </label>
      </div>
      <div class="publish-actions">
        <button class="btn btn-accent" :disabled="saving" @click="submitLink">
          {{ saving ? "提交中..." : editingId ? "保存修改" : "发布友链" }}
        </button>
        <button v-if="editingId" class="btn" :disabled="saving" @click="resetForm">取消修改</button>
      </div>
    </section>

    <section class="card links-board">
      <div class="links-head links-row">
        <div>友链名称</div>
        <div>主要作用</div>
      </div>

      <p v-if="loading" class="meta board-state">加载中...</p>
      <p v-else-if="links.length === 0" class="meta board-state">暂无友链</p>

      <article
        v-else
        v-for="item in links"
        :key="item.id"
        class="links-row link-item"
        role="button"
        tabindex="0"
        @click="handleRowClick($event, item.url)"
        @keyup.enter="openLink(item.url)"
      >
        <div class="name-col">
          <a
            class="friendly-anchor"
            :href="normalizeUrl(item.url)"
            target="_blank"
            rel="noopener noreferrer"
            @click.stop
          >
            <h3>{{ item.name }}</h3>
            <p class="friendly-anchor-domain">{{ formatDomain(item.url) }}</p>
          </a>
        </div>
        <div class="desc-col">
          <section class="desc-markdown markdown" v-html="renderMarkdown(item.description || '')"></section>
          <div v-if="auth.isManager" class="manager-tools" @click.stop>
            <span class="meta">{{ item.is_enabled ? "已启用" : "已禁用" }}</span>
            <button class="btn btn-mini" @click="startEdit(item)">编辑</button>
            <button class="btn btn-mini" @click="toggleEnabled(item)">
              {{ item.is_enabled ? "禁用" : "启用" }}
            </button>
            <button class="btn btn-mini" @click="removeLink(item)">删除</button>
          </div>
        </div>
      </article>
    </section>
  </section>
</template>

<script setup>
import { nextTick, onMounted, reactive, ref } from "vue";

import api from "../services/api";
import { renderMarkdown } from "../services/markdown";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const auth = useAuthStore();
const ui = useUiStore();

const loading = ref(false);
const saving = ref(false);
const editingId = ref(null);
const links = ref([]);
const publishCardRef = ref(null);

const form = reactive({
  name: "",
  description: "",
  url: "",
  order: 0,
  is_enabled: true,
});

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return fallback;
  if (typeof payload.detail === "string") return payload.detail;
  if (typeof payload === "string") return payload;
  if (typeof payload === "object") {
    const rows = [];
    for (const [key, value] of Object.entries(payload)) {
      if (Array.isArray(value)) rows.push(`${key}: ${value.join("，")}`);
      else if (typeof value === "string") rows.push(`${key}: ${value}`);
    }
    if (rows.length) return rows.join("；");
  }
  return fallback;
}

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

function applyForm(item) {
  editingId.value = item.id;
  form.name = item.name || "";
  form.description = item.description || "";
  form.url = item.url || "";
  form.order = Number(item.order || 0);
  form.is_enabled = Boolean(item.is_enabled);
}

function scrollPublishCardIntoView() {
  const element = publishCardRef.value;
  if (!(element instanceof HTMLElement)) return;
  element.scrollIntoView({ behavior: "smooth", block: "start" });
}

function startEdit(item) {
  applyForm(item);
  nextTick(scrollPublishCardIntoView);
}

function openLink(url) {
  const href = normalizeUrl(url);
  if (!href) return;
  window.open(href, "_blank", "noopener,noreferrer");
}

function handleRowClick(event, url) {
  const target = event?.target;
  if (target instanceof Element && target.closest("a")) {
    return;
  }
  openLink(url);
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

async function loadLinks() {
  loading.value = true;
  try {
    const rows = [];
    let page = 1;
    const params = auth.isManager ? { include_disabled: 1 } : {};
    while (page) {
      const { data } = await api.get("/friendly-links/", { params: { ...params, page } });
      if (Array.isArray(data)) {
        rows.push(...data);
        break;
      }
      rows.push(...(Array.isArray(data?.results) ? data.results : []));
      page = nextPageFromUrl(data?.next);
    }
    links.value = rows;
  } catch (error) {
    links.value = [];
    ui.error(getErrorText(error, "友链加载失败"));
  } finally {
    loading.value = false;
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
    await loadLinks();
  } catch (error) {
    ui.error(getErrorText(error, "友链提交失败"));
  } finally {
    saving.value = false;
  }
}

async function toggleEnabled(item) {
  if (!auth.isManager) return;
  try {
    await api.patch(`/friendly-links/${item.id}/`, { is_enabled: !item.is_enabled });
    ui.success(item.is_enabled ? "已禁用" : "已启用");
    await loadLinks();
  } catch (error) {
    ui.error(getErrorText(error, "状态更新失败"));
  }
}

async function removeLink(item) {
  if (!auth.isManager) return;
  if (!window.confirm(`确认删除友链：${item.name}？`)) return;
  try {
    await api.delete(`/friendly-links/${item.id}/`);
    if (editingId.value === item.id) resetForm();
    ui.success("友链已删除");
    await loadLinks();
  } catch (error) {
    ui.error(getErrorText(error, "删除失败"));
  }
}

onMounted(async () => {
  await loadLinks();
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

.link-item {
  border-bottom: 1px solid var(--hairline);
  cursor: pointer;
  transition: background 0.2s ease;
}

.link-item:last-child {
  border-bottom: 0;
}

.link-item:hover {
  background: color-mix(in srgb, var(--accent) 8%, var(--surface-strong));
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
