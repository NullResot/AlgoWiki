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
