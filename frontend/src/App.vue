<template>
  <div class="app-shell" :class="`app-shell--${theme.currentTheme}`">
    <TopNav />
    <ToastStack />
    <ChatAssistantLauncher />
    <main class="page-shell" :class="{ 'page-shell--flush': isHomeLayout }">
      <RouterView />
    </main>
    <footer class="site-footer">
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
import { computed, onBeforeUnmount, onMounted } from "vue";
import { RouterView } from "vue-router";
import { useRoute } from "vue-router";
import AnnouncementModal from "./components/AnnouncementModal.vue";
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
const { showAnnouncement, activeAnnouncement, dismissAnnouncement } = useAnnouncementPopup(auth);

theme.init();
useScrollGradientTheme();

function handleInvalidToken() {
  auth.clearAuth();
}

onMounted(() => {
  window.addEventListener("algowiki:auth-invalid", handleInvalidToken);
});

onBeforeUnmount(() => {
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
