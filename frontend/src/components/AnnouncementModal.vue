<template>
  <div v-if="visible && announcement" class="modal-wrap" @click.self="emit('close')">
    <article class="modal card">
      <header class="modal-head">
        <h3>{{ announcement.title }}</h3>
        <button class="btn btn-ghost" @click="emit('close')">关闭</button>
      </header>
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
</script>

<style scoped>
.modal-wrap {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(14, 20, 33, 0.42);
}

.modal {
  max-width: 780px;
  width: 100%;
  padding: 20px;
  box-shadow: 0 20px 44px rgba(10, 18, 32, 0.3);
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
