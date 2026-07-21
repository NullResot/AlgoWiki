from datetime import date
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from .models import (
    AIModerationConfig,
    Answer,
    PulseDailyEdition,
    PulseLedgerEntry,
    PulsePollOption,
    PulsePollVote,
    PulseUserDay,
    Question,
    User,
)
from .pulse.services import (
    PulseConflict,
    get_or_create_daily_edition,
    get_wallet,
    submit_daily_answer,
    submit_poll_vote,
)


class PulseDailyServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="daily-user", password="Pass123!")
        self.now = timezone.datetime(2026, 7, 19, 8, 30, tzinfo=timezone.get_current_timezone())

    def test_materialization_creates_one_published_edition_for_shanghai_date(self):
        first = get_or_create_daily_edition(now=self.now)
        second = get_or_create_daily_edition(now=self.now)

        self.assertEqual(first.id, second.id)
        self.assertEqual(first.date, date(2026, 7, 19))
        self.assertEqual(first.status, PulseDailyEdition.Status.PUBLISHED)
        self.assertEqual(PulseDailyEdition.objects.count(), 1)
        self.assertGreaterEqual(first.poll_options.count(), 2)

    def test_daily_question_never_uses_normal_seven_day_auto_close(self):
        edition = get_or_create_daily_edition(now=self.now)

        self.assertEqual(edition.question.status, Question.Status.OPEN)
        self.assertIsNone(edition.question.auto_close_at)

    def test_precreated_admin_edition_wins_over_random_materialization(self):
        admin = User.objects.create_user(username="topic-admin", role=User.Role.ADMIN)
        question = Question.objects.create(
            title="管理员预设话题",
            content_md="预设内容",
            author=admin,
            auto_close_at=None,
        )
        preset = PulseDailyEdition.objects.create(
            date=date(2026, 7, 19),
            question=question,
            poll_prompt="管理员预设投票",
            source_type=PulseDailyEdition.SourceType.ADMIN,
            status=PulseDailyEdition.Status.DRAFT,
            created_by=admin,
        )
        PulsePollOption.objects.create(edition=preset, position=1, text="A")
        PulsePollOption.objects.create(edition=preset, position=2, text="B")

        edition = get_or_create_daily_edition(now=self.now)

        self.assertEqual(edition.id, preset.id)
        self.assertEqual(edition.question.title, "管理员预设话题")
        self.assertEqual(edition.status, PulseDailyEdition.Status.PUBLISHED)

    def test_first_valid_answer_grants_one_reroll_ticket_only_once(self):
        config = AIModerationConfig.get_solo()
        config.is_enabled = True
        config.answer_enabled = True
        config.set_api_key("test-key")
        config.save()
        safe_payload = {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"risk_level":"safe","suggested_action":"approve",'
                            '"categories":[],"summary":"内容安全","user_notice":""}'
                        )
                    }
                }
            ],
            "usage": {},
        }
        with patch(
            "wiki.ai_moderation.invoke_ai_moderation_completion",
            return_value=safe_payload,
        ):
            first = submit_daily_answer(
                user=self.user,
                content_md="可读性优先，性能瓶颈再用数据定位。",
                now=self.now,
            )
            second = submit_daily_answer(
                user=self.user,
                content_md="关键路径可以进一步用基准测试验证。",
                now=self.now,
            )

        self.assertIsInstance(first, Answer)
        self.assertIsInstance(second, Answer)
        self.assertEqual(get_wallet(self.user)[PulseLedgerEntry.Asset.REROLL], 1)
        self.assertEqual(
            PulseLedgerEntry.objects.filter(
                user=self.user, asset=PulseLedgerEntry.Asset.REROLL
            ).count(),
            1,
        )
        day = PulseUserDay.objects.get(user=self.user, business_date=date(2026, 7, 19))
        self.assertIsNotNone(day.community_completed_at)
        self.assertIsNotNone(day.community_rewarded_at)

    def test_poll_vote_is_immutable_and_returns_aggregate(self):
        edition = get_or_create_daily_edition(now=self.now)
        options = list(edition.poll_options.all())

        result = submit_poll_vote(
            user=self.user, option_id=options[0].id, now=self.now
        )

        self.assertEqual(result["total_votes"], 1)
        self.assertEqual(result["selected_option_id"], options[0].id)
        self.assertEqual(sum(item["percentage"] for item in result["options"]), 100)
        self.assertEqual(PulsePollVote.objects.count(), 1)

        with self.assertRaises(PulseConflict):
            submit_poll_vote(
                user=self.user, option_id=options[1].id, now=self.now
            )

        day = PulseUserDay.objects.get(user=self.user, business_date=edition.date)
        self.assertIsNotNone(day.poll_completed_at)

    def test_materialize_command_can_prewarm_a_specific_date(self):
        output = StringIO()

        call_command("materialize_pulse", date="2026-07-21", stdout=output)

        self.assertTrue(PulseDailyEdition.objects.filter(date=date(2026, 7, 21)).exists())
        self.assertIn("2026-07-21", output.getvalue())
