from rest_framework import serializers

from ..models import PulseChallengeAssignment, PulseLedgerEntry, PulseMakeup


class BindingStartSerializer(serializers.Serializer):
    handle = serializers.CharField(min_length=3, max_length=24)


class BindingVerifySerializer(serializers.Serializer):
    verification_id = serializers.IntegerField(min_value=1)


class SelfUnbindSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False, max_length=256)


class AnswerCreateSerializer(serializers.Serializer):
    content_md = serializers.CharField(min_length=3, max_length=20000)


class AnswerListQuerySerializer(serializers.Serializer):
    limit = serializers.IntegerField(min_value=1, max_value=100, default=30)
    offset = serializers.IntegerField(min_value=0, default=0)


class PollVoteSerializer(serializers.Serializer):
    option_id = serializers.IntegerField(min_value=1)


class ChallengeChooseSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=PulseChallengeAssignment.Mode.choices)


class ChallengeCheckSerializer(serializers.Serializer):
    assignment_id = serializers.IntegerField(min_value=1)


class MakeupCreateSerializer(serializers.Serializer):
    target_date = serializers.DateField()
    kind = serializers.ChoiceField(choices=PulseMakeup.Kind.choices)


class RedeemSerializer(serializers.Serializer):
    code = serializers.CharField(min_length=6, max_length=64)
    idempotency_key = serializers.CharField(min_length=4, max_length=180)


class RankingQuerySerializer(serializers.Serializer):
    school_name = serializers.CharField(max_length=120, required=False)
    rating_min = serializers.IntegerField(min_value=0, max_value=5000, required=False)
    rating_max = serializers.IntegerField(min_value=0, max_value=5000, required=False)

    def validate(self, attrs):
        if (
            "rating_min" in attrs
            and "rating_max" in attrs
            and attrs["rating_max"] < attrs["rating_min"]
        ):
            raise serializers.ValidationError(
                {"rating_max": "最高 Rating 不能低于最低 Rating。"}
            )
        return attrs


class AdminUnbindSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=2, max_length=300)
    allow_rebind_now = serializers.BooleanField(default=False)


class AdminLedgerQuerySerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1, required=False)


class AdminGrantSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)
    rewards = serializers.DictField(child=serializers.IntegerField(min_value=1))
    idempotency_key = serializers.CharField(min_length=4, max_length=180)
    note = serializers.CharField(max_length=300, allow_blank=True, required=False)

    def validate_rewards(self, value):
        allowed = {asset for asset, _ in PulseLedgerEntry.Asset.choices}
        unknown = set(value) - allowed
        if unknown:
            raise serializers.ValidationError(f"Unknown assets: {', '.join(sorted(unknown))}")
        if not value:
            raise serializers.ValidationError("At least one reward is required.")
        return value


class AdminCampaignCreateSerializer(serializers.Serializer):
    key = serializers.SlugField(min_length=3, max_length=80)
    name = serializers.CharField(min_length=2, max_length=120)
    reward_payload = serializers.DictField(child=serializers.IntegerField(min_value=1))
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    is_enabled = serializers.BooleanField(default=True)

    def validate_reward_payload(self, value):
        allowed = {asset for asset, _ in PulseLedgerEntry.Asset.choices}
        if not value or set(value) - allowed:
            raise serializers.ValidationError("奖励资产无效或为空。")
        return value

    def validate(self, attrs):
        if attrs["ends_at"] <= attrs["starts_at"]:
            raise serializers.ValidationError({"ends_at": "结束时间必须晚于开始时间。"})
        return attrs


class AdminCampaignUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=2, max_length=120, required=False)
    reward_payload = serializers.DictField(
        child=serializers.IntegerField(min_value=1), required=False
    )
    starts_at = serializers.DateTimeField(required=False)
    ends_at = serializers.DateTimeField(required=False)
    is_enabled = serializers.BooleanField(required=False)

    def validate_reward_payload(self, value):
        allowed = {asset for asset, _ in PulseLedgerEntry.Asset.choices}
        if not value or set(value) - allowed:
            raise serializers.ValidationError("奖励资产无效或为空。")
        return value


class AdminCodeCreateSerializer(serializers.Serializer):
    code = serializers.CharField(min_length=6, max_length=64)
    reward_payload = serializers.DictField(child=serializers.IntegerField(min_value=1))
    starts_at = serializers.DateTimeField(required=False, allow_null=True)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
    max_uses = serializers.IntegerField(min_value=1, default=1)
    per_user_limit = serializers.IntegerField(min_value=1, default=1)


class AdminEditionCreateSerializer(serializers.Serializer):
    date = serializers.DateField()
    title = serializers.CharField(min_length=3, max_length=220)
    content_md = serializers.CharField(min_length=3, max_length=20000)
    poll_prompt = serializers.CharField(min_length=3, max_length=300)
    options = serializers.ListField(
        child=serializers.CharField(min_length=1, max_length=180),
        min_length=2,
        max_length=5,
    )
    publish = serializers.BooleanField(default=False)


class AdminEditionUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(min_length=3, max_length=220, required=False)
    content_md = serializers.CharField(min_length=3, max_length=20000, required=False)
    poll_prompt = serializers.CharField(min_length=3, max_length=300, required=False)
    options = serializers.ListField(
        child=serializers.CharField(min_length=1, max_length=180),
        min_length=2,
        max_length=5,
        required=False,
    )
    status = serializers.ChoiceField(
        choices=("draft", "published"), required=False
    )


class AdminCodeUpdateSerializer(serializers.Serializer):
    is_enabled = serializers.BooleanField(required=False)
    starts_at = serializers.DateTimeField(required=False, allow_null=True)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
