from django.db import migrations, models
import django.db.models.deletion
from django.utils.text import slugify


BUILTIN_TRICK_TERMS = [
    "二分答案",
    "双指针",
    "滑动窗口",
    "前缀和",
    "差分",
    "离散化",
    "贪心",
    "排序技巧",
    "位运算",
    "lowbit",
    "快速幂",
    "矩阵快速幂",
    "欧拉函数",
    "扩展欧几里得",
    "中国剩余定理",
    "筛法",
    "质因数分解",
    "组合数学",
    "容斥原理",
    "博弈论",
    "DFS",
    "BFS",
    "最短路",
    "并查集",
    "最小生成树",
    "树形DP",
    "换根DP",
    "LCA",
    "树状数组",
    "线段树",
    "可持久化数据结构",
    "单调栈",
    "单调队列",
    "字符串哈希",
    "KMP",
    "AC自动机",
    "后缀数组",
    "网络流",
    "最小割",
    "费用流",
    "状态压缩DP",
    "区间DP",
    "数位DP",
    "概率DP",
    "构造",
    "交互题",
    "模拟",
    "精度处理",
    "卡常",
    "代码模板",
]


def seed_builtin_terms(apps, schema_editor):
    TrickTerm = apps.get_model("wiki", "TrickTerm")
    for name in BUILTIN_TRICK_TERMS:
        base = slugify(name) or "trick-term"
        candidate = base
        index = 2
        while TrickTerm.objects.filter(slug=candidate).exists():
            candidate = f"{base}-{index}"
            index += 1
        TrickTerm.objects.get_or_create(
            name=name,
            defaults={
                "slug": candidate,
                "description": "",
                "is_active": True,
                "is_builtin": True,
            },
        )


def unseed_builtin_terms(apps, schema_editor):
    TrickTerm = apps.get_model("wiki", "TrickTerm")
    TrickTerm.objects.filter(name__in=BUILTIN_TRICK_TERMS, is_builtin=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("wiki", "0028_headernavigationitem_questions"),
    ]

    operations = [
        migrations.CreateModel(
            name="TrickTerm",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=80, unique=True)),
                ("slug", models.SlugField(blank=True, max_length=100, unique=True)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("is_builtin", models.BooleanField(default=False)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="TrickTermSuggestion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=80)),
                ("normalized_name", models.CharField(db_index=True, max_length=80)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("review_note", models.CharField(blank=True, max_length=255)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "proposer",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="trick_term_suggestions", to="wiki.user"),
                ),
                (
                    "reviewer",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_trick_term_suggestions", to="wiki.user"),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddField(
            model_name="trickentry",
            name="terms",
            field=models.ManyToManyField(blank=True, related_name="trick_entries", to="wiki.trickterm"),
        ),
        migrations.AddConstraint(
            model_name="tricktermsuggestion",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "pending")),
                fields=("normalized_name", "status"),
                name="uniq_pending_trick_term_suggestion",
            ),
        ),
        migrations.RunPython(seed_builtin_terms, reverse_code=unseed_builtin_terms),
    ]
