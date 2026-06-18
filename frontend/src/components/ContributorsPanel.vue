<template>
  <div class="contributors-block" :class="{ 'contributors-block--compact': compact }">
    <button
      type="button"
      class="contributors-toggle"
      :class="{ 'is-open': expanded }"
      @click="expanded = !expanded"
    >
      <span class="contributors-toggle-title">{{ title }}</span>
      <span class="contributors-toggle-count">{{ countLabel }}</span>
      <span class="contributors-toggle-icon" aria-hidden="true">{{ expanded ? "▾" : "▸" }}</span>
    </button>

    <div v-if="expanded" class="contributors-panel">
      <div v-if="normalizedContributors.length" class="contributors-list">
        <article
          v-for="(item, index) in normalizedContributors"
          :key="item.user?.id || `contributor-${index}`"
          class="contributors-item"
          :title="contributorSummaryText(item)"
        >
          <img
            class="contributors-avatar"
            :src="avatarSrc(item.user)"
            :alt="`${item.user?.username || '用户'} 头像`"
            loading="lazy"
          />
          <div class="contributors-item-head">
            <strong class="contributors-name">{{ item.user?.username || "-" }}</strong>
            <span v-if="item.is_creator" class="contributors-badge">{{ creatorBadgeText }}</span>
          </div>
          <p class="contributors-item-meta">
            {{ contributorSummaryText(item) }}
          </p>
        </article>
      </div>
      <p v-else class="contributors-empty">{{ emptyText }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  title: {
    type: String,
    default: "贡献者",
  },
  contributors: {
    type: Array,
    default: () => [],
  },
  compact: {
    type: Boolean,
    default: false,
  },
  emptyText: {
    type: String,
    default: "暂无贡献者记录",
  },
  creatorBadgeText: {
    type: String,
    default: "创建者",
  },
  defaultExpanded: {
    type: Boolean,
    default: false,
  },
});

const expanded = ref(Boolean(props.defaultExpanded));
const DEFAULT_AVATAR_URL = "/wiki-assets/default-avatar.svg";

const normalizedContributors = computed(() =>
  Array.isArray(props.contributors) ? props.contributors.filter((item) => item?.user) : []
);

const countLabel = computed(() => `${normalizedContributors.value.length} 人`);

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function contributorSummaryText(item) {
  const parts = [];
  const createdEntryCount = Number(item?.created_entry_count || 0);
  if (createdEntryCount > 0) {
    parts.push(`创建条目 ${createdEntryCount} 条`);
  } else if (item?.is_creator) {
    parts.push("创建条目");
  }
  if (Number(item?.approved_revision_count || 0) > 0) {
    parts.push(`已通过 ${Number(item.approved_revision_count)} 次修改`);
  }
  parts.push(`首次贡献 ${formatTime(item?.first_contributed_at)}`);
  if (String(item?.last_contributed_at || "") !== String(item?.first_contributed_at || "")) {
    parts.push(`最近贡献 ${formatTime(item?.last_contributed_at)}`);
  }
  return parts.join(" · ");
}

function avatarSrc(user) {
  return String(user?.avatar_url || "").trim() || DEFAULT_AVATAR_URL;
}
</script>

<style scoped>
.contributors-block {
  display: grid;
  gap: 8px;
}

.contributors-toggle {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 38px;
  width: fit-content;
  padding: 7px 12px;
  border: 1px solid color-mix(in srgb, var(--hairline) 92%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--surface-soft) 84%, white 16%);
  color: var(--text-strong);
  font: inherit;
  cursor: pointer;
  transition: border-color 0.18s ease, background-color 0.18s ease, color 0.18s ease;
}

.contributors-toggle:hover,
.contributors-toggle.is-open {
  border-color: color-mix(in srgb, var(--accent) 38%, var(--hairline));
  background: color-mix(in srgb, var(--accent) 8%, var(--surface-soft));
}

.contributors-toggle-title {
  font-weight: 600;
}

.contributors-toggle-count,
.contributors-toggle-icon {
  color: var(--text-quiet);
}

.contributors-panel {
  border: 1px solid color-mix(in srgb, var(--hairline) 92%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--surface-soft) 92%, white 8%);
  padding: 12px;
}

.contributors-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(118px, 1fr));
  gap: 10px;
}

.contributors-item {
  display: grid;
  justify-items: center;
  gap: 8px;
  min-width: 0;
  padding: 14px 10px;
  border: 1px solid color-mix(in srgb, var(--hairline) 88%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--surface-strong) 76%, white 24%);
  text-align: center;
}

.contributors-item-head {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
  width: 100%;
}

.contributors-avatar {
  width: 48px;
  height: 48px;
  border-radius: 999px;
  object-fit: cover;
  background: color-mix(in srgb, var(--accent) 12%, var(--surface-soft));
  border: 1px solid color-mix(in srgb, var(--hairline) 78%, transparent);
}

.contributors-name {
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.contributors-item-meta,
.contributors-empty {
  margin: 0;
  color: var(--text-quiet);
  font-size: 13px;
  line-height: 1.5;
}

.contributors-item-meta {
  display: -webkit-box;
  min-height: 38px;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.contributors-badge {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 2px 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent) 14%, transparent);
  color: var(--accent);
  font-size: 12px;
  font-weight: 600;
}

.contributors-block--compact .contributors-toggle {
  width: 100%;
  justify-content: space-between;
  min-height: 34px;
  padding: 6px 10px;
  border-radius: 10px;
  font-size: 13px;
}

.contributors-block--compact .contributors-panel {
  padding: 10px;
  border-radius: 10px;
}

.contributors-block--compact .contributors-item {
  padding: 12px 8px;
}

.contributors-block--compact .contributors-list {
  grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
}

.contributors-block--compact .contributors-avatar {
  width: 40px;
  height: 40px;
}

.contributors-block--compact .contributors-item-meta,
.contributors-block--compact .contributors-empty {
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 640px) {
  .contributors-toggle {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
