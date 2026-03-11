<template>
  <section class="auth-wrap">
    <article class="card auth-card">
      <div class="auth-tabs">
        <button class="btn" :class="{ 'btn-accent': mode === 'login' }" @click="mode = 'login'">登录</button>
        <button class="btn" :class="{ 'btn-accent': mode === 'register' }" @click="mode = 'register'">注册</button>
      </div>

      <div v-if="mode === 'login'" class="auth-form">
        <input class="input" v-model="loginForm.username" placeholder="用户名" />
        <input class="input" v-model="loginForm.password" type="password" placeholder="密码" />
        <button class="btn btn-accent" :disabled="auth.loading" @click="login">登录</button>
      </div>

      <div v-else class="auth-form">
        <input class="input" v-model="registerForm.username" placeholder="用户名" />
        <input class="input" v-model="registerForm.email" placeholder="邮箱" />
        <input class="input" v-model="registerForm.school_name" placeholder="学校（可选）" />
        <input class="input" v-model="registerForm.password" type="password" placeholder="密码" />
        <button class="btn btn-accent" :disabled="auth.loading" @click="register">注册</button>
      </div>

      <p class="meta" v-if="errorMsg">{{ errorMsg }}</p>
    </article>
  </section>
</template>

<script setup>
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { useAuthStore } from "../stores/auth";

const router = useRouter();
const auth = useAuthStore();

const mode = ref("login");
const errorMsg = ref("");

const loginForm = reactive({
  username: "",
  password: "",
});

const registerForm = reactive({
  username: "",
  email: "",
  school_name: "",
  password: "",
});

function getErrorText(error, fallback) {
  const payload = error?.response?.data;
  if (!payload) return fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload)) return payload.join("；");
  if (typeof payload === "object") {
    const items = [];
    for (const [key, value] of Object.entries(payload)) {
      if (Array.isArray(value)) {
        items.push(`${key}: ${value.join("，")}`);
      } else if (typeof value === "string") {
        items.push(`${key}: ${value}`);
      }
    }
    if (items.length) return items.join("；");
  }
  return fallback;
}

async function login() {
  errorMsg.value = "";
  try {
    await auth.login(loginForm);
    await router.push({ name: "profile" });
  } catch (error) {
    errorMsg.value = getErrorText(error, "登录失败");
  }
}

async function register() {
  errorMsg.value = "";
  try {
    await auth.register(registerForm);
    await router.push({ name: "profile" });
  } catch (error) {
    errorMsg.value = getErrorText(error, "注册失败");
  }
}
</script>

<style scoped>
.auth-wrap {
  display: grid;
  place-items: center;
  min-height: calc(100vh - 180px);
}

.auth-card {
  width: min(520px, 100%);
  padding: 20px;
}

.auth-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.auth-form {
  display: grid;
  gap: 10px;
}
</style>
