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
import { onMounted } from "vue";
import { RouterLink } from "vue-router";

import { usePulseStore } from "../../stores/pulse";
import PulseStar from "./PulseStar.vue";

const pulse = usePulseStore();
onMounted(() => pulse.initialize().catch(() => {}));
</script>

<style scoped>
.pulse-header-entry {
  height: 38px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 3px 10px 3px 6px;
  border: 1px solid color-mix(in srgb, #d9a344 38%, var(--hairline));
  border-radius: 999px;
  color: var(--text-main);
  background: color-mix(in srgb, #f4c76a 8%, var(--surface-strong));
  text-decoration: none;
  transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}

.pulse-header-entry:hover {
  transform: translateY(-1px);
  border-color: color-mix(in srgb, #d9a344 72%, var(--hairline));
  background: color-mix(in srgb, #f4c76a 13%, var(--surface-strong));
}

.pulse-header-copy { display: flex; align-items: baseline; gap: 5px; white-space: nowrap; }
.pulse-header-copy strong { font-size: 12px; font-weight: 750; }
.pulse-header-copy small { color: var(--text-soft); font-size: 10px; }

.pulse-header-entry--complete {
  border-color: color-mix(in srgb, #42b883 55%, var(--hairline));
  background: color-mix(in srgb, #42b883 10%, var(--surface-strong));
}

@media (max-width: 620px) {
  .pulse-header-entry { width: 36px; height: 36px; padding: 3px; justify-content: center; }
  .pulse-header-copy { display: none; }
}
</style>
