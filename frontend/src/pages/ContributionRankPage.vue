<template>
  <section class="rank-page">
    <header class="rank-hero">
      <div>
        <p class="kicker">AlgoWiki Contribution</p>
        <h1>贡献榜</h1>
        <p class="meta">
          按 Trick、竞赛 Wiki、赛事协作、社区邀请和高校协作分开展示，方便查看不同方向的贡献情况。
        </p>
      </div>
      <RouterLink v-if="auth.isAuthenticated" class="btn btn-accent" :to="{ name: 'profile-section', params: { section: 'invitation' } }">
        我的邀请
      </RouterLink>
    </header>

    <nav class="rank-tabs" aria-label="贡献榜分类">
      <button
        v-for="item in rankTabs"
        :key="item.key"
        type="button"
        :class="{ active: activeType === item.key }"
        @click="switchType(item.key)"
      >
        {{ item.label }}
      </button>
    </nav>

    <section v-if="loading" class="rank-empty">贡献榜加载中...</section>
    <section v-else-if="!rankResults.length" class="rank-empty">当前暂无贡献数据。</section>
    <section v-else class="rank-grid">
      <article v-for="(item, index) in rankResults" :key="rankKey(item, index)" class="rank-card">
        <span class="rank-number">#{{ index + 1 }}</span>
        <template v-if="activeType === 'schools'">
          <div class="rank-school-mark">{{ schoolInitials(item.school_name) }}</div>
          <div class="rank-main">
            <strong>{{ item.school_name || "未填写学校" }}</strong>
            <span>{{ item.user_count || 0 }} 人参与</span>
          </div>
          <div class="rank-score">
            <strong>{{ item.total_contribution_score || 0 }}</strong>
            <span>总贡献</span>
          </div>
        </template>
        <template v-else>
          <img class="rank-avatar" :src="avatarSrc(item)" :alt="`${item.username || '用户'} 头像`" loading="lazy" />
          <div class="rank-main">
            <strong>{{ item.username }}</strong>
            <span>{{ item.school_name || "未填写学校" }}</span>
          </div>
          <div class="rank-score">
            <strong>{{ displayScore(item) }}</strong>
            <span>{{ activeScoreLabel }}</span>
          </div>
        </template>
      </article>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import api from "../services/api";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const ui = useUiStore();

const rankTabs = [
  { key: "overall", label: "综合贡献", scoreKey: "total_contribution_score", scoreLabel: "综合" },
  { key: "content", label: "内容贡献", scoreKey: "content_contribution_score", scoreLabel: "内容" },
  { key: "trick", label: "Trick 贡献", scoreKey: "trick_contribution_score", scoreLabel: "Trick" },
  { key: "wiki", label: "Wiki 贡献", scoreKey: "wiki_contribution_score", scoreLabel: "Wiki" },
  { key: "competition", label: "赛事贡献", scoreKey: "competition_contribution_score", scoreLabel: "赛事" },
  { key: "community", label: "社区贡献", scoreKey: "community_contribution_score", scoreLabel: "社区" },
  { key: "schools", label: "高校贡献", scoreKey: "total_contribution_score", scoreLabel: "总贡献" },
  { key: "recent", label: "近期贡献", scoreKey: "recent_total_score", scoreLabel: "近 30 天" },
];

const validTypes = new Set(rankTabs.map((item) => item.key));
const activeType = ref(validTypes.has(String(route.query.type || "")) ? String(route.query.type) : "overall");
const rankResults = ref([]);
const loading = ref(false);
const DEFAULT_AVATAR_URL = "/wiki-assets/default-avatar.svg";

const activeTab = computed(() => rankTabs.find((item) => item.key === activeType.value) || rankTabs[0]);
const activeScoreLabel = computed(() => activeTab.value.scoreLabel);

function avatarSrc(item) {
  return item?.avatar_url || DEFAULT_AVATAR_URL;
}

function schoolInitials(value) {
  return String(value || "校").trim().slice(0, 2).toUpperCase();
}

function displayScore(item) {
  return Number(item?.[activeTab.value.scoreKey] || 0);
}

function rankKey(item, index) {
  return activeType.value === "schools" ? `${item.school_name}-${index}` : item.id;
}

async function loadRankings() {
  loading.value = true;
  try {
    const { data } = await api.get("/contribution-rankings/", {
      params: { type: activeType.value, limit: 50 },
    });
    rankResults.value = Array.isArray(data?.results) ? data.results : [];
  } catch (error) {
    ui.error(error?.response?.data?.detail || "贡献榜加载失败");
    rankResults.value = [];
  } finally {
    loading.value = false;
  }
}

async function switchType(type) {
  activeType.value = type;
  await router.replace({ name: "contributions", query: { type } });
  await loadRankings();
}

onMounted(loadRankings);
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

.rank-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.rank-tabs button {
  border: 1px solid var(--hairline);
  border-radius: 999px;
  background: var(--surface);
  color: var(--text);
  padding: 9px 14px;
  font-weight: 700;
  cursor: pointer;
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
}

.rank-number {
  color: var(--text-soft);
  font-weight: 800;
  min-width: 34px;
}

.rank-avatar,
.rank-school-mark {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  object-fit: cover;
  background: color-mix(in srgb, var(--accent) 13%, var(--surface-strong));
}

.rank-school-mark {
  display: grid;
  place-items: center;
  color: var(--accent);
  font-weight: 900;
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
