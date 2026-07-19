import test from "node:test";
import assert from "node:assert/strict";

import { getDailyPlanetId } from "../src/features/pulse/dailyPlanet.js";

test("daily planet follows the Beijing business-date anchor", () => {
  assert.equal(getDailyPlanetId("2026-07-19"), "C");
  assert.equal(getDailyPlanetId("2026-07-20"), "A");
  assert.equal(getDailyPlanetId("2026-07-21"), "B");
  assert.equal(getDailyPlanetId("2026-07-22"), "C");
});

test("daily planet remains deterministic across month and year boundaries", () => {
  assert.equal(getDailyPlanetId("2026-08-01"), "A");
  assert.equal(getDailyPlanetId("2026-12-31"), "C");
  assert.equal(getDailyPlanetId("2027-01-01"), "A");
});

test("invalid or missing dates fall back to A", () => {
  for (const value of [undefined, "", "2026-02-30", "20-07-2026", "invalid"]) {
    assert.equal(getDailyPlanetId(value), "A");
  }
});
