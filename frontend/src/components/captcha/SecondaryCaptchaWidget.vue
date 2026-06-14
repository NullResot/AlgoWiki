<template>
  <div class="secondary-captcha">
    <button type="button" class="secondary-btn" :disabled="verifying" @click="startVerification">
      {{ buttonText }}
    </button>
    <p class="secondary-note">
      {{ provider === "geetest" ? "二次验证用于拦截自动化刷接口。" : "当前二次验证码服务未启用。" }}
    </p>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { getCaptchaConfig } from "../../composables/useCaptcha";

const emit = defineEmits(["verified", "error"]);

const runtimeConfig = ref(null);
const provider = computed(() => runtimeConfig.value?.secondary_provider || import.meta.env.VITE_SECONDARY_CAPTCHA_PROVIDER || "geetest");
const captchaId = computed(() => runtimeConfig.value?.geetest_captcha_id || import.meta.env.VITE_GEETEST_CAPTCHA_ID || "");
const hasRealGeeTestConfig = computed(() => provider.value === "geetest" && Boolean(captchaId.value));
const verifying = ref(false);
const verified = ref(false);

const buttonText = computed(() => {
  if (verified.value) return "二次验证已完成";
  if (verifying.value) return "请完成二次验证...";
  return "开始二次验证";
});

function loadGeeTestScript() {
  if (window.initGeetest4) return Promise.resolve(window.initGeetest4);
  if (window.__algowikiGeeTestPromise) return window.__algowikiGeeTestPromise;
  window.__algowikiGeeTestPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://static.geetest.com/v4/gt4.js";
    script.async = true;
    script.onload = () => resolve(window.initGeetest4);
    script.onerror = () => reject(new Error("二次验证码脚本加载失败"));
    document.head.appendChild(script);
  });
  return window.__algowikiGeeTestPromise;
}

onMounted(async () => {
  runtimeConfig.value = await getCaptchaConfig();
});

async function startVerification() {
  if (verified.value) return;
  verifying.value = true;
  try {
    if (!hasRealGeeTestConfig.value) {
      const payload = {
        provider: provider.value || "custom",
        payload: { dev_bypass: true, generated_at: Date.now() },
      };
      verified.value = true;
      emit("verified", payload);
      return;
    }
    const initGeetest4 = await loadGeeTestScript();
    if (!initGeetest4) throw new Error("二次验证码不可用");
    initGeetest4(
      {
        captchaId: captchaId.value,
        product: "bind",
      },
      (captchaObj) => {
        captchaObj.onReady(() => {
          captchaObj.showCaptcha();
        });
        captchaObj.onSuccess(() => {
          const result = captchaObj.getValidate();
          verified.value = true;
          emit("verified", {
            provider: "geetest",
            payload: result || {},
          });
        });
        captchaObj.onError(() => {
          emit("error", new Error("二次验证码验证失败"));
        });
      }
    );
  } catch (error) {
    emit("error", error);
  } finally {
    verifying.value = false;
  }
}
</script>

<style scoped>
.secondary-captcha {
  display: grid;
  gap: 8px;
}

.secondary-btn {
  min-height: 42px;
  border: 0;
  border-radius: 12px;
  padding: 0 16px;
  color: #ffffff;
  background: #111827;
  font-weight: 700;
  cursor: pointer;
}

.secondary-btn:disabled {
  cursor: wait;
  opacity: 0.7;
}

.secondary-note {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}
</style>
