<template>
  <section class="ranking-panel">
    <header class="ranking-head">
      <div><span>LIVE SIGNAL BOARD</span><h2>脉冲排行榜</h2><p>挑战积分来自 Codeforces 公开完成证据；同分时按更早完成时间排序。</p></div>
      <div class="ranking-switches" aria-label="排行榜类型"><button class="active">总积分</button></div>
    </header>

    <div class="ranking-toolbar">
      <div class="ranking-filter-cluster">
        <div class="ranking-scopes" aria-label="排行榜人群范围">
          <button v-for="item in scopes" :key="item.id" :class="{ active: scope === item.id }" @click="selectScope(item.id)">
            <span>{{ item.label }}</span>
            <small v-if="item.id === 'rating'">{{ ratingRange?.label || "未绑定" }}</small>
          </button>
        </div>
        <p v-if="scope === 'rating'" class="rating-range-note">
          <template v-if="ratingRange">当前 Rating <strong>{{ ratingRange.rating }}</strong><i></i>当前分段 <strong>{{ ratingRange.label }}</strong></template>
          <template v-else>绑定 Codeforces 后将显示你所在的 Rating 分段。</template>
        </p>
      </div>
      <label class="page-size">每页
        <select :value="pageSize" @change="selectPageSize">
          <option :value="10">10 条</option>
          <option :value="20">20 条</option>
          <option :value="50">50 条</option>
        </select>
      </label>
    </div>

    <div class="ranking-table" :class="`page-size-${pageSize}`">
      <div class="ranking-row ranking-row--head"><span>名次</span><span>观测者</span><span>连续</span><span>总积分</span></div>
      <div class="ranking-scroll" tabindex="0" aria-label="排行榜列表">
        <div v-for="entry in displayEntries" :key="`${entry.rank}-${entry.user_id}`" class="ranking-row" :class="{ 'is-self': entry.user_id === currentUserId, 'is-podium': entry.rank <= 3 }">
          <span class="ranking-rank"><i v-if="entry.rank <= 3">✦</i>{{ entry.rank }}</span>
          <span class="ranking-user"><strong>{{ entry.username }}</strong><small>{{ entry.school_name || (entry.rating ? `Rating ${entry.rating}` : "未绑定 Rating") }}</small></span>
          <span class="ranking-trend">{{ entry.current_streak }} 天</span>
          <strong class="ranking-score">{{ entry.points }}</strong>
        </div>
        <div v-if="displayEntries.length === 0" class="ranking-empty">当前范围还没有完成记录</div>
      </div>
    </div>

    <footer class="ranking-footer">
      <p class="ranking-note">共 {{ pagination.count || 0 }} 位观测者，封禁账号默认不进入公开排行。</p>
      <nav class="ranking-pagination" aria-label="排行榜分页">
        <button type="button" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
        <span>第 {{ page }} / {{ totalPages }} 页</span>
        <button type="button" :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</button>
      </nav>
    </footer>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";
import { getRatingBand } from "../../features/pulse/pulseState";
import { useAuthStore } from "../../stores/auth";

const props = defineProps({
  entries: { type: Array, default: () => [] },
  pagination: { type: Object, default: () => ({ count: 0, page: 1, page_size: 20, total_pages: 1 }) },
  rating: { type: [Number, String], default: null },
});
const emit = defineEmits(["change"]);
const auth = useAuthStore();
const scope = ref("global");
const scopes = [{ id: "global", label: "全站" }, { id: "rating", label: "我的 Rating 段" }, { id: "school", label: "我的高校" }];
const displayEntries = computed(() => props.entries || []);
const currentUserId = computed(() => auth.user?.id || 0);
const ratingRange = computed(() => getRatingBand(props.rating));
const page = computed(() => Number(props.pagination.page || 1));
const pageSize = computed(() => Number(props.pagination.page_size || 20));
const totalPages = computed(() => Math.max(1, Number(props.pagination.total_pages || 1)));

function request(pageValue, pageSizeValue = pageSize.value) {
  emit("change", { scope: scope.value, page: pageValue, pageSize: pageSizeValue });
}
function selectScope(value) { scope.value = value; request(1); }
function selectPageSize(event) { request(1, Number(event.target.value)); }
function changePage(value) { request(Math.max(1, Math.min(totalPages.value, value))); }
</script>

<style scoped>
.ranking-panel { height: 100%; min-height: 0; display: flex; flex-direction: column; padding: clamp(22px,3vw,38px); overflow: hidden; border: 1px solid rgba(255,255,255,.08); border-radius: 24px; background: linear-gradient(145deg,rgba(18,32,38,.88),rgba(10,14,25,.92) 58%,rgba(34,24,45,.76)); }
.ranking-head { display:flex; align-items:end; justify-content:space-between; gap:24px; flex:0 0 auto; }.ranking-head span { color:#d9ac5d; font-size:10px; letter-spacing:.18em; }.ranking-head h2 { margin:8px 0; color:#f2f0e8; font:600 clamp(26px,3vw,38px)/1 Georgia,"Songti SC",serif; }.ranking-head p { max-width:650px; margin:0; color:#8995a8; font-size:12px; line-height:1.7; }
.ranking-switches,.ranking-scopes { display:flex; gap:5px; padding:4px; border:1px solid rgba(255,255,255,.07); border-radius:12px; background:rgba(255,255,255,.025); }.ranking-switches button,.ranking-scopes button { min-height:40px; border:0; border-radius:8px; padding:0 13px; color:#78859a; background:transparent; font:inherit; font-size:11px; cursor:pointer; }.ranking-scopes button { display:grid; align-content:center; gap:2px; }.ranking-scopes button small { color:#a9956c; font-size:10px; font-variant-numeric:tabular-nums; }.ranking-switches button.active,.ranking-scopes button.active { color:#171b25; background:linear-gradient(135deg,#dcb45e,#c89a4d); }.ranking-scopes button.active small { color:rgba(23,27,37,.68); }
.ranking-toolbar { display:flex; justify-content:space-between; align-items:flex-start; gap:18px; margin:22px 0 12px; flex:0 0 auto; }.ranking-filter-cluster { display:grid; min-width:0; max-width:100%; gap:8px; }.rating-range-note { display:flex; align-items:center; gap:7px; margin:0 0 0 5px; color:#7f8c9e; font-size:11px; }.rating-range-note strong { color:#d8b76f; font-weight:600; font-variant-numeric:tabular-nums; }.rating-range-note i { width:3px; height:3px; border-radius:50%; background:#4fc4db; box-shadow:0 0 8px rgba(79,196,219,.65); }.page-size { display:flex; align-items:center; gap:9px; color:#7f8c9e; font-size:11px; }.page-size select { min-height:40px; border:1px solid rgba(255,255,255,.09); border-radius:10px; padding:0 32px 0 12px; color:#cbd2d9; background:#101723; }
.ranking-table { min-height:0; overflow:hidden; border:1px solid rgba(255,255,255,.07); border-radius:16px; background:rgba(5,10,18,.28); }.ranking-row { display:grid; grid-template-columns:80px minmax(180px,1fr) 90px 110px; align-items:center; min-height:64px; padding:0 18px; box-sizing:border-box; border-bottom:1px solid rgba(255,255,255,.055); color:#cbd1da; }.ranking-row--head { position:relative; z-index:2; min-height:42px; color:#6f7b8d; background:rgba(22,30,42,.96); font-size:10px; letter-spacing:.08em; }.ranking-scroll { max-height:min(640px,calc(100vh - 390px)); min-height:128px; overflow-y:auto; overscroll-behavior:contain; scrollbar-color:rgba(218,180,92,.42) rgba(255,255,255,.025); }.ranking-scroll .ranking-row:last-child { border-bottom:0; }.ranking-row.is-podium { background:linear-gradient(90deg,rgba(221,174,85,.065),transparent 55%); }.ranking-row.is-self { background:linear-gradient(90deg,rgba(75,193,255,.12),rgba(75,193,255,.025)); box-shadow:inset 2px 0 #5bcaff; }
.ranking-rank { color:#8591a1; font:600 17px Georgia,serif; font-variant-numeric:tabular-nums; }.ranking-rank i { color:#e5b75d; margin-right:8px; font-style:normal; font-size:10px; }.ranking-user { display:grid; gap:5px; }.ranking-user strong { color:#f1f0eb; font-size:14px; }.ranking-user small { color:#738095; font-size:10px; }.ranking-trend { color:#71d3aa; font-size:12px; font-variant-numeric:tabular-nums; }.ranking-score { justify-self:end; color:#f0c46d; font:600 20px Georgia,serif; font-variant-numeric:tabular-nums; }.ranking-empty { min-height:128px; display:grid; place-items:center; color:#697589; font-size:12px; }
.ranking-footer { display:flex; align-items:center; justify-content:space-between; gap:18px; margin-top:14px; flex:0 0 auto; }.ranking-note { margin:0; color:#687487; font-size:10px; }.ranking-pagination { display:flex; align-items:center; gap:10px; color:#8490a0; font-size:11px; }.ranking-pagination button { min-height:40px; border:1px solid rgba(255,255,255,.09); border-radius:10px; padding:0 14px; color:#c5ccd4; background:rgba(255,255,255,.025); cursor:pointer; }.ranking-pagination button:disabled { opacity:.32; cursor:default; }
@media (min-width:1121px) and (max-height:800px) { .ranking-panel { padding:14px 18px; }.ranking-head { align-items:center; }.ranking-head h2 { margin:4px 0 0; font-size:25px; }.ranking-head p { display:none; }.ranking-toolbar { margin:8px 0; }.ranking-scroll { max-height:320px; }.ranking-note { overflow:hidden; white-space:nowrap; text-overflow:ellipsis; } }
@media (max-width:700px) { .ranking-head { display:grid; }.ranking-switches { width:fit-content; }.ranking-toolbar { align-items:flex-end; flex-wrap:wrap; }.ranking-scopes { max-width:100%; overflow-x:auto; }.ranking-row { grid-template-columns:48px minmax(140px,1fr) 60px; padding:0 12px; }.ranking-trend { display:none; }.ranking-row--head span:nth-child(3) { display:none; }.ranking-footer { align-items:flex-end; flex-direction:column; }.ranking-note { align-self:flex-start; }.ranking-scroll { max-height:58vh; } }
</style>
