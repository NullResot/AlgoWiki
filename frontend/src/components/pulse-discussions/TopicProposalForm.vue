<template>
  <section class="proposal-panel" lang="zh-CN">
    <span class="eyebrow">COMMUNITY SIGNAL</span>
    <h2>把明晚的话题交给你</h2>
    <p>提交有争议、有经验价值的问题。AI 先做安全审核，管理员再决定排期。</p>
    <form v-if="auth.isAuthenticated" @submit.prevent="submit">
      <label>话题标题<input v-model.trim="form.title" maxlength="220" placeholder="例如：赛时先写暴力还是先证明？" /></label>
      <label>为什么值得讨论<textarea v-model.trim="form.content_md" maxlength="20000" rows="5" placeholder="补充背景、冲突点或你的观察。"></textarea></label>
      <label>标签<input v-model.trim="tagText" maxlength="160" placeholder="赛时策略, 训练方法（最多 5 个）" /></label>
      <p v-if="error" class="form-error">{{ error }}</p>
      <button type="submit" :disabled="submitting">{{ submitting ? "AI 审核中" : "提交热门讨论" }}</button>
    </form>
    <RouterLink v-else :to="{ name: 'auth' }" class="login-link">登录后提交话题</RouterLink>
    <div v-if="result" class="proposal-result" :class="`is-${result.status}`">
      <strong>{{ statusLabel(result.status) }}</strong>
      <span>{{ result.review_note || "投稿已保存，可在这里继续查看状态。" }}</span>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from "vue";
import pulseApi from "../../services/pulse";
import { useAuthStore } from "../../stores/auth";

const auth = useAuthStore();
const form = reactive({ title: "", content_md: "" });
const tagText = ref("");
const submitting = ref(false);
const error = ref("");
const result = ref(null);

function tags() {
  return [...new Set(tagText.value.split(/[,，]/).map((item) => item.trim()).filter(Boolean))].slice(0, 5);
}

function statusLabel(status) {
  return { ai_pending: "AI 审核中", admin_pending: "等待管理员排期", scheduled: "已进入每日讨论日程", rejected: "投稿未通过" }[status] || "投稿已保存";
}

async function submit() {
  error.value = "";
  if (form.title.length < 5 || form.content_md.length < 10) {
    error.value = "标题至少 5 个字，说明至少 10 个字。";
    return;
  }
  submitting.value = true;
  try {
    result.value = await pulseApi.proposeTopic({ ...form, tags: tags() });
    form.title = "";
    form.content_md = "";
    tagText.value = "";
  } catch (requestError) {
    error.value = requestError?.response?.data?.detail || "提交失败，请稍后再试。";
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.proposal-panel { position: sticky; top: 96px; padding: 28px; border: 1px solid rgba(195,169,113,.2); border-radius: 24px; background: radial-gradient(circle at 85% 0, rgba(92,71,119,.2), transparent 42%), linear-gradient(155deg, rgba(19,37,38,.94), rgba(10,15,24,.96)); box-shadow: inset 0 1px rgba(255,255,255,.05), 0 28px 70px rgba(0,0,0,.22); }
.eyebrow { color: #d5b36d; font: 600 10px ui-monospace, monospace; letter-spacing: .18em; }
h2 { margin: 12px 0 10px; color: var(--text-primary, #f5f1e8); font: 600 25px/1.35 Georgia, "Songti SC", serif; }
p { color: var(--text-secondary, #9ba8b2); font-size: 14px; line-height: 1.75; }
form { display: grid; gap: 15px; margin-top: 24px; }
label { display: grid; gap: 8px; color: #b7c1c9; font-size: 13px; }
input, textarea { width: 100%; box-sizing: border-box; border: 1px solid rgba(151,190,188,.17); border-radius: 13px; padding: 12px 14px; color: var(--text-primary, #eef1ed); background: rgba(2,10,14,.52); font: inherit; outline: none; transition: border-color 180ms ease, box-shadow 180ms ease; }
input:focus, textarea:focus { border-color: rgba(213,179,109,.6); box-shadow: 0 0 0 3px rgba(213,179,109,.08); }
textarea { resize: vertical; min-height: 118px; }
button, .login-link { min-height: 44px; border: 1px solid rgba(213,179,109,.36); border-radius: 13px; color: #efe5ca; background: linear-gradient(135deg, rgba(113,86,39,.7), rgba(55,46,39,.9)); font-weight: 650; cursor: pointer; }
button:disabled { cursor: wait; opacity: .65; }
.login-link { display: grid; place-items: center; margin-top: 22px; text-decoration: none; }
.form-error { margin: -4px 0 0; color: #ee9d94; font-size: 12px; }
.proposal-result { display: grid; gap: 5px; margin-top: 18px; padding: 14px; border-left: 2px solid #d5b36d; background: rgba(213,179,109,.07); color: #c5cdd2; font-size: 12px; }
.proposal-result strong { color: #e5c984; }
@media (max-width: 980px) { .proposal-panel { position: static; } }
</style>
