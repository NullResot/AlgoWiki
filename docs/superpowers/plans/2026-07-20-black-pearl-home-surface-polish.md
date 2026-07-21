# Black Pearl Home Surface Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Midnight a black-pearl planetary homepage, a dark pearlescent Wiki directory, and a restrained search button without changing product structure or other themes.

**Architecture:** Keep the existing Vue templates and state untouched. Add Midnight-scoped CSS to `HomePage.vue`, `WikiPage.vue`, and `TopNav.vue`, reuse the existing obsidian planet asset, and protect the visual contract with source-level theme regression tests.

**Tech Stack:** Vue 3 single-file components, scoped CSS, CSS gradients and masks, Node test runner, Vite.

---

## File map

- `frontend/src/pages/HomePage.vue`: Midnight-only cosmic background, black-pearl planet, card materials, responsive and reduced-motion behavior.
- `frontend/src/pages/WikiPage.vue`: Midnight-only table-of-contents root, active, hover, count, and toggle surfaces.
- `frontend/src/components/TopNav.vue`: Midnight-only restrained search action states.
- `frontend/tests/midnight-theme.test.mjs`: Source-level regression contract for the three visual changes.

### Task 1: Black-pearl homepage environment

**Files:**
- Modify: `frontend/tests/midnight-theme.test.mjs`
- Modify: `frontend/src/pages/HomePage.vue`

- [ ] **Step 1: Write the failing homepage contract test**

Add the source import and test below:

```js
const homePage = source("../src/pages/HomePage.vue");

test("Midnight home uses one masked obsidian planet and layered starlight", () => {
  assert.match(homePage, /planet-obsidian\.webp/);
  assert.match(homePage, /data-theme="midnight"[\s\S]*\.home-redesign::before/);
  assert.match(homePage, /data-theme="midnight"[\s\S]*\.home-redesign::after/);
  assert.match(homePage, /mask-image:\s*radial-gradient/);
  assert.match(homePage, /overflow:\s*(?:clip|hidden)/);
});
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
node --test frontend/tests/midnight-theme.test.mjs
```

Expected: FAIL because `HomePage.vue` does not reference `planet-obsidian.webp` or define Midnight environment pseudo-elements.

- [ ] **Step 3: Implement the Midnight homepage environment**

In `HomePage.vue`, keep `.home-inner` above decoration and add Midnight-scoped layers using the existing asset:

```css
.home-redesign {
  position: relative;
  isolation: isolate;
  overflow: clip;
}

.home-inner {
  position: relative;
  z-index: 2;
}

:global(html[data-theme="midnight"]) .home-redesign {
  background:
    radial-gradient(circle at 82% 16%, rgba(137, 102, 181, 0.1), transparent 31%),
    radial-gradient(circle at 24% 42%, rgba(92, 174, 156, 0.08), transparent 34%),
    linear-gradient(145deg, #03070b 0%, #071116 46%, #0b0c17 100%);
}

:global(html[data-theme="midnight"]) .home-redesign::before {
  content: "";
  position: absolute;
  width: min(76vw, 1080px);
  aspect-ratio: 1;
  top: clamp(-250px, -13vw, -110px);
  left: clamp(-420px, -18vw, -170px);
  border-radius: 50%;
  background: url("../assets/pulse/planet-obsidian.webp") center / cover no-repeat;
  mask-image: radial-gradient(circle at 50% 50%, black 0 58%, rgba(0, 0, 0, 0.78) 68%, transparent 82%);
  opacity: 0.52;
  filter: saturate(0.78) contrast(1.08);
  pointer-events: none;
  z-index: 0;
}

:global(html[data-theme="midnight"]) .home-redesign::after {
  content: "";
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 8% 17%, rgba(238, 236, 229, 0.66) 0 1px, transparent 1.5px),
    radial-gradient(circle at 70% 12%, rgba(200, 167, 92, 0.55) 0 1px, transparent 1.6px),
    radial-gradient(circle at 89% 37%, rgba(126, 187, 188, 0.46) 0 1px, transparent 1.7px),
    radial-gradient(circle at 36% 68%, rgba(238, 236, 229, 0.42) 0 0.8px, transparent 1.4px);
  background-size: 360px 320px, 520px 430px, 410px 370px, 620px 480px;
  opacity: 0.62;
  pointer-events: none;
  z-index: 1;
}
```

Add Midnight-specific low-contrast gradients to `.feature-card`, `.feature-card--support`, and `.support-btn`. Keep text contrast and existing geometry unchanged. At `max-width: 900px`, reduce the planet to at most `820px`, lower opacity, and reposition it above the hero. Under `prefers-reduced-motion: reduce`, disable any environment animation.

- [ ] **Step 4: Verify GREEN and build**

Run:

```powershell
node --test frontend/tests/midnight-theme.test.mjs
npm --prefix frontend run build
```

Expected: the Midnight test passes and Vite completes successfully with only pre-existing warnings.

- [ ] **Step 5: Commit and push the homepage batch**

```powershell
git add frontend/tests/midnight-theme.test.mjs frontend/src/pages/HomePage.vue
git commit -m "feat: add black pearl starfield to home"
git push origin codex/midnight-pulse-demo
```

### Task 2: Dark pearlescent Wiki directory

**Files:**
- Modify: `frontend/tests/midnight-theme.test.mjs`
- Modify: `frontend/src/pages/WikiPage.vue`

- [ ] **Step 1: Write the failing directory contract test**

```js
const wikiPage = source("../src/pages/WikiPage.vue");

test("Midnight Wiki directory replaces white active blocks with pearl surfaces", () => {
  assert.match(wikiPage, /data-theme="midnight"[\s\S]*\.toc-sub-row--chapter\.toc-sub-row--root/);
  assert.match(wikiPage, /data-theme="midnight"[\s\S]*\.toc-sub-row--active/);
  assert.match(wikiPage, /rgba\(92,\s*174,\s*156/);
  assert.match(wikiPage, /rgba\(200,\s*167,\s*92/);
});
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
node --test frontend/tests/midnight-theme.test.mjs
```

Expected: FAIL because `WikiPage.vue` has no Midnight-specific directory material rules.

- [ ] **Step 3: Implement Midnight directory materials**

Append Midnight-scoped rules after the base directory rules. Override root, hover, active, count, and toggle states with dark blue-black gradients, peacock reflection, and restrained champagne edges. Do not remove the base styles required by other themes.

```css
:global(html[data-theme="midnight"]) .toc-count,
:global(html[data-theme="midnight"]) .toc-sub-row--chapter.toc-sub-row--root .toc-sub-link {
  background: linear-gradient(135deg, rgba(11, 29, 30, 0.94), rgba(22, 18, 34, 0.92));
  border: 1px solid rgba(92, 174, 156, 0.16);
  color: #e7e4db;
  box-shadow: inset 0 1px 0 rgba(238, 236, 229, 0.035);
}

:global(html[data-theme="midnight"]) .toc-sub-row--chapter .toc-sub-link:hover {
  background: linear-gradient(135deg, rgba(15, 38, 39, 0.96), rgba(29, 23, 42, 0.94));
  color: #eeece5;
}

:global(html[data-theme="midnight"]) .toc-sub-row--active .toc-sub-link,
:global(html[data-theme="midnight"]) .toc-sub-row--selected-root .toc-sub-link {
  background: linear-gradient(120deg, rgba(92, 174, 156, 0.16), rgba(200, 167, 92, 0.09) 54%, rgba(137, 102, 181, 0.13));
  border-color: rgba(200, 167, 92, 0.34);
  color: #d8c78f;
  box-shadow: inset 0 1px 0 rgba(238, 236, 229, 0.05);
}
```

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
node --test frontend/tests/midnight-theme.test.mjs
```

Expected: all Midnight tests pass.

### Task 3: Restrained pearlescent search action

**Files:**
- Modify: `frontend/tests/midnight-theme.test.mjs`
- Modify: `frontend/src/components/TopNav.vue`

- [ ] **Step 1: Write the failing search-button contract test**

```js
test("Midnight search action uses a restrained pearl material", () => {
  assert.doesNotMatch(topNav, /#d6bc75|#b98f45/i);
  assert.match(topNav, /top-search-submit:hover/);
  assert.match(topNav, /color:\s*#d8c78f/i);
});
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
node --test frontend/tests/midnight-theme.test.mjs
```

Expected: FAIL because the current button uses `#d6bc75` and `#b98f45` and has no Midnight hover material.

- [ ] **Step 3: Implement the search states**

Replace the existing Midnight button override without changing padding or layout:

```css
:global(html[data-theme="midnight"] .top-search-submit) {
  color: #d8c78f;
  background: linear-gradient(135deg, rgba(11, 31, 32, 0.98), rgba(28, 22, 39, 0.96));
  box-shadow:
    inset 0 0 0 1px rgba(200, 167, 92, 0.28),
    inset 0 1px 0 rgba(238, 236, 229, 0.05),
    0 0 18px rgba(92, 174, 156, 0.06);
  transition: transform 160ms cubic-bezier(0.16, 1, 0.3, 1), filter 160ms ease, box-shadow 160ms ease;
}

:global(html[data-theme="midnight"] .top-search-submit:hover) {
  filter: brightness(1.12);
  box-shadow:
    inset 0 0 0 1px rgba(200, 167, 92, 0.42),
    inset 0 1px 0 rgba(238, 236, 229, 0.07),
    0 0 18px rgba(92, 174, 156, 0.09);
}

:global(html[data-theme="midnight"] .top-search-submit:active) {
  transform: scale(0.97);
}
```

- [ ] **Step 4: Verify GREEN and the complete frontend suite**

Run:

```powershell
node --test frontend/tests/midnight-theme.test.mjs
npm --prefix frontend run test:pulse
npm --prefix frontend run test:pulse-demo
npm --prefix frontend run build
```

Expected: all tests pass and the build completes with only pre-existing warnings.

- [ ] **Step 5: Commit and push the reading-surface batch**

```powershell
git add frontend/tests/midnight-theme.test.mjs frontend/src/pages/WikiPage.vue frontend/src/components/TopNav.vue
git commit -m "style: refine midnight reading surfaces"
git push origin codex/midnight-pulse-demo
```

### Task 4: Browser verification

**Files:**
- No product file changes unless verification exposes a defect.

- [ ] **Step 1: Open the real local homepage and Wiki page in Midnight**

Use the existing Vite preview and verify the homepage, `/wiki`, and the article view. Confirm the real page uses the existing header and data.

- [ ] **Step 2: Verify desktop viewports**

Check at 2048×1080 and 1440×900:

- No horizontal scrollbar.
- The planet is partially visible, naturally masked, and does not cover the hero or cards.
- Card gradients remain subtle and readable.
- Directory root and active rows are dark, not white.
- Search action is visible but no longer bright yellow.

- [ ] **Step 3: Verify mobile viewport**

Check at 375×812:

- No horizontal overflow.
- Planet opacity and position do not reduce title readability.
- Mobile navigation and directory interaction remain usable.
- Controls retain their existing touch sizes.

- [ ] **Step 4: Verify accessibility and motion**

Check keyboard focus on search and directory controls. Emulate `prefers-reduced-motion: reduce` and confirm no continuous decorative movement remains.

- [ ] **Step 5: Fix only verified defects, rerun tests, then push**

If browser inspection exposes a defect, first add or update the smallest regression test, confirm it fails, apply the minimal CSS correction, rerun the complete frontend verification, commit, and push the correction.
