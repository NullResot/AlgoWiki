import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

test("announcement modal stays inside narrow mobile viewports", async () => {
  const source = await readFile(
    new URL("src/components/AnnouncementModal.vue", root),
    "utf8",
  );

  assert.match(source, /\.modal\s*\{[\s\S]*box-sizing:\s*border-box/);
  assert.match(source, /max-height:\s*calc\(100dvh\s*-\s*20px\)/);
  assert.match(source, /overflow-y:\s*auto/);
  assert.match(source, /overflow-wrap:\s*anywhere/);
  assert.match(source, /font-size:\s*clamp\(22px,/);
});
