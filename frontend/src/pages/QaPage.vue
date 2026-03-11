<template>
  <section class="qa-layout">
    <aside class="qa-sidebar">
      <div class="qa-title-row">
        <h2>问答</h2>
        <button class="btn" @click="loadQuestions()">刷新</button>
      </div>

      <div class="question-filters">
        <select class="select" v-model="filters.scope" @change="loadQuestions()">
          <option value="all">全部问题</option>
          <option value="mine" :disabled="!auth.isAuthenticated">我的问题</option>
        </select>
        <input class="input" v-model="filters.search" placeholder="搜索问题" @keyup.enter="loadQuestions()" />
        <select class="select" v-model="filters.status" @change="loadQuestions()">
          <option value="">全部状态</option>
          <option value="open">open</option>
          <option value="closed">closed</option>
        </select>
        <select class="select" v-model="filters.order" @change="loadQuestions()">
          <option value="latest">按最近活跃</option>
          <option value="answers">按回答数</option>
          <option value="created_newest">按发布时间（新）</option>
          <option value="created_oldest">按发布时间（旧）</option>
          <option value="oldest">按最早活跃</option>
        </select>
        <button class="btn" @click="loadQuestions()">筛选</button>
        <button class="btn" @click="resetQuestionFilters()">重置</button>
      </div>

      <p class="meta">问题总数：{{ questionPagination.count }}</p>

      <article
        class="question-item"
        v-for="item in questions"
        :key="item.id"
        :class="{ active: selectedQuestion?.id === item.id }"
        @click="selectQuestion(item)"
      >
        <h3>{{ item.title }}</h3>
        <div class="meta">
          {{ item.author.username }} · {{ item.answers_count }} 回答 · {{ formatQuestionStatus(item.status) }}
        </div>
      </article>
      <button v-if="questionPagination.next" class="btn btn-more" @click="loadMoreQuestions">
        {{ questionPagination.loadingMore ? "加载中..." : "加载更多问题" }}
      </button>
      <p class="meta" v-if="!questions.length">暂无问题。</p>

      <section v-if="auth.isAuthenticated" class="create-question">
        <h3>我要提问</h3>
        <input class="input" v-model="questionForm.title" placeholder="问题标题" />
        <ImageUploadHelper label="上传图片并插入 Markdown" @uploaded="onQuestionImageUploaded" />
        <textarea class="textarea" v-model="questionForm.content_md" placeholder="Markdown 问题描述"></textarea>
        <div class="answer-actions">
          <button class="btn" @click="restoreQuestionDraft">恢复草稿</button>
          <button class="btn" @click="clearQuestionDraft">清空草稿</button>
        </div>
        <button class="btn btn-accent" @click="createQuestion">提交问题</button>
      </section>
      <p v-else class="meta">登录后可提问与回答。</p>
    </aside>

    <article class="qa-main">
      <article class="qa-question-card card" v-for="item in questions" :key="`qa-main-${item.id}`">
        <header class="qa-main-header qa-expand-head" @click="toggleQuestion(item)">
          <div>
            <h1 class="qa-question-title">{{ item.title }}</h1>
            <div class="meta">
              {{ item.author.username }} · {{ formatQuestionStatus(item.status) }} · {{ item.answers_count }} 回答
            </div>
          </div>
          <span class="pill">{{ selectedQuestion?.id === item.id ? "收起" : "展开" }}</span>
        </header>

        <section v-if="selectedQuestion?.id === item.id" class="qa-question-body">
          <section class="markdown" v-html="renderMarkdown(item.content_md || '')"></section>

          <div class="qa-actions" v-if="canToggleStatus">
            <button class="btn" @click="startEditQuestion" v-if="canEditQuestion && !questionEdit.editing">编辑问题</button>
            <button v-if="selectedQuestion.status === 'open'" class="btn" @click="closeQuestion">关闭问题</button>
            <button v-else class="btn" @click="reopenQuestion">重开问题</button>
            <button class="btn" @click="removeQuestion">删除问题</button>
          </div>
          <section class="answer-form" v-if="questionEdit.editing">
            <h3>编辑问题</h3>
            <input class="input" v-model="questionEdit.title" placeholder="问题标题" />
            <ImageUploadHelper label="上传图片并插入 Markdown" @uploaded="onQuestionEditImageUploaded" />
            <textarea class="textarea" v-model="questionEdit.content_md" placeholder="Markdown 问题描述"></textarea>
            <div class="answer-actions">
              <button class="btn btn-accent" @click="saveEditedQuestion">保存问题</button>
              <button class="btn" @click="cancelEditQuestion">取消</button>
            </div>
          </section>

          <section class="answers">
            <div class="answers-head">
              <h3>回答</h3>
              <div class="answers-tools">
                <span class="meta">共 {{ answerPagination.count }} 条</span>
                <select class="select" v-model="answerOrder" @change="reloadAnswersOrder">
                  <option value="oldest">按时间正序</option>
                  <option value="latest">按时间倒序</option>
                  <option value="accepted_first">采纳优先</option>
                </select>
              </div>
            </div>
            <article class="answer-item" v-for="answer in answers" :key="answer.id">
              <div class="meta">
                {{ answer.author.username }} · {{ formatTime(answer.created_at) }}
                <span class="pill" v-if="answer.is_accepted">已采纳</span>
              </div>
              <section
                v-if="answerEdit.id !== answer.id"
                class="markdown"
                v-html="renderMarkdown(answer.content_md)"
              ></section>
              <div v-else class="answer-form">
                <ImageUploadHelper label="上传图片并插入 Markdown" @uploaded="onAnswerEditImageUploaded" />
                <textarea class="textarea" v-model="answerEdit.content_md" placeholder="编辑回答"></textarea>
                <div class="answer-actions">
                  <button class="btn btn-accent" @click="saveEditedAnswer(answer)">保存回答</button>
                  <button class="btn" @click="cancelEditAnswer">取消</button>
                </div>
              </div>
              <div class="answer-actions">
                <button v-if="canAcceptAnswer && !answer.is_accepted" class="btn" @click="acceptAnswer(answer.id)">采纳</button>
                <button v-if="canEditAnswer(answer) && answerEdit.id !== answer.id" class="btn" @click="startEditAnswer(answer)">
                  编辑回答
                </button>
                <button v-if="canDeleteAnswer(answer)" class="btn" @click="removeAnswer(answer.id)">删除回答</button>
              </div>
            </article>
            <button v-if="answerPagination.next" class="btn btn-more" @click="loadMoreAnswers">
              {{ answerPagination.loadingMore ? "加载中..." : "加载更多回答" }}
            </button>
          </section>

          <div class="answer-form" v-if="auth.isAuthenticated">
            <ImageUploadHelper label="上传图片并插入 Markdown" @uploaded="onAnswerImageUploaded" />
            <textarea class="textarea" v-model="answerForm.content_md" placeholder="写下回答"></textarea>
            <div class="answer-actions">
              <button class="btn" @click="restoreAnswerDraft" :disabled="!selectedQuestion">恢复草稿</button>
              <button class="btn" @click="clearAnswerDraft" :disabled="!selectedQuestion">清空草稿</button>
            </div>
            <button class="btn btn-accent" @click="createAnswer">提交回答</button>
          </div>
          <p v-else class="meta">登录后可回答。</p>
        </section>
      </article>
      <p v-if="!questions.length" class="meta">暂无问题。</p>
    </article>

    <aside class="qa-right">
      <h3>使用提示</h3>
      <p class="meta">描述最小可复现信息，便于社区更快定位问题。</p>
      <p class="meta">管理员与学校用户可协助维护赛事板块内容。</p>
      <RouterLink class="hint-link" :to="{ name: 'wiki' }">返回知识库</RouterLink>
      <RouterLink class="hint-link" :to="{ name: 'review' }" v-if="auth.isReviewer">进入审核台</RouterLink>
    </aside>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { RouterLink } from "vue-router";

import ImageUploadHelper from "../components/ImageUploadHelper.vue";
import api from "../services/api";
import { renderMarkdown } from "../services/markdown";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const auth = useAuthStore();
const ui = useUiStore();

const questions = ref([]);
const selectedQuestion = ref(null);
const answers = ref([]);
const answerOrder = ref("oldest");
const questionEdit = reactive({
  editing: false,
  title: "",
  content_md: "",
});
const answerEdit = reactive({
  id: null,
  content_md: "",
});

const filters = reactive({
  scope: "all",
  search: "",
  status: "",
  order: "latest",
});

const questionPagination = reactive({
  count: 0,
  next: "",
  loadingMore: false,
});

const answerPagination = reactive({
  count: 0,
  next: "",
  loadingMore: false,
});

const questionForm = reactive({
  title: "",
  content_md: "",
});

const answerForm = reactive({
  content_md: "",
});

const canToggleStatus = computed(() => {
  if (!selectedQuestion.value || !auth.user) return false;
  return auth.isManager || selectedQuestion.value.author.id === auth.user.id;
});
const canAcceptAnswer = computed(() => canToggleStatus.value);
const canEditQuestion = computed(() => {
  if (!selectedQuestion.value || !auth.user) return false;
  return auth.isManager || selectedQuestion.value.author.id === auth.user.id;
});

function appendMarkdown(target, snippet) {
  const next = String(snippet || "").trim();
  if (!next) return String(target || "");
  const base = String(target || "");
  return base ? `${base}\n\n${next}\n` : `${next}\n`;
}

function onQuestionImageUploaded(payload) {
  questionForm.content_md = appendMarkdown(questionForm.content_md, payload?.markdown);
}

function onQuestionEditImageUploaded(payload) {
  questionEdit.content_md = appendMarkdown(questionEdit.content_md, payload?.markdown);
}

function onAnswerImageUploaded(payload) {
  answerForm.content_md = appendMarkdown(answerForm.content_md, payload?.markdown);
}

function onAnswerEditImageUploaded(payload) {
  answerEdit.content_md = appendMarkdown(answerEdit.content_md, payload?.markdown);
}

function canDeleteAnswer(answer) {
  if (!auth.user) return false;
  return auth.isManager || answer.author.id === auth.user.id;
}

function canEditAnswer(answer) {
  if (!auth.user) return false;
  return auth.isManager || answer.author.id === auth.user.id;
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function formatQuestionStatus(status) {
  const map = {
    pending: "审核中",
    open: "open",
    closed: "closed",
    hidden: "hidden",
  };
  return map[status] || status || "-";
}

function normalizePageValue(page, fallback = 1) {
  const n = Number(page);
  if (!Number.isFinite(n) || n < 1) return fallback;
  return Math.floor(n);
}

function nextPageFromUrl(url, fallback = 2) {
  if (!url) return fallback;
  try {
    return Number(new URL(url, window.location.origin).searchParams.get("page") || String(fallback));
  } catch {
    return fallback;
  }
}

function safeParseDraft(rawValue) {
  if (!rawValue) return null;
  try {
    return JSON.parse(rawValue);
  } catch {
    return null;
  }
}

function getQuestionDraftKey() {
  return `algowiki_qa_question_draft_${auth.user?.id || "guest"}`;
}

function getAnswerDraftKey(questionId) {
  return `algowiki_qa_answer_draft_${auth.user?.id || "guest"}_${questionId}`;
}

function persistQuestionDraft() {
  if (!auth.isAuthenticated) return;
  try {
    localStorage.setItem(
      getQuestionDraftKey(),
      JSON.stringify({
        title: questionForm.title,
        content_md: questionForm.content_md,
        updated_at: Date.now(),
      })
    );
  } catch {
    // ignore storage errors
  }
}

function restoreQuestionDraft(showMessage = true) {
  if (!auth.isAuthenticated) return;
  const payload = safeParseDraft(localStorage.getItem(getQuestionDraftKey()));
  if (!payload) return;
  questionForm.title = payload.title || "";
  questionForm.content_md = payload.content_md || "";
  if (showMessage) ui.info("已恢复问题草稿");
}

function clearQuestionDraft(showMessage = true) {
  try {
    localStorage.removeItem(getQuestionDraftKey());
  } catch {
    // ignore storage errors
  }
  if (showMessage) ui.info("已清空问题草稿");
}

function persistAnswerDraft() {
  if (!auth.isAuthenticated || !selectedQuestion.value) return;
  try {
    localStorage.setItem(
      getAnswerDraftKey(selectedQuestion.value.id),
      JSON.stringify({
        content_md: answerForm.content_md,
        updated_at: Date.now(),
      })
    );
  } catch {
    // ignore storage errors
  }
}

function restoreAnswerDraft(showMessage = true) {
  if (!auth.isAuthenticated || !selectedQuestion.value) return;
  const payload = safeParseDraft(localStorage.getItem(getAnswerDraftKey(selectedQuestion.value.id)));
  answerForm.content_md = payload?.content_md || "";
  if (payload && showMessage) ui.info("已恢复回答草稿");
}

function clearAnswerDraft(showMessage = true) {
  if (!selectedQuestion.value) return;
  try {
    localStorage.removeItem(getAnswerDraftKey(selectedQuestion.value.id));
  } catch {
    // ignore storage errors
  }
  answerForm.content_md = "";
  if (showMessage) ui.info("已清空回答草稿");
}

function buildQuestionParams(page = 1) {
  const params = { page };
  if (filters.scope === "mine" && auth.isAuthenticated) params.mine = 1;
  if (filters.search.trim()) params.search = filters.search.trim();
  if (filters.status) params.status = filters.status;
  if (filters.order) params.order = filters.order;
  return params;
}

function buildAnswerParams(questionId, page = 1) {
  return {
    question: questionId,
    page,
    order: answerOrder.value,
  };
}

async function loadQuestions(page = 1, append = false) {
  const safePage = normalizePageValue(page, 1);
  try {
    const { data } = await api.get("/questions/", { params: buildQuestionParams(safePage) });
    const items = data.results || data;
    questions.value = append ? [...questions.value, ...items] : items;
    questionPagination.count = data.count || questions.value.length;
    questionPagination.next = data.next || "";

    if (!questions.value.length) {
      selectedQuestion.value = null;
      answers.value = [];
      answerPagination.count = 0;
      answerPagination.next = "";
      cancelEditQuestion();
      cancelEditAnswer();
      return;
    }

    if (append) return;

    const currentId = selectedQuestion.value?.id;
    const target = currentId ? questions.value.find((item) => item.id === currentId) : questions.value[0];
    if (!target) {
      await selectQuestion(questions.value[0]);
      return;
    }

    selectedQuestion.value = target;
    cancelEditQuestion();
    cancelEditAnswer();
    await loadAnswers(target.id, 1, false);
  } catch (error) {
    if (safePage !== 1 && isInvalidPageError(error)) {
      return loadQuestions(1, false);
    }
    ui.error(getErrorText(error, "问题列表加载失败"));
  }
}

async function selectQuestion(item) {
  if (!item) return;
  try {
    selectedQuestion.value = item;
    cancelEditQuestion();
    cancelEditAnswer();
    await loadAnswers(item.id, 1, false);
  } catch (error) {
    ui.error(getErrorText(error, "回答加载失败"));
  }
}

async function toggleQuestion(item) {
  if (!item) return;
  if (selectedQuestion.value?.id === item.id) {
    selectedQuestion.value = null;
    answers.value = [];
    answerPagination.count = 0;
    answerPagination.next = "";
    cancelEditQuestion();
    cancelEditAnswer();
    return;
  }
  await selectQuestion(item);
}

async function loadAnswers(questionId, page = 1, append = false) {
  const safePage = normalizePageValue(page, 1);
  try {
    const { data } = await api.get("/answers/", { params: buildAnswerParams(questionId, safePage) });
    const items = data.results || data;
    answers.value = append ? [...answers.value, ...items] : items;
    answerPagination.count = data.count || answers.value.length;
    answerPagination.next = data.next || "";
  } catch (error) {
    if (safePage !== 1 && isInvalidPageError(error)) {
      return loadAnswers(questionId, 1, false);
    }
    throw error;
  }
}

async function loadMoreQuestions() {
  if (!questionPagination.next || questionPagination.loadingMore) return;
  questionPagination.loadingMore = true;
  try {
    await loadQuestions(nextPageFromUrl(questionPagination.next), true);
  } finally {
    questionPagination.loadingMore = false;
  }
}

async function loadMoreAnswers() {
  if (!selectedQuestion.value || !answerPagination.next || answerPagination.loadingMore) return;
  answerPagination.loadingMore = true;
  try {
    await loadAnswers(selectedQuestion.value.id, nextPageFromUrl(answerPagination.next), true);
  } finally {
    answerPagination.loadingMore = false;
  }
}

async function reloadAnswersOrder() {
  if (!selectedQuestion.value) return;
  cancelEditAnswer();
  await loadAnswers(selectedQuestion.value.id, 1, false);
}

function resetQuestionFilters() {
  filters.scope = "all";
  filters.search = "";
  filters.status = "";
  filters.order = "latest";
  loadQuestions(1, false);
}

function startEditQuestion() {
  if (!selectedQuestion.value || !canEditQuestion.value) return;
  questionEdit.editing = true;
  questionEdit.title = selectedQuestion.value.title || "";
  questionEdit.content_md = selectedQuestion.value.content_md || "";
}

function cancelEditQuestion() {
  questionEdit.editing = false;
  questionEdit.title = "";
  questionEdit.content_md = "";
}

async function saveEditedQuestion() {
  if (!selectedQuestion.value || !canEditQuestion.value) return;
  if (!questionEdit.title.trim() || !questionEdit.content_md.trim()) {
    ui.info("请填写问题标题和内容");
    return;
  }
  try {
    const payload = {
      title: questionEdit.title.trim(),
      content_md: questionEdit.content_md,
    };
    await api.patch(`/questions/${selectedQuestion.value.id}/`, payload);
    ui.success("问题已更新");
    cancelEditQuestion();
    await loadQuestions(1, false);
  } catch (error) {
    ui.error(getErrorText(error, "更新问题失败"));
  }
}

function startEditAnswer(answer) {
  if (!canEditAnswer(answer)) return;
  answerEdit.id = answer.id;
  answerEdit.content_md = answer.content_md || "";
}

function cancelEditAnswer() {
  answerEdit.id = null;
  answerEdit.content_md = "";
}

async function saveEditedAnswer(answer) {
  if (!canEditAnswer(answer)) return;
  if (!answerEdit.content_md.trim()) {
    ui.info("回答内容不能为空");
    return;
  }
  try {
    await api.patch(`/answers/${answer.id}/`, {
      content_md: answerEdit.content_md,
    });
    ui.success("回答已更新");
    cancelEditAnswer();
    await loadAnswers(selectedQuestion.value.id, 1, false);
  } catch (error) {
    ui.error(getErrorText(error, "更新回答失败"));
  }
}

async function createQuestion() {
  if (!questionForm.title || !questionForm.content_md) {
    ui.info("请填写问题标题和内容");
    return;
  }

  try {
    const payload = {
      title: questionForm.title,
      content_md: questionForm.content_md,
    };

    const { data } = await api.post("/questions/", payload);

    questionForm.title = "";
    questionForm.content_md = "";
    clearQuestionDraft(false);
    await loadQuestions(1, false);
    const created = questions.value.find((item) => item.id === data.id);
    if (created) {
      await selectQuestion(created);
    }
    ui.success("问题已提交");
  } catch (error) {
    ui.error(getErrorText(error, "提交问题失败"));
  }
}

async function createAnswer() {
  if (!selectedQuestion.value || !answerForm.content_md.trim()) {
    ui.info("请填写回答内容");
    return;
  }

  try {
    await api.post("/answers/", {
      question: selectedQuestion.value.id,
      content_md: answerForm.content_md,
    });
    clearAnswerDraft(false);
    cancelEditAnswer();
    await loadAnswers(selectedQuestion.value.id, 1, false);
    await loadQuestions(1, false);
    ui.success("回答已提交");
  } catch (error) {
    ui.error(getErrorText(error, "提交回答失败"));
  }
}

async function acceptAnswer(answerId) {
  try {
    await api.post(`/answers/${answerId}/accept/`);
    cancelEditAnswer();
    await loadAnswers(selectedQuestion.value.id, 1, false);
    await loadQuestions(1, false);
    ui.success("回答已采纳");
  } catch (error) {
    ui.error(getErrorText(error, "采纳失败"));
  }
}

async function closeQuestion() {
  try {
    await api.post(`/questions/${selectedQuestion.value.id}/close/`);
    await loadQuestions();
    selectedQuestion.value.status = "closed";
    ui.success("问题已关闭");
  } catch (error) {
    ui.error(getErrorText(error, "关闭问题失败"));
  }
}

async function reopenQuestion() {
  try {
    await api.post(`/questions/${selectedQuestion.value.id}/reopen/`);
    await loadQuestions();
    selectedQuestion.value.status = "open";
    ui.success("问题已重开");
  } catch (error) {
    ui.error(getErrorText(error, "重开问题失败"));
  }
}

async function removeQuestion() {
  if (!selectedQuestion.value) return;
  if (!window.confirm(`确认删除问题「${selectedQuestion.value.title}」？`)) return;
  try {
    await api.delete(`/questions/${selectedQuestion.value.id}/`);
    ui.success("问题已删除");
    selectedQuestion.value = null;
    answers.value = [];
    cancelEditQuestion();
    cancelEditAnswer();
    await loadQuestions();
  } catch (error) {
    ui.error(getErrorText(error, "删除问题失败"));
  }
}

async function removeAnswer(answerId) {
  if (!window.confirm("确认删除该回答？")) return;
  try {
    await api.delete(`/answers/${answerId}/`);
    ui.success("回答已删除");
    cancelEditAnswer();
    await loadAnswers(selectedQuestion.value.id, 1, false);
    await loadQuestions(1, false);
  } catch (error) {
    ui.error(getErrorText(error, "删除回答失败"));
  }
}

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload)) return payload.join("；");
  if (typeof payload === "object") {
    const parts = [];
    for (const [field, value] of Object.entries(payload)) {
      if (Array.isArray(value)) {
        parts.push(`${field}: ${value.join("，")}`);
      } else if (typeof value === "string") {
        parts.push(`${field}: ${value}`);
      }
    }
    if (parts.length) return parts.join("；");
  }
  return fallback;
}

function isInvalidPageError(error) {
  const payload = error?.response?.data;
  const detail =
    typeof payload?.detail === "string"
      ? payload.detail
      : typeof payload === "string"
      ? payload
      : "";
  return /invalid page|无效页面/i.test(detail);
}

watch(
  [() => questionForm.title, () => questionForm.content_md],
  () => {
    persistQuestionDraft();
  }
);

watch(
  () => selectedQuestion.value?.id,
  () => {
    answerForm.content_md = "";
    restoreAnswerDraft(false);
  }
);

watch(
  () => answerForm.content_md,
  () => {
    persistAnswerDraft();
  }
);

watch(
  () => auth.user?.id,
  () => {
    restoreQuestionDraft(false);
    if (selectedQuestion.value) restoreAnswerDraft(false);
  }
);

onMounted(async () => {
  restoreQuestionDraft(false);
  await loadQuestions();
});
</script>

<style scoped>
.qa-layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr) 220px;
  gap: 24px;
}

.qa-sidebar,
.qa-right {
  align-self: start;
  position: sticky;
  top: 94px;
}

.qa-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.question-filters {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
  margin-bottom: 10px;
}

.qa-title-row h2 {
  font-size: 34px;
}

.question-item {
  margin-top: 8px;
  border: 1px solid var(--hairline);
  border-radius: 12px;
  padding: 12px;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.55);
  box-shadow: var(--shadow-sm);
}

.question-item.active {
  background: rgba(79, 143, 255, 0.08);
  box-shadow: var(--shadow-md);
}

.question-item h3 {
  margin-bottom: 4px;
  font-size: 20px;
}

.create-question {
  margin-top: 12px;
  border-top: 1px solid var(--hairline);
  padding-top: 12px;
  display: grid;
  gap: 8px;
}

.create-question :deep(.image-upload-helper),
.answer-form :deep(.image-upload-helper) {
  margin-bottom: -1px;
}

.qa-main-header {
  margin-bottom: 10px;
}

.qa-main-header h1 {
  font-size: clamp(34px, 5vw, 54px);
}

.qa-question-card {
  padding: 14px;
  margin-bottom: 12px;
}

.qa-question-title {
  font-size: clamp(30px, 4.2vw, 52px);
}

.qa-expand-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  cursor: pointer;
}

.qa-question-body {
  margin-top: 10px;
  border-top: 1px solid var(--hairline);
  padding-top: 10px;
}

.qa-actions {
  margin: 10px 0 12px;
}

.answers {
  margin-top: 12px;
}

.answer-item {
  border-top: 1px solid var(--hairline);
  padding-top: 10px;
  margin-top: 10px;
  font-size: 16px;
}

.answers-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.answers-tools {
  display: flex;
  align-items: center;
  gap: 8px;
}

.answer-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}

.btn-more {
  margin-top: 10px;
}

.answer-form {
  margin-top: 14px;
  display: grid;
  gap: 8px;
}

.qa-right h3 {
  font-size: 24px;
  margin-bottom: 10px;
}

.hint-link {
  display: block;
  margin-top: 8px;
  color: var(--accent);
  font-size: 15px;
}

@media (max-width: 1260px) {
  .qa-layout {
    grid-template-columns: 300px minmax(0, 1fr);
  }

  .qa-right {
    grid-column: 1 / -1;
    position: static;
    border-top: 1px solid var(--hairline);
    padding-top: 10px;
  }
}

@media (max-width: 960px) {
  .qa-layout {
    grid-template-columns: 1fr;
    gap: 14px;
  }

  .qa-sidebar {
    position: static;
  }

  .qa-main-header h1 {
    font-size: clamp(30px, 9vw, 42px);
  }

  .question-item h3 {
    font-size: 19px;
  }

  .answers-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .answers-tools {
    flex-wrap: wrap;
  }
}
</style>
