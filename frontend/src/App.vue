<template>
  <div class="app-shell" :class="`app-shell--${theme.currentTheme}`">
    <TopNav />
    <AnnouncementBanner />
    <ToastStack />
    <CaptchaDialog />
    <ChatAssistantLauncher />
    <main
      class="page-shell"
      :class="{
        'page-shell--flush': isHomeLayout,
        'page-shell--pulse': isPulseLayout,
      }"
    >
      <RouterView />
    </main>
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
import { RouterView } from "vue-router";
import { useRoute } from "vue-router";
import AnnouncementBanner from "./components/AnnouncementBanner.vue";
import AnnouncementModal from "./components/AnnouncementModal.vue";
import CaptchaDialog from "./components/captcha/CaptchaDialog.vue";
import ChatAssistantLauncher from "./components/ChatAssistantLauncher.vue";
import TopNav from "./components/TopNav.vue";
import ToastStack from "./components/ToastStack.vue";
import { useAnnouncementPopup } from "./composables/useAnnouncementPopup";
import { useScrollGradientTheme } from "./composables/useScrollGradientTheme";
import { useAuthStore } from "./stores/auth";
import { useThemeStore } from "./stores/theme";

const route = useRoute();
const auth = useAuthStore();
const theme = useThemeStore();
const isHomeLayout = computed(() => route.name === "home");
const isPulseLayout = computed(() => route.name === "pulse-demo");
const { showAnnouncement, activeAnnouncement, dismissAnnouncement } = useAnnouncementPopup(auth);

theme.init();
const stopPulseThemeWatch = watch(
  isPulseLayout,
  (isPulse) => {
    if (isPulse) theme.beginTemporaryTheme("midnight");
    else theme.endTemporaryTheme();
  },
  { immediate: true, flush: "sync" }
);
useScrollGradientTheme();

function handleInvalidToken() {
  auth.clearAuth();
}

onMounted(() => {
  window.addEventListener("algowiki:auth-invalid", handleInvalidToken);
});

onBeforeUnmount(() => {
  stopPulseThemeWatch();
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
  color: rgba(103, 116, 142, 0.92);
  font-size: 12px;
  line-height: 1.5;
  text-decoration: none;
  transition: color 0.18s ease;
}

.site-footer__record:hover {
  color: rgba(74, 90, 122, 0.98);
  text-decoration: underline;
}

@media (max-width: 960px) {
  .site-footer {
    padding: 0 12px 14px;
  }
}
</style>
