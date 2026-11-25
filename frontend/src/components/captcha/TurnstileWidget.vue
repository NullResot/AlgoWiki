<template>
  <div class="turnstile-widget">
    <div v-if="loadingConfig" class="captcha-placeholder">
      正在加载安全验证组件...
    </div>
    <div v-else-if="!siteKey" class="captcha-placeholder captcha-placeholder--error">
      当前人机验证暂未配置完成，请联系管理员处理。
    </div>
    <div v-else ref="containerRef" class="turnstile-slot"></div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { getCaptchaConfig } from "../../composables/useCaptcha";

const emit = defineEmits(["verified", "expired", "error"]);

const runtimeConfig = ref(null);
const loadingConfig = ref(true);
const siteKey = computed(() => runtimeConfig.value?.turnstile_site_key || import.meta.env.VITE_TURNSTILE_SITE_KEY || "");
const containerRef = ref(null);
let widgetId = null;

function loadTurnstileScript() {
  if (window.turnstile) return Promise.resolve(window.turnstile);
  if (window.__algowikiTurnstilePromise) return window.__algowikiTurnstilePromise;
  window.__algowikiTurnstilePromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    script.async = true;
    script.defer = true;
    script.onload = () => resolve(window.turnstile);
    script.onerror = () => reject(new Error("Turnstile 脚本加载失败"));
    document.head.appendChild(script);
  });
  return window.__algowikiTurnstilePromise;
}

async function renderWidget() {
  if (loadingConfig.value) return;
  if (!siteKey.value) {
    emit("error", new Error("当前人机验证暂未配置完成"));
    return;
  }
  await nextTick();
  if (!containerRef.value) return;
  try {
    const turnstile = await loadTurnstileScript();
    if (!turnstile || !containerRef.value) throw new Error("安全验证组件加载失败");
    if (widgetId !== null) {
      turnstile.remove(widgetId);
      widgetId = null;
    }
    widgetId = turnstile.render(containerRef.value, {
      sitekey: siteKey.value,
      callback: (token) => emit("verified", token),
      "expired-callback": () => {
        emit("expired");
        if (widgetId !== null) turnstile.reset(widgetId);
      },
      "error-callback": () => emit("error", new Error("人机验证未通过，请重试")),
    });
  } catch (error) {
    emit("error", error);
  }
}

function reset() {
  if (siteKey.value && window.turnstile && widgetId !== null) {
    window.turnstile.reset(widgetId);
  } else {
    renderWidget();
  }
}

watch(siteKey, renderWidget, { immediate: true });

onMounted(async () => {
  try {
    runtimeConfig.value = await getCaptchaConfig({ force: true });
  } catch (error) {
    emit("error", error);
  } finally {
    loadingConfig.value = false;
    renderWidget();
  }
});

onBeforeUnmount(() => {
  if (window.turnstile && widgetId !== null) {
    window.turnstile.remove(widgetId);
    widgetId = null;
  }
});

defineExpose({ reset });
</script>

<style scoped>
.turnstile-widget {
  min-height: 70px;
}

.turnstile-slot {
  min-height: 65px;
}

.captcha-placeholder {
  border: 1px dashed color-mix(in srgb, var(--accent) 36%, transparent);
  border-radius: 12px;
  padding: 14px;
  color: var(--text-soft);
  background: color-mix(in srgb, var(--accent) 8%, var(--surface-soft));
  font-size: 13px;
  line-height: 1.6;
}

.captcha-placeholder--error {
  border-color: color-mix(in srgb, var(--danger) 42%, transparent);
  color: var(--danger);
  background: color-mix(in srgb, var(--danger) 12%, var(--surface-soft));
}
</style>
