<template>
  <section class="discussions-page" lang="zh-CN">
    <div class="pearl-glow pearl-glow--one" aria-hidden="true"></div>
    <div class="pearl-glow pearl-glow--two" aria-hidden="true"></div>
    <div class="page-shell">
      <nav class="community-nav" aria-label="动态社区频道">
        <RouterLink :to="{ name: 'moments' }">社区动态</RouterLink>
        <RouterLink :to="{ name: 'pulse-discussions' }" class="active">每日讨论</RouterLink>
      </nav>

      <header class="archive-hero">
        <div>
          <span class="eyebrow">MIDNIGHT DISCUSSION ARCHIVE</span>
          <h1>每天零点，留下一个值得争论的问题</h1>
          <p>这里收录每一期算法竞赛话题。当天参与会点亮脉冲，往期讨论仍然永久开放。</p>
        </div>
        <div class="hero-orbit" aria-hidden="true"><i></i><span></span></div>
      </header>

      <form class="archive-filter" aria-label="讨论档案筛选" @submit.prevent="applyFilters">
        <label class="search-field">
          <span>搜索讨论</span>
          <div class="search-input-wrap">
            <input v-model.trim="filters.q" placeholder="题目、观点或关键词" />
            <button
              v-if="filters.q"
              type="button"
              class="search-clear"
              aria-label="清空搜索词"
              @click="clearSearch"
            >
              ×
            </button>
          </div>
        </label>
        <div class="order-switch" aria-label="排序方式">
          <button type="button" :class="{ active: filters.ordering === 'newest' }" @click="setOrdering('newest')">最新发布</button>
          <button type="button" :class="{ active: filters.ordering === 'active' }" @click="setOrdering('active')">最近活跃</button>
        </div>
        <label class="mine-switch" :class="{ disabled: !auth.isAuthenticated }">
          <input
            v-model="filters.mine"
            type="checkbox"
            :disabled="!auth.isAuthenticated"
            @change="applyFilters"
          />
          只看我参与
        </label>
        <label class="size-field">每页
          <select v-model.number="filters.page_size" @change="applyFilters">
            <option :value="10">10</option><option :value="20">20</option><option :value="50">50</option>
          </select>
        </label>
        <button class="search-button" type="submit" :disabled="loading">{{ loading ? "检索中..." : "检索" }}</button>
      </form>

      <div class="archive-grid">
        <section class="archive-main" aria-live="polite">
          <div v-if="loading && !archive.results.length" class="state-skeleton">
            <SkeletonBlock :lines="5" :line-height="20" label="正在接收讨论历史信号" />
          </div>
          <div v-else-if="error && !archive.results.length" class="state-error-card" role="alert">
            <strong>信号暂时中断</strong>
            <p>{{ error }}</p>
            <button type="button" @click="load">重新加载</button>
          </div>
          <div v-else :class="{ 'is-dimmed': loading }">
            <DiscussionTimeline :items="archive.results" />
          </div>
          <nav v-if="archive.total_pages > 1" class="pagination" aria-label="讨论分页">
            <button type="button" :disabled="loading || archive.page <= 1" @click="goPage(archive.page - 1)">上一页</button>
            <span>{{ archive.page }} / {{ archive.total_pages }}</span>
            <button type="button" :disabled="loading || archive.page >= archive.total_pages" @click="goPage(archive.page + 1)">下一页</button>
          </nav>
        </section>
        <aside><TopicProposalForm /></aside>
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import SkeletonBlock from "../components/SkeletonBlock.vue";
import DiscussionTimeline from "../components/pulse-discussions/DiscussionTimeline.vue";
import TopicProposalForm from "../components/pulse-discussions/TopicProposalForm.vue";
import pulseApi from "../services/pulse";
import { useAuthStore } from "../stores/auth";
import { safeScrollTo } from "../utils/motion";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const filters = reactive({ q: "", ordering: "newest", mine: false, page: 1, page_size: 20 });
const archive = reactive({ count: 0, page: 1, page_size: 20, total_pages: 1, results: [] });
const loading = ref(false);
const error = ref("");
let loadRequestId = 0;

function readFiltersFromQuery(query) {
  filters.q = typeof query.q === "string" ? query.q.trim() : "";
  filters.ordering = query.ordering === "active" ? "active" : "newest";
  filters.mine = auth.isAuthenticated && query.mine === "1";
  const parsedPage = Number(query.page || 1);
  filters.page = Number.isFinite(parsedPage) && parsedPage >= 1 ? parsedPage : 1;
  const parsedSize = Number(query.page_size || 20);
  filters.page_size = [10, 20, 50].includes(parsedSize) ? parsedSize : 20;
}

function buildQueryFromFilters() {
  const query = {};
  if (filters.q) query.q = filters.q;
  if (filters.ordering !== "newest") query.ordering = filters.ordering;
  if (filters.mine && auth.isAuthenticated) query.mine = "1";
  if (filters.page > 1) query.page = String(filters.page);
  if (filters.page_size !== 20) query.page_size = String(filters.page_size);
  return query;
}

async function load() {
  const currentId = ++loadRequestId;
  loading.value = true;
  error.value = "";
  try {
    const data = await pulseApi.discussions({ ...filters });
    if (currentId !== loadRequestId) return;
    Object.assign(archive, data);
  } catch (requestError) {
    if (currentId !== loadRequestId) return;
    error.value = requestError?.response?.data?.detail || "讨论档案暂时无法读取。";
  } finally {
    if (currentId === loadRequestId) {
      loading.value = false;
    }
  }
}

function syncUrlAndLoad() {
  const nextQuery = buildQueryFromFilters();
  router.replace({ query: nextQuery }).catch(() => {});
  load();
}

function applyFilters() {
  filters.page = 1;
  syncUrlAndLoad();
}

function clearSearch() {
  filters.q = "";
  applyFilters();
}

function setOrdering(value) {
  filters.ordering = value;
  applyFilters();
}

function goPage(page) {
  filters.page = page;
  syncUrlAndLoad();
  safeScrollTo({ top: 0 });
}

watch(
  () => auth.isAuthenticated,
  (signedIn) => {
    if (!signedIn && filters.mine) {
      filters.mine = false;
      applyFilters();
    }
  },
);

onMounted(() => {
  readFiltersFromQuery(route.query);
  load();
});
</script>

<style scoped>
.discussions-page { position: relative; min-height: 100vh; overflow-x: clip; color: #edf0ec; background: radial-gradient(circle at 12% 15%, rgba(18,74,73,.25), transparent 32%), radial-gradient(circle at 88% 8%, rgba(74,45,102,.22), transparent 30%), linear-gradient(145deg, #061014, #080b14 56%, #100d18); }
.discussions-page::before { content: ""; position: fixed; inset: 0; pointer-events: none; opacity: .35; background-image: radial-gradient(circle, rgba(220,195,132,.85) 0 1px, transparent 1.5px), radial-gradient(circle, rgba(117,213,218,.55) 0 1px, transparent 1.5px); background-position: 8% 14%, 72% 32%; background-size: 220px 230px, 310px 290px; }
.pearl-glow { position: absolute; width: 420px; height: 420px; border-radius: 50%; filter: blur(90px); opacity: .14; pointer-events: none; }
.pearl-glow--one { left: -220px; top: 32%; background: #3aa8a4; }.pearl-glow--two { right: -220px; top: 12%; background: #8c5eb3; }
.page-shell { position: relative; z-index: 1; width: min(1420px, calc(100% - 56px)); margin: 0 auto; padding: 26px 0 70px; }
.community-nav { display: flex; gap: 28px; min-height: 48px; align-items: center; border-bottom: 1px solid rgba(255,255,255,.08); }
.community-nav a { position: relative; color: #8c98a3; text-decoration: none; font-size: 14px; transition: color var(--dur-fast) var(--ease-out); }
.community-nav a:hover { color: #d8dfe5; }
.community-nav a.active { color: #f0e8d5; }.community-nav a.active::after { content: ""; position: absolute; left: 0; right: 0; bottom: -16px; height: 2px; background: linear-gradient(90deg,#d7b66e,#56c1ca); box-shadow: 0 0 16px rgba(215,182,110,.5); }
.archive-hero { min-height: 270px; display: flex; align-items: center; justify-content: space-between; gap: 40px; }
.eyebrow { color: #d7b66e; font: 600 11px ui-monospace, monospace; letter-spacing: .19em; }
h1 { max-width: 820px; margin: 18px 0 16px; color: #f3f0e7; font: 600 clamp(34px, 4.5vw, 66px)/1.12 Georgia, "Songti SC", serif; letter-spacing: -.035em; }
.archive-hero p { max-width: 720px; margin: 0; color: #a8b4bd; font-size: 16px; line-height: 1.8; }
.hero-orbit { position: relative; flex: 0 0 170px; aspect-ratio: 1; border: 1px solid rgba(95,196,201,.23); border-radius: 50%; transform: rotate(-18deg); box-shadow: 0 0 70px rgba(74,173,178,.08); }
.hero-orbit::before { content: ""; position: absolute; inset: 30px; border-radius: 50%; background: radial-gradient(circle at 36% 30%, #d8d1c0, #37464c 22%, #081216 67%); box-shadow: inset -18px -13px 30px #010506, 0 0 38px rgba(94,196,201,.18); }
.hero-orbit i { position: absolute; top: 16px; left: 76px; width: 9px; height: 9px; border-radius: 50%; background: #e1bd69; box-shadow: 0 0 18px #e1bd69; }
.archive-filter { display: flex; align-items: end; gap: 12px; padding: 16px; border: 1px solid rgba(157,194,193,.14); border-radius: 19px; background: rgba(7,15,22,.66); backdrop-filter: blur(18px); }
.search-field { flex: 1; min-width: 230px; }.archive-filter label { color: #96a4af; font-size: 12px; }.search-field span { display: block; margin: 0 0 7px 4px; }
.search-input-wrap { position: relative; display: flex; align-items: center; }
.search-clear { position: absolute; right: 8px; width: 26px; height: 26px; border: 0; border-radius: 50%; color: #9aa7b3; background: rgba(255,255,255,.08); font-size: 16px; line-height: 1; cursor: pointer; transition: background-color var(--dur-fast) var(--ease-out), color var(--dur-fast) var(--ease-out); }
.search-clear:hover { color: #f3f0e7; background: rgba(255,255,255,.16); }
.archive-filter input:not([type="checkbox"]), select { min-height: 42px; box-sizing: border-box; border: 1px solid rgba(157,194,193,.16); border-radius: 11px; color: #e9eee9; background: rgba(3,10,15,.72); outline: none; transition: border-color var(--dur-fast) var(--ease-out), box-shadow var(--dur-fast) var(--ease-out); }
.search-field input { width: 100%; padding: 0 38px 0 14px; }
.archive-filter input:not([type="checkbox"]):focus, select:focus { border-color: rgba(213,179,109,.58); box-shadow: 0 0 0 3px rgba(213,179,109,.08); }
.size-field select { color-scheme: dark; padding: 0 12px; }
.order-switch { display: flex; padding: 4px; border: 1px solid rgba(255,255,255,.07); border-radius: 12px; }.order-switch button, .search-button, .pagination button, .state-error-card button { min-height: 36px; border: 0; border-radius: 9px; padding: 0 14px; color: #98a4ae; background: transparent; cursor: pointer; transition: color var(--dur-fast) var(--ease-out), background-color var(--dur-fast) var(--ease-out), border-color var(--dur-fast) var(--ease-out), transform var(--dur-fast) var(--ease-out); }.order-switch button.active { color: #efe6cf; background: rgba(213,179,109,.15); }
.order-switch button:hover, .pagination button:not(:disabled):hover { color: #edf0ec; }
.order-switch button:active, .search-button:not(:disabled):active, .pagination button:not(:disabled):active { transform: scale(0.97); }
.mine-switch { min-height: 42px; display: flex; align-items: center; gap: 8px; padding: 0 8px; cursor: pointer; }.mine-switch.disabled { opacity: .45; cursor: default; }.size-field { display: flex; align-items: center; gap: 7px; }
.search-button { min-height: 42px; color: #e8dfcc; border: 1px solid rgba(213,179,109,.3); background: rgba(102,80,43,.42); }
.search-button:not(:disabled):hover { border-color: rgba(213,179,109,.65); background: rgba(124,97,50,.58); }
.search-button:disabled { opacity: .55; cursor: wait; }
.archive-grid { display: grid; grid-template-columns: minmax(0, 1fr) 350px; gap: 30px; margin-top: 28px; }
.archive-main > div { transition: opacity var(--dur-fast) var(--ease-out); }
.archive-main > .is-dimmed { opacity: .58; pointer-events: none; }
.state-skeleton { padding: 28px; border: 1px solid rgba(157,194,193,.15); border-radius: 22px; background: rgba(11,17,29,.76); }
.state-error-card { display: grid; justify-items: center; gap: 10px; padding: 48px 24px; border: 1px solid rgba(237,154,147,.28); border-radius: 22px; background: rgba(42,18,22,.45); text-align: center; }
.state-error-card strong { color: #f6b2ab; font-size: 16px; }
.state-error-card p { margin: 0; color: #d5b4b1; font-size: 14px; }
.state-error-card button { border: 1px solid rgba(237,154,147,.4); color: #f8dcd9; background: rgba(237,154,147,.12); }
.pagination { display: flex; align-items: center; justify-content: center; gap: 18px; margin: 28px 0; color: #96a4af; font-variant-numeric: tabular-nums; }.pagination button { border: 1px solid rgba(255,255,255,.12); }.pagination button:disabled { opacity: .35; cursor: default; }
.community-nav a:focus-visible, .order-switch button:focus-visible, .search-button:focus-visible, .pagination button:focus-visible, .search-clear:focus-visible { outline: 2px solid rgba(92,205,244,.72); outline-offset: 2px; }
@media (max-width: 980px) { .archive-grid { grid-template-columns: 1fr; } .archive-filter { flex-wrap: wrap; } .search-field { flex-basis: 100%; } .hero-orbit { display: none; } }
@media (max-width: 600px) { .page-shell { width: min(100% - 28px, 1420px); } .archive-hero { min-height: 230px; } .archive-filter { align-items: stretch; } .order-switch { width: 100%; }.order-switch button { flex: 1; } h1 { font-size: 35px; } }
@media (prefers-reduced-motion: reduce) {
  .order-switch button, .search-button, .pagination button, .state-error-card button { transition: color var(--dur-fast) linear, background-color var(--dur-fast) linear, border-color var(--dur-fast) linear; }
  .order-switch button:active, .search-button:not(:disabled):active, .pagination button:not(:disabled):active { transform: none; }
}
</style>
