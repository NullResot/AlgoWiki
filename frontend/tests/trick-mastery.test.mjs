import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const projectRoot = new URL("../../", import.meta.url);

test("closing a deep-linked mastered trick restores the normal filtered grid", async () => {
  const source = await readFile(
    new URL("frontend/src/pages/ExtraPage.vue", projectRoot),
    "utf8",
  );
  const closeStart = source.indexOf("function closeTrickModal() {");
  const closeEnd = source.indexOf("function syncTrickQuery", closeStart);
  assert.ok(closeStart >= 0 && closeEnd > closeStart);
  const closeBlock = source.slice(closeStart, closeEnd);

  assert.match(closeBlock, /if \(!showMasteredTricks\.value\)/);
  assert.match(
    closeBlock,
    /tricks\.value = tricks\.value\.filter\(\(item\) => !item\?\.is_mastered\)/,
  );
});

test("mastery controls are limited to approved tricks", async () => {
  const source = await readFile(
    new URL("frontend/src/pages/ExtraPage.vue", projectRoot),
    "utf8",
  );

  assert.match(
    source,
    /auth\.isAuthenticated\s*&&\s*selectedTrick\.status === 'approved'/,
  );
});

test("reset clears the mastered-trick filter", async () => {
  const source = await readFile(
    new URL("frontend/src/pages/ExtraPage.vue", projectRoot),
    "utf8",
  );
  const resetStart = source.indexOf("function resetTrickFilters() {");
  const resetEnd = source.indexOf("function toggleShowMasteredTricks", resetStart);
  assert.ok(resetStart >= 0 && resetEnd > resetStart);
  const resetBlock = source.slice(resetStart, resetEnd);

  assert.match(resetBlock, /showMasteredTricks\.value = false/);
});
