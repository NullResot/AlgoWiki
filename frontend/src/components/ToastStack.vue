<template>
  <section class="toast-stack" aria-live="polite" aria-atomic="false">
    <TransitionGroup name="toast">
      <article
        v-for="toast in ui.toasts"
        :key="toast.id"
        class="toast-item card"
        :class="`toast-${toast.type}`"
        @mouseenter="ui.pauseToast(toast.id)"
        @mouseleave="ui.resumeToast(toast.id)"
        @focusin="ui.pauseToast(toast.id)"
        @focusout="ui.resumeToast(toast.id)"
      >
        <span class="toast-indicator" aria-hidden="true">
          <svg v-if="toast.type === 'success'" viewBox="0 0 20 20" fill="none">
            <path d="M5 10.5l3.2 3.2L15 7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <svg v-else-if="toast.type === 'error'" viewBox="0 0 20 20" fill="none">
            <path d="M10 6v4.5M10 13.8h.01" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          </svg>
          <svg v-else viewBox="0 0 20 20" fill="none">
            <path d="M10 9v5M10 6.2h.01" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          </svg>
        </span>
        <div class="toast-main">
          <strong v-if="toast.title">{{ toast.title }}</strong>
          <p>{{ toast.message }}</p>
          <button
            v-if="toast.action"
            type="button"
            class="toast-action-btn"
            @click="triggerToastAction(toast)"
          >
            {{ toast.action.label }}
          </button>
        </div>
        <button
          type="button"
          class="toast-close"
          aria-label="关闭通知"
          @click="ui.removeToast(toast.id)"
        >
          ×
        </button>
      </article>
    </TransitionGroup>
  </section>
</template>

<script setup>
import { useUiStore } from "../stores/ui";

const ui = useUiStore();

async function triggerToastAction(toast) {
  if (!toast?.action?.onClick) return;
  const fn = toast.action.onClick;
  ui.removeToast(toast.id);
  await fn();
}
</script>

<style scoped>
.toast-stack {
  position: fixed;
  top: 84px;
  right: 16px;
  z-index: var(--z-toast, 90);
  display: grid;
  gap: 10px;
  pointer-events: none;
}

.toast-item {
  width: min(370px, calc(100vw - 32px));
  padding: 11px 12px;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: start;
  pointer-events: auto;
  border-color: var(--panel-border-strong);
}

.toast-indicator {
  width: 22px;
  height: 22px;
  margin-top: 1px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}

.toast-indicator svg {
  width: 14px;
  height: 14px;
}

.toast-success .toast-indicator {
  background: color-mix(in srgb, var(--success) 18%, transparent);
  color: var(--success);
}

.toast-error .toast-indicator {
  background: color-mix(in srgb, var(--danger) 18%, transparent);
  color: var(--danger);
}

.toast-info .toast-indicator {
  background: color-mix(in srgb, var(--accent) 18%, transparent);
  color: var(--accent);
}

.toast-main {
  min-width: 0;
}

.toast-main strong {
  display: block;
  font-size: 14px;
  color: var(--text-strong);
  line-height: 1.3;
}

.toast-main p {
  margin: 3px 0 0;
  font-size: 13.5px;
  color: var(--text);
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.toast-action-btn {
  margin-top: 6px;
  border: 1px solid color-mix(in srgb, var(--accent) 34%, transparent);
  border-radius: 999px;
  padding: 4px 10px;
  background: color-mix(in srgb, var(--accent) 12%, var(--surface-strong));
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition:
    background-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    transform var(--dur-press, 90ms) var(--ease-out, ease);
}

.toast-action-btn:hover {
  background: color-mix(in srgb, var(--accent) 20%, var(--surface-strong));
}

.toast-action-btn:active {
  transform: scale(0.96);
}

.toast-close {
  width: 26px;
  height: 26px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--text-quiet);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition:
    background-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    color var(--dur-fast, 150ms) var(--ease-standard, ease),
    transform var(--dur-press, 90ms) var(--ease-out, ease);
}

.toast-close:hover {
  background: var(--surface-soft);
  color: var(--text-strong);
}

.toast-close:active {
  transform: scale(0.92);
}

.toast-success {
  background: color-mix(in srgb, var(--success) 14%, var(--surface-overlay));
}

.toast-error {
  background: color-mix(in srgb, var(--danger) 14%, var(--surface-overlay));
}

.toast-info {
  background: color-mix(in srgb, var(--accent) 10%, var(--surface-overlay));
}

.toast-enter-active {
  transition:
    opacity var(--dur-base, 220ms) var(--ease-out, cubic-bezier(0.22, 1, 0.36, 1)),
    transform var(--dur-base, 220ms) var(--ease-out, cubic-bezier(0.22, 1, 0.36, 1));
}

.toast-leave-active {
  position: absolute;
  right: 0;
  transition:
    opacity var(--dur-exit, 135ms) var(--ease-in, ease),
    transform var(--dur-exit, 135ms) var(--ease-in, ease);
}

.toast-move {
  transition: transform var(--dur-base, 220ms) var(--ease-out, cubic-bezier(0.22, 1, 0.36, 1));
}

.toast-enter-from {
  opacity: 0;
  transform: translate3d(12px, -4px, 0) scale(0.97);
}

.toast-leave-to {
  opacity: 0;
  transform: translate3d(10px, 0, 0) scale(0.96);
}

@media (max-width: 620px) {
  .toast-stack {
    top: 68px;
    right: 10px;
  }

  .toast-item {
    width: min(350px, calc(100vw - 20px));
  }
}

@media (prefers-reduced-motion: reduce) {
  .toast-enter-from,
  .toast-leave-to {
    transform: none;
  }

  .toast-move {
    transition: none;
  }
}
</style>
