#!/usr/bin/env python3

import fcntl
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path


API_ROOT = "https://api.github.com"
REPOSITORY = "NullResot/AlgoWiki"
WORKFLOW_PATH = ".github/workflows/ci-delivery.yml"
IMAGE_REPOSITORY = "ghcr.io/nullresot/algowiki-web"
STATE_ROOT = Path("/var/lib/algowiki/deployments")
LOCK_FILE = Path("/run/lock/algowiki-release-poller.lock")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
IMAGE_RE = re.compile(r"^ghcr\.io/nullresot/algowiki-web@sha256:[0-9a-f]{64}$")


def api_get(path: str, query: dict[str, str] | None = None):
    url = f"{API_ROOT}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "algowiki-release-poller/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def read_state(environment: str) -> dict[str, str]:
    state_file = STATE_ROOT / environment / "last-success"
    if not state_file.is_file():
        return {}
    values: dict[str, str] = {}
    for line in state_file.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key.strip()] = value.strip()
    return values


def current_branch_sha(branch: str) -> str:
    payload = api_get(f"/repos/{REPOSITORY}/git/ref/heads/{branch}")
    sha = payload.get("object", {}).get("sha", "")
    if not SHA_RE.fullmatch(sha):
        raise RuntimeError(f"GitHub returned an invalid {branch} branch revision")
    return sha


def latest_successful_push(runs: list[dict], branch: str, not_before: str) -> dict | None:
    for run in runs:
        if (
            run.get("event") == "push"
            and run.get("head_branch") == branch
            and run.get("conclusion") == "success"
            and run.get("path") == WORKFLOW_PATH
            and run.get("head_repository", {}).get("full_name") == REPOSITORY
            and run.get("run_started_at", "") >= not_before
        ):
            return run
    return None


def release_runs(workflow: str) -> list[dict]:
    runs: list[dict] = []
    for branch in ("test", "main"):
        payload = api_get(
            f"/repos/{REPOSITORY}/actions/workflows/{workflow}/runs",
            {
                "branch": branch,
                "event": "push",
                "status": "success",
                "per_page": "1",
            },
        )
        runs.extend(payload.get("workflow_runs", []))
    return runs


def resolve_test_image(source_revision: str) -> str:
    tag = f"{IMAGE_REPOSITORY}:sha-{source_revision}"
    subprocess.run(["docker", "pull", "--quiet", tag], check=True, timeout=900)
    result = subprocess.run(
        [
            "docker",
            "image",
            "inspect",
            "--format",
            "{{range .RepoDigests}}{{println .}}{{end}}",
            tag,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    images = [line.strip() for line in result.stdout.splitlines()]
    image = next((value for value in images if IMAGE_RE.fullmatch(value)), "")
    if not image:
        raise RuntimeError(f"No immutable GHCR digest resolved for {tag}")
    return image


def approved_production_deployment(deployment_revision: str, not_before: str) -> bool:
    deployments = api_get(
        f"/repos/{REPOSITORY}/deployments",
        {"sha": deployment_revision, "environment": "production", "per_page": "10"},
    )
    for deployment in deployments:
        if (
            deployment.get("sha") != deployment_revision
            or deployment.get("ref") != "main"
            or deployment.get("environment") != "production"
            or deployment.get("created_at", "") < not_before
            or (deployment.get("performed_via_github_app") or {}).get("slug") != "github-actions"
        ):
            continue
        statuses = api_get(f"/repos/{REPOSITORY}/deployments/{deployment['id']}/statuses")
        if statuses and statuses[0].get("state") == "success":
            return True
    return False


def production_source_revision(deployment_revision: str) -> str:
    pull_requests = api_get(f"/repos/{REPOSITORY}/commits/{deployment_revision}/pulls")
    for pull_request in pull_requests:
        if (
            pull_request.get("merged_at")
            and pull_request.get("base", {}).get("ref") == "main"
            and pull_request.get("head", {}).get("ref") == "test"
            and pull_request.get("head", {}).get("repo", {}).get("full_name") == REPOSITORY
            and pull_request.get("merge_commit_sha") == deployment_revision
        ):
            source_revision = pull_request.get("head", {}).get("sha", "")
            if SHA_RE.fullmatch(source_revision):
                return source_revision
    raise RuntimeError("Current main was not created by a same-repository test to main merge")


def deploy_test(run: dict) -> None:
    source_revision = run.get("head_sha", "")
    if not SHA_RE.fullmatch(source_revision):
        raise RuntimeError("Successful test run has an invalid revision")
    if read_state("test").get("deployment_revision") == source_revision:
        return
    if current_branch_sha("test") != source_revision:
        print("Latest successful test run is not the current test branch head; skipping")
        return
    image = resolve_test_image(source_revision)
    print(f"Deploying approved test revision {source_revision} as {image}", flush=True)
    subprocess.run(
        [
            "/usr/local/sbin/algowiki-ci-deploy-test",
            "--image",
            image,
            "--source-revision",
            source_revision,
            "--deployment-revision",
            source_revision,
        ],
        check=True,
        timeout=1800,
    )


def deploy_production(run: dict, not_before: str) -> None:
    deployment_revision = run.get("head_sha", "")
    if not SHA_RE.fullmatch(deployment_revision):
        raise RuntimeError("Successful production run has an invalid revision")
    if read_state("production").get("deployment_revision") == deployment_revision:
        return
    if current_branch_sha("main") != deployment_revision:
        print("Latest successful main run is not the current main branch head; skipping")
        return
    if not approved_production_deployment(deployment_revision, not_before):
        print("Current main revision has no successful GitHub production approval; skipping")
        return
    source_revision = production_source_revision(deployment_revision)
    print(
        f"Deploying approved production revision {deployment_revision} from tested source {source_revision}",
        flush=True,
    )
    subprocess.run(
        [
            "/usr/local/sbin/algowiki-ci-deploy-production",
            "--source-revision",
            source_revision,
            "--deployment-revision",
            deployment_revision,
        ],
        check=True,
        timeout=1800,
    )


def process_runs(runs: list[dict], not_before: str) -> None:
    failures: list[str] = []
    test_run = latest_successful_push(runs, "test", not_before)
    production_run = latest_successful_push(runs, "main", not_before)

    if test_run:
        try:
            deploy_test(test_run)
        except Exception as error:
            failures.append(f"test: {error}")
            print(f"Test release processing failed: {error}", file=sys.stderr, flush=True)
    if production_run:
        try:
            deploy_production(production_run, not_before)
        except Exception as error:
            failures.append(f"production: {error}")
            print(f"Production release processing failed: {error}", file=sys.stderr, flush=True)

    if failures:
        raise RuntimeError("; ".join(failures))


def main() -> int:
    if os.geteuid() != 0:
        raise RuntimeError("The release poller must run as root")
    not_before = os.environ.get("ALGOWIKI_RELEASE_NOT_BEFORE", "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", not_before):
        raise RuntimeError("ALGOWIKI_RELEASE_NOT_BEFORE must be an ISO UTC timestamp")

    LOCK_FILE.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    with LOCK_FILE.open("w", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another release poll is already running; skipping")
            return 0

        workflow = urllib.parse.quote(WORKFLOW_PATH, safe="")
        runs = release_runs(workflow)
        process_runs(runs, not_before)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Release poll failed: {error}", file=sys.stderr, flush=True)
        raise
