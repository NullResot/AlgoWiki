from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from .ai_moderation import AIModerationProviderError
from .models import (
    AIModerationConfig,
    AIModerationRecord,
    Answer,
    PulseDailyEdition,
    PulseLedgerEntry,
    Question,
    User,
)
from .pulse.services import get_wallet, submit_daily_answer


class AIModerationRetryModelTests(TestCase):
    def test_new_retry_record_is_due(self):
        record = AIModerationRecord.objects.create(
            target_type=AIModerationRecord.TargetType.ANSWER,
            target_id=41,
            retry_state=AIModerationRecord.RetryState.QUEUED,
            next_retry_at=timezone.now() - timedelta(seconds=1),
        )

        self.assertTrue(record.is_retry_due())

    def test_finished_record_is_not_due(self):
        record = AIModerationRecord.objects.create(
            target_type=AIModerationRecord.TargetType.ANSWER,
            target_id=42,
            retry_state=AIModerationRecord.RetryState.FINISHED,
            next_retry_at=timezone.now() - timedelta(seconds=1),
        )

        self.assertFalse(record.is_retry_due())


class AIModerationFailClosedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="moderation-queue-user", password="Pass123!"
        )
        self.now = timezone.datetime(
            2026, 7, 19, 10, 0, tzinfo=timezone.get_current_timezone()
        )
        self.config = AIModerationConfig.get_solo()
        self.config.is_enabled = True
        self.config.answer_enabled = True
        self.config.failure_action = AIModerationConfig.FailureAction.PENDING
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
                            '"categories":[],"summary":"内容安全","user_notice":""}'
                        )
                    }
                }
            ],
            "usage": {},
        }

    @patch("wiki.ai_moderation.invoke_ai_moderation_completion")
    def test_daily_answer_stays_pending_and_queues_retry_when_provider_fails(
        self, invoke
    ):
        invoke.side_effect = AIModerationProviderError("timeout", status_code=502)

        answer = submit_daily_answer(
            user=self.user,
            content_md="我会先证明单调性，再讨论边界。",
            now=self.now,
        )

        answer.refresh_from_db()
        self.assertEqual(answer.status, Answer.Status.PENDING)
        self.assertEqual(get_wallet(self.user)[PulseLedgerEntry.Asset.REROLL], 0)
        record = AIModerationRecord.objects.get(
            target_id=answer.id,
            target_type=AIModerationRecord.TargetType.ANSWER,
        )
        self.assertEqual(record.retry_state, AIModerationRecord.RetryState.QUEUED)
        self.assertEqual(record.attempt_count, 1)
        self.assertEqual(len(record.content_fingerprint), 64)
        self.assertIsNotNone(record.next_retry_at)

    @patch("wiki.ai_moderation.invoke_ai_moderation_completion")
    def test_safe_daily_answer_is_published_and_rewarded_after_review(self, invoke):
        invoke.return_value = self.safe_payload()

        answer = submit_daily_answer(
            user=self.user,
            content_md="先给出不变量，再用反例检查边界。",
            now=self.now,
        )

        answer.refresh_from_db()
        invoke.assert_called_once()
        self.assertEqual(answer.status, Answer.Status.VISIBLE)
        self.assertEqual(get_wallet(self.user)[PulseLedgerEntry.Asset.REROLL], 1)
        self.assertTrue(
            AIModerationRecord.objects.filter(
                target_id=answer.id,
                target_type=AIModerationRecord.TargetType.ANSWER,
                status=AIModerationRecord.Status.APPLIED,
            ).exists()
        )

    @patch("wiki.ai_moderation.invoke_ai_moderation_completion")
    def test_stale_retry_cannot_publish_edited_content(self, invoke):
        from .ai_moderation import retry_ai_moderation_record

        invoke.side_effect = AIModerationProviderError("timeout", status_code=502)
        answer = submit_daily_answer(
            user=self.user,
            content_md="旧内容需要审核。",
            now=self.now,
        )
        record = AIModerationRecord.objects.get(
            target_id=answer.id,
            target_type=AIModerationRecord.TargetType.ANSWER,
        )
        answer.content_md = "编辑后的新内容必须重新审核。"
        answer.save(update_fields=["content_md", "updated_at"])
        invoke.side_effect = None
        invoke.return_value = self.safe_payload()

        retry_ai_moderation_record(record)

        answer.refresh_from_db()
        record.refresh_from_db()
        self.assertEqual(answer.status, Answer.Status.PENDING)
        self.assertEqual(record.status, AIModerationRecord.Status.SKIPPED)
        self.assertEqual(record.retry_state, AIModerationRecord.RetryState.FINISHED)

    @patch("wiki.ai_moderation.invoke_ai_moderation_completion")
    def test_due_retry_is_processed_and_can_publish_safe_content(self, invoke):
        from .ai_moderation import process_due_ai_moderation_records

        invoke.side_effect = AIModerationProviderError("timeout", status_code=502)
        answer = submit_daily_answer(
            user=self.user,
            content_md="队列恢复后应继续完成审核。",
            now=self.now,
        )
        record = AIModerationRecord.objects.get(
            target_id=answer.id,
            target_type=AIModerationRecord.TargetType.ANSWER,
        )
        record.next_retry_at = timezone.now() - timedelta(seconds=1)
        record.save(update_fields=["next_retry_at"])
        invoke.side_effect = None
        invoke.return_value = self.safe_payload()

        processed = process_due_ai_moderation_records(limit=10)

        answer.refresh_from_db()
        self.assertEqual(processed, 1)
        self.assertEqual(answer.status, Answer.Status.VISIBLE)
        self.assertFalse(
            AIModerationRecord.objects.filter(
                target_id=answer.id,
                target_type=AIModerationRecord.TargetType.ANSWER,
                retry_state=AIModerationRecord.RetryState.QUEUED,
            ).exists()
        )
