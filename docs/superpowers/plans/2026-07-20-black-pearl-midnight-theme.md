# Black Pearl Midnight Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已经确认的「孔雀金丝」黑珍珠 Midnight 主题和按北京时间每日轮换的单颗拟真星球落地到 AlgoWiki，同时保持现有顶栏结构、Pulse 业务逻辑和正式环境不受影响。

**Architecture:** 主题材质继续由全局 CSS 变量和现有 `TopNav` 样式承担，Pulse 页面只消费主题，不创建第二套导航。每日星球由一个纯日期选择函数和一个只渲染当天资源的 Vue 组件组成，业务日期来自现有 `/api/pulse/today/` 返回的 `edition.date`；Pulse store 继续负责午夜刷新，并在页面重新可见时补做跨日检查。

**Tech Stack:** Vue 3、Pinia、Vite 6、Node.js `node:test`、CSS 自定义属性与渐变、WebP 静态资源、Django Pulse API（只回归验证，不修改契约）

---

## 文件结构

- Create: `frontend/src/features/pulse/dailyPlanet.js` — 严格解析 `YYYY-MM-DD` 并按固定锚点返回 `A | B | C`。
- Create: `frontend/src/components/pulse-demo/DailyPlanet.vue` — 只渲染当天一张 WebP，负责圆形裁切、轨道、完成光晕和无障碍名称。
- Create: `frontend/src/assets/pulse/planet-tempest.webp` — A「鎏金风暴」运行时资源。
- Create: `frontend/src/assets/pulse/planet-obsidian.webp` — B「黑曜熔金」运行时资源。
- Create: `frontend/src/assets/pulse/planet-ocean.webp` — C「极光深海」运行时资源。
- Modify: `frontend/src/features/pulse/pulseState.js` — 增加北京时间日期键与跨日判断纯函数。
- Modify: `frontend/src/stores/pulse.js` — 页面恢复可见时比较业务日期，必要时刷新当天数据。
- Modify: `frontend/src/pages/PulseDemoPage.vue` — 用 `DailyPlanet` 替换 CSS 算法星，升级模块渐变和字号，不改变问答/挑战/投票结构与事件。
- Keep: `frontend/src/components/pulse-demo/PulseStar.vue` — 页面中央不再使用，但顶栏 `PulseHeaderEntry` 的 compact 状态仍复用该组件。
- Modify: `frontend/src/assets/theme.css` — 将 Midnight 变量和全站背景升级为黑珍珠、孔雀虹彩与静态星光材质。
- Modify: `frontend/src/components/TopNav.vue` — 只修改 scoped CSS，让现有顶栏在 Midnight 下获得黑珍珠材质；不改变模板、顺序、断点或事件。
- Modify: `frontend/src/stores/theme.js` — 更新 Midnight 的展示名称与描述，标识仍为 `midnight`。
- Create: `frontend/tests/daily-planet.test.mjs` — 覆盖锚点、负偏移、跨月、跨年和无效日期。
- Create: `frontend/tests/daily-planet-component.test.mjs` — 校验组件只包含一个 `<img>`、三张 WebP 映射和无轮播控制。
- Create: `frontend/tests/pulse-store-lifecycle.test.mjs` — 校验 visibility 生命周期接线和同日不刷新策略。
- Create: `frontend/tests/midnight-theme.test.mjs` — 校验主题语义变量、星光层和顶栏 DOM 未被重构。
- Modify: `frontend/tests/pulse-layout.test.mjs` — 校验 DailyPlanet 集成、预览说明清理和可读字号。

### Task 1: 每日星球选择纯函数

**Files:**
- Create: `frontend/tests/daily-planet.test.mjs`
- Create: `frontend/src/features/pulse/dailyPlanet.js`

- [ ] **Step 1: 写入失败测试**

```js
import test from "node:test";
import assert from "node:assert/strict";

import { getDailyPlanetId } from "../src/features/pulse/dailyPlanet.js";

test("daily planet follows the Beijing business-date anchor", () => {
  assert.equal(getDailyPlanetId("2026-07-19"), "C");
  assert.equal(getDailyPlanetId("2026-07-20"), "A");
  assert.equal(getDailyPlanetId("2026-07-21"), "B");
  assert.equal(getDailyPlanetId("2026-07-22"), "C");
});

test("daily planet remains deterministic across month and year boundaries", () => {
  assert.equal(getDailyPlanetId("2026-08-01"), "A");
  assert.equal(getDailyPlanetId("2026-12-31"), "C");
  assert.equal(getDailyPlanetId("2027-01-01"), "A");
});

test("invalid or missing dates fall back to A", () => {
  for (const value of [undefined, "", "2026-02-30", "20-07-2026", "invalid"]) {
    assert.equal(getDailyPlanetId(value), "A");
  }
});
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd frontend && node --test tests/daily-planet.test.mjs`

Expected: FAIL，错误包含 `ERR_MODULE_NOT_FOUND`。

- [ ] **Step 3: 写入最小日期实现**

```js
const DAY_MS = 24 * 60 * 60 * 1000;
const ANCHOR_UTC = Date.UTC(2026, 6, 20);
const PLANET_IDS = Object.freeze(["A", "B", "C"]);

function parseBusinessDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const timestamp = Date.UTC(year, month - 1, day);
  const parsed = new Date(timestamp);
  if (
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() !== month - 1 ||
    parsed.getUTCDate() !== day
  ) return null;
  return timestamp;
}

export function getDailyPlanetId(businessDate) {
  const timestamp = parseBusinessDate(businessDate);
  if (timestamp === null) return "A";
  const offset = Math.round((timestamp - ANCHOR_UTC) / DAY_MS);
  return PLANET_IDS[((offset % PLANET_IDS.length) + PLANET_IDS.length) % PLANET_IDS.length];
}
```

- [ ] **Step 4: 运行测试并确认通过**

Run: `cd frontend && node --test tests/daily-planet.test.mjs`

Expected: 3 tests PASS。

- [ ] **Step 5: 提交日期选择逻辑**

```powershell
git add frontend/src/features/pulse/dailyPlanet.js frontend/tests/daily-planet.test.mjs
git commit -m "feat: select the daily pulse planet"
```

### Task 2: 拟真星球资源与单图组件

**Files:**
- Create: `frontend/src/assets/pulse/planet-tempest.webp`
- Create: `frontend/src/assets/pulse/planet-obsidian.webp`
- Create: `frontend/src/assets/pulse/planet-ocean.webp`
- Create: `frontend/tests/daily-planet-component.test.mjs`
- Create: `frontend/src/components/pulse-demo/DailyPlanet.vue`

- [ ] **Step 1: 写入组件契约失败测试**

```js
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const componentPath = fileURLToPath(
  new URL("../src/components/pulse-demo/DailyPlanet.vue", import.meta.url),
);
const source = readFileSync(componentPath, "utf8");

test("daily planet renders exactly one image without carousel controls", () => {
  assert.equal((source.match(/<img\b/g) || []).length, 1);
  assert.doesNotMatch(source, /autoplay|carousel|pause|planet-selector/i);
  assert.match(source, /:src="planet\.src"/);
});

test("daily planet maps all three WebP assets and clips the source square", () => {
  assert.match(source, /planet-tempest\.webp/);
  assert.match(source, /planet-obsidian\.webp/);
  assert.match(source, /planet-ocean\.webp/);
  assert.match(source, /overflow:\s*hidden/);
  assert.match(source, /border-radius:\s*50%/);
});
```

- [ ] **Step 2: 运行测试并确认组件不存在**

Run: `cd frontend && node --test tests/daily-planet-component.test.mjs`

Expected: FAIL，错误包含 `ENOENT`。

- [ ] **Step 3: 转换并复制三张已批准素材**

Use the bundled Python runtime and its WebP-enabled Pillow build to resize each source to 1024×1024 and encode WebP quality 82:

```powershell
$runtimePython = 'C:\Users\28119\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$sourceRoot = 'C:\Users\28119\.codex\generated_images\019f7393-2dcd-7052-9bbc-87b72ebffca1'
$targetRoot = 'frontend\src\assets\pulse'
New-Item -ItemType Directory -Force -Path $targetRoot | Out-Null
& $runtimePython -c "from pathlib import Path; from PIL import Image; source=Path(r'$sourceRoot'); target=Path(r'$targetRoot'); files={'exec-4d9c1b1a-8f9b-409b-8a0f-75ce1c57bc6f.png':'planet-tempest.webp','exec-13c4515c-a91f-4d98-98e8-bf549b25bba0.png':'planet-obsidian.webp','exec-c2da956e-5d1d-4262-a62e-bc5164114c03.png':'planet-ocean.webp'}; [(lambda im,name: (im.thumbnail((1024,1024), Image.Resampling.LANCZOS), im.save(target/name, 'WEBP', quality=82, method=6)))(Image.open(source/src).convert('RGB'), dst) for src,dst in files.items()]"
```

Source mapping:

```text
exec-4d9c1b1a-8f9b-409b-8a0f-75ce1c57bc6f.png -> planet-tempest.webp
exec-13c4515c-a91f-4d98-98e8-bf549b25bba0.png -> planet-obsidian.webp
exec-c2da956e-5d1d-4262-a62e-bc5164114c03.png -> planet-ocean.webp
```

Run after conversion:

```powershell
Get-ChildItem frontend/src/assets/pulse/*.webp | Select-Object Name,Length
```

Expected: 三个文件均存在，每个文件不高于 512000 bytes。

- [ ] **Step 4: 创建单图组件**

```vue
<template>
  <figure
    class="daily-planet"
    :class="[`daily-planet--${planet.id.toLowerCase()}`, { 'daily-planet--complete': progress === 3 }]"
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
import tempestUrl from "../../assets/pulse/planet-tempest.webp";
import obsidianUrl from "../../assets/pulse/planet-obsidian.webp";
import oceanUrl from "../../assets/pulse/planet-ocean.webp";
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
```

Component CSS must implement these exact responsibilities:

```css
.daily-planet { position:relative; width:min(92%, 430px); aspect-ratio:1; display:grid; place-items:center; isolation:isolate; }
.daily-planet__disc { position:relative; z-index:2; width:68%; aspect-ratio:1; overflow:hidden; border-radius:50%; box-shadow:0 0 55px rgba(74,167,174,.18), 0 28px 70px rgba(0,0,0,.46); animation:planet-float 7s ease-in-out infinite; }
.daily-planet__disc img { width:100%; height:100%; display:block; object-fit:cover; transform:scale(var(--planet-scale,1.19)); filter:saturate(.9) contrast(1.05); }
.daily-planet--a { --planet-scale:1.17; }
.daily-planet--b { --planet-scale:1.2; }
.daily-planet--c { --planet-scale:1.18; }
.daily-planet__orbit { position:absolute; border:1px solid rgba(93,174,169,.24); border-radius:50%; }
.daily-planet__orbit--outer { width:88%; height:48%; transform:rotate(-14deg); }
.daily-planet__orbit--inner { width:70%; height:70%; border-style:dashed; border-color:rgba(200,167,92,.2); transform:rotate(24deg); }
.daily-planet__beacon { position:absolute; z-index:3; top:27%; right:7%; width:8px; height:8px; border-radius:50%; background:#74c9d7; box-shadow:0 0 18px #74c9d7; }
.daily-planet--complete .daily-planet__disc { box-shadow:0 0 72px rgba(92,174,156,.28), 0 0 30px rgba(200,167,92,.2), 0 28px 70px rgba(0,0,0,.46); }
@keyframes planet-float { 50% { transform:translateY(-6px) scale(1.012); } }
@media (prefers-reduced-motion:reduce) { .daily-planet__disc { animation:none; } }
```

- [ ] **Step 5: 运行组件和日期测试**

Run: `cd frontend && node --test tests/daily-planet.test.mjs tests/daily-planet-component.test.mjs`

Expected: 5 tests PASS。

- [ ] **Step 6: 提交资源与组件**

```powershell
git add frontend/src/assets/pulse frontend/src/components/pulse-demo/DailyPlanet.vue frontend/tests/daily-planet-component.test.mjs
git commit -m "feat: add realistic daily pulse planets"
```

### Task 3: 北京时间跨日与页面恢复刷新

**Files:**
- Modify: `frontend/src/features/pulse/pulseState.js`
- Modify: `frontend/src/stores/pulse.js`
- Modify: `frontend/tests/pulse-state.test.mjs`
- Create: `frontend/tests/pulse-store-lifecycle.test.mjs`

- [ ] **Step 1: 为北京时间纯函数写失败测试**

Append to `frontend/tests/pulse-state.test.mjs`:

```js
test("Shanghai date comparison refreshes only after the business date changes", () => {
  assert.equal(
    pulseStateModule.getShanghaiDateKey(new Date("2026-07-19T15:59:59Z")),
    "2026-07-19",
  );
  assert.equal(
    pulseStateModule.getShanghaiDateKey(new Date("2026-07-19T16:00:00Z")),
    "2026-07-20",
  );
  assert.equal(
    pulseStateModule.shouldRefreshPulseDate("2026-07-20", new Date("2026-07-20T08:00:00+08:00")),
    false,
  );
  assert.equal(
    pulseStateModule.shouldRefreshPulseDate("2026-07-19", new Date("2026-07-20T08:00:00+08:00")),
    true,
  );
});
```

Create `frontend/tests/pulse-store-lifecycle.test.mjs`:

```js
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const storePath = fileURLToPath(new URL("../src/stores/pulse.js", import.meta.url));
const source = readFileSync(storePath, "utf8");

test("pulse store rechecks the business date when the page becomes visible", () => {
  assert.match(source, /visibilitychange/);
  assert.match(source, /shouldRefreshPulseDate/);
  assert.match(source, /document\.visibilityState\s*!==\s*"visible"/);
  assert.match(source, /removeEventListener\("visibilitychange"/);
});
```

- [ ] **Step 2: 运行测试并确认缺少导出和生命周期接线**

Run: `cd frontend && node --test tests/pulse-state.test.mjs tests/pulse-store-lifecycle.test.mjs`

Expected: FAIL，缺少 `getShanghaiDateKey` 或 `visibilitychange`。

- [ ] **Step 3: 增加北京时间纯函数**

Append to `frontend/src/features/pulse/pulseState.js`:

```js
export function getShanghaiDateKey(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

export function shouldRefreshPulseDate(businessDate, date = new Date()) {
  return String(businessDate || "") !== getShanghaiDateKey(date);
}
```

- [ ] **Step 4: 接入 visibility 生命周期**

Import `shouldRefreshPulseDate` in `frontend/src/stores/pulse.js`, then add:

```js
async function handleVisibilityChange() {
  if (document.visibilityState !== "visible") return;
  if (!shouldRefreshPulseDate(state.value.edition?.date)) return;
  await fetchToday().catch(() => {});
  startTimers();
}

function bindVisibilityRefresh() {
  if (typeof document === "undefined") return;
  document.removeEventListener("visibilitychange", handleVisibilityChange);
  document.addEventListener("visibilitychange", handleVisibilityChange);
}
```

Call `bindVisibilityRefresh()` after `startTimers()` in `initialize()`. In `onScopeDispose`, add:

```js
document.removeEventListener("visibilitychange", handleVisibilityChange);
```

- [ ] **Step 5: 运行状态和生命周期测试**

Run: `cd frontend && node --test tests/pulse-state.test.mjs tests/pulse-store-lifecycle.test.mjs`

Expected: all tests PASS。

- [ ] **Step 6: 提交跨日刷新**

```powershell
git add frontend/src/features/pulse/pulseState.js frontend/src/stores/pulse.js frontend/tests/pulse-state.test.mjs frontend/tests/pulse-store-lifecycle.test.mjs
git commit -m "fix: refresh pulse after a hidden midnight"
```

### Task 4: Pulse 页面集成与渐变模块

**Files:**
- Modify: `frontend/tests/pulse-layout.test.mjs`
- Modify: `frontend/src/pages/PulseDemoPage.vue`
- Keep: `frontend/src/components/pulse-demo/PulseStar.vue`

- [ ] **Step 1: 更新布局失败测试**

Replace the typography test and add integration assertions:

```js
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
  for (const selector of ["signal-card--question", "signal-card--challenge", "signal-card--poll", "orbit-log"]) {
    assert.match(source, new RegExp(`\\.${selector}\\s*\\{[^}]*linear-gradient`, "s"));
  }
});
```

- [ ] **Step 2: 运行布局测试并确认失败**

Run: `cd frontend && node --test tests/pulse-layout.test.mjs`

Expected: FAIL，页面仍包含 `PulseStar` 和旧字号。

- [ ] **Step 3: 替换中央星球模板与导入**

Replace the existing `<PulseStar ... />` with:

```vue
<DailyPlanet
  :business-date="pulse.state.edition?.date || ''"
  :progress="pulse.progressCount"
/>
```

Replace the import with:

```js
import DailyPlanet from "../components/pulse-demo/DailyPlanet.vue";
```

Keep the existing status caption and three semantic legend entries; they show current completion state and are not planet-rotation annotations.

- [ ] **Step 4: 升级字体和四类模块表面**

Set the Pulse scale to:

```css
--pulse-text-xs: 12px;
--pulse-text-sm: 14px;
--pulse-text-md: 15px;
```

Use transparent borders plus layered gradients:

```css
.signal-card, .orbit-log {
  border:1px solid transparent;
  box-shadow:0 26px 74px rgba(0,0,0,.2), inset 0 1px 0 rgba(255,255,255,.035);
}
.signal-card--question { background:linear-gradient(145deg,rgba(10,31,32,.94),rgba(9,15,26,.95)) padding-box,linear-gradient(135deg,rgba(92,174,156,.28),rgba(93,153,184,.08),rgba(200,167,92,.12)) border-box; }
.signal-card--challenge { background:linear-gradient(145deg,rgba(12,23,39,.96),rgba(24,17,43,.94)) padding-box,linear-gradient(135deg,rgba(90,153,184,.26),rgba(137,102,181,.22),rgba(200,167,92,.1)) border-box; }
.signal-card--poll { background:linear-gradient(105deg,rgba(11,31,31,.95),rgba(15,24,40,.95),rgba(30,20,48,.94)) padding-box,linear-gradient(90deg,rgba(92,174,156,.28),rgba(90,153,184,.22),rgba(137,102,181,.24)) border-box; }
.orbit-log { background:linear-gradient(145deg,rgba(9,29,30,.95),rgba(25,18,42,.94)) padding-box,linear-gradient(90deg,rgba(200,167,92,.22),rgba(92,174,156,.16),rgba(137,102,181,.25)) border-box; }
```

Update `.star-stage :deep(.pulse-star)` to `.star-stage :deep(.daily-planet)`. Keep desktop single-screen rules; on mobile retain natural vertical scrolling.

- [ ] **Step 5: 确认旧组件只服务顶栏并运行 Pulse 前端测试**

Run:

```powershell
rg -n "PulseStar" frontend/src
Set-Location frontend
npm run test:pulse
```

Expected: `PulseDemoPage.vue` 无引用，`PulseHeaderEntry.vue` 保留 compact 引用；all Pulse tests PASS。

- [ ] **Step 6: 提交页面集成**

```powershell
git add frontend/src/pages/PulseDemoPage.vue frontend/tests/pulse-layout.test.mjs docs/superpowers/plans/2026-07-20-black-pearl-midnight-theme.md
git commit -m "feat: present pulse as a black pearl observatory"
```

### Task 5: 全站黑珍珠 Midnight 主题和初版顶栏

**Files:**
- Create: `frontend/tests/midnight-theme.test.mjs`
- Modify: `frontend/src/assets/theme.css`
- Modify: `frontend/src/components/TopNav.vue`
- Modify: `frontend/src/stores/theme.js`

- [ ] **Step 1: 写入主题失败测试**

```js
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

function source(relativePath) {
  return readFileSync(fileURLToPath(new URL(relativePath, import.meta.url)), "utf8");
}

const themeCss = source("../src/assets/theme.css");
const topNav = source("../src/components/TopNav.vue");
const themeStore = source("../src/stores/theme.js");

test("Midnight exposes black-pearl semantic colors and layered stars", () => {
  assert.match(themeCss, /--pearl-peacock:\s*#5cae9c/i);
  assert.match(themeCss, /--pearl-blue:\s*#5a99b8/i);
  assert.match(themeCss, /--pearl-violet:\s*#8966b5/i);
  assert.match(themeCss, /--pearl-gold:\s*#c8a75c/i);
  assert.match(themeCss, /html\[data-theme="midnight"\] body::before[\s\S]*radial-gradient/);
  assert.match(themeCss, /background-size:[^;]*,/);
});

test("TopNav keeps the initial content order while Midnight changes only material", () => {
  const order = ["class=\"brand\"", "class=\"desktop-nav\"", "<PulseHeaderEntry", "class=\"top-search\"", "class=\"theme-anchor\""];
  let cursor = -1;
  for (const token of order) {
    const next = topNav.indexOf(token);
    assert.ok(next > cursor, `${token} must retain its initial position`);
    cursor = next;
  }
  assert.match(topNav, /data-theme="midnight"[\s\S]*\.topbar/);
  assert.match(topNav, /data-theme="midnight"[\s\S]*\.top-search-submit/);
});

test("theme picker describes Midnight as Black Pearl", () => {
  assert.match(themeStore, /name:\s*"Black Pearl"/);
  assert.match(themeStore, /孔雀虹彩/);
});
```

- [ ] **Step 2: 运行主题测试并确认失败**

Run: `cd frontend && node --test tests/midnight-theme.test.mjs`

Expected: FAIL，缺少黑珍珠语义变量和新名称。

- [ ] **Step 3: 更新 Midnight 全局变量与星光层**

In `html[data-theme="midnight"]`, define:

```css
--bg:#03070b;
--text:#d9dedc;
--text-strong:#eeece5;
--text-soft:#a9b7b7;
--text-quiet:#829294;
--pearl-peacock:#5cae9c;
--pearl-blue:#5a99b8;
--pearl-violet:#8966b5;
--pearl-gold:#c8a75c;
--surface-page:#03070b;
--surface:rgba(8,22,24,.9);
--surface-strong:rgba(10,25,28,.96);
--surface-soft:rgba(13,29,34,.9);
--surface-muted:rgba(8,19,25,.95);
--nav-bg:rgba(3,9,13,.9);
--accent:#c8a75c;
--accent-gradient:linear-gradient(135deg,#d5b86d 0%,#b58a3f 100%);
```

Replace the Midnight body background and `body::before` with layered blue-green/purple nebulae and at least four differently sized radial star fields. Cold white stars dominate; champagne-gold stars remain sparse. No animation is added.

- [ ] **Step 4: 为现有 TopNav 增加 Midnight 材质**

Do not edit `<template>`. Add scoped global rules:

```css
:global(html[data-theme="midnight"] .topbar) {
  background:linear-gradient(100deg,rgba(3,9,13,.96),rgba(8,22,26,.94) 46%,rgba(16,13,28,.94));
  border-bottom-color:rgba(200,167,92,.18);
  box-shadow:0 14px 38px rgba(0,0,0,.22);
}
:global(html[data-theme="midnight"] .top-search),
:global(html[data-theme="midnight"] .theme-toggle),
:global(html[data-theme="midnight"] .auth-pill) {
  border-color:rgba(136,170,166,.18);
  background:linear-gradient(135deg,rgba(13,34,35,.88),rgba(24,19,38,.84));
  box-shadow:inset 0 1px 0 rgba(255,255,255,.04),0 10px 28px rgba(0,0,0,.2);
}
:global(html[data-theme="midnight"] .top-search-submit) {
  color:#090c0d;
  background:linear-gradient(135deg,#d6bc75,#b98f45);
  box-shadow:0 0 20px rgba(200,167,92,.12);
}
```

Update the Midnight swatch to a peacock-green/blue/violet pearl with one small gold highlight. Do not change `.topbar-inner` dimensions, grid columns, padding, breakpoints or template order.

- [ ] **Step 5: 更新主题元数据并运行全部前端测试**

Set Midnight metadata to:

```js
name: "Black Pearl",
description: "黑珍珠暗面、孔雀虹彩与香槟金星光。",
```

Run: `cd frontend && node --test tests/*.test.mjs`

Expected: all frontend tests PASS。

- [ ] **Step 6: 提交全站主题**

```powershell
git add frontend/src/assets/theme.css frontend/src/components/TopNav.vue frontend/src/stores/theme.js frontend/tests/midnight-theme.test.mjs
git commit -m "feat: redesign Midnight as a black pearl theme"
```

### Task 6: 构建、回归与浏览器验收

**Files:**
- Modify only if a verification failure identifies a concrete defect in files from Tasks 1–5.

- [ ] **Step 1: 运行前端自动化测试与生产构建**

Run:

```powershell
Set-Location frontend
npm run test:pulse
npm run test:pulse-demo
node --test tests/daily-planet.test.mjs tests/daily-planet-component.test.mjs tests/pulse-store-lifecycle.test.mjs tests/midnight-theme.test.mjs
npm run build
```

Expected: tests PASS；Vite build exits 0；无新增 warning。

- [ ] **Step 2: 运行后端 Pulse 回归和迁移检查**

Run:

```powershell
Set-Location backend
python manage.py test wiki.test_pulse_models wiki.test_pulse_daily wiki.test_pulse_api wiki.test_pulse_bindings wiki.test_pulse_challenges wiki.test_pulse_rewards
python manage.py makemigrations --check --dry-run
```

Expected: tests PASS；输出 `No changes detected`。

- [ ] **Step 3: 检查资产体积和单图引用**

Run:

```powershell
Get-ChildItem frontend/src/assets/pulse/*.webp | Select-Object Name,Length
rg -n "<img|autoplay|carousel|pause" frontend/src/components/pulse-demo/DailyPlanet.vue
```

Expected: 每张 WebP ≤ 512000 bytes；组件只有一个 `<img>`；无自动轮播或暂停控件。

- [ ] **Step 4: 启动隔离预览并做桌面验收**

Start Vite on a free localhost port and use the in-app browser to inspect `/pulse` at:

```text
2048×1080
1920×1080
1440×900
1366×768
1280×720
```

For every viewport verify: initial TopNav alignment is unchanged; no page scrollbar; text remains readable; one realistic planet is visible with no black square; question/challenge/poll/orbit cards have distinct low-contrast gradients; starfield has cold-white, gold and peacock/violet depth; browser console has no errors.

- [ ] **Step 5: 做移动端和日期验收**

Inspect 390×844 and 430×932. Verify: existing mobile menu works; no horizontal overflow; content scrolls vertically; touch controls are not clipped. Mock or intercept `edition.date` with `2026-07-19`, `2026-07-20`, `2026-07-21`; verify C, A, B respectively and exactly one planet image request for each reload.

- [ ] **Step 6: 检查差异与最终提交状态**

Run:

```powershell
git diff --check
git status --short --branch -uall
git log --oneline -8
```

Expected: `git diff --check` exits 0；`.superpowers/` 预览文件保持 untracked 且未提交；产品变更全部位于 `codex/midnight-pulse-demo`；没有推送、合并或部署操作。
