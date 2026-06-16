<template>
  <section class="manager-stack">
    <header class="section-head">
      <div>
        <h2>用户管理</h2>
        <p class="meta">集中处理用户筛选、封禁、恢复、删除、彻底删除和角色调整。</p>
      </div>
      <button class="btn" type="button" @click="loadUsers">刷新用户列表</button>
    </header>

    <div class="toolbar">
      <select v-model="filters.role" class="select">
        <option value="">全部角色</option>
        <option value="normal">normal</option>
        <option value="school">school</option>
        <option value="admin">admin</option>
        <option value="superadmin">superadmin</option>
      </select>
      <select v-model="filters.is_active" class="select">
        <option value="">全部状态</option>
        <option value="1">active</option>
        <option value="0">inactive</option>
      </select>
      <select v-model="filters.is_banned" class="select">
        <option value="">全部封禁状态</option>
        <option value="1">banned</option>
        <option value="0">not banned</option>
      </select>
      <input
        v-model="filters.search"
        class="input grow"
        placeholder="搜索用户名 / 邮箱 / 学校"
        @keyup.enter="loadUsers"
      />
      <button class="btn" type="button" @click="loadUsers">筛选</button>
      <button class="btn" type="button" @click="resetFilters">重置</button>
    </div>

    <div class="toolbar">
      <label class="check-line">
        <input type="checkbox" :checked="allUsersChecked" @change="toggleSelectAll($event.target.checked)" />
        <span>全选当前结果</span>
      </label>
      <button class="btn" type="button" @click="bulkAction('ban', '批量封禁用户')">批量封禁</button>
      <button class="btn" type="button" @click="bulkAction('unban', '批量解封用户')">批量解封</button>
      <button class="btn" type="button" @click="bulkAction('reactivate', '批量恢复用户')">批量恢复</button>
      <button class="btn" type="button" @click="bulkSoftDelete">批量删除</button>
      <template v-if="auth.isSuperAdmin">
        <select v-model="bulkRole" class="select">
          <option value="normal">normal</option>
          <option value="school">school</option>
          <option value="admin">admin</option>
        </select>
        <button class="btn" type="button" @click="bulkSetRole">批量设角色</button>
      </template>
    </div>

    <p class="meta">共 {{ meta.count }} 个用户</p>

    <div class="user-card-list">
      <article
        v-for="item in users"
        :key="item.id"
        class="user-card"
        :class="{ 'user-card--focused': Number(item.id) === Number(focusedUserId) }"
        tabindex="0"
        role="button"
        @click="openUserModal(item)"
        @keydown.enter.prevent="openUserModal(item)"
      >
        <label class="check-line user-card-check" @click.stop>
          <input type="checkbox" :value="item.id" v-model="selectedUserIds" />
          <span class="sr-only">选择 {{ item.username }}</span>
        </label>
        <img
          class="user-avatar"
          :src="avatarSrc(item)"
          :alt="`${item.username || '用户'} 头像`"
          loading="lazy"
        />
        <div class="user-card-main">
          <div class="user-card-title">
            <strong>{{ item.username }}</strong>
            <span class="role-pill">{{ formatRole(item.role) }}</span>
          </div>
          <p class="meta">{{ item.email || "未填写邮箱" }} · {{ item.school_name || "未填写学校" }}</p>
          <p class="meta">{{ formatUserState(item) }} · 手机号{{ formatPhoneVerificationStatus(item.phone_verification?.status) }}</p>
        </div>
        <span class="user-card-more">管理</span>
      </article>
    </div>

    <button v-if="meta.hasMore" class="btn" type="button" @click="loadMoreUsers">加载更多用户</button>
    <p v-if="!users.length" class="meta">当前没有匹配的用户。</p>

    <div v-if="activeUserDetails" class="modal-backdrop" @click.self="closeUserModal">
      <section class="user-modal" role="dialog" aria-modal="true" aria-label="用户管理操作">
        <header class="user-modal-head">
          <img
            class="user-modal-avatar"
            :src="avatarSrc(activeUserDetails)"
            :alt="`${activeUserDetails.username || '用户'} 头像`"
          />
          <div class="user-modal-title">
            <h3>{{ activeUserDetails.username }}</h3>
            <p class="meta">ID #{{ activeUserDetails.id }} · {{ formatRole(activeUserDetails.role) }}</p>
          </div>
          <button class="btn btn-mini" type="button" @click="closeUserModal">关闭</button>
        </header>

        <dl class="user-detail-grid">
          <div>
            <dt>账号状态</dt>
            <dd>{{ formatUserState(activeUserDetails) }}</dd>
          </div>
          <div>
            <dt>邮箱</dt>
            <dd>{{ activeUserDetails.email || "未填写" }}</dd>
          </div>
          <div>
            <dt>学校</dt>
            <dd>{{ activeUserDetails.school_name || "未填写" }}</dd>
          </div>
          <div>
            <dt>手机号</dt>
            <dd>
              {{ formatAdminPhoneLabel(activeUserDetails) }}
              <span v-if="formatPhoneHint(activeUserDetails)" class="phone-hint">
                {{ formatPhoneHint(activeUserDetails) }}
              </span>
            </dd>
          </div>
          <div>
            <dt>注册时间</dt>
            <dd>{{ formatDateTime(activeUserDetails.date_joined) }}</dd>
          </div>
          <div>
            <dt>上次登录</dt>
            <dd>{{ formatLastLogin(activeUserDetails.last_login) }}</dd>
          </div>
        </dl>

        <section class="modal-section">
          <h4>账号操作</h4>
          <div class="modal-actions">
            <button v-if="!activeUserDetails.is_banned" class="btn" type="button" @click="banUser(activeUserDetails)">封禁</button>
            <button v-else class="btn" type="button" @click="unbanUser(activeUserDetails)">解封</button>
            <button v-if="!activeUserDetails.is_active" class="btn" type="button" @click="reactivateUser(activeUserDetails)">恢复</button>
            <button v-if="activeUserDetails.is_active" class="btn" type="button" @click="softDeleteUser(activeUserDetails)">删除</button>
            <button
              v-if="!activeUserDetails.is_active && activeUserDetails.role !== 'superadmin'"
              class="btn"
              type="button"
              @click="hardDeleteUser(activeUserDetails)"
            >
              彻底删除
            </button>
          </div>
        </section>

        <section v-if="auth.isSuperAdmin" class="modal-section">
          <h4>角色调整</h4>
          <div class="modal-actions">
            <button v-if="activeUserDetails.role !== 'admin'" class="btn" type="button" @click="setRole(activeUserDetails, 'admin')">设为管理员</button>
            <button v-if="activeUserDetails.role !== 'school'" class="btn" type="button" @click="setRole(activeUserDetails, 'school')">设为学校用户</button>
            <button v-if="activeUserDetails.role !== 'normal'" class="btn" type="button" @click="setRole(activeUserDetails, 'normal')">设为普通用户</button>
          </div>
        </section>

        <section class="modal-section">
          <h4>发送公告</h4>
          <div class="modal-notice-form">
            <input v-model="notificationForm.title" class="input" placeholder="公告标题" />
            <select v-model="notificationForm.level" class="select">
              <option value="info">普通</option>
              <option value="warning">提醒</option>
            </select>
            <input v-model="notificationForm.link" class="input" placeholder="跳转链接（可选，如 /profile）" />
            <textarea v-model="notificationForm.content" class="textarea" placeholder="公告内容"></textarea>
            <button
              class="btn btn-accent"
              type="button"
              :disabled="sendingNotificationUserId !== null"
              @click="sendNotificationToUser"
            >
              {{ sendingNotificationUserId !== null ? "发送中..." : "发送给该用户" }}
            </button>
          </div>
        </section>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";

import api, { isRequestCanceled } from "../../services/api";
import { useRequestControllers } from "../../composables/useRequestControllers";
import { useAuthStore } from "../../stores/auth";
import { useUiStore } from "../../stores/ui";

const auth = useAuthStore();
const ui = useUiStore();
const route = useRoute();
const requests = useRequestControllers();

const users = ref([]);
const selectedUserIds = ref([]);
const focusedUserId = ref("");
const bulkRole = ref("normal");
const activeUserId = ref(null);
const sendingNotificationUserId = ref(null);
const DEFAULT_AVATAR_URL = "/wiki-assets/default-avatar.svg";
const notificationForm = reactive({
  title: "",
  content: "",
  link: "",
  level: "info",
});

const filters = reactive({
  role: "",
  is_active: "",
  is_banned: "",
  search: "",
});

const meta = reactive({
  count: 0,
  page: 1,
  hasMore: false,
});

const allUsersChecked = computed(
  () => users.value.length > 0 && selectedUserIds.value.length === users.value.length
);
const activeUserDetails = computed(() =>
  users.value.find((item) => Number(item.id) === Number(activeUserId.value)) || null
);

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return error?.message || fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload)) return payload.join("；");
  if (typeof payload === "object") {
    const parts = [];
    for (const [field, value] of Object.entries(payload)) {
      if (Array.isArray(value)) {
        parts.push(`${field}: ${value.join("，")}`);
      } else if (typeof value === "string") {
        parts.push(`${field}: ${value}`);
      }
    }
    if (parts.length) return parts.join("；");
  }
  return fallback;
}

function unpackListPayload(data) {
  if (Array.isArray(data)) {
    return { results: data, count: data.length };
  }
  const results = Array.isArray(data?.results) ? data.results : [];
  const count = Number.isFinite(data?.count) ? data.count : results.length;
  return { results, count };
}

function appendUniqueById(baseList, extraList) {
  const existed = new Set(baseList.map((item) => item.id));
  const merged = [...baseList];
  for (const item of extraList) {
    if (!existed.has(item.id)) {
      existed.add(item.id);
      merged.push(item);
    }
  }
  return merged;
}

function updateMeta(totalCount, loadedCount, page) {
  meta.count = totalCount;
  meta.page = page;
  meta.hasMore = loadedCount < totalCount;
}

function syncSelectedIds() {
  const valid = new Set(users.value.map((item) => item.id));
  selectedUserIds.value = selectedUserIds.value.filter((id) => valid.has(id));
}

function syncActiveUser() {
  if (!activeUserId.value) return;
  const matched = users.value.some((item) => Number(item.id) === Number(activeUserId.value));
  if (!matched) {
    closeUserModal();
  }
}

function buildParams(page = 1) {
  const params = { page };
  if (focusedUserId.value) params.id = focusedUserId.value;
  if (filters.role) params.role = filters.role;
  if (filters.is_active) params.is_active = filters.is_active;
  if (filters.is_banned) params.is_banned = filters.is_banned;
  if (filters.search.trim()) params.search = filters.search.trim();
  return params;
}

function isInvalidPageError(error) {
  const detail = String(error?.response?.data?.detail || error?.message || "").trim();
  return /invalid page|\u65e0\u6548\u9875\u9762/i.test(detail);
}

async function loadUsers(page = 1, append = false) {
  const safePage = Number.isFinite(page) && page > 0 ? Math.floor(page) : 1;
  const controller = requests.replace("user-list");
  try {
    const { data } = await api.get("/users/", {
      params: buildParams(safePage),
      signal: controller.signal,
    });
    if (!requests.isCurrent("user-list", controller)) return;
    const { results, count } = unpackListPayload(data);
    users.value = append ? appendUniqueById(users.value, results) : results;
    updateMeta(count, users.value.length, safePage);
    syncSelectedIds();
    syncActiveUser();
  } catch (error) {
    if (isRequestCanceled(error)) return;
    if (isInvalidPageError(error) && safePage > 1) {
      await loadUsers(1, false);
      return;
    }
    ui.error(getErrorText(error, "用户列表加载失败"));
  } finally {
    requests.release("user-list", controller);
  }
}

async function loadMoreUsers() {
  if (!meta.hasMore) return;
  await loadUsers(meta.page + 1, true);
}

function toggleSelectAll(checked) {
  selectedUserIds.value = checked ? users.value.map((item) => item.id) : [];
}

function resetFilters() {
  focusedUserId.value = "";
  filters.role = "";
  filters.is_active = "";
  filters.is_banned = "";
  filters.search = "";
  meta.page = 1;
  loadUsers(1, false);
}

function openUserModal(item) {
  activeUserId.value = item?.id || null;
  notificationForm.title = "";
  notificationForm.content = "";
  notificationForm.link = "";
  notificationForm.level = "info";
}

function closeUserModal() {
  activeUserId.value = null;
}

async function bulkAction(action, successText, extraPayload = {}) {
  if (!selectedUserIds.value.length) {
    ui.info("请先选择用户");
    return;
  }

  try {
    const { data } = await api.post("/users/bulk-action/", {
      ids: selectedUserIds.value,
      action,
      ...extraPayload,
    });
    const successCount = Number(data?.success || 0);
    const failedCount = Number(data?.failed || 0);
    if (successCount) ui.success(`${successText}：成功 ${successCount} 条`);
    if (failedCount) ui.error(`${successText}：失败 ${failedCount} 条`);
    await loadUsers();
  } catch (error) {
    ui.error(getErrorText(error, `${successText}失败`));
  }
}

async function bulkSoftDelete() {
  if (!selectedUserIds.value.length) {
    ui.info("请先选择用户");
    return;
  }
  if (!window.confirm(`确认删除选中的 ${selectedUserIds.value.length} 个用户？`)) return;
  await bulkAction("soft_delete", "批量删除用户");
}

async function bulkSetRole() {
  await bulkAction("set_role", "批量设置角色", { role: bulkRole.value });
}

async function banUser(item) {
  try {
    await api.post(`/users/${item.id}/ban/`, { reason: "" });
    ui.success("用户已封禁");
    await loadUsers();
  } catch (error) {
    ui.error(getErrorText(error, "封禁用户失败"));
  }
}

async function unbanUser(item) {
  try {
    await api.post(`/users/${item.id}/unban/`);
    ui.success("用户已解封");
    await loadUsers();
  } catch (error) {
    ui.error(getErrorText(error, "解封用户失败"));
  }
}

async function reactivateUser(item) {
  try {
    await api.post(`/users/${item.id}/reactivate/`);
    ui.success("用户已恢复");
    await loadUsers();
  } catch (error) {
    ui.error(getErrorText(error, "恢复用户失败"));
  }
}

async function softDeleteUser(item) {
  if (!window.confirm(`确认删除用户「${item.username}」？`)) return;
  try {
    await api.post(`/users/${item.id}/soft_delete/`);
    ui.success("用户已删除");
    await loadUsers();
  } catch (error) {
    ui.error(getErrorText(error, "删除用户失败"));
  }
}

async function hardDeleteUser(item) {
  const message = [
    `确认彻底删除用户「${item.username}」？`,
    "此操作不可恢复：账号会被物理删除，动态帖子/评论会同步删除，Wiki 和赛事专区录入者将显示为“已注销用户”。",
  ].join("\n");
  if (!window.confirm(message)) return;
  try {
    await api.post(`/users/${item.id}/hard_delete/`);
    ui.success("用户已彻底删除");
    if (Number(activeUserId.value) === Number(item.id)) {
      closeUserModal();
    }
    await loadUsers();
  } catch (error) {
    ui.error(getErrorText(error, "彻底删除用户失败"));
  }
}

async function setRole(item, role) {
  try {
    await api.post(`/users/${item.id}/set_role/`, { role });
    ui.success("角色已更新");
    await loadUsers();
  } catch (error) {
    ui.error(getErrorText(error, "更新角色失败"));
  }
}

async function sendNotificationToUser() {
  if (!activeUserDetails.value?.id) {
    ui.info("请先选择一个用户");
    return;
  }
  if (!notificationForm.title.trim() || !notificationForm.content.trim()) {
    ui.info("请填写公告标题和内容");
    return;
  }

  sendingNotificationUserId.value = activeUserDetails.value.id;
  try {
    await api.post(`/users/${activeUserDetails.value.id}/send-notification/`, {
      title: notificationForm.title.trim(),
      content: notificationForm.content.trim(),
      link: notificationForm.link.trim(),
      level: notificationForm.level,
    });
    ui.success(`已向 ${activeUserDetails.value.username} 发送公告`);
    notificationForm.title = "";
    notificationForm.content = "";
    notificationForm.link = "";
    notificationForm.level = "info";
  } catch (error) {
    ui.error(getErrorText(error, "发送单用户公告失败"));
  } finally {
    sendingNotificationUserId.value = null;
  }
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

function formatLastLogin(value) {
  return value ? formatDateTime(value) : "从未登录";
}

function formatPhoneVerificationStatus(value) {
  const map = {
    verified: "已验证",
    pending: "验证中",
    rejected: "未通过",
    revoked: "已撤销",
    unverified: "未验证",
  };
  return map[value] || "未验证";
}

function formatRole(value) {
  const map = {
    normal: "普通用户",
    school: "学校用户",
    admin: "管理员",
    superadmin: "超级管理员",
  };
  return map[value] || value || "-";
}

function avatarSrc(item) {
  return String(item?.avatar_url || "").trim() || DEFAULT_AVATAR_URL;
}

function formatUserState(item) {
  const state = item?.is_active ? "活跃" : "已删除";
  const ban = item?.is_banned ? "已封禁" : "正常";
  return `${state} · ${ban}`;
}

function formatAdminPhoneLabel(item) {
  const verification = item?.phone_verification || {};
  if (auth.isSuperAdmin && verification.phone_number) {
    return `+${verification.phone_country_code || "86"} ${verification.phone_number}`;
  }
  return verification.phone_masked || "-";
}

function formatPhoneHint(item) {
  const verification = item?.phone_verification || {};
  if (auth.isSuperAdmin) {
    if (verification.phone_number) return "完整号码仅超级管理员可见";
    if (verification.phone_masked) return "历史数据未保存完整号码，仅可显示掩码";
  }
  if (verification.phone_masked) return "完整号码仅超级管理员可见";
  return "";
}

function syncFocusedUserFromRoute() {
  const value = String(route.query.user || "").trim();
  focusedUserId.value = /^\d+$/.test(value) ? value : "";
}

onMounted(() => {
  syncFocusedUserFromRoute();
  loadUsers();
});

watch(
  () => route.query.user,
  () => {
    syncFocusedUserFromRoute();
    loadUsers(1, false);
  },
);
</script>

<style scoped>
.manager-stack {
  display: grid;
  gap: 12px;
}

.section-head,
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.section-head {
  justify-content: space-between;
  align-items: start;
}

.grow {
  flex: 1 1 280px;
}

.check-line {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
  border: 0;
}

.user-card-list {
  display: grid;
  gap: 10px;
}

.user-card {
  display: grid;
  grid-template-columns: auto 52px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  min-width: 0;
  padding: 12px;
  border-radius: 14px;
  background: var(--surface-soft);
  border: 1px solid var(--hairline);
  cursor: pointer;
  transition: border-color 0.18s ease, background-color 0.18s ease, box-shadow 0.18s ease;
}

.user-card:hover,
.user-card:focus-visible {
  border-color: color-mix(in srgb, var(--accent) 36%, var(--hairline));
  background: color-mix(in srgb, var(--accent) 5%, var(--surface-soft));
  outline: none;
}

.user-card--focused {
  border-color: color-mix(in srgb, var(--accent) 45%, var(--hairline));
  background: color-mix(in srgb, var(--accent) 8%, var(--surface-soft));
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 10%, transparent);
}

.user-card-check {
  align-self: center;
}

.user-avatar,
.user-modal-avatar {
  border-radius: 999px;
  object-fit: cover;
  background: #eef2ff;
  border: 1px solid color-mix(in srgb, var(--hairline) 78%, transparent);
}

.user-avatar {
  width: 52px;
  height: 52px;
}

.user-card-main {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.user-card-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.user-card-title strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.role-pill {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 2px 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent) 10%, transparent);
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
}

.user-card-more {
  color: var(--text-quiet);
  font-size: 13px;
  font-weight: 700;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.42);
}

.user-modal {
  display: grid;
  gap: 16px;
  width: min(760px, 100%);
  max-height: min(760px, calc(100vh - 48px));
  overflow: auto;
  padding: 20px;
  border-radius: 18px;
  background: var(--surface-strong, #fff);
  border: 1px solid var(--hairline);
  box-shadow: 0 24px 72px rgba(15, 23, 42, 0.22);
}

.user-modal-head {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr) auto;
  align-items: center;
  gap: 14px;
}

.user-modal-avatar {
  width: 64px;
  height: 64px;
}

.user-modal-title {
  min-width: 0;
}

.user-modal-title h3 {
  margin: 0 0 4px;
  font-size: 22px;
}

.user-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

.user-detail-grid div {
  min-width: 0;
  padding: 12px;
  border-radius: 12px;
  background: var(--surface-soft);
  border: 1px solid color-mix(in srgb, var(--hairline) 78%, transparent);
}

.user-detail-grid dt {
  margin-bottom: 6px;
  color: var(--text-quiet);
  font-size: 12px;
}

.user-detail-grid dd {
  margin: 0;
  min-width: 0;
  overflow-wrap: anywhere;
  color: var(--text-strong);
  font-size: 14px;
  font-weight: 600;
}

.phone-hint {
  display: block;
  margin-top: 4px;
  color: var(--text-quiet);
  font-size: 12px;
  font-weight: 400;
}

.modal-section {
  display: grid;
  gap: 10px;
}

.modal-section h4 {
  margin: 0;
  font-size: 15px;
}

.modal-actions,
.modal-notice-form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.modal-notice-form {
  align-items: stretch;
}

.modal-notice-form .input,
.modal-notice-form .textarea {
  flex: 1 1 220px;
}

.textarea {
  min-height: 96px;
}

.meta {
  margin: 0;
  color: var(--text-quiet);
}

@media (max-width: 960px) {
  .user-card {
    grid-template-columns: auto 44px minmax(0, 1fr);
  }

  .user-card-more {
    display: none;
  }

  .user-avatar {
    width: 44px;
    height: 44px;
  }

  .user-detail-grid,
  .user-modal-head {
    grid-template-columns: 1fr;
  }

  .user-modal-head {
    justify-items: start;
  }
}
</style>
