import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

test("dynamic navigation remains visible when the header API is unavailable", async () => {
  const source = await readFile(new URL("src/composables/useHeaderNav.js", root), "utf8");
  const momentsFallback = source.match(/\{[^{}]*key:\s*"moments"[^{}]*\}/)?.[0] || "";

  assert.match(momentsFallback, /title:\s*"动态"/);
  assert.match(momentsFallback, /is_visible:\s*true/);
});
