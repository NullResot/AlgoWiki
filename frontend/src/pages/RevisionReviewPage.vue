<template>
  <section class="revision-detail-page" v-if="proposal">
    <article class="detail-card">
      <header class="detail-head">
        <div>
          <h2>{{ proposal.article_title || proposal.proposed_title || "修订审批" }}</h2>
          <p class="meta">
            提议人 {{ proposal.proposer?.username || "-" }} · 提交于 {{ formatDateTime(proposal.created_at) }}
          </p>
          <p class="meta">修订备注：{{ proposal.reason || "无" }}</p>
        </div>
        <div class="head-actions">
          <button class="btn" @click="goBack">返回审核台</button>
          <button class="btn" @click="compareMode = !compareMode">
            {{ compareMode ? "返回默认视图" : "切换对比视图" }}
          </button>
        </div>
      </header>

      <section class="card preview-card">
        <div class="preview-head">
          <h3>{{ compareMode ? "对比视图" : "修改后渲染" }}</h3>
          <button
            v-if="compareMode"
            class="btn btn-press"
            @mousedown.prevent="setPressingOriginal(true)"
            @mouseup="setPressingOriginal(false)"
            @mouseleave="setPressingOriginal(false)"
            @touchstart.prevent="setPressingOriginal(true)"
            @touchend="setPressingOriginal(false)"
            @touchcancel="setPressingOriginal(false)"
          >
            {{ pressingOriginal ? "松开返回修改后" : "长按查看原页面" }}
          </button>
        </div>
        <div class="meta" v-if="compareMode">
          当前显示：{{ pressingOriginal ? "原页面渲染结果" : "修改后渲染结果" }}
        </div>
        <div class="markdown rendered-area" v-html="activeRenderHtml"></div>
      </section>

      <section class="card diff-card">
        <h3>修订差异（单列）</h3>
        <p class="meta">绿色为新增，红色为删除；行内改动会使用绿色/红色背景标出。</p>
        <div class="diff-render" v-html="diffHtml"></div>
      </section>

      <section v-if="proposal.status === 'pending'" class="card review-action-card">
        <h3>审批操作</h3>
        <textarea class="textarea" v-model="reviewNote" placeholder="审批备注（可选）"></textarea>
        <div class="review-actions">
          <button class="btn btn-accent" :disabled="submittingReview" @click="approve">
            {{ submittingReview ? "处理中..." : "通过" }}
          </button>
          <button class="btn" :disabled="submittingReview" @click="reject">
            {{ submittingReview ? "处理中..." : "驳回" }}
          </button>
        </div>
      </section>

      <section v-else class="card review-action-card">
        <h3>审批结果</h3>
        <p class="meta">结果：{{ statusText(proposal.status) }}</p>
        <p class="meta">审批人：{{ proposal.reviewer?.username || "-" }}</p>
        <p class="meta">审批时间：{{ formatDateTime(proposal.reviewed_at) }}</p>
        <p class="meta">审批备注：{{ proposal.review_note || "无" }}</p>
      </section>
    </article>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import api from "../services/api";
import { renderMarkdown } from "../services/markdown";
import { renderUnifiedDiffHtml } from "../services/revisionDiff";
import { useUiStore } from "../stores/ui";

const route = useRoute();
const router = useRouter();
const ui = useUiStore();

const proposal = ref(null);
const reviewNote = ref("");
const submittingReview = ref(false);
const compareMode = ref(false);
const pressingOriginal = ref(false);

const activeRenderHtml = computed(() => {
  const item = proposal.value;
  if (!item) return "";
  if (compareMode.value && pressingOriginal.value) {
    return renderMarkdown(item.article_content_md || "");
  }
  return renderMarkdown(item.proposed_content_md || "");
});

const diffHtml = computed(() => {
  const item = proposal.value;
  if (!item) return "";
  return renderUnifiedDiffHtml(item.article_content_md || "", item.proposed_content_md || "");
});

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function statusText(status) {
  const mapping = {
    pending: "待审核",
    approved: "通过",
    rejected: "驳回",
  };
  return mapping[status] || status || "-";
}

function setPressingOriginal(flag) {
  pressingOriginal.value = Boolean(flag);
}

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  return fallback;
}

function goBack() {
  router.push({ name: "review" });
}

async function loadProposal() {
  try {
    const { data } = await api.get(`/revisions/${route.params.id}/`);
    proposal.value = data;
    reviewNote.value = data.review_note || "";
  } catch (error) {
    ui.error(getErrorText(error, "审批条目加载失败"));
    goBack();
  }
}

async function approve() {
  if (!proposal.value || proposal.value.status !== "pending") return;
  submittingReview.value = true;
  try {
    const { data } = await api.post(`/revisions/${proposal.value.id}/approve/`, {
      review_note: reviewNote.value.trim(),
    });
    proposal.value = data;
    ui.success("修订已通过");
  } catch (error) {
    ui.error(getErrorText(error, "通过失败"));
  } finally {
    submittingReview.value = false;
  }
}

async function reject() {
  if (!proposal.value || proposal.value.status !== "pending") return;
  submittingReview.value = true;
  try {
    const { data } = await api.post(`/revisions/${proposal.value.id}/reject/`, {
      review_note: reviewNote.value.trim(),
    });
    proposal.value = data;
    ui.success("修订已驳回");
  } catch (error) {
    ui.error(getErrorText(error, "驳回失败"));
  } finally {
    submittingReview.value = false;
  }
}

onMounted(async () => {
  await loadProposal();
});
</script>

<style scoped>
.revision-detail-page {
  max-width: 1320px;
  margin: 0 auto;
}

.detail-card {
  display: grid;
  gap: 12px;
}

.detail-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.detail-head h2 {
  font-size: 34px;
}

.head-actions {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.preview-card,
.diff-card,
.review-action-card {
  padding: 14px;
}

.preview-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.preview-head h3,
.diff-card h3,
.review-action-card h3 {
  font-size: 24px;
  margin: 0;
}

.rendered-area {
  max-height: 72vh;
  overflow: auto;
  border-radius: 12px;
  border: 1px solid var(--hairline);
  padding: 12px;
  background: rgba(255, 255, 255, 0.7);
}

.btn-press {
  user-select: none;
}

.diff-render {
  border-radius: 12px;
  border: 1px solid var(--hairline);
  background: rgba(255, 255, 255, 0.75);
  max-height: 58vh;
  overflow: auto;
}

.diff-render :deep(.diff-line) {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 8px;
  align-items: baseline;
  padding: 4px 10px;
  font-family: "Consolas", "Courier New", monospace;
  white-space: pre-wrap;
  line-height: 1.55;
}

.diff-render :deep(.diff-line--insert) {
  background: rgba(45, 180, 105, 0.15);
  color: #16643d;
}

.diff-render :deep(.diff-line--delete) {
  background: rgba(224, 74, 74, 0.15);
  color: #8d2222;
}

.diff-render :deep(.diff-line--equal) {
  color: #2f3946;
}

.diff-render :deep(.diff-line--ellipsis) {
  color: var(--muted);
}

.diff-render :deep(.diff-sign) {
  text-align: center;
  opacity: 0.8;
}

.diff-render :deep(.diff-inline-delete) {
  background: rgba(224, 74, 74, 0.28);
  color: #7a1c1c;
  text-decoration: line-through;
  padding: 0 2px;
  border-radius: 4px;
}

.diff-render :deep(.diff-inline-insert) {
  background: rgba(45, 180, 105, 0.28);
  color: #0f6139;
  padding: 0 2px;
  border-radius: 4px;
}

.review-actions {
  display: flex;
  gap: 8px;
}

@media (max-width: 960px) {
  .detail-head {
    flex-direction: column;
  }

  .head-actions {
    width: 100%;
    flex-wrap: wrap;
  }
}
</style>
