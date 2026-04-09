<template>
  <section class="announcement-page">
    <header class="announcement-page-head">
      <div>
        <h1>公告</h1>
        <p>按发布时间倒序查看全部公告</p>
      </div>
      <RouterLink v-if="auth.isManager" class="btn btn-accent" :to="{ name: 'manage-announcements' }">
        发布公告
      </RouterLink>
    </header>

    <section v-if="loading" class="card state-card">
      <p class="meta">公告加载中...</p>
    </section>

    <section v-else-if="announcements.length === 0" class="card state-card">
      <p class="meta">暂无公告。</p>
    </section>

    <section v-else class="announcement-list">
      <article
        v-for="item in announcements"
        :id="getAnnouncementElementId(item.id)"
        :key="item.id"
        class="announcement-card card"
        :class="{ 'announcement-card--focused': focusedAnnouncementId === item.id }"
      >
        <header class="announcement-card-head">
          <div class="announcement-card-title-row">
            <div class="announcement-card-title-group">
              <h2>{{ item.title }}</h2>
              <span v-if="focusedAnnouncementId === item.id" class="announcement-focus-pill">当前公告</span>
            </div>
            <div v-if="auth.isManager" class="announcement-actions">
              <button class="btn btn-mini" type="button" @click="startEditAnnouncement(item)">
                {{ editingAnnouncementId === item.id ? "取消编辑" : "编辑" }}
              </button>
              <button
                class="btn btn-mini"
                type="button"
                :disabled="deletingAnnouncementId === item.id"
                @click="deleteAnnouncement(item)"
              >
                {{ deletingAnnouncementId === item.id ? "删除中..." : "删除" }}
              </button>
            </div>
          </div>
          <div class="announcement-meta">
            <span>发布时间：{{ formatDateTime(item.created_at) }}</span>
            <span>发布者：{{ item?.created_by?.username || "system" }}</span>
            <span v-if="auth.isManager">状态：{{ item.is_published ? "已发布" : "未发布" }}</span>
            <span v-if="auth.isManager">优先级：{{ item.priority ?? 0 }}</span>
          </div>
        </header>

        <section v-if="auth.isManager && editingAnnouncementId === item.id" class="announcement-editor">
          <input v-model.trim="editForm.title" class="input" placeholder="公告标题" />
          <textarea
            v-model="editForm.content_md"
            class="textarea"
            placeholder="使用 Markdown 编写公告内容"
          ></textarea>
          <div class="announcement-editor-grid">
            <label class="announcement-check">
              <span>优先级</span>
              <input v-model.number="editForm.priority" class="input announcement-priority" type="number" />
            </label>
            <label class="announcement-check announcement-check--switch">
              <input v-model="editForm.is_published" type="checkbox" />
              <span>已发布</span>
            </label>
          </div>
          <div class="announcement-actions">
            <button
              class="btn btn-accent"
              type="button"
              :disabled="savingAnnouncement"
              @click="saveAnnouncementEdit(item)"
            >
              {{ savingAnnouncement ? "保存中..." : "保存公告" }}
            </button>
            <button class="btn" type="button" :disabled="savingAnnouncement" @click="cancelEditAnnouncement">
              取消
            </button>
          </div>
        </section>

        <section v-else class="markdown announcement-markdown" v-html="renderMarkdown(item.content_md || '')"></section>
      </article>
    </section>
  </section>
</template>

<script setup>
import { nextTick, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import api from "../services/api";
import { renderMarkdown } from "../services/markdown";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const route = useRoute();
const auth = useAuthStore();
const ui = useUiStore();
const loading = ref(false);
const announcements = ref([]);
const editingAnnouncementId = ref(null);
const savingAnnouncement = ref(false);
const deletingAnnouncementId = ref(null);
const focusedAnnouncementId = ref(null);

const editForm = reactive({
  title: "",
  content_md: "",
  priority: 0,
  is_published: true,
});

function getErrorText(error, fallback = "操作失败") {
  return error?.response?.data?.detail || error?.message || fallback;
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
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

function resetEditForm() {
  editingAnnouncementId.value = null;
  editForm.title = "";
  editForm.content_md = "";
  editForm.priority = 0;
  editForm.is_published = true;
}

function normalizeAnnouncementId(value) {
  const parsed = Number(String(value || "").trim());
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function getAnnouncementElementId(id) {
  return `announcement-${id}`;
}

async function focusAnnouncementFromRoute() {
  const targetId = normalizeAnnouncementId(route.query.announcement);
  focusedAnnouncementId.value = targetId;
  if (!targetId || !announcements.value.some((item) => item.id === targetId)) {
    return;
  }
  await nextTick();
  const element = document.getElementById(getAnnouncementElementId(targetId));
  if (!element) return;
  element.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function loadAllAnnouncements() {
  loading.value = true;
  try {
    const rows = [];
    let page = 1;
    while (page) {
      const params = { page };
      if (auth.isManager) {
        params.all = 1;
      }
      const { data } = await api.get("/announcements/", { params });
      if (Array.isArray(data)) {
        rows.push(...data);
        break;
      }
      const items = Array.isArray(data?.results) ? data.results : [];
      rows.push(...items);
      page = nextPageFromUrl(data?.next);
    }

    announcements.value = rows.sort((a, b) => {
      const aTs = Date.parse(a?.created_at || "");
      const bTs = Date.parse(b?.created_at || "");
      return (Number.isNaN(bTs) ? 0 : bTs) - (Number.isNaN(aTs) ? 0 : aTs);
    });
  } catch (error) {
    announcements.value = [];
    ui.error(getErrorText(error, "公告加载失败"));
  } finally {
    loading.value = false;
  }

  await focusAnnouncementFromRoute();
}

function startEditAnnouncement(item) {
  if (editingAnnouncementId.value === item.id) {
    resetEditForm();
    return;
  }
  editingAnnouncementId.value = item.id;
  editForm.title = item.title || "";
  editForm.content_md = item.content_md || "";
  editForm.priority = Number(item.priority || 0);
  editForm.is_published = Boolean(item.is_published);
}

function cancelEditAnnouncement() {
  resetEditForm();
}

async function saveAnnouncementEdit(item) {
  if (!auth.isManager || !item?.id) return;
  if (!editForm.title.trim() || !editForm.content_md.trim()) {
    ui.info("请填写公告标题和正文内容");
    return;
  }
  if (savingAnnouncement.value) return;

  savingAnnouncement.value = true;
  try {
    await api.patch(`/announcements/${item.id}/`, {
      title: editForm.title.trim(),
      content_md: editForm.content_md,
      priority: Number(editForm.priority || 0),
      is_published: Boolean(editForm.is_published),
    });
    ui.success("公告已更新");
    resetEditForm();
    await loadAllAnnouncements();
  } catch (error) {
    ui.error(getErrorText(error, "公告保存失败"));
  } finally {
    savingAnnouncement.value = false;
  }
}

async function deleteAnnouncement(item) {
  if (!auth.isManager || !item?.id) return;
  if (!window.confirm(`确认删除公告「${item.title}」？`)) return;

  deletingAnnouncementId.value = item.id;
  try {
    await api.delete(`/announcements/${item.id}/`);
    if (editingAnnouncementId.value === item.id) {
      resetEditForm();
    }
    ui.success("公告已删除");
    await loadAllAnnouncements();
  } catch (error) {
    ui.error(getErrorText(error, "删除公告失败"));
  } finally {
    deletingAnnouncementId.value = null;
  }
}

watch(
  () => auth.isManager,
  async () => {
    resetEditForm();
    await loadAllAnnouncements();
  }
);

watch(
  () => route.query.announcement,
  async () => {
    await focusAnnouncementFromRoute();
  }
);

onMounted(async () => {
  await loadAllAnnouncements();
});
</script>

<style scoped>
.announcement-page {
  width: min(1320px, 100%);
  margin: 0 auto;
  display: grid;
  gap: 16px;
}

.announcement-page-head {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: 16px;
}

.announcement-page-head h1 {
  font-size: clamp(34px, 3.2vw, 48px);
  line-height: 1.12;
}

.announcement-page-head p {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 15px;
}

.state-card {
  padding: 22px;
}

.announcement-list {
  display: grid;
  gap: 14px;
}

.announcement-card {
  padding: 20px 22px;
  scroll-margin-top: 110px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.announcement-card--focused {
  border-color: color-mix(in srgb, var(--accent) 36%, transparent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 12%, transparent), var(--shadow-sm);
}

.announcement-card-title-group {
  display: grid;
  gap: 8px;
}

.announcement-focus-pill {
  width: fit-content;
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent) 12%, var(--surface-strong));
  color: var(--accent);
  font-size: 13px;
  font-weight: 700;
}

.announcement-card-head {
  display: grid;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--hairline);
}

.announcement-card-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.announcement-card-head h2 {
  font-size: clamp(24px, 2vw, 32px);
  line-height: 1.2;
}

.announcement-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  color: var(--text-quiet);
  font-size: 14px;
}

.announcement-meta span {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: var(--surface-soft);
  border: 1px solid var(--hairline);
}

.announcement-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.announcement-editor {
  display: grid;
  gap: 10px;
}

.announcement-editor-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.announcement-check {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--text-soft);
  font-size: 14px;
}

.announcement-check--switch input {
  width: 16px;
  height: 16px;
}

.announcement-priority {
  width: 92px;
}

.announcement-markdown {
  color: var(--text);
  font-size: clamp(1.02rem, 0.98rem + 0.18vw, 1.1rem);
}

.announcement-markdown :deep(p:first-child) {
  margin-top: 0;
}

:global(html[data-theme="academic"]) .announcement-card {
  background: var(--surface-strong);
}

:global(html[data-theme="academic"]) .announcement-markdown {
  font-family: var(--font-reading);
}

:global(html[data-theme="geek"]) .announcement-card,
:global(html[data-theme="geek"]) .announcement-meta span {
  border-width: 2px;
}

:global(html[data-theme="geek"]) .announcement-card-head h2 {
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

@media (max-width: 760px) {
  .announcement-page {
    gap: 12px;
  }

  .announcement-page-head {
    flex-direction: column;
    align-items: stretch;
  }

  .announcement-page-head .btn {
    width: 100%;
  }

  .announcement-card {
    padding: 14px;
  }

  .announcement-card-title-row {
    flex-direction: column;
    align-items: stretch;
  }

  .announcement-card-head h2 {
    font-size: clamp(20px, 6vw, 26px);
  }

  .announcement-meta {
    font-size: 13px;
  }
}
.announcement-page {
  width: min(1120px, 100%);
  gap: 20px;
}

.state-card {
  padding: 16px 0;
  border: 0;
  border-top: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.announcement-card,
:global(html[data-theme="academic"]) .announcement-card,
:global(html[data-theme="geek"]) .announcement-card {
  padding: 22px 0;
  border: 0;
  border-top: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.announcement-card:first-child {
  padding-top: 0;
  border-top: 0;
}

.announcement-card--focused {
  border-color: color-mix(in srgb, var(--accent) 34%, transparent);
  box-shadow: none;
}

.announcement-card-head {
  margin-bottom: 14px;
  padding-bottom: 12px;
}

.announcement-meta span {
  min-height: auto;
  padding: 0;
  border: 0;
  background: transparent;
}

@media (max-width: 760px) {
  .announcement-card {
    padding: 18px 0;
  }
}
</style>
