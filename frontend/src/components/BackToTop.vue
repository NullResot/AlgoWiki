<template>
  <Transition name="aw-popover">
    <button
      v-if="visible"
      type="button"
      class="back-to-top"
      aria-label="回到页面顶部"
      title="回到顶部"
      @click="scrollToTop"
    >
      <svg viewBox="0 0 20 20" focusable="false" aria-hidden="true">
        <path
          d="M10 15.5V4.8m0 0L5.6 9.2M10 4.8l4.4 4.4"
          fill="none"
          stroke="currentColor"
          stroke-width="1.9"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </button>
  </Transition>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { safeScrollTo } from "../utils/motion";

const visible = ref(false);
let rafId = 0;

function syncScroll() {
  rafId = 0;
  if (typeof window === "undefined") return;
  visible.value = window.scrollY > 520;
}

function handleScroll() {
  if (rafId) return;
  rafId = window.requestAnimationFrame(syncScroll);
}

function scrollToTop() {
  safeScrollTo({ top: 0, behavior: "smooth" });
}

onMounted(() => {
  syncScroll();
  window.addEventListener("scroll", handleScroll, { passive: true });
});

onBeforeUnmount(() => {
  window.removeEventListener("scroll", handleScroll);
  if (rafId) window.cancelAnimationFrame(rafId);
});
</script>

<style scoped>
.back-to-top {
  position: fixed;
  left: 20px;
  bottom: 24px;
  z-index: 65;
  width: 42px;
  height: 42px;
  border: 1px solid var(--panel-border-strong);
  border-radius: 999px;
  background: var(--surface-overlay);
  color: var(--text-strong);
  box-shadow: var(--shadow-sm);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transform-origin: center;
  transition:
    transform var(--dur-fast, 150ms) var(--ease-out, cubic-bezier(0.22, 1, 0.36, 1)),
    border-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    background-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    box-shadow var(--dur-fast, 150ms) var(--ease-standard, ease);
}

.back-to-top svg {
  width: 18px;
  height: 18px;
}

@media (hover: hover) {
  .back-to-top:hover {
    transform: translate3d(0, -2px, 0);
    border-color: var(--accent);
    color: var(--accent);
    box-shadow: var(--shadow-md);
  }
}

.back-to-top:active {
  transform: scale(0.95);
  transition-duration: var(--dur-press, 90ms);
}

@media (max-width: 640px) {
  .back-to-top {
    left: 12px;
    bottom: 16px;
    width: 38px;
    height: 38px;
  }
}
</style>
