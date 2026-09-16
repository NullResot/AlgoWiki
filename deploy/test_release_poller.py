import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest import mock


if os.name == "nt":
    sys.modules.setdefault("fcntl", mock.Mock())


POLLER_PATH = Path(__file__).with_name("server-poll-github-releases.py")
SPEC = importlib.util.spec_from_file_location("algowiki_release_poller", POLLER_PATH)
poller = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(poller)


class ReleasePollerTests(unittest.TestCase):
    def run_payload(self, **overrides):
        payload = {
            "event": "push",
            "head_branch": "test",
            "head_sha": "a" * 40,
            "conclusion": "success",
            "path": poller.WORKFLOW_PATH,
            "run_started_at": "2026-09-17T04:00:00Z",
            "head_repository": {"full_name": poller.REPOSITORY},
        }
        payload.update(overrides)
        return payload

    def test_successful_push_requires_the_canonical_workflow_and_repository(self):
        valid = self.run_payload()
        pull_request = self.run_payload(event="pull_request")
        wrong_workflow = self.run_payload(path=".github/workflows/untrusted.yml")
        wrong_repository = self.run_payload(head_repository={"full_name": "fork/AlgoWiki"})

        selected = poller.latest_successful_push(
            [pull_request, wrong_workflow, wrong_repository, valid],
            "test",
            "2026-09-17T03:00:00Z",
        )

        self.assertIs(selected, valid)
        self.assertIsNone(
            poller.latest_successful_push([valid], "test", "2026-09-17T05:00:00Z")
        )

    def test_production_approval_requires_github_actions_and_latest_success_status(self):
        deployment_revision = "b" * 40
        deployment = {
            "id": 123,
            "sha": deployment_revision,
            "ref": "main",
            "environment": "production",
            "created_at": "2026-09-17T04:00:00Z",
            "performed_via_github_app": {"slug": "github-actions"},
        }

        with mock.patch.object(
            poller,
            "api_get",
            side_effect=[[deployment], [{"state": "success"}]],
        ):
            self.assertTrue(
                poller.approved_production_deployment(
                    deployment_revision, "2026-09-17T03:00:00Z"
                )
            )

        deployment["performed_via_github_app"] = None
        with mock.patch.object(poller, "api_get", return_value=[deployment]):
            self.assertFalse(
                poller.approved_production_deployment(
                    deployment_revision, "2026-09-17T03:00:00Z"
                )
            )

    def test_production_source_must_be_a_same_repository_test_merge(self):
        deployment_revision = "c" * 40
        source_revision = "d" * 40
        pull_request = {
            "merged_at": "2026-09-17T04:00:00Z",
            "merge_commit_sha": deployment_revision,
            "base": {"ref": "main"},
            "head": {
                "ref": "test",
                "sha": source_revision,
                "repo": {"full_name": poller.REPOSITORY},
            },
        }

        with mock.patch.object(poller, "api_get", return_value=[pull_request]):
            self.assertEqual(
                poller.production_source_revision(deployment_revision), source_revision
            )


if __name__ == "__main__":
    unittest.main()
