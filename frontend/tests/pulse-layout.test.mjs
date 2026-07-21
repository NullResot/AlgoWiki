import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const pulsePagePath = fileURLToPath(
  new URL("../src/pages/PulseDemoPage.vue", import.meta.url),
);
const source = readFileSync(pulsePagePath, "utf8");
const dailyPlanetPath = fileURLToPath(
  new URL("../src/components/pulse-demo/DailyPlanet.vue", import.meta.url),
);
const dailyPlanetSource = readFileSync(dailyPlanetPath, "utf8");

test("pulse page keeps the operational workspace and removes presentation chrome", () => {
  assert.match(source, /class="pulse-tabs"/);
  assert.doesNotMatch(source, /class="pulse-brandline"/);
  assert.doesNotMatch(source, /class="pulse-title-row"/);
  assert.doesNotMatch(source, /class="pulse-summary"/);
  assert.doesNotMatch(source, /class="pulse-disclaimer"/);
});

test("pulse workspace uses the daily planet without duplicate presentation labels", () => {
  assert.match(source, /<DailyPlanet/);
  assert.match(source, /:business-date="pulse\.state\.edition\?\.date/);
  assert.doesNotMatch(source, /<PulseStar/);
  assert.doesNotMatch(source, /ALGO PULSE|DAILY PLANET RULE|今天只出现一颗星球|自动切换至/);
});

test("pulse workspace declares a readable typography scale", () => {
  assert.match(source, /--pulse-text-xs:\s*12px/);
  assert.match(source, /--pulse-text-sm:\s*14px/);
  assert.match(source, /--pulse-text-md:\s*15px/);
});

test("pulse modules use distinct pearl gradients", () => {
  for (const selector of [
    "signal-card--question",
    "signal-card--challenge",
    "signal-card--poll",
    "orbit-log",
  ]) {
    assert.match(source, new RegExp(`\\.${selector}\\s*\\{[^}]*linear-gradient`, "s"));
  }
});

test("the tempest planet crop removes the source image's black margin", () => {
  assert.match(dailyPlanetSource, /\.daily-planet--a\s*\{\s*--planet-scale:\s*1\.32;/);
});

test("challenge cards acknowledge a click while Codeforces is responding", () => {
  assert.match(source, /const choosingMode = ref\(""\)/);
  assert.match(source, /:aria-busy="choosingMode === 'A'"/);
  assert.match(source, /正在连接 Codeforces/);
  assert.match(source, /正在重新抽取/);
  assert.match(source, /\.mode-card\.choosing/);
});
