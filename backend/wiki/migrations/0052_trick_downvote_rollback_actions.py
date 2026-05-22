from django.db import migrations, models


TRICK_CONTRIBUTION_ACTION_CHOICES = [
    ("trick_approved", "Trick 通过审核"),
    ("trick_approval_rollback", "Trick 投稿收益回滚"),
    ("trick_received_like", "Trick 收到点赞"),
    ("trick_received_like_rollback", "Trick 点赞收益回滚"),
    ("trick_cast_downvote", "发起 Trick 点踩"),
    ("trick_cast_downvote_rollback", "Trick 点踩消耗回滚"),
    ("trick_received_downvote", "Trick 收到点踩"),
    ("trick_received_downvote_rollback", "Trick 收到点踩回滚"),
    ("trick_delete_review_reward", "Trick 删除审核奖励"),
    ("admin_adjustment", "管理员调整"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("wiki", "0051_aimoderation_suspicious_approve"),
    ]

    operations = [
        migrations.AlterField(
            model_name="trickcontributionevent",
            name="action_type",
            field=models.CharField(
                choices=TRICK_CONTRIBUTION_ACTION_CHOICES,
                db_index=True,
                max_length=40,
            ),
        ),
    ]
