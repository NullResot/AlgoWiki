import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);
const source = (path) => readFile(new URL(path, root), "utf8");

test("ranking panel uses a scroll viewport and server pagination controls", async () => {
  const panel = await source("src/components/pulse-demo/PulseRankingPanel.vue");

  assert.doesNotMatch(panel, /repeat\(5,/);
  assert.match(panel, /overflow-y:\s*auto/);
  assert.match(panel, /<option[^>]*10/);
  assert.match(panel, /<option[^>]*20/);
  assert.match(panel, /<option[^>]*50/);
  assert.match(panel, /上一页/);
  assert.match(panel, /下一页/);
  assert.match(panel, /pageSize/);
});

test("ranking store keeps pagination metadata and ignores stale responses", async () => {
  const store = await source("src/stores/pulse.js");

  assert.match(store, /rankingPage/);
  assert.match(store, /rankingRequestId/);
  assert.match(store, /requestId\s*!==\s*rankingRequestId/);
  assert.match(store, /total_pages/);
});

test("pulse page forwards scope, page, and page size to the server", async () => {
  const page = await source("src/pages/PulseDemoPage.vue");

  assert.match(page, /@change="loadRankingPage"/);
  assert.match(page, /page_size:\s*pageSize/);
  assert.match(page, /page,/);
});
