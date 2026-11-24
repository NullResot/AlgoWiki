<template>
  <Teleport to="body">
    <Transition name="aw-modal">
      <div v-if="visible" class="captcha-backdrop" @click.self="cancel">
        <section class="captcha-dialog aw-modal-panel" role="dialog" aria-modal="true" aria-label="安全验证">
          <header class="captcha-head">
            <div>
              <p class="captcha-kicker">安全验证</p>
              <h2>请先完成人机验证</h2>
              <p>{{ sceneLabel }}需要完成人机验证，验证通过后将自动继续。</p>
            </div>
            <button type="button" class="captcha-close" aria-label="关闭验证" @click="cancel">×</button>
          </header>

          <div v-if="showTwoStepIndicator" class="captcha-steps" aria-label="验证步骤">
            <span :class="['captcha-step', step === 'turnstile' ? 'active' : '', turnstileToken ? 'done' : '']">1</span>
            <span class="captcha-line"></span>
            <span :class="['captcha-step', step === 'secondary' ? 'active' : '', secondaryResult ? 'done' : '']">2</span>
          </div>

          <div class="captcha-body">
            <Transition name="aw-swap" mode="out-in">
              <TurnstileWidget
                v-if="step === 'turnstile'"
                key="turnstile"
                ref="turnstileRef"
                @verified="handleTurnstileVerified"
                @expired="handleTurnstileExpired"
                @error="handleError"
              />
              <SecondaryCaptchaWidget
                v-else
                key="secondary"
                @verified="handleSecondaryVerified"
                @error="handleError"
              />
            </Transition>
          </div>

          <footer class="captcha-foot">
            <span class="captcha-status">{{ statusText }}</span>
            <button type="button" class="btn btn-mini" @click="cancel">取消</button>
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { getCaptchaConfig, rejectCaptchaProof, resolveCaptchaProof } from "../../composables/useCaptcha";
import { useOverlayA11y } from "../../composables/useOverlayA11y";
import SecondaryCaptchaWidget from "./SecondaryCaptchaWidget.vue";
import TurnstileWidget from "./TurnstileWidget.vue";

const visible = ref(false);
const scene = ref("");
const step = ref("turnstile");
const statusText = ref("正在准备验证...");
const turnstileToken = ref("");
const secondaryResult = ref(null);
const turnstileRef = ref(null);
const captchaConfig = ref(null);

const sceneNames = {
  send_email_code: "发送邮箱验证码",
  send_sms_code: "发送短信验证码",
  password_reset: "找回密码",
  bind_email: "绑定邮箱",
  bind_phone: "绑定手机号",
  change_password_code: "修改密码",
  school_apply: "学校用户认证申请",
  school_survey_submit: "提交高校调研表",
  upload_image: "上传图片",
  real_name_start: "发起实名认证",
  account_cancel: "注销账号",
  assistant_chat: "AI 助手对话",
};

const sceneLabel = computed(() => sceneNames[scene.value] || "当前操作");
const showTwoStepIndicator = computed(() => Boolean(captchaConfig.value?.secondary_enabled));

function open(event) {
  scene.value = event?.detail?.scene || "";
  step.value = "turnstile";
  statusText.value = "正在进行人机验证...";
  turnstileToken.value = "";
  secondaryResult.value = null;
  visible.value = true;
  getCaptchaConfig()
    .then((config) => {
      captchaConfig.value = config;
    })
    .catch(() => {});
}

function cancel() {
  if (!visible.value) return;
  visible.value = false;
  rejectCaptchaProof(new Error("验证码已取消"));
}

useOverlayA11y(visible, cancel);

function handleTurnstileVerified(token) {
  turnstileToken.value = token;
  if (!captchaConfig.value?.secondary_enabled) {
    resolveVerifiedProof(null);
    return;
  }
  step.value = "secondary";
  statusText.value = "请完成第二步安全验证";
}

function handleTurnstileExpired() {
  turnstileToken.value = "";
  statusText.value = "验证已过期，请重新验证";
  turnstileRef.value?.reset?.();
}

function handleSecondaryVerified(result) {
  secondaryResult.value = result;
  resolveVerifiedProof(result);
}

function resolveVerifiedProof(result) {
  const payload = {
    scene: scene.value,
    turnstile_token: turnstileToken.value,
    secondary_provider: result?.provider || captchaConfig.value?.secondary_provider || "",
    secondary_payload: result?.payload || {},
  };
  statusText.value = "验证通过，正在继续...";
  visible.value = false;
  resolveCaptchaProof(payload);
}

function handleError(error) {
  statusText.value = error?.message || "人机验证未通过，请重试";
}

onMounted(() => {
  window.addEventListener("algowiki:captcha-open", open);
});

onBeforeUnmount(() => {
  window.removeEventListener("algowiki:captcha-open", open);
  if (visible.value) {
    visible.value = false;
    rejectCaptchaProof(new Error("验证码已取消"));
  }
});
</script>

<style scoped>
.captcha-backdrop {
  position: fixed;
  inset: 0;
  z-index: var(--z-captcha, 5000);
  display: grid;
  place-items: center;
  padding: 18px;
  background: color-mix(in srgb, #020617 48%, transparent);
}

.captcha-dialog {
  width: min(440px, calc(100vw - 28px));
  overflow: hidden;
  border: 1px solid var(--panel-border-strong);
  border-radius: var(--radius-md);
  background: var(--surface-overlay);
  box-shadow: var(--shadow-md);
}

.captcha-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 20px 12px;
}

.captcha-head h2 {
  margin: 0;
  color: var(--text-strong);
  font-size: 20px;
}

.captcha-head p {
  margin: 6px 0 0;
  color: var(--text-soft);
  font-size: 13px;
  line-height: 1.6;
}

.captcha-kicker {
  margin: 0 0 4px !important;
  color: var(--accent) !important;
  font-size: 11px !important;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.captcha-close {
  width: 32px;
  height: 32px;
  flex: 0 0 auto;
  border: 1px solid var(--hairline);
  border-radius: 999px;
  color: var(--text-soft);
  background: var(--surface-soft);
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  transition:
    background-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    color var(--dur-fast, 150ms) var(--ease-standard, ease),
    transform var(--dur-press, 90ms) var(--ease-out, ease);
}

.captcha-close:hover {
  color: var(--text-strong);
  background: var(--surface-strong);
}

.captcha-close:active {
  transform: scale(0.94);
}

.captcha-steps {
  display: flex;
  align-items: center;
  padding: 8px 20px 10px;
}

.captcha-step {
  display: inline-grid;
  width: 26px;
  height: 26px;
  place-items: center;
  border-radius: 999px;
  color: var(--text-soft);
  background: var(--surface-chip);
  font-size: 12px;
  font-weight: 800;
  transition:
    background-color var(--dur-base, 220ms) var(--ease-out, ease),
    color var(--dur-base, 220ms) var(--ease-out, ease);
}

.captcha-step.active {
  color: var(--accent-contrast);
  background: var(--accent);
}

.captcha-step.done {
  color: #ffffff;
  background: var(--success);
}

.captcha-line {
  flex: 1;
  height: 2px;
  background: var(--hairline-strong);
}

.captcha-body {
  padding: 12px 20px 18px;
}

.captcha-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-top: 1px solid var(--hairline);
  padding: 14px 20px;
}

.captcha-status {
  color: var(--text-soft);
  font-size: 13px;
}
</style>
