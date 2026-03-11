<template>
  <section class="toast-stack" aria-live="polite">
    <TransitionGroup name="toast">
      <article
        v-for="toast in ui.toasts"
        :key="toast.id"
        class="toast-item card"
        :class="`toast-${toast.type}`"
      >
        <div class="toast-main">
          <strong v-if="toast.title">{{ toast.title }}</strong>
          <p>{{ toast.message }}</p>
        </div>
        <button class="btn btn-ghost toast-close" @click="ui.removeToast(toast.id)">×</button>
      </article>
    </TransitionGroup>
  </section>
</template>

<script setup>
import { useUiStore } from "../stores/ui";

const ui = useUiStore();
</script>

<style scoped>
.toast-stack {
  position: fixed;
  top: 84px;
  right: 16px;
  z-index: 60;
  display: grid;
  gap: 10px;
  pointer-events: none;
}

.toast-item {
  width: min(360px, calc(100vw - 32px));
  padding: 10px 12px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: start;
  pointer-events: auto;
}

.toast-main strong {
  font-size: 14px;
}

.toast-main p {
  margin: 4px 0 0;
  font-size: 14px;
  color: #273243;
  line-height: 1.5;
}

.toast-close {
  padding: 4px 8px;
  font-size: 18px;
  line-height: 1;
}

.toast-success {
  background: rgba(225, 252, 240, 0.96);
}

.toast-error {
  background: rgba(255, 231, 233, 0.96);
}

.toast-info {
  background: rgba(231, 241, 255, 0.96);
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.22s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

@media (max-width: 620px) {
  .toast-stack {
    top: 72px;
    right: 10px;
  }

  .toast-item {
    width: min(340px, calc(100vw - 20px));
  }
}
</style>
