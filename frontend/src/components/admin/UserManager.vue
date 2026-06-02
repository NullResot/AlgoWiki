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

    <section class="admin-row notice-card">
      <div class="row-main">
        <strong>单用户公告</strong>
        <p class="meta">
          先用上方用户名 / 邮箱搜索筛选用户，再点击某个用户的“发送公告”。
        </p>
        <p class="meta" v-if="notificationTarget">
          当前目标：{{ notificationTarget.username }} ·
          {{ notificationTarget.email || "未填写邮箱" }}
        </p>
        <p v-else class="meta">当前还没有选择发送对象。</p>
      </div>
      <div class="row-actions">
        <button
          v-if="notificationTarget"
          class="btn btn-mini"
          type="button"
          @click="clearNotificationTarget"
        >
          清空目标
        </button>
      </div>
      <div class="toolbar notice-form">
        <input
          v-model="notificationForm.title"
          class="input"
          placeholder="公告标题"
        />
        <select v-model="notificationForm.level" class="select">
          <option value="info">普通</option>
          <option value="warning">提醒</option>
        </select>
        <input
          v-model="notificationForm.link"
          class="input grow"
          placeholder="跳转链接（可选，如 /profile）"
        />
        <textarea
          v-model="notificationForm.content"
          class="textarea grow"
          placeholder="公告内容"
        ></textarea>
        <button
          class="btn btn-accent"
          type="button"
          :disabled="!notificationTarget || sendingNotificationUserId !== null"
          @click="sendNotificationToUser"
        >
          {{ sendingNotificationUserId !== null ? "发送中..." : "发送公告" }}
        </button>
      </div>
    </section>

    <p class="meta">共 {{ meta.count }} 个用户</p>

    <article
      v-for="item in users"
      :key="item.id"
      class="admin-row"
      :class="{ 'admin-row--focused': Number(item.id) === Number(focusedUserId) }"
    >
      <div class="row-main">
        <label class="check-line">
          <input type="checkbox" :value="item.id" v-model="selectedUserIds" />
          <span>选择</span>
        </label>
        <strong>{{ item.username }}</strong>
        <p class="meta">{{ item.role }} · {{ item.is_active ? "活跃" : "已删除" }} · {{ item.is_banned ? "已封禁" : "正常" }}</p>
        <p class="meta">{{ item.email || "-" }} · {{ item.school_name || "未填写学校" }}</p>
        <p class="meta">
          手机号：{{ item.phone_verification?.phone_masked || "-" }}
          <span v-if="item.phone_verification?.phone_last4"> / 后四位 {{ item.phone_verification.phone_last4 }}</span>
          ·
          {{ formatPhoneVerificationStatus(item.phone_verification?.status) }}
        </p>
        <p class="meta">上次登录：{{ formatLastLogin(item.last_login) }}</p>
      </div>
      <div class="row-actions">
        <button v-if="!item.is_banned" class="btn btn-mini" type="button" @click="banUser(item)">封禁</button>
        <button v-else class="btn btn-mini" type="button" @click="unbanUser(item)">解封</button>
        <button v-if="!item.is_active" class="btn btn-mini" type="button" @click="reactivateUser(item)">恢复</button>
        <button v-if="item.is_active" class="btn btn-mini" type="button" @click="softDeleteUser(item)">删除</button>
        <button v-if="!item.is_active && item.role !== 'superadmin'" class="btn btn-mini" type="button" @click="hardDeleteUser(item)">彻底删除</button>
        <button class="btn btn-mini" type="button" @click="selectNotificationTarget(item)">发送公告</button>
        <template v-if="auth.isSuperAdmin">
          <button v-if="item.role !== 'admin'" class="btn btn-mini" type="button" @click="setRole(item, 'admin')">设为管理员</button>
          <button v-if="item.role !== 'school'" class="btn btn-mini" type="button" @click="setRole(item, 'school')">设为学校用户</button>
          <button v-if="item.role !== 'normal'" class="btn btn-mini" type="button" @click="setRole(item, 'normal')">设为普通用户</button>
        </template>
      </div>
    </article>

    <button v-if="meta.hasMore" class="btn" type="button" @click="loadMoreUsers">加载更多用户</button>
    <p v-if="!users.length" class="meta">当前没有匹配的用户。</p>
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
const notificationTarget = ref(null);
const sendingNotificationUserId = ref(null);
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

function syncNotificationTarget() {
  if (!notificationTarget.value?.id) return;
  const matched = users.value.find((item) => item.id === notificationTarget.value.id);
  if (matched) {
    notificationTarget.value = matched;
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
    syncNotificationTarget();
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

function selectNotificationTarget(item) {
  notificationTarget.value = item;
}

function clearNotificationTarget() {
  notificationTarget.value = null;
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
    if (notificationTarget.value?.id === item.id) {
      notificationTarget.value = null;
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
  if (!notificationTarget.value?.id) {
    ui.info("请先选择一个用户");
    return;
  }
  if (!notificationForm.title.trim() || !notificationForm.content.trim()) {
    ui.info("请填写公告标题和内容");
    return;
  }

  sendingNotificationUserId.value = notificationTarget.value.id;
  try {
    await api.post(`/users/${notificationTarget.value.id}/send-notification/`, {
      title: notificationForm.title.trim(),
      content: notificationForm.content.trim(),
      link: notificationForm.link.trim(),
      level: notificationForm.level,
    });
    ui.success(`已向 ${notificationTarget.value.username} 发送公告`);
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

.grow {
  flex: 1 1 280px;
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

.admin-row--focused {
  border-color: color-mix(in srgb, var(--accent) 45%, var(--hairline));
  background: color-mix(in srgb, var(--accent) 8%, var(--surface-soft));
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 10%, transparent);
}

.notice-card {
  grid-template-columns: minmax(0, 1fr) auto;
}

.row-main {
  min-width: 0;
}

.notice-form {
  grid-column: 1 / -1;
  align-items: stretch;
}

.textarea {
  min-height: 96px;
}

.meta {
  margin: 0;
  color: var(--text-quiet);
}

@media (max-width: 960px) {
  .admin-row {
    grid-template-columns: 1fr;
  }
}
</style>
