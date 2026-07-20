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
