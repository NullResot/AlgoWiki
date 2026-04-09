<template>
  <section class="review-layout">
    <header class="review-card review-shell-head">
      <div>
        <p class="review-kicker">{{ currentSectionConfig.label }}</p>
        <h1>审核台</h1>
        <p class="meta">{{ currentSectionConfig.description }}</p>
      </div>
      <button class="btn" @click="reloadCurrentSection">刷新当前分区</button>
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
          <span class="review-tab-count">{{ formatCount(item.pendingCount) }}</span>
        </div>
        <span>{{ item.description }}</span>
      </RouterLink>
    </nav>

    <article v-if="currentSection === 'revisions'" class="review-card full">
      <h2>内容修改审核</h2>
      <p class="meta">待审核：{{ revisionCount }}</p>
      <div class="ticket-filters">
        <label class="meta select-all">
          <input type="checkbox" :checked="allPendingChecked" @change="toggleSelectAllPending($event.target.checked)" />
          全选待审
        </label>
        <input class="input" v-model="revisionFilters.search" placeholder="搜索条目标题/说明" @keyup.enter="loadPendingRevisions" />
        <input class="input" v-model="bulkReviewNote" placeholder="批量审核备注（可选）" />
        <button class="btn btn-accent" @click="bulkReviewRevisions('approve')">批量通过</button>
        <button class="btn" @click="bulkReviewRevisions('reject')">批量驳回</button>
      </div>
      <article class="review-row" v-for="item in pendingRevisions" :key="item.id">
        <div class="review-main">
          <label class="meta select-all">
            <input type="checkbox" :value="item.id" v-model="selectedPendingRevisionIds" />
            选择
          </label>
          <strong>{{ item.article_title || item.proposed_title || "未命名条目" }}</strong>
          <p class="meta">提议人：{{ item.proposer?.username || "-" }} · 提交时间：{{ formatDateTime(item.created_at) }}</p>
          <p class="meta">修订备注：{{ item.reason || "无" }}</p>
          <div class="diff-preview" v-html="item._diffPreview"></div>
        </div>
        <div class="review-actions">
          <button class="btn btn-accent" @click="openRevisionDetail(item)">进入审批页面</button>
        </div>
      </article>
      <p v-if="!pendingRevisions.length" class="meta">当前没有待审核的内容修改。</p>
    </article>

    <article v-else-if="currentSection === 'practice'" class="review-card full">
      <h2>补题链接审核</h2>
      <p class="meta">待审核：{{ practiceCount }}</p>
      <article class="review-row" v-for="item in pendingPracticeProposals" :key="item.id">
        <div class="review-main">
          <strong>{{ item.proposed_short_name || item.proposed_official_name || "未命名申请" }}</strong>
          <p class="meta">申请人：{{ item.proposer?.username || "-" }} · 提交时间：{{ formatDateTime(item.created_at) }}</p>
          <p class="meta">{{ item.proposed_year || "-" }} · {{ item.proposed_series || "-" }} · {{ item.proposed_stage || "-" }}</p>
          <p class="meta" v-if="item.target_entry_summary">目标条目：{{ item.target_entry_summary }}</p>
          <pre class="proposal-preview">{{ item.practice_links_text || "-" }}</pre>
          <p class="meta">说明：{{ item.reason || "无" }}</p>
          <textarea class="textarea" v-model="item._reviewNote" placeholder="审核备注（可选）"></textarea>
        </div>
        <div class="review-actions">
          <button class="btn btn-accent" :disabled="reviewingPracticeId === item.id" @click="reviewPractice(item, 'approve')">通过</button>
          <button class="btn" :disabled="reviewingPracticeId === item.id" @click="reviewPractice(item, 'reject')">驳回</button>
        </div>
      </article>
      <p v-if="!pendingPracticeProposals.length" class="meta">当前没有待审核的补题链接申请。</p>
    </article>

    <article v-else-if="currentSection === 'submissions'" class="review-card full">
      <h2>提交 Issue 与评论审核</h2>
      <p class="meta">Issue 待处理：{{ ticketCount }}<span v-if="auth.isManager"> · 评论待审核：{{ commentCount }}</span></p>

      <section class="review-block">
        <h3>提交 Issue</h3>
        <div class="ticket-filters">
          <select class="select" v-model="ticketFilters.scope" @change="loadPendingTickets">
            <option value="">全部范围</option>
            <option value="assigned">我负责的</option>
            <option value="created">我创建的</option>
          </select>
          <select class="select" v-model="ticketFilters.kind" @change="loadPendingTickets">
            <option value="">全部类型</option>
            <option value="issue">issue</option>
            <option value="request">request</option>
          </select>
          <input class="input" v-model="ticketFilters.search" placeholder="搜索标题或内容" @keyup.enter="loadPendingTickets" />
        </div>
        <article class="review-row" v-for="item in tickets" :key="item.id">
          <div class="review-main">
            <strong>{{ item.title }}</strong>
            <p class="meta">{{ item.kind }} · {{ statusText(item.status) }} · {{ item.author.username }}</p>
            <p class="meta">处理人：{{ item.assignee?.username ? `${item.assignee.username} (${item.assignee.role})` : "未分派" }}</p>
            <p class="ticket-content">{{ item.content }}</p>
          </div>
          <div class="review-actions" v-if="auth.isManager">
            <select class="select" v-model="item._assignTo">
              <option value="">未分派</option>
              <option v-for="user in assigneeOptions" :key="`review-assignee-${item.id}-${user.id}`" :value="String(user.id)">
                {{ user.username }} ({{ user.role }})
              </option>
            </select>
            <select class="select" v-model="item._nextStatus">
              <option value="open">受理</option>
              <option value="in_progress">处理中</option>
              <option value="resolved">已解决</option>
              <option value="rejected">驳回</option>
            </select>
            <textarea class="textarea" v-model="item._note" placeholder="处理备注（可选）"></textarea>
            <button class="btn btn-accent" @click="updateTicketStatus(item)">提交处理</button>
          </div>
        </article>
        <p v-if="!tickets.length" class="meta">当前没有待处理的 Issue。</p>
      </section>

      <section v-if="auth.isManager" class="review-block">
        <h3>评论审核</h3>
        <div class="ticket-filters">
          <label class="meta select-all">
            <input type="checkbox" :checked="allPendingCommentsChecked" @change="toggleSelectAllPendingComments($event.target.checked)" />
            全选待审评论
          </label>
          <input class="input" v-model="commentFilters.search" placeholder="搜索评论内容" @keyup.enter="loadPendingComments" />
          <input class="input" v-model="commentFilters.author" placeholder="评论用户名/ID" @keyup.enter="loadPendingComments" />
          <input class="input" v-model="commentFilters.article" placeholder="条目ID" @keyup.enter="loadPendingComments" />
          <input class="input" v-model="bulkCommentReviewNote" placeholder="批量审核备注（可选）" />
          <button class="btn btn-accent" @click="bulkReviewComments('approve')">批量通过</button>
          <button class="btn" @click="bulkReviewComments('reject')">批量驳回</button>
        </div>
        <article class="review-row" v-for="item in pendingComments" :key="item.id">
          <div class="review-main">
            <label class="meta select-all">
              <input type="checkbox" :value="item.id" v-model="selectedPendingCommentIds" />
              选择
            </label>
            <strong>评论 #{{ item.id }} · {{ item.article_title || `条目#${item.article}` }}</strong>
            <p class="meta">评论人：{{ item.author?.username || "-" }} · 提交时间：{{ formatDateTime(item.created_at) }}</p>
            <p class="ticket-content">{{ item.content }}</p>
            <textarea class="textarea" v-model="item._reviewNote" placeholder="审核备注（可选）"></textarea>
          </div>
          <div class="review-actions">
            <button class="btn btn-accent" :disabled="reviewingCommentId === item.id" @click="reviewComment(item, 'approve')">通过</button>
            <button class="btn" :disabled="reviewingCommentId === item.id" @click="reviewComment(item, 'reject')">驳回</button>
          </div>
        </article>
        <p v-if="!pendingComments.length" class="meta">当前没有待审核评论。</p>
      </section>
    </article>

    <article v-else-if="currentSection === 'tricks'" class="review-card full">
      <h2>trick技巧审核</h2>
      <p class="meta">待审核：{{ trickCount }}</p>
      <div class="ticket-filters">
        <input class="input" v-model="trickFilters.search" placeholder="搜索标题或内容" @keyup.enter="loadPendingTricks" />
      </div>
      <article class="review-row" v-for="item in pendingTricks" :key="item.id">
        <div class="review-main">
          <strong>{{ item.title || "未命名 trick" }}</strong>
          <p class="meta">提交人：{{ item.author?.username || "-" }} · 提交时间：{{ formatDateTime(item.created_at) }}</p>
          <div class="markdown trick-markdown" v-html="renderMarkdown(item.content_md || '')"></div>
        </div>
        <div class="review-actions">
          <button class="btn btn-accent" :disabled="reviewingTrickId === item.id" @click="reviewTrick(item, 'approved')">通过</button>
          <button class="btn" :disabled="reviewingTrickId === item.id" @click="reviewTrick(item, 'rejected')">驳回</button>
        </div>
      </article>
      <p v-if="!pendingTricks.length" class="meta">当前没有待审核的 trick 投稿。</p>
    </article>
  </section>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { RouterLink, useRouter } from "vue-router";

import api from "../services/api";
import { renderMarkdown } from "../services/markdown";
import { renderUnifiedDiffHtml } from "../services/revisionDiff";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const auth = useAuthStore();
const ui = useUiStore();
const router = useRouter();
const props = defineProps({ section: { type: String, default: "revisions" } });

const SECTION_CONFIG = {
  revisions: { label: "内容修改", description: "优先处理条目修订申请。", routeName: "review" },
  practice: { label: "补题链接", description: "处理补题链接新增和修改申请。", routeName: "review-practice" },
  submissions: { label: "Issue 与评论", description: "集中处理用户提交的 Issue 与评论。", routeName: "review-submissions" },
  tricks: { label: "trick技巧", description: "审核 trick 投稿，决定是否公开。", routeName: "review-tricks" },
};
const MANAGER_KEYS = ["revisions", "practice", "submissions", "tricks"];
const BASIC_KEYS = ["revisions", "submissions"];

const counts = reactive({ revisions: 0, practice: 0, submissions: 0, tickets: 0, comments: 0, tricks: 0 });
const pendingRevisions = ref([]);
const pendingPracticeProposals = ref([]);
const tickets = ref([]);
const pendingComments = ref([]);
const pendingTricks = ref([]);
const assigneeOptions = ref([]);

const selectedPendingRevisionIds = ref([]);
const selectedPendingCommentIds = ref([]);
const bulkReviewNote = ref("");
const bulkCommentReviewNote = ref("");
const reviewingPracticeId = ref(null);
const reviewingCommentId = ref(null);
const reviewingTrickId = ref(null);

const revisionFilters = reactive({ search: "" });
const ticketFilters = reactive({ scope: "", kind: "", search: "" });
const commentFilters = reactive({ search: "", author: "", article: "" });
const trickFilters = reactive({ search: "" });

const reviewSections = computed(() =>
  (auth.isManager ? MANAGER_KEYS : BASIC_KEYS).map((key) => ({
    key,
    ...SECTION_CONFIG[key],
    pendingCount: counts[key],
  }))
);
const currentSection = computed(() => normalizeReviewSection(props.section));
const currentSectionConfig = computed(() => SECTION_CONFIG[currentSection.value]);

const revisionCount = computed(() => counts.revisions);
const practiceCount = computed(() => counts.practice);
const ticketCount = computed(() => counts.tickets);
const commentCount = computed(() => counts.comments);
const trickCount = computed(() => counts.tricks);
const allPendingChecked = computed(() => pendingRevisions.value.length > 0 && pendingRevisions.value.length === selectedPendingRevisionIds.value.length);
const allPendingCommentsChecked = computed(() => pendingComments.value.length > 0 && pendingComments.value.length === selectedPendingCommentIds.value.length);

function normalizeReviewSection(section) {
  if (auth.isManager) {
    if (section === "tickets" || section === "comments") return "submissions";
    return MANAGER_KEYS.includes(section) ? section : "revisions";
  }
  if (section === "tickets" || section === "comments") return "submissions";
  return BASIC_KEYS.includes(section) ? section : "revisions";
}

function buildReviewRoute(section) {
  const key = normalizeReviewSection(section);
  return { name: SECTION_CONFIG[key].routeName };
}

function formatCount(value) {
  const count = Number(value || 0);
  return count > 99 ? "99+" : String(count);
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function statusText(status) {
  return {
    pending: "审核中",
    approved: "通过",
    rejected: "驳回",
    open: "待处理",
    in_progress: "处理中",
    resolved: "已解决",
  }[status] || status || "-";
}

function getErrorText(error, fallback = "操作失败") {
  return error?.response?.data?.detail || error?.message || fallback;
}

function unpackListPayload(data) {
  if (Array.isArray(data)) return { results: data, count: data.length };
  return {
    results: Array.isArray(data?.results) ? data.results : [],
    count: Number.isFinite(data?.count) ? data.count : 0,
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

async function loadCounts() {
  const [revisions, practice, ticketsCount, comments, tricks] = await Promise.all([
    fetchCount("/revisions/", { status: "pending" }),
    auth.isManager ? fetchCount("/competition-practice-proposals/", { status: "pending" }) : Promise.resolve(0),
    fetchCount("/issues/", auth.isManager ? { status: "pending" } : { status: "pending", scope: "assigned" }),
    auth.isManager ? fetchCount("/comments/", { status: "pending" }) : Promise.resolve(0),
    auth.isManager ? fetchCount("/tricks/", { include_all: 1, status: "pending" }) : Promise.resolve(0),
  ]);
  counts.revisions = revisions;
  counts.practice = practice;
  counts.tickets = ticketsCount;
  counts.comments = comments;
  counts.submissions = ticketsCount + comments;
  counts.tricks = tricks;
}

async function loadPendingRevisions() {
  const params = { page: 1, status: "pending" };
  if (revisionFilters.search.trim()) params.search = revisionFilters.search.trim();
  const { data } = await api.get("/revisions/", { params });
  pendingRevisions.value = unpackListPayload(data).results.map((item) => ({
    ...item,
    _diffPreview: renderUnifiedDiffHtml(item.article_content_md || "", item.proposed_content_md || "", { maxLines: 16 }),
  }));
  selectedPendingRevisionIds.value = selectedPendingRevisionIds.value.filter((id) => pendingRevisions.value.some((item) => item.id === id));
}

async function loadPendingPracticeProposals() {
  if (!auth.isManager) return;
  const { data } = await api.get("/competition-practice-proposals/", { params: { page: 1, status: "pending" } });
  pendingPracticeProposals.value = unpackListPayload(data).results.map((item) => ({ ...item, _reviewNote: item._reviewNote || "" }));
}

async function loadPendingTickets() {
  const params = { page: 1, status: "pending" };
  if (ticketFilters.scope) params.scope = ticketFilters.scope;
  if (!auth.isManager && auth.role === "school" && !params.scope) params.scope = "assigned";
  if (ticketFilters.kind) params.kind = ticketFilters.kind;
  if (ticketFilters.search.trim()) params.search = ticketFilters.search.trim();
  const { data } = await api.get("/issues/", { params });
  tickets.value = unpackListPayload(data).results.map((item) => ({
    ...item,
    _assignTo: item.assignee?.id ? String(item.assignee.id) : "",
    _nextStatus: "open",
    _note: item.resolution_note || "",
  }));
}

async function loadPendingComments() {
  if (!auth.isManager) return;
  const params = { page: 1, status: "pending" };
  if (commentFilters.search.trim()) params.search = commentFilters.search.trim();
  if (commentFilters.author.trim()) params.author = commentFilters.author.trim();
  if (commentFilters.article.trim()) params.article = commentFilters.article.trim();
  const { data } = await api.get("/comments/", { params });
  pendingComments.value = unpackListPayload(data).results.map((item) => ({ ...item, _reviewNote: item._reviewNote || "" }));
  selectedPendingCommentIds.value = selectedPendingCommentIds.value.filter((id) => pendingComments.value.some((item) => item.id === id));
}

async function loadPendingTricks() {
  if (!auth.isManager) return;
  const params = { page: 1, include_all: 1, status: "pending", order: "created_newest" };
  if (trickFilters.search.trim()) params.search = trickFilters.search.trim();
  const { data } = await api.get("/tricks/", { params });
  pendingTricks.value = unpackListPayload(data).results;
}

async function loadAssigneeOptions() {
  if (!auth.isManager) return;
  const { data } = await api.get("/users/assignees/");
  assigneeOptions.value = Array.isArray(data) ? data : data.results || [];
}

async function ensureLoaded(section) {
  if (section === "revisions") return loadPendingRevisions();
  if (section === "practice") return loadPendingPracticeProposals();
  if (section === "submissions") {
    return Promise.all([loadPendingTickets(), auth.isManager ? loadPendingComments() : Promise.resolve(), loadAssigneeOptions()]);
  }
  if (section === "tricks") return loadPendingTricks();
}

async function reloadCurrentSection() {
  await Promise.all([loadCounts(), ensureLoaded(currentSection.value)]);
}

function toggleSelectAllPending(checked) {
  selectedPendingRevisionIds.value = checked ? pendingRevisions.value.map((item) => item.id) : [];
}

function toggleSelectAllPendingComments(checked) {
  selectedPendingCommentIds.value = checked ? pendingComments.value.map((item) => item.id) : [];
}

function openRevisionDetail(item) {
  router.push({ name: "review-revision", params: { id: item.id } });
}

function notifyBulkSummary(data, label) {
  const success = Number(data?.success || 0);
  const failed = Number(data?.failed || 0);
  if (success) ui.success(`${label}：成功 ${success} 条`);
  if (failed) ui.error(`${label}：失败 ${failed} 条`);
}

async function bulkReviewRevisions(action) {
  if (!selectedPendingRevisionIds.value.length) return ui.info("请先选择修订提议");
  try {
    const { data } = await api.post("/revisions/bulk-review/", {
      ids: selectedPendingRevisionIds.value,
      action,
      review_note: bulkReviewNote.value || "",
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
    await api.post(`/competition-practice-proposals/${item.id}/${action}/`, { review_note: item._reviewNote || "" });
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
    ui.success("Issue 已处理");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "Issue 处理失败"));
  }
}

async function reviewComment(item, action) {
  reviewingCommentId.value = item.id;
  try {
    await api.post(`/comments/${item.id}/${action}/`, { review_note: item._reviewNote || "" });
    ui.success(action === "approve" ? "评论已通过" : "评论已驳回");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "评论审核失败"));
  } finally {
    reviewingCommentId.value = null;
  }
}

async function bulkReviewComments(action) {
  if (!selectedPendingCommentIds.value.length) return ui.info("请先选择评论");
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

watch(
  () => props.section,
  async (value) => {
    const normalized = normalizeReviewSection(value);
    if (value !== normalized) {
      await router.replace(buildReviewRoute(normalized));
      return;
    }
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
.review-block { margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--hairline); }
.review-block:first-of-type { margin-top: 0; padding-top: 0; border-top: 0; }
.ticket-filters { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; }
.ticket-filters .select { width: 160px; }
.ticket-filters .input { width: min(320px, 100%); }
.select-all { display: inline-flex; align-items: center; gap: 6px; }
.review-row { display: grid; grid-template-columns: minmax(0, 1fr) 240px; gap: 12px; padding: 11px 12px; margin-top: 10px; border-radius: 10px; background: var(--surface-soft); }
.review-main { min-width: 0; }
.review-actions { display: grid; gap: 8px; align-content: start; }
.ticket-content { margin: 8px 0; white-space: pre-wrap; line-height: 1.55; }
.proposal-preview { margin: 8px 0; padding: 10px 12px; border-radius: 10px; border: 1px solid var(--hairline); background: var(--surface-strong); white-space: pre-wrap; font-family: var(--font-mono); font-size: 13px; }
.diff-preview { margin-top: 8px; max-height: 240px; overflow: auto; border-radius: 8px; border: 1px solid var(--hairline); background: var(--surface-strong); }
.trick-markdown { margin-top: 8px; }
@media (max-width: 1100px) { .review-shell-head, .review-row { grid-template-columns: 1fr; } }
@media (max-width: 640px) { .review-tabs { grid-template-columns: 1fr; } .ticket-filters .select, .ticket-filters .input { width: 100%; } }
</style>
