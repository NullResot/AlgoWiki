<template>
  <section class="auth-wrap">
    <article class="card auth-card">
      <div class="auth-tabs">
        <button class="btn" :class="{ 'btn-accent': mode === 'login' }" @click="switchMode('login')">登录</button>
        <button class="btn" :class="{ 'btn-accent': mode === 'register' }" @click="switchMode('register')">注册</button>
        <button class="btn" :class="{ 'btn-accent': mode === 'reset' }" @click="switchMode('reset')">找回密码</button>
      </div>

      <div v-if="mode === 'login'" class="auth-form">
        <input class="input" v-model.trim="loginForm.username" placeholder="用户名 / 邮箱 / 手机号" autocomplete="username" />
        <div class="password-field">
          <input
            class="input password-input"
            v-model="loginForm.password"
            :type="passwordVisibility.login ? 'text' : 'password'"
            placeholder="密码"
            autocomplete="current-password"
            @keyup.enter="login"
          />
          <button
            class="password-toggle"
            type="button"
            :aria-label="passwordVisibility.login ? '隐藏密码' : '显示密码'"
            :title="passwordVisibility.login ? '隐藏密码' : '显示密码'"
            @click="togglePasswordVisibility('login')"
          >
            {{ passwordVisibility.login ? "隐藏" : "显示" }}
          </button>
        </div>
        <button class="btn btn-accent" :disabled="auth.loading" @click="login">登录</button>
      </div>

      <div v-else-if="mode === 'register'" class="auth-form">
        <input
          class="input"
          v-model.trim="registerForm.username"
          placeholder="用户名"
          autocomplete="username"
          @input="handleRegisterFieldInput"
        />
        <input
          class="input"
          v-model.trim="registerForm.email"
          placeholder="邮箱（可选，用于找回账号）"
          autocomplete="email"
          @input="handleRegisterFieldInput"
        />
        <input
          class="input"
          v-model.trim="registerForm.phone_number"
          placeholder="手机号"
          autocomplete="tel"
          inputmode="tel"
          @input="handleRegisterFieldInput"
        />
        <input
          class="input"
          v-model.trim="registerForm.school_name"
          autocomplete="organization"
          placeholder="学校"
          @input="handleRegisterFieldInput"
        />
        <input
          class="input"
          v-model.trim="registerForm.invitation_code"
          placeholder="邀请码（可选）"
          autocomplete="off"
          @input="handleRegisterFieldInput"
        />
        <p v-if="registerInviteHint" class="code-meta invite-hint">{{ registerInviteHint }}</p>
        <div class="password-field">
          <input
            class="input password-input"
            v-model="registerForm.password"
            :type="passwordVisibility.register ? 'text' : 'password'"
            placeholder="密码"
            autocomplete="new-password"
            @input="handleRegisterFieldInput"
          />
          <button
            class="password-toggle"
            type="button"
            :aria-label="passwordVisibility.register ? '隐藏密码' : '显示密码'"
            :title="passwordVisibility.register ? '隐藏密码' : '显示密码'"
            @click="togglePasswordVisibility('register')"
          >
            {{ passwordVisibility.register ? "隐藏" : "显示" }}
          </button>
        </div>
        <p class="field-help">
          密码至少 8 个字符，不能全是数字，不能与用户名、邮箱或学校过于相似，避免使用常见弱密码。
        </p>

        <div class="register-avatar-card">
          <div class="register-avatar-preview">
            <img :src="registerAvatarPreviewSrc" alt="注册头像预览" />
          </div>
          <div class="register-avatar-body">
            <strong>头像（可选）</strong>
            <p class="code-meta">支持 JPG、PNG、WebP，最大 2MB。未上传时使用默认头像。</p>
            <input
              ref="registerAvatarInputRef"
              class="visually-hidden-input"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              @change="onRegisterAvatarSelected"
            />
            <div class="register-avatar-actions">
              <button class="btn btn-mini" type="button" @click="pickRegisterAvatar">
                {{ registerAvatarFile ? "重新选择" : "上传头像" }}
              </button>
              <button
                v-if="registerAvatarFile"
                class="btn btn-mini"
                type="button"
                @click="clearRegisterAvatar"
              >
                移除
              </button>
            </div>
          </div>
        </div>

        <div v-if="registerTicket.token" class="code-card">
          <p class="code-title">验证码已发送</p>
          <p class="code-meta">
            验证码已发送至 {{ registerTicket.masked_phone }}。
            有效期 {{ Math.ceil(registerTicket.expires_in_seconds / 60) }} 分钟。
          </p>
          <input
            class="input"
            v-model.trim="registerForm.code"
            placeholder="短信验证码"
            inputmode="numeric"
            @keyup.enter="completeRegister"
          />
        </div>

        <p v-if="registerCompletionHint" class="code-meta action-hint">{{ registerCompletionHint }}</p>
        <div class="auth-actions">
          <button class="btn" :disabled="auth.loading" @click="sendRegisterCode">
            {{ auth.loading ? "发送中..." : registerTicket.token ? "重新发送验证码" : "发送验证码" }}
          </button>
          <button
            class="btn btn-accent"
            :disabled="auth.loading"
            @click="completeRegister"
          >
            {{ auth.loading ? "处理中..." : "完成注册" }}
          </button>
        </div>
      </div>

      <div v-else class="auth-form">
        <input
          class="input"
          v-model.trim="resetForm.email"
          placeholder="注册邮箱"
          autocomplete="email"
          @input="clearResetSession"
        />

        <div v-if="resetTicket.token" class="code-card">
          <p class="code-title">重置验证码已发送</p>
          <p class="code-meta">
            若该邮箱已注册，验证码已发送至 {{ resetTicket.masked_email }}。
          </p>
          <input
            class="input"
            v-model.trim="resetForm.code"
            placeholder="邮箱验证码"
            inputmode="numeric"
          />
          <div class="password-field">
            <input
              class="input password-input"
              v-model="resetForm.new_password"
              :type="passwordVisibility.resetNew ? 'text' : 'password'"
              placeholder="新密码"
              autocomplete="new-password"
            />
            <button
              class="password-toggle"
              type="button"
              :aria-label="passwordVisibility.resetNew ? '隐藏密码' : '显示密码'"
              :title="passwordVisibility.resetNew ? '隐藏密码' : '显示密码'"
              @click="togglePasswordVisibility('resetNew')"
            >
              {{ passwordVisibility.resetNew ? "隐藏" : "显示" }}
            </button>
          </div>
          <div class="password-field">
            <input
              class="input password-input"
              v-model="resetForm.confirm_password"
              :type="passwordVisibility.resetConfirm ? 'text' : 'password'"
              placeholder="确认新密码"
              autocomplete="new-password"
              @keyup.enter="completeResetPassword"
            />
            <button
              class="password-toggle"
              type="button"
              :aria-label="passwordVisibility.resetConfirm ? '隐藏密码' : '显示密码'"
              :title="passwordVisibility.resetConfirm ? '隐藏密码' : '显示密码'"
              @click="togglePasswordVisibility('resetConfirm')"
            >
              {{ passwordVisibility.resetConfirm ? "隐藏" : "显示" }}
            </button>
          </div>
        </div>

        <div class="auth-actions">
          <button class="btn" :disabled="auth.loading" @click="sendResetCode">
            {{ auth.loading ? "发送中..." : resetTicket.token ? "重新发送验证码" : "发送找回验证码" }}
          </button>
          <button
            class="btn btn-accent"
            :disabled="auth.loading || !resetTicket.token"
            @click="completeResetPassword"
          >
            {{ auth.loading ? "处理中..." : "重置密码" }}
          </button>
        </div>
      </div>

      <p v-if="infoMsg" class="meta info-text">{{ infoMsg }}</p>
      <p v-if="errorMsg" class="meta error-text">{{ errorMsg }}</p>
    </article>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import api from "../services/api";
import { useAuthStore } from "../stores/auth";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();

const mode = ref("login");
const errorMsg = ref("");
const infoMsg = ref("");
const registerTicket = reactive({
  token: "",
  masked_phone: "",
  expires_in_seconds: 0,
});
const DEFAULT_AVATAR_URL = "/wiki-assets/default-avatar.svg";
const registerAvatarInputRef = ref(null);
const registerAvatarFile = ref(null);
const registerAvatarPreviewUrl = ref("");
const registerAvatarMaxBytes = 2 * 1024 * 1024;
const allowedRegisterAvatarMimeTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
const registerAvatarPreviewSrc = computed(() => registerAvatarPreviewUrl.value || DEFAULT_AVATAR_URL);
const resetTicket = reactive({
  token: "",
  masked_email: "",
  expires_in_seconds: 0,
});
const passwordVisibility = reactive({
  login: false,
  register: false,
  resetNew: false,
  resetConfirm: false,
});

const loginForm = reactive({
  username: "",
  password: "",
});

const registerForm = reactive({
  username: "",
  email: "",
  phone_number: "",
  school_name: "",
  invitation_code: "",
  password: "",
  code: "",
});

const registerInviteHint = computed(() => {
  const code = String(registerForm.invitation_code || "").trim();
  if (!code) return "";
  return `将使用邀请码 ${code.toUpperCase()} 完成注册。手机号验证通过后，邀请人会获得社区贡献。`;
});

const registerCompletionHint = computed(() => {
  if (!registerTicket.token) return "完成注册前请先发送短信验证码。";
  if (!String(registerForm.code || "").trim()) return "请填写收到的短信验证码。";
  return "";
});

const resetForm = reactive({
  email: "",
  code: "",
  new_password: "",
  confirm_password: "",
});

function clearMessages() {
  errorMsg.value = "";
  infoMsg.value = "";
}

function resetPasswordVisibility() {
  passwordVisibility.login = false;
  passwordVisibility.register = false;
  passwordVisibility.resetNew = false;
  passwordVisibility.resetConfirm = false;
}

function togglePasswordVisibility(key) {
  if (!(key in passwordVisibility)) return;
  passwordVisibility[key] = !passwordVisibility[key];
}

function clearRegisterSession() {
  registerTicket.token = "";
  registerTicket.masked_phone = "";
  registerTicket.expires_in_seconds = 0;
  registerForm.code = "";
}

function handleRegisterFieldInput() {
  clearMessages();
  clearRegisterSession();
}

function revokeRegisterAvatarPreview() {
  if (registerAvatarPreviewUrl.value) {
    URL.revokeObjectURL(registerAvatarPreviewUrl.value);
  }
  registerAvatarPreviewUrl.value = "";
}

function pickRegisterAvatar() {
  registerAvatarInputRef.value?.click();
}

function clearRegisterAvatar() {
  registerAvatarFile.value = null;
  revokeRegisterAvatarPreview();
  if (registerAvatarInputRef.value) {
    registerAvatarInputRef.value.value = "";
  }
}

function onRegisterAvatarSelected(event) {
  const file = event.target.files?.[0] || null;
  if (!file) return;
  const fileName = String(file.name || "").toLowerCase();
  const hasAllowedExtension = [".jpg", ".jpeg", ".png", ".webp"].some((ext) => fileName.endsWith(ext));
  if (!allowedRegisterAvatarMimeTypes.has(file.type) && !hasAllowedExtension) {
    errorMsg.value = "仅支持 JPG、PNG、WebP 头像。";
    clearRegisterAvatar();
    return;
  }
  if (file.size > registerAvatarMaxBytes) {
    errorMsg.value = "头像图片不能超过 2MB。";
    clearRegisterAvatar();
    return;
  }
  revokeRegisterAvatarPreview();
  registerAvatarFile.value = file;
  registerAvatarPreviewUrl.value = URL.createObjectURL(file);
}

function clearResetSession() {
  resetTicket.token = "";
  resetTicket.masked_email = "";
  resetTicket.expires_in_seconds = 0;
  resetForm.code = "";
}

function getErrorText(error, fallback) {
  const payload = error?.response?.data;
  if (!payload) return fallback;
  if (typeof payload === "string") return translateAuthError(payload);
  if (typeof payload.detail === "string") return translateAuthError(payload.detail);
  if (Array.isArray(payload)) return payload.map(translateAuthError).join("; ");
  if (typeof payload === "object") {
    const items = [];
    for (const [key, value] of Object.entries(payload)) {
      if (key === "request_id" || key === "retry_after_seconds") continue;
      const label = authFieldLabel(key);
      if (Array.isArray(value)) {
        items.push(`${label}: ${value.map(translateAuthError).join("; ")}`);
      } else if (typeof value === "string") {
        items.push(`${label}: ${translateAuthError(value)}`);
      }
    }
    if (items.length) return items.join("; ");
  }
  return fallback;
}

function authFieldLabel(key) {
  const labels = {
    username: "用户名",
    email: "邮箱",
    phone_number: "手机号",
    phone_country_code: "手机号",
    password: "密码",
    new_password: "新密码",
    confirm_password: "确认密码",
    school_name: "学校",
    code: "验证码",
    verify_code: "验证码",
    ticket_token: "验证码会话",
    non_field_errors: "提示",
  };
  return labels[key] || key;
}

function translateAuthError(message) {
  const text = String(message || "").trim();
  const exact = {
    "Username is required.": "请填写用户名。",
    "This username is already in use.": "用户名已被使用，请换一个。",
    "Email is required.": "请填写邮箱。",
    "This email is already in use.": "邮箱已被使用，请换一个或直接留空。",
    "School is required.": "请填写学校。",
    "This phone number is already in use.": "手机号已绑定其他账号。",
    "Only mainland China phone numbers are supported.": "目前仅支持中国大陆手机号。",
    "Please enter a valid mainland China mobile number.": "请输入有效的中国大陆手机号。",
    "Please request a new verification code.": "请先发送新的验证码。",
    "Verification session is invalid.": "验证码会话无效，请重新发送验证码。",
    "Verification code expired. Please request a new one.": "验证码已过期，请重新发送。",
    "Please enter the verification code.": "请填写短信验证码。",
    "Verification code is incorrect or expired.": "验证码错误或已过期，请核对后重试。",
    "Too many incorrect attempts. Please request a new verification code.": "验证码错误次数过多，请重新发送验证码。",
  };
  if (exact[text]) return exact[text];
  if (text.includes("too short") && text.includes("at least 8")) {
    return "密码至少需要 8 个字符。";
  }
  if (text.includes("entirely numeric")) {
    return "密码不能全是数字。";
  }
  if (text.includes("too common")) {
    return "密码过于常见，请换一个更安全的密码。";
  }
  if (text.includes("too similar")) {
    return "密码不能与用户名、邮箱或学校过于相似。";
  }
  return text;
}

function normalizeMainlandPhone(value) {
  let text = String(value || "").replace(/\D/g, "");
  if (text.startsWith("86") && text.length === 13) {
    text = text.slice(2);
  }
  return text;
}

function getRegisterFormError() {
  const username = String(registerForm.username || "").trim();
  const email = String(registerForm.email || "").trim();
  const phone = normalizeMainlandPhone(registerForm.phone_number);
  const school = String(registerForm.school_name || "").trim();
  const password = String(registerForm.password || "");

  if (!username) return "请填写用户名。";
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return "邮箱格式不正确。邮箱是可选项，也可以先留空。";
  }
  if (!phone) return "请填写手机号。";
  if (!/^1[3-9]\d{9}$/.test(phone)) return "请输入有效的中国大陆手机号。";
  if (!school) return "请填写学校。";
  if (!password) return "请填写密码。";
  if (password.length < 8) return "密码至少需要 8 个字符。";
  if (/^\d+$/.test(password)) return "密码不能全是数字。";
  const lowerPassword = password.toLowerCase();
  const comparableValues = [username, email.split("@")[0], school]
    .map((item) => String(item || "").trim().toLowerCase())
    .filter((item) => item.length >= 3);
  if (comparableValues.some((item) => lowerPassword.includes(item) || item.includes(lowerPassword))) {
    return "密码不能与用户名、邮箱或学校过于相似。";
  }
  return "";
}

function switchMode(nextMode) {
  mode.value = nextMode;
  clearMessages();
  clearRegisterSession();
  clearResetSession();
  if (nextMode !== "register") {
    clearRegisterAvatar();
  }
  resetPasswordVisibility();
}

function applyInviteFromRoute() {
  const invite = String(route.query.invite || route.query.invitation || "").trim();
  if (invite) {
    registerForm.invitation_code = invite.toUpperCase();
    mode.value = "register";
  }
  if (String(route.query.mode || "").trim() === "register") {
    mode.value = "register";
  }
}

async function login() {
  clearMessages();
  try {
    await auth.login(loginForm);
    await router.push({ name: "profile" });
  } catch (error) {
    errorMsg.value = getErrorText(error, "登录失败");
  }
}

async function sendRegisterCode() {
  clearMessages();
  const validationError = getRegisterFormError();
  if (validationError) {
    errorMsg.value = validationError;
    return;
  }

  try {
    const data = await auth.requestRegisterPhoneCode({
      username: registerForm.username,
      email: registerForm.email,
      phone_country_code: "86",
      phone_number: registerForm.phone_number,
      school_name: registerForm.school_name,
      invitation_code: registerForm.invitation_code,
      password: registerForm.password,
    });
    registerTicket.token = data.ticket_token || "";
    registerTicket.masked_phone = data.masked_phone || "";
    registerTicket.expires_in_seconds = Number(data.expires_in_seconds || 0);
    registerForm.code = "";
    infoMsg.value = `验证码已发送至 ${registerTicket.masked_phone}。`;
  } catch (error) {
    errorMsg.value = getErrorText(error, "注册验证码发送失败");
  }
}

async function completeRegister() {
  clearMessages();
  const validationError = getRegisterFormError();
  if (validationError) {
    errorMsg.value = `请先修正注册信息：${validationError}`;
    return;
  }
  if (!registerTicket.token) {
    errorMsg.value = "请先点击“发送验证码”，完成短信验证后再注册。";
    return;
  }
  if (!String(registerForm.code || "").trim()) {
    errorMsg.value = "请填写收到的短信验证码。";
    return;
  }

  try {
    let payload = {
      ticket_token: registerTicket.token,
      code: registerForm.code,
    };
    if (registerAvatarFile.value) {
      const formData = new FormData();
      Object.entries(payload).forEach(([key, value]) => formData.append(key, value));
      formData.append("avatar_image", registerAvatarFile.value);
      payload = formData;
    }
    await auth.register(payload);
    clearRegisterAvatar();
    await router.push({ name: "profile" });
  } catch (error) {
    errorMsg.value = getErrorText(error, "注册失败");
  }
}

async function sendResetCode() {
  clearMessages();
  try {
    const data = await auth.requestPasswordResetCode({
      email: resetForm.email,
    });
    resetTicket.token = data.ticket_token || "";
    resetTicket.masked_email = data.masked_email || "";
    resetTicket.expires_in_seconds = Number(data.expires_in_seconds || 0);
    resetForm.code = "";
    infoMsg.value = data.detail || "若该邮箱已注册，验证码已发送。";
  } catch (error) {
    errorMsg.value = getErrorText(error, "找回密码验证码发送失败");
  }
}

async function completeResetPassword() {
  clearMessages();
  if (!resetTicket.token) {
    errorMsg.value = "请先发送找回验证码。";
    return;
  }

  try {
    await auth.resetPassword({
      ticket_token: resetTicket.token,
      code: resetForm.code,
      new_password: resetForm.new_password,
      confirm_password: resetForm.confirm_password,
    });
    await router.push({ name: "profile" });
  } catch (error) {
    errorMsg.value = getErrorText(error, "密码重置失败");
  }
}

watch(
  () => [route.query.invite, route.query.invitation, route.query.mode],
  () => applyInviteFromRoute(),
);

onMounted(() => {
  applyInviteFromRoute();
});

</script>

<style scoped>
.auth-wrap {
  display: grid;
  place-items: center;
  min-height: calc(100vh - 180px);
}

.auth-card {
  width: min(560px, 100%);
  padding: 20px;
}

.auth-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.auth-form {
  display: grid;
  gap: 10px;
}

.password-field {
  position: relative;
}

.password-input {
  padding-right: 64px;
}

.password-toggle {
  position: absolute;
  top: 50%;
  right: 14px;
  transform: translateY(-50%);
  border: 0;
  background: transparent;
  padding: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted, #6b7280);
  cursor: pointer;
}

.password-toggle:hover {
  color: #4f46e5;
}

.auth-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.field-help,
.action-hint {
  margin-top: -4px;
  line-height: 1.6;
}

.register-avatar-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px;
  border: 1px solid var(--line-color, #d7deea);
  border-radius: 16px;
  background: rgba(248, 250, 252, 0.86);
}

.register-avatar-preview {
  flex: 0 0 auto;
  width: 64px;
  height: 64px;
  border-radius: 999px;
  overflow: hidden;
  border: 1px solid rgba(99, 102, 241, 0.18);
  background: #eef2ff;
}

.register-avatar-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.register-avatar-body {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.register-avatar-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.visually-hidden-input {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}

.code-card {
  display: grid;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--line-color, #d7deea);
  border-radius: 16px;
  background: rgba(244, 247, 252, 0.8);
}

.code-title {
  font-size: 13px;
  font-weight: 700;
}

.code-meta {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted, #6b7280);
}

.info-text {
  color: #2563eb;
}

.error-text {
  color: #dc2626;
}
</style>
