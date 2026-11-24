<template>
  <RouterLink
    class="pulse-header-entry"
    :class="{ 'pulse-header-entry--complete': pulse.isComplete }"
    :to="{ name: 'pulse' }"
    :aria-label="pulse.isComplete ? '今日脉冲已完成，打开算法星图' : `打开今日脉冲，已完成 ${pulse.progressCount}/3`"
  >
    <PulseStar
      :progress="pulse.progressCount"
      :question-complete="pulse.state.communityCompleted"
      :challenge-complete="pulse.state.challengeCompleted"
      :poll-complete="pulse.state.pollCompleted"
      compact
    />
    <span class="pulse-header-copy">
      <strong>{{ pulse.isComplete ? "今日完成" : "今日脉冲" }}</strong>
      <small v-if="!pulse.isComplete">{{ pulse.progressCount }}/3</small>
    </span>
  </RouterLink>
</template>

<script setup>
import { watch } from "vue";
import { RouterLink } from "vue-router";

import { useAuthStore } from "../../stores/auth";
import { usePulseStore } from "../../stores/pulse";
import PulseStar from "./PulseStar.vue";

const auth = useAuthStore();
const pulse = usePulseStore();

watch(
  () => auth.token || "anonymous",
  (sessionKey) => {
    pulse.initialize(sessionKey).catch(() => {});
  },
  { immediate: true },
);
</script>

<style scoped>
.pulse-header-entry {
  height: 38px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 3px 10px 3px 6px;
  border: 1px solid color-mix(in srgb, #d9a344 38%, var(--hairline));
  border-radius: 999px;
  color: var(--text-strong);
  background: color-mix(in srgb, #f4c76a 8%, var(--surface-strong));
  text-decoration: none;
  transition:
    transform var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out),
    background-color var(--dur-fast) var(--ease-out);
}

.pulse-header-entry:hover {
  transform: translate3d(0, -1px, 0);
  border-color: color-mix(in srgb, #d9a344 72%, var(--hairline));
  background: color-mix(in srgb, #f4c76a 13%, var(--surface-strong));
}

.pulse-header-entry:active {
  transform: scale(0.97);
}

.pulse-header-copy { display: flex; align-items: baseline; gap: 5px; white-space: nowrap; }
.pulse-header-copy strong { font-size: 12px; font-weight: 750; }
.pulse-header-copy small { color: var(--text-soft); font-size: 11px; font-variant-numeric: tabular-nums; }

.pulse-header-entry--complete {
  border-color: color-mix(in srgb, #42b883 55%, var(--hairline));
  background: color-mix(in srgb, #42b883 10%, var(--surface-strong));
}

@media (max-width: 620px) {
  .pulse-header-entry { width: 36px; height: 36px; padding: 3px; justify-content: center; }
  .pulse-header-copy { display: none; }
}

@media (max-width: 480px) {
  .pulse-header-entry { width: 34px; height: 34px; flex: 0 0 auto; }
}

@media (prefers-reduced-motion: reduce) {
  .pulse-header-entry {
    transition: border-color var(--dur-fast) linear, background-color var(--dur-fast) linear;
  }

  .pulse-header-entry:hover,
  .pulse-header-entry:active {
    transform: none;
  }
}
</style>
