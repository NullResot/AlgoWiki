from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from .models import AIModerationRecord


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
