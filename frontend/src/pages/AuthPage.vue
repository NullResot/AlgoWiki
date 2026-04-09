<template>
  <section class="auth-wrap">
    <article class="card auth-card">
      <div class="auth-tabs">
        <button class="btn" :class="{ 'btn-accent': mode === 'login' }" @click="switchMode('login')">登录</button>
        <button class="btn" :class="{ 'btn-accent': mode === 'register' }" @click="switchMode('register')">注册</button>
        <button class="btn" :class="{ 'btn-accent': mode === 'reset' }" @click="switchMode('reset')">找回密码</button>
      </div>

      <div v-if="mode === 'login'" class="auth-form">
        <input class="input" v-model.trim="loginForm.username" placeholder="用户名" autocomplete="username" />
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
          @input="clearRegisterSession"
        />
        <input
          class="input"
          v-model.trim="registerForm.email"
          placeholder="邮箱"
          autocomplete="email"
          @input="clearRegisterSession"
        />
        <input
          class="input"
          v-model.trim="registerForm.school_name"
          placeholder="学校（可选）"
          @input="clearRegisterSession"
        />
        <div class="password-field">
          <input
            class="input password-input"
            v-model="registerForm.password"
            :type="passwordVisibility.register ? 'text' : 'password'"
            placeholder="密码"
            autocomplete="new-password"
            @input="clearRegisterSession"
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

        <div class="captcha-card">
          <div class="captcha-header">
            <span class="captcha-title">注册校验</span>
            <button class="btn btn-ghost" type="button" :disabled="challengeLoading" @click="loadRegisterChallenge">
              {{ challengeLoading ? "刷新中..." : "换一题" }}
            </button>
          </div>
          <p class="captcha-prompt">
            {{ registerChallenge.prompt || "正在加载验证题..." }}
          </p>
          <input
            class="input"
            v-model.trim="registerForm.captcha_answer"
            placeholder="请输入答案"
            inputmode="numeric"
            @input="clearRegisterSession"
          />
          <p v-if="registerChallenge.expires_in_seconds" class="captcha-meta">
            此题有效期 {{ Math.ceil(registerChallenge.expires_in_seconds / 60) }} 分钟。
          </p>
        </div>

        <div class="trap-field" aria-hidden="true">
          <label for="register-website">网站</label>
          <input
            id="register-website"
            v-model="registerForm.website"
            type="text"
            autocomplete="off"
            tabindex="-1"
            @input="clearRegisterSession"
          />
        </div>

        <div v-if="registerTicket.token" class="code-card">
          <p class="code-title">验证码已发送</p>
          <p class="code-meta">
            验证码已发送至 {{ registerTicket.masked_email }}。
            有效期 {{ Math.ceil(registerTicket.expires_in_seconds / 60) }} 分钟。
          </p>
          <input
            class="input"
            v-model.trim="registerForm.code"
            placeholder="邮箱验证码"
            inputmode="numeric"
            @keyup.enter="completeRegister"
          />
        </div>

        <div class="auth-actions">
          <button class="btn" :disabled="auth.loading || challengeLoading" @click="sendRegisterCode">
            {{ auth.loading ? "发送中..." : registerTicket.token ? "重新发送验证码" : "发送验证码" }}
          </button>
          <button
            class="btn btn-accent"
            :disabled="auth.loading || !registerTicket.token"
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
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import api from "../services/api";
import { useAuthStore } from "../stores/auth";

const router = useRouter();
const auth = useAuthStore();

const mode = ref("login");
const errorMsg = ref("");
const infoMsg = ref("");
const challengeLoading = ref(false);
const registerChallenge = reactive({
  prompt: "",
  token: "",
  expires_in_seconds: 0,
});
const registerTicket = reactive({
  token: "",
  masked_email: "",
  expires_in_seconds: 0,
});
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
  school_name: "",
  password: "",
  captcha_answer: "",
  website: "",
  code: "",
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
  registerTicket.masked_email = "";
  registerTicket.expires_in_seconds = 0;
  registerForm.code = "";
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
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload)) return payload.join("; ");
  if (typeof payload === "object") {
    const items = [];
    for (const [key, value] of Object.entries(payload)) {
      if (key === "request_id" || key === "retry_after_seconds") continue;
      if (Array.isArray(value)) {
        items.push(`${key}: ${value.join("; ")}`);
      } else if (typeof value === "string") {
        items.push(`${key}: ${value}`);
      }
    }
    if (items.length) return items.join("; ");
  }
  return fallback;
}

function switchMode(nextMode) {
  mode.value = nextMode;
  clearMessages();
  clearRegisterSession();
  clearResetSession();
  resetPasswordVisibility();
  if (nextMode === "register" && !registerChallenge.token && !challengeLoading.value) {
    loadRegisterChallenge();
  }
}

async function loadRegisterChallenge() {
  challengeLoading.value = true;
  try {
    const { data } = await api.get("/auth/register-challenge/");
    registerChallenge.prompt = data.prompt || "";
    registerChallenge.token = data.token || "";
    registerChallenge.expires_in_seconds = Number(data.expires_in_seconds || 0);
    registerForm.captcha_answer = "";
    registerForm.website = "";
    clearRegisterSession();
  } catch (error) {
    errorMsg.value = getErrorText(error, "验证题加载失败");
  } finally {
    challengeLoading.value = false;
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
  if (!registerChallenge.token) {
    await loadRegisterChallenge();
    if (!registerChallenge.token) return;
  }

  try {
    const data = await auth.requestRegisterEmailCode({
      username: registerForm.username,
      email: registerForm.email,
      school_name: registerForm.school_name,
      password: registerForm.password,
      captcha_token: registerChallenge.token,
      captcha_answer: registerForm.captcha_answer,
      website: registerForm.website,
    });
    registerTicket.token = data.ticket_token || "";
    registerTicket.masked_email = data.masked_email || "";
    registerTicket.expires_in_seconds = Number(data.expires_in_seconds || 0);
    registerForm.code = "";
    infoMsg.value = `验证码已发送至 ${registerTicket.masked_email}。`;
  } catch (error) {
    errorMsg.value = getErrorText(error, "注册验证码发送失败");
    await loadRegisterChallenge();
  }
}

async function completeRegister() {
  clearMessages();
  if (!registerTicket.token) {
    errorMsg.value = "请先发送验证码。";
    return;
  }

  try {
    await auth.register({
      ticket_token: registerTicket.token,
      code: registerForm.code,
    });
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

onMounted(() => {
  if (mode.value === "register") {
    loadRegisterChallenge();
  }
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

.captcha-card,
.code-card {
  display: grid;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--line-color, #d7deea);
  border-radius: 16px;
  background: rgba(244, 247, 252, 0.8);
}

.captcha-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.captcha-title,
.code-title {
  font-size: 13px;
  font-weight: 700;
}

.captcha-prompt {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.captcha-meta,
.code-meta {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted, #6b7280);
}

.btn-ghost {
  border-style: dashed;
}

.trap-field {
  position: absolute;
  left: -9999px;
  width: 1px;
  height: 1px;
  overflow: hidden;
}

.info-text {
  color: #2563eb;
}

.error-text {
  color: #dc2626;
}
</style>
