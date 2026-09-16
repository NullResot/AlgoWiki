from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from .models import (
    CodeforcesBinding,
    CodeforcesEvidence,
    PulseDailyEdition,
    PulseLedgerEntry,
    PulseMakeup,
    PulsePollOption,
    PulsePollVote,
    PulseUserDay,
    Question,
    User,
)


class PulseModelConstraintTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pulse-one", password="Pass123!")
        self.other = User.objects.create_user(username="pulse-two", password="Pass123!")
        self.system = User.objects.create_user(username="pulse-system")
        self.question = Question.objects.create(
            title="今日讨论",
            content_md="说说你的判断。",
            author=self.system,
            auto_close_at=None,
        )
        self.edition = PulseDailyEdition.objects.create(
            date=date(2026, 7, 19),
            question=self.question,
            poll_prompt="你会先读题解吗？",
        )

    def test_only_one_active_binding_can_use_a_handle(self):
        CodeforcesBinding.objects.create(
            owner=self.user,
            active_user=self.user,
            handle="Tourist",
            handle_ci="tourist",
            active_handle_ci="tourist",
            verified_at=timezone.now(),
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            CodeforcesBinding.objects.create(
                owner=self.other,
                active_user=self.other,
                handle="tourist",
                handle_ci="tourist",
                active_handle_ci="tourist",
                verified_at=timezone.now(),
            )

    def test_only_one_active_binding_can_belong_to_a_user(self):
        CodeforcesBinding.objects.create(
            owner=self.user,
            active_user=self.user,
            handle="FirstHandle",
            handle_ci="firsthandle",
            active_handle_ci="firsthandle",
            verified_at=timezone.now(),
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            CodeforcesBinding.objects.create(
                owner=self.user,
                active_user=self.user,
                handle="SecondHandle",
                handle_ci="secondhandle",
                active_handle_ci="secondhandle",
                verified_at=timezone.now(),
            )

    def test_submission_evidence_is_globally_unique(self):
        CodeforcesEvidence.objects.create(
            submission_id=991,
            user=self.user,
            purpose=CodeforcesEvidence.Purpose.BINDING,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            CodeforcesEvidence.objects.create(
                submission_id=991,
                user=self.other,
                purpose=CodeforcesEvidence.Purpose.CHALLENGE,
            )

    def test_user_has_one_state_per_business_date(self):
        PulseUserDay.objects.create(
            user=self.user,
            edition=self.edition,
            business_date=self.edition.date,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            PulseUserDay.objects.create(
                user=self.user,
                edition=self.edition,
                business_date=self.edition.date,
            )

    def test_user_can_vote_only_once_per_edition(self):
        option_one = PulsePollOption.objects.create(
            edition=self.edition, position=1, text="会"
        )
        option_two = PulsePollOption.objects.create(
            edition=self.edition, position=2, text="不会"
        )
        PulsePollVote.objects.create(
            edition=self.edition, option=option_one, user=self.user
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            PulsePollVote.objects.create(
                edition=self.edition, option=option_two, user=self.user
            )

    def test_ledger_event_key_is_idempotent(self):
        PulseLedgerEntry.objects.create(
            user=self.user,
            asset=PulseLedgerEntry.Asset.POINT,
            delta=1,
            balance_after=1,
            event_key="challenge:2026-07-19:user-1",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            PulseLedgerEntry.objects.create(
                user=self.user,
                asset=PulseLedgerEntry.Asset.POINT,
                delta=1,
                balance_after=2,
                event_key="challenge:2026-07-19:user-1",
            )

    def test_makeup_target_can_only_be_claimed_once(self):
        target = self.edition.date - timedelta(days=1)
        PulseMakeup.objects.create(
            user=self.user,
            target_date=target,
            kind=PulseMakeup.Kind.SUPER,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            PulseMakeup.objects.create(
                user=self.user,
                target_date=target,
                kind=PulseMakeup.Kind.NORMAL,
            )
