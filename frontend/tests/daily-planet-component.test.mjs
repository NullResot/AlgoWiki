import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const componentPath = fileURLToPath(
  new URL("../src/components/pulse-demo/DailyPlanet.vue", import.meta.url),
);
const source = readFileSync(componentPath, "utf8");

test("daily planet renders exactly one image without carousel controls", () => {
  assert.equal((source.match(/<img\b/g) || []).length, 1);
  assert.doesNotMatch(source, /autoplay|carousel|pause|planet-selector/i);
  assert.match(source, /:src="planet\.src"/);
});

test("daily planet maps all three WebP assets and clips the source square", () => {
  assert.match(source, /planet-tempest\.webp/);
  assert.match(source, /planet-obsidian\.webp/);
  assert.match(source, /planet-ocean\.webp/);
  assert.match(source, /overflow:\s*hidden/);
  assert.match(source, /border-radius:\s*50%/);
});
