<template>
  <figure
    class="daily-planet"
    :class="[
      `daily-planet--${planet.id.toLowerCase()}`,
      { 'daily-planet--complete': progress === 3 },
    ]"
    role="img"
    :aria-label="`今日算法星球：${planet.name}，已完成 ${progress} 项`"
  >
    <span class="daily-planet__orbit daily-planet__orbit--outer" aria-hidden="true"></span>
    <span class="daily-planet__orbit daily-planet__orbit--inner" aria-hidden="true"></span>
    <span class="daily-planet__beacon" aria-hidden="true"></span>
    <span class="daily-planet__disc" aria-hidden="true">
      <img :src="planet.src" alt="" decoding="async" fetchpriority="high" />
    </span>
  </figure>
</template>

<script setup>
import { computed } from "vue";

import oceanUrl from "../../assets/pulse/planet-ocean.webp";
import obsidianUrl from "../../assets/pulse/planet-obsidian.webp";
import tempestUrl from "../../assets/pulse/planet-tempest.webp";
import { getDailyPlanetId } from "../../features/pulse/dailyPlanet";

const props = defineProps({
  businessDate: { type: String, default: "" },
  progress: { type: Number, default: 0 },
});

const planets = Object.freeze({
  A: { id: "A", name: "鎏金风暴", src: tempestUrl },
  B: { id: "B", name: "黑曜熔金", src: obsidianUrl },
  C: { id: "C", name: "极光深海", src: oceanUrl },
});

const planet = computed(() => planets[getDailyPlanetId(props.businessDate)]);
</script>

<style scoped>
.daily-planet {
  --planet-scale: 1.19;
  position: relative;
  width: min(92%, 430px);
  aspect-ratio: 1;
  display: grid;
  place-items: center;
  isolation: isolate;
  margin: 0;
}

.daily-planet::before,
.daily-planet::after {
  content: "";
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}

.daily-planet::before {
  width: 61%;
  aspect-ratio: 1;
  background:
    radial-gradient(circle at 38% 34%, rgba(200, 167, 92, 0.2), transparent 36%),
    radial-gradient(circle, rgba(78, 164, 166, 0.2), transparent 69%);
  filter: blur(22px);
}

.daily-planet::after {
  width: 72%;
  aspect-ratio: 1;
  border: 1px solid rgba(200, 167, 92, 0.08);
  box-shadow: inset 0 0 48px rgba(90, 153, 184, 0.05);
}

.daily-planet__disc {
  position: relative;
  z-index: 2;
  width: 68%;
  aspect-ratio: 1;
  overflow: hidden;
  border: 1px solid rgba(213, 190, 126, 0.2);
  border-radius: 50%;
  background: #03080b;
  box-shadow:
    0 0 55px rgba(74, 167, 174, 0.18),
    0 28px 70px rgba(0, 0, 0, 0.46),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
  animation: planet-float 7s ease-in-out infinite;
}

.daily-planet__disc::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background:
    radial-gradient(circle at 30% 24%, rgba(255, 245, 210, 0.11), transparent 22%),
    linear-gradient(135deg, transparent 42%, rgba(0, 0, 0, 0.22) 76%);
  mix-blend-mode: screen;
  pointer-events: none;
}

.daily-planet__disc img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
  transform: scale(var(--planet-scale));
  filter: saturate(0.9) contrast(1.05);
}

.daily-planet--a { --planet-scale: 1.32; }
.daily-planet--b { --planet-scale: 1.2; }
.daily-planet--c { --planet-scale: 1.18; }

.daily-planet__orbit {
  position: absolute;
  border: 1px solid rgba(93, 174, 169, 0.24);
  border-radius: 50%;
  pointer-events: none;
}

.daily-planet__orbit--outer {
  width: 88%;
  height: 48%;
  transform: rotate(-14deg);
  box-shadow: 0 0 24px rgba(90, 153, 184, 0.04);
}

.daily-planet__orbit--inner {
  width: 70%;
  height: 70%;
  border-color: rgba(200, 167, 92, 0.2);
  border-style: dashed;
  transform: rotate(24deg);
}

.daily-planet__beacon {
  position: absolute;
  z-index: 3;
  top: 27%;
  right: 7%;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #74c9d7;
  box-shadow: 0 0 18px #74c9d7;
}

.daily-planet--complete .daily-planet__disc {
  box-shadow:
    0 0 72px rgba(92, 174, 156, 0.28),
    0 0 30px rgba(200, 167, 92, 0.2),
    0 28px 70px rgba(0, 0, 0, 0.46),
    inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

@keyframes planet-float {
  50% { transform: translateY(-6px) scale(1.012); }
}

@media (max-width: 760px) {
  .daily-planet { width: min(88vw, 390px); }
}

@media (prefers-reduced-motion: reduce) {
  .daily-planet__disc { animation: none; }
}
</style>
