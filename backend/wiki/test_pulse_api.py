from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch

from django.core.cache import cache
from rest_framework.test import APIClient, APITestCase

from .models import CodeforcesBinding, PulseLedgerEntry, User
from .pulse.codeforces import CodeforcesUnavailable


SHANGHAI = ZoneInfo("Asia/Shanghai")


class ApiCodeforcesClient:
    def __init__(self):
        self.info = {"handle": "ApiHandle", "rating": 1200, "maxRating": 1400}
        self.submissions = []
        self.problems = [
            {"contestId": 700, "index": "A", "rating": 1500, "name": "API Problem"}
        ]

    def user_info(self, handle):
        return dict(self.info)

    def user_status(self, handle, *, count=10000):
        return list(self.submissions)

    def problemset(self):
        return {"problems": list(self.problems)}

    def contests(self):
        return []


class UnavailableCodeforcesClient(ApiCodeforcesClient):
    def user_info(self, handle):
        raise CodeforcesUnavailable("Codeforces unavailable")


def api_submission(submission_id, created_at, *, contest_id=4, index="A"):
    return {
        "id": submission_id,
        "contestId": contest_id,
        "creationTimeSeconds": int(created_at.timestamp()),
        "problem": {"contestId": contest_id, "index": index},
        "author": {"participantType": "PRACTICE", "members": [{"handle": "ApiHandle"}]},
        "verdict": "OK",
    }


class PulseApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="api-user", password="ApiPass123!")
        self.admin = User.objects.create_user(
            username="api-admin", password="ApiPass123!", role=User.Role.ADMIN
        )
        self.client = APIClient()
        self.cf = ApiCodeforcesClient()
        self.now = datetime.now(tz=SHANGHAI)

    def authenticate(self, user=None):
        self.client.force_authenticate(user=user or self.user)

    def test_today_is_public_but_personal_state_requires_authentication(self):
        anonymous = self.client.get("/api/pulse/today/")

        self.assertEqual(anonymous.status_code, 200)
        self.assertIn("edition", anonymous.data)
        self.assertIsNone(anonymous.data["me"])

        self.authenticate()
        personal = self.client.get("/api/pulse/today/")
        self.assertEqual(personal.status_code, 200)
        self.assertEqual(personal.data["me"]["wallet"]["point"], 0)
        self.assertEqual(personal.data["me"]["progress"], 0)

    def test_rankings_reject_invalid_rating_filters(self):
        response = self.client.get("/api/pulse/rankings/?rating_min=not-a-rating")

        self.assertEqual(response.status_code, 400)

    def test_rankings_return_server_pagination_with_global_ranks(self):
        for index in range(25):
            user = User.objects.create_user(username=f"rank-user-{index:02d}")
            PulseLedgerEntry.objects.create(
                user=user,
                asset=PulseLedgerEntry.Asset.POINT,
                delta=25 - index,
                balance_after=25 - index,
                event_key=f"api-ranking-{index}",
                source_type="test",
            )

        response = self.client.get("/api/pulse/rankings/?page=2&page_size=10")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["page"], 2)
        self.assertEqual(response.data["page_size"], 10)
        self.assertEqual(response.data["count"], 27)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertEqual(response.data["results"][0]["rank"], 11)

    def test_rankings_reject_unsupported_page_size(self):
        response = self.client.get("/api/pulse/rankings/?page_size=25")

        self.assertEqual(response.status_code, 400)

    def test_list_endpoints_reject_invalid_numeric_filters(self):
        self.authenticate()
        answers = self.client.get("/api/pulse/answers/?limit=not-a-number")

        self.authenticate(self.admin)
        ledger = self.client.get("/api/pulse/admin/ledger/?user_id=not-a-number")

        self.assertEqual(answers.status_code, 400)
        self.assertEqual(ledger.status_code, 400)

    def test_banned_user_cannot_mutate_pulse(self):
        self.user.is_banned = True
        self.user.save(update_fields=["is_banned"])
        self.authenticate()

        response = self.client.post(
            "/api/pulse/answers/", {"content_md": "这是一条有效回答。"}, format="json"
        )

        self.assertEqual(response.status_code, 403)

    @patch("wiki.pulse.views.get_codeforces_client")
    def test_binding_verify_and_self_unbind_flow(self, factory):
        factory.return_value = self.cf
        self.authenticate()
        started = self.client.post(
            "/api/pulse/codeforces/bind/start/", {"handle": "ApiHandle"}, format="json"
        )
        self.assertEqual(started.status_code, 201)

        issued_at = started.data["issued_at"]
        if isinstance(issued_at, str):
            issued_at = datetime.fromisoformat(issued_at.replace("Z", "+00:00"))
        self.cf.submissions = [api_submission(701, issued_at + timedelta(minutes=1))]
        verified = self.client.post(
            "/api/pulse/codeforces/bind/verify/",
            {"verification_id": started.data["id"]},
            format="json",
        )
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.data["handle"], "ApiHandle")

        wrong = self.client.post(
            "/api/pulse/codeforces/unbind/", {"current_password": "wrong"}, format="json"
        )
        self.assertEqual(wrong.status_code, 403)
        unbound = self.client.post(
            "/api/pulse/codeforces/unbind/",
            {"current_password": "ApiPass123!"},
            format="json",
        )
        self.assertEqual(unbound.status_code, 200)
        self.assertFalse(unbound.data["is_active"])

    @patch("wiki.pulse.views.get_codeforces_client")
    def test_codeforces_outage_maps_to_503(self, factory):
        factory.return_value = UnavailableCodeforcesClient()
        self.authenticate()

        response = self.client.post(
            "/api/pulse/codeforces/bind/start/", {"handle": "ApiHandle"}, format="json"
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "codeforces_unavailable")

    @patch("wiki.pulse.views.get_codeforces_client")
    def test_codeforces_actions_are_rate_limited_per_user(self, factory):
        factory.return_value = self.cf
        self.authenticate()

        responses = [
            self.client.post(
                "/api/pulse/codeforces/bind/start/",
                {"handle": "ApiHandle"},
                format="json",
            )
            for _ in range(13)
        ]

        self.assertTrue(all(response.status_code == 201 for response in responses[:12]))
        self.assertEqual(responses[-1].status_code, 429)

    def test_answer_and_vote_update_real_daily_state(self):
        self.authenticate()
        today = self.client.get("/api/pulse/today/").data
        option_id = today["edition"]["poll"]["options"][0]["id"]

        answer = self.client.post(
            "/api/pulse/answers/", {"content_md": "先写清晰版本，再用基准数据决定是否优化。"}, format="json"
        )
        vote = self.client.post(
            "/api/pulse/vote/", {"option_id": option_id}, format="json"
        )
        repeated = self.client.post(
            "/api/pulse/vote/", {"option_id": option_id}, format="json"
        )

        self.assertEqual(answer.status_code, 201)
        self.assertEqual(answer.data["wallet"]["reroll"], 1)
        self.assertEqual(vote.status_code, 201)
        self.assertEqual(repeated.status_code, 409)

    @patch("wiki.pulse.views.get_codeforces_client")
    def test_choose_and_check_mode_a_through_api(self, factory):
        factory.return_value = self.cf
        CodeforcesBinding.objects.create(
            owner=self.user,
            active_user=self.user,
            handle="ApiHandle",
            handle_ci="apihandle",
            active_handle_ci="apihandle",
            rating=1200,
            verified_at=self.now,
        )
        self.authenticate()
        chosen = self.client.post(
            "/api/pulse/challenges/choose/", {"mode": "A"}, format="json"
        )
        self.assertEqual(chosen.status_code, 201)
        assigned_at = chosen.data["assigned_at"]
        if isinstance(assigned_at, str):
            assigned_at = datetime.fromisoformat(assigned_at.replace("Z", "+00:00"))
        self.cf.submissions = [
            api_submission(702, assigned_at + timedelta(minutes=1), contest_id=700, index="A")
        ]

        checked = self.client.post(
            "/api/pulse/challenges/check/",
            {"assignment_id": chosen.data["id"]},
            format="json",
        )

        self.assertEqual(checked.status_code, 200)
        self.assertEqual(checked.data["status"], "completed")
        self.assertEqual(checked.data["points_awarded"], 1)

    @patch("wiki.pulse.views.get_codeforces_client")
    def test_pending_normal_makeup_is_returned_by_today_api(self, factory):
        factory.return_value = self.cf
        CodeforcesBinding.objects.create(
            owner=self.user,
            active_user=self.user,
            handle="ApiHandle",
            handle_ci="apihandle",
            active_handle_ci="apihandle",
            rating=1200,
            verified_at=self.now,
        )
        PulseLedgerEntry.objects.create(
            user=self.user,
            asset=PulseLedgerEntry.Asset.MAKEUP,
            delta=1,
            balance_after=1,
            event_key="api:pending-makeup-ticket",
            source_type="admin_grant",
        )
        self.authenticate()

        created = self.client.post(
            "/api/pulse/makeups/",
            {
                "target_date": (self.now.date() - timedelta(days=1)).isoformat(),
                "kind": "normal",
            },
            format="json",
        )
        today = self.client.get("/api/pulse/today/")

        self.assertEqual(created.status_code, 201)
        self.assertEqual(today.status_code, 200)
        pending = today.data["me"]["pending_makeup"]
        self.assertEqual(pending["id"], created.data["id"])
        self.assertEqual(pending["assignment"]["id"], created.data["assignment"]["id"])
        self.assertEqual(pending["status"], "pending")

    def test_admin_can_grant_and_unbind_with_reason(self):
        binding = CodeforcesBinding.objects.create(
            owner=self.user,
            active_user=self.user,
            handle="ApiHandle",
            handle_ci="apihandle",
            active_handle_ci="apihandle",
            rating=1200,
            verified_at=self.now,
        )
        self.authenticate(self.admin)
        missing_reason = self.client.post(
            f"/api/pulse/admin/bindings/{binding.id}/unbind/", {}, format="json"
        )
        self.assertEqual(missing_reason.status_code, 400)

        unbound = self.client.post(
            f"/api/pulse/admin/bindings/{binding.id}/unbind/",
            {"reason": "用户请求迁移", "allow_rebind_now": True},
            format="json",
        )
        grant = self.client.post(
            "/api/pulse/admin/grants/",
            {
                "user_id": self.user.id,
                "rewards": {"makeup": 1, "super_makeup": 1},
                "idempotency_key": "api-admin-grant",
                "note": "夏季活动",
            },
            format="json",
        )

        self.assertEqual(unbound.status_code, 200)
        self.assertFalse(unbound.data["is_active"])
        self.assertEqual(grant.status_code, 201)
        self.assertEqual(grant.data["wallet"]["makeup"], 1)

    def test_admin_creates_hashed_code_and_user_redeems_it(self):
        self.authenticate(self.admin)
        created = self.client.post(
            "/api/pulse/admin/codes/",
            {
                "code": "API-PULSE-2026",
                "reward_payload": {"reroll": 2},
                "max_uses": 5,
                "per_user_limit": 1,
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["code"], "API-PULSE-2026")

        self.authenticate(self.user)
        redeemed = self.client.post(
            "/api/pulse/redeem/",
            {"code": "API-PULSE-2026", "idempotency_key": "api-redeem-one"},
            format="json",
        )

        self.assertEqual(redeemed.status_code, 201)
        self.assertEqual(redeemed.data["wallet"]["reroll"], 2)
        self.assertEqual(
            PulseLedgerEntry.objects.filter(user=self.user, asset="reroll").count(), 1
        )

    def test_admin_configures_activity_reward_claimed_on_today_visit(self):
        self.authenticate(self.admin)
        created = self.client.post(
            "/api/pulse/admin/campaigns/",
            {
                "key": "api-summer-2026",
                "name": "API 夏季活动",
                "reward_payload": {"reroll": 1, "makeup": 1},
                "starts_at": (self.now - timedelta(hours=1)).isoformat(),
                "ends_at": (self.now + timedelta(days=1)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)

        self.authenticate(self.user)
        today = self.client.get("/api/pulse/today/")
        repeated = self.client.get("/api/pulse/today/")

        self.assertEqual(today.status_code, 200)
        self.assertEqual(today.data["me"]["wallet"]["reroll"], 1)
        self.assertEqual(today.data["me"]["wallet"]["makeup"], 1)
        self.assertEqual(today.data["me"]["claimed_campaign_ids"], [created.data["id"]])
        self.assertEqual(repeated.data["me"]["claimed_campaign_ids"], [])
