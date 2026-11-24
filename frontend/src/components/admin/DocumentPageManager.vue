<template>
  <section class="manager-stack">
    <header class="section-head">
      <div>
        <h2>文档页面管理</h2>
        <p class="meta">
          这里管理“文档”左侧子页面的显示名称、顺序、显隐、删除和新增。新增时会自动创建对应的文档页面。
        </p>
      </div>
      <button class="btn" type="button" :disabled="loading" @click="loadAll">
        {{ loading ? "刷新中..." : "刷新文档页面" }}
      </button>
    </header>

    <div class="form-card">
      <div class="form-grid">
        <input v-model.trim="form.title" class="input" placeholder="显示标题" />
        <input v-model.trim="form.key" class="input" placeholder="唯一 key，例如 trick-guide" />
        <input v-model.trim="form.page_slug" class="input" placeholder="页面 slug，例如 trick-guide" />
      </div>
      <div class="toolbar">
        <label class="check-line">
          <input v-model="form.is_visible" type="checkbox" />
          <span>显示</span>
        </label>
        <button class="btn btn-accent" type="button" :disabled="saving" @click="saveSection">
          {{ saving ? "保存中..." : (editingSectionId ? "保存文档子页面" : "新增文档子页面") }}
        </button>
        <button v-if="editingSectionId" class="btn" type="button" @click="resetForm">取消编辑</button>
      </div>
    </div>

    <p class="meta">共 {{ sections.length }} 个文档子页面</p>

    <div v-if="loading && !sections.length" class="loading-box">
      <SkeletonBlock :lines="3" :line-height="18" label="正在加载文档子页面" />
    </div>
    <template v-else>
      <article v-for="item in orderedSections" :key="item.id" class="admin-row">
        <div class="row-main">
          <strong>{{ item.title }}</strong>
          <p class="meta">
            {{ item.key }} · /extra/{{ item.page_slug || "-" }} · 排序 {{ item.display_order }} ·
            {{ item.is_visible ? "显示" : "隐藏" }}
          </p>
        </div>
        <div class="row-actions">
          <button class="btn btn-mini" type="button" :disabled="actingId === item.id" @click="startEdit(item)">编辑</button>
          <button class="btn btn-mini" type="button" :disabled="!canMoveUp(item) || actingId === item.id" @click="moveSection(item, 'up')">
            上移
          </button>
          <button class="btn btn-mini" type="button" :disabled="!canMoveDown(item) || actingId === item.id" @click="moveSection(item, 'down')">
            下移
          </button>
          <button class="btn btn-mini" type="button" :disabled="actingId === item.id" @click="toggleVisibility(item)">
            {{ item.is_visible ? "隐藏" : "显示" }}
          </button>
          <button class="btn btn-mini btn-danger" type="button" :disabled="actingId === item.id" @click="deleteSection(item)">删除</button>
        </div>
      </article>

      <p v-if="!sections.length" class="meta">当前还没有文档子页面。</p>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import SkeletonBlock from "../SkeletonBlock.vue";
import { useDocumentNav } from "../../composables/useDocumentNav";
import api from "../../services/api";
import { useUiStore } from "../../stores/ui";

const ui = useUiStore();
const { loadDocumentNav } = useDocumentNav();

const sections = ref([]);
const loading = ref(false);
const saving = ref(false);
const actingId = ref(null);
const editingSectionId = ref(null);
const editingPageId = ref(null);
const originalPageSlug = ref("");

const form = reactive({
  title: "",
  key: "",
  page_slug: "",
  is_visible: true,
});

const orderedSections = computed(() =>
  [...sections.value].sort((left, right) => {
    const orderDelta =
      Number(left.display_order || 0) - Number(right.display_order || 0);
    if (orderDelta !== 0) return orderDelta;
    return Number(left.id || 0) - Number(right.id || 0);
  }),
);

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return error?.message || fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload)) return payload.join("；");
  if (typeof payload === "object") {
    const firstValue = Object.values(payload)[0];
    if (Array.isArray(firstValue)) return firstValue.join("；");
    if (typeof firstValue === "string") return firstValue;
  }
  return fallback;
}

function resetForm() {
  editingSectionId.value = null;
  editingPageId.value = null;
  originalPageSlug.value = "";
  form.title = "";
  form.key = "";
  form.page_slug = "";
  form.is_visible = true;
}

function startEdit(item) {
  editingSectionId.value = item.id;
  editingPageId.value = item.page || null;
  originalPageSlug.value = item.page_slug || "";
  form.title = item.title || item.page_title || "";
  form.key = item.key || "";
  form.page_slug = item.page_slug || item.key || "";
  form.is_visible = item.is_visible !== false;
}

function buildSectionPayload(pageId) {
  return {
    title: form.title.trim(),
    key: form.key.trim(),
    page: pageId,
    is_visible: Boolean(form.is_visible),
  };
}

function buildPagePayload() {
  return {
    title: form.title.trim(),
    slug: form.page_slug.trim(),
    description: "",
    content_md: "",
    access_level: "public",
    is_enabled: true,
  };
}

function canMoveUp(item) {
  return orderedSections.value[0]?.id !== item.id;
}

function canMoveDown(item) {
  return orderedSections.value[orderedSections.value.length - 1]?.id !== item.id;
}

async function syncDocumentSectionNav() {
  await loadDocumentNav(true);
}

async function loadSections() {
  try {
    const { data } = await api.get("/document-page-sections/", {
      params: { include_hidden: 1 },
    });
    sections.value = Array.isArray(data?.results)
      ? data.results
      : Array.isArray(data)
        ? data
        : [];
  } catch (error) {
    ui.error(getErrorText(error, "文档页面加载失败"));
  }
}

async function loadAll() {
  loading.value = true;
  try {
    await loadSections();
  } finally {
    loading.value = false;
  }
}

async function saveSection() {
  if (saving.value) return;
  if (!form.title.trim() || !form.key.trim() || !form.page_slug.trim()) {
    ui.info("请先填写标题、key 和页面 slug");
    return;
  }

  let createdPageSlug = "";
  saving.value = true;

  try {
    if (editingSectionId.value) {
      const currentPageSlug = originalPageSlug.value || form.page_slug.trim();
      const { data: pageData } = await api.patch(
        `/pages/${encodeURIComponent(currentPageSlug)}/`,
        buildPagePayload(),
      );
      await api.patch(
        `/document-page-sections/${editingSectionId.value}/`,
        buildSectionPayload(pageData.id || editingPageId.value),
      );
      ui.success("文档子页面已更新");
    } else {
      const { data: pageData } = await api.post("/pages/", buildPagePayload());
      createdPageSlug = String(pageData?.slug || form.page_slug.trim());
      try {
        await api.post(
          "/document-page-sections/",
          buildSectionPayload(pageData.id),
        );
      } catch (error) {
        if (createdPageSlug) {
          try {
            await api.delete(`/pages/${encodeURIComponent(createdPageSlug)}/`);
          } catch {
            // Keep rollback best-effort.
          }
        }
        throw error;
      }
      ui.success("文档子页面已创建");
    }
    resetForm();
    await Promise.all([loadSections(), syncDocumentSectionNav()]);
  } catch (error) {
    ui.error(getErrorText(error, "保存文档子页面失败"));
  } finally {
    saving.value = false;
  }
}

async function moveSection(item, direction) {
  if (actingId.value === item.id) return;
  actingId.value = item.id;
  try {
    await api.post(`/document-page-sections/${item.id}/move/`, { direction });
    await Promise.all([loadSections(), syncDocumentSectionNav()]);
    ui.success("文档子页面顺序已更新");
  } catch (error) {
    ui.error(getErrorText(error, "移动文档子页面失败"));
  } finally {
    actingId.value = null;
  }
}

async function toggleVisibility(item) {
  if (actingId.value === item.id) return;
  actingId.value = item.id;
  try {
    await api.patch(`/document-page-sections/${item.id}/`, {
      is_visible: !item.is_visible,
    });
    await Promise.all([loadSections(), syncDocumentSectionNav()]);
    ui.success(item.is_visible ? "文档子页面已隐藏" : "文档子页面已显示");
  } catch (error) {
    ui.error(getErrorText(error, "更新文档子页面状态失败"));
  } finally {
    actingId.value = null;
  }
}

async function deleteSection(item) {
  if (actingId.value === item.id) return;
  const confirmed = await ui.confirm({
    title: `确认删除文档子页面「${item.title}」`,
    message: "删除后将移除文档左侧菜单中对应的页面入口。",
    confirmText: "确认删除",
    cancelText: "取消",
    danger: true,
  });
  if (!confirmed) return;
  actingId.value = item.id;
  try {
    await api.delete(`/document-page-sections/${item.id}/`);
    if (editingSectionId.value === item.id) {
      resetForm();
    }
    await Promise.all([loadSections(), syncDocumentSectionNav()]);
    ui.success("文档子页面已删除");
  } catch (error) {
    ui.error(getErrorText(error, "删除文档子页面失败"));
  } finally {
    actingId.value = null;
  }
}

onMounted(() => {
  loadAll();
});
</script>

<style scoped>
.manager-stack {
  display: grid;
  gap: 12px;
}

.section-head,
.toolbar,
.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.section-head {
  justify-content: space-between;
  align-items: start;
}

.form-card {
  display: grid;
  gap: 10px;
  padding: 14px;
  border-radius: 14px;
  background: var(--surface-soft);
  border: 1px solid var(--hairline);
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.check-line {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.admin-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  padding: 12px;
  border-radius: 14px;
  background: var(--surface-soft);
  border: 1px solid var(--hairline);
}

.row-main {
  min-width: 0;
}

.meta {
  margin: 0;
  color: var(--text-quiet);
}

@media (max-width: 960px) {
  .form-grid,
  .admin-row {
    grid-template-columns: 1fr;
  }
}
</style>
