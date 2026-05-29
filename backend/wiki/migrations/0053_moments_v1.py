import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import wiki.models


def seed_moment_defaults(apps, schema_editor):
    MomentSettings = apps.get_model("wiki", "MomentSettings")
    HeaderNavigationItem = apps.get_model("wiki", "HeaderNavigationItem")
    MomentSettings.objects.get_or_create(singleton_key=1)
    HeaderNavigationItem.objects.update_or_create(
        key="moments",
        defaults={
            "title": "动态",
            "display_order": 34,
            "is_visible": False,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("wiki", "0052_trick_downvote_rollback_actions"),
    ]

    operations = [
        migrations.AddField(
            model_name="aimoderationconfig",
            name="moment_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="aimoderationconfig",
            name="moment_comment_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name="aimoderationrecord",
            name="target_type",
            field=models.CharField(
                choices=[
                    ("comment", "Comment"),
                    ("question", "Question"),
                    ("answer", "Answer"),
                    ("ticket", "Ticket"),
                    ("moment", "Moment"),
                    ("moment_comment", "Moment Comment"),
                ],
                db_index=True,
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="headernavigationitem",
            name="key",
            field=models.CharField(
                choices=[
                    ("home", "Home"),
                    ("competition-wiki", "Competition Wiki"),
                    ("competitions", "Competition Zone"),
                    ("moments", "Moments"),
                    ("questions", "Q&A"),
                    ("about", "About AlgoWiki"),
                    ("friendly-links", "Friendly Links"),
                ],
                db_index=True,
                max_length=40,
                unique=True,
            ),
        ),
        migrations.CreateModel(
            name="MomentSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("singleton_key", models.PositiveSmallIntegerField(default=1, editable=False, unique=True)),
                ("is_enabled", models.BooleanField(default=False)),
                ("publishing_enabled", models.BooleanField(default=False)),
                ("commenting_enabled", models.BooleanField(default=False)),
                ("reactions_enabled", models.BooleanField(default=True)),
                ("favorites_enabled", models.BooleanField(default=True)),
                ("hot_list_enabled", models.BooleanField(default=False)),
                ("featured_feed_enabled", models.BooleanField(default=False)),
                ("require_real_name", models.BooleanField(default=True)),
                ("require_manual_review_for_new_users", models.BooleanField(default=True)),
                ("new_user_manual_review_count", models.PositiveSmallIntegerField(default=3)),
                ("daily_post_limit", models.PositiveSmallIntegerField(default=20)),
                ("daily_comment_limit", models.PositiveSmallIntegerField(default=80)),
                ("max_images_per_post", models.PositiveSmallIntegerField(default=9)),
                ("max_image_size_mb", models.PositiveSmallIntegerField(default=5)),
                ("max_text_length", models.PositiveIntegerField(default=2000)),
                ("max_comment_length", models.PositiveIntegerField(default=500)),
                ("auto_hide_report_threshold", models.PositiveSmallIntegerField(default=3)),
                ("hot_window_days", models.PositiveSmallIntegerField(default=7)),
                ("hot_limit", models.PositiveSmallIntegerField(default=10)),
                ("hot_like_weight", models.PositiveSmallIntegerField(default=2)),
                ("hot_favorite_weight", models.PositiveSmallIntegerField(default=3)),
                ("hot_comment_weight", models.PositiveSmallIntegerField(default=2)),
                ("hot_report_penalty", models.PositiveSmallIntegerField(default=10)),
                (
                    "rules_summary",
                    models.TextField(
                        blank=True,
                        default=(
                            "请发布与算法学习、竞赛训练、站内协作相关的内容。"
                            "禁止发布违法违规、色情低俗、暴力恐怖、涉政攻击、广告引流、"
                            "考试或正在进行比赛的题目答案、侵犯隐私或人身攻击内容。"
                        ),
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_moment_settings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="RealNameVerification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("unverified", "Unverified"),
                            ("pending", "Pending"),
                            ("verified", "Verified"),
                            ("rejected", "Rejected"),
                            ("revoked", "Revoked"),
                        ],
                        db_index=True,
                        default="unverified",
                        max_length=20,
                    ),
                ),
                ("real_name_masked", models.CharField(blank=True, max_length=40)),
                ("id_number_last4", models.CharField(blank=True, max_length=4)),
                ("provider", models.CharField(blank=True, default="manual", max_length=40)),
                ("provider_trace_id", models.CharField(blank=True, max_length=120)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("review_note", models.CharField(blank=True, max_length=300)),
                (
                    "reviewer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_real_name_verifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="real_name_verification",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="Moment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("content", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending Review"),
                            ("published", "Published"),
                            ("rejected", "Rejected"),
                            ("hidden", "Hidden"),
                            ("deleted", "Deleted"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("published_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("review_note", models.CharField(blank=True, max_length=300)),
                ("allow_hot", models.BooleanField(db_index=True, default=True)),
                ("is_featured", models.BooleanField(db_index=True, default=False)),
                ("comments_locked", models.BooleanField(default=False)),
                ("hidden_at", models.DateTimeField(blank=True, null=True)),
                ("hidden_reason", models.CharField(blank=True, max_length=300)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("like_count", models.PositiveIntegerField(default=0)),
                ("favorite_count", models.PositiveIntegerField(default=0)),
                ("comment_count", models.PositiveIntegerField(default=0)),
                ("report_count", models.PositiveIntegerField(default=0)),
                ("hot_score", models.IntegerField(db_index=True, default=0)),
                ("last_ai_summary", models.CharField(blank=True, max_length=300)),
                ("last_ai_risk_level", models.CharField(blank=True, max_length=20)),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="moments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "deleted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="deleted_moments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "hidden_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="hidden_moments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_moments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-published_at", "-created_at", "-id"],
                "indexes": [
                    models.Index(fields=["status", "published_at"], name="wiki_moment_status_a895cf_idx"),
                    models.Index(fields=["allow_hot", "hot_score"], name="wiki_moment_allow_h_2ba7e6_idx"),
                    models.Index(fields=["author", "status"], name="wiki_moment_author__3531eb_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="MomentImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("image", models.ImageField(upload_to=wiki.models.moment_image_upload_to)),
                ("original_name", models.CharField(blank=True, max_length=255)),
                ("content_type", models.CharField(blank=True, max_length=120)),
                ("size_bytes", models.PositiveIntegerField(default=0)),
                ("display_order", models.PositiveSmallIntegerField(default=0)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending Review"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                            ("hidden", "Hidden"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("moderation_summary", models.CharField(blank=True, max_length=300)),
                (
                    "moment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="images",
                        to="wiki.moment",
                    ),
                ),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="uploaded_moment_images",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["display_order", "id"]},
        ),
        migrations.CreateModel(
            name="MomentComment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("content", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending Review"),
                            ("visible", "Visible"),
                            ("rejected", "Rejected"),
                            ("hidden", "Hidden"),
                            ("deleted", "Deleted"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("review_note", models.CharField(blank=True, max_length=300)),
                ("report_count", models.PositiveIntegerField(default=0)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("last_ai_summary", models.CharField(blank=True, max_length=300)),
                ("last_ai_risk_level", models.CharField(blank=True, max_length=20)),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="moment_comments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "deleted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="deleted_moment_comments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "moment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comments",
                        to="wiki.moment",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_moment_comments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["created_at", "id"],
                "indexes": [
                    models.Index(fields=["moment", "status"], name="wiki_moment_moment__938804_idx"),
                    models.Index(fields=["author", "status"], name="wiki_moment_author__0a09c4_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="MomentLike",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "moment",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="likes", to="wiki.moment"),
                ),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="moment_likes", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"ordering": ["-created_at"], "unique_together": {("moment", "user")}},
        ),
        migrations.CreateModel(
            name="MomentFavorite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "moment",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="favorites", to="wiki.moment"),
                ),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="moment_favorites", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"ordering": ["-created_at"], "unique_together": {("moment", "user")}},
        ),
        migrations.CreateModel(
            name="MomentReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "target_type",
                    models.CharField(choices=[("moment", "Moment"), ("comment", "Comment")], db_index=True, max_length=20),
                ),
                (
                    "reason",
                    models.CharField(
                        choices=[
                            ("spam", "Spam"),
                            ("porn", "Porn"),
                            ("political", "Political"),
                            ("violence", "Violence"),
                            ("abuse", "Abuse"),
                            ("privacy", "Privacy"),
                            ("cheating", "Cheating"),
                            ("irrelevant", "Irrelevant"),
                            ("other", "Other"),
                        ],
                        db_index=True,
                        default="other",
                        max_length=20,
                    ),
                ),
                ("description", models.CharField(blank=True, max_length=500)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("resolved", "Resolved"), ("rejected", "Rejected")],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("handled_at", models.DateTimeField(blank=True, null=True)),
                ("resolution_action", models.CharField(blank=True, max_length=80)),
                ("resolution_note", models.CharField(blank=True, max_length=300)),
                (
                    "comment",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="reports", to="wiki.momentcomment"),
                ),
                (
                    "handled_by",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="handled_moment_reports", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "moment",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="reports", to="wiki.moment"),
                ),
                (
                    "reporter",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="moment_reports", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "target_author",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="received_moment_reports", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["target_type", "status", "created_at"], name="wiki_moment_target__40e219_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="MomentUserRestriction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("can_post", models.BooleanField(default=True)),
                ("can_comment", models.BooleanField(default=True)),
                ("can_react", models.BooleanField(default=True)),
                ("can_upload_images", models.BooleanField(default=True)),
                ("can_enter_hot", models.BooleanField(default=True)),
                ("muted_until", models.DateTimeField(blank=True, null=True)),
                ("reason", models.CharField(blank=True, max_length=300)),
                (
                    "updated_by",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_moment_user_restrictions", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "user",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="moment_restriction", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"ordering": ["user__username"]},
        ),
        migrations.CreateModel(
            name="MomentAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("create", "Create"),
                            ("update", "Update"),
                            ("approve", "Approve"),
                            ("reject", "Reject"),
                            ("hide", "Hide"),
                            ("delete", "Delete"),
                            ("restore", "Restore"),
                            ("report", "Report"),
                            ("restrict", "Restrict"),
                            ("config", "Config"),
                            ("hot", "Hot"),
                            ("verify", "Verify"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("target_type", models.CharField(blank=True, db_index=True, max_length=80)),
                ("target_id", models.PositiveBigIntegerField(blank=True, db_index=True, null=True)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "actor",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="moment_audit_actions", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "target_user",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="moment_audit_logs", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["event_type", "created_at"], name="wiki_moment_event_t_834c14_idx"),
                    models.Index(fields=["target_type", "target_id"], name="wiki_moment_target__471c68_idx"),
                ],
            },
        ),
        migrations.AlterField(
            model_name="contributionevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("star", "Star"),
                    ("comment", "Comment"),
                    ("issue", "Issue"),
                    ("revision", "Revision"),
                    ("question", "Question"),
                    ("answer", "Answer"),
                    ("announcement", "Announcement"),
                    ("moment", "Moment"),
                    ("admin", "Admin Action"),
                ],
                max_length=20,
            ),
        ),
        migrations.RunPython(seed_moment_defaults, migrations.RunPython.noop),
    ]
