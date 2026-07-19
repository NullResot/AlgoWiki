import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const pulsePagePath = fileURLToPath(
  new URL("../src/pages/PulseDemoPage.vue", import.meta.url),
);
const source = readFileSync(pulsePagePath, "utf8");

test("pulse page keeps the operational workspace and removes presentation chrome", () => {
  assert.match(source, /class="pulse-tabs"/);
  assert.doesNotMatch(source, /class="pulse-brandline"/);
  assert.doesNotMatch(source, /class="pulse-title-row"/);
  assert.doesNotMatch(source, /class="pulse-summary"/);
  assert.doesNotMatch(source, /class="pulse-disclaimer"/);
});

test("pulse workspace declares a readable typography scale", () => {
  assert.match(source, /--pulse-text-xs:\s*11px/);
  assert.match(source, /--pulse-text-sm:\s*12px/);
  assert.match(source, /--pulse-text-md:\s*14px/);
});
