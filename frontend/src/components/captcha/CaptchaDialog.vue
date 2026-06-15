<template>
  <Teleport to="body">
    <div v-if="visible" class="captcha-backdrop" @click.self="cancel">
      <section class="captcha-dialog" role="dialog" aria-modal="true" aria-label="人机验证">
        <header class="captcha-head">
          <div>
            <p class="captcha-kicker">Security Check</p>
            <h2>请先完成验证</h2>
            <p>{{ sceneLabel }} 需要完成人机验证，验证通过后才会继续操作。</p>
          </div>
          <button type="button" class="captcha-close" @click="cancel">×</button>
        </header>

        <div class="captcha-steps" aria-label="验证码步骤">
          <span :class="['captcha-step', step === 'turnstile' ? 'active' : '', turnstileToken ? 'done' : '']">1</span>
          <span class="captcha-line"></span>
          <span :class="['captcha-step', step === 'secondary' ? 'active' : '', secondaryResult ? 'done' : '']">2</span>
        </div>

        <div class="captcha-body">
          <TurnstileWidget
            v-if="step === 'turnstile'"
            ref="turnstileRef"
            @verified="handleTurnstileVerified"
            @expired="handleTurnstileExpired"
            @error="handleError"
          />
          <SecondaryCaptchaWidget
            v-else
            @verified="handleSecondaryVerified"
            @error="handleError"
          />
        </div>

        <footer class="captcha-foot">
          <span class="captcha-status">{{ statusText }}</span>
          <button type="button" class="captcha-secondary" @click="cancel">取消</button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { getCaptchaConfig, rejectCaptchaProof, resolveCaptchaProof } from "../../composables/useCaptcha";
import SecondaryCaptchaWidget from "./SecondaryCaptchaWidget.vue";
import TurnstileWidget from "./TurnstileWidget.vue";

const visible = ref(false);
const scene = ref("");
const step = ref("turnstile");
const statusText = ref("正在加载验证...");
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
  school_survey_submit: "提交学校收集表",
  upload_image: "上传图片",
  real_name_start: "发起实名认证",
  account_cancel: "注销账号",
  assistant_chat: "AI 助手对话",
};

const sceneLabel = computed(() => sceneNames[scene.value] || "当前操作");

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
  visible.value = false;
  rejectCaptchaProof(new Error("验证码已取消"));
}

function handleTurnstileVerified(token) {
  turnstileToken.value = token;
  if (!captchaConfig.value?.secondary_enabled) {
    resolveVerifiedProof(null);
    return;
  }
  step.value = "secondary";
  statusText.value = "请完成二次验证";
}

function handleTurnstileExpired() {
  turnstileToken.value = "";
  statusText.value = "验证码已过期，请重新验证";
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
  statusText.value = "验证完成，正在继续...";
  visible.value = false;
  resolveCaptchaProof(payload);
}

function handleError(error) {
  statusText.value = error?.message || "验证码验证失败，请重新验证";
}

onMounted(() => {
  window.addEventListener("algowiki:captcha-open", open);
});

onBeforeUnmount(() => {
  window.removeEventListener("algowiki:captcha-open", open);
});
</script>

<style scoped>
.captcha-backdrop {
  position: fixed;
  inset: 0;
  z-index: 120;
  display: grid;
  place-items: center;
  padding: 18px;
  background: rgba(15, 23, 42, 0.38);
  backdrop-filter: blur(10px);
}

.captcha-dialog {
  width: min(440px, calc(100vw - 28px));
  overflow: hidden;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.22);
}

.captcha-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 20px 12px;
}

.captcha-head h2 {
  margin: 0;
  color: #0f172a;
  font-size: 20px;
}

.captcha-head p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.captcha-kicker {
  margin: 0 0 4px !important;
  color: #6366f1 !important;
  font-size: 11px !important;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.captcha-close {
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 10px;
  color: #64748b;
  background: #f8fafc;
  cursor: pointer;
  font-size: 20px;
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
  color: #64748b;
  background: #e2e8f0;
  font-size: 12px;
  font-weight: 800;
}

.captcha-step.active {
  color: #ffffff;
  background: #6366f1;
}

.captcha-step.done {
  color: #ffffff;
  background: #16a34a;
}

.captcha-line {
  flex: 1;
  height: 2px;
  background: #e2e8f0;
}

.captcha-body {
  padding: 12px 20px 18px;
}

.captcha-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-top: 1px solid #f1f5f9;
  padding: 14px 20px;
}

.captcha-status {
  color: #64748b;
  font-size: 13px;
}

.captcha-secondary {
  min-height: 34px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 0 14px;
  color: #334155;
  background: #ffffff;
  cursor: pointer;
  font-weight: 700;
}
</style>
