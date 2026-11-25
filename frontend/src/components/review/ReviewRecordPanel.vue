<template>
  <div class="review-record-panel">
    <p class="meta">
      审核人：{{ reviewerName || "-" }} · 记录时间：{{ formatDateTime(reviewedAt) }}
    </p>
    <div class="review-record-note">
      {{ existingNote || "暂无批注记录" }}
    </div>
    <textarea
      v-model="draft"
      class="textarea"
      placeholder="追加管理员批注"
    ></textarea>
    <button
      class="btn"
      type="button"
      :disabled="loading || !draft.trim()"
      @click="handleSubmit"
    >
      {{ loading ? "提交中..." : "追加批注" }}
    </button>
  </div>
</template>

<script setup>
import { ref } from "vue";

const props = defineProps({
  reviewerName: {
    type: String,
    default: "",
  },
  reviewedAt: {
    type: [String, Number, Date, null],
    default: null,
  },
  existingNote: {
    type: String,
    default: "",
  },
  loading: {
    type: Boolean,
    default: false,
  },
  onSubmit: {
    type: Function,
    default: null,
  },
});

const draft = ref("");

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

async function handleSubmit() {
  const note = draft.value.trim();
  if (!note || typeof props.onSubmit !== "function") return;
  const ok = await props.onSubmit(note);
  if (ok) {
    draft.value = "";
  }
}
</script>

<style scoped>
.review-record-panel {
  display: grid;
  gap: 8px;
  width: 100%;
}

.review-record-note {
  white-space: pre-wrap;
  line-height: 1.6;
  color: var(--text);
  border: 1px solid var(--hairline);
  background: var(--surface-strong);
  border-radius: 10px;
  padding: 10px 12px;
}
</style>
