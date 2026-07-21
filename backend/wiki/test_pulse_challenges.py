from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.test import TestCase

from .models import (
    CodeforcesBinding,
    CodeforcesEvidence,
    PulseChallengeAssignment,
    PulseLedgerEntry,
    PulseUserDay,
    User,
)
from .pulse.services import (
    PulseConflict,
    check_challenge_completion,
    choose_challenge,
    rating_band_divisions,
    reroll_challenge,
    target_problem_rating,
    write_ledger_entry,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")


def cf_submission(
    submission_id,
    created_at,
    *,
    contest_id,
    index,
    verdict="OK",
    participant_type="PRACTICE",
    handle="PulseHandle",
):
    return {
        "id": submission_id,
        "contestId": contest_id,
        "creationTimeSeconds": int(created_at.timestamp()),
        "problem": {"contestId": contest_id, "index": index},
        "author": {
            "participantType": participant_type,
            "members": [{"handle": handle}],
        },
        "verdict": verdict,
    }


class ChallengeCodeforcesClient:
    def __init__(self, *, rating=1200, problems=None, contests=None, standings=None, submissions=None):
        self.rating = rating
        self.problems = list(problems or [])
        self.contest_rows = list(contests or [])
        self.standings = dict(standings or {})
        self.submissions = list(submissions or [])

    def user_info(self, handle):
        payload = {"handle": handle}
        if self.rating is not None:
            payload["rating"] = self.rating
            payload["maxRating"] = self.rating
        return payload

    def user_status(self, handle, *, count=10000):
        return list(self.submissions)

    def problemset(self):
        return {"problems": list(self.problems), "problemStatistics": []}

    def contests(self):
        return list(self.contest_rows)

    def contest_standings(self, contest_id):
        return list(self.standings[int(contest_id)])


def problem(contest_id, index, rating, name=None):
    return {
        "contestId": contest_id,
        "index": index,
        "rating": rating,
        "name": name or f"Problem {contest_id}{index}",
    }


def contest(contest_id, name):
    return {
        "id": contest_id,
        "name": name,
        "phase": "FINISHED",
        "type": "CF",
    }


class PulseChallengeServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="challenger", password="Pass123!")
        self.now = datetime(2026, 7, 19, 12, 0, tzinfo=SHANGHAI)
        self.binding = CodeforcesBinding.objects.create(
            owner=self.user,
            active_user=self.user,
            handle="PulseHandle",
            handle_ci="pulsehandle",
            active_handle_ci="pulsehandle",
            rating=1200,
            verified_at=self.now,
        )

    def test_rating_rules_include_unrated_fallback_and_clamps(self):
        self.assertEqual(target_problem_rating(None), 1100)
        self.assertEqual(target_problem_rating(-100), 800)
        self.assertEqual(target_problem_rating(3400), 3500)
        self.assertEqual(rating_band_divisions(1399), {"div3", "div4"})
        self.assertEqual(rating_band_divisions(1400), {"div2"})
        self.assertEqual(rating_band_divisions(1899), {"div2"})
        self.assertEqual(rating_band_divisions(1900), {"div1"})

    def test_mode_a_excludes_accepted_problem_and_uses_nearest_available_rating(self):
        problems = [problem(10, "A", 1500), problem(11, "B", 1600), problem(12, "C", 1600)]
        history = [
            cf_submission(
                1,
                self.now - timedelta(days=1),
                contest_id=10,
                index="A",
            )
        ]
        client = ChallengeCodeforcesClient(
            rating=1200, problems=problems, submissions=history
        )

        assignment = choose_challenge(
            user=self.user,
            mode="A",
            client=client,
            now=self.now,
            chooser=lambda rows: rows[0],
        )

        self.assertEqual(assignment.target_key, "11:B")
        self.assertEqual(assignment.target_data["requested_rating"], 1500)
        self.assertEqual(assignment.target_data["rating"], 1600)
        self.assertEqual(assignment.deadline_at, datetime(2026, 7, 20, 4, 0, tzinfo=SHANGHAI))

    def test_daily_mode_is_locked_and_rerolls_stay_in_same_mode_twice(self):
        client = ChallengeCodeforcesClient(
            rating=1200,
            problems=[
                problem(20, "A", 1500),
                problem(21, "A", 1500),
                problem(22, "A", 1500),
                problem(23, "A", 1500),
            ],
        )
        initial = choose_challenge(
            user=self.user,
            mode="A",
            client=client,
            now=self.now,
            chooser=lambda rows: rows[0],
        )
        write_ledger_entry(
            user=self.user,
            asset=PulseLedgerEntry.Asset.REROLL,
            delta=2,
            event_key="test:reroll-wallet",
        )

        with self.assertRaises(PulseConflict):
            choose_challenge(
                user=self.user, mode="B", client=client, now=self.now
            )

        second = reroll_challenge(
            user=self.user,
            client=client,
            now=self.now,
            chooser=lambda rows: rows[0],
        )
        third = reroll_challenge(
            user=self.user,
            client=client,
            now=self.now,
            chooser=lambda rows: rows[0],
        )

        self.assertEqual(initial.mode, second.mode)
        self.assertEqual(second.mode, third.mode)
        self.assertEqual({initial.target_key, second.target_key, third.target_key}, {"20:A", "21:A", "22:A"})
        with self.assertRaises(PulseConflict):
            reroll_challenge(user=self.user, client=client, now=self.now)

    def test_mode_a_completion_requires_new_ac_and_awards_once(self):
        client = ChallengeCodeforcesClient(
            rating=1200, problems=[problem(30, "C", 1500)]
        )
        assignment = choose_challenge(
            user=self.user, mode="A", client=client, now=self.now
        )
        client.submissions = [
            cf_submission(
                301,
                self.now + timedelta(minutes=20),
                contest_id=30,
                index="C",
            )
        ]

        completed = check_challenge_completion(
            user=self.user,
            assignment_id=assignment.id,
            client=client,
            now=self.now + timedelta(minutes=21),
        )
        repeated = check_challenge_completion(
            user=self.user,
            assignment_id=assignment.id,
            client=client,
            now=self.now + timedelta(minutes=22),
        )

        self.assertEqual(completed.id, repeated.id)
        self.assertEqual(completed.status, PulseChallengeAssignment.Status.COMPLETED)
        self.assertEqual(
            PulseLedgerEntry.objects.get(
                user=self.user, asset=PulseLedgerEntry.Asset.POINT
            ).balance_after,
            1,
        )
        day = PulseUserDay.objects.get(user=self.user, business_date=self.now.date())
        self.assertIsNotNone(day.signed_at)
        self.assertTrue(CodeforcesEvidence.objects.filter(submission_id=301).exists())

    def test_mode_a_does_not_accept_submission_before_assignment(self):
        client = ChallengeCodeforcesClient(
            rating=1200,
            problems=[problem(31, "A", 1500)],
            submissions=[
                cf_submission(
                    310,
                    self.now - timedelta(minutes=1),
                    contest_id=31,
                    index="A",
                    verdict="WRONG_ANSWER",
                )
            ],
        )
        assignment = choose_challenge(
            user=self.user, mode="A", client=client, now=self.now
        )
        client.submissions[0]["verdict"] = "OK"

        with self.assertRaises(PulseConflict):
            check_challenge_completion(
                user=self.user,
                assignment_id=assignment.id,
                client=client,
                now=self.now + timedelta(minutes=1),
            )

    def test_mode_b_selects_unattempted_finished_contest_for_rating_band(self):
        contests = [
            contest(100, "Codeforces Round 100 (Div. 2)"),
            contest(101, "Codeforces Round 101 (Div. 3)"),
            contest(102, "Codeforces Round 102 (Div. 2)"),
        ]
        history = [
            cf_submission(
                900,
                self.now - timedelta(days=30),
                contest_id=100,
                index="A",
                verdict="WRONG_ANSWER",
            )
        ]
        standings = {
            102: [problem(102, "A", 800), problem(102, "B", 1200), problem(102, "C", 1600)]
        }
        client = ChallengeCodeforcesClient(
            rating=1500,
            contests=contests,
            standings=standings,
            submissions=history,
        )

        assignment = choose_challenge(
            user=self.user,
            mode="B",
            client=client,
            now=self.now,
            chooser=lambda rows: rows[0],
        )

        self.assertEqual(assignment.target_key, "contest:102")
        self.assertEqual(assignment.target_data["problem_count"], 3)
        self.assertEqual(assignment.target_data["required_solved"], 1)

    def test_mode_b_requires_virtual_distinct_accepted_problems_before_four(self):
        standings = {
            200: [
                problem(200, "A", 800),
                problem(200, "B", 900),
                problem(200, "C", 1100),
                problem(200, "D", 1300),
            ]
        }
        client = ChallengeCodeforcesClient(
            rating=1300,
            contests=[contest(200, "Codeforces Round 200 (Div. 3)")],
            standings=standings,
        )
        assignment = choose_challenge(
            user=self.user, mode="B", client=client, now=self.now
        )
        client.submissions = [
            cf_submission(
                2001,
                self.now + timedelta(hours=1),
                contest_id=200,
                index="A",
                participant_type="VIRTUAL",
            ),
            cf_submission(
                2002,
                self.now + timedelta(hours=1, minutes=10),
                contest_id=200,
                index="A",
                participant_type="VIRTUAL",
            ),
            cf_submission(
                2003,
                self.now + timedelta(hours=2),
                contest_id=200,
                index="B",
                participant_type="PRACTICE",
            ),
        ]
        with self.assertRaises(PulseConflict):
            check_challenge_completion(
                user=self.user,
                assignment_id=assignment.id,
                client=client,
                now=self.now + timedelta(hours=2),
            )

        client.submissions.append(
            cf_submission(
                2004,
                self.now + timedelta(hours=3),
                contest_id=200,
                index="B",
                participant_type="VIRTUAL",
            )
        )
        completed = check_challenge_completion(
            user=self.user,
            assignment_id=assignment.id,
            client=client,
            now=self.now + timedelta(hours=3),
        )

        self.assertEqual(completed.completion_data["solved_count"], 2)
        self.assertEqual(
            PulseLedgerEntry.objects.get(
                user=self.user, asset=PulseLedgerEntry.Asset.POINT
            ).balance_after,
            3,
        )

    def test_completion_after_deadline_is_rejected(self):
        client = ChallengeCodeforcesClient(
            rating=1200, problems=[problem(40, "A", 1500)]
        )
        assignment = choose_challenge(
            user=self.user, mode="A", client=client, now=self.now
        )
        client.submissions = [
            cf_submission(
                4001,
                datetime(2026, 7, 20, 4, 0, 1, tzinfo=SHANGHAI),
                contest_id=40,
                index="A",
            )
        ]

        with self.assertRaises(PulseConflict):
            check_challenge_completion(
                user=self.user,
                assignment_id=assignment.id,
                client=client,
                now=datetime(2026, 7, 20, 4, 0, 1, tzinfo=SHANGHAI),
            )
