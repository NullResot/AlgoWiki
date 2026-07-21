from datetime import date, timedelta
from unittest.mock import patch

from django.utils import timezone
from rest_framework.test import APITestCase

from .models import (
    AIModerationConfig,
    AIModerationRecord,
    Answer,
    PulseDailyEdition,
    PulseLedgerEntry,
    PulseTopicProposal,
    User,
    Question,
)


class PulseTopicProposalTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="topic-author", password="Pass123!"
        )
        self.admin = User.objects.create_user(
            username="topic-admin", password="Pass123!", role=User.Role.ADMIN
        )
        self.config = AIModerationConfig.get_solo()
        self.config.is_enabled = True
        self.config.topic_proposal_enabled = True
        self.config.set_api_key("test-key")
        self.config.save()

    @staticmethod
    def safe_payload():
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"risk_level":"safe","suggested_action":"approve",'
                            '"categories":[],"summary":"适合公开讨论","user_notice":""}'
                        )
                    }
                }
            ],
            "usage": {},
        }

    @patch("wiki.ai_moderation.invoke_ai_moderation_completion")
    def test_safe_proposal_requires_admin_schedule(self, invoke):
        invoke.return_value = self.safe_payload()
        self.client.force_authenticate(self.user)

        response = self.client.post(
            "/api/pulse/topic-proposals/",
            {
                "title": "赛时先写暴力还是先证明？",
                "content_md": "讨论时间分配策略与风险控制。",
                "tags": ["赛时策略"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        proposal = PulseTopicProposal.objects.get(id=response.data["id"])
        self.assertEqual(proposal.status, PulseTopicProposal.Status.ADMIN_PENDING)
        self.assertFalse(
            PulseDailyEdition.objects.filter(
                source_payload__proposal_id=proposal.id
            ).exists()
        )

    def test_admin_schedule_reserves_future_date(self):
        proposal = PulseTopicProposal.objects.create(
            author=self.user,
            title="赛时先写暴力还是先证明？",
            content_md="讨论时间分配策略与风险控制。",
            tags=["赛时策略"],
            status=PulseTopicProposal.Status.ADMIN_PENDING,
        )
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            f"/api/pulse/admin/topic-proposals/{proposal.id}/schedule/",
            {
                "scheduled_date": "2026-07-23",
                "poll_prompt": "你更倾向哪一种？",
                "poll_options": ["先写暴力", "先证明"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        edition = PulseDailyEdition.objects.get(date=date(2026, 7, 23))
        proposal.refresh_from_db()
        self.assertEqual(edition.source_type, PulseDailyEdition.SourceType.HOT)
        self.assertEqual(edition.status, PulseDailyEdition.Status.DRAFT)
        self.assertEqual(edition.source_payload["proposal_id"], proposal.id)
        self.assertEqual(proposal.status, PulseTopicProposal.Status.SCHEDULED)
        self.assertEqual(proposal.edition_id, edition.id)


class PulseDiscussionArchiveTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="discussion-reader", password="Pass123!"
        )
        self.admin = User.objects.create_user(
            username="discussion-admin", password="Pass123!", role=User.Role.ADMIN
        )
        self.config = AIModerationConfig.get_solo()
        self.config.is_enabled = True
        self.config.answer_enabled = True
        self.config.failure_action = AIModerationConfig.FailureAction.PENDING
        self.config.set_api_key("test-key")
        self.config.save()
        self.yesterday = self.make_edition(
            date(2026, 7, 19), "昨天的图论讨论", "补图思想什么时候最自然？"
        )
        self.today = self.make_edition(
            date(2026, 7, 20), "今天的动态规划讨论", "状态设计还是转移设计更重要？"
        )

    def make_edition(self, target_date, title, content):
        question = Question.objects.create(
            author=self.admin,
            title=title,
            content_md=content,
            status=Question.Status.OPEN,
            auto_close_at=None,
        )
        return PulseDailyEdition.objects.create(
            date=target_date,
            question=question,
            poll_prompt="你更认同哪一种？",
            source_type=PulseDailyEdition.SourceType.ADMIN,
            status=PulseDailyEdition.Status.PUBLISHED,
            created_by=self.admin,
        )

    @staticmethod
    def safe_payload():
        return PulseTopicProposalTests.safe_payload()

    def test_archive_lists_newest_first_and_supports_search(self):
        response = self.client.get(
            "/api/pulse/discussions/", {"q": "动态规划", "page_size": 10}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["date"], "2026-07-20")
        self.assertEqual(response.data["results"][0]["answer_count"], 0)

    @patch("wiki.ai_moderation.invoke_ai_moderation_completion")
    def test_historical_safe_answer_is_visible_but_never_rewarded(self, invoke):
        invoke.return_value = self.safe_payload()
        self.client.force_authenticate(self.user)

        response = self.client.post(
            "/api/pulse/discussions/2026-07-19/answers/",
            {"content_md": "补充一个昨天没有想到的反例。"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Answer.Status.VISIBLE)
        self.assertFalse(
            PulseLedgerEntry.objects.filter(
                user=self.user, asset=PulseLedgerEntry.Asset.REROLL
            ).exists()
        )

    @patch("wiki.ai_moderation.invoke_ai_moderation_completion")
    def test_author_can_see_own_pending_answer_but_public_cannot(self, invoke):
        invoke.side_effect = RuntimeError("provider offline")
        self.client.force_authenticate(self.user)
        create_response = self.client.post(
            "/api/pulse/discussions/2026-07-19/answers/",
            {"content_md": "这条回答等待审核后才能公开。"},
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.data["status"], Answer.Status.PENDING)

        mine = self.client.get("/api/pulse/discussions/2026-07-19/")
        self.assertEqual(len(mine.data["answers"]), 1)
        self.assertEqual(mine.data["answers"][0]["status"], Answer.Status.PENDING)

        self.client.force_authenticate(user=None)
        public = self.client.get("/api/pulse/discussions/2026-07-19/")
        self.assertEqual(public.data["answers"], [])
