<template>
  <section class="rank-page">
    <header class="rank-hero">
      <div>
        <p class="kicker">AlgoWiki Contribution</p>
        <h1>贡献榜</h1>
        <p class="meta">
          按 Trick、竞赛 Wiki、赛事协作和社区邀请分开展示，方便查看不同方向的贡献情况。
        </p>
      </div>
      <RouterLink v-if="auth.isAuthenticated" class="btn btn-accent" :to="{ name: 'profile-section', params: { section: 'invitation' } }">
        我的邀请
      </RouterLink>
    </header>

    <div class="rank-tabs-wrap">
      <nav class="rank-tabs" role="tablist" aria-label="贡献榜分类">
        <button
          v-for="item in rankTabs"
          :key="item.key"
          type="button"
          role="tab"
          :aria-selected="activeType === item.key"
          :class="{ active: activeType === item.key }"
          @click="switchType(item.key)"
        >
          {{ item.label }}
        </button>
      </nav>
      <p class="rank-rule-hint">{{ activeTab.ruleHint }}</p>
    </div>

    <SkeletonBlock
      v-if="loading && !rankResults.length"
      :lines="5"
      :line-height="18"
      label="正在加载贡献榜"
    />

    <EmptyErrorState
      v-else-if="loadError && !rankResults.length"
      tone="error"
      title="贡献榜加载失败"
      :description="loadError"
      action-label="重新加载"
      :busy="loading"
      @action="loadRankings"
    />

    <EmptyErrorState
      v-else-if="!loading && !rankResults.length"
      title="当前暂无贡献数据"
      description="随着大家参与条目编辑、Trick 投稿和社区共建，榜单会逐步充实。"
    />

    <section v-else class="rank-grid" :class="{ 'is-loading': loading }">
      <article
        v-for="(item, index) in rankResults"
        :key="rankKey(item, index)"
        class="rank-card"
        :class="[
          index < 3 ? `rank-card--top-${index + 1}` : '',
          { 'rank-card--self': isCurrentUser(item) },
        ]"
      >
        <span class="rank-number tabular-nums">#{{ index + 1 }}</span>
        <img class="rank-avatar" :src="avatarSrc(item)" :alt="`${item.username || '用户'} 头像`" loading="lazy" />
        <div class="rank-main">
          <div class="rank-name-line">
            <strong>{{ item.username }}</strong>
            <span v-if="isCurrentUser(item)" class="rank-self-badge">我</span>
          </div>
          <span>{{ item.school_name || "未填写学校" }}</span>
        </div>
        <div class="rank-score">
          <strong class="tabular-nums">{{ displayScore(item) }}</strong>
          <span>{{ activeScoreLabel }}</span>
        </div>
      </article>
    </section>
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import EmptyErrorState from "../components/EmptyErrorState.vue";
import SkeletonBlock from "../components/SkeletonBlock.vue";
import { useRequestControllers } from "../composables/useRequestControllers";
import api, { isRequestCanceled } from "../services/api";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";
import { extractApiError } from "../utils/format";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const ui = useUiStore();
const requests = useRequestControllers();

const rankTabs = [
  {
    key: "trick",
    label: "Trick 贡献",
    scoreKey: "trick_contribution_score",
    scoreLabel: "Trick",
    ruleHint: "统计维度：通过审核的 Trick 投稿及社区认可表现。",
  },
  {
    key: "wiki",
    label: "Wiki 贡献",
    scoreKey: "wiki_contribution_score",
    scoreLabel: "Wiki",
    ruleHint: "统计维度：算法百科条目创建与有效版本修订贡献。",
  },
  {
    key: "competition",
    label: "赛事贡献",
    scoreKey: "competition_contribution_score",
    scoreLabel: "赛事",
    ruleHint: "统计维度：赛事日程补充、题解练兵反馈与竞赛资料协作。",
  },
  {
    key: "community",
    label: "社区贡献",
    scoreKey: "community_contribution_score",
    scoreLabel: "社区",
    ruleHint: "统计维度：有效好友邀请、日常讨论分享与社区互动活跃。",
  },
];

const validTypes = new Set(rankTabs.map((item) => item.key));
const activeType = ref(validTypes.has(String(route.query.type || "")) ? String(route.query.type) : "trick");
const rankResults = ref([]);
const loading = ref(false);
const loadError = ref("");
const DEFAULT_AVATAR_URL = "/wiki-assets/default-avatar.svg";

const activeTab = computed(() => rankTabs.find((item) => item.key === activeType.value) || rankTabs[0]);
const activeScoreLabel = computed(() => activeTab.value.scoreLabel);

function avatarSrc(item) {
  return item?.avatar_url || DEFAULT_AVATAR_URL;
}

function isCurrentUser(item) {
  return Boolean(auth.user?.id && item?.id && Number(item.id) === Number(auth.user.id));
}

function displayScore(item) {
  return Number(item?.[activeTab.value.scoreKey] || 0);
}

function rankKey(item, index) {
  return item.id || `${activeType.value}-${index}`;
}

async function loadRankings() {
  const controller = requests.replace("rankings");
  loading.value = true;
  loadError.value = "";
  try {
    const { data } = await api.get("/contribution-rankings/", {
      params: { type: activeType.value, limit: 50 },
      signal: controller.signal,
    });
    if (!requests.isCurrent("rankings", controller)) return;
    rankResults.value = Array.isArray(data?.results) ? data.results : [];
  } catch (error) {
    if (isRequestCanceled(error) || !requests.isCurrent("rankings", controller)) return;
    const msg = extractApiError(error, "贡献榜加载失败，请稍后重试");
    loadError.value = msg;
    if (!rankResults.value.length) {
      ui.error(msg);
    }
  } finally {
    if (requests.release("rankings", controller)) {
      loading.value = false;
    }
  }
}

async function switchType(type) {
  if (!validTypes.has(type) || type === activeType.value) return;
  activeType.value = type;
  await router.replace({ name: "contributions", query: { type } });
}

watch(
  () => route.query.type,
  (raw) => {
    const nextType = validTypes.has(String(raw || "")) ? String(raw) : "trick";
    activeType.value = nextType;
    loadRankings();
  },
  { immediate: true },
);
</script>

<style scoped>
.rank-page {
  display: grid;
  gap: 22px;
  width: min(1120px, 100%);
  margin: 0 auto;
  padding: 24px 16px 56px;
}

.rank-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  padding: 24px;
  border: 1px solid var(--hairline);
  border-radius: 18px;
  background: var(--surface);
}

.rank-hero h1 {
  margin: 4px 0 8px;
  font-size: 32px;
}

.rank-tabs-wrap {
  display: grid;
  gap: 8px;
}

.rank-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.rank-rule-hint {
  margin: 0;
  color: var(--text-quiet);
  font-size: 13px;
}

.rank-tabs button {
  border: 1px solid var(--hairline);
  border-radius: 999px;
  background: var(--surface);
  color: var(--text);
  padding: 9px 14px;
  font-weight: 700;
  cursor: pointer;
  transition:
    border-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    background-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    color var(--dur-fast, 150ms) var(--ease-standard, ease),
    transform var(--dur-press, 90ms) var(--ease-out, ease);
}

.rank-tabs button:hover {
  border-color: color-mix(in srgb, var(--accent) 28%, var(--hairline));
}

.rank-tabs button:active {
  transform: scale(0.97);
}

.rank-tabs button.active {
  border-color: color-mix(in srgb, var(--accent) 38%, var(--hairline));
  background: color-mix(in srgb, var(--accent) 12%, var(--surface));
  color: var(--accent);
}

.rank-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
  transition: opacity var(--dur-fast, 150ms) var(--ease-standard, ease);
}

.rank-grid.is-loading {
  opacity: 0.56;
  pointer-events: none;
}

.rank-card {
  min-height: 86px;
  display: grid;
  grid-template-columns: auto 46px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--hairline);
  border-radius: 14px;
  background: var(--surface);
  transition:
    border-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    transform var(--dur-fast, 150ms) var(--ease-out, ease);
}

@media (hover: hover) {
  .rank-card:hover {
    transform: translate3d(0, -1px, 0);
    border-color: color-mix(in srgb, var(--accent) 24%, var(--hairline));
  }
}

.rank-card--top-1 {
  border-color: color-mix(in srgb, #f59e0b 45%, var(--hairline));
  background: color-mix(in srgb, #f59e0b 7%, var(--surface));
}

.rank-card--top-2 {
  border-color: color-mix(in srgb, #94a3b8 48%, var(--hairline));
}

.rank-card--top-3 {
  border-color: color-mix(in srgb, #d97706 42%, var(--hairline));
}

.rank-card--self {
  border-color: color-mix(in srgb, var(--accent) 52%, var(--hairline));
  background: color-mix(in srgb, var(--accent) 7%, var(--surface));
}

.rank-card--top-1 .rank-number {
  color: color-mix(in srgb, #d97706 82%, var(--text-strong));
}

.rank-name-line {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.rank-self-badge {
  flex: 0 0 auto;
  padding: 1px 7px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent) 16%, var(--surface-strong));
  color: var(--accent);
  font-size: 11px;
  font-weight: 700;
}

.rank-number {
  color: var(--text-soft);
  font-weight: 800;
  min-width: 34px;
}

.rank-avatar {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  object-fit: cover;
  background: color-mix(in srgb, var(--accent) 13%, var(--surface-strong));
}

.rank-main {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.rank-main strong,
.rank-main span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rank-main span,
.rank-score span,
.rank-empty {
  color: var(--text-soft);
  font-size: 13px;
}

.rank-score {
  display: grid;
  gap: 3px;
  text-align: right;
}

.rank-score strong {
  color: var(--accent);
  font-size: 22px;
}

.rank-empty {
  padding: 24px;
  border: 1px dashed var(--hairline);
  border-radius: 14px;
  text-align: center;
}

@media (max-width: 640px) {
  .rank-hero {
    align-items: stretch;
    flex-direction: column;
  }

  .rank-card {
    grid-template-columns: auto 42px minmax(0, 1fr);
  }

  .rank-score {
    grid-column: 3;
    text-align: left;
  }
}
</style>
