# Eclipse Observatory Theme and Motion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a complete Midnight theme, apply it temporarily on `/pulse-demo`, restore the previous theme on exit, and add the approved tactile motion system without changing the verified layout.

**Architecture:** Extend the existing Pinia theme store with a temporary override lifecycle while keeping `currentTheme` as the effective theme consumed by the app. `App.vue` owns the route-scoped override so the theme is active before the pulse page renders. Theme visuals remain token-driven in `theme.css`; pulse-only transitions stay inside the pulse components and animate only opacity and transforms.

**Tech Stack:** Vue 3, Pinia, Vue Router, scoped CSS, native CSS transitions and keyframes, Node test runner, Vite.

---

## File map

- `frontend/src/stores/theme.js`: Midnight option, effective theme state, temporary override lifecycle and storage boundary.
- `frontend/tests/theme-store.test.mjs`: theme normalization, persistence and temporary restore regression tests.
- `frontend/package.json`: one command that runs both pulse and theme tests.
- `frontend/src/App.vue`: synchronous route-scoped theme entry and cleanup.
- `frontend/src/assets/theme.css`: complete Midnight semantic tokens and global dark atmosphere.
- `frontend/src/components/TopNav.vue`: Midnight swatches, eclipse rim, temporary-mode note and dark mobile surfaces.
- `frontend/src/pages/PulseDemoPage.vue`: keyed view transitions, metric transitions, staged card entry and tactile controls.
- `frontend/src/components/pulse-demo/PulseStar.vue`: one-shot progress response and reduced-motion fallback.

### Task 1: Temporary Midnight theme state

**Files:**
- Create: `frontend/tests/theme-store.test.mjs`
- Modify: `frontend/src/stores/theme.js`
- Modify: `frontend/package.json`

- [ ] **Step 1: Write the failing theme store tests**

Create `frontend/tests/theme-store.test.mjs` with a small browser shim and these behaviors:

```js
import test from "node:test";
import assert from "node:assert/strict";
import { createPinia, setActivePinia } from "pinia";
import { useThemeStore } from "../src/stores/theme.js";

function installBrowserShim(storedTheme = "modern") {
  const storage = new Map([["algowiki-theme", storedTheme]]);
  globalThis.document = { documentElement: { dataset: {} } };
  globalThis.window = {
    localStorage: {
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
    },
  };
  return storage;
}

function createTheme(storedTheme) {
  const storage = installBrowserShim(storedTheme);
  setActivePinia(createPinia());
  const theme = useThemeStore();
  theme.init();
  return { theme, storage };
}

test("midnight is a normal persistent theme outside temporary mode", () => {
  const { theme, storage } = createTheme("modern");
  theme.setTheme("midnight");
  assert.equal(theme.currentTheme, "midnight");
  assert.equal(storage.get("algowiki-theme"), "midnight");
  assert.equal(document.documentElement.dataset.theme, "midnight");
});

test("temporary midnight does not overwrite the stored preference", () => {
  const { theme, storage } = createTheme("academic");
  theme.beginTemporaryTheme("midnight");
  assert.equal(theme.currentTheme, "midnight");
  assert.equal(theme.isTemporary, true);
  assert.equal(storage.get("algowiki-theme"), "academic");
});

test("theme choices stay temporary until the pulse route exits", () => {
  const { theme, storage } = createTheme("geek");
  theme.beginTemporaryTheme("midnight");
  theme.setTheme("modern");
  assert.equal(theme.currentTheme, "modern");
  assert.equal(storage.get("algowiki-theme"), "geek");
  theme.endTemporaryTheme();
  assert.equal(theme.currentTheme, "geek");
  assert.equal(theme.isTemporary, false);
});

test("repeated temporary entry preserves the original restore target", () => {
  const { theme } = createTheme("academic");
  theme.beginTemporaryTheme("midnight");
  theme.beginTemporaryTheme("midnight");
  theme.endTemporaryTheme();
  assert.equal(theme.currentTheme, "academic");
});
```

- [ ] **Step 2: Run the test and verify RED**

Run: `node --test tests/theme-store.test.mjs`

Expected: FAIL because `midnight`, `beginTemporaryTheme`, `endTemporaryTheme` and `isTemporary` do not exist.

- [ ] **Step 3: Implement the minimal store behavior**

Add the Midnight option and temporary state to `frontend/src/stores/theme.js`:

```js
{
  id: "midnight",
  label: "Midnight",
  name: "Eclipse Observatory",
  description: "真空黑观测台、脉冲光谱与暗舱层级。",
}
```

Add `temporaryRestoreTheme: null` to state, an `isTemporary` getter, and these actions:

```js
beginTemporaryTheme(themeId) {
  if (this.temporaryRestoreTheme === null) {
    this.temporaryRestoreTheme = this.currentTheme;
  }
  this.currentTheme = normalizeTheme(themeId);
  applyThemeToDocument(this.currentTheme);
},
endTemporaryTheme() {
  if (this.temporaryRestoreTheme === null) return;
  const restoreTheme = this.temporaryRestoreTheme;
  this.temporaryRestoreTheme = null;
  this.currentTheme = restoreTheme;
  applyThemeToDocument(restoreTheme);
},
```

At the start of `setTheme`, route temporary choices through the override without writing storage:

```js
const nextTheme = normalizeTheme(themeId);
if (this.temporaryRestoreTheme !== null) {
  this.currentTheme = nextTheme;
  applyThemeToDocument(nextTheme);
  return;
}
```

- [ ] **Step 4: Run the theme tests and verify GREEN**

Run: `node --test tests/theme-store.test.mjs`

Expected: 4 tests pass, 0 fail.

- [ ] **Step 5: Add the combined test command**

Change `frontend/package.json` scripts to include:

```json
"test:pulse-demo": "node --test tests/pulse-demo-state.test.mjs tests/theme-store.test.mjs"
```

- [ ] **Step 6: Run the combined suite**

Run: `npm run test:pulse-demo`

Expected: existing 11 pulse tests plus 4 theme tests pass.

- [ ] **Step 7: Commit the state layer**

```bash
git add frontend/src/stores/theme.js frontend/tests/theme-store.test.mjs frontend/package.json
git commit -m "feat: add temporary midnight theme state"
```

### Task 2: Route lifecycle and complete Midnight tokens

**Files:**
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/assets/theme.css`

- [ ] **Step 1: Add synchronous route ownership in `App.vue`**

Import `watch`, then register a synchronous immediate watcher after `theme.init()`:

```js
const stopPulseThemeWatch = watch(
  isPulseLayout,
  (isPulse) => {
    if (isPulse) theme.beginTemporaryTheme("midnight");
    else theme.endTemporaryTheme();
  },
  { immediate: true, flush: "sync" }
);
```

Release it during app unmount:

```js
stopPulseThemeWatch();
theme.endTemporaryTheme();
```

- [ ] **Step 2: Add Midnight semantic tokens**

Add `html[data-theme="midnight"]` after the Modern token block in `frontend/src/assets/theme.css`. Override the complete semantic color surface with these primitives and derive component tokens from them:

```css
html[data-theme="midnight"] {
  --bg: #070b14;
  --text: #d7dce6;
  --text-strong: #f4f1e8;
  --text-soft: #9aa6b8;
  --text-quiet: #69758a;
  --muted: rgba(215, 220, 230, 0.58);
  --hairline: rgba(226, 236, 255, 0.075);
  --hairline-strong: rgba(226, 236, 255, 0.14);
  --bg-1: rgba(232, 188, 102, 0.07);
  --bg-2: rgba(99, 215, 245, 0.065);
  --bg-3: rgba(155, 131, 246, 0.055);
  --accent: #e8bc66;
  --accent-contrast: #111722;
  --accent-soft: rgba(232, 188, 102, 0.12);
  --accent-gradient: linear-gradient(135deg, #efc877 0%, #dca84f 100%);
  --accent-shadow: 0 0 0 1px rgba(232, 188, 102, 0.18);
  --danger: #ef8f8f;
  --success: #68d2aa;
  --surface-page: #070b14;
  --surface: rgba(11, 17, 29, 0.92);
  --surface-strong: rgba(14, 22, 36, 0.97);
  --surface-soft: rgba(18, 28, 44, 0.88);
  --surface-muted: rgba(12, 20, 33, 0.96);
  --surface-chip: rgba(145, 164, 195, 0.1);
  --surface-overlay: rgba(12, 19, 31, 0.985);
  --surface-highlight: rgba(99, 215, 245, 0.08);
  --panel-border: rgba(226, 236, 255, 0.09);
  --panel-border-strong: rgba(226, 236, 255, 0.15);
  --card-shadow: 0 0 0 1px rgba(226, 236, 255, 0.06);
  --card-shadow-hover: 0 0 0 1px rgba(99, 215, 245, 0.16);
  --shadow-sm: 0 0 0 1px rgba(226, 236, 255, 0.08);
  --shadow-md: 0 18px 48px rgba(0, 0, 0, 0.42), 0 0 0 1px rgba(226, 236, 255, 0.09);
  --inner-highlight: inset 0 1px 0 rgba(255, 255, 255, 0.035);
  --button-bg: rgba(17, 26, 42, 0.94);
  --button-border: rgba(226, 236, 255, 0.1);
  --button-text: var(--text-strong);
  --button-hover-bg: rgba(23, 35, 55, 0.98);
  --input-bg: rgba(5, 10, 19, 0.72);
  --input-border: rgba(226, 236, 255, 0.1);
  --input-focus: rgba(99, 215, 245, 0.24);
  --nav-bg: rgba(7, 11, 20, 0.94);
  --nav-pill-bg: rgba(15, 23, 37, 0.88);
  --nav-pill-border: rgba(226, 236, 255, 0.11);
  --nav-link: rgba(215, 220, 230, 0.66);
  --nav-link-active: #f4f1e8;
  --search-bg: rgba(5, 10, 19, 0.78);
  --search-border: rgba(226, 236, 255, 0.09);
  --pill-bg: rgba(232, 188, 102, 0.12);
  --pill-text: #efc877;
  --label-bg: rgba(154, 166, 184, 0.1);
  --label-text: #9aa6b8;
  --link: #75d9f4;
  --link-visited: #b5a5fa;
  --code-inline-bg: rgba(99, 215, 245, 0.08);
  --code-inline-text: #c8effa;
  --table-head-bg: rgba(18, 28, 44, 0.92);
  --content-rule: rgba(226, 236, 255, 0.11);
  --content-selection-bg: rgba(232, 188, 102, 0.22);
  --content-selection-text: #f4f1e8;
}
```

Add a Midnight `body::before` atmosphere using sparse radial points and ensure it has no pointer events.

- [ ] **Step 3: Preserve reduced motion during theme changes**

Extend the global reduced-motion rule so body theme transitions collapse to color-only feedback of at most 120ms.

- [ ] **Step 4: Build after the token change**

Run: `npm run build`

Expected: Vite exits 0 with no CSS parse errors.

- [ ] **Step 5: Commit the theme lifecycle and tokens**

```bash
git add frontend/src/App.vue frontend/src/assets/theme.css
git commit -m "feat: apply midnight theme to pulse route"
```

### Task 3: Eclipse navigation material

**Files:**
- Modify: `frontend/src/components/TopNav.vue`

- [ ] **Step 1: Add temporary-mode copy to desktop and mobile theme selectors**

Inside `.theme-panel`, before the option buttons, render:

```vue
<p v-if="theme.isTemporary" class="theme-panel-note">
  脉冲剧场临时主题，离开后恢复
</p>
```

Add the same sentence below `.mobile-theme-label` for the mobile menu.

- [ ] **Step 2: Add the Midnight swatch**

```css
.theme-toggle-swatch--midnight,
.theme-option-swatch--midnight {
  border-color: rgba(232, 188, 102, 0.28);
  background:
    radial-gradient(circle at 32% 30%, #f2c972 0 10%, transparent 28%),
    linear-gradient(135deg, #070b14 0%, #14233b 58%, #63d7f5 100%);
  box-shadow: 0 0 10px rgba(99, 215, 245, 0.14);
}
```

- [ ] **Step 3: Build the eclipse rim and dark control states**

Use `html[data-theme="midnight"]` through `:global(...)` selectors in the scoped style. Add a topbar `::before` layer containing sparse star points and a 1px bottom spectral line. Keep the material restrained:

```css
:global(html[data-theme="midnight"]) .topbar::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  background:
    radial-gradient(circle at 71% 35%, rgba(232, 188, 102, 0.12) 0 1px, transparent 2px),
    radial-gradient(circle at 88% 24%, rgba(99, 215, 245, 0.1) 0 1px, transparent 2px),
    linear-gradient(90deg, rgba(232, 188, 102, 0.72), rgba(99, 215, 245, 0.58), rgba(155, 131, 246, 0.68)) bottom / 100% 1px no-repeat;
  opacity: 0.72;
}
```

Add explicit hover, active and `:focus-visible` states. Use `transform: scale(0.97)` only on press; do not use `transition: all`.

- [ ] **Step 4: Verify desktop and mobile menu surfaces in the browser**

At 1280x720 and 390x844, confirm the header, theme panel and mobile drawer use Midnight tokens; confirm text and controls have no horizontal overflow.

- [ ] **Step 5: Commit the navigation material**

```bash
git add frontend/src/components/TopNav.vue
git commit -m "feat: add eclipse navigation material"
```

### Task 4: Tactile view and state transitions

**Files:**
- Modify: `frontend/src/pages/PulseDemoPage.vue`

- [ ] **Step 1: Key the three views without changing their layout wrapper**

Replace the three top-level conditional views with one transition and keyed wrappers:

```vue
<Transition name="pulse-view" mode="out-in">
  <section v-if="activeTab === 'observatory'" key="observatory" class="observatory" aria-label="今夜观测台">
    <!-- existing observatory children remain unchanged -->
  </section>
  <PulseAtlasPanel v-else-if="activeTab === 'atlas'" key="atlas" :progress="pulse.progressCount" class="pulse-view-panel" />
  <PulseRankingPanel v-else key="ranking" class="pulse-view-panel" />
</Transition>
```

- [ ] **Step 2: Add spring-like view timing**

```css
.pulse-view-enter-active {
  transition: opacity 240ms cubic-bezier(.23, 1, .32, 1), transform 240ms cubic-bezier(.23, 1, .32, 1);
}
.pulse-view-leave-active {
  transition: opacity 140ms cubic-bezier(.4, 0, 1, 1), transform 140ms cubic-bezier(.4, 0, 1, 1);
}
.pulse-view-enter-from { opacity: 0; transform: translateY(6px) scale(.985); }
.pulse-view-leave-to { opacity: 0; transform: translateY(-3px) scale(.992); }
```

- [ ] **Step 3: Add staged observatory entry**

Assign `--signal-order` values to question, star, challenge, poll and orbit. Animate their first appearance with 45ms intervals using opacity and transform only. The total cascade must finish within 420ms.

- [ ] **Step 4: Animate metric replacements and result panels**

Wrap summary values, the star readout and conditional result panels in keyed Vue transitions. Use a shared `pulse-result` transition with 180ms to 220ms opacity and scale. Keep typography size identical between states so the layout does not jump.

- [ ] **Step 5: Add tactile controls**

Apply 100ms to 140ms press feedback to tabs, mode cards, action buttons and poll options:

```css
.pulse-tabs button,
.mode-card,
.primary-action,
.secondary-action,
.poll-options button {
  transition-property: transform, border-color, background-color, color, opacity;
  transition-duration: 140ms;
  transition-timing-function: cubic-bezier(.23, 1, .32, 1);
}

.pulse-tabs button:active,
.mode-card:active,
.primary-action:active,
.secondary-action:active,
.poll-options button:active {
  transform: scale(.97);
}
```

- [ ] **Step 6: Replace the existing toast `transition: all`**

Use explicit opacity and transform transitions, 220ms on entry and 150ms on exit.

- [ ] **Step 7: Add the reduced-motion fallback**

Inside the page reduced-motion query, preserve an opacity transition of at most 120ms and force transforms to none for view, result, card and toast transitions.

- [ ] **Step 8: Browser-check all three tabs and completion states**

At 1280x720, switch through all tabs and complete question, challenge and poll. Confirm no element changes the document dimensions and the progress remains visible. Repeat at 390x844 to confirm no horizontal overflow.

- [ ] **Step 9: Commit the view motion**

```bash
git add frontend/src/pages/PulseDemoPage.vue
git commit -m "feat: add tactile pulse view transitions"
```

### Task 5: One-shot star response

**Files:**
- Modify: `frontend/src/components/pulse-demo/PulseStar.vue`

- [ ] **Step 1: Add a keyed signal burst**

Render one decorative signal ring when progress is nonzero:

```vue
<Transition name="star-signal" mode="out-in">
  <span v-if="progress" :key="progress" class="star-signal" aria-hidden="true"></span>
</Transition>
```

- [ ] **Step 2: Animate only the new signal ring**

Use a 480ms one-shot transform and opacity keyframe that begins at `scale(.84)`, peaks below `scale(1.08)`, and fades by the end. Do not restart or amplify the existing infinite ambient loops.

- [ ] **Step 3: Add number response without layout shift**

Key the readout number by progress and use a 220ms `scale(.94)` to `scale(1)` transition. Keep `font-variant-numeric: tabular-nums` on all progress metrics.

- [ ] **Step 4: Disable the burst in reduced-motion mode**

Hide `.star-signal` and remove readout transforms under `prefers-reduced-motion: reduce`; retain the new number and static color state.

- [ ] **Step 5: Commit the star response**

```bash
git add frontend/src/components/pulse-demo/PulseStar.vue
git commit -m "feat: animate pulse star responses"
```

### Task 6: Full verification and visual review

**Files:**
- Verify: `frontend/src/stores/theme.js`
- Verify: `frontend/src/assets/theme.css`
- Verify: `frontend/src/App.vue`
- Verify: `frontend/src/components/TopNav.vue`
- Verify: `frontend/src/pages/PulseDemoPage.vue`
- Verify: `frontend/src/components/pulse-demo/PulseStar.vue`

- [ ] **Step 1: Run all automated tests**

Run: `npm run test:pulse-demo`

Expected: 15 tests pass, 0 fail.

- [ ] **Step 2: Run the production build**

Run: `npm run build`

Expected: Vite exits 0. Existing chunk-size warnings are recorded but do not fail the build.

- [ ] **Step 3: Check the diff**

Run: `git diff --check`

Expected: no whitespace errors.

- [ ] **Step 4: Verify route restoration in the browser**

For Modern, Academic and Geek: select the theme on a non-pulse page, enter `/pulse-demo`, confirm `data-theme="midnight"`, leave the page, and confirm the original `data-theme` value returns. Refresh `/pulse-demo` and confirm no white header frame appears.

- [ ] **Step 5: Verify visual viewports**

Check 2048x1080, 1440x900, 1280x720 and 390x844. Desktop document height must equal viewport height; mobile document width must equal viewport width. Check observatory, atlas, ranking, theme panel and mobile menu.

- [ ] **Step 6: Verify reduced motion**

Emulate `prefers-reduced-motion: reduce`. Switch tabs and complete one task. Confirm computed transforms remain `none`, ambient star animations stop, and state text still updates.

- [ ] **Step 7: Run the design review**

Apply the squint, signature, token and swap tests. The signature must be visible in at least five places: eclipse line, Midnight swatch, inset search, dark theme panel, and pulse-linked focus/press feedback.

- [ ] **Step 8: Leave the local preview ready**

Reset the Demo to 0/3, keep `/pulse-demo` visible, restore the real browser viewport, and leave the tab open for user review. Do not push or deploy.
