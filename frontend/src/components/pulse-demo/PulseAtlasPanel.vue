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
      <template v-for="day in days" :key="day.dateKey">
        <button
          v-if="day.canRepair"
          type="button"
          class="atlas-day is-clickable"
          :class="[dayClass(day), { 'is-selected': targetDate === day.dateKey }]"
          :title="`点击选择补签日期 ${day.dateKey}`"
          :aria-label="`选择补签日期 ${day.dateKey}`"
          :aria-pressed="targetDate === day.dateKey"
          @click="selectDay(day.dateKey)"
        >
          <span class="atlas-day__number">{{ day.day }}</span>
          <i class="atlas-day__star" :style="{ '--level': Math.max(day.level, day.today ? progress : 0) }"></i>
        </button>
        <div v-else class="atlas-day" :class="dayClass(day)">
          <span class="atlas-day__number">{{ day.day }}</span>
          <i class="atlas-day__star" :style="{ '--level': Math.max(day.level, day.today ? progress : 0) }"></i>
          <small v-if="day.today">TODAY</small>
        </div>
      </template>
    </div>

    <div class="atlas-legend" aria-label="星图图例">
      <span><i class="legend-dot legend-dot--signed"></i>已点亮（点击未点亮过去日期可直接选入补签）</span>
      <span><i class="legend-dot legend-dot--repair"></i>普通补签修复</span>
      <span><i class="legend-dot legend-dot--super"></i>超级补签修复</span>
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
          <button
            type="button"
            :disabled="busyAction === 'check-makeup'"
            @click="$emit('check-makeup', pendingMakeup.assignment?.id)"
          >
            {{ busyAction === "check-makeup" ? "检测中..." : "检测 AC" }}
          </button>
        </div>
        <div class="atlas-tools__line">
          <input v-model="targetDate" type="date" :max="yesterday" aria-label="补签日期" />
          <button
            type="button"
            :disabled="wallet.makeup < 1 || !targetDate || Boolean(busyAction)"
            @click="$emit('makeup', targetDate, 'normal')"
          >
            {{ busyAction === "makeup" ? "处理中..." : `补签 ${wallet.makeup}` }}
          </button>
          <button
            type="button"
            :disabled="wallet.super_makeup < 1 || !targetDate || Boolean(busyAction)"
            @click="$emit('makeup', targetDate, 'super')"
          >
            {{ busyAction === "makeup" ? "处理中..." : `超级 ${wallet.super_makeup}` }}
          </button>
        </div>
        <div class="atlas-tools__line">
          <input v-model.trim="redeemCode" placeholder="输入兑换码（至少 6 位）" aria-label="兑换码" @keyup.enter="redeem" />
          <button type="button" :disabled="redeemCode.length < 6 || Boolean(busyAction)" @click="redeem">
            {{ busyAction === "redeem" ? "兑换中..." : "兑换" }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";

import { getShanghaiDateKey } from "../../features/pulse/pulseState";

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
  busyAction: { type: String, default: "" },
});
const emit = defineEmits(["makeup", "redeem", "check-makeup"]);
const targetDate = ref("");
const redeemCode = ref("");
const shanghaiTodayKey = computed(() => getShanghaiDateKey());
const dateParts = computed(() => {
  const [y, m, d] = shanghaiTodayKey.value.split("-").map((v) => Number(v));
  return {
    year: y || new Date().getFullYear(),
    month: m ? m - 1 : new Date().getMonth(),
    day: d || new Date().getDate(),
  };
});
const lastDay = computed(() => new Date(Date.UTC(dateParts.value.year, dateParts.value.month + 1, 0)).getUTCDate());
const signed = computed(() => new Set(props.atlas.signed_dates || []));
const makeupMap = computed(() => new Map((props.atlas.makeups || []).map((item) => [item.target_date, item.kind])));
const days = computed(() => {
  const { year, month, day: todayDay } = dateParts.value;
  return Array.from({ length: lastDay.value }, (_, index) => {
    const day = index + 1;
    const key = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    const isToday = day === todayDay;
    const isFuture = day > todayDay;
    const isSigned = signed.value.has(key);
    const kind = makeupMap.value.get(key);
    return {
      day,
      dateKey: key,
      level: isSigned ? 3 : 0,
      today: isToday,
      future: isFuture,
      repaired: kind === "normal",
      superRepaired: kind === "super",
      canRepair: !isFuture && !isToday && !isSigned,
    };
  });
});
const monthLabel = computed(() => {
  const { year, month } = dateParts.value;
  return new Intl.DateTimeFormat("en-US", { month: "short", year: "numeric", timeZone: "UTC" })
    .format(new Date(Date.UTC(year, month, 1)))
    .toUpperCase();
});
const totalStars = computed(() => signed.value.size);
const yesterday = computed(() => {
  const { year, month, day } = dateParts.value;
  const value = new Date(Date.UTC(year, month, day));
  value.setUTCDate(value.getUTCDate() - 1);
  return `${value.getUTCFullYear()}-${String(value.getUTCMonth() + 1).padStart(2, "0")}-${String(value.getUTCDate()).padStart(2, "0")}`;
});

function selectDay(dateKey) {
  targetDate.value = targetDate.value === dateKey ? "" : dateKey;
}

function redeem() {
  if (redeemCode.value.length < 6 || props.busyAction) return;
  emit("redeem", redeemCode.value, () => {
    redeemCode.value = "";
  });
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
.atlas-head { display: flex; justify-content: space-between; gap: 24px; padding-bottom: 24px; border-bottom: 1px solid rgba(255, 255, 255, 0.07); }
.atlas-eyebrow { color: #d9ac5d; font-size: 11px; letter-spacing: 0.2em; }
.atlas-head h2 { margin: 8px 0; color: #f2f0e8; font: 600 clamp(24px, 3vw, 38px)/1.2 Georgia, "Songti SC", serif; }
.atlas-head p { margin: 0; color: #8f9bad; font-size: 13px; }
.atlas-score { display: grid; align-content: center; justify-items: end; min-width: 100px; }
.atlas-score strong { color: #f2c56e; font: 600 42px/1 Georgia, serif; font-variant-numeric: tabular-nums; }
.atlas-score span { color: #8c98ab; font-size: 11px; }
.atlas-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 9px; padding: 20px 0 12px; }
.atlas-day { position: relative; min-height: 74px; display: grid; place-items: center; padding: 0; font: inherit; color: inherit; border: 1px solid rgba(255,255,255,0.06); border-radius: 13px; background: rgba(255,255,255,0.018); transition: border-color var(--dur-fast) var(--ease-out), background-color var(--dur-fast) var(--ease-out), transform var(--dur-fast) var(--ease-out); }
.atlas-day.is-clickable { cursor: pointer; }
.atlas-day.is-clickable:hover { border-color: rgba(226, 180, 93, 0.42); background: rgba(226, 180, 93, 0.05); transform: translate3d(0, -1px, 0); }
.atlas-day.is-clickable:active { transform: scale(0.97); }
.atlas-day.is-clickable:focus-visible,
.atlas-tools input:focus-visible,
.atlas-tools button:focus-visible { outline: 2px solid rgba(92, 205, 244, 0.72); outline-offset: 2px; }
.atlas-day.is-selected { border-color: #5ccdf4; background: rgba(92, 205, 244, 0.12); box-shadow: 0 0 0 1px rgba(92, 205, 244, 0.35); }
.atlas-day__number { position: absolute; top: 7px; left: 8px; color: #7e8b9f; font-size: 11px; font-variant-numeric: tabular-nums; }
.atlas-day__star { --level: 0; width: calc(5px + var(--level) * 4px); height: calc(5px + var(--level) * 4px); border-radius: 50%; background: rgba(255, 198, 92, calc(0.16 + var(--level) * 0.24)); box-shadow: 0 0 calc(var(--level) * 8px) rgba(255, 186, 70, calc(var(--level) * 0.22)); }
.atlas-day small { position: absolute; bottom: 6px; color: #e2b45d; font-size: 10px; letter-spacing: .08em; }
.atlas-day.is-today { border-color: rgba(226,180,93,.55); background: rgba(226,180,93,.045); }
.atlas-day.is-repaired { border-style: dashed; border-color: rgba(112,184,255,.55); }
.atlas-day.is-super-repaired .atlas-day__star { background: #dff7ff; box-shadow: 0 0 7px #fff, 0 0 20px #63c9ff; }
.atlas-day.is-future { opacity: .35; }
.atlas-legend { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 14px; color: #8c98ab; font-size: 12px; }
.atlas-legend span { display: inline-flex; align-items: center; gap: 7px; }
.atlas-foot { display: grid; grid-template-columns: 1fr 1fr minmax(260px, .9fr); gap: 10px; }
.streak-card, .atlas-tools { display: flex; align-items: center; gap: 12px; padding: 15px; border-radius: 14px; background: rgba(255,255,255,.03); }
.streak-icon { width: 38px; height: 38px; display: grid; place-items: center; border-radius: 50%; }
.streak-icon--gold { color: #f4c267; background: rgba(244,194,103,.1); }
.streak-icon--cyan { color: #66d8ff; background: rgba(102,216,255,.1); }
.streak-card div { display: grid; grid-template-columns: auto auto; align-items: baseline; gap: 6px; }
.streak-card small { color: #8d9ab0; font-size: 12px; }
.streak-card strong { color: #f2f0e8; font-size: 16px; font-variant-numeric: tabular-nums; }
.streak-card p { grid-column: 1 / 3; margin: 3px 0 0; color: #7e8b9f; font-size: 11px; }
.atlas-tools { display:grid; gap:7px; }
.makeup-task { display:grid; grid-template-columns:1fr auto; gap:4px 8px; padding:9px 10px; border:1px solid rgba(92,205,244,.22); border-radius:9px; background:rgba(92,205,244,.055); }
.makeup-task span { color:#6ed4f5; font-size:11px; letter-spacing:.04em; }
.makeup-task a { grid-column:1; overflow:hidden; color:#edf5f8; font-size:12px; text-decoration:none; text-overflow:ellipsis; white-space:nowrap; }
.makeup-task button { grid-column:2; grid-row:1 / 3; }
.atlas-tools__line { display:flex; gap:6px; }
.atlas-tools input { min-width:0; width:100%; min-height:36px; border:1px solid rgba(255,255,255,.12); border-radius:8px; outline:0; padding:7px 9px; color:#e5eaf0; background:rgba(0,0,0,.22); font:inherit; font-size:12px; color-scheme:dark; }
.atlas-tools button { flex:0 0 auto; min-height:36px; border:0; border-radius:8px; padding:7px 11px; color:#171c27; background:#dcb05b; font:inherit; font-size:12px; font-weight:800; cursor:pointer; font-variant-numeric:tabular-nums; transition: opacity var(--dur-fast) var(--ease-out), transform var(--dur-fast) var(--ease-out); }
.atlas-tools button:not(:disabled):active { transform:scale(.97); }
.atlas-tools button:disabled { opacity:.35; cursor:not-allowed; }
.legend-dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
.legend-dot--signed { background: #ffc65c; box-shadow: 0 0 8px rgba(255, 186, 70, 0.5); }
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

@media (prefers-reduced-motion: reduce) {
  .atlas-day.is-clickable,
  .atlas-tools button {
    transition: border-color var(--dur-fast) linear, background-color var(--dur-fast) linear, opacity var(--dur-fast) linear;
  }

  .atlas-day.is-clickable:hover,
  .atlas-day.is-clickable:active,
  .atlas-tools button:not(:disabled):active {
    transform: none;
  }
}
</style>
