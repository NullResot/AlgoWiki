<template>
  <section class="review-layout">
    <header class="review-card review-shell-head">
      <div>
        <p class="review-kicker">{{ currentSectionConfig.label }}</p>
        <h1>审核台</h1>
        <p class="meta">{{ currentSectionConfig.description }}</p>
      </div>
      <button class="btn" type="button" @click="reloadCurrentSection">刷新当前分区</button>
    </header>

    <nav class="review-tabs" aria-label="审核分区">
      <RouterLink
        v-for="item in reviewSections"
        :key="item.key"
        :to="buildReviewRoute(item.key)"
        class="review-tab"
        :class="{ 'review-tab--active': item.key === currentSection }"
      >
        <div class="review-tab-head">
          <strong>{{ item.label }}</strong>
          <span class="review-tab-count">{{ formatCount(counts[item.key]) }}</span>
        </div>
        <span>{{ item.description }}</span>
      </RouterLink>
    </nav>

    <article v-if="currentSection === 'revisions'" class="review-card full">
      <h2>内容修订审核</h2>
      <p class="meta">待审核 {{ counts.revisions }} 条</p>
      <div class="toolbar">
        <label class="check-line"><input type="checkbox" :checked="allPendingRevisionsChecked" @change="toggleSelectAllRevisions($event.target.checked)" />全选当前结果</label>
        <input v-model="revisionFilters.search" class="input" placeholder="搜索条目标题 / 说明" @keyup.enter="loadPendingRevisions" />
        <input v-model="bulkRevisionReviewNote" class="input grow" placeholder="批量审核备注（可选）" />
        <button class="btn btn-accent" type="button" @click="bulkReviewRevisions('approve')">批量通过</button>
        <button class="btn" type="button" @click="bulkReviewRevisions('reject')">批量驳回</button>
      </div>
      <article v-for="item in pendingRevisions" :key="item.id" class="review-row">
        <div class="review-main">
          <label class="check-line"><input type="checkbox" :value="item.id" v-model="selectedPendingRevisionIds" />选择</label>
          <strong>{{ item.article_title || item.proposed_title || "未命名条目" }}</strong>
          <p class="meta">提议人：{{ item.proposer?.username || "-" }} · 提交时间：{{ formatDateTime(item.created_at) }}</p>
          <p class="meta">修订说明：{{ item.reason || "无" }}</p>
          <div class="diff-preview" v-html="item._diffPreview"></div>
        </div>
        <div class="review-actions">
          <button class="btn btn-accent" type="button" @click="openRevisionDetail(item)">进入审批页面</button>
        </div>
      </article>
      <p v-if="!pendingRevisions.length" class="meta">当前没有待审核修订。</p>
    </article>

    <article v-else-if="currentSection === 'practice'" class="review-card full">
      <h2>补题链接审核</h2>
      <p class="meta">待审核 {{ counts.practice }} 条</p>
      <article v-for="item in pendingPracticeProposals" :key="item.id" class="review-row">
        <div class="review-main">
          <strong>{{ item.proposed_short_name || item.proposed_official_name || "未命名申请" }}</strong>
          <p class="meta">申请人：{{ item.proposer?.username || "-" }} · 提交时间：{{ formatDateTime(item.created_at) }}</p>
          <p class="meta">{{ item.proposed_year || "-" }} · {{ item.proposed_series || "-" }} · {{ item.proposed_stage || "-" }}</p>
          <p v-if="item.target_entry_summary" class="meta">目标条目：{{ item.target_entry_summary }}</p>
          <pre class="proposal-preview">{{ item.practice_links_text || "-" }}</pre>
          <p class="meta">说明：{{ item.reason || "无" }}</p>
          <textarea v-model="item._reviewNote" class="textarea" placeholder="审核备注（可选）"></textarea>
        </div>
        <div class="review-actions">
          <button class="btn btn-accent" type="button" :disabled="reviewingPracticeId === item.id" @click="reviewPractice(item, 'approve')">通过</button>
          <button class="btn" type="button" :disabled="reviewingPracticeId === item.id" @click="reviewPractice(item, 'reject')">驳回</button>
        </div>
      </article>
      <p v-if="!pendingPracticeProposals.length" class="meta">当前没有待审核补题链接申请。</p>
    </article>

    <article v-else-if="currentSection === 'tickets'" class="review-card full">
      <h2>工单审核</h2>
      <p class="meta">待处理 {{ counts.tickets }} 条</p>
      <div class="toolbar">
        <select v-model="ticketFilters.kind" class="select" @change="loadPendingTickets">
          <option value="">全部类型</option><option value="issue">issue</option><option value="request">request</option>
        </select>
        <input v-model="ticketFilters.author" class="input" placeholder="提交者用户名" @keyup.enter="loadPendingTickets" />
        <input v-model="ticketFilters.search" class="input grow" placeholder="搜索标题或内容" @keyup.enter="loadPendingTickets" />
        <button class="btn" type="button" @click="loadPendingTickets">筛选</button>
        <button class="btn" type="button" @click="resetTicketFilters">重置</button>
      </div>
      <article v-for="item in pendingTickets" :key="item.id" class="review-row">
        <div class="review-main">
          <strong>{{ item.title }}</strong>
          <p class="meta">{{ item.kind }} · {{ item.author?.username || "-" }} · {{ formatDateTime(item.created_at) }}</p>
          <p class="meta">处理人：{{ item.assignee?.username ? `${item.assignee.username} (${item.assignee.role})` : "未分派" }}</p>
          <p class="ticket-content">{{ item.content }}</p>
        </div>
        <div class="review-actions">
          <select v-model="item._assignTo" class="select">
            <option value="">未分派</option>
            <option v-for="user in assigneeOptions" :key="`ticket-assignee-${item.id}-${user.id}`" :value="String(user.id)">{{ user.username }} ({{ user.role }})</option>
          </select>
          <select v-model="item._nextStatus" class="select">
            <option value="open">受理</option><option value="in_progress">处理中</option><option value="resolved">已解决</option><option value="rejected">驳回</option>
          </select>
          <textarea v-model="item._note" class="textarea" placeholder="处理备注（可选）"></textarea>
          <button class="btn btn-accent" type="button" @click="updateTicketStatus(item)">提交处理</button>
        </div>
      </article>
      <p v-if="!pendingTickets.length" class="meta">当前没有待处理工单。</p>
    </article>

    <article v-else-if="currentSection === 'comments'" class="review-card full">
      <h2>评论审核</h2>
      <p class="meta">待审核 {{ counts.comments }} 条</p>
      <div class="toolbar">
        <label class="check-line"><input type="checkbox" :checked="allPendingCommentsChecked" @change="toggleSelectAllComments($event.target.checked)" />全选当前结果</label>
        <input v-model="commentFilters.search" class="input" placeholder="搜索评论内容" @keyup.enter="loadPendingComments" />
        <input v-model="commentFilters.author" class="input" placeholder="评论用户名 / ID" @keyup.enter="loadPendingComments" />
        <input v-model="commentFilters.article" class="input" placeholder="条目 ID" @keyup.enter="loadPendingComments" />
        <input v-model="bulkCommentReviewNote" class="input grow" placeholder="批量审核备注（可选）" />
        <button class="btn btn-accent" type="button" @click="bulkReviewComments('approve')">批量通过</button>
        <button class="btn" type="button" @click="bulkReviewComments('reject')">批量驳回</button>
      </div>
      <article v-for="item in pendingComments" :key="item.id" class="review-row">
        <div class="review-main">
          <label class="check-line"><input type="checkbox" :value="item.id" v-model="selectedPendingCommentIds" />选择</label>
          <strong>评论 #{{ item.id }} · {{ item.article_title || `条目 #${item.article}` }}</strong>
          <p class="meta">评论人：{{ item.author?.username || "-" }} · 提交时间：{{ formatDateTime(item.created_at) }}</p>
          <p class="ticket-content">{{ item.content }}</p>
          <textarea v-model="item._reviewNote" class="textarea" placeholder="审核备注（可选）"></textarea>
        </div>
        <div class="review-actions">
          <button class="btn btn-accent" type="button" :disabled="reviewingCommentId === item.id" @click="reviewComment(item, 'approve')">通过</button>
          <button class="btn" type="button" :disabled="reviewingCommentId === item.id" @click="reviewComment(item, 'reject')">驳回</button>
        </div>
      </article>
      <p v-if="!pendingComments.length" class="meta">当前没有待审核评论。</p>
    </article>

    <article v-else-if="currentSection === 'tricks'" class="review-card full">
      <h2>trick 技巧审核</h2>
      <p class="meta">待审核 {{ counts.tricks }} 条</p>
      <div class="toolbar">
        <input v-model="trickFilters.search" class="input grow" placeholder="搜索标题或内容" @keyup.enter="loadPendingTricks" />
        <select v-model="trickFilters.term" class="select" @change="loadPendingTricks">
          <option value="">全部词条</option>
          <option v-for="term in trickTerms" :key="`review-trick-term-${term.id}`" :value="String(term.id)">{{ term.name }}</option>
        </select>
        <button class="btn" type="button" @click="loadPendingTricks">筛选</button>
        <button class="btn" type="button" @click="resetTrickFilters">重置</button>
      </div>
      <article v-for="item in pendingTricks" :key="item.id" class="review-row">
        <div class="review-main">
          <strong>{{ item.title || "未命名 trick" }}</strong>
          <p class="meta">提交人：{{ item.author?.username || "-" }} · 提交时间：{{ formatDateTime(item.created_at) }}</p>
          <div class="markdown trick-markdown" v-html="renderMarkdown(item.content_md || '')"></div>
        </div>
        <div class="review-actions">
          <button class="btn btn-accent" type="button" :disabled="reviewingTrickId === item.id" @click="reviewTrick(item, 'approved')">通过</button>
          <button class="btn" type="button" :disabled="reviewingTrickId === item.id" @click="reviewTrick(item, 'rejected')">驳回</button>
        </div>
      </article>
      <p v-if="!pendingTricks.length" class="meta">当前没有待审核 trick 投稿。</p>
    </article>

    <article v-else-if="currentSection === 'trick_terms'" class="review-card full">
      <h2>trick 词条候选审核</h2>
      <p class="meta">待审核 {{ counts.trick_terms }} 条</p>
      <article v-for="item in pendingTrickTermSuggestions" :key="item.id" class="review-row">
        <div class="review-main">
          <strong>{{ item.name }}</strong>
          <p class="meta">提交人：{{ item.proposer?.username || "-" }} · 提交时间：{{ formatDateTime(item.created_at) }}</p>
          <p class="meta" v-if="item.linked_tricks_count">关联 trick：{{ item.linked_tricks_count }} 条</p>
          <p class="meta" v-if="item.linked_tricks?.length">{{ item.linked_tricks.map((x) => x.title || `#${x.id}`).join('、') }}</p>
          <textarea v-model="item._reviewNote" class="textarea" placeholder="审核备注（可选）"></textarea>
        </div>
        <div class="review-actions">
          <button class="btn btn-accent" type="button" :disabled="reviewingTrickTermSuggestionId === item.id" @click="reviewTrickTermSuggestion(item, 'approved')">通过</button>
          <button class="btn" type="button" :disabled="reviewingTrickTermSuggestionId === item.id" @click="reviewTrickTermSuggestion(item, 'rejected')">驳回</button>
        </div>
      </article>
      <p v-if="!pendingTrickTermSuggestions.length" class="meta">当前没有待审核词条候选。</p>
    </article>

    <article v-else-if="currentSection === 'questions'" class="review-card full">
      <h2>问答问题审核</h2>
      <p class="meta">待审核 {{ counts.questions }} 条</p>
      <div class="toolbar">
        <label class="check-line"><input type="checkbox" :checked="allPendingQuestionsChecked" @change="toggleSelectAllQuestions($event.target.checked)" />全选当前结果</label>
        <input v-model="questionFilters.search" class="input" placeholder="按标题 / 内容搜索问题" @keyup.enter="loadPendingQuestions" />
        <input v-model="questionFilters.author" class="input" placeholder="提问用户名" @keyup.enter="loadPendingQuestions" />
        <select v-model="questionFilters.category" class="select">
          <option value="">全部分类</option>
          <option v-for="item in categories" :key="`question-category-${item.id}`" :value="String(item.id)">{{ item.name }}</option>
        </select>
        <button class="btn btn-accent" type="button" @click="bulkModerateQuestions('approve')">批量通过</button>
        <button class="btn" type="button" @click="bulkModerateQuestions('reject')">批量驳回</button>
        <button class="btn" type="button" @click="resetQuestionFilters">重置</button>
      </div>
      <article v-for="item in pendingQuestions" :key="item.id" class="review-row">
        <div class="review-main">
          <label class="check-line"><input type="checkbox" :value="item.id" v-model="selectedPendingQuestionIds" />选择</label>
          <strong>{{ item.title }}</strong>
          <p class="meta">提问者 {{ item.author?.username || "-" }} · {{ formatDateTime(item.created_at) }} · 回答 {{ item.answers_count }}<span v-if="item.category_name"> · 分类 {{ item.category_name }}</span></p>
          <p class="ticket-content">{{ item.content_md }}</p>
        </div>
        <div class="review-actions">
          <button class="btn btn-accent" type="button" @click="reviewQuestion(item, 'approve')">通过</button>
          <button class="btn" type="button" @click="reviewQuestion(item, 'reject')">驳回</button>
        </div>
      </article>
      <p v-if="!pendingQuestions.length" class="meta">当前没有待审核问题。</p>
    </article>

    <article v-else-if="currentSection === 'answers'" class="review-card full">
      <h2>问答回答审核</h2>
      <p class="meta">待审核 {{ counts.answers }} 条</p>
      <div class="toolbar">
        <label class="check-line"><input type="checkbox" :checked="allPendingAnswersChecked" @change="toggleSelectAllAnswers($event.target.checked)" />全选当前结果</label>
        <input v-model="answerFilters.search" class="input grow" placeholder="按回答内容搜索" @keyup.enter="loadPendingAnswers" />
        <input v-model="answerFilters.author" class="input" placeholder="回答用户名" @keyup.enter="loadPendingAnswers" />
        <button class="btn btn-accent" type="button" @click="bulkModerateAnswers('approve')">批量通过</button>
        <button class="btn" type="button" @click="bulkModerateAnswers('reject')">批量驳回</button>
        <button class="btn" type="button" @click="resetAnswerFilters">重置</button>
      </div>
      <article v-for="item in pendingAnswers" :key="item.id" class="review-row">
        <div class="review-main">
          <label class="check-line"><input type="checkbox" :value="item.id" v-model="selectedPendingAnswerIds" />选择</label>
          <strong>{{ item.question_title || `问题 #${item.question}` }}</strong>
          <p class="meta">回答者 {{ item.author?.username || "-" }} · {{ formatDateTime(item.created_at) }}</p>
          <p class="ticket-content">{{ item.content_md }}</p>
        </div>
        <div class="review-actions">
          <button class="btn btn-accent" type="button" @click="reviewAnswer(item, 'approve')">通过</button>
          <button class="btn" type="button" @click="reviewAnswer(item, 'reject')">驳回</button>
        </div>
      </article>
      <p v-if="!pendingAnswers.length" class="meta">当前没有待审核回答。</p>
    </article>
  </section>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { RouterLink, useRouter } from "vue-router";

import api from "../services/api";
import { renderMarkdown } from "../services/markdown";
import { renderUnifiedDiffHtml } from "../services/revisionDiff";
import { useUiStore } from "../stores/ui";

const ui = useUiStore();
const router = useRouter();

const props = defineProps({
  section: {
    type: String,
    default: "revisions",
  },
});

const reviewSections = [
  { key: "revisions", label: "内容修订", description: "审核条目修订申请。", routeName: "review" },
  { key: "practice", label: "补题链接", description: "审核补题链接新增和修改申请。", routeName: "review-practice" },
  { key: "tickets", label: "工单", description: "处理问答区与站内工单。", routeName: "review-tickets" },
  { key: "comments", label: "评论", description: "审核条目评论。", routeName: "review-comments" },
  { key: "tricks", label: "trick 技巧", description: "审核 trick 投稿。", routeName: "review-tricks" },
  { key: "trick_terms", label: "trick 词条", description: "审核词条候选。", routeName: "review-trick-terms" },
  { key: "questions", label: "问题", description: "审核问答区问题。", routeName: "review-questions" },
  { key: "answers", label: "回答", description: "审核问答区回答。", routeName: "review-answers" },
];

const reviewSectionKeys = new Set(reviewSections.map((item) => item.key));
const reviewSectionMap = new Map(reviewSections.map((item) => [item.key, item]));

const counts = reactive({
  revisions: 0,
  practice: 0,
  tickets: 0,
  comments: 0,
  tricks: 0,
  trick_terms: 0,
  questions: 0,
  answers: 0,
});

const categories = ref([]);
const assigneeOptions = ref([]);
const pendingRevisions = ref([]);
const pendingPracticeProposals = ref([]);
const pendingTickets = ref([]);
const pendingComments = ref([]);
const pendingTricks = ref([]);
const pendingTrickTermSuggestions = ref([]);
const pendingQuestions = ref([]);
const pendingAnswers = ref([]);
const trickTerms = ref([]);

const selectedPendingRevisionIds = ref([]);
const selectedPendingCommentIds = ref([]);
const selectedPendingQuestionIds = ref([]);
const selectedPendingAnswerIds = ref([]);
const bulkRevisionReviewNote = ref("");
const bulkCommentReviewNote = ref("");
const reviewingPracticeId = ref(null);
const reviewingCommentId = ref(null);
const reviewingTrickId = ref(null);
const reviewingTrickTermSuggestionId = ref(null);

const revisionFilters = reactive({ search: "" });
const ticketFilters = reactive({ kind: "", author: "", search: "" });
const commentFilters = reactive({ search: "", author: "", article: "" });
const trickFilters = reactive({ search: "", term: "" });
const questionFilters = reactive({ search: "", author: "", category: "" });
const answerFilters = reactive({ search: "", author: "" });

const currentSection = computed(() => normalizeReviewSection(props.section));
const currentSectionConfig = computed(() => reviewSectionMap.get(currentSection.value) || reviewSections[0]);

const allPendingRevisionsChecked = computed(
  () => pendingRevisions.value.length > 0 && selectedPendingRevisionIds.value.length === pendingRevisions.value.length
);
const allPendingCommentsChecked = computed(
  () => pendingComments.value.length > 0 && selectedPendingCommentIds.value.length === pendingComments.value.length
);
const allPendingQuestionsChecked = computed(
  () => pendingQuestions.value.length > 0 && selectedPendingQuestionIds.value.length === pendingQuestions.value.length
);
const allPendingAnswersChecked = computed(
  () => pendingAnswers.value.length > 0 && selectedPendingAnswerIds.value.length === pendingAnswers.value.length
);

function normalizeReviewSection(section) {
  const value = Array.isArray(section) ? section[0] : section;
  if (typeof value !== "string" || !reviewSectionKeys.has(value)) {
    return "revisions";
  }
  return value;
}

function buildReviewRoute(section) {
  const item = reviewSectionMap.get(normalizeReviewSection(section));
  return { name: item?.routeName || "review" };
}

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return error?.message || fallback;
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

function unpackListPayload(data) {
  if (Array.isArray(data)) {
    return { results: data, count: data.length, next: null };
  }
  return {
    results: Array.isArray(data?.results) ? data.results : [],
    count: Number.isFinite(data?.count) ? data.count : 0,
    next: data?.next || null,
  };
}

async function fetchCount(path, params = {}) {
  try {
    const { data } = await api.get(path, { params: { ...params, page: 1 } });
    return unpackListPayload(data).count;
  } catch {
    return 0;
  }
}

async function fetchAllPages(path, params = {}) {
  const merged = [];
  let page = 1;
  let totalCount = 0;

  while (page <= 50) {
    const { data } = await api.get(path, { params: { ...params, page } });
    const payload = unpackListPayload(data);
    totalCount = payload.count || totalCount;
    merged.push(...payload.results);
    if (!payload.next) break;
    page += 1;
  }

  return {
    results: merged,
    count: totalCount || merged.length,
  };
}

async function loadCounts() {
  const [revisions, practice, tickets, comments, tricks, trickTermsPending, questions, answers] = await Promise.all([
    fetchCount("/revisions/", { status: "pending" }),
    fetchCount("/competition-practice-proposals/", { status: "pending" }),
    fetchCount("/issues/", { status: "pending" }),
    fetchCount("/comments/", { status: "pending" }),
    fetchCount("/tricks/", { include_all: 1, status: "pending" }),
    fetchCount("/trick-term-suggestions/", { status: "pending" }),
    fetchCount("/questions/", { status: "pending" }),
    fetchCount("/answers/", { status: "pending" }),
  ]);
  counts.revisions = revisions;
  counts.practice = practice;
  counts.tickets = tickets;
  counts.comments = comments;
  counts.tricks = tricks;
  counts.trick_terms = trickTermsPending;
  counts.questions = questions;
  counts.answers = answers;
}

async function loadTrickTerms() {
  try {
    const { results } = await fetchAllPages("/trick-terms/");
    trickTerms.value = results;
  } catch (error) {
    ui.error(getErrorText(error, "trick 词条列表加载失败"));
  }
}

async function loadCategories() {
  try {
    const { data } = await api.get("/categories/", { params: { include_hidden: 1 } });
    categories.value = Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
  } catch (error) {
    ui.error(getErrorText(error, "分类列表加载失败"));
  }
}

async function loadAssigneeOptions() {
  try {
    const { data } = await api.get("/users/assignees/");
    assigneeOptions.value = Array.isArray(data) ? data : data.results || [];
  } catch (error) {
    ui.error(getErrorText(error, "处理人列表加载失败"));
  }
}

async function loadPendingRevisions() {
  try {
    const params = { status: "pending" };
    if (revisionFilters.search.trim()) params.search = revisionFilters.search.trim();
    const { results } = await fetchAllPages("/revisions/", params);
    pendingRevisions.value = results.map((item) => ({
      ...item,
      _diffPreview: renderUnifiedDiffHtml(item.article_content_md || "", item.proposed_content_md || "", { maxLines: 16 }),
    }));
    syncSelectedIds(selectedPendingRevisionIds, pendingRevisions.value);
  } catch (error) {
    ui.error(getErrorText(error, "修订列表加载失败"));
  }
}

async function loadPendingPracticeProposals() {
  try {
    const { results } = await fetchAllPages("/competition-practice-proposals/", { status: "pending" });
    pendingPracticeProposals.value = results.map((item) => ({ ...item, _reviewNote: item._reviewNote || "" }));
  } catch (error) {
    ui.error(getErrorText(error, "补题链接申请加载失败"));
  }
}

async function loadPendingTickets() {
  try {
    const params = { status: "pending" };
    if (ticketFilters.kind) params.kind = ticketFilters.kind;
    if (ticketFilters.author.trim()) params.author = ticketFilters.author.trim();
    if (ticketFilters.search.trim()) params.search = ticketFilters.search.trim();
    const { results } = await fetchAllPages("/issues/", params);
    pendingTickets.value = results.map((item) => ({
      ...item,
      _assignTo: item.assignee?.id ? String(item.assignee.id) : "",
      _nextStatus: "open",
      _note: item.resolution_note || "",
    }));
  } catch (error) {
    ui.error(getErrorText(error, "工单列表加载失败"));
  }
}

async function loadPendingComments() {
  try {
    const params = { status: "pending" };
    if (commentFilters.search.trim()) params.search = commentFilters.search.trim();
    if (commentFilters.author.trim()) params.author = commentFilters.author.trim();
    if (commentFilters.article.trim()) params.article = commentFilters.article.trim();
    const { results } = await fetchAllPages("/comments/", params);
    pendingComments.value = results.map((item) => ({ ...item, _reviewNote: item._reviewNote || "" }));
    syncSelectedIds(selectedPendingCommentIds, pendingComments.value);
  } catch (error) {
    ui.error(getErrorText(error, "评论列表加载失败"));
  }
}

async function loadPendingTricks() {
  try {
    const params = { include_all: 1, status: "pending", order: "created_newest" };
    if (trickFilters.search.trim()) params.search = trickFilters.search.trim();
    if (trickFilters.term) params.term = trickFilters.term;
    const { results } = await fetchAllPages("/tricks/", params);
    pendingTricks.value = results;
  } catch (error) {
    ui.error(getErrorText(error, "trick 列表加载失败"));
  }
}

async function loadPendingTrickTermSuggestions() {
  try {
    const { results } = await fetchAllPages("/trick-term-suggestions/", { status: "pending" });
    pendingTrickTermSuggestions.value = results.map((item) => ({
      ...item,
      _reviewNote: item._reviewNote || "",
    }));
  } catch (error) {
    ui.error(getErrorText(error, "词条候选列表加载失败"));
  }
}

async function loadPendingQuestions() {
  try {
    const params = { status: "pending", order: "created_newest" };
    if (questionFilters.search.trim()) params.search = questionFilters.search.trim();
    if (questionFilters.author.trim()) params.author = questionFilters.author.trim();
    if (questionFilters.category) params.category = questionFilters.category;
    const { results } = await fetchAllPages("/questions/", params);
    pendingQuestions.value = results;
    syncSelectedIds(selectedPendingQuestionIds, pendingQuestions.value);
  } catch (error) {
    ui.error(getErrorText(error, "问题列表加载失败"));
  }
}

async function loadPendingAnswers() {
  try {
    const params = { status: "pending", order: "latest" };
    if (answerFilters.search.trim()) params.search = answerFilters.search.trim();
    if (answerFilters.author.trim()) params.author = answerFilters.author.trim();
    const { results } = await fetchAllPages("/answers/", params);
    pendingAnswers.value = results;
    syncSelectedIds(selectedPendingAnswerIds, pendingAnswers.value);
  } catch (error) {
    ui.error(getErrorText(error, "回答列表加载失败"));
  }
}

async function ensureLoaded(section) {
  switch (section) {
    case "revisions":
      await loadPendingRevisions();
      break;
    case "practice":
      await loadPendingPracticeProposals();
      break;
    case "tickets":
      await Promise.all([loadPendingTickets(), loadAssigneeOptions()]);
      break;
    case "comments":
      await loadPendingComments();
      break;
    case "tricks":
      await Promise.all([loadPendingTricks(), trickTerms.value.length ? Promise.resolve() : loadTrickTerms()]);
      break;
    case "trick_terms":
      await loadPendingTrickTermSuggestions();
      break;
    case "questions":
      await Promise.all([loadPendingQuestions(), categories.value.length ? Promise.resolve() : loadCategories()]);
      break;
    case "answers":
      await loadPendingAnswers();
      break;
    default:
      break;
  }
}

async function reloadCurrentSection() {
  await Promise.all([loadCounts(), ensureLoaded(currentSection.value)]);
}

function syncSelectedIds(target, list) {
  const valid = new Set(list.map((item) => item.id));
  target.value = target.value.filter((id) => valid.has(id));
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatCount(value) {
  const count = Number(value || 0);
  return count > 99 ? "99+" : String(count);
}

function toggleSelectAllRevisions(checked) {
  selectedPendingRevisionIds.value = checked ? pendingRevisions.value.map((item) => item.id) : [];
}

function toggleSelectAllComments(checked) {
  selectedPendingCommentIds.value = checked ? pendingComments.value.map((item) => item.id) : [];
}

function toggleSelectAllQuestions(checked) {
  selectedPendingQuestionIds.value = checked ? pendingQuestions.value.map((item) => item.id) : [];
}

function toggleSelectAllAnswers(checked) {
  selectedPendingAnswerIds.value = checked ? pendingAnswers.value.map((item) => item.id) : [];
}

function resetTicketFilters() {
  ticketFilters.kind = "";
  ticketFilters.author = "";
  ticketFilters.search = "";
  loadPendingTickets();
}

function resetTrickFilters() {
  trickFilters.search = "";
  trickFilters.term = "";
  loadPendingTricks();
}

function resetQuestionFilters() {
  questionFilters.search = "";
  questionFilters.author = "";
  questionFilters.category = "";
  loadPendingQuestions();
}

function resetAnswerFilters() {
  answerFilters.search = "";
  answerFilters.author = "";
  loadPendingAnswers();
}

function openRevisionDetail(item) {
  router.push({ name: "review-revision", params: { id: item.id } });
}

function notifyBulkSummary(data, label) {
  const successCount = Number(data?.success || 0);
  const failedCount = Number(data?.failed || 0);
  if (successCount) ui.success(`${label}：成功 ${successCount} 条`);
  if (failedCount) ui.error(`${label}：失败 ${failedCount} 条`);
}

async function bulkReviewRevisions(action) {
  if (!selectedPendingRevisionIds.value.length) {
    ui.info("请先选择修订提议");
    return;
  }
  try {
    const { data } = await api.post("/revisions/bulk-review/", {
      ids: selectedPendingRevisionIds.value,
      action,
      review_note: bulkRevisionReviewNote.value || "",
    });
    notifyBulkSummary(data, action === "approve" ? "批量通过修订" : "批量驳回修订");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "修订审核失败"));
  }
}

async function reviewPractice(item, action) {
  reviewingPracticeId.value = item.id;
  try {
    await api.post(`/competition-practice-proposals/${item.id}/${action}/`, {
      review_note: item._reviewNote || "",
    });
    ui.success(action === "approve" ? "补题链接申请已通过" : "补题链接申请已驳回");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "补题链接审核失败"));
  } finally {
    reviewingPracticeId.value = null;
  }
}

async function updateTicketStatus(item) {
  try {
    await api.post(`/issues/${item.id}/set_status/`, {
      status: item._nextStatus,
      assign_to: item._assignTo || null,
      resolution_note: item._note || "",
    });
    ui.success("工单已处理");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "工单处理失败"));
  }
}

async function reviewComment(item, action) {
  reviewingCommentId.value = item.id;
  try {
    await api.post(`/comments/${item.id}/${action}/`, {
      review_note: item._reviewNote || "",
    });
    ui.success(action === "approve" ? "评论已通过" : "评论已驳回");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "评论审核失败"));
  } finally {
    reviewingCommentId.value = null;
  }
}

async function bulkReviewComments(action) {
  if (!selectedPendingCommentIds.value.length) {
    ui.info("请先选择评论");
    return;
  }
  try {
    const { data } = await api.post("/comments/bulk-review/", {
      ids: selectedPendingCommentIds.value,
      action,
      review_note: bulkCommentReviewNote.value || "",
    });
    notifyBulkSummary(data, action === "approve" ? "批量通过评论" : "批量驳回评论");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "评论审核失败"));
  }
}

async function reviewTrick(item, status) {
  reviewingTrickId.value = item.id;
  try {
    await api.post(`/tricks/${item.id}/set-status/`, { status });
    ui.success(status === "approved" ? "trick 已通过" : "trick 已驳回");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "trick 审核失败"));
  } finally {
    reviewingTrickId.value = null;
  }
}

async function reviewTrickTermSuggestion(item, status) {
  reviewingTrickTermSuggestionId.value = item.id;
  try {
    await api.post(`/trick-term-suggestions/${item.id}/set-status/`, {
      status,
      review_note: item._reviewNote || "",
    });
    ui.success(status === "approved" ? "词条候选已通过" : "词条候选已驳回");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "词条候选审核失败"));
  } finally {
    reviewingTrickTermSuggestionId.value = null;
  }
}

async function reviewQuestion(item, action) {
  try {
    await api.post(`/questions/${item.id}/${action}/`);
    ui.success(action === "approve" ? "问题已通过" : "问题已驳回");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "问题审核失败"));
  }
}

async function bulkModerateQuestions(action) {
  if (!selectedPendingQuestionIds.value.length) {
    ui.info("请先选择问题");
    return;
  }
  try {
    const { data } = await api.post("/questions/bulk-moderate/", {
      ids: selectedPendingQuestionIds.value,
      action,
    });
    notifyBulkSummary(data, action === "approve" ? "批量通过问题" : "批量驳回问题");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "问题审核失败"));
  }
}

async function reviewAnswer(item, action) {
  try {
    await api.post(`/answers/${item.id}/${action}/`);
    ui.success(action === "approve" ? "回答已通过" : "回答已驳回");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "回答审核失败"));
  }
}

async function bulkModerateAnswers(action) {
  if (!selectedPendingAnswerIds.value.length) {
    ui.info("请先选择回答");
    return;
  }
  try {
    const { data } = await api.post("/answers/bulk-moderate/", {
      ids: selectedPendingAnswerIds.value,
      action,
    });
    notifyBulkSummary(data, action === "approve" ? "批量通过回答" : "批量驳回答案");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "回答审核失败"));
  }
}

watch(
  () => props.section,
  async (value) => {
    const normalized = normalizeReviewSection(value);
    if (value !== normalized) {
      await router.replace(buildReviewRoute(normalized));
      return;
    }
    window.scrollTo({ top: 0, behavior: "auto" });
    await reloadCurrentSection();
  },
  { immediate: true }
);
</script>

<style scoped>
.review-layout { display: grid; gap: 16px; }
.review-card { border: 1px solid var(--hairline); border-radius: 16px; background: var(--surface); padding: 14px; box-shadow: var(--shadow-sm); }
.review-shell-head { display: flex; justify-content: space-between; gap: 16px; align-items: start; }
.review-kicker { margin: 0 0 4px; font-size: 12px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: var(--accent); }
.review-shell-head h1, .review-card h2 { margin: 0 0 8px; }
.review-tabs { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
.review-tab { border: 1px solid var(--hairline); border-radius: 14px; background: var(--surface); padding: 12px 14px; display: grid; gap: 6px; }
.review-tab--active { border-color: color-mix(in srgb, var(--accent) 42%, transparent); background: color-mix(in srgb, var(--accent) 10%, var(--surface-strong)); }
.review-tab-head { display: flex; justify-content: space-between; gap: 10px; align-items: center; }
.review-tab-count { min-width: 34px; text-align: center; padding: 2px 10px; border-radius: 999px; background: color-mix(in srgb, var(--accent) 14%, var(--surface-strong)); font-weight: 700; color: var(--text-strong); }
.toolbar, .review-actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.check-line { display: inline-flex; align-items: center; gap: 6px; }
.grow { flex: 1 1 260px; }
.review-row { display: grid; grid-template-columns: minmax(0, 1fr) 260px; gap: 12px; padding: 11px 12px; margin-top: 10px; border-radius: 10px; background: var(--surface-soft); }
.review-main { min-width: 0; }
.ticket-content { margin: 8px 0 0; white-space: pre-wrap; line-height: 1.55; }
.proposal-preview { margin: 8px 0; padding: 10px 12px; border-radius: 10px; border: 1px solid var(--hairline); background: var(--surface-strong); white-space: pre-wrap; font-family: var(--font-mono); font-size: 13px; }
.diff-preview { margin-top: 8px; max-height: 240px; overflow: auto; border-radius: 8px; border: 1px solid var(--hairline); background: var(--surface-strong); }
.trick-markdown { margin-top: 8px; }
.meta { color: var(--text-quiet); }
@media (max-width: 1100px) { .review-shell-head, .review-row { grid-template-columns: 1fr; } }
@media (max-width: 640px) { .review-tabs { grid-template-columns: 1fr; } }
</style>
