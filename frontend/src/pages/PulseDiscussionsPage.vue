<template>
  <main class="discussions-page" lang="zh-CN">
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
          <input v-model.trim="filters.q" placeholder="题目、观点或关键词" />
        </label>
        <div class="order-switch" aria-label="排序方式">
          <button type="button" :class="{ active: filters.ordering === 'newest' }" @click="setOrdering('newest')">最新发布</button>
          <button type="button" :class="{ active: filters.ordering === 'active' }" @click="setOrdering('active')">最近活跃</button>
        </div>
        <label class="mine-switch" :class="{ disabled: !auth.isAuthenticated }">
          <input v-model="filters.mine" type="checkbox" :disabled="!auth.isAuthenticated" />
          只看我参与
        </label>
        <label class="size-field">每页
          <select v-model.number="filters.page_size" @change="applyFilters">
            <option :value="10">10</option><option :value="20">20</option><option :value="50">50</option>
          </select>
        </label>
        <button class="search-button" type="submit">检索</button>
      </form>

      <div class="archive-grid">
        <section class="archive-main" aria-live="polite">
          <p v-if="loading" class="state-line">正在接收历史信号...</p>
          <p v-else-if="error" class="state-line is-error">{{ error }}</p>
          <DiscussionTimeline v-else :items="archive.results" />
          <nav v-if="archive.total_pages > 1" class="pagination" aria-label="讨论分页">
            <button type="button" :disabled="archive.page <= 1" @click="goPage(archive.page - 1)">上一页</button>
            <span>{{ archive.page }} / {{ archive.total_pages }}</span>
            <button type="button" :disabled="archive.page >= archive.total_pages" @click="goPage(archive.page + 1)">下一页</button>
          </nav>
        </section>
        <aside><TopicProposalForm /></aside>
      </div>
    </div>
  </main>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import DiscussionTimeline from "../components/pulse-discussions/DiscussionTimeline.vue";
import TopicProposalForm from "../components/pulse-discussions/TopicProposalForm.vue";
import pulseApi from "../services/pulse";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const filters = reactive({ q: "", ordering: "newest", mine: false, page: 1, page_size: 20 });
const archive = reactive({ count: 0, page: 1, page_size: 20, total_pages: 1, results: [] });
const loading = ref(false);
const error = ref("");

async function load() {
  loading.value = true;
  error.value = "";
  try {
    Object.assign(archive, await pulseApi.discussions({ ...filters }));
  } catch (requestError) {
    error.value = requestError?.response?.data?.detail || "讨论档案暂时无法读取。";
  } finally {
    loading.value = false;
  }
}

function applyFilters() { filters.page = 1; load(); }
function setOrdering(value) { filters.ordering = value; applyFilters(); }
function goPage(page) { filters.page = page; load(); window.scrollTo({ top: 0, behavior: "smooth" }); }

onMounted(load);
</script>

<style scoped>
.discussions-page { position: relative; min-height: 100vh; overflow: hidden; color: var(--text-primary, #edf0ec); background: radial-gradient(circle at 12% 15%, rgba(18,74,73,.25), transparent 32%), radial-gradient(circle at 88% 8%, rgba(74,45,102,.22), transparent 30%), linear-gradient(145deg, #061014, #080b14 56%, #100d18); }
.discussions-page::before { content: ""; position: fixed; inset: 0; pointer-events: none; opacity: .35; background-image: radial-gradient(circle, rgba(220,195,132,.85) 0 1px, transparent 1.5px), radial-gradient(circle, rgba(117,213,218,.55) 0 1px, transparent 1.5px); background-position: 8% 14%, 72% 32%; background-size: 220px 230px, 310px 290px; }
.pearl-glow { position: absolute; width: 420px; height: 420px; border-radius: 50%; filter: blur(90px); opacity: .14; pointer-events: none; }
.pearl-glow--one { left: -220px; top: 32%; background: #3aa8a4; }.pearl-glow--two { right: -220px; top: 12%; background: #8c5eb3; }
.page-shell { position: relative; z-index: 1; width: min(1420px, calc(100% - 56px)); margin: 0 auto; padding: 26px 0 70px; }
.community-nav { display: flex; gap: 28px; min-height: 48px; align-items: center; border-bottom: 1px solid rgba(255,255,255,.08); }
.community-nav a { position: relative; color: var(--text-muted, #7f8c98); text-decoration: none; font-size: 14px; }
.community-nav a.active { color: #f0e8d5; }.community-nav a.active::after { content: ""; position: absolute; left: 0; right: 0; bottom: -16px; height: 2px; background: linear-gradient(90deg,#d7b66e,#56c1ca); box-shadow: 0 0 16px rgba(215,182,110,.5); }
.archive-hero { min-height: 270px; display: flex; align-items: center; justify-content: space-between; gap: 40px; }
.eyebrow { color: #d7b66e; font: 600 11px ui-monospace, monospace; letter-spacing: .19em; }
h1 { max-width: 820px; margin: 18px 0 16px; font: 600 clamp(34px, 4.5vw, 66px)/1.12 Georgia, "Songti SC", serif; letter-spacing: -.035em; }
.archive-hero p { max-width: 720px; margin: 0; color: var(--text-secondary, #9eabb4); font-size: 16px; line-height: 1.8; }
.hero-orbit { position: relative; flex: 0 0 170px; aspect-ratio: 1; border: 1px solid rgba(95,196,201,.23); border-radius: 50%; transform: rotate(-18deg); box-shadow: 0 0 70px rgba(74,173,178,.08); }
.hero-orbit::before { content: ""; position: absolute; inset: 30px; border-radius: 50%; background: radial-gradient(circle at 36% 30%, #d8d1c0, #37464c 22%, #081216 67%); box-shadow: inset -18px -13px 30px #010506, 0 0 38px rgba(94,196,201,.18); }
.hero-orbit i { position: absolute; top: 16px; left: 76px; width: 9px; height: 9px; border-radius: 50%; background: #e1bd69; box-shadow: 0 0 18px #e1bd69; }
.archive-filter { display: flex; align-items: end; gap: 12px; padding: 16px; border: 1px solid rgba(157,194,193,.14); border-radius: 19px; background: rgba(7,15,22,.66); backdrop-filter: blur(18px); }
.search-field { flex: 1; min-width: 230px; }.archive-filter label { color: #86949e; font-size: 11px; }.search-field span { display: block; margin: 0 0 7px 4px; }
.archive-filter input:not([type="checkbox"]), select { min-height: 42px; box-sizing: border-box; border: 1px solid rgba(157,194,193,.16); border-radius: 11px; color: #e9eee9; background: rgba(3,10,15,.72); outline: none; }.search-field input { width: 100%; padding: 0 14px; }
.order-switch { display: flex; padding: 4px; border: 1px solid rgba(255,255,255,.07); border-radius: 12px; }.order-switch button, .search-button, .pagination button { min-height: 36px; border: 0; border-radius: 9px; padding: 0 14px; color: #88959f; background: transparent; cursor: pointer; }.order-switch button.active { color: #efe6cf; background: rgba(213,179,109,.13); }
.mine-switch { min-height: 42px; display: flex; align-items: center; gap: 8px; padding: 0 8px; }.mine-switch.disabled { opacity: .45; }.size-field { display: flex; align-items: center; gap: 7px; }.size-field select { padding: 0 9px; }
.search-button { min-height: 42px; color: #e8dfcc; border: 1px solid rgba(213,179,109,.3); background: rgba(102,80,43,.42); }
.archive-grid { display: grid; grid-template-columns: minmax(0, 1fr) 350px; gap: 30px; margin-top: 28px; }.state-line { padding: 60px; text-align: center; color: #8b98a3; }.state-line.is-error { color: #ed9a93; }
.pagination { display: flex; align-items: center; justify-content: center; gap: 18px; margin: 28px 0; color: #87939d; }.pagination button { border: 1px solid rgba(255,255,255,.1); }.pagination button:disabled { opacity: .35; cursor: default; }
@media (max-width: 980px) { .archive-grid { grid-template-columns: 1fr; } .archive-filter { flex-wrap: wrap; } .search-field { flex-basis: 100%; } .hero-orbit { display: none; } }
@media (max-width: 600px) { .page-shell { width: min(100% - 28px, 1420px); } .archive-hero { min-height: 230px; } .archive-filter { align-items: stretch; } .order-switch { width: 100%; }.order-switch button { flex: 1; } h1 { font-size: 35px; } }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important; } }
</style>
