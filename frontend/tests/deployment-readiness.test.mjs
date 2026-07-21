import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const projectRoot = new URL("../../", import.meta.url);

test("moderation worker waits until web migrations and health checks finish", async () => {
  const compose = await readFile(new URL("docker-compose.server.yml", projectRoot), "utf8");
  const worker = compose.split(/\n  moderation-worker:/)[1] || "";

  assert.match(worker, /depends_on:[\s\S]*web:[\s\S]*condition:\s*service_healthy/);
});

test("registry deployment retries health before checking feature routes", async () => {
  const script = await readFile(
    new URL("deploy/server-update-from-registry.sh", projectRoot),
    "utf8",
  );
  const healthPosition = script.indexOf("wait_for_app_health");
  const routesPosition = script.indexOf("Navigation and feature route checks");

  assert.ok(healthPosition >= 0, "deployment needs a bounded health retry");
  assert.ok(routesPosition > healthPosition, "route smoke tests must run after health");
  assert.match(script, /for attempt in \$\(seq 1 30\)/);
  assert.match(
    script,
    /remove_old_service_container "\$\{configured_compose_project\}" "moderation-worker"/,
  );
});
