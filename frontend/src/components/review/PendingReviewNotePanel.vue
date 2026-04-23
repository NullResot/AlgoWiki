<template>
  <div class="pending-review-note-panel">
    <div class="pending-review-note-head">
      <strong>{{ title }}</strong>
      <span class="meta">{{ hint }}</span>
    </div>
    <div class="pending-review-note-preview">
      {{ previewText }}
    </div>
    <textarea
      :value="modelValue"
      class="textarea pending-review-note-input"
      :placeholder="placeholder"
      @input="emit('update:modelValue', $event.target.value)"
    ></textarea>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  modelValue: {
    type: String,
    default: "",
  },
  placeholder: {
    type: String,
    default: "可选填写审核批注",
  },
  title: {
    type: String,
    default: "审核批注",
  },
  hint: {
    type: String,
    default: "会随当前审核结果一并通知用户",
  },
  emptyText: {
    type: String,
    default: "可选填写；点击通过或驳回后，批注会发送到对方的通知栏。",
  },
});

const emit = defineEmits(["update:modelValue"]);

const previewText = computed(() => {
  const text = String(props.modelValue || "").trim();
  return text || props.emptyText;
});
</script>

<style scoped>
.pending-review-note-panel {
  display: grid;
  gap: 8px;
  width: 100%;
}

.pending-review-note-head {
  display: grid;
  gap: 2px;
}

.pending-review-note-head strong {
  font-size: 13px;
  color: var(--text-strong);
}

.pending-review-note-head .meta {
  margin: 0;
  font-size: 12px;
}

.pending-review-note-preview {
  min-height: 72px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--hairline);
  background: var(--surface-strong);
  color: var(--text);
  line-height: 1.6;
  white-space: pre-wrap;
}

.pending-review-note-input {
  min-height: 88px;
  resize: vertical;
}
</style>
