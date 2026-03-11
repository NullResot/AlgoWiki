<template>
  <header class="topbar">
    <div class="topbar-inner">
      <button class="menu-toggle" @click="toggleMobileMenu" aria-label="菜单">
        <span></span>
        <span></span>
        <span></span>
      </button>

      <RouterLink class="brand" :to="{ name: 'home' }">AlgoWiki</RouterLink>

      <nav class="desktop-nav">
        <RouterLink class="nav-link" v-for="item in primaryNav" :key="item.name" :to="item.to">{{ item.name }}</RouterLink>
      </nav>

      <form class="search" @submit.prevent="submitSearch">
        <input class="search-input" v-model="searchKeyword" placeholder="搜索" />
      </form>

      <div class="actions">
        <RouterLink v-if="!auth.isAuthenticated" class="auth-pill" :to="{ name: 'auth' }">登录</RouterLink>

        <template v-else>
          <button class="notify-toggle" @click="toggleNoticePanel">
            通知
            <span v-if="unreadCount" class="notify-count">{{ unreadCount > 99 ? "99+" : unreadCount }}</span>
          </button>
          <Transition name="drop">
            <div v-if="showNoticePanel" class="notify-panel">
              <div class="notify-panel-head">
                <strong>站内通知</strong>
                <button class="notify-link" @click="markAllNotificationsRead">全部已读</button>
              </div>
              <div v-if="loadingNotifications" class="notify-empty">加载中...</div>
              <template v-else>
                <button
                  v-for="item in notifications"
                  :key="item.id"
                  class="notify-item"
                  :class="{ 'notify-item--unread': !item.is_read }"
                  @click="openNotification(item)"
                >
                  <span class="notify-title">{{ item.title }}</span>
                  <span class="notify-content">{{ item.content || "点击查看详情" }}</span>
                  <span class="notify-time">{{ formatNotificationTime(item.created_at) }}</span>
                </button>
                <p v-if="!notifications.length" class="notify-empty">暂无通知</p>
              </template>
            </div>
          </Transition>
          <button class="auth-pill user-trigger" @click="toggleUserPanel">{{ auth.user?.username }}</button>
          <Transition name="drop">
            <div v-if="showUserPanel" class="user-panel">
              <p class="user-name">{{ auth.user?.username || "-" }}</p>
              <p class="user-meta">角色：{{ roleText(auth.user?.role) }}</p>
              <p class="user-meta">学校：{{ auth.user?.school_name || "-" }}</p>
              <p class="user-meta">注册：{{ formatJoinDate(auth.user?.date_joined) }}</p>
              <div class="user-actions">
                <RouterLink class="btn btn-mini" :to="{ name: 'profile' }" @click="closeUserPanel">个人中心</RouterLink>
                <button class="btn btn-mini" @click="logout">退出</button>
              </div>
            </div>
          </Transition>
        </template>
      </div>
    </div>

    <Transition name="drop">
      <div v-if="showMobileMenu" class="mobile-panel">
        <form class="mobile-search" @submit.prevent="submitSearch">
          <input class="search-input" v-model="searchKeyword" placeholder="搜索" />
        </form>
        <RouterLink class="mobile-link" v-for="item in primaryNav" :key="item.name" :to="item.to" @click="showMobileMenu = false">
          {{ item.name }}
        </RouterLink>
        <RouterLink
          v-if="auth.isReviewer"
          class="mobile-link"
          :to="{ name: 'review' }"
          @click="showMobileMenu = false"
        >
          审核台
        </RouterLink>
        <RouterLink
          v-if="auth.isManager"
          class="mobile-link"
          :to="{ name: 'admin' }"
          @click="showMobileMenu = false"
        >
          管理台
        </RouterLink>
      </div>
    </Transition>
  </header>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import api from "../services/api";
import { useAuthStore } from "../stores/auth";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const showMobileMenu = ref(false);
const searchKeyword = ref(typeof route.query.search === "string" ? route.query.search : "");
const notifications = ref([]);
const loadingNotifications = ref(false);
const unreadCount = ref(0);
const showNoticePanel = ref(false);
const showUserPanel = ref(false);
let unreadTimer = null;

const primaryNav = computed(() => {
  const nav = [
    { name: "首页", to: { name: "home" } },
    { name: "公告", to: { name: "announcements" } },
    { name: "【打破信息差】", to: { name: "wiki" } },
    { name: "赛事专区", to: { name: "competitions" } },
    { name: "trick技巧", to: { name: "extra", params: { slug: "tricks" } } },
    { name: "问答", to: { name: "questions" } },
    { name: "关于AlgoWiki", to: { name: "extra", params: { slug: "about" } } },
    { name: "友链", to: { name: "friendly-links" } },
  ];
  if (auth.isReviewer) nav.push({ name: "审核", to: { name: "review" } });
  if (auth.isManager) nav.push({ name: "管理", to: { name: "admin" } });
  return nav;
});

function toggleMobileMenu() {
  showMobileMenu.value = !showMobileMenu.value;
}

function closeNoticePanel() {
  showNoticePanel.value = false;
}

function closeUserPanel() {
  showUserPanel.value = false;
}

function toggleUserPanel() {
  showNoticePanel.value = false;
  showUserPanel.value = !showUserPanel.value;
}

async function refreshUnreadCount() {
  if (!auth.isAuthenticated) {
    unreadCount.value = 0;
    return;
  }
  try {
    const { data } = await api.get("/notifications/unread-count/");
    unreadCount.value = Number(data?.count || 0);
  } catch {
    unreadCount.value = 0;
  }
}

async function loadNotifications() {
  if (!auth.isAuthenticated) return;
  loadingNotifications.value = true;
  try {
    const { data } = await api.get("/notifications/", { params: { page: 1 } });
    notifications.value = Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
  } catch {
    notifications.value = [];
  } finally {
    loadingNotifications.value = false;
  }
}

function formatNotificationTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

async function openNotification(item) {
  if (!item?.id) return;
  if (!item.is_read) {
    try {
      await api.post(`/notifications/${item.id}/mark-read/`);
      item.is_read = true;
      item.read_at = new Date().toISOString();
    } catch {
      // Keep navigation flow non-blocking.
    }
  }
  await refreshUnreadCount();
  closeNoticePanel();
  const link = typeof item.link === "string" ? item.link.trim() : "";
  if (link) {
    router.push(link);
  }
}

async function markAllNotificationsRead() {
  if (!auth.isAuthenticated) return;
  try {
    await api.post("/notifications/mark-all-read/");
    notifications.value = notifications.value.map((item) => ({
      ...item,
      is_read: true,
      read_at: item.read_at || new Date().toISOString(),
    }));
    unreadCount.value = 0;
  } catch {
    // Keep panel available even if request fails.
  }
}

async function toggleNoticePanel() {
  if (!auth.isAuthenticated) {
    router.push({ name: "auth" });
    return;
  }
  showUserPanel.value = false;
  showNoticePanel.value = !showNoticePanel.value;
  if (showNoticePanel.value) {
    await loadNotifications();
    await refreshUnreadCount();
  }
}

function startUnreadPolling() {
  stopUnreadPolling();
  if (!auth.isAuthenticated) return;
  unreadTimer = window.setInterval(() => {
    refreshUnreadCount();
  }, 30000);
}

function stopUnreadPolling() {
  if (unreadTimer) {
    window.clearInterval(unreadTimer);
    unreadTimer = null;
  }
}

function submitSearch() {
  const query = searchKeyword.value.trim();
  showMobileMenu.value = false;
  router.push({
    name: "wiki",
    query: query ? { search: query } : {},
  });
}

async function logout() {
  closeUserPanel();
  closeNoticePanel();
  await auth.logout();
  router.push({ name: "home" });
}

function roleText(role) {
  const labels = {
    normal: "普通用户",
    school: "学校用户",
    admin: "管理员",
    superadmin: "超级管理员",
  };
  return labels[role] || role || "-";
}

function formatJoinDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function handleDocumentClick(event) {
  const target = event.target;
  if (!(target instanceof Element)) return;
  if (!target.closest(".actions")) {
    closeNoticePanel();
    closeUserPanel();
  }
}

watch(
  () => route.fullPath,
  () => {
    showMobileMenu.value = false;
    closeNoticePanel();
    closeUserPanel();
    searchKeyword.value = typeof route.query.search === "string" ? route.query.search : "";
  }
);

watch(
  () => auth.isAuthenticated,
  () => {
    closeNoticePanel();
    closeUserPanel();
    notifications.value = [];
    refreshUnreadCount();
    startUnreadPolling();
  },
  { immediate: true }
);

onMounted(() => {
  refreshUnreadCount();
  startUnreadPolling();
  document.addEventListener("click", handleDocumentClick);
});

onBeforeUnmount(() => {
  stopUnreadPolling();
  document.removeEventListener("click", handleDocumentClick);
});
</script>

<style scoped>
.topbar {
  position: sticky;
  top: 0;
  z-index: 30;
  background: rgba(255, 255, 255, 0.86);
  backdrop-filter: blur(16px) saturate(1.25);
  border-bottom: 1px solid var(--hairline);
}

.topbar-inner {
  width: 100%;
  height: 72px;
  margin: 0;
  padding: 0 clamp(16px, 2.6vw, 42px);
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr) auto auto;
  align-items: center;
  gap: clamp(10px, 1.2vw, 16px);
}

.menu-toggle {
  display: none;
  width: 34px;
  height: 34px;
  border: 0;
  border-radius: 9px;
  background: rgba(238, 245, 255, 0.8);
  padding: 6px 7px;
}

.menu-toggle span {
  display: block;
  height: 2px;
  margin: 4px 0;
  background: #333;
}

.brand {
  font-family: "Space Grotesk", "Noto Sans SC", sans-serif;
  font-weight: 700;
  font-size: clamp(38px, 2.7vw, 46px);
  line-height: 1;
  white-space: nowrap;
}

.desktop-nav {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  overflow-x: auto;
  scrollbar-width: none;
}

.desktop-nav::-webkit-scrollbar {
  display: none;
}

.nav-link,
.mini-topic {
  font-size: 14px;
  font-weight: 500;
  color: var(--muted);
  white-space: nowrap;
}

.mini-topic-link:hover {
  color: #4f8fff;
}

.nav-link.router-link-active {
  color: var(--accent);
}

.search {
  width: clamp(250px, 18vw, 360px);
  justify-self: end;
}

.search-input {
  width: 100%;
  height: 38px;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.07);
  background: rgba(245, 246, 250, 0.92);
  padding: 0 14px;
  font-size: 14px;
}

.actions {
  display: flex;
  align-items: center;
  gap: 10px;
  position: relative;
}

.auth-pill {
  border: 1px solid rgba(0, 0, 0, 0.58);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: none;
  padding: 8px 18px;
  font-size: 14px;
  white-space: nowrap;
}

.user-trigger {
  cursor: pointer;
}

.notify-toggle {
  border: 1px solid rgba(0, 0, 0, 0.18);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.85);
  padding: 8px 12px;
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.notify-count {
  min-width: 18px;
  height: 18px;
  border-radius: 999px;
  background: var(--accent);
  color: #fff;
  font-size: 11px;
  line-height: 18px;
  text-align: center;
  padding: 0 4px;
}

.notify-panel {
  position: absolute;
  right: 116px;
  top: 44px;
  width: min(360px, calc(100vw - 28px));
  max-height: 420px;
  overflow: auto;
  border: 1px solid var(--hairline);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: var(--shadow-md);
  padding: 10px;
  display: grid;
  gap: 8px;
  z-index: 35;
}

.notify-panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.notify-link {
  border: 0;
  background: transparent;
  color: var(--accent);
  font-size: 12px;
}

.notify-item {
  border: 1px solid var(--hairline);
  border-radius: 10px;
  background: #fff;
  padding: 9px;
  text-align: left;
  display: grid;
  gap: 3px;
}

.notify-item--unread {
  border-color: rgba(69, 128, 255, 0.35);
  background: rgba(239, 246, 255, 0.9);
}

.notify-title {
  font-size: 13px;
  font-weight: 600;
  color: #1f2630;
}

.notify-content {
  font-size: 12px;
  color: #546071;
}

.notify-time {
  font-size: 11px;
  color: #7b8798;
}

.notify-empty {
  font-size: 12px;
  color: #7a8290;
  margin: 2px 0;
}

.user-panel {
  position: absolute;
  right: 0;
  top: 44px;
  width: 232px;
  border: 1px solid var(--hairline);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: var(--shadow-md);
  padding: 10px;
  display: grid;
  gap: 5px;
  z-index: 36;
}

.user-name {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
}

.user-meta {
  margin: 0;
  font-size: 13px;
  color: #5f6a79;
}

.user-actions {
  margin-top: 6px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.mobile-panel {
  display: none;
}

@media (max-width: 1180px) {
  .topbar-inner {
    grid-template-columns: auto auto minmax(0, 1fr) auto;
  }

  .search {
    display: none;
  }
}

@media (max-width: 960px) {
  .topbar {
    position: sticky;
  }

  .topbar-inner {
    height: 62px;
    padding: 0 12px;
    grid-template-columns: auto auto 1fr auto;
    gap: 10px;
  }

  .menu-toggle {
    display: block;
  }

  .brand {
    font-size: 32px;
  }

  .desktop-nav {
    display: none;
  }

  .actions {
    justify-self: end;
  }

  .notify-panel {
    right: 0;
    top: 42px;
  }

  .mobile-panel {
    display: grid;
    gap: 6px;
    padding: 10px 12px 12px;
    background: rgba(255, 255, 255, 0.95);
    box-shadow: var(--shadow-sm);
  }

  .mobile-search {
    margin-bottom: 6px;
  }

  .mobile-link {
    font-size: 14px;
    color: #252a33;
    padding: 8px 4px;
  }

  .mobile-link--section {
    color: #4f8fff;
    padding-top: 4px;
    padding-bottom: 4px;
  }
}

@media (max-width: 620px) {
  .auth-pill {
    padding: 7px 13px;
    font-size: 13px;
  }

  .notify-toggle {
    padding: 7px 10px;
  }

  .brand {
    font-size: 28px;
  }
}

.drop-enter-active,
.drop-leave-active {
  transition: all 0.2s ease;
}

.drop-enter-from,
.drop-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
