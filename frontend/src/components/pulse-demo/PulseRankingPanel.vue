<template>
  <section class="ranking-panel">
    <header class="ranking-head">
      <div><span>LIVE SIGNAL BOARD</span><h2>脉冲排行榜</h2><p>挑战积分来自 Codeforces 公开完成证据；同分时按更早完成时间排序。</p></div>
      <div class="ranking-switches" aria-label="排行榜类型"><button class="active">总积分</button></div>
    </header>
    <div class="ranking-scopes" aria-label="排行榜人群范围">
      <button v-for="item in scopes" :key="item.id" :class="{ active: scope === item.id }" @click="selectScope(item.id)">{{ item.label }}</button>
    </div>
    <div class="ranking-table">
      <div class="ranking-row ranking-row--head"><span>名次</span><span>观测者</span><span>连续</span><span>总积分</span></div>
      <div v-for="entry in displayEntries" :key="`${entry.rank}-${entry.user_id}`" class="ranking-row" :class="{ 'is-self': entry.user_id === currentUserId, 'is-podium': entry.rank <= 3 }">
        <span class="ranking-rank"><i v-if="entry.rank <= 3">✦</i>{{ entry.rank }}</span>
        <span class="ranking-user"><strong>{{ entry.username }}</strong><small>{{ entry.school_name || (entry.rating ? `Rating ${entry.rating}` : "未绑定 Rating") }}</small></span>
        <span class="ranking-trend">{{ entry.current_streak }} 天</span>
        <strong class="ranking-score">{{ entry.points }}</strong>
      </div>
      <div v-if="displayEntries.length === 0" class="ranking-empty">当前范围还没有完成记录</div>
    </div>
    <p class="ranking-note">榜单按服务器数据实时读取，封禁账号默认不进入公开排行。</p>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";
import { useAuthStore } from "../../stores/auth";

const props = defineProps({ entries: { type: Array, default: () => [] } });
const emit = defineEmits(["scope-change"]);
const auth = useAuthStore();
const scope = ref("global");
const scopes = [{ id: "global", label: "全站" }, { id: "rating", label: "我的 Rating 段" }, { id: "school", label: "我的高校" }];
const displayEntries = computed(() => props.entries || []);
const currentUserId = computed(() => auth.user?.id || 0);

function selectScope(value) {
  scope.value = value;
  emit("scope-change", value);
}
</script>

<style scoped>
.ranking-panel { padding: clamp(22px, 3vw, 38px); border: 1px solid rgba(255,255,255,.08); border-radius: 24px; background: rgba(10,14,25,.78); }
.ranking-head { display: flex; align-items: end; justify-content: space-between; gap: 24px; }
.ranking-head span { color: #d9ac5d; font-size: 10px; letter-spacing: .18em; }
.ranking-head h2 { margin: 8px 0; color: #f2f0e8; font: 600 clamp(26px,3vw,38px)/1 Georgia,"Songti SC",serif; }
.ranking-head p { max-width: 650px; margin: 0; color: #8995a8; font-size: 12px; line-height: 1.7; }
.ranking-switches, .ranking-scopes { display: flex; gap: 5px; padding: 4px; border: 1px solid rgba(255,255,255,.07); border-radius: 12px; background: rgba(255,255,255,.025); }
.ranking-switches button, .ranking-scopes button { border: 0; border-radius: 8px; padding: 8px 13px; color: #78859a; background: transparent; font: inherit; font-size: 10px; cursor: pointer; }
.ranking-switches button.active, .ranking-scopes button.active { color: #141924; background: #dfb45e; }
.ranking-scopes { width: fit-content; margin: 25px 0 12px; }
.ranking-table { overflow: hidden; border: 1px solid rgba(255,255,255,.07); border-radius: 16px; }
.ranking-row { display: grid; grid-template-columns: 80px minmax(180px,1fr) 80px 110px; align-items: center; min-height: 64px; padding: 0 18px; border-bottom: 1px solid rgba(255,255,255,.055); color: #cbd1da; }
.ranking-row:last-child { border-bottom: 0; }
.ranking-row--head { min-height: 38px; color: #647086; background: rgba(255,255,255,.025); font-size: 9px; letter-spacing: .08em; }
.ranking-row.is-podium { background: linear-gradient(90deg, rgba(221,174,85,.06), transparent 55%); }
.ranking-row.is-self { background: linear-gradient(90deg, rgba(75,193,255,.12), rgba(75,193,255,.025)); box-shadow: inset 2px 0 #5bcaff; }
.ranking-rank { color: #7b8799; font: 600 16px Georgia,serif; }
.ranking-rank i { color: #e5b75d; margin-right: 8px; font-style: normal; font-size: 10px; }
.ranking-user { display: grid; gap: 4px; }
.ranking-user strong { color: #f1f0eb; font-size: 13px; }
.ranking-user small { color: #6f7b8e; font-size: 9px; }
.ranking-trend { color: #71d3aa; font-size: 11px; }
.ranking-score { justify-self: end; color: #f0c46d; font: 600 19px Georgia,serif; }
.ranking-empty { min-height: 96px; display:grid; place-items:center; color:#667286; font-size:11px; }
.ranking-note { margin: 14px 0 0; color: #606c80; font-size: 9px; text-align: right; }

@media (min-width: 1121px) {
  .ranking-panel {
    height: 100%;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .ranking-head,
  .ranking-scopes,
  .ranking-note { flex: 0 0 auto; }

  .ranking-table {
    flex: 0 1 359px;
    min-height: 0;
    display: grid;
    grid-template-rows: 38px repeat(5, minmax(0, 1fr));
  }

  .ranking-row {
    min-height: 0;
    height: 100%;
  }
}

@media (min-width: 1121px) and (max-height: 800px) {
  .ranking-panel { padding: 14px 18px; }
  .ranking-head { align-items: center; }
  .ranking-head h2 { margin: 4px 0 0; font-size: 25px; }
  .ranking-head p { display: none; }
  .ranking-switches button,
  .ranking-scopes button { padding: 6px 10px; }
  .ranking-scopes { margin: 8px 0; }
  .ranking-table { flex-basis: 320px; }
  .ranking-row { padding-inline: 14px; }
  .ranking-user { gap: 1px; }
  .ranking-note {
    margin-top: 6px;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
}

@media (max-width: 700px) { .ranking-head { display: grid; } .ranking-switches { width: fit-content; } .ranking-row { grid-template-columns: 48px minmax(140px,1fr) 60px; padding: 0 12px; } .ranking-trend { display: none; } .ranking-row--head span:nth-child(3) { display:none; } .ranking-scopes { max-width: 100%; overflow-x: auto; } }
</style>
