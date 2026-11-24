<template>
  <section class="discussion-detail" lang="zh-CN">
    <div class="detail-shell">
      <nav class="detail-nav">
        <RouterLink :to="{ name: 'pulse-discussions' }">← 返回每日讨论</RouterLink>
        <span>{{ route.params.date }}</span>
      </nav>
      <div v-if="loading && !discussion" class="detail-skeleton">
        <SkeletonBlock :lines="6" :line-height="20" label="正在接收讨论详情" />
      </div>
      <div v-else-if="error && !discussion" class="state-error-card" role="alert">
        <strong>信号暂时无法接通</strong>
        <p>{{ error }}</p>
        <button type="button" @click="load()">重试加载</button>
      </div>
      <template v-else-if="discussion">
        <article class="question-card">
          <div class="question-meta"><span>DAILY QUESTION</span><time>{{ discussion.date }}</time></div>
          <h1>{{ discussion.question.title }}</h1>
          <p class="question-body">{{ discussion.question.content_md }}</p>
          <div v-if="discussion.poll?.options?.length" class="poll-strip">
            <span>{{ discussion.poll.prompt }}</span>
            <i v-for="option in discussion.poll.options" :key="option.id">{{ option.text }} · {{ option.percentage }}%</i>
          </div>
        </article>

        <section class="answers-section">
          <header>
            <div>
              <span class="eyebrow">COMMUNITY ANSWERS</span>
              <h2>{{ discussion.answers.length }} 个回答</h2>
            </div>
            <span v-if="refreshing" class="refresh-pill">正在同步回答...</span>
          </header>
          <article v-for="answer in discussion.answers" :key="answer.id" class="answer-card" :class="{ pending: answer.status === 'pending' }">
            <div class="answer-author"><strong>{{ answer.author.username }}</strong><time>{{ formatTime(answer.created_at) }}</time><span v-if="answer.status === 'pending'">AI 审核中 · pending</span></div>
            <p>{{ answer.content_md }}</p>
          </article>
          <div v-if="!discussion.answers.length" class="empty-answer">还没有公开回答，成为第一个留下思路的人。</div>
        </section>

        <form v-if="auth.isAuthenticated" class="answer-composer" aria-label="发表回答" @submit.prevent="submitAnswer">
          <div><span class="eyebrow">YOUR SIGNAL</span><h2>留下一个可验证的思路</h2><p>历史话题仍可回答；只有话题当天的首次有效回答会获得换签券。</p></div>
          <textarea
            v-model.trim="content"
            maxlength="20000"
            rows="6"
            placeholder="给出判断、反例、训练瞬间或一条可复现的思路。（支持 Ctrl/Cmd + Enter 提交）"
            @keydown.ctrl.enter.prevent="submitAnswer"
            @keydown.meta.enter.prevent="submitAnswer"
          ></textarea>
          <p v-if="submitMessage" class="submit-message" :class="{ 'is-error': submitError }" role="status">{{ submitMessage }}</p>
          <div class="composer-foot">
            <small>{{ content.length }} / 20000（至少 3 个字符）</small>
            <button type="submit" :disabled="submitting || content.length < 3">{{ submitting ? "提交审核中" : "提交回答" }}</button>
          </div>
        </form>
        <RouterLink v-else :to="{ name: 'auth' }" class="login-card">登录后参与这场讨论</RouterLink>
      </template>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import SkeletonBlock from "../components/SkeletonBlock.vue";
import pulseApi from "../services/pulse";
import { useAuthStore } from "../stores/auth";

const route = useRoute();
const auth = useAuthStore();
const discussion = ref(null);
const loading = ref(false);
const refreshing = ref(false);
const error = ref("");
const content = ref("");
const submitting = ref(false);
const submitMessage = ref("");
const submitError = ref(false);
let loadRequestId = 0;

async function load({ silent = false } = {}) {
  const currentId = ++loadRequestId;
  if (silent && discussion.value) {
    refreshing.value = true;
  } else {
    loading.value = true;
  }
  error.value = "";
  try {
    const data = await pulseApi.discussion(route.params.date);
    if (currentId !== loadRequestId) return;
    discussion.value = data;
  } catch (requestError) {
    if (currentId !== loadRequestId) return;
    if (!silent || !discussion.value) {
      error.value = requestError?.response?.data?.detail || "这期讨论暂时无法读取。";
    }
  } finally {
    if (currentId === loadRequestId) {
      loading.value = false;
      refreshing.value = false;
    }
  }
}

async function submitAnswer() {
  if (submitting.value || content.value.length < 3) return;
  submitting.value = true;
  submitMessage.value = "";
  submitError.value = false;
  try {
    const answer = await pulseApi.answerDiscussion(route.params.date, content.value);
    content.value = "";
    submitMessage.value = answer.status === "visible" ? "回答已通过 AI 审核并公开。" : "回答已保存，正在等待 AI 审核。";
    await load({ silent: true });
  } catch (requestError) {
    submitError.value = true;
    submitMessage.value = requestError?.response?.data?.detail || "提交失败，请稍后重试。";
  } finally {
    submitting.value = false;
  }
}

function formatTime(value) { return new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value)); }
onMounted(() => load());
watch(() => route.params.date, () => load());
</script>

<style scoped>
.discussion-detail { min-height: 100vh; color: #eef0eb; background: radial-gradient(circle at 80% 8%, rgba(78,53,103,.23), transparent 28%), radial-gradient(circle at 10% 38%, rgba(31,93,91,.2), transparent 33%), #070c12; }
.discussion-detail::before { content: ""; position: fixed; inset: 0; pointer-events: none; opacity: .3; background-image: radial-gradient(circle, #d8b767 0 1px, transparent 1.4px); background-size: 260px 240px; }
.detail-shell { position: relative; width: min(1080px, calc(100% - 44px)); margin: 0 auto; padding: 30px 0 80px; }.detail-nav { display: flex; justify-content: space-between; padding-bottom: 22px; border-bottom: 1px solid rgba(255,255,255,.08); color: #8c9aa4; font-variant-numeric: tabular-nums; }.detail-nav a { color: #d5bf86; text-decoration: none; transition: color var(--dur-fast) var(--ease-out); }.detail-nav a:hover { color: #f3e6be; }
.detail-skeleton { margin-top: 36px; padding: 32px; border: 1px solid rgba(170,190,187,.16); border-radius: 26px; background: rgba(11,17,29,.78); }
.state-error-card { display: grid; justify-items: center; gap: 10px; margin-top: 40px; padding: 48px 24px; border: 1px solid rgba(237,154,147,.28); border-radius: 24px; background: rgba(42,18,22,.45); text-align: center; }
.state-error-card strong { color: #f6b2ab; font-size: 16px; }
.state-error-card p { margin: 0; color: #d5b4b1; font-size: 14px; }
.state-error-card button { min-height: 38px; padding: 0 16px; border: 1px solid rgba(237,154,147,.42); border-radius: 10px; color: #f8dcd9; background: rgba(237,154,147,.14); cursor: pointer; }
.question-card { margin-top: 48px; padding: clamp(28px,5vw,62px); border: 1px solid rgba(170,190,187,.17); border-radius: 30px; background: linear-gradient(140deg, rgba(17,38,39,.9), rgba(11,15,25,.93) 55%, rgba(39,27,49,.8)); box-shadow: inset 0 1px rgba(255,255,255,.05), 0 35px 90px rgba(0,0,0,.25); }.question-meta { display: flex; justify-content: space-between; color: #92a0ac; font-size: 12px; font-variant-numeric: tabular-nums; }.question-meta span,.eyebrow { color: #d8b86e; font: 600 10px ui-monospace,monospace; letter-spacing: .17em; }
h1 { margin: 25px 0 20px; color: #f3f0e7; font: 600 clamp(34px,5vw,64px)/1.18 Georgia,"Songti SC",serif; letter-spacing: -.03em; }.question-body { max-width: 830px; color: #b7c2c8; font-size: 17px; line-height: 1.9; white-space: pre-wrap; }
.poll-strip { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 32px; padding-top: 22px; border-top: 1px solid rgba(255,255,255,.07); color: #9aa7b0; font-size: 12px; font-variant-numeric: tabular-nums; }.poll-strip span { width: 100%; color: #d4c4a0; }.poll-strip i { border: 1px solid rgba(126,187,187,.15); border-radius: 999px; padding: 8px 12px; font-style: normal; background: rgba(4,13,18,.4); }
.answers-section { margin-top: 56px; }.answers-section header { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; }.answers-section header h2,.answer-composer h2 { margin: 9px 0 0; color: #f3f0e7; font: 600 30px Georgia,"Songti SC",serif; }.refresh-pill { color: #8c98a3; font-size: 12px; }.answer-card { margin-top: 16px; padding: 25px 28px; border: 1px solid rgba(255,255,255,.08); border-radius: 20px; background: rgba(11,19,27,.75); }.answer-card.pending { border-style: dashed; opacity: .78; }.answer-author { display: flex; gap: 14px; align-items: center; color: #8c98a3; font-size: 12px; font-variant-numeric: tabular-nums; }.answer-author strong { color: #e2e8e3; font-size: 14px; }.answer-author span { margin-left: auto; color: #d7b66e; }.answer-card p { color: #c0c8ce; line-height: 1.85; white-space: pre-wrap; }.empty-answer { margin-top: 16px; padding: 46px; border: 1px dashed rgba(255,255,255,.1); border-radius: 20px; text-align: center; color: #8c98a3; }
.answer-composer { display: grid; gap: 18px; margin-top: 48px; padding: 30px; border: 1px solid rgba(213,179,109,.18); border-radius: 24px; background: rgba(14,24,29,.84); }.answer-composer p { margin: 8px 0 0; color: #96a3ac; }.answer-composer textarea { width: 100%; box-sizing: border-box; min-height: 160px; resize: vertical; border: 1px solid rgba(144,190,188,.18); border-radius: 15px; padding: 16px; color: #edf0eb; background: rgba(3,10,14,.65); font: 15px/1.7 inherit; outline: none; transition: border-color var(--dur-fast) var(--ease-out), box-shadow var(--dur-fast) var(--ease-out); }.answer-composer textarea:focus { border-color: rgba(213,179,109,.58); box-shadow: 0 0 0 3px rgba(213,179,109,.07); }.composer-foot { display: flex; align-items: center; justify-content: space-between; gap: 12px; }.composer-foot small { color: #8c98a3; font-size: 12px; font-variant-numeric: tabular-nums; }.answer-composer button { min-width: 150px; min-height: 44px; border: 1px solid rgba(213,179,109,.35); border-radius: 12px; color: #f0e5ca; background: linear-gradient(135deg, rgba(110,84,40,.78), rgba(54,44,38,.9)); cursor: pointer; transition: border-color var(--dur-fast) var(--ease-out), transform var(--dur-fast) var(--ease-out), opacity var(--dur-fast) var(--ease-out); }.answer-composer button:not(:disabled):hover { border-color: rgba(213,179,109,.65); transform: translate3d(0, -1px, 0); }.answer-composer button:not(:disabled):active { transform: scale(0.98); }.answer-composer button:disabled { opacity: .45; cursor: default; }.submit-message { color: #7ae2b5 !important; font-size: 13px; }.submit-message.is-error { color: #f49b94 !important; }.login-card { display: grid; place-items: center; min-height: 84px; margin-top: 42px; border: 1px solid rgba(213,179,109,.2); border-radius: 18px; color: #dcc58f; text-decoration: none; background: rgba(20,29,31,.72); }
.detail-nav a:focus-visible, .answer-composer button:focus-visible, .login-card:focus-visible, .state-error-card button:focus-visible { outline: 2px solid rgba(92,205,244,.72); outline-offset: 2px; }
@media (max-width: 620px) { .detail-shell { width: min(100% - 26px,1080px); }.question-card { border-radius: 22px; }.question-meta,.answer-author,.composer-foot { align-items: flex-start; flex-wrap: wrap; }.answer-author span { width: 100%; margin-left: 0; }.answer-composer { padding: 22px 18px; }.answer-composer button { width: 100%; } }
@media (prefers-reduced-motion: reduce) {
  .answer-composer button { transition: border-color var(--dur-fast) linear, opacity var(--dur-fast) linear; }
  .answer-composer button:not(:disabled):hover, .answer-composer button:not(:disabled):active { transform: none; }
}
</style>
