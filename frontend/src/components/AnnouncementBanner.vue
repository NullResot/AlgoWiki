<template>
  <Transition name="aw-collapse">
    <div v-if="visible && announcement" class="announcement-banner" role="region" aria-label="站内重要公告">
      <button class="banner-main" type="button" @click="openAnnouncement">
        <span class="banner-level" :class="`banner-level--${announcement.level || 'normal'}`">
          {{ levelLabel }}
        </span>
        <strong>{{ announcement.title }}</strong>
        <span v-if="announcement.summary" class="banner-summary">{{ announcement.summary }}</span>
      </button>
      <button class="banner-close" type="button" aria-label="关闭公告横幅" @click="dismissBanner">×</button>
    </div>
  </Transition>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import api from "../services/api";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const auth = useAuthStore();
const router = useRouter();
const ui = useUiStore();
const announcement = ref(null);
const dismissedKey = ref("");

const visible = computed(() => {
  if (!announcement.value?.id) return false;
  return dismissedKey.value !== storageKey(announcement.value.id);
});

const levelLabel = computed(() => {
  const labels = {
    emergency: "紧急",
    important: "重要",
    normal: "公告",
    low: "公告",
  };
  return labels[announcement.value?.level] || "公告";
});

function storageKey(id) {
  const mode = auth.isAuthenticated ? `user_${auth.user?.id || "unknown"}` : "anon";
  return `announcement_banner_${mode}_${id}`;
}

async function loadBanner() {
  try {
    const { data } = await api.get("/announcements/banner/");
    announcement.value = data?.id ? data : null;
    dismissedKey.value = "";
    if (announcement.value?.id && localStorage.getItem(storageKey(announcement.value.id))) {
      dismissedKey.value = storageKey(announcement.value.id);
    }
  } catch {
    announcement.value = null;
  }
}

function restoreBanner(key) {
  try {
    localStorage.removeItem(key);
  } catch {
    // Ignore storage failures.
  }
  if (dismissedKey.value === key) {
    dismissedKey.value = "";
  }
}

function dismissBanner() {
  if (!announcement.value?.id) return;
  const key = storageKey(announcement.value.id);
  try {
    localStorage.setItem(key, "1");
  } catch {
    // Ignore storage failures.
  }
  dismissedKey.value = key;
  ui.info("已收起顶部公告横幅", "提示", 3200, {
    action: {
      label: "撤销",
      onClick: () => restoreBanner(key),
    },
  });
}

async function openAnnouncement() {
  if (!announcement.value?.id) return;
  await router.push({
    name: "announcements",
    query: { announcement: String(announcement.value.id) },
  });
}

onMounted(() => {
  loadBanner();
});

watch(
  () => [auth.isAuthenticated, auth.user?.id],
  () => {
    loadBanner();
  }
);
</script>

<style scoped>
.announcement-banner {
  display: flex;
  align-items: stretch;
  justify-content: center;
  gap: 8px;
  padding: 8px 16px;
  border-bottom: 1px solid var(--hairline);
  background: color-mix(in srgb, var(--accent) 8%, var(--surface-strong));
}

.banner-main {
  display: flex;
  flex: 1 1 auto;
  max-width: 1180px;
  min-width: 0;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: 0;
  border-radius: 999px;
  padding: 2px 6px;
  background: transparent;
  color: var(--text);
  font: inherit;
  cursor: pointer;
  transition: opacity var(--dur-fast, 150ms) var(--ease-standard, ease);
}

.banner-main:hover strong {
  color: var(--accent);
}

.banner-main strong {
  color: var(--text-strong);
  white-space: nowrap;
  transition: color var(--dur-fast, 150ms) var(--ease-standard, ease);
}

.banner-summary {
  min-width: 0;
  overflow: hidden;
  color: var(--muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.banner-level {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 9px;
  border-radius: 999px;
  background: var(--pill-bg);
  color: var(--pill-text);
  font-size: 12px;
  font-weight: 800;
}

.banner-level--emergency {
  background: color-mix(in srgb, var(--danger) 16%, var(--surface-strong));
  color: var(--danger);
}

.banner-level--important {
  background: var(--surface-warning);
  color: var(--surface-warning-text);
}

.banner-close {
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  border: 1px solid var(--hairline);
  border-radius: 999px;
  background: var(--surface-strong);
  color: var(--text-soft);
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition:
    background-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    color var(--dur-fast, 150ms) var(--ease-standard, ease),
    transform var(--dur-press, 90ms) var(--ease-out, ease);
}

.banner-close:hover {
  background: var(--surface-soft);
  color: var(--text-strong);
}

.banner-close:active {
  transform: scale(0.93);
}

@media (max-width: 760px) {
  .announcement-banner {
    padding: 8px 10px;
  }

  .banner-main {
    justify-content: flex-start;
  }

  .banner-summary {
    display: none;
  }
}
</style>
