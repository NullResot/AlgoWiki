from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from unittest.mock import Mock

from .models import (
    CodeforcesBinding,
    CodeforcesEvidence,
    CodeforcesVerification,
    SecurityAuditLog,
    User,
    UserNotification,
)
from .pulse.codeforces import CodeforcesClient
from .pulse.services import (
    PulseConflict,
    PulsePermissionDenied,
    PulseValidationError,
    admin_unbind_codeforces,
    self_unbind_codeforces,
    start_binding,
    verify_binding,
)


class FakeCodeforcesClient:
    def __init__(self, *, info=None, submissions=None):
        self.info = info or {
            "handle": "Tourist",
            "rating": 3828,
            "maxRating": 4009,
        }
        self.submissions = list(submissions or [])
        self.info_calls = []
        self.status_calls = []

    def user_info(self, handle):
        self.info_calls.append(handle)
        return dict(self.info)

    def user_status(self, handle, *, count=10000):
        self.status_calls.append((handle, count))
        return list(self.submissions)


def submission(
    submission_id,
    created_at,
    *,
    handle="Tourist",
    contest_id=4,
    index="A",
    verdict="OK",
):
    return {
        "id": submission_id,
        "contestId": contest_id,
        "creationTimeSeconds": int(created_at.timestamp()),
        "problem": {"contestId": contest_id, "index": index},
        "author": {"members": [{"handle": handle}]},
        "verdict": verdict,
    }


class CodeforcesBindingServiceTests(TestCase):
    def setUp(self):
        self.now = timezone.now().replace(microsecond=0)
        self.user = User.objects.create_user(
            username="binder", password="BindPass123!"
        )
        self.other = User.objects.create_user(
            username="other-binder", password="BindPass123!"
        )

    def test_start_binding_records_latest_submission_and_ten_minute_window(self):
        client = FakeCodeforcesClient(
            submissions=[submission(91, self.now - timedelta(minutes=2))]
        )

        verification = start_binding(
            user=self.user, handle=" tourist ", client=client, now=self.now
        )

        self.assertEqual(verification.handle, "Tourist")
        self.assertEqual(verification.handle_ci, "tourist")
        self.assertEqual(verification.baseline_submission_id, 91)
        self.assertEqual(verification.rating, 3828)
        self.assertEqual(verification.expires_at, self.now + timedelta(minutes=10))

    def test_start_binding_rejects_invalid_handle(self):
        with self.assertRaises(PulseValidationError):
            start_binding(
                user=self.user,
                handle="bad handle!",
                client=FakeCodeforcesClient(),
                now=self.now,
            )

    def test_verify_binding_accepts_a_new_4a_ac(self):
        verification = start_binding(
            user=self.user,
            handle="Tourist",
            client=FakeCodeforcesClient(
                submissions=[submission(100, self.now - timedelta(minutes=1))]
            ),
            now=self.now,
        )
        valid = submission(101, self.now + timedelta(minutes=1))

        binding = verify_binding(
            user=self.user,
            verification_id=verification.id,
            client=FakeCodeforcesClient(submissions=[valid]),
            now=self.now + timedelta(minutes=2),
        )

        self.assertEqual(binding.handle, "Tourist")
        self.assertEqual(binding.active_user, self.user)
        self.assertEqual(binding.verification_submission_id, 101)
        self.assertTrue(
            CodeforcesEvidence.objects.filter(
                submission_id=101,
                purpose=CodeforcesEvidence.Purpose.BINDING,
            ).exists()
        )
        verification.refresh_from_db()
        self.assertEqual(verification.status, CodeforcesVerification.Status.VERIFIED)

    def test_verify_binding_rejects_expired_session(self):
        verification = start_binding(
            user=self.user,
            handle="Tourist",
            client=FakeCodeforcesClient(),
            now=self.now,
        )

        with self.assertRaises(PulseConflict):
            verify_binding(
                user=self.user,
                verification_id=verification.id,
                client=FakeCodeforcesClient(
                    submissions=[submission(1, self.now + timedelta(minutes=11))]
                ),
                now=self.now + timedelta(minutes=11),
            )

        verification.refresh_from_db()
        self.assertEqual(verification.status, CodeforcesVerification.Status.EXPIRED)

    def test_verify_binding_rejects_invalid_submission_shapes(self):
        cases = {
            "old submission": submission(100, self.now + timedelta(minutes=1)),
            "wrong problem": submission(
                102, self.now + timedelta(minutes=1), contest_id=71, index="A"
            ),
            "not accepted": submission(
                102, self.now + timedelta(minutes=1), verdict="WRONG_ANSWER"
            ),
            "wrong author": submission(
                102, self.now + timedelta(minutes=1), handle="Petr"
            ),
            "before issue": submission(102, self.now - timedelta(seconds=1)),
        }

        for label, candidate in cases.items():
            with self.subTest(label=label):
                verification = CodeforcesVerification.objects.create(
                    user=self.user,
                    handle="Tourist",
                    handle_ci="tourist",
                    baseline_submission_id=100,
                    issued_at=self.now,
                    expires_at=self.now + timedelta(minutes=10),
                )
                with self.assertRaises(PulseConflict):
                    verify_binding(
                        user=self.user,
                        verification_id=verification.id,
                        client=FakeCodeforcesClient(submissions=[candidate]),
                        now=self.now + timedelta(minutes=2),
                    )

    def test_verify_binding_rejects_replayed_submission_id(self):
        CodeforcesEvidence.objects.create(
            submission_id=102,
            user=self.other,
            purpose=CodeforcesEvidence.Purpose.BINDING,
        )
        verification = CodeforcesVerification.objects.create(
            user=self.user,
            handle="Tourist",
            handle_ci="tourist",
            baseline_submission_id=100,
            issued_at=self.now,
            expires_at=self.now + timedelta(minutes=10),
        )

        with self.assertRaises(PulseConflict):
            verify_binding(
                user=self.user,
                verification_id=verification.id,
                client=FakeCodeforcesClient(
                    submissions=[submission(102, self.now + timedelta(minutes=1))]
                ),
                now=self.now + timedelta(minutes=2),
            )

    def _binding(self):
        return CodeforcesBinding.objects.create(
            owner=self.user,
            active_user=self.user,
            handle="Tourist",
            handle_ci="tourist",
            active_handle_ci="tourist",
            rating=3828,
            verified_at=self.now,
        )

    def test_self_unbind_requires_current_password(self):
        self._binding()

        with self.assertRaises(PulsePermissionDenied):
            self_unbind_codeforces(
                user=self.user, current_password="wrong", now=self.now
            )

    def test_self_unbind_preserves_history_and_applies_transfer_cooling(self):
        binding = self._binding()

        result = self_unbind_codeforces(
            user=self.user,
            current_password="BindPass123!",
            now=self.now,
        )

        self.assertEqual(result.id, binding.id)
        self.assertIsNone(result.active_user)
        self.assertIsNone(result.active_handle_ci)
        self.assertEqual(result.unbound_at, self.now)
        self.assertEqual(result.rebind_not_before, self.now + timedelta(days=7))
        self.assertTrue(UserNotification.objects.filter(user=self.user).exists())
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                user=self.user, metadata__action="codeforces_self_unbind"
            ).exists()
        )
    def test_original_owner_can_rebind_during_cooling_but_other_user_cannot(self):
        binding = self._binding()
        self_unbind_codeforces(
            user=self.user,
            current_password="BindPass123!",
            now=self.now,
        )

        owner_verification = start_binding(
            user=self.user,
            handle="Tourist",
            client=FakeCodeforcesClient(),
            now=self.now + timedelta(days=1),
        )
        self.assertEqual(owner_verification.handle_ci, binding.handle_ci)

        with self.assertRaises(PulseConflict):
            start_binding(
                user=self.other,
                handle="Tourist",
                client=FakeCodeforcesClient(),
                now=self.now + timedelta(days=1),
            )

    def test_admin_unbind_requires_reason_and_can_clear_cooling(self):
        binding = self._binding()
        admin = User.objects.create_user(
            username="pulse-admin", role=User.Role.ADMIN
        )

        with self.assertRaises(PulseValidationError):
            admin_unbind_codeforces(
                actor=admin, binding=binding, reason="", now=self.now
            )

        result = admin_unbind_codeforces(
            actor=admin,
            binding=binding,
            reason="用户申请迁移账号",
            allow_rebind_now=True,
            now=self.now,
        )

        self.assertEqual(result.rebind_not_before, self.now)
        self.assertEqual(result.unbound_by, admin)
        self.assertTrue(
            UserNotification.objects.filter(user=self.user, actor=admin).exists()
        )
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                user=self.user,
                metadata__action="codeforces_admin_unbind",
                metadata__allow_rebind_now=True,
            ).exists()
        )


class CodeforcesClientPaginationTests(TestCase):
    def test_user_status_all_reads_every_page(self):
        first_page = [{"id": value} for value in range(10000, 0, -1)]
        second_page = [{"id": -1}, {"id": -2}]
        client = CodeforcesClient()
        client._request = Mock(side_effect=[first_page, second_page])

        result = client.user_status_all("Tourist")

        self.assertEqual(len(result), 10002)
        self.assertEqual(
            client._request.call_args_list[1].args,
            ("user.status", {"handle": "Tourist", "from": 10001, "count": 10000}),
        )
