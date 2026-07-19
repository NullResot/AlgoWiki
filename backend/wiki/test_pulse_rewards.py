from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.test import TestCase

from .models import (
    CodeforcesBinding,
    PulseChallengeAssignment,
    PulseLedgerEntry,
    PulseMakeup,
    PulseRedemption,
    PulseRewardCampaign,
    PulseUserDay,
    User,
)
from .pulse.services import (
    PulseConflict,
    admin_grant_assets,
    check_challenge_completion,
    claim_active_campaigns,
    create_makeup,
    create_redemption_code,
    get_rankings,
    get_wallet,
    redeem_code,
    streak_summary,
    write_ledger_entry,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")


class RewardCodeforcesClient:
    def __init__(self):
        self.submissions = []

    def user_info(self, handle):
        return {"handle": handle, "rating": 1200, "maxRating": 1300}

    def user_status(self, handle, *, count=10000):
        return list(self.submissions)

    def problemset(self):
        return {
            "problems": [
                {
                    "contestId": 500,
                    "index": "A",
                    "rating": 1500,
                    "name": "Makeup Problem",
                }
            ]
        }


def accepted_submission(submission_id, created_at):
    return {
        "id": submission_id,
        "contestId": 500,
        "creationTimeSeconds": int(created_at.timestamp()),
        "problem": {"contestId": 500, "index": "A"},
        "author": {"participantType": "PRACTICE", "members": [{"handle": "RewardHandle"}]},
        "verdict": "OK",
    }


class PulseRewardServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reward-user", password="Pass123!")
        self.admin = User.objects.create_user(username="reward-admin", role=User.Role.ADMIN)
        self.now = datetime(2026, 7, 19, 12, 0, tzinfo=SHANGHAI)
        CodeforcesBinding.objects.create(
            owner=self.user,
            active_user=self.user,
            handle="RewardHandle",
            handle_ci="rewardhandle",
            active_handle_ci="rewardhandle",
            rating=1200,
            verified_at=self.now,
        )

    def test_ledger_event_is_idempotent_and_never_goes_negative(self):
        first, created = write_ledger_entry(
            user=self.user,
            asset=PulseLedgerEntry.Asset.REROLL,
            delta=1,
            event_key="reward:test:one",
        )
        repeated, repeated_created = write_ledger_entry(
            user=self.user,
            asset=PulseLedgerEntry.Asset.REROLL,
            delta=1,
            event_key="reward:test:one",
        )

        self.assertTrue(created)
        self.assertFalse(repeated_created)
        self.assertEqual(first.id, repeated.id)
        self.assertEqual(get_wallet(self.user)[PulseLedgerEntry.Asset.REROLL], 1)
        with self.assertRaises(PulseConflict):
            write_ledger_entry(
                user=self.user,
                asset=PulseLedgerEntry.Asset.REROLL,
                delta=-2,
                event_key="reward:test:negative",
            )

    def test_normal_makeup_consumes_ticket_and_completes_with_new_mode_a_ac(self):
        admin_grant_assets(
            actor=self.admin,
            user=self.user,
            rewards={PulseLedgerEntry.Asset.MAKEUP: 1},
            event_key="grant:normal-makeup",
            note="测试活动",
        )
        client = RewardCodeforcesClient()
        makeup = create_makeup(
            user=self.user,
            target_date=date(2026, 7, 17),
            kind=PulseMakeup.Kind.NORMAL,
            client=client,
            now=self.now,
        )

        self.assertEqual(makeup.status, PulseMakeup.Status.PENDING)
        self.assertEqual(makeup.assignment.mode, PulseChallengeAssignment.Mode.A)
        self.assertEqual(get_wallet(self.user)[PulseLedgerEntry.Asset.MAKEUP], 0)

        client.submissions = [accepted_submission(5001, self.now + timedelta(hours=1))]
        check_challenge_completion(
            user=self.user,
            assignment_id=makeup.assignment_id,
            client=client,
            now=self.now + timedelta(hours=1),
        )
        makeup.refresh_from_db()

        self.assertEqual(makeup.status, PulseMakeup.Status.COMPLETED)
        day = PulseUserDay.objects.get(user=self.user, business_date=date(2026, 7, 17))
        self.assertIsNotNone(day.signed_at)
        self.assertEqual(get_wallet(self.user)[PulseLedgerEntry.Asset.POINT], 1)

    def test_super_makeup_signs_immediately_and_duplicate_date_is_rejected(self):
        admin_grant_assets(
            actor=self.admin,
            user=self.user,
            rewards={PulseLedgerEntry.Asset.SUPER_MAKEUP: 1},
            event_key="grant:super-makeup",
        )
        makeup = create_makeup(
            user=self.user,
            target_date=date(2026, 7, 16),
            kind=PulseMakeup.Kind.SUPER,
            client=RewardCodeforcesClient(),
            now=self.now,
        )

        self.assertEqual(makeup.status, PulseMakeup.Status.COMPLETED)
        self.assertEqual(get_wallet(self.user)[PulseLedgerEntry.Asset.SUPER_MAKEUP], 0)
        self.assertEqual(get_wallet(self.user)[PulseLedgerEntry.Asset.POINT], 1)
        with self.assertRaises(PulseConflict):
            create_makeup(
                user=self.user,
                target_date=date(2026, 7, 16),
                kind=PulseMakeup.Kind.SUPER,
                client=RewardCodeforcesClient(),
                now=self.now,
            )

    def test_redemption_code_is_hashed_limited_and_idempotent(self):
        code = create_redemption_code(
            actor=self.admin,
            raw_code="PULSE-2026",
            reward_payload={PulseLedgerEntry.Asset.REROLL: 2, PulseLedgerEntry.Asset.MAKEUP: 1},
            starts_at=self.now - timedelta(minutes=1),
            ends_at=self.now + timedelta(days=1),
            max_uses=10,
            per_user_limit=1,
        )

        self.assertNotEqual(code.code_hash, "PULSE-2026")
        first = redeem_code(
            user=self.user,
            raw_code="pulse-2026",
            idempotency_key="redeem-request-one",
            now=self.now,
        )
        repeated = redeem_code(
            user=self.user,
            raw_code="PULSE-2026",
            idempotency_key="redeem-request-one",
            now=self.now,
        )

        self.assertEqual(first.id, repeated.id)
        self.assertEqual(PulseRedemption.objects.count(), 1)
        self.assertEqual(get_wallet(self.user)[PulseLedgerEntry.Asset.REROLL], 2)
        self.assertEqual(get_wallet(self.user)[PulseLedgerEntry.Asset.MAKEUP], 1)
        with self.assertRaises(PulseConflict):
            redeem_code(
                user=self.user,
                raw_code="PULSE-2026",
                idempotency_key="redeem-request-two",
                now=self.now,
            )

    def test_redemption_code_respects_time_window(self):
        create_redemption_code(
            actor=self.admin,
            raw_code="FUTURE-CODE",
            reward_payload={PulseLedgerEntry.Asset.REROLL: 1},
            starts_at=self.now + timedelta(hours=1),
            ends_at=self.now + timedelta(days=1),
        )

        with self.assertRaises(PulseConflict):
            redeem_code(
                user=self.user,
                raw_code="FUTURE-CODE",
                idempotency_key="future-request",
                now=self.now,
            )

    def test_active_campaign_is_claimed_once_on_first_visit(self):
        campaign = PulseRewardCampaign.objects.create(
            key="summer-2026",
            name="2026 夏季训练活动",
            reward_payload={PulseLedgerEntry.Asset.REROLL: 2},
            starts_at=self.now - timedelta(hours=1),
            ends_at=self.now + timedelta(days=2),
            is_enabled=True,
            created_by=self.admin,
        )

        first = claim_active_campaigns(user=self.user, now=self.now)
        repeated = claim_active_campaigns(user=self.user, now=self.now)

        self.assertEqual(first, [campaign.id])
        self.assertEqual(repeated, [])
        self.assertEqual(get_wallet(self.user)[PulseLedgerEntry.Asset.REROLL], 2)
        self.assertEqual(
            PulseLedgerEntry.objects.filter(
                event_key=f"pulse-campaign:{campaign.id}:{self.user.id}:reroll"
            ).count(),
            1,
        )

    def test_streaks_and_rankings_are_stable_and_exclude_banned_users(self):
        for target in (date(2026, 7, 15), date(2026, 7, 16), date(2026, 7, 18), date(2026, 7, 19)):
            from .pulse.services import get_or_create_daily_edition, get_or_create_user_day

            edition = get_or_create_daily_edition(business_date=target)
            day = get_or_create_user_day(user=self.user, edition=edition)
            day.signed_at = self.now
            day.save(update_fields=["signed_at", "updated_at"])
        write_ledger_entry(
            user=self.user,
            asset=PulseLedgerEntry.Asset.POINT,
            delta=4,
            event_key="ranking:user-points",
        )
        banned = User.objects.create_user(username="banned-ranker", is_banned=True)
        write_ledger_entry(
            user=banned,
            asset=PulseLedgerEntry.Asset.POINT,
            delta=99,
            event_key="ranking:banned-points",
        )

        summary = streak_summary(self.user, as_of_date=date(2026, 7, 19))
        rankings = get_rankings(as_of_date=date(2026, 7, 19))

        self.assertEqual(summary, {"current": 2, "longest": 2, "signed_dates": ["2026-07-15", "2026-07-16", "2026-07-18", "2026-07-19"]})
        self.assertEqual(rankings[0]["user_id"], self.user.id)
        self.assertNotIn(banned.id, {row["user_id"] for row in rankings})
