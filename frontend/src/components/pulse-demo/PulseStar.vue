<template>
  <div
    class="pulse-star"
    :class="[`pulse-star--${progress}`, { 'pulse-star--compact': compact, 'pulse-star--complete': progress === 3 }]"
    role="img"
    :aria-label="`今日算法星已点亮 ${progress} 项，共 3 项`"
  >
    <div class="star-field" aria-hidden="true">
      <i v-for="index in 12" :key="index" :style="particleStyle(index)"></i>
    </div>
    <div class="orbit orbit--outer" :class="{ 'is-live': challengeComplete }">
      <span class="satellite"></span>
    </div>
    <div class="orbit orbit--inner" :class="{ 'is-live': questionComplete }"></div>
    <div class="star-halo"></div>
    <Transition name="star-signal">
      <span v-if="progress" :key="progress" class="star-signal" aria-hidden="true"></span>
    </Transition>
    <div class="star-core" :class="{ 'has-voice': pollComplete }">
      <span class="star-grain star-grain--one"></span>
      <span class="star-grain star-grain--two"></span>
      <span class="star-grain star-grain--three"></span>
    </div>
    <div v-if="!compact" class="star-readout">
      <span class="star-readout__eyebrow">ALGO PULSE</span>
      <Transition name="star-count" mode="out-in">
        <strong :key="progress">{{ progress }}/3</strong>
      </Transition>
      <span>{{ progress === 3 ? "今日星体稳定" : "等待今日信号" }}</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  progress: { type: Number, default: 0 },
  questionComplete: { type: Boolean, default: false },
  challengeComplete: { type: Boolean, default: false },
  pollComplete: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
});

function particleStyle(index) {
  const angle = (index * 137.5) % 360;
  const distance = 33 + ((index * 17) % 38);
  const size = 1 + (index % 3);
  return {
    "--particle-angle": `${angle}deg`,
    "--particle-distance": `${distance / 100}`,
    "--particle-size": `${size}px`,
    "--particle-delay": `${(index % 5) * -0.55}s`,
  };
}
</script>

<style scoped>
.pulse-star {
  --star-size: clamp(240px, 30vw, 390px);
  --star-energy: 0.22;
  position: relative;
  width: var(--star-size);
  aspect-ratio: 1;
  display: grid;
  place-items: center;
  isolation: isolate;
}

.pulse-star--1 { --star-energy: 0.44; }
.pulse-star--2 { --star-energy: 0.7; }
.pulse-star--3 { --star-energy: 1; }

.star-field,
.star-halo,
.orbit,
.star-core {
  position: absolute;
  inset: 50% auto auto 50%;
  transform: translate(-50%, -50%);
  border-radius: 50%;
}

.star-field {
  width: 100%;
  height: 100%;
}

.star-field i {
  position: absolute;
  top: 50%;
  left: 50%;
  width: var(--particle-size);
  height: var(--particle-size);
  border-radius: 50%;
  background: rgba(255, 236, 179, calc(0.3 + var(--star-energy) * 0.55));
  box-shadow: 0 0 8px rgba(255, 199, 94, 0.7);
  transform: rotate(var(--particle-angle)) translateX(calc(var(--star-size) * var(--particle-distance)));
  animation: star-twinkle 3s ease-in-out var(--particle-delay) infinite;
}

.star-halo {
  width: 61%;
  height: 61%;
  background:
    radial-gradient(circle, rgba(255, 221, 134, calc(var(--star-energy) * 0.28)), transparent 48%),
    radial-gradient(circle, rgba(78, 175, 255, calc(var(--star-energy) * 0.18)), transparent 68%);
  filter: blur(18px);
  animation: halo-breathe 4.2s ease-in-out infinite;
}

.star-signal {
  position: absolute;
  inset: 50% auto auto 50%;
  z-index: 2;
  width: 43%;
  aspect-ratio: 1;
  border: 1px solid rgba(242, 195, 107, 0.72);
  border-radius: 50%;
  pointer-events: none;
  box-shadow:
    0 0 18px rgba(242, 195, 107, 0.28),
    inset 0 0 14px rgba(242, 195, 107, 0.12);
}

.pulse-star--2 .star-signal {
  border-color: rgba(88, 216, 255, 0.76);
  box-shadow:
    0 0 20px rgba(88, 216, 255, 0.3),
    inset 0 0 14px rgba(88, 216, 255, 0.12);
}

.pulse-star--3 .star-signal {
  border-color: rgba(166, 142, 255, 0.78);
  box-shadow:
    0 0 24px rgba(166, 142, 255, 0.32),
    0 0 38px rgba(88, 216, 255, 0.16),
    inset 0 0 16px rgba(242, 195, 107, 0.14);
}

.star-signal-enter-active {
  animation: star-signal-burst 0.48s cubic-bezier(0.2, 0.8, 0.2, 1) both;
}

.star-signal-leave-active { transition: opacity 0.1s ease; }
.star-signal-leave-to { opacity: 0; }

.orbit {
  border: 1px solid rgba(126, 163, 208, 0.2);
  transform: translate(-50%, -50%) rotate(-14deg);
  transition: border-color 0.35s ease, box-shadow 0.35s ease;
}

.orbit--outer {
  width: 88%;
  height: 47%;
}

.orbit--inner {
  width: 68%;
  height: 68%;
  border-style: dashed;
  transform: translate(-50%, -50%) rotate(26deg);
}

.orbit.is-live {
  border-color: rgba(79, 211, 255, 0.75);
  box-shadow: 0 0 20px rgba(52, 179, 255, 0.22), inset 0 0 20px rgba(52, 179, 255, 0.1);
}

.orbit--inner.is-live {
  border-color: rgba(255, 203, 101, 0.75);
}

.satellite {
  position: absolute;
  top: 49%;
  right: -4px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #58d8ff;
  box-shadow: 0 0 14px rgba(88, 216, 255, 0.9);
}

.star-core {
  width: 39%;
  height: 39%;
  overflow: hidden;
  background:
    radial-gradient(circle at 33% 29%, rgba(255, 255, 232, calc(0.45 + var(--star-energy) * 0.45)) 0 5%, transparent 17%),
    radial-gradient(circle at 62% 68%, rgba(255, 175, 75, calc(0.35 + var(--star-energy) * 0.5)), transparent 29%),
    radial-gradient(circle at 50% 50%, #ffe7a5 0, #f2a33f 44%, #6f3b29 76%, #101423 100%);
  box-shadow:
    0 0 calc(20px + var(--star-energy) * 38px) rgba(255, 178, 66, calc(0.18 + var(--star-energy) * 0.4)),
    inset -18px -18px 36px rgba(26, 17, 37, 0.42),
    inset 10px 10px 24px rgba(255, 250, 211, 0.18);
  filter: saturate(calc(0.65 + var(--star-energy) * 0.55));
  transition: filter 0.5s ease, box-shadow 0.5s ease;
}

.star-core::after {
  content: "";
  position: absolute;
  inset: -20%;
  border-radius: 48%;
  opacity: 0;
  background: repeating-conic-gradient(from 20deg, transparent 0 16deg, rgba(141, 87, 255, 0.3) 18deg 21deg);
  transition: opacity 0.4s ease;
  animation: texture-spin 18s linear infinite;
}

.star-core.has-voice::after { opacity: 1; }

.star-grain {
  position: absolute;
  width: 12%;
  aspect-ratio: 1;
  border-radius: 50%;
  background: rgba(117, 53, 33, 0.2);
  box-shadow: inset 2px 2px 5px rgba(36, 16, 29, 0.28);
}

.star-grain--one { left: 22%; top: 57%; }
.star-grain--two { right: 20%; top: 27%; width: 8%; }
.star-grain--three { right: 28%; bottom: 14%; width: 5%; }

.star-readout {
  position: absolute;
  bottom: 1%;
  left: 50%;
  transform: translateX(-50%);
  display: grid;
  justify-items: center;
  gap: 2px;
  color: #f8f5ea;
  text-shadow: 0 2px 18px rgba(0, 0, 0, 0.75);
}

.star-readout strong {
  font-family: Georgia, "Times New Roman", serif;
  font-size: 24px;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.star-count-enter-active,
.star-count-leave-active {
  transition:
    opacity 0.16s ease,
    transform 0.2s cubic-bezier(0.2, 0.8, 0.2, 1);
}

.star-count-enter-from { opacity: 0; transform: translateY(5px) scale(0.94); }
.star-count-leave-to { opacity: 0; transform: translateY(-4px) scale(0.98); }

.star-readout span:last-child { color: #9ca9bc; font-size: 11px; }
.star-readout__eyebrow { color: #f2bd65; font-size: 9px; letter-spacing: 0.24em; }

.pulse-star--compact { --star-size: 30px; }
.pulse-star--compact .star-field,
.pulse-star--compact .orbit,
.pulse-star--compact .star-readout { display: none; }
.pulse-star--compact .star-core { width: 48%; height: 48%; }
.pulse-star--compact .star-halo { width: 100%; height: 100%; filter: blur(5px); }

@keyframes halo-breathe {
  50% { transform: translate(-50%, -50%) scale(1.14); opacity: 0.75; }
}

@keyframes star-twinkle {
  50% { opacity: 0.25; transform: rotate(var(--particle-angle)) translateX(calc(var(--star-size) * var(--particle-distance))) scale(0.6); }
}

@keyframes texture-spin {
  to { transform: rotate(360deg); }
}

@keyframes star-signal-burst {
  0% { opacity: 0; transform: translate(-50%, -50%) scale(0.72); }
  34% { opacity: 0.92; }
  100% { opacity: 0; transform: translate(-50%, -50%) scale(2.05); }
}

@media (prefers-reduced-motion: reduce) {
  .star-field i,
  .star-halo,
  .star-core::after { animation: none; }

  .star-signal { display: none; }

  .star-count-enter-active,
  .star-count-leave-active {
    transition: opacity 0.12s linear;
  }

  .star-count-enter-from,
  .star-count-leave-to { transform: none; }
}
</style>
