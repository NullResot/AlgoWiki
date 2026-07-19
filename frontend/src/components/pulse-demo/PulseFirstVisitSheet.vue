<template>
  <section class="pulse-sheet" aria-labelledby="pulse-sheet-title">
    <div class="pulse-sheet__glow" aria-hidden="true"></div>
    <button class="pulse-sheet__close" type="button" aria-label="今天不再自动展开" @click="$emit('close')">×</button>
    <div class="pulse-sheet__signal">
      <span class="pulse-sheet__date">{{ displayDate }}</span>
      <span class="pulse-sheet__line"></span>
      <span>00:00 已刷新</span>
    </div>
    <div class="pulse-sheet__copy">
      <span class="pulse-sheet__eyebrow">MIDNIGHT PULSE · DEMO</span>
      <h2 id="pulse-sheet-title">今夜，AlgoWiki 收到三束新信号</h2>
      <p>一个值得争论的问题、一条只属于你的训练轨道，以及全站观点正在形成的星体纹理。</p>
    </div>
    <ol class="pulse-sheet__events">
      <li :class="{ done: progress > 0 }"><span>01</span><strong>回答今日脑洞</strong><small>点亮知识核心</small></li>
      <li :class="{ done: progress > 1 }"><span>02</span><strong>完成 A / B 挑战</strong><small>点亮训练轨道</small></li>
      <li :class="{ done: progress > 2 }"><span>03</span><strong>投下今日立场</strong><small>写入星体纹理</small></li>
    </ol>
    <div class="pulse-sheet__action">
      <div class="pulse-sheet__progress">
        <strong>{{ progress }}/3</strong>
        <span>今日观测进度</span>
      </div>
      <RouterLink :to="{ name: 'pulse-demo' }" class="pulse-sheet__button" @click="$emit('close')">
        进入午夜脉冲剧场 <span>↗</span>
      </RouterLink>
    </div>
  </section>
</template>

<script setup>
import { computed } from "vue";
import { RouterLink } from "vue-router";

defineProps({ progress: { type: Number, default: 0 } });
defineEmits(["close"]);

const displayDate = computed(() =>
  new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", weekday: "short" }).format(new Date())
);
</script>

<style scoped>
.pulse-sheet {
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: minmax(220px, 1.2fr) minmax(420px, 1.7fr) auto;
  align-items: center;
  gap: clamp(20px, 3vw, 44px);
  margin: 8px 0 18px;
  padding: clamp(24px, 3vw, 38px);
  border: 1px solid color-mix(in srgb, #d7ad62 30%, var(--hairline));
  border-radius: 24px;
  color: #f4f1e8;
  background:
    linear-gradient(120deg, rgba(17, 21, 34, 0.98), rgba(22, 27, 43, 0.96)),
    var(--surface-strong);
  box-shadow: 0 22px 60px rgba(15, 20, 31, 0.16);
  animation: sheet-arrive 0.55s cubic-bezier(0.2, 0.8, 0.2, 1) both;
}

.pulse-sheet__glow {
  position: absolute;
  width: 350px;
  height: 350px;
  right: -80px;
  top: -200px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(224, 171, 75, 0.2), transparent 66%);
  pointer-events: none;
}

.pulse-sheet__close {
  position: absolute;
  top: 12px;
  right: 14px;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 50%;
  color: #9ba5b6;
  background: rgba(255, 255, 255, 0.06);
  font-size: 20px;
  cursor: pointer;
}

.pulse-sheet__signal { align-self: stretch; display: grid; align-content: center; gap: 10px; color: #9ca8bb; font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase; }
.pulse-sheet__date { color: #eac172; font: 700 22px/1 Georgia, "Times New Roman", serif; letter-spacing: 0.04em; }
.pulse-sheet__line { width: 80px; height: 1px; background: linear-gradient(90deg, #dda84a, transparent); }
.pulse-sheet__eyebrow { color: #dda84a; font-size: 10px; font-weight: 750; letter-spacing: 0.2em; }
.pulse-sheet__copy h2 { max-width: 620px; margin: 8px 0 9px; font: 600 clamp(24px, 2.7vw, 38px)/1.12 Georgia, "Times New Roman", "Songti SC", serif; letter-spacing: -0.025em; }
.pulse-sheet__copy p { max-width: 660px; margin: 0; color: #aab3c1; font-size: 13px; line-height: 1.75; }

.pulse-sheet__events {
  grid-column: 1 / 3;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.pulse-sheet__events li { display: grid; grid-template-columns: auto 1fr; column-gap: 10px; padding: 12px 14px; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 13px; background: rgba(255, 255, 255, 0.025); }
.pulse-sheet__events li > span { grid-row: 1 / 3; color: #566075; font: 700 10px/1.4 Georgia, serif; }
.pulse-sheet__events strong { font-size: 12px; }
.pulse-sheet__events small { color: #818c9f; font-size: 10px; margin-top: 2px; }
.pulse-sheet__events li.done { border-color: rgba(76, 200, 154, 0.3); background: rgba(76, 200, 154, 0.06); }
.pulse-sheet__events li.done > span { color: #66d4a7; }

.pulse-sheet__action { grid-row: 1 / 3; grid-column: 3; display: grid; justify-items: end; gap: 18px; min-width: 210px; }
.pulse-sheet__progress { text-align: right; }
.pulse-sheet__progress strong { display: block; color: #f2c56e; font: 600 32px/1 Georgia, serif; }
.pulse-sheet__progress span { color: #7f8a9d; font-size: 10px; }
.pulse-sheet__button { display: inline-flex; align-items: center; gap: 18px; padding: 13px 17px; border-radius: 12px; color: #181d2a; background: #e6b95e; text-decoration: none; font-size: 12px; font-weight: 800; box-shadow: 0 10px 26px rgba(216, 163, 70, 0.18); }
.pulse-sheet__button:hover { background: #f0c873; transform: translateY(-1px); }

@keyframes sheet-arrive { from { opacity: 0; transform: translateY(-14px); } }

@media (max-width: 960px) {
  .pulse-sheet { grid-template-columns: 1fr; }
  .pulse-sheet__signal { align-self: auto; grid-template-columns: auto 60px auto; align-items: center; justify-content: start; }
  .pulse-sheet__events { grid-column: 1; }
  .pulse-sheet__action { grid-row: auto; grid-column: 1; grid-template-columns: auto 1fr; align-items: center; justify-items: stretch; }
  .pulse-sheet__progress { text-align: left; }
  .pulse-sheet__button { justify-self: end; }
}

@media (max-width: 620px) {
  .pulse-sheet { margin-top: 4px; padding: 24px 18px 18px; border-radius: 18px; gap: 18px; }
  .pulse-sheet__events { grid-template-columns: 1fr; }
  .pulse-sheet__action { grid-template-columns: 1fr; }
  .pulse-sheet__button { width: 100%; justify-content: space-between; }
}

@media (prefers-reduced-motion: reduce) { .pulse-sheet { animation: none; } }
</style>
