<template>
  <section class="revision-detail-page">
    <div v-if="loading && !proposal" class="detail-card card">
      <SkeletonBlock :lines="6" :line-height="20" label="正在加载修订审核详情" />
    </div>
    <div v-else-if="loadError && !proposal" class="detail-card card">
      <EmptyErrorState
        title="修订条目暂时无法读取"
        :description="loadError"
        action-label="重新加载"
        tone="error"
        @action="loadProposal"
      />
      <div class="head-actions">
        <button class="btn" type="button" @click="goBack">返回审核列表</button>
      </div>
    </div>
    <article v-else-if="proposal" class="detail-card">
      <header class="detail-head">
        <div>
          <h2>{{ proposal.article_title || proposal.proposed_title || "修订审核" }}</h2>
          <p class="meta">
            提交者 {{ proposal.proposer?.username || "-" }} · 提交时间 {{ formatDateTime(proposal.created_at) }}
          </p>
          <p class="meta">修订说明：{{ proposal.reason || "无" }}</p>
        </div>
        <div class="head-actions">
          <button class="btn" type="button" @click="goBack">返回审核列表</button>
          <button class="btn" type="button" @click="toggleCompareMode">
            {{ compareMode ? "退出对照视图" : "切换对照视图" }}
          </button>
        </div>
      </header>

      <section class="card preview-card" :class="{ 'preview-card--online': compareMode && pressingOriginal }">
        <div class="preview-head">
          <h3>{{ compareMode ? "对照预览" : "渲染预览" }}</h3>
          <button
            v-if="compareMode"
            type="button"
            class="btn btn-press"
            :aria-pressed="pressingOriginal"
            @click="setPressingOriginal(!pressingOriginal)"
          >
            {{ pressingOriginal ? "切回修改版本" : "对照当前线上版本" }}
          </button>
        </div>
        <div v-if="compareMode" class="preview-mode-row">
          <span class="preview-mode-pill" :class="{ 'is-online': pressingOriginal }">
            当前显示：{{ pressingOriginal ? "当前线上版本" : mergeConflict ? "冲突解决稿" : "待审核修订稿" }}
          </span>
        </div>
        <Transition name="aw-swap" mode="out-in">
          <div :key="`${compareMode}-${pressingOriginal}-${Boolean(mergeConflict)}`" class="markdown rendered-area" v-html="activeRenderHtml"></div>
        </Transition>
      </section>

      <section class="card diff-card">
        <h3>修订差异</h3>
        <p class="meta">绿色为新增，红色为删除。</p>
        <div class="diff-render" v-html="diffHtml"></div>
      </section>

      <Transition name="aw-collapse">
        <section
          v-if="proposal.status === 'pending' && mergeConflict"
          ref="conflictPanelEl"
          class="card review-action-card conflict-card"
        >
          <h3>合并冲突处理</h3>
          <p class="meta">{{ mergeConflict.detail }}</p>
          <p v-if="mergeConflict.conflicts?.length" class="meta">
            冲突字段：{{ mergeConflict.conflicts.map((item) => conflictFieldLabel(item.field)).join(" / ") }}
          </p>
          <label class="field-label">
            <span>合并后的标题</span>
            <input class="input" v-model="resolutionForm.title" placeholder="请输入最终采用的标题" />
          </label>
          <label class="field-label">
            <span>合并后的摘要（可选）</span>
            <textarea class="textarea" v-model="resolutionForm.summary" placeholder="可选填写最终摘要"></textarea>
          </label>
          <label class="field-label">
            <span>合并后的正文</span>
            <textarea
              class="textarea resolution-textarea"
              v-model="resolutionForm.content_md"
              placeholder="在此删除冲突标记并整理最终正文内容"
            ></textarea>
          </label>
          <p class="meta">已预填后端自动合并草稿。确认并消除冲突标记后，在下方点击「解决冲突并通过」。</p>
        </section>
      </Transition>

      <section v-if="proposal.status === 'pending'" class="card review-action-card">
        <h3>审核操作</h3>
        <textarea class="textarea" v-model="reviewNote" placeholder="审核备注（可选，驳回建议写明原因）"></textarea>
        <div class="review-actions">
          <button class="btn btn-accent" type="button" :disabled="submittingReview" @click="approve">
            {{ submittingReview ? "处理中..." : mergeConflict ? "解决冲突并通过" : "通过" }}
          </button>
          <button class="btn btn-danger" type="button" :disabled="submittingReview" @click="reject">
            {{ submittingReview ? "处理中..." : "驳回" }}
          </button>
        </div>
      </section>

      <section v-if="proposal.status !== 'pending'" class="card review-action-card">
        <h3>审核结果</h3>
        <p class="meta">结果：{{ statusText(proposal.status) }}</p>
        <p class="meta">审核人：{{ proposal.reviewer?.username || "-" }}</p>
        <p class="meta">审核时间：{{ formatDateTime(proposal.reviewed_at) }}</p>
        <p class="meta">审核备注：{{ proposal.review_note || "无" }}</p>
      </section>
    </article>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import EmptyErrorState from "../components/EmptyErrorState.vue";
import SkeletonBlock from "../components/SkeletonBlock.vue";
import api from "../services/api";
import { renderMarkdown } from "../services/markdown";
import { renderUnifiedDiffHtml } from "../services/revisionDiff";
import { useUiStore } from "../stores/ui";
import { safeScrollIntoView } from "../utils/motion";

const route = useRoute();
const router = useRouter();
const ui = useUiStore();

const proposal = ref(null);
const loading = ref(true);
const loadError = ref("");
const reviewNote = ref("");
const submittingReview = ref(false);
const compareMode = ref(false);
const pressingOriginal = ref(false);
const mergeConflict = ref(null);
const conflictPanelEl = ref(null);
const resolutionForm = reactive({
  title: "",
  summary: "",
  content_md: "",
  base_updated_at: "",
});

const activeRenderHtml = computed(() => {
  const item = proposal.value;
  if (!item) return "";
  if (compareMode.value && pressingOriginal.value) {
    return renderMarkdown(mergeConflict.value?.current?.content_md || item.article_content_md || "");
  }
  if (mergeConflict.value) {
    return renderMarkdown(resolutionForm.content_md || mergeConflict.value?.merged?.content_md || "");
  }
  return renderMarkdown(item.proposed_content_md || "");
});

const diffHtml = computed(() => {
  const item = proposal.value;
  if (!item) return "";
  const beforeText = mergeConflict.value?.current?.content_md || item.article_content_md || "";
  const afterText = mergeConflict.value ? resolutionForm.content_md : (item.proposed_content_md || "");
  return renderUnifiedDiffHtml(beforeText, afterText);
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

function toggleCompareMode() {
  compareMode.value = !compareMode.value;
  if (!compareMode.value) {
    pressingOriginal.value = false;
  }
}

function conflictFieldLabel(field) {
  return { title: "标题", summary: "摘要", content_md: "正文" }[field] || field;
}

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  return fallback;
}

function resetMergeConflict() {
  mergeConflict.value = null;
  resolutionForm.title = "";
  resolutionForm.summary = "";
  resolutionForm.content_md = "";
  resolutionForm.base_updated_at = "";
}

function applyMergeConflict(error) {
  const payload = error?.response?.data;
  const merge = payload?.merge;
  if (error?.response?.status !== 409 || payload?.code !== "revision_merge_conflict" || !merge) {
    return false;
  }

  mergeConflict.value = {
    detail: payload?.detail || "修订和当前线上版本存在合并冲突",
    conflicts: Array.isArray(merge?.conflicts) ? merge.conflicts : [],
    current: merge?.current || null,
    merged: merge?.merged || null,
  };
  resolutionForm.title = merge?.merged?.title ?? proposal.value?.proposed_title ?? "";
  resolutionForm.summary = merge?.merged?.summary ?? proposal.value?.proposed_summary ?? "";
  resolutionForm.content_md = merge?.merged?.content_md ?? proposal.value?.proposed_content_md ?? "";
  resolutionForm.base_updated_at = merge?.current?.updated_at || "";
  ui.error(payload?.detail || "修订和当前线上版本冲突，请先在下方处理冲突。");
  nextTick(() => safeScrollIntoView(conflictPanelEl.value, { block: "center" }));
  return true;
}

function goBack() {
  if (typeof window !== "undefined" && window.history.length > 1 && window.history.state?.back) {
    router.back();
    return;
  }
  router.push({ name: "review" });
}

async function loadProposal() {
  loading.value = true;
  loadError.value = "";
  try {
    const { data } = await api.get(`/revisions/${route.params.id}/`);
    proposal.value = data;
    reviewNote.value = data.review_note || "";
    resetMergeConflict();
  } catch (error) {
    const message = getErrorText(error, "审核条目加载失败");
    loadError.value = message;
    ui.error(message);
  } finally {
    loading.value = false;
  }
}

async function approve() {
  if (!proposal.value || proposal.value.status !== "pending") return;
  submittingReview.value = true;
  try {
    const payload = {
      review_note: reviewNote.value.trim(),
    };
    if (mergeConflict.value) {
      payload.resolved_title = resolutionForm.title.trim();
      payload.resolved_summary = resolutionForm.summary.trim();
      payload.resolved_content_md = resolutionForm.content_md;
      payload.resolution_base_updated_at = resolutionForm.base_updated_at || null;
    }
    const { data } = await api.post(`/revisions/${proposal.value.id}/approve/`, payload);
    proposal.value = data;
    resetMergeConflict();
    ui.success("修订已通过");
  } catch (error) {
    if (applyMergeConflict(error)) {
      return;
    }
    ui.error(getErrorText(error, "通过失败"));
  } finally {
    submittingReview.value = false;
  }
}

async function reject() {
  if (!proposal.value || proposal.value.status !== "pending" || submittingReview.value) return;
  const confirmed = await ui.confirm({
    title: "确认驳回该修订",
    message: reviewNote.value.trim()
      ? "驳回后提交者将收到你填写的审核备注，可重新修改后再提交。"
      : "当前尚未填写审核备注，驳回后提交者将看不到具体修改建议，确定继续驳回吗？",
    confirmText: "确认驳回",
    cancelText: "返回补充",
    danger: true,
  });
  if (!confirmed) return;
  submittingReview.value = true;
  try {
    const { data } = await api.post(`/revisions/${proposal.value.id}/reject/`, {
      review_note: reviewNote.value.trim(),
    });
    proposal.value = data;
    resetMergeConflict();
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
  display: grid;
  gap: 10px;
}

.preview-card--online {
  border-color: color-mix(in srgb, var(--accent) 42%, var(--hairline));
}

.preview-mode-row {
  display: flex;
  align-items: center;
}

.preview-mode-pill {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-soft);
  background: var(--surface-soft);
  border: 1px solid var(--hairline);
}

.preview-mode-pill.is-online {
  color: var(--accent);
  border-color: color-mix(in srgb, var(--accent) 45%, var(--hairline));
  background: color-mix(in srgb, var(--accent) 12%, var(--surface-soft));
}

.conflict-card {
  border-color: color-mix(in srgb, var(--danger) 40%, var(--hairline));
  background: color-mix(in srgb, var(--danger) 5%, var(--surface));
}

.field-label {
  display: grid;
  gap: 6px;
  font-size: 13px;
  color: var(--text-soft);
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
  background: var(--surface-strong);
}

.btn-press {
  user-select: none;
}

.diff-render {
  border-radius: 12px;
  border: 1px solid var(--hairline);
  background: var(--surface-strong);
  max-height: 58vh;
  overflow: auto;
}

.diff-render :deep(.diff-line) {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 8px;
  align-items: baseline;
  padding: 4px 10px;
  font-family: var(--font-mono);
  white-space: pre-wrap;
  line-height: 1.55;
}

.diff-render :deep(.diff-line--insert) {
  background: color-mix(in srgb, var(--success) 15%, transparent);
  color: var(--success);
}

.diff-render :deep(.diff-line--delete) {
  background: color-mix(in srgb, var(--danger) 15%, transparent);
  color: var(--danger);
}

.diff-render :deep(.diff-line--equal) {
  color: var(--text);
}

.diff-render :deep(.diff-line--ellipsis) {
  color: var(--muted);
}

.diff-render :deep(.diff-sign) {
  text-align: center;
  opacity: 0.8;
}

.diff-render :deep(.diff-inline-delete) {
  background: color-mix(in srgb, var(--danger) 24%, transparent);
  color: var(--danger);
  text-decoration: line-through;
  padding: 0 2px;
  border-radius: 4px;
}

.diff-render :deep(.diff-inline-insert) {
  background: color-mix(in srgb, var(--success) 24%, transparent);
  color: var(--success);
  padding: 0 2px;
  border-radius: 4px;
}

.review-actions {
  display: flex;
  gap: 8px;
}

.resolution-textarea {
  min-height: 280px;
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
