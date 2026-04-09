<template>
  <div class="manager-shell">
    <div class="section-head">
      <div>
        <h2>标题管理</h2>
        <p class="meta">这里管理顶部导航栏的一级标题，也就是首页、竞赛wiki、赛事专区、关于AlgoWiki、友链。</p>
      </div>
    </div>

    <div class="form-stack">
      <div class="form-grid">
        <select v-model="selectedKey" class="select">
          <option v-for="item in items" :key="item.id" :value="item.key">{{ item.title }}</option>
        </select>
        <input v-model="form.title" class="input" placeholder="标题名称" />
      </div>
      <div class="action-row">
        <label class="switch-line">
          <input v-model="form.is_visible" type="checkbox" />
          <span>显示</span>
        </label>
        <button class="btn btn-accent" type="button" @click="saveSelected">保存标题</button>
      </div>
    </div>

    <article v-for="item in items" :key="item.id" class="admin-row">
      <div class="row-main">
        <strong>{{ item.title }}</strong>
        <p class="meta">key: {{ item.key }} · order {{ item.display_order }} · {{ item.is_visible ? "显示中" : "已隐藏" }}</p>
      </div>
      <div class="row-actions">
        <RouterLink class="btn btn-mini" :to="resolveRoute(item.key)">打开</RouterLink>
        <button class="btn btn-mini" type="button" @click="pickItem(item)">编辑</button>
        <button class="btn btn-mini" type="button" @click="moveItem(item, 'up')">上移</button>
        <button class="btn btn-mini" type="button" @click="moveItem(item, 'down')">下移</button>
        <button class="btn btn-mini" type="button" @click="toggleVisible(item)">{{ item.is_visible ? "隐藏" : "显示" }}</button>
      </div>
    </article>
  </div>
</template>

<script setup>
import { reactive, ref } from "vue";
import { RouterLink } from "vue-router";

import api from "../../services/api";
import { useUiStore } from "../../stores/ui";

const ui = useUiStore();

const items = ref([]);
const selectedKey = ref("home");
const form = reactive({ title: "", is_visible: true });

function extractResults(data) {
  return Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
}

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload?.detail === "string") return payload.detail;
  return fallback;
}

function sortItems(rows) {
  return [...rows].sort((left, right) => {
    const orderDelta = Number(left.display_order || 0) - Number(right.display_order || 0);
    if (orderDelta !== 0) return orderDelta;
    return Number(left.id || 0) - Number(right.id || 0);
  });
}

function pickItem(item) {
  selectedKey.value = item.key;
  form.title = item.title || "";
  form.is_visible = item.is_visible !== false;
}

function resolveRoute(key) {
  const mapping = {
    home: { name: "home" },
    "competition-wiki": { name: "wiki", query: { category: "xcpc-sites" } },
    competitions: { name: "competitions", query: { tab: "calendar" } },
    about: { name: "extra", params: { slug: "about" } },
    "friendly-links": { name: "friendly-links" },
  };
  return mapping[key] || { name: "home" };
}

async function loadItems() {
  const { data } = await api.get("/header-nav/", { params: { include_hidden: 1 } });
  items.value = sortItems(extractResults(data));
  const current = items.value.find((item) => item.key === selectedKey.value) || items.value[0];
  if (current) {
    pickItem(current);
  }
}

async function saveSelected() {
  const current = items.value.find((item) => item.key === selectedKey.value);
  if (!current) {
    ui.info("请选择一个标题");
    return;
  }
  if (!String(form.title || "").trim()) {
    ui.info("请填写标题名称");
    return;
  }

  try {
    await api.patch(`/header-nav/${current.id}/`, {
      title: String(form.title || "").trim(),
      is_visible: !!form.is_visible,
    }, { params: { include_hidden: 1 } });
    ui.success("标题已更新");
    await loadItems();
  } catch (error) {
    ui.error(getErrorText(error, "标题更新失败"));
  }
}

async function moveItem(item, direction) {
  try {
    await api.post(`/header-nav/${item.id}/move/`, { direction }, { params: { include_hidden: 1 } });
    await loadItems();
  } catch (error) {
    ui.error(getErrorText(error, "标题移动失败"));
  }
}

async function toggleVisible(item) {
  try {
    await api.patch(`/header-nav/${item.id}/`, { is_visible: !item.is_visible }, { params: { include_hidden: 1 } });
    await loadItems();
  } catch (error) {
    ui.error(getErrorText(error, "标题状态更新失败"));
  }
}

loadItems();
</script>

<style scoped>
.manager-shell {
  display: grid;
  gap: 10px;
}

.section-head,
.action-row,
.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.section-head {
  justify-content: space-between;
  align-items: start;
  margin-bottom: 4px;
}

.meta {
  margin: 6px 0 0;
  color: var(--text-quiet);
}

.form-stack {
  display: grid;
  gap: 10px;
  margin-bottom: 14px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.switch-line {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.admin-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  margin-top: 10px;
  border-radius: 12px;
  background: var(--surface-soft);
  padding: 12px;
}

.admin-row:first-of-type {
  margin-top: 0;
}

.row-main {
  min-width: 0;
}

@media (max-width: 960px) {
  .form-grid,
  .admin-row {
    grid-template-columns: 1fr;
  }
}
</style>
