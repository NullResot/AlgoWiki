<template>
  <section class="manager-stack">
    <header class="section-head">
      <div>
        <h2>竞赛 Wiki 页面管理</h2>
        <p class="meta">这里管理“竞赛 Wiki”标题下级菜单对应的分类。仅顶级分类会显示在导航下拉中。</p>
      </div>
      <button class="btn" type="button" :disabled="loading" @click="loadCategories">
        {{ loading ? "刷新中..." : "刷新分类" }}
      </button>
    </header>

    <div class="form-card">
      <div class="form-grid">
        <input v-model.trim="form.name" class="input" placeholder="分类名称" />
        <input v-model.trim="form.slug" class="input" placeholder="slug（可选）" />
        <select v-model="form.parent" class="select">
          <option value="">无父级分类</option>
          <option v-for="item in parentOptions" :key="item.id" :value="String(item.id)">
            {{ item.name }}
          </option>
        </select>
        <select v-model="form.moderation_scope" class="select">
          <option value="public">全站公开 (public)</option>
          <option value="school">校内专区 (school)</option>
        </select>
      </div>
      <div class="toolbar">
        <label class="check-line">
          <input v-model="form.is_visible" type="checkbox" />
          <span>显示</span>
        </label>
        <button class="btn btn-accent" type="button" :disabled="saving" @click="saveCategory">
          {{ saving ? "保存中..." : (editingCategoryId ? "保存分类" : "新增分类") }}
        </button>
        <button v-if="editingCategoryId" class="btn" type="button" @click="resetForm">取消编辑</button>
      </div>
    </div>

    <p class="meta">共 {{ categories.length }} 个分类</p>

    <div v-if="loading && !categories.length" class="loading-box">
      <SkeletonBlock :lines="3" :line-height="18" label="正在加载分类列表" />
    </div>
    <template v-else>
      <article v-for="item in orderedCategories" :key="item.id" class="admin-row">
        <div class="row-main">
          <strong>{{ item.name }}</strong>
          <p class="meta">
            {{ item.slug || "-" }} ·
            {{ item.parent_name ? `父级 ${item.parent_name}` : "顶级导航" }} ·
            {{ formatScopeLabel(item.moderation_scope) }} ·
            排序 {{ item.order }} ·
            {{ item.is_visible ? "显示" : "隐藏" }}
          </p>
        </div>
        <div class="row-actions">
          <button class="btn btn-mini" type="button" :disabled="actingId === item.id" @click="startEdit(item)">编辑</button>
          <button class="btn btn-mini" type="button" :disabled="!canMoveUp(item) || actingId === item.id" @click="moveCategory(item, 'up')">上移</button>
          <button class="btn btn-mini" type="button" :disabled="!canMoveDown(item) || actingId === item.id" @click="moveCategory(item, 'down')">下移</button>
          <button class="btn btn-mini" type="button" :disabled="actingId === item.id" @click="toggleVisibility(item)">
            {{ item.is_visible ? "隐藏" : "显示" }}
          </button>
          <button class="btn btn-mini btn-danger" type="button" :disabled="actingId === item.id" @click="deleteCategory(item)">删除</button>
        </div>
      </article>

      <p v-if="!categories.length" class="meta">当前还没有分类。</p>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import SkeletonBlock from "../SkeletonBlock.vue";
import { useSectionNav } from "../../composables/useSectionNav";
import api from "../../services/api";
import { useUiStore } from "../../stores/ui";

const ui = useUiStore();
const { loadSectionNav } = useSectionNav();

const categories = ref([]);
const loading = ref(false);
const saving = ref(false);
const actingId = ref(null);
const editingCategoryId = ref(null);

const form = reactive({
  name: "",
  slug: "",
  parent: "",
  moderation_scope: "public",
  is_visible: true,
});

const orderedCategories = computed(() =>
  [...categories.value].sort((left, right) => {
    const orderDelta = Number(left.order || 0) - Number(right.order || 0);
    if (orderDelta !== 0) return orderDelta;
    return Number(left.id || 0) - Number(right.id || 0);
  })
);

const parentOptions = computed(() =>
  orderedCategories.value.filter((item) => item.id !== editingCategoryId.value)
);

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return error?.message || fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload)) return payload.join("；");
  return fallback;
}

function siblingRows(item) {
  const parentId = item.parent || null;
  return orderedCategories.value.filter((entry) => (entry.parent || null) === parentId);
}

function canMoveUp(item) {
  return siblingRows(item)[0]?.id !== item.id;
}

function canMoveDown(item) {
  const rows = siblingRows(item);
  return rows[rows.length - 1]?.id !== item.id;
}

function resetForm() {
  editingCategoryId.value = null;
  form.name = "";
  form.slug = "";
  form.parent = "";
  form.moderation_scope = "public";
  form.is_visible = true;
}

function startEdit(item) {
  editingCategoryId.value = item.id;
  form.name = item.name || "";
  form.slug = item.slug || "";
  form.parent = item.parent ? String(item.parent) : "";
  form.moderation_scope = item.moderation_scope || "public";
  form.is_visible = item.is_visible !== false;
}

function buildPayload() {
  const payload = {
    name: form.name.trim(),
    parent: form.parent ? Number(form.parent) : null,
    moderation_scope: form.moderation_scope,
    is_visible: Boolean(form.is_visible),
  };
  if (form.slug.trim()) {
    payload.slug = form.slug.trim();
  }
  return payload;
}

function formatScopeLabel(scope) {
  return { public: "全站公开", school: "校内专区" }[scope] || scope;
}

async function syncCategoryNav() {
  await loadSectionNav(true);
}

async function loadCategories() {
  loading.value = true;
  try {
    const { data } = await api.get("/categories/", { params: { include_hidden: 1 } });
    categories.value = Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
  } catch (error) {
    ui.error(getErrorText(error, "分类加载失败"));
  } finally {
    loading.value = false;
  }
}

async function saveCategory() {
  if (saving.value) return;
  if (!form.name.trim()) {
    ui.info("请先填写分类名称");
    return;
  }

  saving.value = true;
  try {
    if (editingCategoryId.value) {
      await api.patch(`/categories/${editingCategoryId.value}/`, buildPayload());
      ui.success("分类已保存");
    } else {
      await api.post("/categories/", buildPayload());
      ui.success("分类已创建");
    }
    resetForm();
    await Promise.all([loadCategories(), syncCategoryNav()]);
  } catch (error) {
    ui.error(getErrorText(error, "分类保存失败"));
  } finally {
    saving.value = false;
  }
}

async function moveCategory(item, direction) {
  if (actingId.value === item.id) return;
  actingId.value = item.id;
  try {
    await api.post(`/categories/${item.id}/move/`, { direction });
    await Promise.all([loadCategories(), syncCategoryNav()]);
    ui.success("分类顺序已更新");
  } catch (error) {
    ui.error(getErrorText(error, "分类移动失败"));
  } finally {
    actingId.value = null;
  }
}

async function toggleVisibility(item) {
  if (actingId.value === item.id) return;
  actingId.value = item.id;
  try {
    await api.patch(`/categories/${item.id}/`, { is_visible: !item.is_visible });
    await Promise.all([loadCategories(), syncCategoryNav()]);
    ui.success(item.is_visible ? "分类已隐藏" : "分类已显示");
  } catch (error) {
    ui.error(getErrorText(error, "分类状态更新失败"));
  } finally {
    actingId.value = null;
  }
}

async function deleteCategory(item) {
  if (actingId.value === item.id) return;
  const confirmed = await ui.confirm({
    title: `确认删除分类「${item.name}」`,
    message: "删除后将同步移除该导航分类入口，请确保旗下没有依赖该路径的重要条目。",
    confirmText: "确认删除",
    cancelText: "取消",
    danger: true,
  });
  if (!confirmed) return;
  actingId.value = item.id;
  try {
    await api.delete(`/categories/${item.id}/`);
    if (editingCategoryId.value === item.id) {
      resetForm();
    }
    await Promise.all([loadCategories(), syncCategoryNav()]);
    ui.success("分类已删除");
  } catch (error) {
    ui.error(getErrorText(error, "删除分类失败"));
  } finally {
    actingId.value = null;
  }
}

onMounted(() => {
  loadCategories();
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
  grid-template-columns: repeat(4, minmax(0, 1fr));
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
