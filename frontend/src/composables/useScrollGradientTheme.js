import { onBeforeUnmount, onMounted } from "vue";

const stops = [
  { p: 0.0, accent: "#7C5CFF", bg1: "hsla(270,95%,75%,.14)", bg2: "hsla(210,95%,72%,.12)", bg3: "hsla(300,80%,75%,.10)" },
  { p: 0.33, accent: "#4B8DFF", bg1: "hsla(220,95%,75%,.14)", bg2: "hsla(205,95%,72%,.12)", bg3: "hsla(260,75%,75%,.10)" },
  { p: 0.66, accent: "#22A370", bg1: "hsla(165,85%,72%,.12)", bg2: "hsla(205,95%,72%,.10)", bg3: "hsla(150,70%,72%,.10)" },
  { p: 1.0, accent: "#FF7A59", bg1: "hsla(18,95%,75%,.12)", bg2: "hsla(40,95%,74%,.10)", bg3: "hsla(205,95%,72%,.08)" },
];

function clamp01(value) {
  return Math.max(0, Math.min(1, value));
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function parseHexColor(hex) {
  const normalized = String(hex || "").trim().replace("#", "");
  if (!/^[0-9a-fA-F]{6}$/.test(normalized)) return { r: 124, g: 92, b: 255 };
  return {
    r: parseInt(normalized.slice(0, 2), 16),
    g: parseInt(normalized.slice(2, 4), 16),
    b: parseInt(normalized.slice(4, 6), 16),
  };
}

function toRgbString(color) {
  return `rgb(${Math.round(color.r)}, ${Math.round(color.g)}, ${Math.round(color.b)})`;
}

function parseHslaColor(value) {
  const raw = String(value || "").trim();
  const match = raw.match(/hsla?\(([^)]+)\)/i);
  if (!match) return { h: 220, s: 95, l: 72, a: 0.12 };
  const tokens = match[1].split(",").map((item) => item.trim());
  if (tokens.length < 3) return { h: 220, s: 95, l: 72, a: 0.12 };
  return {
    h: Number.parseFloat(tokens[0]) || 0,
    s: Number.parseFloat(tokens[1].replace("%", "")) || 0,
    l: Number.parseFloat(tokens[2].replace("%", "")) || 0,
    a: tokens[3] == null ? 1 : Number.parseFloat(tokens[3]) || 0,
  };
}

function toHslaString(color) {
  return `hsla(${color.h.toFixed(2)}, ${color.s.toFixed(2)}%, ${color.l.toFixed(2)}%, ${color.a.toFixed(3)})`;
}

function interpolateColorStops(left, right, t) {
  const accentLeft = parseHexColor(left.accent);
  const accentRight = parseHexColor(right.accent);
  const bg1Left = parseHslaColor(left.bg1);
  const bg1Right = parseHslaColor(right.bg1);
  const bg2Left = parseHslaColor(left.bg2);
  const bg2Right = parseHslaColor(right.bg2);
  const bg3Left = parseHslaColor(left.bg3);
  const bg3Right = parseHslaColor(right.bg3);

  return {
    accent: toRgbString({
      r: lerp(accentLeft.r, accentRight.r, t),
      g: lerp(accentLeft.g, accentRight.g, t),
      b: lerp(accentLeft.b, accentRight.b, t),
    }),
    bg1: toHslaString({
      h: lerp(bg1Left.h, bg1Right.h, t),
      s: lerp(bg1Left.s, bg1Right.s, t),
      l: lerp(bg1Left.l, bg1Right.l, t),
      a: lerp(bg1Left.a, bg1Right.a, t),
    }),
    bg2: toHslaString({
      h: lerp(bg2Left.h, bg2Right.h, t),
      s: lerp(bg2Left.s, bg2Right.s, t),
      l: lerp(bg2Left.l, bg2Right.l, t),
      a: lerp(bg2Left.a, bg2Right.a, t),
    }),
    bg3: toHslaString({
      h: lerp(bg3Left.h, bg3Right.h, t),
      s: lerp(bg3Left.s, bg3Right.s, t),
      l: lerp(bg3Left.l, bg3Right.l, t),
      a: lerp(bg3Left.a, bg3Right.a, t),
    }),
  };
}

function pickTheme(progress) {
  const p = clamp01(progress);
  let left = stops[0];
  let right = stops[stops.length - 1];

  for (let i = 0; i < stops.length - 1; i += 1) {
    if (p >= stops[i].p && p <= stops[i + 1].p) {
      left = stops[i];
      right = stops[i + 1];
      break;
    }
  }

  const t = clamp01((p - left.p) / (right.p - left.p || 1));
  return interpolateColorStops(left, right, t);
}

export function useScrollGradientTheme() {
  let rafId = 0;

  const update = () => {
    rafId = 0;
    const max = document.body.scrollHeight - window.innerHeight;
    const progress = max > 0 ? window.scrollY / max : 0;
    const theme = pickTheme(progress);
    const root = document.documentElement;

    root.style.setProperty("--accent", theme.accent);
    root.style.setProperty("--bg-1", theme.bg1);
    root.style.setProperty("--bg-2", theme.bg2);
    root.style.setProperty("--bg-3", theme.bg3);
  };

  const onScroll = () => {
    if (rafId) return;
    rafId = window.requestAnimationFrame(update);
  };

  onMounted(() => {
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
  });

  onBeforeUnmount(() => {
    window.removeEventListener("scroll", onScroll);
    if (rafId) {
      window.cancelAnimationFrame(rafId);
    }
  });
}
