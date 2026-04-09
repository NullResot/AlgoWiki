<template>
  <section class="qa-shell">
    <aside class="qa-sidebar card">
      <button class="btn btn-accent qa-primary-btn" type="button" @click="toggleAskPanel">
        {{ showAskPanel ? "收起提问面板" : "我要提问" }}
      </button>

      <section class="qa-sidebar-block">
        <p class="qa-sidebar-label">浏览方式</p>
        <button
          v-for="item in scopeOptions"
          :key="item.value"
          type="button"
          class="qa-sidebar-link"
          :class="{ 'qa-sidebar-link--active': filters.scope === item.value }"
          :disabled="item.authOnly && !auth.isAuthenticated"
          @click="switchScope(item.value)"
        >
          <span>{{ item.label }}</span>
          <small>{{ item.hint }}</small>
        </button>
      </section>

      <section v-if="filters.scope !== 'deleted'" class="qa-sidebar-block">
        <p class="qa-sidebar-label">状态筛选</p>
        <div class="qa-chip-row">
          <button
            v-for="item in statusOptions"
            :key="item.value || 'all'"
            type="button"
            class="qa-chip"
            :class="{ 'qa-chip--active': filters.status === item.value }"
            @click="setStatusFilter(item.value)"
          >
            {{ item.label }}
          </button>
        </div>
      </section>

      <section class="qa-sidebar-block">
        <p class="qa-sidebar-label">检索</p>
        <input class="input" v-model="filters.search" placeholder="搜索标题或正文" @keyup.enter="loadQuestions()" />
      </section>

      <section class="qa-sidebar-block">
        <p class="qa-sidebar-label">当前结果</p>
        <p class="meta qa-side-meta">{{ scopeSummary }}</p>
        <div class="qa-side-actions">
          <button class="btn" type="button" @click="loadQuestions()">刷新</button>
          <button class="btn" type="button" @click="resetQuestionFilters">重置</button>
        </div>
      </section>

      <p v-if="!auth.isAuthenticated" class="meta qa-login-tip">登录后可提问、回答和保存草稿。</p>
    </aside>

    <main class="qa-main">
      <section v-if="auth.isAuthenticated && showAskPanel" ref="askPanelRef" class="qa-compose">
        <h3>发布新问题</h3>
        <input ref="questionTitleInput" class="input" v-model="questionForm.title" placeholder="问题标题" />
        <textarea class="textarea" v-model="questionForm.content_md" placeholder="Markdown 问题描述"></textarea>
        <div class="qa-compose-actions">
          <button class="btn" type="button" @click="restoreQuestionDraft">恢复草稿</button>
          <button class="btn" type="button" @click="clearQuestionDraft">清空草稿</button>
        </div>
        <button class="btn btn-accent" type="button" @click="createQuestion">提交问题</button>
      </section>

      <header class="qa-header card">
        <div class="qa-header-copy">
          <p class="qa-kicker">Discussion Board</p>
          <h1>{{ boardTitle }}</h1>
          <p class="meta">{{ boardDescription }}</p>
        </div>
        <div class="qa-header-tools">
          <div class="qa-order-group">
            <button
              v-for="item in orderOptions"
              :key="item.value"
              type="button"
              class="qa-order-btn"
              :class="{ 'qa-order-btn--active': filters.order === item.value }"
              @click="setOrder(item.value)"
            >
              {{ item.label }}
            </button>
          </div>
          <button class="btn" type="button" @click="loadQuestions()">刷新列表</button>
        </div>
      </header>

      <div v-if="usingDemoQuestions" class="qa-demo-banner">
        当前列表是开发环境演示数据，用于验收问答区布局，不会写入正式站点。
      </div>

      <section class="qa-feed">
        <article
          v-for="item in displayQuestions"
          :key="String(item.id)"
          class="qa-thread card"
          :class="{ 'qa-thread--active': selectedQuestion?.id === item.id }"
        >
          <button type="button" class="qa-thread-summary" @click="toggleQuestion(item)">
            <div class="qa-thread-copy">
              <div class="qa-thread-top">
                <span class="qa-status" :class="`qa-status--${item.status || 'unknown'}`">
                  {{ formatQuestionStatus(item.status) }}
                </span>
                <span class="qa-thread-time">{{ formatTime(item.updated_at || item.created_at) }}</span>
              </div>

              <h2>{{ item.title }}</h2>
              <p v-if="selectedQuestion?.id !== item.id" class="qa-thread-preview">{{ getQuestionPreview(item).text }}</p>

              <div v-if="isDemoQuestion(item)" class="qa-tag-row">
                <span class="qa-tag" v-if="isDemoQuestion(item)">演示数据</span>
              </div>

              <div class="qa-thread-meta">
                <span>{{ item.author.username }}</span>
                <span>{{ item.answers_count }} 条回答</span>
                <span v-if="getQuestionPreview(item).isAccepted">已采纳回答</span>
              </div>
            </div>

            <div class="qa-thread-side">
              <strong>{{ item.answers_count }}</strong>
              <span>回答</span>
              <span v-if="getQuestionPreview(item).isAccepted" class="qa-thread-badge">已采纳</span>
            </div>
          </button>

          <section v-if="selectedQuestion?.id === item.id" class="qa-thread-detail">
            <div v-if="isSelectedDemoQuestion" class="qa-demo-inline">
              这是用于本地验收的演示讨论串，下面的回答区是只读样本。
            </div>

            <section
              v-if="item.content_md?.trim()"
              class="markdown qa-question-markdown"
              v-html="renderMarkdown(item.content_md || '')"
            ></section>

            <div class="qa-detail-actions" v-if="canToggleStatus && selectedQuestion.status !== 'hidden'">
              <button v-if="canApproveQuestion" class="btn btn-accent" type="button" @click="approveQuestion">
                通过问题
              </button>
              <button class="btn" type="button" @click="startEditQuestion" v-if="canEditQuestion && !questionEdit.editing">
                编辑问题
              </button>
              <button v-if="selectedQuestion.status === 'open'" class="btn" type="button" @click="closeQuestion">关闭问题</button>
              <button v-else-if="selectedQuestion.status === 'closed'" class="btn" type="button" @click="reopenQuestion">重开问题</button>
              <button class="btn" type="button" @click="removeQuestion">删除问题</button>
            </div>
            <div v-else-if="selectedQuestion.status === 'hidden'" class="qa-hidden-restore">
              <p class="meta qa-hidden-note">
                该问题已删除，仅在“已删除问题”分区保留只读查看，最多保留最近 30 条。
              </p>
              <button v-if="canRestoreQuestion" class="btn" type="button" @click="restoreQuestion">恢复问题</button>
            </div>

            <section class="qa-edit-panel" v-if="questionEdit.editing">
              <h3>编辑问题</h3>
              <input class="input" v-model="questionEdit.title" placeholder="问题标题" />
              <textarea class="textarea" v-model="questionEdit.content_md" placeholder="Markdown 问题描述"></textarea>
              <div class="qa-compose-actions">
                <button class="btn btn-accent" type="button" @click="saveEditedQuestion">保存问题</button>
                <button class="btn" type="button" @click="cancelEditQuestion">取消</button>
              </div>
            </section>

            <section class="qa-answer-panel">
              <div class="qa-answer-head">
                <div>
                  <h3>回答区</h3>
                  <p class="meta">共 {{ currentAnswers.length }} 条回答</p>
                </div>
                <select class="select qa-answer-order" v-model="answerOrder" @change="reloadAnswersOrder">
                  <option value="oldest">按时间正序</option>
                  <option value="latest">按时间倒序</option>
                  <option value="accepted_first">采纳优先</option>
                </select>
              </div>

              <article class="answer-item" v-for="answer in currentAnswers" :key="String(answer.id)">
                <div class="answer-item-head">
                  <div class="meta">
                    {{ answer.author.username }} · {{ formatTime(answer.created_at) }}
                  </div>
                  <div class="answer-item-flags">
                    <span class="pill" v-if="answer.is_accepted">已采纳</span>
                    <span class="pill" v-if="answer.status !== 'visible'">{{ formatAnswerStatus(answer.status) }}</span>
                  </div>
                </div>

                <section
                  v-if="answerEdit.id !== answer.id"
                  class="markdown"
                  v-html="renderMarkdown(answer.content_md || '')"
                ></section>

                <div v-else class="qa-edit-panel">
                  <textarea class="textarea" v-model="answerEdit.content_md" placeholder="编辑回答"></textarea>
                  <div class="qa-compose-actions">
                    <button class="btn btn-accent" type="button" @click="saveEditedAnswer(answer)">保存回答</button>
                    <button class="btn" type="button" @click="cancelEditAnswer">取消</button>
                  </div>
                </div>

                <div class="qa-compose-actions" v-if="!answer.__demo">
                  <button v-if="canAcceptAnswer && !answer.is_accepted" class="btn" type="button" @click="acceptAnswer(answer.id)">采纳</button>
                  <button v-if="canEditAnswer(answer) && answerEdit.id !== answer.id" class="btn" type="button" @click="startEditAnswer(answer)">
                    编辑回答
                  </button>
                  <button v-if="canDeleteAnswer(answer)" class="btn" type="button" @click="removeAnswer(answer.id)">删除回答</button>
                </div>
              </article>

              <button v-if="answerPagination.next" class="btn qa-more" type="button" @click="loadMoreAnswers">
                {{ answerPagination.loadingMore ? "加载中..." : "加载更多回答" }}
              </button>
            </section>

            <div class="qa-edit-panel" v-if="canReplyToSelectedQuestion">
              <textarea class="textarea" v-model="answerForm.content_md" placeholder="写下回答"></textarea>
              <button class="btn btn-accent" type="button" @click="createAnswer">提交回答</button>
            </div>

            <p v-else-if="isSelectedDemoQuestion" class="meta">演示问题只用于本地验收，不会提交回答到后端。</p>
            <p v-else-if="selectedQuestion?.status === 'hidden'" class="meta">该问题已删除，不再接受新回答。</p>
            <p v-else-if="selectedQuestion?.status === 'closed'" class="meta">该问题已关闭，暂不接受新回答。</p>
            <p v-else class="meta">登录后可回答。</p>
          </section>
        </article>

        <button v-if="questionPagination.next && !usingDemoQuestions" class="btn qa-more" type="button" @click="loadMoreQuestions">
          {{ questionPagination.loadingMore ? "加载中..." : "加载更多问题" }}
        </button>

        <div v-if="!displayQuestions.length" class="qa-empty card">
          <strong>{{ emptyStateTitle }}</strong>
          <p class="meta">{{ emptyStateDescription }}</p>
        </div>
      </section>
    </main>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";

import { DEMO_QA_QUESTIONS } from "../content/demoContent";
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
const showAskPanel = ref(false);
const askPanelRef = ref(null);
const questionTitleInput = ref(null);
const answerPreviewMap = reactive({});
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

const scopeOptions = [
  { value: "all", label: "全部问题", hint: "公开讨论流", authOnly: false },
  { value: "mine", label: "我的提问", hint: "我发起的问题", authOnly: true },
  { value: "answered", label: "我的回答", hint: "我参与过的讨论", authOnly: true },
  { value: "deleted", label: "已删除问题", hint: "仅查看已隐藏问题", authOnly: true },
];

const statusOptions = [
  { value: "", label: "全部" },
  { value: "open", label: "开放" },
  { value: "closed", label: "已关闭" },
  { value: "pending", label: "审核中" },
];

const orderOptions = [
  { value: "latest", label: "最新活跃" },
  { value: "answers", label: "最多回答" },
  { value: "created_newest", label: "最新发布" },
];

const usingDemoQuestions = computed(
  () =>
    Boolean(import.meta.env.DEV) &&
    !questions.value.length &&
    filters.scope === "all" &&
    !filters.search.trim() &&
    !filters.status
);

const displayQuestions = computed(() => {
  if (questions.value.length) {
    return [...questions.value];
  }
  if (!usingDemoQuestions.value) {
    return [];
  }
  return sortQuestionList([...DEMO_QA_QUESTIONS]);
});

const isSelectedDemoQuestion = computed(() => Boolean(selectedQuestion.value?.__demo));
const currentAnswers = computed(() => (isSelectedDemoQuestion.value ? selectedQuestion.value?.demo_answers || [] : answers.value));
const canReplyToSelectedQuestion = computed(
  () => auth.isAuthenticated && !isSelectedDemoQuestion.value && selectedQuestion.value?.status === "open"
);

const canToggleStatus = computed(() => {
  if (!selectedQuestion.value || !auth.user || isSelectedDemoQuestion.value) return false;
  return auth.isManager || selectedQuestion.value.author.id === auth.user.id;
});
const canAcceptAnswer = computed(
  () => !isSelectedDemoQuestion.value && canToggleStatus.value && ["open", "closed"].includes(selectedQuestion.value?.status || "")
);
const canApproveQuestion = computed(
  () => !isSelectedDemoQuestion.value && auth.isManager && selectedQuestion.value?.status === "pending"
);
const canRestoreQuestion = computed(() => {
  if (!selectedQuestion.value || !auth.user || isSelectedDemoQuestion.value) return false;
  if (selectedQuestion.value.status !== "hidden") return false;
  return auth.isManager || selectedQuestion.value.author.id === auth.user.id;
});
const canEditQuestion = computed(() => {
  if (!selectedQuestion.value || !auth.user || isSelectedDemoQuestion.value) return false;
  return auth.isManager || selectedQuestion.value.author.id === auth.user.id;
});

const boardTitle = computed(() => {
  if (filters.scope === "mine") return "我的提问";
  if (filters.scope === "answered") return "我参与的讨论";
  if (filters.scope === "deleted") return "已删除问题";
  return "最新讨论";
});

const boardDescription = computed(() => {
  if (usingDemoQuestions.value) {
    return "当前没有真实问答数据，页面已自动填充演示讨论串，方便你直接验收布局和主题。";
  }
  if (filters.scope === "mine") {
    return "这里展示你自己发起的问题，以及它们当前的审核和讨论状态。";
  }
  if (filters.scope === "answered") {
    return "这里聚合了你回答过的问题，方便继续追踪后续讨论。";
  }
  if (filters.scope === "deleted") {
    return "这里单独存放你最近 30 条已删除的问题，不再混入主讨论流，可按需恢复。";
  }
  return "按讨论流浏览最新问题，列表会优先突出状态、标签、回答数和摘要。";
});

const scopeSummary = computed(() => {
  if (usingDemoQuestions.value) {
    return `正在显示 ${displayQuestions.value.length} 条演示问题，用于本地验收。`;
  }
  if (filters.scope === "deleted") {
    return `当前最多展示最近 30 条已删除问题，现有 ${questionPagination.count || displayQuestions.value.length} 条结果。`;
  }
  return `共 ${questionPagination.count || displayQuestions.value.length} 条结果，当前模式：${boardTitle.value}。`;
});

const emptyStateTitle = computed(() => (filters.scope === "deleted" ? "暂无已删除问题" : "暂无讨论"));
const emptyStateDescription = computed(() => {
  if (filters.scope === "deleted") {
    return "删除后的问题会单独归档到这里，仅保留最近 30 条，并支持恢复。";
  }
  return "你可以先切换筛选条件，或者发布第一条问题。";
});

function isDemoQuestion(item) {
  return Boolean(item?.__demo);
}

async function toggleAskPanel() {
  if (!auth.isAuthenticated) {
    ui.info("请先登录后再提问。");
    return;
  }
  const nextState = !showAskPanel.value;
  showAskPanel.value = nextState;
  if (!nextState) return;

  await nextTick();
  askPanelRef.value?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  questionTitleInput.value?.focus?.();
}

function canDeleteAnswer(answer) {
  if (!auth.user || answer?.__demo) return false;
  return auth.isManager || answer.author.id === auth.user.id;
}

function canEditAnswer(answer) {
  if (!auth.user || answer?.__demo) return false;
  return auth.isManager || answer.author.id === auth.user.id;
}

function stripMarkdown(value) {
  return String(value || "")
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "[图片]")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^>\s?/gm, "")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/^\s*\d+\.\s+/gm, "")
    .replace(/\|/g, " ")
    .replace(/\r?\n+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function buildExcerpt(value, limit = 118) {
  const text = stripMarkdown(value);
  if (!text) return "展开后查看完整内容。";
  return text.length > limit ? `${text.slice(0, limit)}...` : text;
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function formatQuestionStatus(status) {
  const map = {
    pending: "审核中",
    open: "开放",
    closed: "已关闭",
    hidden: "已隐藏",
  };
  return map[status] || status || "-";
}

function formatAnswerStatus(status) {
  const map = {
    pending: "审核中",
    visible: "已展示",
    hidden: "已隐藏",
  };
  return map[status] || status || "-";
}

function getQuestionPreview(item) {
  if (isDemoQuestion(item)) {
    const bestAnswer = [...(item.demo_answers || [])].sort((a, b) => Number(b.is_accepted) - Number(a.is_accepted))[0];
    if (bestAnswer) {
      return {
        text: buildExcerpt(bestAnswer.content_md),
        isAccepted: Boolean(bestAnswer.is_accepted),
        sourceLabel: bestAnswer.is_accepted ? "最佳回答摘要" : "讨论摘录",
      };
    }
    return {
      text: buildExcerpt(item.content_md),
      isAccepted: false,
      sourceLabel: "问题概览",
    };
  }
  const cached = answerPreviewMap[item.id];
  if (cached) return cached;
  return {
    text: buildExcerpt(item.content_md),
    isAccepted: false,
    sourceLabel: "问题概览",
  };
}

function compareDate(valueA, valueB) {
  return new Date(valueA || 0).getTime() - new Date(valueB || 0).getTime();
}

function sortQuestionList(items) {
  const sorted = [...items];
  if (filters.order === "answers") {
    return sorted.sort((a, b) => Number(b.answers_count || 0) - Number(a.answers_count || 0) || compareDate(b.updated_at, a.updated_at));
  }
  if (filters.order === "created_newest") {
    return sorted.sort((a, b) => compareDate(b.created_at, a.created_at));
  }
  if (filters.order === "created_oldest") {
    return sorted.sort((a, b) => compareDate(a.created_at, b.created_at));
  }
  if (filters.order === "oldest") {
    return sorted.sort((a, b) => compareDate(a.updated_at, b.updated_at));
  }
  return sorted.sort((a, b) => compareDate(b.updated_at, a.updated_at));
}

function matchesQuestionFilters(item) {
  if (!item) return false;
  if (filters.scope === "deleted") {
    if (item.status !== "hidden") return false;
  } else if (item.status === "hidden") {
    return false;
  }
  if (filters.status && item.status !== filters.status) return false;
  const keyword = filters.search.trim().toLowerCase();
  if (keyword) {
    const haystack = `${item.title || ""}\n${item.content_md || ""}\n${item.category_name || ""}`.toLowerCase();
    if (!haystack.includes(keyword)) return false;
  }
  return true;
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
  questionForm.title = "";
  questionForm.content_md = "";
  if (showMessage) ui.info("已清空问题草稿");
}

function persistAnswerDraft() {
  if (!auth.isAuthenticated || !selectedQuestion.value || isSelectedDemoQuestion.value) return;
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
  if (!auth.isAuthenticated || !selectedQuestion.value || isSelectedDemoQuestion.value) return;
  const payload = safeParseDraft(localStorage.getItem(getAnswerDraftKey(selectedQuestion.value.id)));
  answerForm.content_md = payload?.content_md || "";
  if (payload && showMessage) ui.info("已恢复回答草稿");
}

function clearAnswerDraft(showMessage = true) {
  if (!selectedQuestion.value || isSelectedDemoQuestion.value) return;
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
  if ((filters.scope === "mine" || filters.scope === "deleted") && auth.isAuthenticated) params.mine = 1;
  if (filters.search.trim()) params.search = filters.search.trim();
  if (filters.scope === "deleted") {
    params.status = "hidden";
  } else if (filters.status) {
    params.status = filters.status;
  }
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

function clearQuestionSelection() {
  selectedQuestion.value = null;
  answers.value = [];
  answerPagination.count = 0;
  answerPagination.next = "";
  cancelEditQuestion();
  cancelEditAnswer();
}

async function loadAnswerPreview(item) {
  if (!item?.id || answerPreviewMap[item.id]) return;
  try {
    const { data } = await api.get("/answers/", {
      params: {
        question: item.id,
        page: 1,
        order: "accepted_first",
      },
    });
    const list = Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
    const best = list[0];
    if (best) {
      answerPreviewMap[item.id] = {
        text: buildExcerpt(best.content_md),
        isAccepted: Boolean(best.is_accepted),
        sourceLabel: best.is_accepted ? "最佳回答摘要" : "最新回答摘要",
      };
      return;
    }
  } catch {
    // Keep cards usable when preview requests fail.
  }
  answerPreviewMap[item.id] = {
    text: buildExcerpt(item.content_md),
    isAccepted: false,
    sourceLabel: "问题概览",
  };
}

async function primeAnswerPreviews(items) {
  const targets = items.filter((item) => item && !item.__demo).slice(0, 8);
  await Promise.all(targets.map((item) => loadAnswerPreview(item)));
}

function mergeQuestions(existing, incoming) {
  const map = new Map(existing.map((item) => [String(item.id), item]));
  incoming.forEach((item) => {
    map.set(String(item.id), item);
  });
  return sortQuestionList([...map.values()]);
}

async function loadAnsweredQuestions(page = 1, append = false) {
  if (!auth.isAuthenticated) {
    questions.value = [];
    questionPagination.count = 0;
    questionPagination.next = "";
    clearQuestionSelection();
    return;
  }

  const safePage = normalizePageValue(page, 1);
  try {
    const { data } = await api.get("/answers/mine/", {
      params: { page: safePage, order: "latest" },
    });
    const answerItems = Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
    const previewMap = new Map();
    answerItems.forEach((item) => {
      if (!previewMap.has(item.question)) {
        previewMap.set(item.question, item);
      }
    });

    const details = await Promise.all(
      [...previewMap.keys()].map(async (questionId) => {
        try {
          const response = await api.get(`/questions/${questionId}/`);
          return response.data;
        } catch {
          return null;
        }
      })
    );

    const items = details
      .filter(Boolean)
      .map((item) => {
        const myAnswer = previewMap.get(item.id);
        answerPreviewMap[item.id] = {
          text: buildExcerpt(myAnswer?.content_md || item.content_md),
          isAccepted: Boolean(myAnswer?.is_accepted),
          sourceLabel: myAnswer?.is_accepted ? "我的已采纳回答" : "我的回答摘要",
        };
        return item;
      })
      .filter(matchesQuestionFilters);

    questions.value = append ? mergeQuestions(questions.value, items) : sortQuestionList(items);
    questionPagination.count = Number(data?.count || questions.value.length);
    questionPagination.next = data?.next || "";

    if (!questions.value.length) {
      clearQuestionSelection();
      return;
    }

    if (append) return;

    const currentId = selectedQuestion.value?.id;
    const target = currentId ? questions.value.find((item) => String(item.id) === String(currentId)) : questions.value[0];
    if (!target) {
      await selectQuestion(questions.value[0]);
      return;
    }
    await selectQuestion(target);
  } catch (error) {
    if (safePage !== 1 && isInvalidPageError(error)) {
      return loadAnsweredQuestions(1, false);
    }
    ui.error(getErrorText(error, "已回答问题加载失败"));
  }
}

async function loadQuestions(page = 1, append = false) {
  if (filters.scope === "answered") {
    await loadAnsweredQuestions(page, append);
    return;
  }

  const safePage = normalizePageValue(page, 1);
  try {
    const { data } = await api.get("/questions/", { params: buildQuestionParams(safePage) });
    const items = Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
    questions.value = append ? mergeQuestions(questions.value, items) : sortQuestionList(items);
    questionPagination.count = Number(data?.count || questions.value.length);
    questionPagination.next = data?.next || "";

    if (!questions.value.length) {
      if (!append && usingDemoQuestions.value && displayQuestions.value.length) {
        await selectQuestion(displayQuestions.value[0]);
        return;
      }
      clearQuestionSelection();
      return;
    }

    await primeAnswerPreviews(questions.value);

    if (append) return;

    const currentId = selectedQuestion.value?.id;
    const target = currentId ? questions.value.find((item) => String(item.id) === String(currentId)) : questions.value[0];
    if (!target) {
      await selectQuestion(questions.value[0]);
      return;
    }

    await selectQuestion(target);
  } catch (error) {
    if (safePage !== 1 && isInvalidPageError(error)) {
      return loadQuestions(1, false);
    }
    ui.error(getErrorText(error, "问题列表加载失败"));
  }
}

async function selectQuestion(item) {
  if (!item) {
    clearQuestionSelection();
    return;
  }
  try {
    selectedQuestion.value = item;
    cancelEditQuestion();
    cancelEditAnswer();
    if (isDemoQuestion(item)) {
      answers.value = [];
      answerPagination.count = item.demo_answers?.length || 0;
      answerPagination.next = "";
      return;
    }
    await loadAnswers(item.id, 1, false);
  } catch (error) {
    ui.error(getErrorText(error, "回答加载失败"));
  }
}

async function toggleQuestion(item) {
  if (!item) return;
  if (selectedQuestion.value?.id === item.id) {
    clearQuestionSelection();
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
  if (!selectedQuestion.value || !answerPagination.next || answerPagination.loadingMore || isSelectedDemoQuestion.value) return;
  answerPagination.loadingMore = true;
  try {
    await loadAnswers(selectedQuestion.value.id, nextPageFromUrl(answerPagination.next), true);
  } finally {
    answerPagination.loadingMore = false;
  }
}

async function reloadAnswersOrder() {
  if (!selectedQuestion.value || isSelectedDemoQuestion.value) return;
  cancelEditAnswer();
  await loadAnswers(selectedQuestion.value.id, 1, false);
}

function switchScope(scope) {
  if (!scope || filters.scope === scope) return;
  if ((scope === "mine" || scope === "answered" || scope === "deleted") && !auth.isAuthenticated) {
    ui.info("请先登录后查看该分区。");
    return;
  }
  filters.scope = scope;
  loadQuestions(1, false);
}

function setStatusFilter(status) {
  filters.status = status;
  loadQuestions(1, false);
}

function setOrder(order) {
  filters.order = order;
  loadQuestions(1, false);
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
  if (!selectedQuestion.value || !canEditQuestion.value || isSelectedDemoQuestion.value) return;
  if (!questionEdit.title.trim() || !questionEdit.content_md.trim()) {
    ui.info("请填写问题标题和内容");
    return;
  }
  try {
    const payload = {
      title: questionEdit.title.trim(),
      content_md: questionEdit.content_md,
    };
    const { data } = await api.patch(`/questions/${selectedQuestion.value.id}/`, payload);
    ui.success(data?.status === "pending" ? "问题已更新，等待管理员重新审核" : "问题已更新");
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
  if (!canEditAnswer(answer) || isSelectedDemoQuestion.value) return;
  if (!answerEdit.content_md.trim()) {
    ui.info("回答内容不能为空");
    return;
  }
  try {
    const { data } = await api.patch(`/answers/${answer.id}/`, {
      content_md: answerEdit.content_md,
    });
    ui.success(data?.status === "pending" ? "回答已更新，等待管理员重新审核" : "回答已更新");
    cancelEditAnswer();
    await loadAnswers(selectedQuestion.value.id, 1, false);
    await primeAnswerPreviews([selectedQuestion.value]);
  } catch (error) {
    ui.error(getErrorText(error, "更新回答失败"));
  }
}

async function createQuestion() {
  if (!questionForm.title.trim() || !questionForm.content_md.trim()) {
    ui.info("请填写问题标题和内容");
    return;
  }

  try {
    const { data } = await api.post("/questions/", {
      title: questionForm.title.trim(),
      content_md: questionForm.content_md,
    });

    clearQuestionDraft(false);
    showAskPanel.value = false;
    await loadQuestions(1, false);
    const created = questions.value.find((item) => String(item.id) === String(data.id));
    if (created) {
      await selectQuestion(created);
    }
    ui.success(data?.status === "pending" ? "问题已提交，等待管理员审核" : "问题已提交");
  } catch (error) {
    ui.error(getErrorText(error, "提交问题失败"));
  }
}

async function createAnswer() {
  if (!selectedQuestion.value || !answerForm.content_md.trim() || isSelectedDemoQuestion.value) {
    ui.info("请填写回答内容");
    return;
  }

  try {
    const { data } = await api.post("/answers/", {
      question: selectedQuestion.value.id,
      content_md: answerForm.content_md,
    });
    clearAnswerDraft(false);
    cancelEditAnswer();
    await loadAnswers(selectedQuestion.value.id, 1, false);
    await loadQuestions(1, false);
    ui.success(data?.status === "pending" ? "回答已提交，等待管理员审核" : "回答已提交");
  } catch (error) {
    ui.error(getErrorText(error, "提交回答失败"));
  }
}

async function acceptAnswer(answerId) {
  if (isSelectedDemoQuestion.value) return;
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
  if (isSelectedDemoQuestion.value) return;
  try {
    await api.post(`/questions/${selectedQuestion.value.id}/close/`);
    await loadQuestions(1, false);
    ui.success("问题已关闭");
  } catch (error) {
    ui.error(getErrorText(error, "关闭问题失败"));
  }
}

async function reopenQuestion() {
  if (isSelectedDemoQuestion.value) return;
  try {
    await api.post(`/questions/${selectedQuestion.value.id}/reopen/`);
    await loadQuestions(1, false);
    ui.success("问题已重开");
  } catch (error) {
    ui.error(getErrorText(error, "重开问题失败"));
  }
}

async function approveQuestion() {
  if (!selectedQuestion.value || isSelectedDemoQuestion.value || !auth.isManager) return;
  try {
    await api.post(`/questions/${selectedQuestion.value.id}/approve/`);
    await loadQuestions(1, false);
    ui.success("问题已通过审核");
  } catch (error) {
    ui.error(getErrorText(error, "通过问题失败"));
  }
}

async function removeQuestion() {
  if (!selectedQuestion.value || isSelectedDemoQuestion.value) return;
  if (!window.confirm(`确认删除问题「${selectedQuestion.value.title}」？`)) return;
  try {
    await api.delete(`/questions/${selectedQuestion.value.id}/`);
    ui.success("问题已删除，已从当前列表移除");
    clearQuestionSelection();
    await loadQuestions(1, false);
  } catch (error) {
    ui.error(getErrorText(error, "删除问题失败"));
  }
}

async function restoreQuestion() {
  if (!selectedQuestion.value || isSelectedDemoQuestion.value || !canRestoreQuestion.value) return;
  if (!window.confirm(`确认恢复问题「${selectedQuestion.value.title}」？`)) return;
  try {
    const restoredId = selectedQuestion.value.id;
    const { data } = await api.post(`/questions/${restoredId}/restore/`);
    const restoredToPending = data?.status === "pending";
    ui.success(restoredToPending ? "问题已恢复，等待管理员审核" : "问题已恢复并重新公开");
    clearQuestionSelection();
    if (filters.scope === "deleted") {
      filters.scope = "mine";
    }
    await loadQuestions(1, false);
    const restored = questions.value.find((item) => String(item.id) === String(restoredId));
    if (restored) {
      await selectQuestion(restored);
    }
  } catch (error) {
    ui.error(getErrorText(error, "恢复问题失败"));
  }
}

async function removeAnswer(answerId) {
  if (isSelectedDemoQuestion.value) return;
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
    if (!isSelectedDemoQuestion.value) {
      restoreAnswerDraft(false);
    }
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
    if (selectedQuestion.value && !isSelectedDemoQuestion.value) restoreAnswerDraft(false);
  }
);

onMounted(async () => {
  restoreQuestionDraft(false);
  await loadQuestions();
});
</script>

<style scoped>
.qa-shell {
  display: grid;
  grid-template-columns: 290px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.qa-sidebar {
  position: sticky;
  top: 92px;
  padding: 16px;
  display: grid;
  gap: 14px;
}

.qa-primary-btn {
  width: 100%;
}

.qa-sidebar-block {
  display: grid;
  gap: 10px;
}

.qa-sidebar-label {
  margin: 0;
  color: var(--text-quiet);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.qa-sidebar-link {
  border: 1px solid var(--hairline);
  border-radius: 14px;
  background: var(--surface-soft);
  color: var(--text-strong);
  padding: 10px 12px;
  text-align: left;
  display: grid;
  gap: 3px;
  cursor: pointer;
  transition:
    transform 0.18s ease,
    border-color 0.18s ease,
    background-color 0.18s ease;
}

.qa-sidebar-link:hover:not(:disabled) {
  transform: translateY(-1px);
  border-color: color-mix(in srgb, var(--accent) 24%, transparent);
}

.qa-sidebar-link--active {
  border-color: color-mix(in srgb, var(--accent) 34%, transparent);
  background: color-mix(in srgb, var(--accent) 9%, var(--surface-strong));
}

.qa-sidebar-link:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}

.qa-sidebar-link span {
  font-size: 15px;
  font-weight: 600;
}

.qa-sidebar-link small {
  font-size: 12px;
  color: var(--text-soft);
}

.qa-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.qa-chip {
  border: 1px solid var(--hairline);
  border-radius: 999px;
  background: var(--surface-muted);
  color: var(--text);
  padding: 7px 12px;
  font-size: 13px;
  cursor: pointer;
}

.qa-chip--active {
  border-color: transparent;
  background: var(--accent-gradient);
  color: var(--accent-contrast);
}

.qa-side-meta {
  margin: 0;
  line-height: 1.6;
}

.qa-hidden-note {
  margin: 0;
  padding: 10px 12px;
  border: 1px dashed var(--hairline);
  border-radius: 12px;
  background: var(--surface-soft);
}

.qa-hidden-restore {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.qa-side-actions,
.qa-compose-actions,
.qa-detail-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.qa-compose,
.qa-edit-panel {
  border: 1px solid var(--hairline);
  border-radius: calc(var(--radius-md) - 2px);
  background: var(--surface-soft);
  padding: 14px;
  display: grid;
  gap: 10px;
}

.qa-compose :deep(.image-upload-helper),
.qa-edit-panel :deep(.image-upload-helper) {
  margin-bottom: -1px;
}

.qa-compose h3,
.qa-edit-panel h3,
.qa-question-head h3,
.qa-answer-head h3 {
  margin: 0;
  font-size: 22px;
}

.qa-login-tip {
  margin: 0;
}

.qa-main {
  display: grid;
  gap: 16px;
}

.qa-header {
  padding: 18px 20px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  align-items: center;
}

.qa-header-copy {
  min-width: 0;
}

.qa-kicker {
  margin: 0 0 6px;
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.qa-header-copy h1 {
  margin: 0;
  font-size: clamp(34px, 4.4vw, 48px);
}

.qa-header-tools {
  display: grid;
  justify-items: end;
  gap: 10px;
}

.qa-order-group {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.qa-order-btn {
  border: 1px solid var(--hairline);
  border-radius: 999px;
  background: var(--surface-soft);
  color: var(--text);
  padding: 8px 14px;
  font-size: 13px;
  cursor: pointer;
}

.qa-order-btn--active {
  border-color: color-mix(in srgb, var(--accent) 34%, transparent);
  background: color-mix(in srgb, var(--accent) 9%, var(--surface-strong));
  color: var(--accent);
}

.qa-demo-banner,
.qa-demo-inline {
  border: 1px dashed color-mix(in srgb, var(--accent) 36%, transparent);
  border-radius: calc(var(--radius-sm) + 2px);
  background: color-mix(in srgb, var(--accent) 7%, var(--surface-soft));
  color: var(--text-soft);
  padding: 10px 12px;
  font-size: 15px;
}

.qa-feed {
  display: grid;
  gap: 14px;
}

.qa-thread {
  overflow: hidden;
}

.qa-thread--active {
  border-color: color-mix(in srgb, var(--accent) 28%, transparent);
}

.qa-thread-summary {
  width: 100%;
  border: 0;
  background: transparent;
  text-align: left;
  padding: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 96px;
  gap: 12px;
  cursor: pointer;
}

.qa-thread-copy {
  padding: 14px 16px;
  min-width: 0;
  display: grid;
  gap: 8px;
}

.qa-thread-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.qa-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  padding: 4px 9px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.qa-status--open {
  background: color-mix(in srgb, var(--success) 18%, transparent);
  color: var(--success);
}

.qa-status--closed {
  background: color-mix(in srgb, var(--text-soft) 14%, transparent);
  color: var(--text-soft);
}

.qa-status--pending {
  background: var(--surface-warning);
  color: var(--surface-warning-text);
}

.qa-thread-time {
  color: var(--text-quiet);
  font-size: 12px;
}

.qa-thread-copy h2 {
  margin: 0;
  font-size: clamp(18px, 1.6vw, 24px);
  line-height: 1.28;
}

.qa-thread-preview {
  margin: 0;
  color: var(--text-soft);
  font-size: 14px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.qa-tag-row,
.qa-thread-meta,
.answer-item-flags {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.qa-tag {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 5px 10px;
  background: var(--surface-chip);
  color: var(--text-soft);
  font-size: 12px;
  font-weight: 600;
}

.qa-thread-meta {
  color: var(--text-quiet);
  font-size: 12px;
}

.qa-thread-side {
  border-left: 1px solid var(--hairline);
  background: color-mix(in srgb, var(--accent) 6%, var(--surface-strong));
  display: grid;
  align-content: center;
  justify-items: center;
  gap: 4px;
  padding: 14px 10px;
}

.qa-thread-side strong {
  font-size: 24px;
  line-height: 1;
}

.qa-thread-side span {
  color: var(--text-quiet);
  font-size: 11px;
}

.qa-thread-badge {
  margin-top: 4px;
  border-radius: 999px;
  padding: 3px 8px;
  background: var(--pill-bg);
  color: var(--pill-text);
  font-size: 11px;
  font-weight: 700;
}

.qa-thread-detail {
  border-top: 1px solid var(--hairline);
  padding: 16px 20px 20px;
  display: grid;
  gap: 14px;
}

.qa-question-panel,
.qa-answer-panel {
  display: grid;
  gap: 12px;
}

.qa-question-head,
.qa-answer-head,
.answer-item-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.qa-question-markdown {
  border: 1px solid var(--hairline);
  border-radius: calc(var(--radius-sm) + 2px);
  background: var(--surface-soft);
  padding: 14px;
}

.qa-answer-order {
  width: 180px;
}

.answer-item {
  border: 1px solid var(--hairline);
  border-radius: calc(var(--radius-sm) + 2px);
  background: var(--surface-soft);
  padding: 14px;
  display: grid;
  gap: 10px;
}

.qa-more {
  justify-self: start;
}

.qa-empty {
  padding: 20px;
  display: grid;
  gap: 6px;
}

.qa-empty strong {
  font-size: 22px;
}

:global(html[data-theme="academic"]) .qa-sidebar-link,
:global(html[data-theme="academic"]) .qa-compose,
:global(html[data-theme="academic"]) .qa-edit-panel,
:global(html[data-theme="academic"]) .qa-thread-side,
:global(html[data-theme="academic"]) .qa-question-markdown,
:global(html[data-theme="academic"]) .answer-item {
  background: var(--surface-strong);
}

:global(html[data-theme="academic"]) .qa-thread-copy h2,
:global(html[data-theme="academic"]) .qa-header-copy h1,
:global(html[data-theme="academic"]) .qa-compose h3,
:global(html[data-theme="academic"]) .qa-edit-panel h3,
:global(html[data-theme="academic"]) .qa-question-head h3,
:global(html[data-theme="academic"]) .qa-answer-head h3 {
  font-family: var(--font-reading);
}

:global(html[data-theme="geek"]) .qa-sidebar,
:global(html[data-theme="geek"]) .qa-sidebar-link,
:global(html[data-theme="geek"]) .qa-compose,
:global(html[data-theme="geek"]) .qa-edit-panel,
:global(html[data-theme="geek"]) .qa-header,
:global(html[data-theme="geek"]) .qa-thread,
:global(html[data-theme="geek"]) .qa-question-markdown,
:global(html[data-theme="geek"]) .answer-item,
:global(html[data-theme="geek"]) .qa-demo-banner,
:global(html[data-theme="geek"]) .qa-demo-inline {
  border-width: 2px;
}

:global(html[data-theme="geek"]) .qa-sidebar-label,
:global(html[data-theme="geek"]) .qa-kicker,
:global(html[data-theme="geek"]) .qa-thread-copy h2,
:global(html[data-theme="geek"]) .qa-header-copy h1 {
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

@media (max-width: 1080px) {
  .qa-shell {
    grid-template-columns: 1fr;
  }

  .qa-sidebar {
    position: static;
  }

  .qa-header {
    grid-template-columns: 1fr;
  }

  .qa-header-tools {
    justify-items: start;
  }

  .qa-order-group {
    justify-content: flex-start;
  }
}

@media (max-width: 760px) {
  .qa-thread-summary {
    grid-template-columns: 1fr;
  }

  .qa-thread-side {
    border-left: 0;
    border-top: 1px solid var(--hairline);
    grid-auto-flow: column;
    justify-content: start;
    justify-items: start;
    gap: 10px;
  }

  .qa-thread-detail,
  .qa-thread-copy {
    padding-left: 14px;
    padding-right: 14px;
  }

  .qa-question-head,
  .qa-answer-head,
  .answer-item-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .qa-answer-order {
    width: 100%;
  }
}

@media (max-width: 560px) {
  .qa-sidebar,
  .qa-header {
    padding: 14px;
  }

  .qa-thread-copy h2 {
    font-size: 20px;
  }

  .qa-thread-preview {
    font-size: 14px;
  }

  .qa-thread-side strong {
    font-size: 24px;
  }
}
.qa-shell {
  gap: clamp(22px, 2.6vw, 38px);
}

.qa-sidebar,
.qa-header,
.qa-thread {
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  backdrop-filter: none;
}

.qa-sidebar {
  padding: 4px 20px 0 0;
  border-right: 1px solid color-mix(in srgb, var(--hairline) 82%, transparent);
}

.qa-sidebar-link {
  border: 0;
  border-left: 2px solid transparent;
  border-radius: 0;
  background: transparent;
  padding: 10px 0 10px 12px;
}

.qa-sidebar-link:hover:not(:disabled) {
  transform: none;
}

.qa-sidebar-link--active {
  border-left-color: var(--accent);
  background: color-mix(in srgb, var(--accent) 8%, transparent);
}

.qa-chip,
.qa-order-btn {
  background: transparent;
  box-shadow: none;
}

.qa-compose,
.qa-edit-panel {
  border: 0;
  border-top: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
  border-radius: 0;
  background: transparent;
  padding: 18px 0;
}

.qa-header {
  padding: 0 0 16px;
  border-bottom: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
}

.qa-thread {
  border-top: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
}

.qa-thread-summary {
  grid-template-columns: minmax(0, 1fr) 88px;
}

.qa-thread-copy {
  padding: 14px 0;
}

.qa-thread-side {
  border-left: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
  padding-left: 12px;
}

.qa-thread-detail {
  padding: 0 0 18px;
}

.qa-question-panel,
.qa-answer-panel {
  border: 0;
  border-top: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
  border-radius: 0;
  background: transparent;
  padding: 18px 0 0;
}

.answer-item {
  border: 0;
  border-top: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
  border-radius: 0;
  background: transparent;
  padding: 16px 0;
}

@media (max-width: 760px) {
  .qa-sidebar {
    border-right: 0;
    padding-right: 0;
  }

  .qa-thread-copy,
  .qa-thread-detail {
    padding-left: 12px;
    padding-right: 12px;
  }

  .qa-thread-side {
    padding-left: 0;
    padding-top: 12px;
  }
}

@media (max-width: 560px) {
  .qa-sidebar,
  .qa-header {
    padding: 14px 0;
  }
}
</style>
