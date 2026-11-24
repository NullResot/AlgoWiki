<template>
  <Teleport to="body">
    <Transition name="aw-modal">
      <div v-if="visible && announcement" class="modal-wrap" @click.self="emit('close')">
        <article
          class="modal card aw-modal-panel"
          role="dialog"
          aria-modal="true"
          :aria-label="announcement.title || '站内公告'"
        >
          <header class="modal-head">
            <div>
              <p class="modal-kicker">{{ levelLabel }}</p>
              <h3>{{ announcement.title }}</h3>
            </div>
            <button type="button" class="btn btn-ghost" @click="emit('close')">{{ closeLabel }}</button>
          </header>
          <p v-if="announcement.summary" class="modal-summary">{{ announcement.summary }}</p>
          <section ref="markdownRef" class="markdown" v-html="htmlContent"></section>
        </article>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, ref } from "vue";

import { useMarkdownCodeCopy } from "../composables/useMarkdownCodeCopy";
import { useOverlayA11y } from "../composables/useOverlayA11y";
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
const markdownRef = ref(null);

const isOpen = computed(() => Boolean(props.visible && props.announcement));
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

useOverlayA11y(isOpen, () => emit("close"));
useMarkdownCodeCopy(markdownRef, () => [props.visible, htmlContent.value]);
</script>

<style scoped>
.modal-wrap {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal, 1200);
  display: grid;
  place-items: center;
  box-sizing: border-box;
  padding: 20px;
  overflow: hidden;
  background: color-mix(in srgb, #020617 44%, transparent);
}

.modal {
  width: 100%;
  max-width: 780px;
  max-height: calc(100dvh - 40px);
  box-sizing: border-box;
  padding: 20px;
  overflow-x: hidden;
  overflow-y: auto;
  overflow-wrap: anywhere;
  background: var(--surface-overlay);
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
  margin: 0;
  font-size: clamp(22px, 3vw, 30px);
  overflow-wrap: anywhere;
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
    max-height: calc(100dvh - 20px);
    padding: 12px;
  }

  .modal-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .modal-head h3 {
    font-size: clamp(22px, 7vw, 28px);
  }

  .modal-head .btn {
    min-height: 40px;
  }
}
</style>
