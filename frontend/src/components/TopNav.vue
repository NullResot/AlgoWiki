<template>
  <header class="topbar">
    <div class="topbar-inner">
      <button class="menu-toggle" @click="toggleMobileMenu" aria-label="菜单">
        <span></span>
        <span></span>
        <span></span>
      </button>

      <RouterLink class="brand" :to="{ name: 'home' }" aria-label="返回 AlgoWiki 首页">
        <span class="brand-mark">
          <SiteLogo decorative />
        </span>
        <span class="brand-wordmark">AlgoWiki</span>
      </RouterLink>

      <nav class="desktop-nav" @mouseleave="handleDesktopNavLeave">
        <template v-for="item in primaryNav" :key="item.key">
          <div
            v-if="item.kind === 'dropdown'"
            class="nav-dropdown"
            :class="{ 'nav-dropdown--active': isNavActive(item) }"
            :data-dropdown-key="item.key"
            @mouseenter="openDropdown(item.key)"
            @mouseleave="scheduleCloseDropdown(item.key)"
            @focusin="openDropdown(item.key)"
            @focusout="handleDropdownFocusout(item.key, $event)"
          >
            <RouterLink :to="item.to" custom v-slot="{ href, navigate }">
              <a
                :href="href"
                class="nav-link nav-link--dropdown"
                :class="{ 'nav-link--active': isNavActive(item) }"
                @click="handleDropdownTriggerClick(item.key, navigate, $event)"
              >
                {{ item.name }}
              </a>
            </RouterLink>

            <div
              class="nav-dropdown-panel"
              :class="{ 'nav-dropdown-panel--open': openDropdownKey === item.key }"
              @mouseenter="openDropdown(item.key)"
              @mouseleave="scheduleCloseDropdown(item.key)"
            >
              <RouterLink
                v-for="child in item.children"
                :key="child.key"
                :to="child.to"
                custom
                v-slot="{ href, navigate }"
              >
                <a
                  :href="href"
                  class="nav-dropdown-link"
                  :class="{ 'nav-dropdown-link--active': isNavActive(child) }"
                  @click="handleDropdownNavigate(navigate, $event)"
                >
                  {{ child.name }}
                </a>
              </RouterLink>
            </div>
          </div>

          <RouterLink v-else :to="item.to" custom v-slot="{ href, navigate }">
            <a :href="href" class="nav-link" :class="{ 'nav-link--active': isNavActive(item) }" @click="navigate">
              {{ item.name }}
            </a>
          </RouterLink>
        </template>
      </nav>

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
              <div v-if="auth.isReviewer || auth.isManager" class="user-admin-links">
                <RouterLink
                  v-if="auth.isReviewer"
                  class="btn btn-mini"
                  :to="{ name: 'review' }"
                  @click="closeUserPanel"
                >
                  审核
                </RouterLink>
                <RouterLink
                  v-if="auth.isManager"
                  class="btn btn-mini"
                  :to="{ name: 'admin' }"
                  @click="closeUserPanel"
                >
                  管理
                </RouterLink>
              </div>
            </div>
          </Transition>
        </template>
      </div>
    </div>

    <Transition name="drop">
      <div v-if="showMobileMenu" class="mobile-panel">
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
        <template v-for="item in primaryNav" :key="`mobile-${item.key}`">
          <div v-if="item.kind === 'dropdown'" class="mobile-group">
            <span class="mobile-group-title">{{ item.name }}</span>
            <RouterLink
              v-for="child in item.children"
              :key="`mobile-${child.key}`"
              :to="child.to"
              custom
              v-slot="{ href, navigate }"
            >
              <a
                :href="href"
                class="mobile-link mobile-link--child"
                :class="{ 'mobile-link--active': isNavActive(child) }"
                @click="
                  (event) => {
                    showMobileMenu = false;
                    navigate(event);
                  }
                "
              >
                {{ child.name }}
              </a>
            </RouterLink>
          </div>

          <RouterLink v-else :to="item.to" custom v-slot="{ href, navigate }">
            <a
              :href="href"
              class="mobile-link"
              :class="{ 'mobile-link--active': isNavActive(item) }"
              @click="
                (event) => {
                  showMobileMenu = false;
                  navigate(event);
                }
              "
            >
              {{ item.name }}
            </a>
          </RouterLink>
        </template>
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
import { useCompetitionZoneNav } from "../composables/useCompetitionZoneNav";
import { useHeaderNav } from "../composables/useHeaderNav";
import { useSectionNav } from "../composables/useSectionNav";
import SiteLogo from "./SiteLogo.vue";
import { useAuthStore } from "../stores/auth";
import { useThemeStore } from "../stores/theme";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const theme = useThemeStore();
const { sectionNav, loadSectionNav } = useSectionNav();
const { headerNav, loadHeaderNav } = useHeaderNav();
const { competitionZoneNav, loadCompetitionZoneNav } = useCompetitionZoneNav();

const showMobileMenu = ref(false);
const notifications = ref([]);
const loadingNotifications = ref(false);
const unreadCount = ref(0);
const showNoticePanel = ref(false);
const showUserPanel = ref(false);
const showThemePanel = ref(false);
const openDropdownKey = ref("");
const pinnedDropdownKey = ref("");
const suppressDropdownHover = ref(false);
let unreadTimer = null;
let dropdownCloseTimer = null;

const themeOptions = computed(() => theme.options);
const activeThemeLabel = computed(() => theme.activeTheme?.label || "Theme");
const preferredCompetitionWikiOrder = [
  "关键网站",
  "竞赛概念",
  "比赛介绍",
  "常见术语",
  "代码工具",
  "阶段任务",
  "关于训练",
];

function normalizeNavLabel(value) {
  return String(value || "").replace(/^\s*\d+\s*[.．、]\s*/, "").trim();
}

function getCompetitionWikiPriority(name) {
  const normalizedName = normalizeNavLabel(name);
  const index = preferredCompetitionWikiOrder.findIndex((item) => item === normalizedName);
  return index >= 0 ? index : preferredCompetitionWikiOrder.length + 100;
}

const headerSectionNav = computed(() => {
  return (sectionNav.value || [])
    .map((item) => {
      const category = item.slug || String(item.id || "");
      const normalized = normalizeNavLabel(item.label);
      return {
        key: `section-${category || item.id}`,
        name: normalized || category,
        to: { name: "wiki", query: category ? { category } : {} },
        kind: "wiki-category",
        category,
        order: Number(item.order || 0),
        normalizedName: normalized || category,
      };
    })
    .filter((item) => item.name)
    .sort((left, right) => {
      const priorityDelta =
        getCompetitionWikiPriority(left.normalizedName) - getCompetitionWikiPriority(right.normalizedName);
      if (priorityDelta !== 0) return priorityDelta;
      const orderDelta = Number(left.order || 0) - Number(right.order || 0);
      if (orderDelta !== 0) return orderDelta;
      return String(left.name || "").localeCompare(String(right.name || ""), "zh-Hans-CN");
    });
});

const preferredCompetitionWikiEntry = computed(
  () =>
    headerSectionNav.value.find(
      (item) => item.normalizedName === "关键网站" || String(item.category || "") === "key-sites"
    ) ||
    headerSectionNav.value.find((item) => item.category) ||
    null
);

const competitionWikiNav = computed(() => ({
  key: "competition-wiki",
  name: "竞赛wiki",
  to: preferredCompetitionWikiEntry.value?.to || { name: "wiki" },
  kind: "dropdown",
  routeNames: ["wiki", "article"],
  children: headerSectionNav.value,
}));

const competitionSectionNav = computed(() =>
  (competitionZoneNav.value || [])
    .map((item) => ({
      key: `competition-section-${item.key}`,
      name: item.title,
      to: { name: "competitions", query: { tab: item.key } },
      kind: "route",
      routeNames: ["competitions", "competition-calendar", "questions"],
      queryTab: item.key,
      extraSlugs: item.builtin_view === "tricks" ? ["tricks"] : [],
      targetType: item.target_type,
      builtinView: item.builtin_view,
      pageSlug: item.page_slug,
    }))
    .filter((item) => item.name && item.queryTab)
);

const preferredCompetitionSectionEntry = computed(
  () => competitionSectionNav.value.find((item) => item.queryTab) || null
);

const headerNavConfigMap = computed(() => {
  const map = new Map();
  for (const item of headerNav.value || []) {
    map.set(String(item.key || ""), item);
  }
  return map;
});

const primaryNav = computed(() => {
  const configuredItems = [
    { key: "home", defaultName: "首页", to: { name: "home" }, kind: "route", routeNames: ["home"] },
    {
      ...competitionWikiNav.value,
      defaultName: "竞赛wiki",
    },
    {
      key: "competitions",
      defaultName: "赛事专区",
      to: preferredCompetitionSectionEntry.value?.to || { name: "competitions", query: { tab: "calendar" } },
      kind: "dropdown",
      routeNames: ["competitions", "competition-calendar", "questions"],
      extraSlugs: ["tricks"],
      children: competitionSectionNav.value,
    },
    {
      key: "about",
      defaultName: "关于AlgoWiki",
      to: { name: "extra", params: { slug: "about" } },
      kind: "route",
      routeNames: ["extra"],
      slug: "about",
    },
    {
      key: "friendly-links",
      defaultName: "友链",
      to: { name: "friendly-links" },
      kind: "route",
      routeNames: ["friendly-links"],
    },
  ];

  return configuredItems
    .map((item) => {
      const config = headerNavConfigMap.value.get(String(item.key || ""));
      return {
        ...item,
        name: String(config?.title || item.defaultName || item.name || "").trim(),
        display_order: Number(config?.display_order || 0),
        is_visible: config?.is_visible !== false,
      };
    })
    .filter((item) => item.name && item.is_visible)
    .sort((left, right) => {
      const orderDelta = Number(left.display_order || 0) - Number(right.display_order || 0);
      if (orderDelta !== 0) return orderDelta;
      return String(left.key || "").localeCompare(String(right.key || ""));
    });
});

function isNavActive(item) {
  if (!item) return false;
  if (item.kind === "dropdown") {
    if (Array.isArray(item.routeNames) && item.routeNames.includes(String(route.name || ""))) {
      if (Array.isArray(item.extraSlugs) && route.name === "extra" && item.extraSlugs.includes(String(route.params.slug || ""))) {
        return true;
      }
      return true;
    }
    return Array.isArray(item.children) && item.children.some((child) => isNavActive(child));
  }
  if (item.kind === "wiki-category") {
    return route.name === "wiki" && String(route.query.category || "") === String(item.category || "");
  }
  if (item.kind === "route") {
    if (item.slug) {
      return route.name === "extra" && String(route.params.slug || "") === String(item.slug);
    }
    if (Array.isArray(item.extraSlugs) && route.name === "extra") {
      return item.extraSlugs.includes(String(route.params.slug || ""));
    }
    if (item.queryTab) {
      const currentTab = String(route.query.tab || "schedule");
      return Array.isArray(item.routeNames) && item.routeNames.includes(String(route.name || "")) && currentTab === String(item.queryTab);
    }
    return Array.isArray(item.routeNames) ? item.routeNames.includes(String(route.name || "")) : route.name === item.to?.name;
  }
  return false;
}

function toggleMobileMenu() {
  pinnedDropdownKey.value = "";
  closeDropdowns();
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

function clearDropdownCloseTimer() {
  if (dropdownCloseTimer) {
    window.clearTimeout(dropdownCloseTimer);
    dropdownCloseTimer = null;
  }
}

function openDropdown(key) {
  if (suppressDropdownHover.value) return;
  if (pinnedDropdownKey.value && pinnedDropdownKey.value !== String(key || "")) return;
  clearDropdownCloseTimer();
  openDropdownKey.value = String(key || "");
}

function closeDropdowns() {
  clearDropdownCloseTimer();
  openDropdownKey.value = "";
}

function scheduleCloseDropdown(key) {
  if (pinnedDropdownKey.value === String(key || "")) return;
  clearDropdownCloseTimer();
  const dropdownKey = String(key || "");
  dropdownCloseTimer = window.setTimeout(() => {
    if (openDropdownKey.value === dropdownKey) {
      openDropdownKey.value = "";
    }
    dropdownCloseTimer = null;
  }, 120);
}

function handleDropdownFocusout(key, event) {
  if (pinnedDropdownKey.value === String(key || "")) {
    return;
  }
  const nextTarget = event.relatedTarget;
  if (
    nextTarget instanceof Element &&
    nextTarget.closest(`[data-dropdown-key="${String(key || "")}"]`)
  ) {
    return;
  }
  closeDropdowns();
}

function handleDropdownNavigate(navigate, event) {
  suppressDropdownHover.value = true;
  pinnedDropdownKey.value = "";
  closeDropdowns();
  navigate(event);
  window.setTimeout(() => {
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
  }, 0);
}

function handleDropdownTriggerClick(key, navigate, event) {
  const dropdownKey = String(key || "");
  clearDropdownCloseTimer();
  if (pinnedDropdownKey.value !== dropdownKey) {
    event.preventDefault();
    suppressDropdownHover.value = false;
    pinnedDropdownKey.value = dropdownKey;
    openDropdownKey.value = dropdownKey;
    return;
  }
  handleDropdownNavigate(navigate, event);
}

function handleDesktopNavLeave() {
  if (!pinnedDropdownKey.value) {
    closeDropdowns();
  }
  suppressDropdownHover.value = false;
}

function toggleUserPanel() {
  pinnedDropdownKey.value = "";
  closeDropdowns();
  showNoticePanel.value = false;
  closeThemePanel();
  showUserPanel.value = !showUserPanel.value;
}

function toggleThemePanel() {
  pinnedDropdownKey.value = "";
  closeDropdowns();
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
  pinnedDropdownKey.value = "";
  closeDropdowns();
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

async function logout() {
  pinnedDropdownKey.value = "";
  closeDropdowns();
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
  if (!target.closest(".desktop-nav")) {
    pinnedDropdownKey.value = "";
    closeDropdowns();
    suppressDropdownHover.value = false;
  }
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
    pinnedDropdownKey.value = "";
    closeDropdowns();
    suppressDropdownHover.value = false;
    closeNoticePanel();
    closeUserPanel();
    closeThemePanel();
  }
);

watch(
  () => auth.isAuthenticated,
  () => {
    pinnedDropdownKey.value = "";
    closeDropdowns();
    suppressDropdownHover.value = false;
    closeNoticePanel();
    closeUserPanel();
    notifications.value = [];
    refreshUnreadCount();
    startUnreadPolling();
  },
  { immediate: true }
);

onMounted(() => {
  loadHeaderNav();
  loadSectionNav();
  loadCompetitionZoneNav();
  refreshUnreadCount();
  startUnreadPolling();
  document.addEventListener("click", handleDocumentClick);
});

onBeforeUnmount(() => {
  stopUnreadPolling();
  clearDropdownCloseTimer();
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
  grid-template-columns: auto auto minmax(0, 1fr) auto;
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
  display: inline-flex;
  align-items: center;
  gap: 12px;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: clamp(38px, 2.7vw, 46px);
  line-height: 1;
  white-space: nowrap;
  min-width: 0;
  color: var(--text-strong);
}

.brand-mark {
  width: clamp(38px, 2.8vw, 46px);
  height: clamp(38px, 2.8vw, 46px);
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.brand-wordmark {
  display: inline-block;
  transform: translateY(1px);
}

.desktop-nav {
  display: flex;
  align-items: stretch;
  align-self: stretch;
  height: 100%;
  gap: 4px;
  min-width: 0;
  overflow: visible;
  flex-wrap: nowrap;
}

.desktop-nav > * {
  width: auto;
  height: 100%;
  min-width: max-content;
  flex: 0 0 auto;
}

.nav-link,
.mini-topic {
  display: flex;
  align-items: center;
  justify-content: center;
  width: auto;
  height: 100%;
  min-height: 100%;
  padding: 0 14px;
  font-size: 14px;
  font-weight: 500;
  color: var(--nav-link);
  white-space: nowrap;
  text-align: center;
}

.nav-link--active {
  color: var(--nav-link-active);
}

.nav-dropdown {
  position: relative;
  display: flex;
  align-items: stretch;
  width: auto;
  height: 100%;
}

.nav-dropdown::after {
  content: "";
  position: absolute;
  left: -18px;
  top: 100%;
  width: 228px;
  height: 16px;
}

.nav-link--dropdown::after {
  content: "▾";
  display: inline-block;
  margin-left: 6px;
  font-size: 11px;
  transform: translateY(-1px);
}

.nav-dropdown-panel {
  position: absolute;
  left: 0;
  top: calc(100% + 6px);
  min-width: 188px;
  padding: 10px;
  border: 1px solid var(--panel-border);
  border-radius: 14px;
  background: var(--surface-overlay);
  box-shadow: var(--shadow-md);
  display: grid;
  gap: 6px;
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transform: translateY(-6px);
  transition:
    opacity 0.18s ease,
    visibility 0.18s ease,
    transform 0.18s ease;
  z-index: 34;
}

.nav-dropdown-panel::before {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  top: -16px;
  height: 16px;
}

.nav-dropdown-panel--open {
  opacity: 1;
  visibility: visible;
  pointer-events: auto;
  transform: translateY(0);
}

.nav-dropdown-link {
  border: 1px solid transparent;
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 13px;
  color: var(--text-soft);
  background: transparent;
  transition:
    color 0.18s ease,
    background-color 0.18s ease,
    border-color 0.18s ease;
}

.nav-dropdown-link:hover,
.nav-dropdown-link--active {
  color: var(--nav-link-active);
  background: color-mix(in srgb, var(--accent) 10%, var(--surface-strong));
  border-color: color-mix(in srgb, var(--accent) 20%, transparent);
}

.actions {
  display: flex;
  align-items: center;
  gap: 10px;
  position: relative;
  min-width: 0;
  justify-self: end;
  margin-left: auto;
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

.user-admin-links {
  margin-top: 6px;
  padding-top: 10px;
  border-top: 1px solid var(--hairline);
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.user-admin-links .btn {
  flex: 1 1 calc(50% - 4px);
}

.mobile-panel {
  display: none;
}

.mobile-group {
  display: grid;
  gap: 6px;
}

.mobile-group-title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-quiet);
  padding: 4px 2px 0;
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

  .brand-mark {
    width: 34px;
    height: 34px;
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

  .mobile-link {
    font-size: 14px;
    color: var(--text-strong);
    padding: 12px 10px;
    border-radius: 12px;
    background: var(--surface-soft);
  }

  .mobile-link--child {
    margin-left: 12px;
  }

  .mobile-link--active {
    color: var(--accent);
    background: color-mix(in srgb, var(--accent) 12%, transparent);
    font-weight: 600;
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
    gap: 8px;
  }

  .brand-mark {
    width: 28px;
    height: 28px;
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
