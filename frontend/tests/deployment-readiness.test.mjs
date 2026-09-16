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

test("CI discovers the Django suite without forcing HTTPS redirects on its test client", async () => {
  const workflow = await readFile(
    new URL(".github/workflows/ci-delivery.yml", projectRoot),
    "utf8",
  );

  assert.match(workflow, /SECURE_SSL_REDIRECT:\s*"0"[\s\S]*python backend\/manage\.py test wiki/);
});

test("CI retries GHCR mirror visibility without weakening the Redis digest lock", async () => {
  const workflow = await readFile(
    new URL(".github/workflows/ci-delivery.yml", projectRoot),
    "utf8",
  );

  assert.match(workflow, /for attempt in \$\(seq 1 6\)/);
  assert.match(workflow, /mirrored_digest.*REDIS_DIGEST/);
  assert.match(workflow, /sleep "\$\(\(attempt \* 5\)\)"/);
});

test("develop is validated by pull requests without a duplicate push workflow", async () => {
  const workflow = await readFile(
    new URL(".github/workflows/ci-delivery.yml", projectRoot),
    "utf8",
  );
  const pushBranches = workflow.match(/push:\s*\n\s+branches:\s*\n([\s\S]*?)\n\s+workflow_dispatch:/)?.[1] || "";

  assert.doesNotMatch(pushBranches, /-\s*develop/);
  assert.match(pushBranches, /-\s*test/);
  assert.match(pushBranches, /-\s*main/);
});

test("deployments use a server pull agent instead of exposing inbound CI access", async () => {
  const workflow = await readFile(
    new URL(".github/workflows/ci-delivery.yml", projectRoot),
    "utf8",
  );
  const testJob = workflow.split(/\n  authorize-test-release:/)[1]?.split(/\n  verify-production-promotion:/)[0] || "";
  const productionJob = workflow.split(/\n  authorize-production-release:/)[1] || "";

  assert.match(testJob, /runs-on:\s*ubuntu-latest/);
  assert.match(testJob, /Queue immutable release for the server pull agent/);
  assert.match(
    testJob,
    /url:\s*"https:\/\/test\.algowiki\.cn\/releases\/\$\{\{ github\.sha \}\}\?image_digest=\$\{\{ needs\.publish-test-image\.outputs\.digest \}\}"/,
  );
  assert.match(productionJob, /name:\s*Authorize production deployment/);
  assert.match(productionJob, /environment:[\s\S]*name:\s*production/);
  assert.match(productionJob, /runs-on:\s*ubuntu-latest/);
  assert.doesNotMatch(workflow, /DEPLOY_SSH_KEY|ssh -i|runs-on:\s*\[self-hosted/);
});

test("the server pull agent pins branch heads and production approval evidence", async () => {
  const poller = await readFile(
    new URL("deploy/server-poll-github-releases.py", projectRoot),
    "utf8",
  );

  assert.match(poller, /run\.get\("event"\) == "push"/);
  assert.match(poller, /run\.get\("path"\) == WORKFLOW_PATH/);
  assert.match(poller, /current_branch_sha\("test"\) != source_revision/);
  assert.match(poller, /current_branch_sha\("main"\) != deployment_revision/);
  assert.match(poller, /authorized_test_image\(source_revision, run_id, not_before\)/);
  assert.match(poller, /actions\/runs\/\{run_id\}\/job/);
  assert.match(poller, /parsed\.netloc != "test\.algowiki\.cn"/);
  assert.doesNotMatch(poller, /IMAGE_REPOSITORY}:sha-/);
  assert.match(poller, /approved_production_deployment\(deployment_revision, not_before\)/);
  assert.match(poller, /performed_via_github_app/);
});

test("assistant creation starts with valid nonzero budget limits", async () => {
  const component = await readFile(
    new URL("frontend/src/components/admin/AIAssistantManager.vue", projectRoot),
    "utf8",
  );

  assert.match(component, /form\.daily_request_limit"[^>]*min="1"/);
  assert.match(component, /form\.daily_token_limit"[^>]*min="1"/);
  assert.match(component, /daily_request_limit:\s*100/);
  assert.match(component, /daily_token_limit:\s*200000/);
});

test("production nginx normalizes the CDN client address for forwarding and rate limits", async () => {
  const nginx = await readFile(
    new URL("deploy/nginx.algowiki.conf", projectRoot),
    "utf8",
  );

  assert.match(nginx, /map \$http_ali_cdn_real_ip \$algowiki_cdn_client_ip/);
  assert.match(nginx, /limit_req_zone \$algowiki_client_ip zone=algowiki_auth/);
  assert.match(nginx, /proxy_set_header X-Forwarded-For \$algowiki_client_ip/);
  assert.doesNotMatch(nginx, /proxy_set_header X-Forwarded-For \$remote_addr/);
});
