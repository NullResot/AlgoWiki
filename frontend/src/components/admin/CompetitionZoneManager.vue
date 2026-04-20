<template>
  <section class="manager-stack">
    <header class="section-head">
      <div>
        <h2>赛事专区页面管理</h2>
        <p class="meta">这里管理“赛事专区”标题下级菜单的页面入口、顺序、显隐和目标类型。</p>
      </div>
      <button class="btn" type="button" @click="loadAll">刷新专区页面</button>
    </header>

    <div class="form-card">
      <div class="form-grid">
        <input v-model.trim="form.title" class="input" placeholder="显示标题" />
        <input v-model.trim="form.key" class="input" placeholder="唯一 key，如 calendar" />
        <select v-model="form.target_type" class="select">
          <option value="builtin">内置页面</option>
          <option value="page">扩展页面</option>
        </select>
        <select v-if="form.target_type === 'builtin'" v-model="form.builtin_view" class="select">
          <option v-for="item in builtinOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
        <select v-else v-model="form.page" class="select">
          <option value="">请选择扩展页面</option>
          <option v-for="item in enabledPages" :key="item.id" :value="String(item.id)">
            {{ item.title }} (/extra/{{ item.slug }})
          </option>
        </select>
      </div>
      <div class="toolbar">
        <label class="check-line">
          <input v-model="form.is_visible" type="checkbox" />
          <span>显示</span>
        </label>
        <button class="btn btn-accent" type="button" @click="saveSection">
          {{ editingSectionId ? "保存页面入口" : "新增页面入口" }}
        </button>
        <button v-if="editingSectionId" class="btn" type="button" @click="resetForm">取消编辑</button>
      </div>
    </div>

    <p class="meta">共 {{ sections.length }} 个专区页面入口</p>

    <article v-for="item in orderedSections" :key="item.id" class="admin-row">
      <div class="row-main">
        <strong>{{ displayTitle(item) }}</strong>
        <p class="meta">
          {{ item.key }} · {{ targetLabel(item) }} · order {{ item.display_order }} · {{ item.is_visible ? "显示" : "隐藏" }}
        </p>
      </div>
      <div class="row-actions">
        <button class="btn btn-mini" type="button" @click="startEdit(item)">编辑</button>
        <button class="btn btn-mini" type="button" :disabled="!canMoveUp(item)" @click="moveSection(item, 'up')">上移</button>
        <button class="btn btn-mini" type="button" :disabled="!canMoveDown(item)" @click="moveSection(item, 'down')">下移</button>
        <button class="btn btn-mini" type="button" @click="toggleVisibility(item)">
          {{ item.is_visible ? "隐藏" : "显示" }}
        </button>
        <button class="btn btn-mini" type="button" @click="deleteSection(item)">删除</button>
      </div>
    </article>

    <p v-if="!sections.length" class="meta">当前还没有赛事专区页面入口。</p>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { useCompetitionZoneNav } from "../../composables/useCompetitionZoneNav";
import api from "../../services/api";
import { useUiStore } from "../../stores/ui";

const ui = useUiStore();
const { loadCompetitionZoneNav } = useCompetitionZoneNav();

const builtinOptions = [
  { value: "calendar", label: "常规赛" },
  { value: "tricks", label: "trick 技巧汇总" },
  { value: "schedule", label: "锦标赛" },
  { value: "notice", label: "赛事公告" },
  { value: "practice", label: "补题链接" },
  { value: "qa", label: "问答" },
];

const sections = ref([]);
const pages = ref([]);
const editingSectionId = ref(null);

const form = reactive({
  title: "",
  key: "",
  target_type: "builtin",
  builtin_view: "calendar",
  page: "",
  is_visible: true,
});

const orderedSections = computed(() =>
  [...sections.value].sort((left, right) => {
    const orderDelta = Number(left.display_order || 0) - Number(right.display_order || 0);
    if (orderDelta !== 0) return orderDelta;
    return Number(left.id || 0) - Number(right.id || 0);
  })
);

const enabledPages = computed(() => pages.value.filter((item) => item.is_enabled));
const builtinLabelMap = computed(() => new Map(builtinOptions.map((item) => [item.value, item.label])));

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return error?.message || fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload)) return payload.join("；");
  return fallback;
}

function resetForm() {
  editingSectionId.value = null;
  form.title = "";
  form.key = "";
  form.target_type = "builtin";
  form.builtin_view = "calendar";
  form.page = "";
  form.is_visible = true;
}

function startEdit(item) {
  editingSectionId.value = item.id;
  form.title = displayTitle(item);
  form.key = item.key || "";
  form.target_type = item.target_type || "builtin";
  form.builtin_view = item.builtin_view || "calendar";
  form.page = item.page ? String(item.page) : "";
  form.is_visible = item.is_visible !== false;
}

function buildPayload() {
  const payload = {
    title: form.title.trim(),
    key: form.key.trim(),
    target_type: form.target_type,
    is_visible: Boolean(form.is_visible),
  };
  if (form.target_type === "builtin") {
    payload.builtin_view = form.builtin_view;
    payload.page = null;
  } else {
    payload.builtin_view = "";
    payload.page = form.page ? Number(form.page) : null;
  }
  return payload;
}

function targetLabel(item) {
  if (item.target_type === "page") {
    return item.page_title ? `扩展页面 ${item.page_title}` : "扩展页面";
  }
  return builtinOptions.find((entry) => entry.value === item.builtin_view)?.label || item.builtin_view || "内置页面";
}
function displayTitle(item) {
  if (item?.target_type === "builtin") {
    return builtinLabelMap.value.get(item.builtin_view) || item.title || item.key || "";
  }
  return item?.title || item?.page_title || item?.key || "";
}

function canMoveUp(item) {
  return orderedSections.value[0]?.id !== item.id;
}

function canMoveDown(item) {
  return orderedSections.value[orderedSections.value.length - 1]?.id !== item.id;
}

async function syncSectionNav() {
  await loadCompetitionZoneNav(true);
}

async function loadSections() {
  try {
    const { data } = await api.get("/competition-zone-sections/", { params: { include_hidden: 1 } });
    sections.value = Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
  } catch (error) {
    ui.error(getErrorText(error, "赛事专区页面加载失败"));
  }
}

async function loadPages() {
  try {
    const { data } = await api.get("/pages/", { params: { include_disabled: 1 } });
    pages.value = Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
  } catch (error) {
    ui.error(getErrorText(error, "扩展页面列表加载失败"));
  }
}

async function loadAll() {
  await Promise.all([loadSections(), loadPages()]);
}

async function saveSection() {
  if (!form.title.trim() || !form.key.trim()) {
    ui.info("请先填写标题和 key");
    return;
  }
  if (form.target_type === "page" && !form.page) {
    ui.info("请选择扩展页面");
    return;
  }

  try {
    if (editingSectionId.value) {
      await api.patch(`/competition-zone-sections/${editingSectionId.value}/`, buildPayload());
      ui.success("赛事专区页面入口已保存");
    } else {
      await api.post("/competition-zone-sections/", buildPayload());
      ui.success("赛事专区页面入口已创建");
    }
    resetForm();
    await Promise.all([loadSections(), syncSectionNav()]);
  } catch (error) {
    ui.error(getErrorText(error, "保存赛事专区页面入口失败"));
  }
}

async function moveSection(item, direction) {
  try {
    await api.post(`/competition-zone-sections/${item.id}/move/`, { direction });
    await Promise.all([loadSections(), syncSectionNav()]);
    ui.success("赛事专区页面顺序已更新");
  } catch (error) {
    ui.error(getErrorText(error, "移动赛事专区页面失败"));
  }
}

async function toggleVisibility(item) {
  try {
    await api.patch(`/competition-zone-sections/${item.id}/`, { is_visible: !item.is_visible });
    await Promise.all([loadSections(), syncSectionNav()]);
    ui.success(item.is_visible ? "页面入口已隐藏" : "页面入口已显示");
  } catch (error) {
    ui.error(getErrorText(error, "更新页面入口状态失败"));
  }
}

async function deleteSection(item) {
  if (!window.confirm(`确认删除赛事专区页面入口「${item.title}」？`)) return;
  try {
    await api.delete(`/competition-zone-sections/${item.id}/`);
    if (editingSectionId.value === item.id) {
      resetForm();
    }
    await Promise.all([loadSections(), syncSectionNav()]);
    ui.success("赛事专区页面入口已删除");
  } catch (error) {
    ui.error(getErrorText(error, "删除赛事专区页面入口失败"));
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
