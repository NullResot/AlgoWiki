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
const homePage = source("../src/pages/HomePage.vue");
const wikiPage = source("../src/pages/WikiPage.vue");

test("Midnight exposes black-pearl semantic colors and layered stars", () => {
  assert.match(themeCss, /--pearl-peacock:\s*#5cae9c/i);
  assert.match(themeCss, /--pearl-blue:\s*#5a99b8/i);
  assert.match(themeCss, /--pearl-violet:\s*#8966b5/i);
  assert.match(themeCss, /--pearl-gold:\s*#c8a75c/i);
  assert.match(
    themeCss,
    /html\[data-theme="midnight"\] body::before[\s\S]*radial-gradient/,
  );
  assert.match(themeCss, /background-size:[^;]*,/);
});

test("TopNav keeps the initial content order while Midnight changes only material", () => {
  const order = [
    "class=\"brand\"",
    "class=\"desktop-nav\"",
    "<PulseHeaderEntry",
    "class=\"top-search\"",
    "class=\"theme-anchor\"",
  ];
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

test("Midnight home uses one masked obsidian planet and layered starlight", () => {
  assert.match(homePage, /planet-obsidian\.webp/);
  assert.match(homePage, /data-theme="midnight"[\s\S]*\.home-redesign::before/);
  assert.match(homePage, /data-theme="midnight"[\s\S]*\.home-redesign::after/);
  assert.match(homePage, /mask-image:\s*radial-gradient/);
  assert.match(homePage, /overflow:\s*(?:clip|hidden)/);
});

test("Midnight Wiki directory replaces white active blocks with pearl surfaces", () => {
  assert.match(
    wikiPage,
    /data-theme="midnight"[\s\S]*\.toc-sub-row--chapter\.toc-sub-row--root/,
  );
  assert.match(wikiPage, /data-theme="midnight"[\s\S]*\.toc-sub-row--active/);
  assert.match(wikiPage, /rgba\(92,\s*174,\s*156/);
  assert.match(wikiPage, /rgba\(200,\s*167,\s*92/);
});

test("Midnight search action uses a restrained pearl material", () => {
  assert.doesNotMatch(topNav, /#d6bc75|#b98f45/i);
  assert.match(topNav, /top-search-submit:hover/);
  assert.match(topNav, /color:\s*#d8c78f/i);
});
