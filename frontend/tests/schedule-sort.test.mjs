import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { sortScheduleRows } from "../src/utils/scheduleSort.js";

const root = new URL("../", import.meta.url);

test("sortScheduleRows places ongoing and upcoming contests before ended contests", () => {
  const rows = [
    { id: 1, competition_type: "2026 CCPC 上海市赛", event_date: "2026-07-12", end_date: "2026-07-12", is_past: true },
    { id: 2, competition_type: "2026 ICPC 南京区域赛", event_date: "2026-11-07", end_date: "2026-11-08", is_past: true },
    { id: 3, competition_type: "2026 ICPC 南昌区域赛", event_date: "2026-12-19", end_date: "2026-12-20", is_past: false },
    { id: 4, competition_type: "2026 ICPC 沈阳区域赛", event_date: "2026-11-14", end_date: "2026-11-15", is_past: false },
    { id: 5, competition_type: "2026 ICPC 上海区域赛", event_date: "2026-12-05", end_date: "2026-12-06", is_past: false },
  ];

  const sorted = sortScheduleRows(rows);
  assert.deepEqual(
    sorted.map((item) => item.id),
    [4, 5, 3, 1, 2],
  );
  // Original array is not mutated.
  assert.deepEqual(
    rows.map((item) => item.id),
    [1, 2, 3, 4, 5],
  );
});

test("sortScheduleRows breaks ties by end_date then id", () => {
  const rows = [
    { id: 12, event_date: "2026-11-15", end_date: "2026-11-16", is_past: false },
    { id: 10, event_date: "2026-11-15", end_date: "2026-11-15", is_past: false },
    { id: 8, event_date: "2026-11-15", end_date: "2026-11-15", is_past: false },
  ];

  assert.deepEqual(
    sortScheduleRows(rows).map((item) => item.id),
    [8, 10, 12],
  );
});

test("CompetitionZonePage uses sortScheduleRows for filteredScheduleRows", async () => {
  const page = await readFile(new URL("src/pages/CompetitionZonePage.vue", root), "utf8");
  assert.match(page, /import\s*\{\s*sortScheduleRows\s*\}\s*from\s*["']\.\.\/utils\/scheduleSort["']/);
  assert.match(page, /return sortScheduleRows\(filtered\);/);
});
