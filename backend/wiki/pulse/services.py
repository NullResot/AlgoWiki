import re
import secrets
import hashlib
from datetime import datetime, timedelta, timezone as datetime_timezone
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.db.models import Count, OuterRef, Subquery
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from django.utils.crypto import salted_hmac

from ..models import (
    Answer,
    CodeforcesBinding,
    CodeforcesEvidence,
    CodeforcesVerification,
    PulseDailyEdition,
    PulseChallengeAssignment,
    PulseLedgerEntry,
    PulseMakeup,
    PulsePollOption,
    PulsePollVote,
    PulseRedemption,
    PulseRedemptionCode,
    PulseRewardCampaign,
    PulseUserDay,
    Question,
    SecurityAuditLog,
    User,
    UserNotification,
)
from .codeforces import CodeforcesError


HANDLE_RE = re.compile(r"^[A-Za-z0-9_.-]{3,24}$")
BINDING_WINDOW = timedelta(minutes=10)
HANDLE_TRANSFER_COOLDOWN = timedelta(days=7)
SHANGHAI_ZONE = ZoneInfo("Asia/Shanghai")

CURATED_DAILY_CONTENT = (
    {
        "title": "竞赛代码，到底应不应该为可读性牺牲一点速度？",
        "content": "当常数优化和表达清晰发生冲突时，你会把界线画在哪里？请给出一次真实经历或判断规则。",
        "poll": "赛后补题，应该先看官方题解吗？",
        "options": ("先独立想够 60 分钟", "卡住 20 分钟就看题解", "按题目难度动态决定"),
    },
    {
        "title": "一场比赛中，先做稳题还是先冲最有灵感的题？",
        "content": "不同比赛阶段可能需要不同策略。说说你如何判断当前最值得投入的题目。",
        "poll": "比赛前十分钟应该快速浏览全部题目吗？",
        "options": ("应该，先建立全局地图", "不应该，读到可做题就开写", "取决于比赛时长"),
    },
    {
        "title": "算法模板越完整，现场发挥就一定越稳定吗？",
        "content": "模板可以降低记忆负担，也可能让人跳过真正理解。你如何维护自己的模板库？",
        "poll": "不理解证明的模板可以在比赛中使用吗？",
        "options": ("可以，先解决问题", "不可以，风险不可控", "只使用经过大量验证的部分"),
    },
)


class PulseError(Exception):
    code = "pulse_error"

    def __init__(self, message, *, code=None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class PulseValidationError(PulseError):
    code = "validation_error"


class PulseConflict(PulseError):
    code = "conflict"


class PulsePermissionDenied(PulseError):
    code = "permission_denied"


class PulseExternalUnavailable(PulseError):
    code = "codeforces_unavailable"


def normalize_handle(raw_handle):
    handle = str(raw_handle or "").strip()
    if not HANDLE_RE.fullmatch(handle):
        raise PulseValidationError("请输入 3 至 24 位合法的 Codeforces Handle。")
    return handle, handle.casefold()


def _call_codeforces(callback):
    try:
        return callback()
    except CodeforcesError as exc:
        raise PulseExternalUnavailable(str(exc)) from exc


def _latest_submission_id(submissions):
    return max((int(item.get("id") or 0) for item in submissions), default=0)


def _assert_handle_can_bind(*, user, handle_ci, now):
    active_for_handle = CodeforcesBinding.objects.filter(
        active_handle_ci=handle_ci
    ).first()
    if active_for_handle:
        if active_for_handle.owner_id == user.id:
            raise PulseConflict("这个 Handle 已经绑定到你的账号。", code="already_bound")
        raise PulseConflict("这个 Handle 已绑定到其他 AlgoWiki 用户。", code="handle_in_use")

    if CodeforcesBinding.objects.filter(active_user=user).exists():
        raise PulseConflict("请先解绑当前 Codeforces 账号。", code="user_already_bound")

    cooling = (
        CodeforcesBinding.objects.filter(handle_ci=handle_ci, rebind_not_before__gt=now)
        .order_by("-unbound_at", "-id")
        .first()
    )
    if cooling and cooling.owner_id != user.id:
        raise PulseConflict(
            "这个 Handle 正处于解绑冷却期。", code="handle_cooling"
        )


def start_binding(*, user, handle, client, now=None):
    now = now or timezone.now()
    requested_handle, requested_handle_ci = normalize_handle(handle)
    info = _call_codeforces(lambda: client.user_info(requested_handle))
    canonical_handle, canonical_handle_ci = normalize_handle(
        info.get("handle") or requested_handle
    )
    if canonical_handle_ci != requested_handle_ci:
        raise PulseValidationError("Codeforces 返回的 Handle 与请求不一致。")
    submissions = _call_codeforces(
        lambda: client.user_status(canonical_handle, count=1)
    )

    with transaction.atomic():
        _assert_handle_can_bind(user=user, handle_ci=canonical_handle_ci, now=now)
        CodeforcesVerification.objects.select_for_update().filter(
            status=CodeforcesVerification.Status.PENDING
        ).filter(user=user).update(status=CodeforcesVerification.Status.CANCELLED)
        CodeforcesVerification.objects.select_for_update().filter(
            status=CodeforcesVerification.Status.PENDING,
            handle_ci=canonical_handle_ci,
        ).exclude(user=user).update(status=CodeforcesVerification.Status.CANCELLED)
        return CodeforcesVerification.objects.create(
            user=user,
            handle=canonical_handle,
            handle_ci=canonical_handle_ci,
            baseline_submission_id=_latest_submission_id(submissions),
            rating=info.get("rating"),
            max_rating=info.get("maxRating"),
            issued_at=now,
            expires_at=now + BINDING_WINDOW,
        )


def _submission_author_matches(item, handle_ci):
    members = ((item.get("author") or {}).get("members") or [])
    return any(str(member.get("handle") or "").casefold() == handle_ci for member in members)


def _is_binding_submission(item, verification):
    problem = item.get("problem") or {}
    submission_id = int(item.get("id") or 0)
    created_seconds = int(item.get("creationTimeSeconds") or 0)
    created_at = datetime.fromtimestamp(created_seconds, tz=datetime_timezone.utc)
    return all(
        (
            submission_id > verification.baseline_submission_id,
            int(problem.get("contestId") or item.get("contestId") or 0) == 4,
            str(problem.get("index") or "").upper() == "A",
            item.get("verdict") == "OK",
            _submission_author_matches(item, verification.handle_ci),
            verification.issued_at <= created_at <= verification.expires_at,
        )
    )


def verify_binding(*, user, verification_id, client, now=None):
    now = now or timezone.now()
    verification = CodeforcesVerification.objects.filter(
        id=verification_id, user=user
    ).first()
    if not verification:
        raise PulseValidationError("绑定验证不存在。")
    if verification.status != CodeforcesVerification.Status.PENDING:
        raise PulseConflict("这个绑定验证已经结束。", code="verification_closed")
    if now > verification.expires_at:
        CodeforcesVerification.objects.filter(id=verification.id).update(
            status=CodeforcesVerification.Status.EXPIRED
        )
        raise PulseConflict("验证已超过 10 分钟，请重新开始。", code="verification_expired")

    submissions = _call_codeforces(
        lambda: client.user_status(verification.handle, count=10000)
    )
    candidate = next(
        (item for item in submissions if _is_binding_submission(item, verification)),
        None,
    )
    if candidate is None:
        CodeforcesVerification.objects.filter(id=verification.id).update(
            attempt_count=verification.attempt_count + 1
        )
        raise PulseConflict(
            "尚未检测到验证窗口内新的 4A AC。", code="proof_not_found"
        )

    submission_id = int(candidate["id"])
    try:
        with transaction.atomic():
            locked = CodeforcesVerification.objects.select_for_update().get(
                id=verification.id, user=user
            )
            if locked.status != CodeforcesVerification.Status.PENDING:
                raise PulseConflict("这个绑定验证已经结束。", code="verification_closed")
            _assert_handle_can_bind(user=user, handle_ci=locked.handle_ci, now=now)
            evidence = CodeforcesEvidence.objects.create(
                submission_id=submission_id,
                user=user,
                purpose=CodeforcesEvidence.Purpose.BINDING,
                source_type="codeforces_verification",
                source_id=locked.id,
                payload={
                    "contest_id": 4,
                    "problem_index": "A",
                    "creation_time_seconds": candidate.get("creationTimeSeconds"),
                },
            )
            binding = CodeforcesBinding.objects.create(
                owner=user,
                active_user=user,
                handle=locked.handle,
                handle_ci=locked.handle_ci,
                active_handle_ci=locked.handle_ci,
                rating=locked.rating,
                max_rating=locked.max_rating,
                verified_at=now,
                last_synced_at=now,
                verification_submission_id=evidence.submission_id,
            )
            locked.status = CodeforcesVerification.Status.VERIFIED
            locked.verified_submission_id = submission_id
            locked.attempt_count += 1
            locked.save(
                update_fields=[
                    "status",
                    "verified_submission_id",
                    "attempt_count",
                    "updated_at",
                ]
            )
            SecurityAuditLog.objects.create(
                event_type="codeforces_bound",
                user=user,
                username=user.username,
                detail=f"Codeforces Handle {binding.handle} 已绑定",
                metadata={
                    "action": "codeforces_bind",
                    "handle": binding.handle,
                    "submission_id": submission_id,
                },
            )
            return binding
    except IntegrityError as exc:
        raise PulseConflict(
            "该验证提交或 Handle 已被使用。", code="proof_replayed"
        ) from exc


def _deactivate_binding(*, binding, actor, reason, rebind_not_before, now, action):
    binding.active_user = None
    binding.active_handle_ci = None
    binding.unbound_at = now
    binding.rebind_not_before = rebind_not_before
    binding.unbound_by = actor
    binding.unbind_reason = reason[:300]
    binding.save(
        update_fields=[
            "active_user",
            "active_handle_ci",
            "unbound_at",
            "rebind_not_before",
            "unbound_by",
            "unbind_reason",
            "updated_at",
        ]
    )
    SecurityAuditLog.objects.create(
        event_type="codeforces_unbound",
        user=binding.owner,
        username=binding.owner.username,
        detail=f"Codeforces Handle {binding.handle} 已解绑",
        metadata={
            "action": action,
            "binding_id": binding.id,
            "handle": binding.handle,
            "reason": reason,
            "allow_rebind_now": rebind_not_before <= now,
            "actor_id": actor.id if actor else None,
        },
    )
    UserNotification.objects.create(
        user=binding.owner,
        actor=actor if actor and actor.id != binding.owner_id else None,
        title="Codeforces 账号已解绑",
        content=f"Handle {binding.handle} 已解绑。{reason}"[:500],
        link="/profile",
        level=UserNotification.Level.WARNING,
        target_type="codeforces_binding",
        target_id=binding.id,
    )
    return binding


def self_unbind_codeforces(*, user, current_password, now=None):
    now = now or timezone.now()
    if not user.check_password(current_password or ""):
        raise PulsePermissionDenied("当前密码不正确。")
    with transaction.atomic():
        binding = (
            CodeforcesBinding.objects.select_for_update()
            .filter(active_user=user)
            .first()
        )
        if not binding:
            raise PulseConflict("当前没有已绑定的 Codeforces 账号。")
        return _deactivate_binding(
            binding=binding,
            actor=user,
            reason="用户自助解绑",
            rebind_not_before=now + HANDLE_TRANSFER_COOLDOWN,
            now=now,
            action="codeforces_self_unbind",
        )


def admin_unbind_codeforces(
    *, actor, binding, reason, allow_rebind_now=False, now=None
):
    now = now or timezone.now()
    if not actor or not actor.is_manager:
        raise PulsePermissionDenied("只有管理员可以代为解绑。")
    reason = str(reason or "").strip()
    if not reason:
        raise PulseValidationError("管理员解绑必须填写原因。")
    with transaction.atomic():
        locked = CodeforcesBinding.objects.select_for_update().get(id=binding.id)
        if not locked.is_active:
            raise PulseConflict("这个绑定已经解除。")
        return _deactivate_binding(
            binding=locked,
            actor=actor,
            reason=reason,
            rebind_not_before=now if allow_rebind_now else now + HANDLE_TRANSFER_COOLDOWN,
            now=now,
            action="codeforces_admin_unbind",
        )


def shanghai_business_date(now=None):
    moment = now or timezone.now()
    return timezone.localtime(moment, SHANGHAI_ZONE).date()


def challenge_deadline(business_date):
    return datetime.combine(
        business_date + timedelta(days=1),
        datetime.min.time().replace(hour=4),
        tzinfo=SHANGHAI_ZONE,
    )


def _system_user():
    user, created = User.objects.get_or_create(
        username="pulse-system",
        defaults={"is_active": False, "first_name": "午夜脉冲"},
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


def _publish_existing_edition(edition):
    if edition.status == PulseDailyEdition.Status.DRAFT:
        edition.status = PulseDailyEdition.Status.PUBLISHED
        edition.save(update_fields=["status", "updated_at"])
    edition.question.clear_auto_close()
    if edition.question.status != Question.Status.OPEN or edition.question.auto_close_at:
        edition.question.status = Question.Status.OPEN
        edition.question.auto_close_at = None
        edition.question.save(update_fields=["status", "auto_close_at", "updated_at"])
    return edition


def get_or_create_daily_edition(*, now=None, business_date=None):
    target_date = business_date or shanghai_business_date(now)
    existing = PulseDailyEdition.objects.select_related("question").filter(
        date=target_date
    ).first()
    if existing:
        return _publish_existing_edition(existing)

    topic = CURATED_DAILY_CONTENT[target_date.toordinal() % len(CURATED_DAILY_CONTENT)]
    try:
        with transaction.atomic():
            existing = (
                PulseDailyEdition.objects.select_for_update()
                .select_related("question")
                .filter(date=target_date)
                .first()
            )
            if existing:
                return _publish_existing_edition(existing)
            system = _system_user()
            question = Question.objects.create(
                title=topic["title"],
                content_md=topic["content"],
                author=system,
                status=Question.Status.OPEN,
                auto_close_at=None,
            )
            edition = PulseDailyEdition.objects.create(
                date=target_date,
                question=question,
                poll_prompt=topic["poll"],
                source_type=PulseDailyEdition.SourceType.RANDOM,
                source_payload={"curated_index": target_date.toordinal() % len(CURATED_DAILY_CONTENT)},
                status=PulseDailyEdition.Status.PUBLISHED,
            )
            PulsePollOption.objects.bulk_create(
                [
                    PulsePollOption(edition=edition, position=index, text=text)
                    for index, text in enumerate(topic["options"], start=1)
                ]
            )
            return edition
    except IntegrityError:
        return _publish_existing_edition(
            PulseDailyEdition.objects.select_related("question").get(date=target_date)
        )


def get_or_create_user_day(*, user, edition=None, now=None, business_date=None):
    edition = edition or get_or_create_daily_edition(
        now=now, business_date=business_date
    )
    user_day, _ = PulseUserDay.objects.get_or_create(
        user=user,
        business_date=edition.date,
        defaults={"edition": edition},
    )
    return user_day


def get_wallet(user):
    balances = {asset: 0 for asset, _ in PulseLedgerEntry.Asset.choices}
    latest_by_asset = {}
    for entry in (
        PulseLedgerEntry.objects.filter(user=user)
        .order_by("asset", "-created_at", "-id")
    ):
        if entry.asset not in latest_by_asset:
            latest_by_asset[entry.asset] = entry.balance_after
    balances.update(latest_by_asset)
    return balances


def write_ledger_entry(
    *,
    user,
    asset,
    delta,
    event_key,
    source_type="",
    source_id=None,
    actor=None,
    note="",
    metadata=None,
):
    with transaction.atomic():
        User.objects.select_for_update().get(id=user.id)
        existing = PulseLedgerEntry.objects.filter(event_key=event_key).first()
        if existing:
            return existing, False
        latest = (
            PulseLedgerEntry.objects.filter(user=user, asset=asset)
            .order_by("-created_at", "-id")
            .first()
        )
        balance = latest.balance_after if latest else 0
        next_balance = balance + int(delta)
        if next_balance < 0:
            raise PulseConflict("道具余额不足。", code="insufficient_balance")
        entry = PulseLedgerEntry.objects.create(
            user=user,
            asset=asset,
            delta=delta,
            balance_after=next_balance,
            event_key=event_key,
            source_type=source_type,
            source_id=source_id,
            actor=actor,
            note=note[:300],
            metadata=metadata or {},
        )
        return entry, True


def submit_daily_answer(*, user, content_md, now=None):
    content = str(content_md or "").strip()
    if len(content) < 3:
        raise PulseValidationError("回答至少需要 3 个字符。")
    edition = get_or_create_daily_edition(now=now)
    with transaction.atomic():
        day = get_or_create_user_day(user=user, edition=edition)
        day = PulseUserDay.objects.select_for_update().get(id=day.id)
        answer = Answer.objects.create(
            question=edition.question,
            author=user,
            content_md=content,
            status=Answer.Status.VISIBLE,
        )
        completed_at = now or timezone.now()
        update_fields = []
        if day.community_completed_at is None:
            day.community_completed_at = completed_at
            update_fields.append("community_completed_at")
        if day.community_rewarded_at is None:
            _, created = write_ledger_entry(
                user=user,
                asset=PulseLedgerEntry.Asset.REROLL,
                delta=1,
                event_key=f"pulse-answer:{edition.date.isoformat()}:{user.id}",
                source_type="answer",
                source_id=answer.id,
                note="每日首次有效回答奖励",
            )
            if created:
                day.community_rewarded_at = completed_at
                update_fields.append("community_rewarded_at")
        if update_fields:
            day.save(update_fields=[*update_fields, "updated_at"])
        return answer


def poll_aggregate(*, edition, selected_option_id=None):
    options = list(
        edition.poll_options.annotate(vote_count=Count("votes")).order_by("position", "id")
    )
    total = sum(option.vote_count for option in options)
    percentages = []
    remaining = 100
    for index, option in enumerate(options):
        if total == 0:
            percentage = 0
        elif index == len(options) - 1:
            percentage = remaining
        else:
            percentage = round(option.vote_count * 100 / total)
            percentage = max(0, min(remaining, percentage))
            remaining -= percentage
        percentages.append(
            {
                "id": option.id,
                "position": option.position,
                "text": option.text,
                "votes": option.vote_count,
                "percentage": percentage,
            }
        )
    return {
        "total_votes": total,
        "selected_option_id": selected_option_id,
        "options": percentages,
    }


def submit_poll_vote(*, user, option_id, now=None):
    edition = get_or_create_daily_edition(now=now)
    option = edition.poll_options.filter(id=option_id).first()
    if not option:
        raise PulseValidationError("投票选项不属于今日话题。")
    try:
        with transaction.atomic():
            vote = PulsePollVote.objects.create(
                edition=edition, option=option, user=user
            )
            day = get_or_create_user_day(user=user, edition=edition)
            if day.poll_completed_at is None:
                day.poll_completed_at = now or timezone.now()
                day.save(update_fields=["poll_completed_at", "updated_at"])
    except IntegrityError as exc:
        raise PulseConflict("今天已经投过票，选择不能修改。", code="vote_locked") from exc
    return poll_aggregate(edition=edition, selected_option_id=vote.option_id)


def target_problem_rating(rating):
    base = 800 if rating is None else int(rating)
    rounded = ((base + 300 + 50) // 100) * 100
    return max(800, min(3500, rounded))


def rating_band_divisions(rating):
    value = 800 if rating is None else int(rating)
    if value < 1400:
        return {"div3", "div4"}
    if value < 1900:
        return {"div2"}
    return {"div1"}


def _active_binding(user):
    binding = CodeforcesBinding.objects.filter(active_user=user).first()
    if not binding:
        raise PulseConflict(
            "请先绑定 Codeforces 账号。", code="codeforces_binding_required"
        )
    return binding


def _refresh_binding_rating(binding, client, now):
    info = _call_codeforces(lambda: client.user_info(binding.handle))
    rating = info.get("rating")
    binding.rating = rating
    binding.max_rating = info.get("maxRating", binding.max_rating)
    binding.last_synced_at = now
    binding.save(update_fields=["rating", "max_rating", "last_synced_at", "updated_at"])
    return rating


def _all_user_submissions(client, handle):
    if hasattr(client, "user_status_all"):
        return _call_codeforces(lambda: client.user_status_all(handle))
    return _call_codeforces(lambda: client.user_status(handle, count=10000))


def _problem_key_from_submission(item):
    problem = item.get("problem") or {}
    contest_id = problem.get("contestId") or item.get("contestId")
    index = problem.get("index")
    if contest_id is None or not index:
        return None
    return f"{int(contest_id)}:{index}"


def _accepted_problem_keys(submissions):
    return {
        key
        for item in submissions
        if item.get("verdict") == "OK"
        for key in [_problem_key_from_submission(item)]
        if key
    }


def _choose(candidates, chooser=None):
    if not candidates:
        raise PulseConflict("当前没有符合条件的可抽取目标。", code="no_candidate")
    return (chooser or secrets.choice)(list(candidates))


def _select_problem_target(*, client, rating, submissions, excluded_keys, chooser=None):
    requested_rating = target_problem_rating(rating)
    accepted = _accepted_problem_keys(submissions)
    problemset = _call_codeforces(client.problemset) or {}
    eligible = []
    for item in problemset.get("problems") or []:
        contest_id = item.get("contestId")
        index = item.get("index")
        problem_rating = item.get("rating")
        if contest_id is None or not index or problem_rating is None:
            continue
        key = f"{int(contest_id)}:{index}"
        if key in accepted or key in excluded_keys:
            continue
        eligible.append((abs(int(problem_rating) - requested_rating), int(problem_rating), key, item))
    if not eligible:
        raise PulseConflict("没有找到尚未 AC 的可用题目。", code="no_problem")
    nearest_distance = min(row[0] for row in eligible)
    nearest = [row for row in eligible if row[0] == nearest_distance]
    nearest.sort(key=lambda row: (row[1], row[2]))
    _, actual_rating, key, item = _choose(nearest, chooser)
    return key, {
        "contest_id": int(item["contestId"]),
        "index": str(item["index"]),
        "name": str(item.get("name") or key),
        "rating": actual_rating,
        "requested_rating": requested_rating,
        "url": f"https://codeforces.com/problemset/problem/{int(item['contestId'])}/{item['index']}",
    }


def _contest_division(name):
    normalized = str(name or "").casefold().replace("division", "div")
    if "div. 4" in normalized or "div 4" in normalized:
        return "div4"
    if "div. 3" in normalized or "div 3" in normalized:
        return "div3"
    if "div. 2" in normalized or "div 2" in normalized:
        return "div2"
    if "div. 1" in normalized or "div 1" in normalized:
        return "div1"
    return ""


def _attempted_contest_ids(submissions):
    result = set()
    for item in submissions:
        contest_id = item.get("contestId") or (item.get("problem") or {}).get("contestId")
        if contest_id is not None:
            result.add(int(contest_id))
    return result


def _select_contest_target(*, client, rating, submissions, excluded_keys, chooser=None):
    allowed = rating_band_divisions(rating)
    attempted = _attempted_contest_ids(submissions)
    candidates = []
    for item in _call_codeforces(client.contests) or []:
        contest_id = item.get("id")
        name = str(item.get("name") or "")
        if contest_id is None or item.get("phase") != "FINISHED":
            continue
        if str(item.get("type") or "CF").upper() != "CF":
            continue
        lowered = name.casefold()
        if "team" in lowered or "kotlin" in lowered:
            continue
        division = _contest_division(name)
        key = f"contest:{int(contest_id)}"
        if division not in allowed or int(contest_id) in attempted or key in excluded_keys:
            continue
        candidates.append((int(contest_id), name, division, item))
    candidates.sort(key=lambda row: row[0], reverse=True)
    while candidates:
        selected = _choose(candidates, chooser)
        contest_id, name, division, _ = selected
        problems = _call_codeforces(lambda: client.contest_standings(contest_id)) or []
        valid_problems = [item for item in problems if item.get("index")]
        if valid_problems:
            count = len(valid_problems)
            return f"contest:{contest_id}", {
                "contest_id": contest_id,
                "name": name,
                "division": division,
                "problem_count": count,
                "required_solved": max(1, count - 2),
                "problems": [
                    {
                        "index": str(item["index"]),
                        "name": str(item.get("name") or item["index"]),
                    }
                    for item in valid_problems
                ],
                "url": f"https://codeforces.com/contest/{contest_id}",
            }
        candidates.remove(selected)
    raise PulseConflict("没有找到从未提交过的符合分段 VP。", code="no_contest")


def _build_target(*, mode, client, rating, submissions, excluded_keys, chooser=None):
    if mode == PulseChallengeAssignment.Mode.A:
        return _select_problem_target(
            client=client,
            rating=rating,
            submissions=submissions,
            excluded_keys=excluded_keys,
            chooser=chooser,
        )
    if mode == PulseChallengeAssignment.Mode.B:
        return _select_contest_target(
            client=client,
            rating=rating,
            submissions=submissions,
            excluded_keys=excluded_keys,
            chooser=chooser,
        )
    raise PulseValidationError("挑战模式只能是 A 或 B。")


def choose_challenge(*, user, mode, client, now=None, chooser=None):
    now = now or timezone.now()
    mode = str(mode or "").upper()
    if mode not in {PulseChallengeAssignment.Mode.A, PulseChallengeAssignment.Mode.B}:
        raise PulseValidationError("挑战模式只能是 A 或 B。")
    binding = _active_binding(user)
    rating = _refresh_binding_rating(binding, client, now)
    submissions = _all_user_submissions(client, binding.handle)
    edition = get_or_create_daily_edition(now=now)
    day = get_or_create_user_day(user=user, edition=edition)
    excluded = set(
        PulseChallengeAssignment.objects.filter(
            user=user,
            purpose=PulseChallengeAssignment.Purpose.DAILY,
            business_date=edition.date,
        ).values_list("target_key", flat=True)
    )
    target_key, target_data = _build_target(
        mode=mode,
        client=client,
        rating=rating,
        submissions=submissions,
        excluded_keys=excluded,
        chooser=chooser,
    )
    with transaction.atomic():
        locked_day = PulseUserDay.objects.select_for_update().get(id=day.id)
        if locked_day.challenge_mode and locked_day.challenge_mode != mode:
            raise PulseConflict("今天的挑战模式已经锁定。", code="mode_locked")
        if PulseChallengeAssignment.objects.filter(
            user_day=locked_day,
            purpose=PulseChallengeAssignment.Purpose.DAILY,
        ).exists():
            raise PulseConflict("今天已经抽取过挑战。", code="challenge_exists")
        if not locked_day.challenge_mode:
            locked_day.challenge_mode = mode
            locked_day.save(update_fields=["challenge_mode", "updated_at"])
        return PulseChallengeAssignment.objects.create(
            user=user,
            user_day=locked_day,
            business_date=edition.date,
            purpose=PulseChallengeAssignment.Purpose.DAILY,
            mode=mode,
            sequence=0,
            rating_snapshot=800 if rating is None else int(rating),
            target_key=target_key,
            target_data=target_data,
            assigned_at=now,
            deadline_at=challenge_deadline(edition.date),
        )


def reroll_challenge(*, user, client, now=None, chooser=None):
    now = now or timezone.now()
    edition = get_or_create_daily_edition(now=now)
    day = PulseUserDay.objects.filter(user=user, business_date=edition.date).first()
    if not day or not day.challenge_mode:
        raise PulseConflict("请先选择今日挑战模式。", code="challenge_missing")
    current = (
        PulseChallengeAssignment.objects.filter(
            user_day=day,
            purpose=PulseChallengeAssignment.Purpose.DAILY,
        )
        .order_by("-sequence")
        .first()
    )
    if not current:
        raise PulseConflict("今日挑战不存在。", code="challenge_missing")
    if current.status == PulseChallengeAssignment.Status.COMPLETED:
        raise PulseConflict("已完成的挑战不能换签。", code="challenge_completed")
    if current.sequence >= 2:
        raise PulseConflict("今天的两次换签机会已经用完。", code="reroll_limit")
    binding = _active_binding(user)
    rating = _refresh_binding_rating(binding, client, now)
    submissions = _all_user_submissions(client, binding.handle)
    excluded = set(
        PulseChallengeAssignment.objects.filter(
            user_day=day
        ).values_list("target_key", flat=True)
    )
    target_key, target_data = _build_target(
        mode=current.mode,
        client=client,
        rating=rating,
        submissions=submissions,
        excluded_keys=excluded,
        chooser=chooser,
    )
    with transaction.atomic():
        locked = PulseChallengeAssignment.objects.select_for_update().get(id=current.id)
        if locked.status != PulseChallengeAssignment.Status.ASSIGNED:
            raise PulseConflict("当前挑战状态已经变化，请刷新。", code="stale_challenge")
        write_ledger_entry(
            user=user,
            asset=PulseLedgerEntry.Asset.REROLL,
            delta=-1,
            event_key=f"pulse-reroll:{locked.id}",
            source_type="challenge_reroll",
            source_id=locked.id,
            note="每日挑战换签",
        )
        locked.status = PulseChallengeAssignment.Status.REPLACED
        locked.save(update_fields=["status", "updated_at"])
        return PulseChallengeAssignment.objects.create(
            user=user,
            user_day=locked.user_day,
            business_date=locked.business_date,
            purpose=locked.purpose,
            mode=locked.mode,
            sequence=locked.sequence + 1,
            rating_snapshot=800 if rating is None else int(rating),
            target_key=target_key,
            target_data=target_data,
            assigned_at=now,
            deadline_at=locked.deadline_at,
        )


def _submission_time(item):
    return datetime.fromtimestamp(
        int(item.get("creationTimeSeconds") or 0), tz=datetime_timezone.utc
    )


def _eligible_problem_evidence(assignment, submissions, handle_ci):
    contest_id = int(assignment.target_data["contest_id"])
    index = str(assignment.target_data["index"])
    candidates = [
        item
        for item in submissions
        if item.get("verdict") == "OK"
        and _problem_key_from_submission(item) == f"{contest_id}:{index}"
        and _submission_author_matches(item, handle_ci)
        and assignment.assigned_at <= _submission_time(item) <= assignment.deadline_at
    ]
    if not candidates:
        raise PulseConflict("尚未检测到这道题在分配后的 AC。", code="challenge_not_complete")
    return [max(candidates, key=lambda item: int(item.get("id") or 0))]


def _eligible_vp_evidence(assignment, submissions, handle_ci):
    contest_id = int(assignment.target_data["contest_id"])
    valid_indices = {item["index"] for item in assignment.target_data.get("problems", [])}
    solved = {}
    for item in submissions:
        author = item.get("author") or {}
        key = _problem_key_from_submission(item)
        if not key or not key.startswith(f"{contest_id}:"):
            continue
        index = key.split(":", 1)[1]
        if (
            index not in valid_indices
            or item.get("verdict") != "OK"
            or author.get("participantType") != "VIRTUAL"
            or not _submission_author_matches(item, handle_ci)
            or not (assignment.assigned_at <= _submission_time(item) <= assignment.deadline_at)
        ):
            continue
        current = solved.get(index)
        if current is None or int(item.get("id") or 0) > int(current.get("id") or 0):
            solved[index] = item
    required = int(assignment.target_data.get("required_solved") or 1)
    if len(solved) < required:
        raise PulseConflict(
            f"当前 VP 已完成 {len(solved)}/{required} 道。",
            code="challenge_not_complete",
        )
    return list(solved.values())


def check_challenge_completion(*, user, assignment_id, client, now=None):
    now = now or timezone.now()
    assignment = PulseChallengeAssignment.objects.filter(
        id=assignment_id, user=user
    ).first()
    if not assignment:
        raise PulseValidationError("挑战不存在。")
    if assignment.status == PulseChallengeAssignment.Status.COMPLETED:
        return assignment
    if assignment.status != PulseChallengeAssignment.Status.ASSIGNED:
        raise PulseConflict("这个挑战已经失效。", code="challenge_inactive")
    if now > assignment.deadline_at:
        PulseChallengeAssignment.objects.filter(id=assignment.id).update(
            status=PulseChallengeAssignment.Status.EXPIRED
        )
        raise PulseConflict("挑战已超过次日 04:00 截止时间。", code="challenge_expired")
    binding = _active_binding(user)
    submissions = _all_user_submissions(client, binding.handle)
    if assignment.mode == PulseChallengeAssignment.Mode.A:
        evidence_rows = _eligible_problem_evidence(
            assignment, submissions, binding.handle_ci
        )
        point_delta = 1
    else:
        evidence_rows = _eligible_vp_evidence(
            assignment, submissions, binding.handle_ci
        )
        point_delta = 3

    try:
        with transaction.atomic():
            locked = PulseChallengeAssignment.objects.select_for_update().get(
                id=assignment.id, user=user
            )
            if locked.status == PulseChallengeAssignment.Status.COMPLETED:
                return locked
            if locked.status != PulseChallengeAssignment.Status.ASSIGNED:
                raise PulseConflict("挑战状态已经变化，请刷新。", code="stale_challenge")
            evidence_ids = []
            for row in evidence_rows:
                evidence = CodeforcesEvidence.objects.create(
                    submission_id=int(row["id"]),
                    user=user,
                    purpose=(
                        CodeforcesEvidence.Purpose.MAKEUP
                        if locked.purpose == PulseChallengeAssignment.Purpose.MAKEUP
                        else CodeforcesEvidence.Purpose.CHALLENGE
                    ),
                    source_type="pulse_challenge",
                    source_id=locked.id,
                    payload={
                        "target_key": locked.target_key,
                        "problem": row.get("problem") or {},
                        "creation_time_seconds": row.get("creationTimeSeconds"),
                    },
                )
                evidence_ids.append(evidence.submission_id)
            write_ledger_entry(
                user=user,
                asset=PulseLedgerEntry.Asset.POINT,
                delta=point_delta,
                event_key=f"pulse-challenge-complete:{locked.id}",
                source_type="challenge",
                source_id=locked.id,
                note=f"模式 {locked.mode} 完成奖励",
            )
            locked.status = PulseChallengeAssignment.Status.COMPLETED
            locked.completed_at = now
            locked.completion_data = {
                "evidence_submission_ids": evidence_ids,
                "solved_count": len(evidence_rows),
                "points": point_delta,
            }
            locked.save(
                update_fields=["status", "completed_at", "completion_data", "updated_at"]
            )
            if locked.user_day_id:
                day = PulseUserDay.objects.select_for_update().get(id=locked.user_day_id)
                day.challenge_completed_at = now
                day.signed_at = day.signed_at or now
                day.save(
                    update_fields=["challenge_completed_at", "signed_at", "updated_at"]
                )
            if locked.purpose == PulseChallengeAssignment.Purpose.MAKEUP:
                PulseMakeup.objects.filter(assignment=locked).update(
                    status=PulseMakeup.Status.COMPLETED,
                    completed_at=now,
                    updated_at=now,
                )
            return locked
    except IntegrityError as exc:
        raise PulseConflict(
            "检测到的提交已经用于其他结算。", code="evidence_replayed"
        ) from exc


def _validate_rewards(rewards, *, allow_negative=False):
    if not isinstance(rewards, dict) or not rewards:
        raise PulseValidationError("奖励内容不能为空。")
    allowed = {asset for asset, _ in PulseLedgerEntry.Asset.choices}
    normalized = {}
    for asset, raw_amount in rewards.items():
        if asset not in allowed:
            raise PulseValidationError(f"未知资产类型：{asset}")
        try:
            amount = int(raw_amount)
        except (TypeError, ValueError) as exc:
            raise PulseValidationError("奖励数量必须是整数。") from exc
        if amount == 0 or (amount < 0 and not allow_negative):
            raise PulseValidationError("奖励数量必须大于 0。")
        normalized[asset] = amount
    return normalized


def admin_grant_assets(*, actor, user, rewards, event_key, note=""):
    if not actor or not actor.is_manager:
        raise PulsePermissionDenied("只有管理员可以发放道具。")
    rewards = _validate_rewards(rewards)
    key = str(event_key or "").strip()
    if not key:
        raise PulseValidationError("发放操作必须包含幂等键。")
    key_digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    entries = []
    created_any = False
    with transaction.atomic():
        for asset, amount in sorted(rewards.items()):
            entry, created = write_ledger_entry(
                user=user,
                asset=asset,
                delta=amount,
                event_key=f"pulse-admin-grant:{user.id}:{key_digest}:{asset}",
                source_type="admin_grant",
                actor=actor,
                note=note or "管理员发放",
            )
            entries.append(entry)
            created_any = created_any or created
        if created_any:
            SecurityAuditLog.objects.create(
                event_type="pulse_asset_granted",
                user=user,
                username=user.username,
                detail="管理员发放午夜脉冲资产",
                metadata={
                    "action": "pulse_admin_grant",
                    "actor_id": actor.id,
                    "rewards": rewards,
                    "event_key": key,
                    "note": note,
                },
            )
            UserNotification.objects.create(
                user=user,
                actor=actor,
                title="收到午夜脉冲奖励",
                content=(note or "管理员向你发放了午夜脉冲道具。")[:500],
                link="/pulse",
                target_type="pulse_grant",
            )
    return entries


def claim_active_campaigns(*, user, now=None):
    now = now or timezone.now()
    claimed = []
    campaigns = PulseRewardCampaign.objects.filter(
        is_enabled=True,
        starts_at__lte=now,
        ends_at__gte=now,
    ).order_by("starts_at", "id")
    for campaign in campaigns:
        try:
            rewards = _validate_rewards(campaign.reward_payload)
        except PulseValidationError:
            continue
        campaign_created = False
        for asset, amount in sorted(rewards.items()):
            _, created = write_ledger_entry(
                user=user,
                asset=asset,
                delta=amount,
                event_key=f"pulse-campaign:{campaign.id}:{user.id}:{asset}",
                source_type="campaign",
                source_id=campaign.id,
                actor=campaign.created_by,
                note=campaign.name,
            )
            campaign_created = campaign_created or created
        if campaign_created:
            claimed.append(campaign.id)
            UserNotification.objects.create(
                user=user,
                actor=campaign.created_by,
                title="午夜脉冲活动奖励已到账",
                content=f"你已领取“{campaign.name}”活动奖励。",
                link="/pulse",
                target_type="pulse_campaign",
                target_id=campaign.id,
            )
    return claimed


def create_makeup(*, user, target_date, kind, client, now=None, chooser=None):
    now = now or timezone.now()
    current_date = shanghai_business_date(now)
    if isinstance(target_date, str):
        try:
            target_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError as exc:
            raise PulseValidationError("补签日期格式必须是 YYYY-MM-DD。") from exc
    if target_date >= current_date:
        raise PulseValidationError("只能补签今天之前的日期。")
    if kind not in {PulseMakeup.Kind.NORMAL, PulseMakeup.Kind.SUPER}:
        raise PulseValidationError("补签类型只能是 normal 或 super。")
    if PulseMakeup.objects.filter(user=user, target_date=target_date).exists():
        raise PulseConflict("这个日期已经申请过补签。", code="makeup_exists")

    edition = get_or_create_daily_edition(business_date=target_date)
    day = get_or_create_user_day(user=user, edition=edition)
    if day.signed_at:
        raise PulseConflict("这个日期已经签到。", code="already_signed")

    asset = (
        PulseLedgerEntry.Asset.MAKEUP
        if kind == PulseMakeup.Kind.NORMAL
        else PulseLedgerEntry.Asset.SUPER_MAKEUP
    )
    if get_wallet(user)[asset] < 1:
        raise PulseConflict("补签卷余额不足。", code="insufficient_balance")

    if kind == PulseMakeup.Kind.NORMAL:
        binding = _active_binding(user)
        rating = _refresh_binding_rating(binding, client, now)
        submissions = _all_user_submissions(client, binding.handle)
        excluded = set(
            PulseChallengeAssignment.objects.filter(user=user).values_list(
                "target_key", flat=True
            )
        )
        target_key, target_data = _select_problem_target(
            client=client,
            rating=rating,
            submissions=submissions,
            excluded_keys=excluded,
            chooser=chooser,
        )

    try:
        with transaction.atomic():
            locked_day = PulseUserDay.objects.select_for_update().get(id=day.id)
            makeup = PulseMakeup.objects.create(
                user=user,
                target_date=target_date,
                kind=kind,
                status=PulseMakeup.Status.PENDING,
            )
            write_ledger_entry(
                user=user,
                asset=asset,
                delta=-1,
                event_key=f"pulse-makeup-consume:{makeup.id}:{asset}",
                source_type="makeup",
                source_id=makeup.id,
                note="使用补签卷",
            )
            if kind == PulseMakeup.Kind.SUPER:
                write_ledger_entry(
                    user=user,
                    asset=PulseLedgerEntry.Asset.POINT,
                    delta=1,
                    event_key=f"pulse-super-makeup-point:{makeup.id}",
                    source_type="makeup",
                    source_id=makeup.id,
                    note="超级补签积分",
                )
                locked_day.signed_at = now
                locked_day.save(update_fields=["signed_at", "updated_at"])
                makeup.status = PulseMakeup.Status.COMPLETED
                makeup.completed_at = now
                makeup.save(update_fields=["status", "completed_at", "updated_at"])
                return makeup

            assignment = PulseChallengeAssignment.objects.create(
                user=user,
                user_day=locked_day,
                business_date=target_date,
                purpose=PulseChallengeAssignment.Purpose.MAKEUP,
                mode=PulseChallengeAssignment.Mode.A,
                sequence=0,
                rating_snapshot=800 if rating is None else int(rating),
                target_key=target_key,
                target_data=target_data,
                assigned_at=now,
                deadline_at=now + timedelta(days=7),
            )
            makeup.assignment = assignment
            makeup.save(update_fields=["assignment", "updated_at"])
            return makeup
    except IntegrityError as exc:
        raise PulseConflict("这个日期已经申请过补签。", code="makeup_exists") from exc


def _normalize_redemption_code(raw_code):
    code = str(raw_code or "").strip().upper()
    if len(code) < 6 or len(code) > 64:
        raise PulseValidationError("兑换码长度必须在 6 至 64 位之间。")
    return code


def _code_lookup_digest(code):
    return salted_hmac(
        "algowiki.pulse.redemption-code", code, algorithm="sha256"
    ).hexdigest()


def create_redemption_code(
    *,
    actor,
    raw_code,
    reward_payload,
    starts_at=None,
    ends_at=None,
    max_uses=1,
    per_user_limit=1,
):
    if not actor or not actor.is_manager:
        raise PulsePermissionDenied("只有管理员可以创建兑换码。")
    code = _normalize_redemption_code(raw_code)
    rewards = _validate_rewards(reward_payload)
    max_uses = int(max_uses)
    per_user_limit = int(per_user_limit)
    if max_uses < 1 or per_user_limit < 1 or per_user_limit > max_uses:
        raise PulseValidationError("兑换次数限制无效。")
    if starts_at and ends_at and starts_at >= ends_at:
        raise PulseValidationError("兑换码结束时间必须晚于开始时间。")
    try:
        return PulseRedemptionCode.objects.create(
            code_lookup_digest=_code_lookup_digest(code),
            code_hash=make_password(code),
            code_hint=f"{code[:4]}…{code[-2:]}",
            reward_payload=rewards,
            starts_at=starts_at,
            ends_at=ends_at,
            max_uses=max_uses,
            per_user_limit=per_user_limit,
            created_by=actor,
        )
    except IntegrityError as exc:
        raise PulseConflict("这个兑换码已经存在。", code="code_exists") from exc


def redeem_code(*, user, raw_code, idempotency_key, now=None):
    now = now or timezone.now()
    request_key = str(idempotency_key or "").strip()
    if not request_key:
        raise PulseValidationError("兑换请求缺少幂等键。")
    existing = PulseRedemption.objects.filter(idempotency_key=request_key).first()
    if existing:
        if existing.user_id != user.id:
            raise PulseConflict("兑换请求标识已被使用。")
        return existing
    normalized = _normalize_redemption_code(raw_code)
    code = PulseRedemptionCode.objects.filter(
        code_lookup_digest=_code_lookup_digest(normalized)
    ).first()
    if not code or not check_password(normalized, code.code_hash):
        raise PulseValidationError("兑换码无效。")

    with transaction.atomic():
        locked = PulseRedemptionCode.objects.select_for_update().get(id=code.id)
        if not locked.is_enabled:
            raise PulseConflict("兑换码已停用。", code="code_disabled")
        if locked.starts_at and now < locked.starts_at:
            raise PulseConflict("兑换码尚未生效。", code="code_not_started")
        if locked.ends_at and now > locked.ends_at:
            raise PulseConflict("兑换码已经过期。", code="code_expired")
        if locked.used_count >= locked.max_uses:
            raise PulseConflict("兑换码总次数已用完。", code="code_exhausted")
        used_by_user = PulseRedemption.objects.filter(code=locked, user=user).count()
        if used_by_user >= locked.per_user_limit:
            raise PulseConflict("你已经达到该兑换码的使用上限。", code="user_code_limit")
        redemption = PulseRedemption.objects.create(
            code=locked,
            user=user,
            idempotency_key=request_key,
            reward_payload=locked.reward_payload,
        )
        for asset, amount in sorted(locked.reward_payload.items()):
            write_ledger_entry(
                user=user,
                asset=asset,
                delta=int(amount),
                event_key=f"pulse-redemption:{redemption.id}:{asset}",
                source_type="redemption",
                source_id=redemption.id,
                note=f"兑换码 {locked.code_hint}",
            )
        locked.used_count += 1
        locked.save(update_fields=["used_count", "updated_at"])
        return redemption


def _streak_from_dates(signed_dates, *, as_of_date):
    signed_dates = sorted(set(signed_dates))
    signed_set = set(signed_dates)
    cursor = as_of_date if as_of_date in signed_set else as_of_date - timedelta(days=1)
    current = 0
    while cursor in signed_set:
        current += 1
        cursor -= timedelta(days=1)
    longest = 0
    run = 0
    previous = None
    for signed_date in signed_dates:
        if previous and signed_date == previous + timedelta(days=1):
            run += 1
        else:
            run = 1
        longest = max(longest, run)
        previous = signed_date
    return {
        "current": current,
        "longest": longest,
        "signed_dates": [item.isoformat() for item in signed_dates],
    }


def streak_summary(user, *, as_of_date=None):
    as_of_date = as_of_date or shanghai_business_date()
    signed_dates = PulseUserDay.objects.filter(
        user=user, signed_at__isnull=False
    ).values_list("business_date", flat=True)
    return _streak_from_dates(signed_dates, as_of_date=as_of_date)


def get_rankings(*, as_of_date=None, school_name=None, rating_min=None, rating_max=None):
    as_of_date = as_of_date or shanghai_business_date()
    latest_points = PulseLedgerEntry.objects.filter(
        user_id=OuterRef("pk"), asset=PulseLedgerEntry.Asset.POINT
    ).order_by("-created_at", "-id")
    active_rating = CodeforcesBinding.objects.filter(
        active_user_id=OuterRef("pk")
    ).values("rating")[:1]
    users = User.objects.filter(is_active=True, is_banned=False)
    if school_name:
        users = users.filter(school_name=school_name)
    users = users.annotate(
        pulse_rating=Subquery(active_rating),
        pulse_points=Subquery(latest_points.values("balance_after")[:1]),
        pulse_completed_at=Subquery(latest_points.values("created_at")[:1]),
    )
    if rating_min is not None:
        users = users.filter(pulse_rating__gte=rating_min)
    if rating_max is not None:
        users = users.filter(pulse_rating__lte=rating_max)
    user_rows = list(
        users.order_by("id").values(
            "id",
            "username",
            "school_name",
            "pulse_rating",
            "pulse_points",
            "pulse_completed_at",
        )
    )
    signed_by_user = {item["id"]: [] for item in user_rows}
    for user_id, business_date in PulseUserDay.objects.filter(
        user_id__in=signed_by_user, signed_at__isnull=False
    ).values_list("user_id", "business_date"):
        signed_by_user[user_id].append(business_date)

    rows = []
    for item in user_rows:
        points = int(item["pulse_points"] or 0)
        streak = _streak_from_dates(
            signed_by_user[item["id"]], as_of_date=as_of_date
        )
        rows.append(
            {
                "user_id": item["id"],
                "username": item["username"],
                "school_name": item["school_name"],
                "rating": item["pulse_rating"],
                "points": points,
                "current_streak": streak["current"],
                "longest_streak": streak["longest"],
                "completed_at": item["pulse_completed_at"],
            }
        )
    far_future = datetime.max.replace(tzinfo=datetime_timezone.utc)
    rows.sort(
        key=lambda row: (
            -row["points"],
            row["completed_at"] or far_future,
            row["user_id"],
        )
    )
    last_signature = None
    rank = 0
    for position, row in enumerate(rows, start=1):
        signature = (row["points"], row["completed_at"])
        if signature != last_signature:
            rank = position
            last_signature = signature
        row["rank"] = rank
        row.pop("completed_at", None)
    return rows
