from datetime import date
from unittest.mock import patch

from django.test import override_settings
from rest_framework.test import APITestCase

from .models import (
    AIModerationConfig,
    PulseDailyEdition,
    PulseTopicProposal,
    User,
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
