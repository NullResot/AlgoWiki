<template>
  <section class="review-layout">
    <article class="review-card full">
      <h2>内容修改审核</h2>
      <p class="meta">学校用户可审核赛事板块，管理员可审核全部分类。</p>
      <p class="meta">待审核：{{ pendingPagination.count }}</p>

      <div class="ticket-filters">
        <label class="meta select-all">
          <input type="checkbox" :checked="allPendingChecked" @change="toggleSelectAllPending($event.target.checked)" />
          全选待审
        </label>
        <input class="input" v-model="revisionFilters.search" placeholder="搜索条目标题/说明" @keyup.enter="loadPendingRevisions()" />
        <input class="input" v-model="bulkReviewNote" placeholder="批量审核备注（可选）" />
        <button class="btn btn-accent" @click="bulkApproveRevisions">批量通过</button>
        <button class="btn" @click="bulkRejectRevisions">批量驳回</button>
        <button class="btn" @click="resetRevisionFilters">重置</button>
      </div>

      <article class="revision-row" v-for="item in pendingRevisions" :key="item.id">
        <div class="revision-main">
          <label class="meta select-all">
            <input type="checkbox" :value="item.id" v-model="selectedPendingRevisionIds" />
            选择
          </label>
          <strong>{{ item.article_title || item.proposed_title || "未命名条目" }}</strong>
          <p class="meta">
            提议人：{{ item.proposer?.username || "-" }} · 提交时间：{{ formatDateTime(item.created_at) }} · 状态：{{ statusText(item.status) }}
          </p>
          <p class="meta">修订备注：{{ item.reason || "无" }}</p>
          <p class="meta">差异行数：{{ countChangedLines(item.article_content_md, item.proposed_content_md) }}</p>
          <div class="diff-preview" v-html="item._diffPreview"></div>
        </div>

        <div class="revision-actions">
          <button class="btn btn-accent" @click="openRevisionDetail(item)">进入审批页面</button>
        </div>
      </article>

      <button v-if="pendingPagination.hasMore" class="btn" @click="loadMorePendingRevisions">加载更多待审核</button>
      <p v-if="!pendingRevisions.length" class="meta">当前没有可审核的修订提议。</p>

      <section class="review-history-block">
        <h3>内容修改审批记录</h3>
        <p class="meta">共 {{ reviewedPagination.count }} 条</p>
        <article class="history-row" v-for="item in reviewedRevisions" :key="item.id">
          <div class="history-main">
            <strong>{{ item.article_title || item.proposed_title || "未命名条目" }}</strong>
            <p class="meta">提交日期：{{ formatDateTime(item.created_at) }} · 建议提出者：{{ item.proposer?.username || "-" }}</p>
            <p class="meta">审批人：{{ item.reviewer?.username || "-" }} · 审批时间：{{ formatDateTime(item.reviewed_at) }}</p>
            <p class="meta">审批结果：{{ statusText(item.status) }}</p>
            <p class="meta">修订备注：{{ item.reason || "无" }}</p>
            <p class="meta">审核备注：{{ item.review_note || "无" }}</p>
          </div>
          <div class="history-actions">
            <button class="btn" @click="openRevisionDetail(item)">查看修改后的对比视图</button>
          </div>
        </article>
        <button v-if="reviewedPagination.hasMore" class="btn" @click="loadMoreReviewedRevisions">加载更多审批记录</button>
        <p v-if="!reviewedRevisions.length" class="meta">暂无审批记录。</p>
      </section>
    </article>

    <article class="review-card full">
      <h2>Issue / Request 审核</h2>
      <p class="meta">共 {{ ticketPagination.count }} 条</p>
      <div class="ticket-filters">
        <select class="select" v-model="ticketFilters.scope" @change="loadTickets()">
          <option value="">全部范围</option>
          <option value="assigned">我负责的</option>
          <option value="created">我创建的</option>
        </select>
        <select class="select" v-model="ticketFilters.status" @change="loadTickets()">
          <option value="">全部状态</option>
          <option value="pending">pending</option>
          <option value="open">open</option>
          <option value="in_progress">in_progress</option>
          <option value="resolved">resolved</option>
          <option value="rejected">rejected</option>
        </select>
        <select class="select" v-model="ticketFilters.kind" @change="loadTickets()">
          <option value="">全部类型</option>
          <option value="issue">issue</option>
          <option value="request">request</option>
        </select>
        <input class="input" v-model="ticketFilters.search" placeholder="搜索标题或内容" @keyup.enter="loadTickets()" />
        <button class="btn" @click="loadTickets">筛选</button>
        <button class="btn" @click="resetTicketFilters">重置</button>
      </div>
      <article class="ticket-row" v-for="item in tickets" :key="item.id">
        <div class="ticket-main">
          <strong>{{ item.title }}</strong>
          <p class="meta">{{ item.kind }} · {{ statusText(item.status) }} · {{ item.author.username }}</p>
          <p class="meta">
            处理人：{{ item.assignee?.username ? `${item.assignee.username} (${item.assignee.role})` : "未分派" }}
          </p>
          <p class="meta" v-if="item.related_article_title">关联条目：{{ item.related_article_title }}</p>
          <p class="ticket-content">{{ item.content }}</p>
        </div>
        <div class="ticket-actions" v-if="canManageTicket(item)">
          <select class="select" v-if="auth.isManager" v-model="item._assignTo">
            <option value="">未分派</option>
            <option v-for="user in assigneeOptions" :key="`review-assignee-${item.id}-${user.id}`" :value="String(user.id)">
              {{ user.username }} ({{ user.role }})
            </option>
          </select>
          <select class="select" v-model="item._nextStatus">
            <option value="pending">pending</option>
            <option value="open">open</option>
            <option value="in_progress">in_progress</option>
            <option value="resolved">resolved</option>
            <option value="rejected">rejected</option>
          </select>
          <textarea class="textarea" v-model="item._note" placeholder="处理备注（可选）"></textarea>
          <button class="btn" @click="updateTicketStatus(item)">提交处理</button>
        </div>
      </article>
      <button v-if="ticketPagination.hasMore" class="btn" @click="loadMoreTickets">加载更多工单</button>
      <p v-if="!tickets.length" class="meta">暂无工单。</p>
    </article>

    <article class="review-card full">
      <h2>评论审核</h2>
      <p class="meta">待审核：{{ pendingCommentPagination.count }}</p>

      <div class="ticket-filters">
        <label class="meta select-all">
          <input
            type="checkbox"
            :checked="allPendingCommentsChecked"
            @change="toggleSelectAllPendingComments($event.target.checked)"
          />
          全选待审评论
        </label>
        <input class="input" v-model="commentFilters.search" placeholder="搜索评论内容" @keyup.enter="loadPendingComments()" />
        <input class="input" v-model="commentFilters.author" placeholder="评论用户名/ID" @keyup.enter="loadPendingComments()" />
        <input class="input" v-model="commentFilters.article" placeholder="条目ID" @keyup.enter="loadPendingComments()" />
        <input class="input" v-model="bulkCommentReviewNote" placeholder="批量审核备注（可选）" />
        <button class="btn btn-accent" @click="bulkApproveComments">批量通过</button>
        <button class="btn" @click="bulkRejectComments">批量驳回</button>
        <button class="btn" @click="resetCommentFilters">重置</button>
      </div>

      <article class="comment-row" v-for="item in pendingComments" :key="item.id">
        <div class="comment-main">
          <label class="meta select-all">
            <input type="checkbox" :value="item.id" v-model="selectedPendingCommentIds" />
            选择
          </label>
          <strong>评论 #{{ item.id }} · {{ item.article_title || `条目#${item.article}` }}</strong>
          <p class="meta">
            评论人：{{ item.author?.username || "-" }} · 提交时间：{{ formatDateTime(item.created_at) }} · 状态：{{ statusText(item.status) }}
          </p>
          <p class="comment-content">{{ item.content }}</p>
          <textarea class="textarea" v-model="item._reviewNote" placeholder="审核备注（可选）"></textarea>
        </div>

        <div class="comment-actions">
          <button class="btn btn-accent" :disabled="reviewingCommentId === item.id" @click="approveComment(item)">
            {{ reviewingCommentId === item.id ? "处理中..." : "通过" }}
          </button>
          <button class="btn" :disabled="reviewingCommentId === item.id" @click="rejectComment(item)">
            {{ reviewingCommentId === item.id ? "处理中..." : "驳回" }}
          </button>
        </div>
      </article>
      <button v-if="pendingCommentPagination.hasMore" class="btn" @click="loadMorePendingComments">加载更多评论</button>
      <p v-if="!pendingComments.length" class="meta">当前没有待审核评论。</p>
    </article>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import api from "../services/api";
import { countChangedLines, renderUnifiedDiffHtml } from "../services/revisionDiff";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const auth = useAuthStore();
const ui = useUiStore();
const router = useRouter();

const pendingRevisions = ref([]);
const reviewedRevisions = ref([]);
const pendingComments = ref([]);
const tickets = ref([]);
const assigneeOptions = ref([]);
const selectedPendingRevisionIds = ref([]);
const selectedPendingCommentIds = ref([]);
const bulkReviewNote = ref("");
const bulkCommentReviewNote = ref("");
const reviewingCommentId = ref(null);

const revisionFilters = reactive({
  search: "",
});

const ticketFilters = reactive({
  scope: "",
  status: "",
  kind: "",
  search: "",
});

const commentFilters = reactive({
  search: "",
  author: "",
  article: "",
});

const pendingPagination = reactive({ count: 0, page: 1, hasMore: false, loadingMore: false });
const reviewedPagination = reactive({ count: 0, page: 1, hasMore: false, loadingMore: false });
const ticketPagination = reactive({ count: 0, page: 1, hasMore: false, loadingMore: false });
const pendingCommentPagination = reactive({ count: 0, page: 1, hasMore: false, loadingMore: false });

const allPendingChecked = computed(
  () => pendingRevisions.value.length > 0 && selectedPendingRevisionIds.value.length === pendingRevisions.value.length
);
const allPendingCommentsChecked = computed(
  () => pendingComments.value.length > 0 && selectedPendingCommentIds.value.length === pendingComments.value.length
);

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function statusText(status) {
  const mapping = {
    pending: "审核中",
    approved: "通过",
    rejected: "驳回",
    visible: "已展示",
    hidden: "已隐藏",
  };
  return mapping[status] || status || "-";
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

function unpackListPayload(data) {
  if (Array.isArray(data)) {
    return { results: data, count: data.length };
  }
  const results = Array.isArray(data?.results) ? data.results : [];
  const count = Number.isFinite(data?.count) ? data.count : results.length;
  return { results, count };
}

function appendUniqueById(baseList, extraList) {
  const existed = new Set(baseList.map((item) => item.id));
  const merged = [...baseList];
  for (const item of extraList) {
    if (!existed.has(item.id)) {
      existed.add(item.id);
      merged.push(item);
    }
  }
  return merged;
}

function syncSelectedIds() {
  const validIds = new Set(pendingRevisions.value.map((item) => item.id));
  selectedPendingRevisionIds.value = selectedPendingRevisionIds.value.filter((id) => validIds.has(id));
}

function syncSelectedCommentIds() {
  const validIds = new Set(pendingComments.value.map((item) => item.id));
  selectedPendingCommentIds.value = selectedPendingCommentIds.value.filter((id) => validIds.has(id));
}

function updateMeta(meta, totalCount, loadedCount, page) {
  meta.count = totalCount;
  meta.page = page;
  meta.hasMore = loadedCount < totalCount;
}

function buildPendingRevisionParams(page = 1) {
  const params = { page, status: "pending" };
  if (revisionFilters.search.trim()) params.search = revisionFilters.search.trim();
  return params;
}

function mapRevision(item) {
  return {
    ...item,
    _diffPreview: renderUnifiedDiffHtml(item.article_content_md || "", item.proposed_content_md || "", { maxLines: 16 }),
  };
}

function buildPendingCommentParams(page = 1) {
  const params = { page, status: "pending" };
  if (commentFilters.search.trim()) params.search = commentFilters.search.trim();
  if (commentFilters.author.trim()) params.author = commentFilters.author.trim();
  if (commentFilters.article.trim()) params.article = commentFilters.article.trim();
  return params;
}

async function loadPendingRevisions(page = 1, append = false) {
  try {
    const { data } = await api.get("/revisions/", { params: buildPendingRevisionParams(page) });
    const { results, count } = unpackListPayload(data);
    const mapped = results.map(mapRevision);
    pendingRevisions.value = append ? appendUniqueById(pendingRevisions.value, mapped) : mapped;
    updateMeta(pendingPagination, count, pendingRevisions.value.length, page);
    syncSelectedIds();
  } catch (error) {
    ui.error(getErrorText(error, "修订列表加载失败"));
  }
}

async function loadReviewedRevisions(page = 1, append = false) {
  try {
    const base = revisionFilters.search.trim() ? { search: revisionFilters.search.trim() } : {};
    const [approvedResp, rejectedResp] = await Promise.all([
      api.get("/revisions/", { params: { ...base, page, status: "approved" } }),
      api.get("/revisions/", { params: { ...base, page, status: "rejected" } }),
    ]);

    const approved = unpackListPayload(approvedResp.data);
    const rejected = unpackListPayload(rejectedResp.data);
    const merged = [...approved.results, ...rejected.results]
      .map(mapRevision)
      .sort((a, b) => {
        const ta = new Date(a.reviewed_at || a.updated_at || a.created_at).getTime();
        const tb = new Date(b.reviewed_at || b.updated_at || b.created_at).getTime();
        return tb - ta;
      });

    reviewedRevisions.value = append ? appendUniqueById(reviewedRevisions.value, merged) : merged;
    const totalCount = approved.count + rejected.count;
    updateMeta(reviewedPagination, totalCount, reviewedRevisions.value.length, page);
  } catch (error) {
    ui.error(getErrorText(error, "审批记录加载失败"));
  }
}

async function loadTickets(page = 1, append = false) {
  try {
    const params = { page };
    if (ticketFilters.scope) params.scope = ticketFilters.scope;
    if (ticketFilters.status) params.status = ticketFilters.status;
    if (ticketFilters.kind) params.kind = ticketFilters.kind;
    if (ticketFilters.search.trim()) params.search = ticketFilters.search.trim();

    const { data } = await api.get("/issues/", { params });
    const { results, count } = unpackListPayload(data);
    const mapped = results.map((item) => ({
      ...item,
      _nextStatus: item.status,
      _note: item.resolution_note || "",
      _assignTo: item.assignee?.id ? String(item.assignee.id) : "",
    }));
    tickets.value = append ? appendUniqueById(tickets.value, mapped) : mapped;
    updateMeta(ticketPagination, count, tickets.value.length, page);
  } catch (error) {
    ui.error(getErrorText(error, "工单加载失败"));
  }
}

async function loadPendingComments(page = 1, append = false) {
  try {
    const { data } = await api.get("/comments/", { params: buildPendingCommentParams(page) });
    const { results, count } = unpackListPayload(data);
    const mapped = results.map((item) => ({
      ...item,
      _reviewNote: item._reviewNote || "",
    }));
    pendingComments.value = append ? appendUniqueById(pendingComments.value, mapped) : mapped;
    updateMeta(pendingCommentPagination, count, pendingComments.value.length, page);
    syncSelectedCommentIds();
  } catch (error) {
    ui.error(getErrorText(error, "待审核评论加载失败"));
  }
}

async function loadAssigneeOptions() {
  if (!auth.isManager) {
    assigneeOptions.value = [];
    return;
  }
  try {
    const { data } = await api.get("/users/assignees/");
    assigneeOptions.value = Array.isArray(data) ? data : data.results || [];
  } catch (error) {
    ui.error(getErrorText(error, "处理人列表加载失败"));
  }
}

function canManageTicket(item) {
  if (auth.isManager) return true;
  if (auth.role === "school") {
    return Number(item.assignee?.id) === Number(auth.user?.id);
  }
  return false;
}

async function updateTicketStatus(item) {
  if (!canManageTicket(item)) return;
  try {
    const payload = {
      status: item._nextStatus,
      resolution_note: item._note || "",
    };
    if (auth.isManager) {
      payload.assign_to = item._assignTo || null;
    }
    await api.post(`/issues/${item.id}/set_status/`, payload);
    ui.success("工单状态已更新");
    await loadTickets();
  } catch (error) {
    ui.error(getErrorText(error, "工单更新失败"));
  }
}

function toggleSelectAllPending(checked) {
  selectedPendingRevisionIds.value = checked ? pendingRevisions.value.map((item) => item.id) : [];
}

function toggleSelectAllPendingComments(checked) {
  selectedPendingCommentIds.value = checked ? pendingComments.value.map((item) => item.id) : [];
}

function notifyBulkSummary(summary, successText) {
  const successCount = Number(summary?.success || 0);
  const failCount = Number(summary?.failed || 0);
  if (successCount) {
    ui.success(`${successText}：成功 ${successCount} 条`);
  }
  if (failCount) {
    const sample = Array.isArray(summary?.results)
      ? summary.results.find((item) => item && item.success === false && item.detail)
      : null;
    ui.error(`${successText}：失败 ${failCount} 条${sample ? `（示例：${sample.detail}）` : ""}`);
  }
}

function openRevisionDetail(item) {
  router.push({ name: "review-revision", params: { id: item.id } });
}

async function bulkApproveRevisions() {
  if (!selectedPendingRevisionIds.value.length) {
    ui.info("请先选择修订提议");
    return;
  }
  try {
    const { data } = await api.post("/revisions/bulk-review/", {
      ids: selectedPendingRevisionIds.value,
      action: "approve",
      review_note: bulkReviewNote.value || "",
    });
    notifyBulkSummary(data, "批量通过修订");
    await Promise.all([loadPendingRevisions(), loadReviewedRevisions()]);
  } catch (error) {
    ui.error(getErrorText(error, "批量通过失败"));
  }
}

async function bulkRejectRevisions() {
  if (!selectedPendingRevisionIds.value.length) {
    ui.info("请先选择修订提议");
    return;
  }
  try {
    const { data } = await api.post("/revisions/bulk-review/", {
      ids: selectedPendingRevisionIds.value,
      action: "reject",
      review_note: bulkReviewNote.value || "",
    });
    notifyBulkSummary(data, "批量驳回修订");
    await Promise.all([loadPendingRevisions(), loadReviewedRevisions()]);
  } catch (error) {
    ui.error(getErrorText(error, "批量驳回失败"));
  }
}

async function reviewComment(item, action) {
  reviewingCommentId.value = item.id;
  try {
    await api.post(`/comments/${item.id}/${action}/`, {
      review_note: item._reviewNote || "",
    });
    ui.success(action === "approve" ? "评论已通过" : "评论已驳回");
    await loadPendingComments();
  } catch (error) {
    ui.error(getErrorText(error, action === "approve" ? "评论通过失败" : "评论驳回失败"));
  } finally {
    reviewingCommentId.value = null;
  }
}

function approveComment(item) {
  return reviewComment(item, "approve");
}

function rejectComment(item) {
  return reviewComment(item, "reject");
}

async function bulkApproveComments() {
  if (!selectedPendingCommentIds.value.length) {
    ui.info("请先选择待审核评论");
    return;
  }
  try {
    const { data } = await api.post("/comments/bulk-review/", {
      ids: selectedPendingCommentIds.value,
      action: "approve",
      review_note: bulkCommentReviewNote.value || "",
    });
    notifyBulkSummary(data, "批量通过评论");
    await loadPendingComments();
  } catch (error) {
    ui.error(getErrorText(error, "批量通过评论失败"));
  }
}

async function bulkRejectComments() {
  if (!selectedPendingCommentIds.value.length) {
    ui.info("请先选择待审核评论");
    return;
  }
  try {
    const { data } = await api.post("/comments/bulk-review/", {
      ids: selectedPendingCommentIds.value,
      action: "reject",
      review_note: bulkCommentReviewNote.value || "",
    });
    notifyBulkSummary(data, "批量驳回评论");
    await loadPendingComments();
  } catch (error) {
    ui.error(getErrorText(error, "批量驳回评论失败"));
  }
}

function resetRevisionFilters() {
  revisionFilters.search = "";
  loadPendingRevisions();
  loadReviewedRevisions();
}

function resetTicketFilters() {
  ticketFilters.scope = auth.role === "school" ? "assigned" : "";
  ticketFilters.status = "";
  ticketFilters.kind = "";
  ticketFilters.search = "";
  loadTickets();
}

function resetCommentFilters() {
  commentFilters.search = "";
  commentFilters.author = "";
  commentFilters.article = "";
  loadPendingComments();
}

async function loadMorePendingRevisions() {
  if (!pendingPagination.hasMore || pendingPagination.loadingMore) return;
  pendingPagination.loadingMore = true;
  try {
    await loadPendingRevisions(pendingPagination.page + 1, true);
  } finally {
    pendingPagination.loadingMore = false;
  }
}

async function loadMoreReviewedRevisions() {
  if (!reviewedPagination.hasMore || reviewedPagination.loadingMore) return;
  reviewedPagination.loadingMore = true;
  try {
    await loadReviewedRevisions(reviewedPagination.page + 1, true);
  } finally {
    reviewedPagination.loadingMore = false;
  }
}

async function loadMoreTickets() {
  if (!ticketPagination.hasMore || ticketPagination.loadingMore) return;
  ticketPagination.loadingMore = true;
  try {
    await loadTickets(ticketPagination.page + 1, true);
  } finally {
    ticketPagination.loadingMore = false;
  }
}

async function loadMorePendingComments() {
  if (!pendingCommentPagination.hasMore || pendingCommentPagination.loadingMore) return;
  pendingCommentPagination.loadingMore = true;
  try {
    await loadPendingComments(pendingCommentPagination.page + 1, true);
  } finally {
    pendingCommentPagination.loadingMore = false;
  }
}

onMounted(async () => {
  if (auth.role === "school") {
    ticketFilters.scope = "assigned";
  }
  await loadAssigneeOptions();
  await Promise.all([loadPendingRevisions(), loadReviewedRevisions(), loadTickets(), loadPendingComments()]);
});
</script>

<style scoped>
.review-layout {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.review-card {
  border: 1px solid var(--hairline);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.58);
  padding: 14px;
  box-shadow: var(--shadow-sm);
}

.review-card.full {
  grid-column: 1 / -1;
}

.review-card h2 {
  font-size: 32px;
  margin-bottom: 10px;
}

.revision-row,
.ticket-row,
.history-row,
.comment-row {
  padding: 11px 12px;
  margin-top: 10px;
  border-radius: 10px;
  background: rgba(245, 250, 255, 0.82);
}

.revision-row:first-of-type,
.ticket-row:first-of-type,
.history-row:first-of-type,
.comment-row:first-of-type {
  margin-top: 0;
}

.review-history-block {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--hairline);
}

.review-history-block h3 {
  margin: 0 0 8px;
  font-size: 24px;
}

.revision-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 210px;
  gap: 12px;
}

.diff-preview {
  margin-top: 8px;
  max-height: 240px;
  overflow: auto;
  border-radius: 8px;
  border: 1px solid var(--hairline);
  background: rgba(255, 255, 255, 0.75);
}

.diff-preview :deep(.diff-line) {
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr);
  gap: 8px;
  align-items: baseline;
  padding: 3px 8px;
  font-family: "Consolas", "Courier New", monospace;
  white-space: pre-wrap;
  line-height: 1.45;
  font-size: 13px;
}

.diff-preview :deep(.diff-line--insert) {
  background: rgba(45, 180, 105, 0.15);
  color: #16643d;
}

.diff-preview :deep(.diff-line--delete) {
  background: rgba(224, 74, 74, 0.15);
  color: #8d2222;
}

.diff-preview :deep(.diff-line--equal) {
  color: #2f3946;
}

.diff-preview :deep(.diff-line--ellipsis) {
  color: var(--muted);
}

.diff-preview :deep(.diff-inline-delete) {
  background: rgba(224, 74, 74, 0.28);
  color: #7a1c1c;
  text-decoration: line-through;
  padding: 0 2px;
  border-radius: 4px;
}

.diff-preview :deep(.diff-inline-insert) {
  background: rgba(45, 180, 105, 0.28);
  color: #0f6139;
  padding: 0 2px;
  border-radius: 4px;
}

.revision-actions {
  display: grid;
  align-content: start;
  gap: 8px;
}

.ticket-filters {
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.ticket-filters .select {
  width: 160px;
}

.ticket-filters .input {
  width: min(300px, 100%);
}

.select-all {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.ticket-content {
  margin: 6px 0 0;
  font-size: 16px;
  line-height: 1.56;
}

.ticket-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 12px;
}

.ticket-main {
  min-width: 0;
}

.ticket-actions {
  display: grid;
  gap: 8px;
  align-content: start;
}

.history-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 240px;
  gap: 12px;
}

.history-actions {
  display: grid;
  align-content: start;
}

.comment-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 240px;
  gap: 12px;
}

.comment-main {
  min-width: 0;
}

.comment-actions {
  display: grid;
  align-content: start;
  gap: 8px;
}

.comment-content {
  margin: 8px 0;
  white-space: pre-wrap;
  line-height: 1.55;
}

@media (max-width: 1100px) {
  .revision-row,
  .ticket-row,
  .history-row,
  .comment-row {
    grid-template-columns: 1fr;
  }

  .ticket-filters {
    align-items: stretch;
  }
}

@media (max-width: 640px) {
  .review-card h2 {
    font-size: 28px;
  }

  .ticket-filters .select,
  .ticket-filters .input {
    width: 100%;
  }
}
</style>
