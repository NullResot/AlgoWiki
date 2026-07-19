<template>
  <section class="atlas-panel">
    <header class="atlas-head">
      <div>
        <span class="atlas-eyebrow">PERSONAL CONSTELLATION · {{ monthLabel }}</span>
        <h2>你的每次参与，都没有消失</h2>
        <p>亮度代表当天完成度；补签修复轨迹，但保留那一天曾经错过的痕迹。</p>
      </div>
      <div class="atlas-score"><strong>{{ totalStars }}</strong><span>本月星能</span></div>
    </header>

    <div class="atlas-grid">
      <div v-for="day in days" :key="day.day" class="atlas-day" :class="dayClass(day)">
        <span class="atlas-day__number">{{ day.day }}</span>
        <i class="atlas-day__star" :style="{ '--level': Math.max(day.level, day.today ? progress : 0) }"></i>
        <small v-if="day.today">TODAY</small>
      </div>
    </div>

    <div class="atlas-foot">
      <div class="streak-card">
        <span class="streak-icon streak-icon--gold">✦</span>
        <div><small>当前连续</small><strong>{{ atlas.current }} 天</strong><p>每日挑战完成后写入签到轨迹</p></div>
      </div>
      <div class="streak-card">
        <span class="streak-icon streak-icon--cyan">◎</span>
        <div><small>历史最长</small><strong>{{ atlas.longest }} 天</strong><p>普通补签与超级补签也会修复轨迹</p></div>
      </div>
      <div class="atlas-tools">
        <div v-if="pendingMakeup" class="makeup-task">
          <span>补签任务 · {{ pendingMakeup.target_date }}</span>
          <a :href="pendingMakeup.assignment?.target?.url" target="_blank" rel="noopener">
            {{ pendingMakeup.assignment?.target?.name || pendingMakeup.assignment?.target_key }}
          </a>
          <button type="button" @click="$emit('check-makeup', pendingMakeup.assignment?.id)">检测 AC</button>
        </div>
        <div class="atlas-tools__line">
          <input v-model="targetDate" type="date" :max="yesterday" aria-label="补签日期" />
          <button type="button" :disabled="wallet.makeup < 1 || !targetDate" @click="$emit('makeup', targetDate, 'normal')">补签 {{ wallet.makeup }}</button>
          <button type="button" :disabled="wallet.super_makeup < 1 || !targetDate" @click="$emit('makeup', targetDate, 'super')">超级 {{ wallet.super_makeup }}</button>
        </div>
        <div class="atlas-tools__line">
          <input v-model.trim="redeemCode" placeholder="输入兑换码" aria-label="兑换码" />
          <button type="button" :disabled="redeemCode.length < 6" @click="redeem">兑换</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  progress: { type: Number, default: 0 },
  atlas: {
    type: Object,
    default: () => ({ current: 0, longest: 0, signed_dates: [], makeups: [] }),
  },
  wallet: {
    type: Object,
    default: () => ({ makeup: 0, super_makeup: 0 }),
  },
  pendingMakeup: { type: Object, default: null },
});
const emit = defineEmits(["makeup", "redeem", "check-makeup"]);
const targetDate = ref("");
const redeemCode = ref("");
const today = new Date();
const year = today.getFullYear();
const month = today.getMonth();
const lastDay = new Date(year, month + 1, 0).getDate();
const signed = computed(() => new Set(props.atlas.signed_dates || []));
const makeupMap = computed(() => new Map((props.atlas.makeups || []).map((item) => [item.target_date, item.kind])));
const days = computed(() =>
  Array.from({ length: lastDay }, (_, index) => {
    const day = index + 1;
    const key = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    const isToday = day === today.getDate();
    const kind = makeupMap.value.get(key);
    return {
      day,
      level: signed.value.has(key) ? 3 : 0,
      today: isToday,
      future: day > today.getDate(),
      repaired: kind === "normal",
      superRepaired: kind === "super",
    };
  }),
);
const monthLabel = computed(() =>
  new Intl.DateTimeFormat("en-US", { month: "short", year: "numeric" }).format(today).toUpperCase(),
);
const totalStars = computed(() => signed.value.size);
const yesterday = computed(() => {
  const value = new Date();
  value.setDate(value.getDate() - 1);
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
});

function redeem() {
  if (redeemCode.value.length < 6) return;
  emit("redeem", redeemCode.value);
  redeemCode.value = "";
}

function dayClass(day) {
  return {
    "is-future": day.future,
    "is-today": day.today,
    "is-repaired": day.repaired,
    "is-super-repaired": day.superRepaired,
  };
}
</script>

<style scoped>
.atlas-panel { padding: clamp(22px, 3vw, 38px); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 24px; background: rgba(10, 14, 25, 0.78); }
.atlas-head { display: flex; justify-content: space-between; gap: 24px; padding-bottom: 26px; border-bottom: 1px solid rgba(255, 255, 255, 0.07); }
.atlas-eyebrow { color: #d9ac5d; font-size: 10px; letter-spacing: 0.2em; }
.atlas-head h2 { margin: 8px 0; color: #f2f0e8; font: 600 clamp(24px, 3vw, 38px)/1.2 Georgia, "Songti SC", serif; }
.atlas-head p { margin: 0; color: #8f9bad; font-size: 13px; }
.atlas-score { display: grid; align-content: center; justify-items: end; min-width: 100px; }
.atlas-score strong { color: #f2c56e; font: 600 42px/1 Georgia, serif; }
.atlas-score span { color: #778398; font-size: 10px; }
.atlas-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 9px; padding: 24px 0; }
.atlas-day { position: relative; min-height: 74px; display: grid; place-items: center; border: 1px solid rgba(255,255,255,0.055); border-radius: 13px; background: rgba(255,255,255,0.018); }
.atlas-day__number { position: absolute; top: 7px; left: 8px; color: #586376; font-size: 9px; }
.atlas-day__star { --level: 0; width: calc(5px + var(--level) * 4px); height: calc(5px + var(--level) * 4px); border-radius: 50%; background: rgba(255, 198, 92, calc(0.16 + var(--level) * 0.24)); box-shadow: 0 0 calc(var(--level) * 8px) rgba(255, 186, 70, calc(var(--level) * 0.22)); }
.atlas-day small { position: absolute; bottom: 6px; color: #e2b45d; font-size: 7px; letter-spacing: .1em; }
.atlas-day.is-today { border-color: rgba(226,180,93,.55); background: rgba(226,180,93,.045); }
.atlas-day.is-repaired { border-style: dashed; border-color: rgba(112,184,255,.55); }
.atlas-day.is-super-repaired .atlas-day__star { background: #dff7ff; box-shadow: 0 0 7px #fff, 0 0 20px #63c9ff; }
.atlas-day.is-future { opacity: .35; }
.atlas-foot { display: grid; grid-template-columns: 1fr 1fr minmax(240px, .8fr); gap: 10px; }
.streak-card, .atlas-tools { display: flex; align-items: center; gap: 12px; padding: 15px; border-radius: 14px; background: rgba(255,255,255,.03); }
.streak-icon { width: 38px; height: 38px; display: grid; place-items: center; border-radius: 50%; }
.streak-icon--gold { color: #f4c267; background: rgba(244,194,103,.1); }
.streak-icon--cyan { color: #66d8ff; background: rgba(102,216,255,.1); }
.streak-card div { display: grid; grid-template-columns: auto auto; align-items: baseline; gap: 6px; }
.streak-card small { color: #8793a7; font-size: 10px; }
.streak-card strong { color: #f2f0e8; font-size: 16px; }
.streak-card p { grid-column: 1 / 3; margin: 3px 0 0; color: #667286; font-size: 9px; }
.atlas-tools { display:grid; gap:7px; }
.makeup-task { display:grid; grid-template-columns:1fr auto; gap:4px 8px; padding:7px; border:1px solid rgba(92,205,244,.22); border-radius:9px; background:rgba(92,205,244,.055); }
.makeup-task span { color:#6ed4f5; font-size:8px; letter-spacing:.08em; }
.makeup-task a { grid-column:1; overflow:hidden; color:#edf5f8; font-size:9px; text-decoration:none; text-overflow:ellipsis; white-space:nowrap; }
.makeup-task button { grid-column:2; grid-row:1 / 3; }
.atlas-tools__line { display:flex; gap:5px; }
.atlas-tools input { min-width:0; width:100%; border:1px solid rgba(255,255,255,.09); border-radius:7px; outline:0; padding:7px 8px; color:#dce2ea; background:rgba(0,0,0,.16); font:inherit; font-size:8px; }
.atlas-tools button { flex:0 0 auto; border:0; border-radius:7px; padding:7px 8px; color:#171c27; background:#dcb05b; font:inherit; font-size:8px; font-weight:800; cursor:pointer; }
.atlas-tools button:disabled { opacity:.3; cursor:not-allowed; }
.legend-dot { width: 13px; height: 13px; border-radius: 50%; }
.legend-dot--repair { border: 1px dashed #65baff; }
.legend-dot--super { background: #e9fbff; box-shadow: 0 0 8px #66cfff; }

@media (min-width: 1121px) {
  .atlas-panel {
    height: 100%;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .atlas-head,
  .atlas-foot { flex: 0 0 auto; }

  .atlas-grid {
    flex: 1 1 auto;
    min-height: 0;
    grid-template-rows: repeat(5, minmax(0, 1fr));
  }

  .atlas-day { min-height: 0; }
}

@media (min-width: 1121px) and (max-height: 800px) {
  .atlas-panel { padding: 14px 18px; }
  .atlas-head { align-items: center; padding-bottom: 9px; }
  .atlas-head h2 { margin: 4px 0 0; font-size: 23px; }
  .atlas-head p { display: none; }
  .atlas-score strong { font-size: 30px; }
  .atlas-grid { gap: 5px; padding: 8px 0; }
  .atlas-day { border-radius: 9px; }
  .atlas-day__number { top: 4px; left: 5px; }
  .atlas-day small { bottom: 3px; }
  .atlas-foot { grid-template-columns: 1fr 1fr minmax(210px, .8fr); gap: 6px; }
  .streak-card,
  .atlas-tools { gap: 6px; padding: 7px 9px; border-radius: 10px; }
  .streak-icon { width: 28px; height: 28px; }
  .streak-card p { display: none; }
  .atlas-tools { gap: 4px; }
}

@media (max-width: 900px) { .atlas-foot { grid-template-columns: 1fr 1fr; } .atlas-tools { grid-column: 1 / 3; } }
@media (max-width: 620px) { .atlas-head { align-items: flex-end; } .atlas-head p { display: none; } .atlas-grid { grid-template-columns: repeat(5, 1fr); } .atlas-day { min-height: 60px; } .atlas-foot { grid-template-columns: 1fr; } .atlas-tools { grid-column: 1; } }
</style>
