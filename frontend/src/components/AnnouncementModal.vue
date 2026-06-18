<template>
  <div v-if="visible && announcement" class="modal-wrap" @click.self="emit('close')">
    <article class="modal card">
      <header class="modal-head">
        <div>
          <p class="modal-kicker">{{ levelLabel }}</p>
          <h3>{{ announcement.title }}</h3>
        </div>
        <button class="btn btn-ghost" @click="emit('close')">{{ closeLabel }}</button>
      </header>
      <p v-if="announcement.summary" class="modal-summary">{{ announcement.summary }}</p>
      <section class="markdown" v-html="htmlContent"></section>
    </article>
  </div>
</template>

<script setup>
import { computed } from "vue";

import { renderMarkdown } from "../services/markdown";

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  announcement: {
    type: Object,
    default: null,
  },
});

const emit = defineEmits(["close"]);

const htmlContent = computed(() => renderMarkdown(props.announcement?.content_md || ""));
const closeLabel = computed(() => props.announcement?.requires_ack ? "我已知晓" : "关闭");
const levelLabel = computed(() => {
  const labels = {
    emergency: "紧急公告",
    important: "重要公告",
    normal: "站内公告",
    low: "站内公告",
  };
  return labels[props.announcement?.level] || "站内公告";
});
</script>

<style scoped>
.modal-wrap {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: grid;
  place-items: center;
  padding: 20px;
  background: color-mix(in srgb, var(--text-strong) 26%, transparent);
}

.modal {
  max-width: 780px;
  width: 100%;
  padding: 20px;
  box-shadow: var(--shadow-md);
}

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}

.modal-head h3 {
  font-size: 30px;
}

.modal-kicker {
  margin: 0 0 4px;
  color: var(--accent);
  font-size: 12px;
  font-weight: 800;
}

.modal-summary {
  margin: 0 0 12px;
  color: var(--muted);
  line-height: 1.7;
}

@media (max-width: 760px) {
  .modal-wrap {
    padding: 10px;
  }

  .modal {
    padding: 12px;
  }

  .modal-head {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
