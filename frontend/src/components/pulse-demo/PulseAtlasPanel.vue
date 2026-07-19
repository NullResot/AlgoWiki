<template>
  <section class="atlas-panel">
    <header class="atlas-head">
      <div>
        <span class="atlas-eyebrow">PERSONAL CONSTELLATION · JUL 2026</span>
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
        <div><small>社区连续</small><strong>12 天</strong><p>回答每日问题形成知识核心</p></div>
      </div>
      <div class="streak-card">
        <span class="streak-icon streak-icon--cyan">◎</span>
        <div><small>训练连续</small><strong>7 天</strong><p>每日挑战形成稳定训练轨道</p></div>
      </div>
      <div class="atlas-legend">
        <span><i class="legend-dot legend-dot--repair"></i>普通补签：虚线修复轨道</span>
        <span><i class="legend-dot legend-dot--super"></i>超级补签：蓝白耀斑</span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from "vue";
import { atlasDays } from "../../features/pulse-demo/pulseDemoData";

const props = defineProps({ progress: { type: Number, default: 0 } });
const days = atlasDays;
const totalStars = computed(() => days.reduce((total, day) => total + day.level, 0) + props.progress);

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
.streak-card, .atlas-legend { display: flex; align-items: center; gap: 12px; padding: 15px; border-radius: 14px; background: rgba(255,255,255,.03); }
.streak-icon { width: 38px; height: 38px; display: grid; place-items: center; border-radius: 50%; }
.streak-icon--gold { color: #f4c267; background: rgba(244,194,103,.1); }
.streak-icon--cyan { color: #66d8ff; background: rgba(102,216,255,.1); }
.streak-card div { display: grid; grid-template-columns: auto auto; align-items: baseline; gap: 6px; }
.streak-card small { color: #8793a7; font-size: 10px; }
.streak-card strong { color: #f2f0e8; font-size: 16px; }
.streak-card p { grid-column: 1 / 3; margin: 3px 0 0; color: #667286; font-size: 9px; }
.atlas-legend { display: grid; gap: 8px; color: #7f8b9e; font-size: 9px; }
.atlas-legend span { display: flex; align-items: center; gap: 7px; }
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
  .atlas-legend { gap: 8px; padding: 7px 9px; border-radius: 10px; }
  .streak-icon { width: 28px; height: 28px; }
  .streak-card p { display: none; }
  .atlas-legend { gap: 4px; }
}

@media (max-width: 900px) { .atlas-foot { grid-template-columns: 1fr 1fr; } .atlas-legend { grid-column: 1 / 3; } }
@media (max-width: 620px) { .atlas-head { align-items: flex-end; } .atlas-head p { display: none; } .atlas-grid { grid-template-columns: repeat(5, 1fr); } .atlas-day { min-height: 60px; } .atlas-foot { grid-template-columns: 1fr; } .atlas-legend { grid-column: 1; } }
</style>
