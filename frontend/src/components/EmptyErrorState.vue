<template>
  <div class="state-box" :class="`state-box--${tone}`">
    <strong class="state-title">{{ title }}</strong>
    <p v-if="description" class="state-desc">{{ description }}</p>
    <div v-if="actionLabel" class="state-actions">
      <button type="button" class="btn btn-mini" :disabled="busy" @click="$emit('action')">
        {{ busy ? "处理中..." : actionLabel }}
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    required: true,
  },
  description: {
    type: String,
    default: "",
  },
  actionLabel: {
    type: String,
    default: "",
  },
  busy: {
    type: Boolean,
    default: false,
  },
  tone: {
    type: String,
    default: "neutral",
  },
});

defineEmits(["action"]);
</script>

<style scoped>
.state-box {
  display: grid;
  gap: 8px;
  padding: 18px 20px;
  border: 1px dashed var(--hairline-strong);
  border-radius: var(--radius-md);
  background: var(--surface-soft);
  text-align: center;
  justify-items: center;
}

.state-box--error {
  border-style: solid;
  border-color: color-mix(in srgb, var(--danger) 35%, var(--hairline));
  background: color-mix(in srgb, var(--danger) 7%, var(--surface-soft));
}

.state-title {
  font-size: 15px;
  color: var(--text-strong);
}

.state-desc {
  margin: 0;
  max-width: 48ch;
  font-size: 13.5px;
  color: var(--text-soft);
  line-height: 1.6;
}

.state-actions {
  display: flex;
  gap: 8px;
  margin-top: 2px;
}
</style>
