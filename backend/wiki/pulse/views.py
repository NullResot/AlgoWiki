from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import (
    Answer,
    CodeforcesBinding,
    CodeforcesVerification,
    PulseChallengeAssignment,
    PulseDailyEdition,
    PulseLedgerEntry,
    PulseMakeup,
    PulsePollOption,
    PulsePollVote,
    PulseRedemptionCode,
    PulseRewardCampaign,
    PulseUserDay,
    Question,
    SecurityAuditLog,
    User,
)
from ..permissions import AdminOrSuperAdmin, AuthenticatedAndNotBanned
from .codeforces import CodeforcesClient
from .serializers import (
    AdminCodeCreateSerializer,
    AdminCodeUpdateSerializer,
    AdminCampaignCreateSerializer,
    AdminCampaignUpdateSerializer,
    AdminEditionCreateSerializer,
    AdminEditionUpdateSerializer,
    AdminGrantSerializer,
    AdminUnbindSerializer,
    AnswerCreateSerializer,
    BindingStartSerializer,
    BindingVerifySerializer,
    ChallengeCheckSerializer,
    ChallengeChooseSerializer,
    MakeupCreateSerializer,
    PollVoteSerializer,
    RedeemSerializer,
    SelfUnbindSerializer,
)
from .services import (
    PulseConflict,
    PulseExternalUnavailable,
    PulsePermissionDenied,
    PulseValidationError,
    admin_grant_assets,
    admin_unbind_codeforces,
    check_challenge_completion,
    claim_active_campaigns,
    choose_challenge,
    create_makeup,
    create_redemption_code,
    get_or_create_daily_edition,
    get_or_create_user_day,
    get_rankings,
    get_wallet,
    poll_aggregate,
    redeem_code,
    reroll_challenge,
    self_unbind_codeforces,
    shanghai_business_date,
    start_binding,
    streak_summary,
    submit_daily_answer,
    submit_poll_vote,
    verify_binding,
)


def get_codeforces_client():
    return CodeforcesClient()


class PulseAPIView(APIView):
    def handle_exception(self, exc):
        if isinstance(exc, PulseValidationError):
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if isinstance(exc, PulsePermissionDenied):
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=status.HTTP_403_FORBIDDEN,
            )
        if isinstance(exc, PulseConflict):
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=status.HTTP_409_CONFLICT,
            )
        if isinstance(exc, PulseExternalUnavailable):
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return super().handle_exception(exc)


def binding_payload(binding):
    if not binding:
        return None
    return {
        "id": binding.id,
        "handle": binding.handle,
        "rating": binding.rating,
        "max_rating": binding.max_rating,
        "verified_at": binding.verified_at,
        "last_synced_at": binding.last_synced_at,
        "is_active": binding.is_active,
        "unbound_at": binding.unbound_at,
        "rebind_not_before": binding.rebind_not_before,
        "unbind_reason": binding.unbind_reason,
    }


def verification_payload(verification):
    return {
        "id": verification.id,
        "handle": verification.handle,
        "baseline_submission_id": verification.baseline_submission_id,
        "issued_at": verification.issued_at,
        "expires_at": verification.expires_at,
        "status": verification.status,
        "attempt_count": verification.attempt_count,
    }


def assignment_payload(assignment):
    if not assignment:
        return None
    return {
        "id": assignment.id,
        "business_date": assignment.business_date,
        "purpose": assignment.purpose,
        "mode": assignment.mode,
        "sequence": assignment.sequence,
        "rerolls_used": assignment.sequence,
        "rerolls_remaining": max(0, 2 - assignment.sequence),
        "rating_snapshot": assignment.rating_snapshot,
        "target_key": assignment.target_key,
        "target": assignment.target_data,
        "assigned_at": assignment.assigned_at,
        "deadline_at": assignment.deadline_at,
        "status": assignment.status,
        "completed_at": assignment.completed_at,
        "completion": assignment.completion_data,
        "points_awarded": int(assignment.completion_data.get("points") or 0),
    }


def answer_payload(answer):
    return {
        "id": answer.id,
        "content_md": answer.content_md,
        "status": answer.status,
        "created_at": answer.created_at,
        "author": {
            "id": answer.author_id,
            "username": answer.author.username,
            "school_name": answer.author.school_name,
            "avatar_url": answer.author.avatar_url,
        },
    }


def edition_payload(edition, *, user=None, include_answers=True):
    selected = None
    if user and user.is_authenticated:
        selected = (
            PulsePollVote.objects.filter(edition=edition, user=user)
            .values_list("option_id", flat=True)
            .first()
        )
    poll = poll_aggregate(edition=edition, selected_option_id=selected)
    payload = {
        "id": edition.id,
        "date": edition.date,
        "source_type": edition.source_type,
        "status": edition.status,
        "question": {
            "id": edition.question_id,
            "title": edition.question.title,
            "content_md": edition.question.content_md,
            "answer_count": edition.question.answers.filter(
                status=Answer.Status.VISIBLE
            ).count(),
        },
        "poll": {"prompt": edition.poll_prompt, **poll},
    }
    if include_answers:
        answers = (
            edition.question.answers.filter(status=Answer.Status.VISIBLE)
            .select_related("author")
            .order_by("-created_at")[:50]
        )
        payload["question"]["answers"] = [answer_payload(item) for item in answers]
    return payload


def day_payload(day):
    if not day:
        return {
            "community_completed": False,
            "poll_completed": False,
            "challenge_completed": False,
            "signed": False,
            "challenge_mode": "",
            "progress": 0,
        }
    flags = (
        bool(day.community_completed_at),
        bool(day.poll_completed_at),
        bool(day.challenge_completed_at),
    )
    return {
        "community_completed": flags[0],
        "poll_completed": flags[1],
        "challenge_completed": flags[2],
        "signed": bool(day.signed_at),
        "challenge_mode": day.challenge_mode,
        "progress": sum(flags),
    }


def _current_assignment(day):
    if not day:
        return None
    return (
        day.challenge_assignments.filter(
            purpose=PulseChallengeAssignment.Purpose.DAILY
        )
        .order_by("-sequence")
        .first()
    )


class PulseTodayView(PulseAPIView):
    permission_classes = [AllowAny]

    def get(self, request):
        now = timezone.now()
        edition = get_or_create_daily_edition(now=now)
        me = None
        previous_assignment = None
        if request.user and request.user.is_authenticated:
            day = get_or_create_user_day(user=request.user, edition=edition)
            claimed_campaign_ids = claim_active_campaigns(user=request.user, now=now)
            binding = CodeforcesBinding.objects.filter(active_user=request.user).first()
            if not binding:
                binding = (
                    CodeforcesBinding.objects.filter(owner=request.user)
                    .order_by("-verified_at", "-id")
                    .first()
                )
            pending = (
                CodeforcesVerification.objects.filter(
                    user=request.user,
                    status=CodeforcesVerification.Status.PENDING,
                    expires_at__gt=now,
                )
                .order_by("-created_at")
                .first()
            )
            previous_assignment = (
                PulseChallengeAssignment.objects.filter(
                    user=request.user,
                    purpose=PulseChallengeAssignment.Purpose.DAILY,
                    business_date=edition.date - timedelta(days=1),
                    status=PulseChallengeAssignment.Status.ASSIGNED,
                    deadline_at__gt=now,
                )
                .order_by("-sequence")
                .first()
            )
            pending_makeup = (
                PulseMakeup.objects.filter(
                    user=request.user,
                    status=PulseMakeup.Status.PENDING,
                )
                .select_related("assignment")
                .order_by("-created_at")
                .first()
            )
            me = {
                **day_payload(day),
                "wallet": get_wallet(request.user),
                "claimed_campaign_ids": claimed_campaign_ids,
                "binding": binding_payload(binding),
                "pending_verification": verification_payload(pending) if pending else None,
                "challenge": assignment_payload(_current_assignment(day)),
                "pending_makeup": (
                    {
                        "id": pending_makeup.id,
                        "target_date": pending_makeup.target_date,
                        "kind": pending_makeup.kind,
                        "status": pending_makeup.status,
                        "assignment": assignment_payload(pending_makeup.assignment),
                    }
                    if pending_makeup
                    else None
                ),
                "streak": streak_summary(request.user, as_of_date=edition.date),
            }
        return Response(
            {
                "edition": edition_payload(edition, user=request.user),
                "me": me,
                "previous_active_challenge": assignment_payload(previous_assignment),
                "server_time": now,
            }
        )


class PulseAnswerView(PulseAPIView):
    permission_classes = [AuthenticatedAndNotBanned]

    def get(self, request):
        edition = get_or_create_daily_edition()
        limit = max(1, min(int(request.query_params.get("limit", 30)), 100))
        offset = max(0, int(request.query_params.get("offset", 0)))
        rows = (
            edition.question.answers.filter(status=Answer.Status.VISIBLE)
            .select_related("author")
            .order_by("-created_at")[offset : offset + limit]
        )
        return Response({"results": [answer_payload(item) for item in rows]})

    def post(self, request):
        serializer = AnswerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        answer = submit_daily_answer(user=request.user, **serializer.validated_data)
        return Response(
            {**answer_payload(answer), "wallet": get_wallet(request.user)},
            status=status.HTTP_201_CREATED,
        )


class PulseVoteView(PulseAPIView):
    permission_classes = [AuthenticatedAndNotBanned]

    def post(self, request):
        serializer = PollVoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = submit_poll_vote(user=request.user, **serializer.validated_data)
        return Response(result, status=status.HTTP_201_CREATED)


class PulseBindingStartView(PulseAPIView):
    permission_classes = [AuthenticatedAndNotBanned]

    def post(self, request):
        serializer = BindingStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verification = start_binding(
            user=request.user,
            client=get_codeforces_client(),
            **serializer.validated_data,
        )
        return Response(verification_payload(verification), status=status.HTTP_201_CREATED)


class PulseBindingVerifyView(PulseAPIView):
    permission_classes = [AuthenticatedAndNotBanned]

    def post(self, request):
        serializer = BindingVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        binding = verify_binding(
            user=request.user,
            client=get_codeforces_client(),
            **serializer.validated_data,
        )
        return Response(binding_payload(binding))


class PulseSelfUnbindView(PulseAPIView):
    permission_classes = [AuthenticatedAndNotBanned]

    def post(self, request):
        serializer = SelfUnbindSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        binding = self_unbind_codeforces(
            user=request.user, **serializer.validated_data
        )
        return Response(binding_payload(binding))


class PulseChallengeChooseView(PulseAPIView):
    permission_classes = [AuthenticatedAndNotBanned]

    def post(self, request):
        serializer = ChallengeChooseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = choose_challenge(
            user=request.user,
            client=get_codeforces_client(),
            **serializer.validated_data,
        )
        return Response(assignment_payload(assignment), status=status.HTTP_201_CREATED)


class PulseChallengeRerollView(PulseAPIView):
    permission_classes = [AuthenticatedAndNotBanned]

    def post(self, request):
        assignment = reroll_challenge(
            user=request.user, client=get_codeforces_client()
        )
        return Response(assignment_payload(assignment), status=status.HTTP_201_CREATED)


class PulseChallengeCheckView(PulseAPIView):
    permission_classes = [AuthenticatedAndNotBanned]

    def post(self, request):
        serializer = ChallengeCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = check_challenge_completion(
            user=request.user,
            client=get_codeforces_client(),
            **serializer.validated_data,
        )
        return Response(assignment_payload(assignment))


class PulseMakeupView(PulseAPIView):
    permission_classes = [AuthenticatedAndNotBanned]

    def post(self, request):
        serializer = MakeupCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        makeup = create_makeup(
            user=request.user,
            client=get_codeforces_client(),
            **serializer.validated_data,
        )
        return Response(
            {
                "id": makeup.id,
                "target_date": makeup.target_date,
                "kind": makeup.kind,
                "status": makeup.status,
                "assignment": assignment_payload(makeup.assignment),
                "wallet": get_wallet(request.user),
            },
            status=status.HTTP_201_CREATED,
        )


class PulseRedeemView(PulseAPIView):
    permission_classes = [AuthenticatedAndNotBanned]

    def post(self, request):
        serializer = RedeemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        redemption = redeem_code(
            user=request.user,
            raw_code=serializer.validated_data["code"],
            idempotency_key=serializer.validated_data["idempotency_key"],
        )
        return Response(
            {
                "id": redemption.id,
                "rewards": redemption.reward_payload,
                "wallet": get_wallet(request.user),
            },
            status=status.HTTP_201_CREATED,
        )


class PulseAtlasView(PulseAPIView):
    permission_classes = [AuthenticatedAndNotBanned]

    def get(self, request):
        summary = streak_summary(request.user)
        summary["makeups"] = list(
            PulseMakeup.objects.filter(
                user=request.user, status=PulseMakeup.Status.COMPLETED
            )
            .order_by("target_date")
            .values("target_date", "kind", "completed_at")
        )
        return Response(summary)


class PulseRankingsView(PulseAPIView):
    permission_classes = [AllowAny]

    def get(self, request):
        rows = get_rankings(
            school_name=request.query_params.get("school_name") or None,
            rating_min=request.query_params.get("rating_min") or None,
            rating_max=request.query_params.get("rating_max") or None,
        )
        return Response({"results": rows[:100]})


class PulseAdminBindingsView(PulseAPIView):
    permission_classes = [AdminOrSuperAdmin]

    def get(self, request):
        query = str(request.query_params.get("q") or "").strip()
        rows = CodeforcesBinding.objects.select_related("owner", "active_user", "unbound_by")
        if query:
            rows = rows.filter(
                Q(handle__icontains=query)
                | Q(owner__username__icontains=query)
                | Q(owner__email__icontains=query)
            )
        return Response({"results": [binding_payload(item) | {"owner": {"id": item.owner_id, "username": item.owner.username}} for item in rows[:100]]})


class PulseAdminUnbindView(PulseAPIView):
    permission_classes = [AdminOrSuperAdmin]

    def post(self, request, binding_id):
        serializer = AdminUnbindSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        binding = get_object_or_404(CodeforcesBinding, id=binding_id)
        result = admin_unbind_codeforces(
            actor=request.user, binding=binding, **serializer.validated_data
        )
        return Response(binding_payload(result))


class PulseAdminGrantView(PulseAPIView):
    permission_classes = [AdminOrSuperAdmin]

    def post(self, request):
        serializer = AdminGrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = get_object_or_404(User, id=serializer.validated_data["user_id"])
        admin_grant_assets(
            actor=request.user,
            user=target,
            rewards=serializer.validated_data["rewards"],
            event_key=serializer.validated_data["idempotency_key"],
            note=serializer.validated_data.get("note", ""),
        )
        return Response(
            {"user_id": target.id, "wallet": get_wallet(target)},
            status=status.HTTP_201_CREATED,
        )


def campaign_payload(campaign):
    return {
        "id": campaign.id,
        "key": campaign.key,
        "name": campaign.name,
        "reward_payload": campaign.reward_payload,
        "starts_at": campaign.starts_at,
        "ends_at": campaign.ends_at,
        "is_enabled": campaign.is_enabled,
        "created_at": campaign.created_at,
    }


class PulseAdminCampaignsView(PulseAPIView):
    permission_classes = [AdminOrSuperAdmin]

    def get(self, request):
        return Response(
            {"results": [campaign_payload(item) for item in PulseRewardCampaign.objects.all()[:100]]}
        )

    def post(self, request):
        serializer = AdminCampaignCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        campaign = PulseRewardCampaign.objects.create(
            **serializer.validated_data,
            created_by=request.user,
        )
        SecurityAuditLog.objects.create(
            event_type="pulse_campaign_created",
            user=request.user,
            username=request.user.username,
            detail="创建午夜脉冲活动奖励",
            metadata={"campaign_id": campaign.id, "campaign_key": campaign.key},
        )
        return Response(campaign_payload(campaign), status=status.HTTP_201_CREATED)


class PulseAdminCampaignDetailView(PulseAPIView):
    permission_classes = [AdminOrSuperAdmin]

    def patch(self, request, campaign_id):
        campaign = get_object_or_404(PulseRewardCampaign, id=campaign_id)
        serializer = AdminCampaignUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        next_starts_at = serializer.validated_data.get("starts_at", campaign.starts_at)
        next_ends_at = serializer.validated_data.get("ends_at", campaign.ends_at)
        if next_ends_at <= next_starts_at:
            raise PulseValidationError("结束时间必须晚于开始时间。")
        for field, value in serializer.validated_data.items():
            setattr(campaign, field, value)
        campaign.save(update_fields=[*serializer.validated_data.keys(), "updated_at"])
        SecurityAuditLog.objects.create(
            event_type="pulse_campaign_updated",
            user=request.user,
            username=request.user.username,
            detail="更新午夜脉冲活动奖励",
            metadata={"campaign_id": campaign.id, "fields": list(serializer.validated_data)},
        )
        return Response(campaign_payload(campaign))


def code_payload(code):
    return {
        "id": code.id,
        "code_hint": code.code_hint,
        "reward_payload": code.reward_payload,
        "starts_at": code.starts_at,
        "ends_at": code.ends_at,
        "max_uses": code.max_uses,
        "per_user_limit": code.per_user_limit,
        "used_count": code.used_count,
        "is_enabled": code.is_enabled,
        "created_at": code.created_at,
    }


class PulseAdminCodesView(PulseAPIView):
    permission_classes = [AdminOrSuperAdmin]

    def get(self, request):
        return Response({"results": [code_payload(item) for item in PulseRedemptionCode.objects.all()[:100]]})

    def post(self, request):
        serializer = AdminCodeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_code = serializer.validated_data.pop("code")
        code = create_redemption_code(
            actor=request.user, raw_code=raw_code, **serializer.validated_data
        )
        return Response(
            {**code_payload(code), "code": raw_code}, status=status.HTTP_201_CREATED
        )


class PulseAdminCodeDetailView(PulseAPIView):
    permission_classes = [AdminOrSuperAdmin]

    def patch(self, request, code_id):
        serializer = AdminCodeUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = get_object_or_404(PulseRedemptionCode, id=code_id)
        for field, value in serializer.validated_data.items():
            setattr(code, field, value)
        code.save(update_fields=[*serializer.validated_data.keys(), "updated_at"])
        return Response(code_payload(code))


def admin_edition_payload(edition):
    return edition_payload(edition, include_answers=False)


class PulseAdminEditionsView(PulseAPIView):
    permission_classes = [AdminOrSuperAdmin]

    def get(self, request):
        rows = PulseDailyEdition.objects.select_related("question", "created_by")[:100]
        return Response({"results": [admin_edition_payload(item) for item in rows]})

    def post(self, request):
        serializer = AdminEditionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            with transaction.atomic():
                question = Question.objects.create(
                    title=data["title"],
                    content_md=data["content_md"],
                    author=request.user,
                    status=Question.Status.OPEN,
                    auto_close_at=None,
                )
                edition = PulseDailyEdition.objects.create(
                    date=data["date"],
                    question=question,
                    poll_prompt=data["poll_prompt"],
                    source_type=PulseDailyEdition.SourceType.ADMIN,
                    status=(
                        PulseDailyEdition.Status.PUBLISHED
                        if data["publish"]
                        else PulseDailyEdition.Status.DRAFT
                    ),
                    created_by=request.user,
                )
                PulsePollOption.objects.bulk_create(
                    [
                        PulsePollOption(edition=edition, position=index, text=text)
                        for index, text in enumerate(data["options"], start=1)
                    ]
                )
        except IntegrityError as exc:
            raise PulseConflict("这个日期已经有午夜脉冲内容。") from exc
        return Response(admin_edition_payload(edition), status=status.HTTP_201_CREATED)


class PulseAdminEditionDetailView(PulseAPIView):
    permission_classes = [AdminOrSuperAdmin]

    def patch(self, request, edition_id):
        serializer = AdminEditionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            edition = get_object_or_404(
                PulseDailyEdition.objects.select_for_update().select_related("question"),
                id=edition_id,
            )
            data = serializer.validated_data
            question_fields = []
            if "title" in data:
                edition.question.title = data["title"]
                question_fields.append("title")
            if "content_md" in data:
                edition.question.content_md = data["content_md"]
                question_fields.append("content_md")
            if question_fields:
                edition.question.save(update_fields=[*question_fields, "updated_at"])
            edition_fields = []
            for field in ("poll_prompt", "status"):
                if field in data:
                    setattr(edition, field, data[field])
                    edition_fields.append(field)
            if edition_fields:
                edition.save(update_fields=[*edition_fields, "updated_at"])
            if "options" in data:
                if edition.poll_votes.exists():
                    raise PulseConflict("已有投票后不能替换选项。")
                edition.poll_options.all().delete()
                PulsePollOption.objects.bulk_create(
                    [
                        PulsePollOption(edition=edition, position=index, text=text)
                        for index, text in enumerate(data["options"], start=1)
                    ]
                )
        return Response(admin_edition_payload(edition))


class PulseAdminLedgerView(PulseAPIView):
    permission_classes = [AdminOrSuperAdmin]

    def get(self, request):
        rows = PulseLedgerEntry.objects.select_related("user", "actor")
        user_id = request.query_params.get("user_id")
        if user_id:
            rows = rows.filter(user_id=user_id)
        return Response(
            {
                "results": [
                    {
                        "id": item.id,
                        "user_id": item.user_id,
                        "username": item.user.username,
                        "asset": item.asset,
                        "delta": item.delta,
                        "balance_after": item.balance_after,
                        "event_key": item.event_key,
                        "source_type": item.source_type,
                        "note": item.note,
                        "created_at": item.created_at,
                    }
                    for item in rows[:200]
                ]
            }
        )
