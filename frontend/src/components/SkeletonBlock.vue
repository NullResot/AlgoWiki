<template>
  <div class="skeleton-wrap" role="status" aria-busy="true" :aria-label="label">
    <span
      v-for="(width, idx) in lineWidths"
      :key="idx"
      class="aw-skeleton-line"
      :style="{ width, height: `${lineHeight}px` }"
    ></span>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  lines: {
    type: Number,
    default: 4,
  },
  lineHeight: {
    type: Number,
    default: 16,
  },
  label: {
    type: String,
    default: "内容加载中",
  },
});

const presets = ["64%", "100%", "92%", "84%", "96%", "72%"];
const lineWidths = computed(() =>
  Array.from({ length: Math.max(1, props.lines) }, (_, i) => presets[i % presets.length])
);
</script>

<style scoped>
.skeleton-wrap {
  display: grid;
  gap: 10px;
  padding: 6px 0;
}
</style>
