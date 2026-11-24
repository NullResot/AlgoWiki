<template>
  <figure
    class="daily-planet"
    :class="[
      `daily-planet--${planet.id.toLowerCase()}`,
      {
        'daily-planet--stage-1': progress >= 1,
        'daily-planet--stage-2': progress >= 2,
        'daily-planet--complete': progress === 3,
      },
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
  width: 72%;
  aspect-ratio: 1;
  background:
    radial-gradient(circle at 38% 34%, rgba(200, 167, 92, 0.2), transparent 44%),
    radial-gradient(circle, rgba(78, 164, 166, 0.22) 10%, transparent 72%);
  opacity: 0.65;
  transition: opacity var(--dur-slow) var(--ease-out), transform var(--dur-slow) var(--ease-out);
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
  transition:
    border-color var(--dur-slow) var(--ease-out),
    box-shadow var(--dur-slow) var(--ease-out);
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
  transition:
    transform var(--dur-slow) var(--ease-out),
    background-color var(--dur-slow) var(--ease-out),
    box-shadow var(--dur-slow) var(--ease-out);
}

.daily-planet--stage-1::before {
  opacity: 0.84;
}

.daily-planet--stage-1 .daily-planet__orbit--inner {
  border-color: rgba(226, 180, 93, 0.56);
  box-shadow: 0 0 22px rgba(226, 180, 93, 0.14);
}

.daily-planet--stage-2 .daily-planet__orbit--outer {
  border-color: rgba(92, 205, 244, 0.54);
  box-shadow: 0 0 28px rgba(92, 205, 244, 0.18);
}

.daily-planet--stage-2 .daily-planet__beacon {
  transform: scale(1.25);
  background: #f0c46b;
  box-shadow: 0 0 22px rgba(240, 196, 107, 0.85);
}

.daily-planet--complete::before {
  opacity: 1;
  transform: scale(1.06);
}

.daily-planet--complete .daily-planet__disc {
  box-shadow:
    0 0 72px rgba(92, 174, 156, 0.28),
    0 0 30px rgba(200, 167, 92, 0.2),
    0 28px 70px rgba(0, 0, 0, 0.46),
    inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

@keyframes planet-float {
  50% { transform: translate3d(0, -6px, 0) scale(1.012); }
}

@media (max-width: 760px) {
  .daily-planet { width: min(88vw, 390px); }
}

@media (prefers-reduced-motion: reduce) {
  .daily-planet__disc { animation: none; }
}
</style>
