import json
from pathlib import Path

from django.db import migrations


LEGACY_CONTENT_BY_SLUG = {
    "about": {
        "# 关于 AlgoWiki\n\nAlgoWiki 是一个面向程序设计竞赛学习者的结构化知识库与社区协作平台。",
        "# 关于 AlgoWiki\n\nAlgoWiki 是一个公益性质的算法竞赛 Wiki 信息平台，围绕开源协作、信息共享、互助交流与友善社区建设展开，目标是帮助算法竞赛学习者更低成本地获取可靠资料、赛事信息与备赛经验。\n\n## 主要内容\n\n### 竞赛 Wiki\n\n竞赛 Wiki 以 [【打破信息差】萌新认识与入门算法竞赛](https://github.com/NullResot/xcpc) 为初始数据源，面向刚入门的竞赛选手，系统整理大学生算法竞赛相关信息。\n\n主要包含：\n\n1. 常见赛制与主要竞赛介绍。\n2. 入门训练建议、学习路线与资源汇总。\n3. 竞赛相关网站、项目与工具的整理。\n\n### 赛事专区\n\n赛事专区用于集中维护竞赛相关的时效信息与经验资料，主要包含：\n\n1. 比赛日历表：整理 Codeforces、AtCoder、牛客、洛谷等线上训练比赛日程。\n2. trick 技巧汇总：收集算法竞赛中的技巧、结论与经验，便于检索和复习。\n3. 赛事时刻表：整理年度线下竞赛安排，帮助选手了解比赛时间与阶段。\n4. 赛事公告：补充赛事时刻表中的详细说明，例如语言支持、邀请函、报名链接与特殊规则。\n5. 补题链接：以 [hh2048 / 历年 XCPC 赛事补题链接整理](https://github.com/hh2048/XCPC/tree/main/04%20-%20%E5%8E%86%E5%B9%B4XCPC%E8%B5%9B%E4%BA%8B%E8%A1%A5%E9%A2%98%E9%93%BE%E6%8E%A5%E6%95%B4%E7%90%86) 为初始数据源，帮助选手快速找到对应比赛的补题入口。\n\n## 其他页面\n\n1. 问答：用于提交网站建议、讨论竞赛问题与进行社区互助。\n2. 文档：用于记录站点说明、提交规范与管理员维护说明。\n3. 友链：用于收录和展示竞赛相关的优质网站。\n\n## 参与方式\n\n欢迎通过页面提交、问答反馈、GitHub 贡献等方式参与内容维护。官方交流群：1094808529。\n\n## 项目信息\n\n本项目起始于 2025 年 12 月 26 日 20:01:21。\n\n本项目正式上线于 2026 年 4 月 11 日。",
    },
    "trick-guide": {
        "## 标题\n\n标题应尽量简短，直接概括 trick 的核心用途、结论或适用场景。\n\n## 词条\n\n发布时必须选择对应词条，可多选，但应与内容实际相关。\n\n## 内容\n\n1. 说明 trick 的核心思路、适用范围与限制。\n2. 尽量附上 1 道或多道相关例题，并使用 Markdown 链接。\n3. 不接受代码模板、题解全文搬运、无实际内容的结论堆砌。\n4. 请遵守 Markdown 与 LaTeX 语法，保证排版清晰、表达准确。",
        "## 标题\n\n标题应尽量简短，直接概括 trick 的核心用途、结论或适用场景。\n\n## 词条\n\n发布时必须选择对应词条，可多选，但应与内容实际相关。\n\n## 内容\n\n1. 说明 trick 的核心思路、适用范围与限制。\n2. 尽量附上 1 道或多道相关例题，并使用 Markdown 链接。\n3. 不接受代码模板、题解全文搬运、无实际内容的结论堆砌。\n4. 请遵守 Markdown 与 LaTeX 语法，保证排版清晰、表达准确。\n",
    },
}


def normalize_content(value):
    return str(value or "").replace("\r\n", "\n").strip()


def load_snapshot_defs():
    snapshot_path = (
        Path(__file__).resolve().parents[1]
        / "seed_content"
        / "document_pages_snapshot.json"
    )
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    return payload.get("pages", payload)


def sync_document_pages_snapshot(apps, schema_editor):
    ExtensionPage = apps.get_model("wiki", "ExtensionPage")
    DocumentPageSection = apps.get_model("wiki", "DocumentPageSection")

    for item in load_snapshot_defs():
        page, created = ExtensionPage.objects.get_or_create(
            slug=item["slug"],
            defaults={
                "title": item["page_title"],
                "description": item["description"],
                "content_md": item["content_md"],
                "access_level": item.get("access_level", "public"),
                "is_enabled": item.get("is_enabled", True),
            },
        )

        update_fields = []
        current_content = normalize_content(getattr(page, "content_md", ""))
        legacy_content = {
            normalize_content(value)
            for value in LEGACY_CONTENT_BY_SLUG.get(item["slug"], set())
        }
        if not created and (not current_content or current_content in legacy_content):
            page.content_md = item["content_md"]
            update_fields.append("content_md")
        if not str(page.title or "").strip():
            page.title = item["page_title"]
            update_fields.append("title")
        if not str(page.description or "").strip():
            page.description = item["description"]
            update_fields.append("description")
        if update_fields:
            page.save(update_fields=update_fields + ["updated_at"])

        section, section_created = DocumentPageSection.objects.get_or_create(
            key=item["key"],
            defaults={
                "title": item["section_title"],
                "page": page,
                "display_order": item["display_order"],
                "is_visible": item.get("is_visible", True),
            },
        )
        if not section_created and not section.page_id:
            section.page = page
            section.save(update_fields=["page", "updated_at"])


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("wiki", "0038_restore_default_document_page_content"),
    ]

    operations = [
        migrations.RunPython(sync_document_pages_snapshot, noop_reverse),
    ]
