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
        <div class="theme-anchor">
          <button class="theme-toggle" @click="toggleThemePanel" type="button">
            <span class="theme-toggle-swatch" :class="`theme-toggle-swatch--${theme.currentTheme}`"></span>
            <span class="theme-toggle-label">{{ activeThemeLabel }}</span>
          </button>
          <Transition name="drop">
            <div v-if="showThemePanel" class="theme-panel">
              <button
                v-for="item in themeOptions"
                :key="item.id"
                type="button"
                class="theme-option"
                :class="{ 'theme-option--active': item.id === theme.currentTheme }"
                @click="applyTheme(item.id)"
              >
                <span class="theme-option-swatch" :class="`theme-option-swatch--${item.id}`"></span>
                <span class="theme-option-copy">
                  <strong>{{ item.label }}</strong>
                  <small>{{ item.name }}</small>
                </span>
              </button>
            </div>
          </Transition>
        </div>
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
        <div class="mobile-theme-group">
          <span class="mobile-theme-label">切换主题</span>
          <div class="mobile-theme-options">
            <button
              v-for="item in themeOptions"
              :key="`mobile-theme-${item.id}`"
              type="button"
              class="mobile-theme-btn"
              :class="{ 'mobile-theme-btn--active': item.id === theme.currentTheme }"
              @click="applyTheme(item.id)"
            >
              {{ item.label }}
            </button>
          </div>
        </div>
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
        <RouterLink
          v-if="auth.isAuthenticated"
          class="mobile-link mobile-link--accent"
          :to="{ name: 'profile' }"
          @click="showMobileMenu = false"
        >
          个人中心
        </RouterLink>
        <RouterLink
          v-else
          class="mobile-link mobile-link--accent"
          :to="{ name: 'auth' }"
          @click="showMobileMenu = false"
        >
          登录 / 注册
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
import { useThemeStore } from "../stores/theme";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const theme = useThemeStore();

const showMobileMenu = ref(false);
const searchKeyword = ref(typeof route.query.search === "string" ? route.query.search : "");
const notifications = ref([]);
const loadingNotifications = ref(false);
const unreadCount = ref(0);
const showNoticePanel = ref(false);
const showUserPanel = ref(false);
const showThemePanel = ref(false);
let unreadTimer = null;

const themeOptions = computed(() => theme.options);
const activeThemeLabel = computed(() => theme.activeTheme?.label || "Theme");

const primaryNav = computed(() => {
  const nav = [
    { name: "首页", to: { name: "home" } },
    { name: "公告", to: { name: "announcements" } },
    { name: "【打破信息差】", to: { name: "wiki" } },
    { name: "赛事专区", to: { name: "competitions" } },
    { name: "比赛日历表", to: { name: "competition-calendar" } },
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
  closeThemePanel();
  showMobileMenu.value = !showMobileMenu.value;
}

function closeNoticePanel() {
  showNoticePanel.value = false;
}

function closeUserPanel() {
  showUserPanel.value = false;
}

function closeThemePanel() {
  showThemePanel.value = false;
}

function toggleUserPanel() {
  showNoticePanel.value = false;
  closeThemePanel();
  showUserPanel.value = !showUserPanel.value;
}

function toggleThemePanel() {
  closeNoticePanel();
  closeUserPanel();
  showThemePanel.value = !showThemePanel.value;
}

function applyTheme(themeId) {
  theme.setTheme(themeId);
  closeThemePanel();
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
  closeThemePanel();
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
    closeThemePanel();
  }
}

watch(
  () => route.fullPath,
  () => {
    showMobileMenu.value = false;
    closeNoticePanel();
    closeUserPanel();
    closeThemePanel();
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
  background: var(--nav-bg);
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
  min-width: 0;
}

.menu-toggle {
  display: none;
  width: 34px;
  height: 34px;
  border: 1px solid var(--nav-pill-border);
  border-radius: 9px;
  background: var(--surface-soft);
  padding: 6px 7px;
}

.menu-toggle span {
  display: block;
  height: 2px;
  margin: 4px 0;
  background: var(--text);
}

.brand {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: clamp(38px, 2.7vw, 46px);
  line-height: 1;
  white-space: nowrap;
  min-width: 0;
  color: var(--text-strong);
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
  color: var(--nav-link);
  white-space: nowrap;
}

.mini-topic-link:hover {
  color: var(--accent);
}

.nav-link.router-link-active {
  color: var(--nav-link-active);
}

.search {
  width: clamp(250px, 18vw, 360px);
  justify-self: end;
}

.search-input {
  width: 100%;
  height: 38px;
  border-radius: 12px;
  border: 1px solid var(--search-border);
  background: var(--search-bg);
  padding: 0 14px;
  font-size: 14px;
  color: var(--text);
}

.actions {
  display: flex;
  align-items: center;
  gap: 10px;
  position: relative;
  min-width: 0;
}

.theme-anchor {
  position: relative;
}

.theme-toggle,
.auth-pill {
  border: 1px solid var(--nav-pill-border);
  border-radius: 999px;
  background: var(--nav-pill-bg);
  color: var(--text-strong);
  box-shadow: var(--shadow-sm);
  padding: 8px 18px;
  font-size: 14px;
  white-space: nowrap;
}

.theme-toggle {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  padding: 8px 14px;
  cursor: pointer;
}

.theme-toggle-swatch,
.theme-option-swatch {
  display: inline-flex;
  width: 16px;
  height: 16px;
  border-radius: 999px;
  border: 1px solid rgba(17, 17, 17, 0.18);
  flex: 0 0 auto;
}

.theme-toggle-swatch--modern,
.theme-option-swatch--modern {
  background: linear-gradient(135deg, #7c5cff 0%, #4b8dff 100%);
}

.theme-toggle-swatch--academic,
.theme-option-swatch--academic {
  background: linear-gradient(135deg, #111111 0%, #8a6f50 100%);
}

.theme-toggle-swatch--geek,
.theme-option-swatch--geek {
  background: linear-gradient(135deg, #ffe45c 0%, #ffca28 100%);
}

.theme-toggle-label {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.theme-panel {
  position: absolute;
  right: 0;
  top: 48px;
  width: 240px;
  border: 1px solid var(--panel-border);
  border-radius: 16px;
  background: var(--surface-overlay);
  box-shadow: var(--shadow-md);
  padding: 8px;
  display: grid;
  gap: 6px;
  z-index: 36;
}

.theme-option {
  border: 1px solid transparent;
  border-radius: 12px;
  background: transparent;
  padding: 10px 11px;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  text-align: left;
  color: var(--text);
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    background-color 0.18s ease,
    transform 0.18s ease;
}

.theme-option:hover {
  transform: translateY(-1px);
  border-color: var(--hairline-strong);
  background: var(--surface-soft);
}

.theme-option--active {
  border-color: color-mix(in srgb, var(--accent) 32%, transparent);
  background: color-mix(in srgb, var(--accent) 9%, var(--surface-strong));
}

.theme-option-copy {
  display: grid;
  gap: 2px;
}

.theme-option-copy strong {
  font-size: 13px;
  color: var(--text-strong);
}

.theme-option-copy small {
  font-size: 11px;
  color: var(--text-quiet);
}

.user-trigger {
  cursor: pointer;
  max-width: 132px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.notify-toggle {
  border: 1px solid var(--nav-pill-border);
  border-radius: 999px;
  background: var(--nav-pill-bg);
  color: var(--text-strong);
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
  border: 1px solid var(--panel-border);
  border-radius: 12px;
  background: var(--surface-overlay);
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
  border: 1px solid var(--panel-border);
  border-radius: 10px;
  background: var(--surface-strong);
  padding: 9px;
  text-align: left;
  display: grid;
  gap: 3px;
}

.notify-item--unread {
  border-color: color-mix(in srgb, var(--accent) 35%, transparent);
  background: color-mix(in srgb, var(--accent) 10%, var(--surface-strong));
}

.notify-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-strong);
}

.notify-content {
  font-size: 12px;
  color: var(--text-soft);
}

.notify-time {
  font-size: 11px;
  color: var(--text-quiet);
}

.notify-empty {
  font-size: 12px;
  color: var(--text-quiet);
  margin: 2px 0;
}

.user-panel {
  position: absolute;
  right: 0;
  top: 44px;
  width: 232px;
  border: 1px solid var(--panel-border);
  border-radius: 12px;
  background: var(--surface-overlay);
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
  color: var(--text-soft);
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

.mobile-theme-group {
  display: grid;
  gap: 8px;
  margin-bottom: 4px;
}

.mobile-theme-label {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-quiet);
}

.mobile-theme-options {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.mobile-theme-btn {
  border: 1px solid var(--nav-pill-border);
  border-radius: 999px;
  background: var(--nav-pill-bg);
  color: var(--text-strong);
  padding: 7px 12px;
  font-size: 13px;
  font-weight: 600;
}

.mobile-theme-btn--active {
  background: var(--accent-gradient);
  color: var(--accent-contrast);
  border-color: transparent;
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
    position: fixed;
    left: 12px;
    right: 12px;
    top: 72px;
    width: auto;
    max-height: min(58vh, 420px);
  }

  .user-panel {
    position: fixed;
    left: 12px;
    right: 12px;
    top: 72px;
    width: auto;
  }

  .mobile-panel {
    display: grid;
    gap: 6px;
    padding: 10px 12px 12px;
    background: var(--surface-overlay);
    box-shadow: var(--shadow-sm);
    border-top: 1px solid var(--hairline);
    max-height: calc(100vh - 62px);
    overflow: auto;
  }

  .mobile-search {
    margin-bottom: 6px;
  }

  .mobile-link {
    font-size: 14px;
    color: var(--text-strong);
    padding: 12px 10px;
    border-radius: 12px;
    background: var(--surface-soft);
  }

  .mobile-link--section {
    color: var(--accent);
    padding-top: 4px;
    padding-bottom: 4px;
  }

  .mobile-link--accent {
    color: var(--accent);
    background: color-mix(in srgb, var(--accent) 12%, transparent);
    font-weight: 600;
  }
}

@media (max-width: 620px) {
  .topbar-inner {
    height: 58px;
    padding: 0 10px;
    grid-template-columns: auto minmax(0, 1fr) auto;
    gap: 8px;
  }

  .auth-pill {
    padding: 7px 11px;
    font-size: 13px;
  }

  .notify-toggle {
    min-width: 42px;
    padding: 7px 9px;
    justify-content: center;
  }

  .theme-toggle {
    min-width: 42px;
    padding: 7px 9px;
    justify-content: center;
  }

  .theme-toggle-label {
    display: none;
  }

  .brand {
    font-size: 24px;
  }

  .actions {
    gap: 6px;
  }

  .user-trigger {
    max-width: 88px;
  }

  .notify-panel,
  .user-panel {
    top: 64px;
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
