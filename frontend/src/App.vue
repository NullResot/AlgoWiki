<template>
  <div class="app-shell" :class="`app-shell--${theme.currentTheme}`">
    <TopNav />
    <AnnouncementBanner />
    <ToastStack />
    <ConfirmDialog />
    <CaptchaDialog />
    <ChatAssistantLauncher />
    <main
      class="page-shell"
      :class="{
        'page-shell--flush': isHomeLayout,
        'page-shell--pulse': isPulseLayout,
      }"
    >
      <RouterView v-slot="{ Component, route: viewRoute }">
        <Transition name="aw-route" mode="out-in">
          <component :is="Component" :key="resolveRouteViewKey(viewRoute)" />
        </Transition>
      </RouterView>
    </main>
    <BackToTop v-if="!isPulseLayout" />
    <footer v-if="!isPulseLayout" class="site-footer">
      <a
        class="site-footer__record"
        href="https://beian.miit.gov.cn/"
        target="_blank"
        rel="noopener noreferrer"
      >
        鲁ICP备2026012550号-1
      </a>
    </footer>
    <AnnouncementModal
      :visible="showAnnouncement"
      :announcement="activeAnnouncement"
      @close="dismissAnnouncement"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, watch } from "vue";
import { RouterView, useRoute, useRouter } from "vue-router";
import AnnouncementBanner from "./components/AnnouncementBanner.vue";
import AnnouncementModal from "./components/AnnouncementModal.vue";
import BackToTop from "./components/BackToTop.vue";
import CaptchaDialog from "./components/captcha/CaptchaDialog.vue";
import ChatAssistantLauncher from "./components/ChatAssistantLauncher.vue";
import ConfirmDialog from "./components/ConfirmDialog.vue";
import TopNav from "./components/TopNav.vue";
import ToastStack from "./components/ToastStack.vue";
import { useAnnouncementPopup } from "./composables/useAnnouncementPopup";
import { useScrollGradientTheme } from "./composables/useScrollGradientTheme";
import { useAuthStore } from "./stores/auth";
import { useThemeStore } from "./stores/theme";
import { useUiStore } from "./stores/ui";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const theme = useThemeStore();
const ui = useUiStore();
const isHomeLayout = computed(() => route.name === "home");
const isPulseLayout = computed(() => route.name === "pulse");
const { showAnnouncement, activeAnnouncement, dismissAnnouncement } = useAnnouncementPopup(auth);

function resolveRouteViewKey(viewRoute) {
  const name = String(viewRoute?.name || viewRoute?.path || "view");
  if (name.startsWith("manage")) return "admin-shell";
  if (name.startsWith("review") && name !== "review-revision") return "review-shell";
  if (name.startsWith("profile")) return "profile-shell";
  if (name === "extra") return `extra-${String(viewRoute?.params?.slug || "")}`;
  if (name === "article") return `article-${String(viewRoute?.params?.id || "")}`;
  if (name === "pulse-discussion-detail") return `pulse-discussion-${String(viewRoute?.params?.date || "")}`;
  return name;
}

theme.init();
const stopPulseThemeWatch = watch(
  isPulseLayout,
  (isPulse) => {
    document.documentElement.classList.toggle("pulse-route-active", isPulse);
    if (isPulse) theme.beginTemporaryTheme("midnight");
    else theme.endTemporaryTheme();
  },
  { immediate: true, flush: "sync" }
);
useScrollGradientTheme();

function handleInvalidToken() {
  const wasAuthenticated = auth.isAuthenticated;
  auth.clearAuth();
  if (!wasAuthenticated) return;
  ui.info("登录状态已过期，请重新登录。", "登录提醒");
  if (route.meta?.requiresAuth || route.meta?.requiresManager) {
    const redirect = route.fullPath && route.fullPath !== "/auth" ? route.fullPath : undefined;
    router.push({ name: "auth", query: redirect ? { redirect } : undefined });
  }
}

onMounted(() => {
  window.addEventListener("algowiki:auth-invalid", handleInvalidToken);
});

onBeforeUnmount(() => {
  stopPulseThemeWatch();
  document.documentElement.classList.remove("pulse-route-active");
  theme.endTemporaryTheme();
  window.removeEventListener("algowiki:auth-invalid", handleInvalidToken);
});
</script>

<style scoped>
.app-shell {
  display: flex;
  min-height: 100vh;
  flex-direction: column;
}

.page-shell {
  flex: 1 0 auto;
}

.page-shell--pulse {
  padding: 0;
}

@media (min-width: 1121px) {
  .page-shell--pulse {
    flex: 0 0 auto;
    width: 100%;
    height: calc(100dvh - 72px);
    min-height: 0;
    overflow: hidden;
  }
}

.site-footer {
  display: flex;
  justify-content: center;
  padding: 0 16px 18px;
}

.site-footer__record {
  color: var(--text-quiet);
  font-size: 12px;
  line-height: 1.5;
  text-decoration: none;
  transition: color var(--dur-fast, 150ms) var(--ease-standard, ease);
}

.site-footer__record:hover {
  color: var(--text-soft);
  text-decoration: underline;
}

@media (max-width: 960px) {
  .site-footer {
    padding: 0 12px 14px;
  }
}
</style>
