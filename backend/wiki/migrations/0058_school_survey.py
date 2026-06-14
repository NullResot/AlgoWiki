from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


DEFAULT_UNIVERSITIES = [
    ("清华大学", "THU", "北京市", "北京市"),
    ("北京大学", "PKU", "北京市", "北京市"),
    ("浙江大学", "ZJU", "浙江省", "杭州市"),
    ("上海交通大学", "SJTU", "上海市", "上海市"),
    ("复旦大学", "FDU", "上海市", "上海市"),
    ("南京大学", "NJU", "江苏省", "南京市"),
    ("中国科学技术大学", "USTC", "安徽省", "合肥市"),
    ("武汉大学", "WHU", "湖北省", "武汉市"),
    ("华中科技大学", "HUST", "湖北省", "武汉市"),
    ("哈尔滨工业大学", "HIT", "黑龙江省", "哈尔滨市"),
    ("电子科技大学", "UESTC", "四川省", "成都市"),
    ("北京航空航天大学", "BUAA", "北京市", "北京市"),
    ("西安交通大学", "XJTU", "陕西省", "西安市"),
    ("同济大学", "TONGJI", "上海市", "上海市"),
    ("中山大学", "SYSU", "广东省", "广州市"),
    ("东南大学", "SEU", "江苏省", "南京市"),
    ("北京理工大学", "BIT", "北京市", "北京市"),
    ("华南理工大学", "SCUT", "广东省", "广州市"),
    ("大连理工大学", "DUT", "辽宁省", "大连市"),
    ("山东大学", "SDU", "山东省", "济南市"),
    ("吉林大学", "JLU", "吉林省", "长春市"),
    ("厦门大学", "XMU", "福建省", "厦门市"),
    ("四川大学", "SCU", "四川省", "成都市"),
    ("重庆大学", "CQU", "重庆市", "重庆市"),
    ("天津大学", "TJU", "天津市", "天津市"),
    ("南开大学", "NKU", "天津市", "天津市"),
    ("西北工业大学", "NPU", "陕西省", "西安市"),
    ("北京邮电大学", "BUPT", "北京市", "北京市"),
    ("南京航空航天大学", "NUAA", "江苏省", "南京市"),
    ("南京理工大学", "NJUST", "江苏省", "南京市"),
    ("杭州电子科技大学", "HDU", "浙江省", "杭州市"),
    ("北京师范大学", "BNU", "北京市", "北京市"),
    ("中国人民大学", "RUC", "北京市", "北京市"),
    ("中国农业大学", "CAU", "北京市", "北京市"),
    ("中央民族大学", "MUC", "北京市", "北京市"),
    ("国防科技大学", "NUDT", "湖南省", "长沙市"),
    ("东北大学", "NEU", "辽宁省", "沈阳市"),
    ("湖南大学", "HNU", "湖南省", "长沙市"),
    ("中南大学", "CSU", "湖南省", "长沙市"),
    ("兰州大学", "LZU", "甘肃省", "兰州市"),
]


def seed_default_universities(apps, schema_editor):
    school_model = apps.get_model("wiki", "SchoolSurveySchool")
    for index, (name, abbreviation, province, city) in enumerate(DEFAULT_UNIVERSITIES, start=10):
        school_model.objects.update_or_create(
            name=name,
            defaults={
                "abbreviation": abbreviation,
                "province": province,
                "city": city,
                "school_type": "university",
                "display_order": index,
                "is_active": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("wiki", "0057_user_gender"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SchoolSurveySchool",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(db_index=True, max_length=120, unique=True)),
                ("abbreviation", models.CharField(blank=True, max_length=40)),
                ("province", models.CharField(blank=True, db_index=True, max_length=80)),
                ("city", models.CharField(blank=True, db_index=True, max_length=80)),
                (
                    "school_type",
                    models.CharField(
                        choices=[("university", "University"), ("other", "Other")],
                        db_index=True,
                        default="university",
                        max_length=30,
                    ),
                ),
                ("logo_url", models.URLField(blank=True, max_length=500)),
                ("display_order", models.PositiveIntegerField(db_index=True, default=0)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
            ],
            options={
                "ordering": ["display_order", "name", "id"],
            },
        ),
        migrations.CreateModel(
            name="SchoolSurveySubmission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("form_data", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("submitted", "Submitted"),
                            ("archived", "Archived"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("submitted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                (
                    "author",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="school_survey_submissions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="submissions",
                        to="wiki.schoolsurveyschool",
                    ),
                ),
            ],
            options={
                "ordering": ["-submitted_at", "-updated_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="schoolsurveysubmission",
            index=models.Index(fields=["school", "status", "submitted_at"], name="survey_sub_school_status_idx"),
        ),
        migrations.AddIndex(
            model_name="schoolsurveysubmission",
            index=models.Index(fields=["author", "status", "updated_at"], name="survey_sub_author_status_idx"),
        ),
        migrations.RunPython(seed_default_universities, migrations.RunPython.noop),
    ]
