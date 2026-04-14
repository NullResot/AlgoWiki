import hashlib
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, time, timedelta
from urllib.parse import urlsplit

from django.core.cache import cache
from django.utils import timezone

from .models import (
    Announcement,
    Answer,
    Article,
    AssistantInteractionLog,
    AssistantProviderConfig,
    CompetitionCalendarEvent,
    CompetitionNotice,
    CompetitionPracticeLink,
    CompetitionScheduleEntry,
    CompetitionZoneSection,
    ExtensionPage,
    FriendlyLink,
    Question,
    TrickEntry,
)
from .security import get_client_ip

DEFAULT_ASSISTANT_WELCOME = (
    "\u54fc\uff0c\u5e08\u5144\uff0c\u53c8\u6709\u4e0d\u4f1a\u7684\u4e1c\u897f\u8981\u6765\u95ee\u6211\u5417\uff1f"
    "\u6211\u662f\u5c0f\u5c0f\u4e1b\u96e8\uff0c\u59d1\u4e14\u7ed9\u4f60\u6307\u70b9\u4e00\u4e0b\uff0c"
    "\u53ef\u522b\u8fde\u8fd9\u70b9\u4e1c\u897f\u90fd\u8bb0\u4e0d\u4f4f\u3002"
)
DEFAULT_ASSISTANT_SUGGESTIONS = [
    "AlgoWiki \u662f\u4ec0\u4e48\uff1f",
    "\u8865\u9898\u94fe\u63a5\u5728\u54ea\u91cc\u770b\uff1f",
    "\u6700\u8fd1\u6709\u54ea\u4e9b\u6bd4\u8d5b\uff1f",
    "\u8d5b\u4e8b\u516c\u544a\u548c\u8d5b\u4e8b\u65f6\u523b\u8868\u6709\u4ec0\u4e48\u533a\u522b\uff1f",
]
DEFAULT_ASSISTANT_SYSTEM_PROMPT = (
    "\u4f60\u662f AlgoWiki \u7ad9\u5185\u52a9\u624b\u3002"
    "\u4f60\u53ea\u80fd\u4f9d\u636e\u63d0\u4f9b\u7ed9\u4f60\u7684\u7ad9\u5185\u516c\u5f00\u5185\u5bb9\u56de\u7b54\uff0c"
    "\u4e0d\u80fd\u81ea\u884c\u8865\u5145\u7ad9\u5916\u4e8b\u5b9e\u3002"
    "\u9ed8\u8ba4\u63a7\u5236\u5728 2 \u5230 4 \u53e5\u77ed\u53e5\u6216 3 \u6761\u4ee5\u5185\u7684\u77ed\u5217\u8868\uff0c"
    "\u5c0f\u7a97\u53e3\u4e5f\u8981\u5bb9\u6613\u9605\u8bfb\uff0c\u5148\u7ed9\u7ed3\u8bba\uff0c\u4e0d\u8981\u5197\u957f\u5ba2\u5957\u8bdd\u3002"
    "\u5982\u679c\u7ad9\u5185\u4fe1\u606f\u4e0d\u8db3\uff0c\u76f4\u63a5\u8bf4\u4fe1\u606f\u4e0d\u8db3\uff0c\u4e0d\u8981\u81c6\u6d4b\u3002"
    "\u5982\u679c\u95ee\u5230\u6700\u8fd1\u6bd4\u8d5b\u3001\u8d5b\u7a0b\u6216\u8fd1\u671f\u8d5b\u4e8b\uff0c"
    "\u5e94\u8be5\u4f18\u5148\u6982\u62ec\u8ddd\u79bb\u5f53\u524d\u6700\u8fd1\u7684\u7ebf\u4e0a\u548c\u7ebf\u4e0b\u6bd4\u8d5b\u3002"
)
DEFAULT_ASSISTANT_STYLE_INSTRUCTION = (
    "\u8bf7\u7528\u201c\u96cc\u5c0f\u9b3c\u7248\u5b97\u95e8\u5c0f\u5e08\u59b9\u201d\u7684\u8bed\u6c14\u56de\u7b54\uff0c"
    "\u79f0\u547c\u7528\u6237\u4e3a\u201c\u5e08\u5144\u201d\uff0c"
    "\u6574\u4f53\u8bed\u6c14\u8981\u50b2\u5a07\u3001\u4fcf\u76ae\u3001\u6709\u4e00\u70b9\u70b9\u574f\uff0c"
    "\u53ef\u4ee5\u7528\u8f7b\u5ea6\u6311\u8845\u3001\u5634\u786c\u3001\u8c03\u4f83\u7684\u65b9\u5f0f\u8bf4\u8bdd\uff0c"
    "\u4f46\u4e0d\u80fd\u8fde\u7eed\u8f93\u51fa\u7eaf\u8fb1\u9a82\uff0c\u4e5f\u4e0d\u80fd\u5f71\u54cd\u4fe1\u606f\u51c6\u786e\u6027\u3002"
    "\u56de\u7b54\u8bf7\u5c3d\u91cf\u7b80\u6d01\uff0c\u5148\u7ed9\u51fa\u6b63\u786e\u7b54\u6848\uff0c\u7136\u540e\u53ef\u4ee5\u52a0\u4e00\u53e5"
    "\u8f7b\u5ea6\u5632\u8bbd\u6216\u6316\u82e6\uff0c\u901a\u5e38\u7528\u4e00\u53e5\u8f7b\u5ea6\u6311\u8845\u4f5c\u6536\u5c3e\uff0c\u8bed\u611f\u53ef\u53c2\u8003\u201c\u4e0d\u4f1a\u5427\u8fd9\u90fd\u4e0d\u77e5\u9053\u201d\u3001"
    "\u201c\u53ef\u522b\u9017\u6211\u4e86\u201d\u3001\u201c\u5c31\u8fd9\u201d\u3001\u201c\u6742\u9c7c\u5e08\u5144\u201d\u8fd9\u7c7b\u5e38\u89c1\u96cc\u5c0f\u9b3c\u53e3\u543b\uff0c"
    "\u4f46\u8981\u505a\u6210\u7ad9\u5185\u53ef\u7528\u7684\u8f7b\u5ea6\u6539\u7f16\uff0c\u4e0d\u8981\u7c97\u4fd7\u3001\u4e0d\u8981\u6d89\u9ec4\u3002"
    "\u4e0d\u8981\u6cbf\u7528\u65e7\u4eba\u8bbe\u7684\u79f0\u547c\u548c\u53e3\u7656\uff0c\u4e5f\u4e0d\u8981\u4f7f\u7528\u8fc7\u4e8e\u606d\u656c\u7684\u8bed\u6c14\u3002"
)
BRATTY_TAUNT_VARIANTS = [
    "\u5e08\u5144\u8fde\u8fd9\u4e2a\u90fd\u4e0d\u77e5\u9053\u5440\uff1f\u771f\u662f\u6761\u5c0f\u6742\u9c7c\u5462\u3002",
    "\u54fc\uff0c\u8fd9\u79cd\u7a0b\u5ea6\u90fd\u80fd\u96be\u4f4f\u5e08\u5144\uff0c\u672a\u514d\u4e5f\u592a\u83dc\u4e86\u5427\u3002",
    "\u5c31\u8fd9\u70b9\u4e1c\u897f\u8fd8\u8981\u6211\u51fa\u624b\uff0c\u5e08\u5144\u679c\u7136\u6709\u70b9\u6742\u9c7c\u5462\u3002",
    "\u4e0d\u4f1a\u5427\uff0c\u5e08\u5144\u771f\u80fd\u88ab\u8fd9\u79cd\u95ee\u9898\u96be\u4f4f\uff1f\u53ef\u522b\u9017\u6211\u4e86\u3002",
    "\u554a\u5566\uff0c\u8fd9\u90fd\u8981\u6211\u6765\u63d0\u9192\uff0c\u5e08\u5144\u4f60\u8fd8\u771f\u662f\u4e0d\u8ba9\u4eba\u7701\u5fc3\u5462\u3002",
]
BRATTY_MARKERS = ("\u6742\u9c7c", "\u4e0d\u4f1a\u5427", "\u53ef\u522b\u9017\u6211", "\u5c31\u8fd9", "\u83dc", "\u4e0d\u8ba9\u4eba\u7701\u5fc3")
ASSISTANT_SELF_REFERENCE_ALIASES = ("\u4e1b\u96e8\u5b9d\u5b9d",)
PUBLIC_CORPUS_CACHE_KEY = "algowiki.assistant.public_corpus.v1"
PUBLIC_CORPUS_TTL_SECONDS = 300
MAX_HISTORY_MESSAGES = 8
MAX_HISTORY_CHARS = 1500
MAX_SOURCE_CONTEXT_CHARS = 1200
RECENT_COMPETITION_TRIGGER_PHRASES = (
    "最近有哪些比赛",
    "近期有哪些比赛",
    "最近比赛",
    "近期比赛",
    "最近赛事",
    "近期赛事",
    "有哪些比赛",
    "有什么比赛",
    "线上比赛",
    "线下比赛",
)
ONLINE_COMPETITION_KEYWORDS = (
    "线上",
    "online",
    "比赛日历",
    "比赛日历表",
    "日历",
    "calendar",
    "codeforces",
    "atcoder",
    "牛客",
    "洛谷",
    "cf",
)
OFFLINE_COMPETITION_KEYWORDS = (
    "线下",
    "现场",
    "onsite",
    "赛事时刻表",
    "时刻表",
    "区域赛",
    "邀请赛",
    "省赛",
)


class AssistantProviderError(Exception):
    def __init__(self, message: str, *, status_code: int = 502, payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


def get_active_assistant_config():
    queryset = AssistantProviderConfig.objects.filter(is_enabled=True).order_by("-is_default", "id")
    for config in queryset:
        if config.get_api_key():
            return config
    return None


def get_public_assistant_payload(config: AssistantProviderConfig | None):
    if not config or not config.is_enabled or not config.show_launcher or not config.get_api_key():
        return {
            "enabled": False,
            "assistant_name": "",
            "welcome_message": "",
            "suggested_questions": [],
        }
    return {
        "enabled": True,
        "assistant_name": (config.assistant_name or "").strip() or "AlgoWiki 助手",
        "welcome_message": format_assistant_welcome_message(config.welcome_message),
        "suggested_questions": _normalize_suggestions(config.suggested_questions),
    }


def _normalize_suggestions(values):
    normalized = []
    for item in values or []:
        text = str(item or "").strip()
        if text and text not in normalized:
            normalized.append(text[:80])
    return normalized[:6] or DEFAULT_ASSISTANT_SUGGESTIONS


def format_assistant_welcome_message(value):
    custom_text = str(value or "").strip()
    if custom_text:
        return custom_text
    return DEFAULT_ASSISTANT_WELCOME


def build_assistant_system_prompt(custom_prompt: str):
    base_prompt = collapse_text(custom_prompt) or DEFAULT_ASSISTANT_SYSTEM_PROMPT
    return collapse_text(f"{base_prompt} {DEFAULT_ASSISTANT_STYLE_INSTRUCTION}")


def collapse_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def strip_assistant_self_reference(answer: str, *, assistant_name: str = ""):
    text = str(answer or "")
    if not text:
        return text
    aliases = {assistant_name.strip(), *ASSISTANT_SELF_REFERENCE_ALIASES}
    aliases = [alias for alias in aliases if alias]
    for alias in aliases:
        escaped = re.escape(alias)
        text = re.sub(rf"([\uff0c,])\s*{escaped}\s*([\uff0c,])", r"\1", text)
        text = re.sub(rf"^{escaped}\s*([\uff0c,])\s*", "", text)
        text = re.sub(rf"([\uff0c,])\s*{escaped}\s*$", r"\1", text)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\uff0c\uff0c+", "\uff0c", text)
    text = re.sub(r",,+", ",", text)
    return text.strip()


def build_brattish_taunt(seed_text: str = ""):
    normalized = collapse_text(seed_text)
    if not BRATTY_TAUNT_VARIANTS:
        return ""
    if not normalized:
        return BRATTY_TAUNT_VARIANTS[0]
    digest = hashlib.sha256(normalized.encode("utf-8")).digest()
    return BRATTY_TAUNT_VARIANTS[digest[0] % len(BRATTY_TAUNT_VARIANTS)]


def apply_brattish_tone_to_answer(answer: str, *, seed_text: str = ""):
    text = str(answer or "").strip()
    if not text:
        return build_brattish_taunt(seed_text)
    collapsed = collapse_text(text)
    if any(marker in collapsed for marker in BRATTY_MARKERS):
        return text
    taunt = build_brattish_taunt(f"{seed_text}\n{text}")
    if not taunt:
        return text
    separator = "\n\n" if "\n" in text else " "
    return f"{text.rstrip()}{separator}{taunt}"


def strip_markdown(value):
    text = str(value or "")
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_~>-]", " ", text)
    return collapse_text(text)


def split_markdown_sections(title: str, content_md: str, *, max_chars: int = 900):
    title = collapse_text(title) or "未命名内容"
    sections = []
    current_title = title
    current_lines = []

    def flush():
        text = strip_markdown("\n".join(current_lines))
        if not text:
            return
        for index in range(0, len(text), max_chars):
            chunk = text[index : index + max_chars].strip()
            if chunk:
                sections.append((current_title, chunk))

    for raw_line in str(content_md or "").splitlines():
        heading_match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", raw_line)
        if heading_match:
            flush()
            current_title = f"{title} / {collapse_text(heading_match.group(1))}"
            current_lines = []
            continue
        current_lines.append(raw_line)

    flush()
    return sections or [(title, strip_markdown(content_md)[:max_chars])]


def normalize_markdown_anchor_text(text: str):
    return re.sub(r"\s+", "-", re.sub(r"[^\w\u4e00-\u9fa5\s-]", "", collapse_text(text).lower())).strip()[:64]


def split_markdown_sections_with_anchors(title: str, content_md: str, *, max_chars: int = 900):
    title = collapse_text(title) or "未命名内容"
    sections = []
    current_title = title
    current_anchor = ""
    current_lines = []
    anchor_counts = {}

    def flush():
        text = strip_markdown("\n".join(current_lines))
        if not text:
            return
        for index in range(0, len(text), max_chars):
            chunk = text[index : index + max_chars].strip()
            if chunk:
                sections.append((current_title, chunk, current_anchor))

    def build_anchor(heading_text: str):
        base = normalize_markdown_anchor_text(strip_markdown(heading_text)) or "section"
        count = anchor_counts.get(base, 0) + 1
        anchor_counts[base] = count
        return base if count == 1 else f"{base}-{count}"

    for raw_line in str(content_md or "").splitlines():
        heading_match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", raw_line)
        if heading_match:
            heading_text = collapse_text(heading_match.group(1))
            flush()
            current_title = f"{title} / {heading_text}"
            current_anchor = build_anchor(heading_text)
            current_lines = []
            continue
        current_lines.append(raw_line)

    flush()
    return sections or [(title, strip_markdown(content_md)[:max_chars], "")]


def append_source_hint_to_answer(answer: str, sources):
    text = str(answer or "").strip()
    if not text or not sources:
        return text
    hint = "下面的小来源签点一下就能跳到对应章节，师兄别又在站里迷路啦。"
    if hint in text or "来源签" in text or "对应章节" in text:
        return text
    separator = "\n\n" if "\n" in text else " "
    return f"{text.rstrip()}{separator}{hint}"


def build_public_corpus():
    cached = cache.get(PUBLIC_CORPUS_CACHE_KEY)
    if cached is not None:
        return cached

    documents = []
    now = timezone.now()
    today = timezone.localdate()

    def append_document(*, source_type, source_id, title, url, text, weight=0):
        normalized_title = collapse_text(title)
        normalized_text = collapse_text(text)
        if not normalized_text:
            return
        documents.append(
            {
                "source_type": source_type,
                "source_id": int(source_id),
                "title": normalized_title[:220],
                "url": url,
                "text": normalized_text,
                "title_norm": normalized_title.lower(),
                "search_text": f"{normalized_title} {normalized_text}".lower(),
                "weight": float(weight),
            }
        )

    for article in Article.objects.filter(status=Article.Status.PUBLISHED).select_related("category"):
        url = f"/wiki/{article.id}"
        for section_title, section_text, section_anchor in split_markdown_sections_with_anchors(article.title, article.content_md):
            append_document(
                source_type="article",
                source_id=article.id,
                title=section_title,
                url=f"{url}#{section_anchor}" if section_anchor else url,
                text=f"{article.summary} {section_text}",
                weight=24,
            )

    for announcement in Announcement.objects.active():
        append_document(
            source_type="announcement",
            source_id=announcement.id,
            title=f"站内公告 / {announcement.title}",
            url=f"/announcements?announcement={announcement.id}",
            text=announcement.content_md,
            weight=30,
        )

    for page in ExtensionPage.objects.filter(is_enabled=True, access_level=ExtensionPage.AccessLevel.PUBLIC):
        page_url = f"/extra/{page.slug}"
        for section_title, section_text in split_markdown_sections(page.title, page.content_md):
            append_document(
                source_type="page",
                source_id=page.id,
                title=section_title,
                url=page_url,
                text=f"{page.description} {section_text}",
                weight=18 if page.slug == "about" else 12,
            )

    for link in FriendlyLink.objects.filter(is_enabled=True):
        append_document(
            source_type="friendly_link",
            source_id=link.id,
            title=f"友链 / {link.name}",
            url="/friendly-links",
            text=f"{link.description} {link.url}",
            weight=8,
        )

    for notice in CompetitionNotice.objects.filter(is_visible=True):
        append_document(
            source_type="competition_notice",
            source_id=notice.id,
            title=f"赛事公告 / {notice.title}",
            url=f"/competitions?tab=notice&notice={notice.id}",
            text=f"{notice.get_series_display()} {notice.year or ''} {notice.get_stage_display()} {notice.content_md}",
            weight=22,
        )

    for entry in CompetitionScheduleEntry.objects.select_related("announcement"):
        text = f"{entry.event_date} {entry.competition_time_range} {entry.competition_type} {entry.location} {entry.qq_group}"
        if entry.announcement:
            text = f"{text} {entry.announcement.title} {entry.announcement.content_md}"
        append_document(
            source_type="competition_schedule",
            source_id=entry.id,
            title=f"赛事时刻表 / {entry.competition_type}",
            url="/competitions?tab=schedule",
            text=text,
            weight=16 if entry.event_date >= today else 8,
        )

    for link in CompetitionPracticeLink.objects.all():
        practice_text = " ".join(
            f"{item.get('label', '')} {item.get('url', '')}" for item in (link.practice_links or [])
        )
        append_document(
            source_type="practice_link",
            source_id=link.id,
            title=f"补题链接 / {link.short_name}",
            url="/competitions?tab=practice",
            text=(
                f"{link.year} {link.get_series_display()} {link.get_stage_display()} "
                f"{link.short_name} {link.official_name} {link.organizer} "
                f"{link.practice_links_note} {link.source_section} {practice_text}"
            ),
            weight=18,
        )

    calendar_window_start = now - timedelta(days=30)
    calendar_window_end = now + timedelta(days=180)
    for event in CompetitionCalendarEvent.objects.filter(
        end_time__gte=calendar_window_start,
        start_time__lte=calendar_window_end,
    ):
        append_document(
            source_type="calendar_event",
            source_id=event.id,
            title=f"比赛日历 / {event.title}",
            url="/competitions?tab=calendar",
            text=(
                f"{event.get_source_site_display()} {event.title} {event.organizer} "
                f"{timezone.localtime(event.start_time).strftime('%Y-%m-%d %H:%M')} "
                f"{timezone.localtime(event.end_time).strftime('%Y-%m-%d %H:%M')} {event.url}"
            ),
            weight=14 if event.end_time >= now else 6,
        )

    for entry in TrickEntry.objects.filter(status=TrickEntry.Status.APPROVED).prefetch_related("terms"):
        term_text = " ".join(term.name for term in entry.terms.all())
        trick_text = f"{entry.title} {term_text} {entry.content_md}"
        for section_title, section_text in split_markdown_sections(entry.title, entry.content_md):
            append_document(
                source_type="trick",
                source_id=entry.id,
                title=f"Trick / {section_title}",
                url="/competitions?tab=tricks",
                text=f"{term_text} {section_text} {trick_text}",
                weight=26,
            )

    for section in CompetitionZoneSection.objects.filter(is_visible=True).select_related("page"):
        target_label = section.get_builtin_view_display() if section.target_type == CompetitionZoneSection.TargetType.BUILTIN else (
            section.page.title if section.page else "自定义页面"
        )
        append_document(
            source_type="competition_zone_section",
            source_id=section.id,
            title=f"赛事专区 / {section.title}",
            url=f"/competitions?tab={section.key}",
            text=f"{section.title} {section.key} {target_label}",
            weight=10,
        )

    for question in Question.objects.filter(status__in=[Question.Status.OPEN, Question.Status.CLOSED]).select_related("author"):
        append_document(
            source_type="question",
            source_id=question.id,
            title=f"问答 / {question.title}",
            url=f"/questions?question={question.id}",
            text=question.content_md,
            weight=16,
        )

    visible_answers = Answer.objects.filter(
        status=Answer.Status.VISIBLE,
        question__status__in=[Question.Status.OPEN, Question.Status.CLOSED],
    ).select_related("question", "author")
    for answer in visible_answers:
        append_document(
            source_type="answer",
            source_id=answer.id,
            title=f"问答回答 / {answer.question.title}",
            url=f"/questions?question={answer.question_id}",
            text=answer.content_md,
            weight=14 if answer.is_accepted else 9,
        )

    cache.set(PUBLIC_CORPUS_CACHE_KEY, documents, PUBLIC_CORPUS_TTL_SECONDS)
    return documents


def clear_public_corpus_cache():
    cache.delete(PUBLIC_CORPUS_CACHE_KEY)


def extract_query_tokens(query: str):
    normalized = collapse_text(query).lower()
    if not normalized:
        return []

    seen = set()
    tokens = []

    def push(value):
        token = collapse_text(value).lower()
        if len(token) < 2 or token in seen:
            return
        seen.add(token)
        tokens.append(token)

    push(normalized)
    for item in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", normalized):
        if re.fullmatch(r"[a-z0-9]+", item) and len(item) < 2:
            continue
        push(item)
        if re.fullmatch(r"[\u4e00-\u9fff]+", item) and len(item) > 4:
            for size in (4, 3, 2):
                for index in range(0, len(item) - size + 1):
                    push(item[index : index + size])

    return tokens[:24]


def build_excerpt(text: str, tokens):
    normalized = collapse_text(text)
    if len(normalized) <= 240:
        return normalized
    lowered = normalized.lower()
    best_index = 0
    for token in tokens:
        index = lowered.find(token)
        if index >= 0:
            best_index = index
            break
    start = max(0, best_index - 70)
    end = min(len(normalized), start + 240)
    excerpt = normalized[start:end].strip()
    if start > 0:
        excerpt = f"...{excerpt}"
    if end < len(normalized):
        excerpt = f"{excerpt}..."
    return excerpt


def shorten_text(value: str, max_chars: int = 28):
    text = collapse_text(value)
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1].rstrip()}…"


def contains_any_keyword(text: str, keywords):
    return any(keyword in text for keyword in keywords)


def is_recent_competition_query(query: str):
    normalized = collapse_text(query).lower()
    if not normalized:
        return False
    if contains_any_keyword(normalized, RECENT_COMPETITION_TRIGGER_PHRASES):
        return True
    return (
        contains_any_keyword(normalized, ("比赛", "赛事"))
        and contains_any_keyword(normalized, ("最近", "近期", "这周", "本周", "接下来"))
    )


def wants_online_competitions(query: str):
    normalized = collapse_text(query).lower()
    has_online = contains_any_keyword(normalized, ONLINE_COMPETITION_KEYWORDS)
    has_offline = contains_any_keyword(normalized, OFFLINE_COMPETITION_KEYWORDS)
    if has_online and not has_offline:
        return True
    if has_offline and not has_online:
        return False
    return True


def wants_offline_competitions(query: str):
    normalized = collapse_text(query).lower()
    has_online = contains_any_keyword(normalized, ONLINE_COMPETITION_KEYWORDS)
    has_offline = contains_any_keyword(normalized, OFFLINE_COMPETITION_KEYWORDS)
    if has_offline and not has_online:
        return True
    if has_online and not has_offline:
        return False
    return True


def build_source_reference(*, source_type: str, source_id: int, title: str, url: str, excerpt: str):
    return {
        "source_type": source_type,
        "source_id": source_id,
        "title": title,
        "url": url,
        "excerpt": excerpt,
    }


TRICK_QUERY_KEYWORDS = (
    "trick",
    "tricks",
    "\u6280\u5de7",
    "\u6280\u5de7\u6c47\u603b",
    "\u6280\u5de7\u9875",
    "\u7b97\u6cd5\u6280\u5de7",
    "\u5c0f\u6280\u5de7",
)
TRICK_GENERIC_TOKENS = {
    "trick",
    "tricks",
    "\u6280\u5de7",
    "\u6c47\u603b",
    "\u603b\u7ed3",
    "\u68c0\u7d22",
    "\u641c\u7d22",
    "\u67e5\u627e",
    "\u76f8\u5173",
    "\u5bf9\u5e94",
    "\u4e00\u4e9b",
    "\u54ea\u4e9b",
    "\u6709\u54ea\u4e9b",
    "\u7ed9\u6211",
    "\u5e2e\u6211",
    "\u7ad9\u5185",
    "\u9875\u9762",
    "\u8d5b\u4e8b",
    "\u4e13\u533a",
}


def is_trick_query(query: str, *, current_path: str = "", current_title: str = ""):
    normalized = collapse_text(f"{query} {current_title}").lower()
    path = normalize_assistant_path(current_path).lower()
    if "tab=tricks" in path or "/extra/tricks" in path:
        return True
    return contains_any_keyword(normalized, TRICK_QUERY_KEYWORDS)


def extract_trick_query_tokens(query: str):
    tokens = expand_search_tokens(query, extract_query_tokens(query))
    useful = []
    for token in tokens:
        normalized = collapse_text(token).lower()
        if not normalized or normalized in TRICK_GENERIC_TOKENS:
            continue
        if len(normalized) < 2:
            continue
        if normalized not in useful:
            useful.append(normalized)
    return useful[:10]


def format_trick_item(entry: TrickEntry):
    title = shorten_text(entry.title, 32)
    summary = shorten_text(strip_markdown(entry.content_md), 70)
    if summary and summary != title:
        return f"- {title}\uff1a{summary}"
    return f"- {title}"


def build_trick_digest(query: str, *, current_path: str = "", current_title: str = ""):
    if not is_trick_query(query, current_path=current_path, current_title=current_title):
        return None

    entries = list(
        TrickEntry.objects.filter(status=TrickEntry.Status.APPROVED)
        .prefetch_related("terms")
        .order_by("-updated_at", "-id")[:300]
    )
    if not entries:
        return {
            "answer": "\u5e08\u5144\uff0c\u7ad9\u5185\u6682\u65f6\u8fd8\u6ca1\u6709\u5df2\u901a\u8fc7\u7684 trick \u6280\u5de7\u3002",
            "sources": [
                build_source_reference(
                    source_type="trick_overview",
                    source_id=0,
                    title="\u8d5b\u4e8b\u4e13\u533a / trick\u6280\u5de7",
                    url="/competitions?tab=tricks",
                    excerpt="\u67e5\u770b trick \u6280\u5de7\u6c47\u603b",
                )
            ],
            "model": "builtin-trick-digest",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    tokens = extract_trick_query_tokens(query)
    scored = []
    for entry in entries:
        term_names = [term.name for term in entry.terms.all()]
        title = collapse_text(entry.title)
        body = strip_markdown(entry.content_md)
        haystack = collapse_text(f"{title} {' '.join(term_names)} {body}").lower()
        score = 0.0
        if not tokens:
            score = 1.0
        for token in tokens:
            if token in title.lower():
                score += 80
            if any(token in collapse_text(term).lower() for term in term_names):
                score += 70
            if token in haystack:
                score += min(36, max(8, len(token) * 4))
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda item: (-item[0], -item[1].updated_at.timestamp(), -item[1].id))
    selected = [entry for _, entry in scored[:5]]
    if not selected:
        selected = entries[:5]

    if tokens:
        answer_lines = ["\u5e08\u5144\uff0c\u548c\u4f60\u95ee\u7684\u5185\u5bb9\u6700\u50cf\u7684 trick \u5148\u770b\u8fd9\u51e0\u6761\uff1a"]
    else:
        answer_lines = ["\u5e08\u5144\uff0ctrick \u9875\u91cc\u5df2\u6536\u5f55\u7684\u6280\u5de7\u53ef\u4ee5\u5148\u770b\u8fd9\u51e0\u6761\uff1a"]
    answer_lines.extend(format_trick_item(entry) for entry in selected[:5])

    sources = []
    for entry in selected[:5]:
        terms = " ".join(term.name for term in entry.terms.all())
        sources.append(
            build_source_reference(
                source_type="trick",
                source_id=entry.id,
                title=f"\u8d5b\u4e8b\u4e13\u533a / trick\u6280\u5de7 / {entry.title}",
                url="/competitions?tab=tricks",
                excerpt=build_excerpt(f"{entry.title} {terms} {strip_markdown(entry.content_md)}", tokens or [entry.title]),
            )
        )

    return {
        "answer": "\n".join(answer_lines),
        "sources": sources,
        "model": "builtin-trick-digest",
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def format_recent_online_event(event: CompetitionCalendarEvent):
    start_at = timezone.localtime(event.start_time)
    site_name = collapse_text(event.get_source_site_display())
    title = shorten_text(event.title, 24)
    if site_name and site_name.lower() not in title.lower():
        title = f"{site_name} | {title}"
    return f"- {start_at.strftime('%m-%d %H:%M')} {title}"


def format_recent_offline_event(entry: CompetitionScheduleEntry):
    title = shorten_text(entry.competition_type, 22)
    location = shorten_text(entry.location, 8)
    suffix = f"（{location}）" if location else ""
    return f"- {entry.event_date.strftime('%m-%d')} {title}{suffix}"


def build_recent_competition_digest(query: str):
    if not is_recent_competition_query(query):
        return None

    now = timezone.now()
    today = timezone.localdate()
    online_window_end = now + timedelta(days=60)
    offline_window_end = today + timedelta(days=180)
    include_online = wants_online_competitions(query)
    include_offline = wants_offline_competitions(query)

    online_events = []
    offline_events = []

    if include_online:
        online_events = list(
            CompetitionCalendarEvent.objects.filter(
                end_time__gte=now,
                start_time__lte=online_window_end,
            )
            .order_by("start_time", "source_site", "source_id")[:2]
        )

    if include_offline:
        offline_events = list(
            CompetitionScheduleEntry.objects.filter(
                event_date__gte=today,
                event_date__lte=offline_window_end,
            )
            .order_by("event_date", "id")[:2]
        )

    if not online_events and not offline_events:
        if include_online and not include_offline:
            answer = "站内当前没有可用的近期线上比赛数据。"
        elif include_offline and not include_online:
            answer = "站内当前没有可用的近期线下比赛数据。"
        else:
            answer = "站内当前没有可用的近期比赛数据。"
        return {
            "answer": answer,
            "sources": [],
            "model": "builtin-competition-brief",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    answer_lines = ["最近可关注："]
    sources = []

    if include_online:
        answer_lines.append("线上")
        if online_events:
            answer_lines.extend(format_recent_online_event(event) for event in online_events)
            sources.append(
                build_source_reference(
                    source_type="calendar_overview",
                    source_id=0,
                    title="比赛日历表",
                    url="/competitions?tab=calendar",
                    excerpt="查看近期线上比赛日程",
                )
            )
        else:
            answer_lines.append("- 暂无近期数据")

    if include_offline:
        answer_lines.append("线下")
        if offline_events:
            answer_lines.extend(format_recent_offline_event(entry) for entry in offline_events)
            sources.append(
                build_source_reference(
                    source_type="schedule_overview",
                    source_id=0,
                    title="赛事时刻表",
                    url="/competitions?tab=schedule",
                    excerpt="查看近期线下比赛日程",
                )
            )
        else:
            answer_lines.append("- 暂无近期数据")

    return {
        "answer": "\n".join(answer_lines),
        "sources": sources,
        "model": "builtin-competition-brief",
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def format_recent_offline_event(entry: CompetitionScheduleEntry):
    title = shorten_text(entry.competition_type, 22)
    location = shorten_text(entry.location, 8)
    suffix = f" ({location})" if location else ""
    return f"- {entry.event_date.strftime('%m-%d')} {title}{suffix}"


def shorten_text(value: str, max_chars: int = 28):
    text = collapse_text(value)
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    return f"{text[: max_chars - 3].rstrip()}..."


def contains_any_keyword(text: str, keywords):
    normalized = collapse_text(text).lower()
    return any(collapse_text(keyword).lower() in normalized for keyword in keywords if keyword)


def is_recent_competition_query(query: str):
    normalized = collapse_text(query).lower()
    if not normalized:
        return False
    trigger_phrases = (
        "\u6700\u8fd1\u6709\u54ea\u4e9b\u6bd4\u8d5b",
        "\u8fd1\u671f\u6709\u54ea\u4e9b\u6bd4\u8d5b",
        "\u6700\u8fd1\u6bd4\u8d5b",
        "\u8fd1\u671f\u6bd4\u8d5b",
        "\u6700\u8fd1\u8d5b\u4e8b",
        "\u8fd1\u671f\u8d5b\u4e8b",
        "\u6709\u54ea\u4e9b\u6bd4\u8d5b",
        "\u6700\u8fd1\u6709\u4ec0\u4e48\u6bd4\u8d5b",
        "\u8fd1\u671f\u6709\u4ec0\u4e48\u6bd4\u8d5b",
        "\u6700\u8fd1\u6709\u54ea\u4e9b\u7ebf\u4e0a\u6bd4\u8d5b",
        "\u6700\u8fd1\u6709\u54ea\u4e9b\u7ebf\u4e0b\u6bd4\u8d5b",
        "recent contests",
        "upcoming contests",
        "recent competitions",
        "upcoming competitions",
    )
    if contains_any_keyword(normalized, trigger_phrases):
        return True
    return contains_any_keyword(
        normalized,
        ("\u6bd4\u8d5b", "\u8d5b\u4e8b", "contest", "competition"),
    ) and contains_any_keyword(
        normalized,
        (
            "\u6700\u8fd1",
            "\u8fd1\u671f",
            "\u672c\u5468",
            "\u672c\u6708",
            "\u63a5\u4e0b\u6765",
            "\u5373\u5c06",
            "recent",
            "upcoming",
            "next",
        ),
    )


def wants_online_competitions(query: str):
    normalized = collapse_text(query).lower()
    online_keywords = (
        "\u7ebf\u4e0a",
        "\u6bd4\u8d5b\u65e5\u5386",
        "\u6bd4\u8d5b\u65e5\u5386\u8868",
        "\u65e5\u5386",
        "calendar",
        "online",
        "codeforces",
        "atcoder",
        "\u725b\u5ba2",
        "\u6d1b\u8c37",
        "cf",
    )
    offline_keywords = (
        "\u7ebf\u4e0b",
        "\u73b0\u573a",
        "\u8d5b\u4e8b\u65f6\u523b\u8868",
        "\u65f6\u523b\u8868",
        "\u9080\u8bf7\u8d5b",
        "\u533a\u57df\u8d5b",
        "\u7701\u8d5b",
        "offline",
        "onsite",
        "schedule",
    )
    has_online = contains_any_keyword(normalized, online_keywords)
    has_offline = contains_any_keyword(normalized, offline_keywords)
    if has_online and not has_offline:
        return True
    if has_offline and not has_online:
        return False
    return True


def wants_offline_competitions(query: str):
    normalized = collapse_text(query).lower()
    online_keywords = (
        "\u7ebf\u4e0a",
        "\u6bd4\u8d5b\u65e5\u5386",
        "\u6bd4\u8d5b\u65e5\u5386\u8868",
        "\u65e5\u5386",
        "calendar",
        "online",
        "codeforces",
        "atcoder",
        "\u725b\u5ba2",
        "\u6d1b\u8c37",
        "cf",
    )
    offline_keywords = (
        "\u7ebf\u4e0b",
        "\u73b0\u573a",
        "\u8d5b\u4e8b\u65f6\u523b\u8868",
        "\u65f6\u523b\u8868",
        "\u9080\u8bf7\u8d5b",
        "\u533a\u57df\u8d5b",
        "\u7701\u8d5b",
        "offline",
        "onsite",
        "schedule",
    )
    has_online = contains_any_keyword(normalized, online_keywords)
    has_offline = contains_any_keyword(normalized, offline_keywords)
    if has_offline and not has_online:
        return True
    if has_online and not has_offline:
        return False
    return True


def format_recent_online_event(event: CompetitionCalendarEvent):
    now = timezone.now()
    start_at = timezone.localtime(event.start_time)
    end_at = timezone.localtime(event.end_time)
    site_name = collapse_text(event.get_source_site_display())
    title = shorten_text(event.title, 26)
    if site_name and site_name.lower() not in title.lower():
        title = f"{site_name} | {title}"
    if event.start_time <= now <= event.end_time:
        return f"- 进行中 {title}（至 {end_at.strftime('%m-%d %H:%M')}）"
    return f"- {start_at.strftime('%m-%d %H:%M')} {title}"


def format_recent_offline_event(entry: CompetitionScheduleEntry):
    title = shorten_text(entry.competition_type, 24)
    location = shorten_text(entry.location, 10)
    suffix = f" ({location})" if location else ""
    return f"- {entry.event_date.strftime('%m-%d')} {title}{suffix}"


def build_recent_competition_digest(query: str):
    if not is_recent_competition_query(query):
        return None

    now = timezone.now()
    today = timezone.localdate()
    include_online = wants_online_competitions(query)
    include_offline = wants_offline_competitions(query)

    online_events = []
    offline_events = []

    if include_online:
        online_events = list(
            CompetitionCalendarEvent.objects.filter(end_time__gte=now)
            .order_by("start_time", "source_site", "source_id")[:2]
        )

    if include_offline:
        offline_events = list(
            CompetitionScheduleEntry.objects.filter(event_date__gte=today)
            .order_by("event_date", "id")[:2]
        )

    if not online_events and not offline_events:
        if include_online and not include_offline:
            answer = "\u5e08\u5144\uff0c\u7ad9\u5185\u73b0\u5728\u8fd8\u6ca1\u6709\u53ef\u7528\u7684\u8fd1\u671f\u7ebf\u4e0a\u6bd4\u8d5b\u6570\u636e\uff0c\u4f60\u7a0d\u540e\u518d\u770b\u4e5f\u4e0d\u8fdf\u3002"
        elif include_offline and not include_online:
            answer = "\u5e08\u5144\uff0c\u7ad9\u5185\u73b0\u5728\u8fd8\u6ca1\u6709\u53ef\u7528\u7684\u8fd1\u671f\u7ebf\u4e0b\u6bd4\u8d5b\u6570\u636e\uff0c\u522b\u7740\u6025\uff0c\u6709\u4e86\u6211\u4f1a\u5148\u7ed9\u4f60\u7ffb\u51fa\u6765\u3002"
        else:
            answer = "\u5e08\u5144\uff0c\u7ad9\u5185\u73b0\u5728\u8fd8\u6ca1\u6709\u53ef\u7528\u7684\u8fd1\u671f\u6bd4\u8d5b\u6570\u636e\uff0c\u4f60\u6362\u4e2a\u66f4\u5177\u4f53\u7684\u95ee\u6cd5\u4e5f\u884c\u3002"
        return {
            "answer": answer,
            "sources": [],
            "model": "builtin-competition-brief",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    answer_lines = ["\u5e08\u5144\uff0c\u6700\u8fd1\u5148\u76ef\u8fd9\u51e0\u573a\u5c31\u884c\uff0c\u53ef\u522b\u53c8\u9519\u8fc7\u4e86\u3002"]
    sources = []

    if include_online:
        answer_lines.append("\u7ebf\u4e0a")
        if online_events:
            answer_lines.extend(format_recent_online_event(event) for event in online_events)
            sources.append(
                build_source_reference(
                    source_type="calendar_overview",
                    source_id=0,
                    title="\u6bd4\u8d5b\u65e5\u5386\u8868",
                    url="/competitions?tab=calendar",
                    excerpt="\u67e5\u770b\u8fd1\u671f\u7ebf\u4e0a\u6bd4\u8d5b\u65e5\u7a0b",
                )
            )
        else:
            answer_lines.append("- \u6682\u65e0\u8fd1\u671f\u6570\u636e")

    if include_offline:
        answer_lines.append("\u7ebf\u4e0b")
        if offline_events:
            answer_lines.extend(format_recent_offline_event(entry) for entry in offline_events)
            sources.append(
                build_source_reference(
                    source_type="schedule_overview",
                    source_id=0,
                    title="\u8d5b\u4e8b\u65f6\u523b\u8868",
                    url="/competitions?tab=schedule",
                    excerpt="\u67e5\u770b\u8fd1\u671f\u7ebf\u4e0b\u6bd4\u8d5b\u65e5\u7a0b",
                )
            )
        else:
            answer_lines.append("- \u6682\u65e0\u8fd1\u671f\u6570\u636e")

    return {
        "answer": "\n".join(answer_lines),
        "sources": sources,
        "model": "builtin-competition-brief",
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def normalize_assistant_path(value: str):
    raw = collapse_text(value)
    if not raw:
        return ""
    parsed = urlsplit(raw)
    if parsed.scheme or parsed.netloc:
        path = parsed.path or "/"
        query = parsed.query
    else:
        if "?" in raw:
            path, query = raw.split("?", 1)
        else:
            path, query = raw, ""
    path = f"/{str(path or '').lstrip('/')}" if path else "/"
    return f"{path}?{query}" if query else path


def expand_search_tokens(query: str, tokens):
    normalized = collapse_text(query).lower()
    expanded = []
    seen = set()

    def push(value):
        token = collapse_text(value).lower()
        if len(token) < 2 or token in seen:
            return
        seen.add(token)
        expanded.append(token)

    for token in tokens or []:
        push(token)

    if contains_any_keyword(normalized, ("题意", "题面", "题目描述", "题目")):
        for token in ("题意", "题面", "题目", "描述"):
            push(token)

    if contains_any_keyword(normalized, ("原题", "题源", "出处", "来源", "相似题", "原题机", "找原题")):
        for token in ("原题", "题源", "出处", "来源", "相似题", "原题机", "yuantiji"):
            push(token)

    if contains_any_keyword(normalized, ("网站", "站点", "平台", "工具", "网页")):
        for token in ("网站", "站点", "平台", "工具", "关键网站"):
            push(token)

    if contains_any_keyword(normalized, ("根据题意找到原题", "根据题面找到原题", "通过题意找原题", "通过题面找原题")):
        for token in ("原题机", "yuantiji", "题面相似", "题目出处"):
            push(token)

    return expanded[:32]


def is_original_problem_lookup_query(query: str):
    normalized = collapse_text(query).lower()
    if not normalized:
        return False
    has_source_intent = contains_any_keyword(normalized, ("原题", "题源", "出处", "来源", "相似题", "原题机"))
    has_statement_intent = contains_any_keyword(normalized, ("题意", "题面", "题目", "描述"))
    has_site_intent = contains_any_keyword(normalized, ("网站", "站点", "平台", "工具", "网页", "哪里"))
    return (
        (has_source_intent and has_site_intent)
        or ("找到原题" in normalized and (has_statement_intent or has_site_intent))
        or ("原题网站" in normalized)
        or ("原题机" in normalized)
    )


def is_competition_format_query(query: str):
    normalized = collapse_text(query).lower()
    if not normalized:
        return False
    if "赛制" in normalized:
        return True
    if contains_any_keyword(normalized, ("oi还是acm", "acm还是oi", "oi 还是 acm", "acm 还是 oi")):
        return True
    return (
        contains_any_keyword(normalized, ("oi", "acm", "ioi", "罚时", "部分分", "判分", "封榜"))
        and contains_any_keyword(normalized, ("蓝桥杯", "icpc", "ccpc", "天梯赛", "比赛", "赛事"))
    )


def detect_competition_format_label(text: str):
    normalized = collapse_text(text).lower()
    if not normalized:
        return ""

    format_patterns = (
        ("OI 赛制", ("oi赛制", "oi 赛制")),
        ("ACM 赛制", ("acm赛制", "acm 赛制", "icpc赛制", "icpc 赛制", "acm/icpc")),
        ("IOI 赛制", ("ioi赛制", "ioi 赛制")),
    )
    for label, patterns in format_patterns:
        if any(pattern in normalized for pattern in patterns):
            return label
    return ""


def extract_competition_subject(*values: str):
    generic_titles = {
        "比赛介绍",
        "主页",
        "首页",
        "个人主页",
        "报名参赛",
        "规则",
        "赛制",
        "algowiki",
        "欢迎来到 algowiki!",
        "欢迎来到 algowiki",
        "关于 algowiki",
    }

    for raw in values:
        text = collapse_text(raw)
        if not text:
            continue
        parts = re.split(r"\s*/\s*", text)
        for part in parts:
            candidate = re.split(r"[｜|]", part)[-1].strip()
            candidate = re.sub(r"(是什么|什么|采用|属于|赛制|oi|acm|ioi|？|\?)", "", candidate, flags=re.IGNORECASE)
            candidate = collapse_text(candidate)
            if len(candidate) >= 2 and candidate not in generic_titles:
                return candidate
    return "该比赛"


def extract_competition_format_details(text: str, format_label: str):
    normalized = collapse_text(text).lower()
    details = []

    def push(value: str):
        if value and value not in details:
            details.append(value)

    if any(keyword in normalized for keyword in ("最后一次提交", "最后一次提交判分")):
        push("按最后一次提交判分")
    if "部分分" in normalized:
        push("支持部分分")
    if any(keyword in normalized for keyword in ("赛后统一公布", "赛后统一公")):
        push("分数赛后统一公布")
    if format_label == "ACM 赛制":
        if "罚时" in normalized:
            push("错误提交会产生罚时")
        if any(keyword in normalized for keyword in ("实时榜单", "实时排名", "现场榜单")):
            push("通常按实时榜单排名")

    return details[:3]


def build_competition_format_digest(query: str, *, current_path: str = "", current_title: str = ""):
    if not is_competition_format_query(query):
        return None

    corpus = build_public_corpus()
    tokens = expand_search_tokens(query, extract_query_tokens(query))
    if not tokens:
        return None

    normalized_current_path = normalize_assistant_path(current_path)
    current_title_tokens = expand_search_tokens(current_title, extract_query_tokens(current_title))[:12]
    best_match = None

    for item in corpus:
        title = item["title_norm"]
        text = item["search_text"]
        score = item.get("weight", 0.0)
        item_url = normalize_assistant_path(item.get("url", ""))
        format_label = detect_competition_format_label(text)

        full_query = tokens[0]
        if full_query in title:
            score += 180
        elif full_query in text:
            score += 110

        for token in tokens[1:]:
            base_weight = min(28, max(6, len(token) * 4))
            if token in title:
                score += base_weight * 2.4
            if token in text:
                score += base_weight * 1.2

        if normalized_current_path and item_url:
            current_path_only = normalized_current_path.split("?", 1)[0]
            item_path_only = item_url.split("?", 1)[0]
            if item_url == normalized_current_path:
                score += 320
            elif item_path_only == current_path_only:
                score += 180
            elif current_path_only.startswith(item_path_only) or item_path_only.startswith(current_path_only):
                score += 100

        for token in current_title_tokens:
            if token in title:
                score += 28
            elif token in text:
                score += 12

        if "赛制" in title:
            score += 40
        if any(keyword in text for keyword in ("赛制", "判分", "部分分", "罚时", "封榜", "最后一次提交")):
            score += 70
        if format_label:
            score += 200

        if score < 80 or not format_label:
            continue

        candidate = {
            "source_type": item["source_type"],
            "source_id": item["source_id"],
            "title": item["title"],
            "url": item["url"],
            "text": item["text"],
            "format_label": format_label,
            "score": round(score, 2),
        }
        if best_match is None or candidate["score"] > best_match["score"]:
            best_match = candidate

    if not best_match:
        return None

    subject = extract_competition_subject(best_match["title"], query, current_title)
    detail_points = extract_competition_format_details(best_match["text"], best_match["format_label"])
    answer = f"师兄，{subject}采用 {best_match['format_label']}，这点可别记混了。"
    if detail_points:
        answer = f"{answer} 站内写的是{ '，'.join(detail_points) }。"

    excerpt_tokens = [
        best_match["format_label"].lower(),
        "赛制",
        "最后一次提交",
        "部分分",
        "罚时",
        "封榜",
    ]
    sources = [
        build_source_reference(
            source_type=best_match["source_type"],
            source_id=best_match["source_id"],
            title=best_match["title"],
            url=best_match["url"],
            excerpt=build_excerpt(best_match["text"], excerpt_tokens),
        )
    ]
    return {
        "answer": answer,
        "sources": sources,
        "model": "builtin-competition-format",
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def build_original_problem_site_digest(query: str, *, current_path: str = "", current_title: str = ""):
    if not is_original_problem_lookup_query(query):
        return None

    sources = search_public_corpus(
        query,
        limit=4,
        current_path=current_path,
        current_title=current_title,
    )
    for source in sources:
        haystack = collapse_text(f"{source.get('title', '')} {source.get('excerpt', '')}").lower()
        if any(keyword in haystack for keyword in ("yuantiji", "原题机", "题目出处", "题面相似")):
            return {
                "answer": "师兄，可以看 yuantiji.ac（原题机）。把题面贴进去，就能找题目出处或相似题，省得你到处翻了。",
                "sources": [source],
                "model": "builtin-site-match",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }
    return None


def search_public_corpus(query: str, *, limit: int = 6, current_path: str = "", current_title: str = ""):
    corpus = build_public_corpus()
    tokens = expand_search_tokens(query, extract_query_tokens(query))
    if not tokens:
        return []

    normalized_current_path = normalize_assistant_path(current_path)
    current_title_tokens = expand_search_tokens(current_title, extract_query_tokens(current_title))[:12]
    original_problem_lookup = is_original_problem_lookup_query(query)

    results = []
    for item in corpus:
        title = item["title_norm"]
        text = item["search_text"]
        base_weight = item.get("weight", 0.0)
        score = 0.0
        has_signal = False
        item_url = normalize_assistant_path(item.get("url", ""))
        full_query = tokens[0]
        if full_query in title:
            score += 160
            has_signal = True
        elif full_query in text:
            score += 90
            has_signal = True

        for token in tokens[1:]:
            base_weight = min(28, max(6, len(token) * 4))
            if token in title:
                score += base_weight * 2.2
                has_signal = True
            if token in text:
                score += base_weight
                has_signal = True

        if normalized_current_path and item_url:
            current_path_only = normalized_current_path.split("?", 1)[0]
            item_path_only = item_url.split("?", 1)[0]
            if item_url == normalized_current_path:
                score += 260
                has_signal = True
            elif item_path_only == current_path_only:
                score += 140
                has_signal = True
            elif current_path_only.startswith(item_path_only) or item_path_only.startswith(current_path_only):
                score += 80
                has_signal = True

        for token in current_title_tokens:
            if token in title:
                score += 20
                has_signal = True
            elif token in text:
                score += 8
                has_signal = True

        if original_problem_lookup:
            if any(keyword in title or keyword in text for keyword in ("yuantiji", "原题机", "题目出处", "题面相似")):
                score += 220
                has_signal = True
            if "关键网站" in title:
                score += 36

        if not has_signal:
            continue

        score += base_weight
        if score < 18:
            continue

        results.append(
            {
                "source_type": item["source_type"],
                "source_id": item["source_id"],
                "title": item["title"],
                "url": item["url"],
                "excerpt": build_excerpt(item["text"], tokens),
                "score": round(score, 2),
            }
        )

    results.sort(key=lambda item: (-item["score"], item["title"]))
    deduped = []
    seen = set()
    for item in results:
        key = (item["source_type"], item["source_id"], item["title"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def build_chat_messages_compact(*, config: AssistantProviderConfig, message: str, history, sources):
    system_prompt = build_assistant_system_prompt(config.system_prompt)
    source_blocks = []
    for index, item in enumerate(sources, start=1):
        excerpt = collapse_text(item.get("excerpt", ""))[:MAX_SOURCE_CONTEXT_CHARS]
        source_blocks.append(
            f"[Source {index}] Title: {item['title']}\nURL: {item['url']}\nExcerpt: {excerpt}"
        )
    context_block = "\n\n".join(source_blocks)

    messages = [{"role": "system", "content": system_prompt}]
    if context_block:
        messages.append(
            {
                "role": "system",
                "content": (
                    "The following content was retrieved from public AlgoWiki pages. "
                    "Answer using only this material.\n\n"
                    f"{context_block}"
                ),
            }
        )

    normalized_history = []
    for item in history or []:
        role = str((item or {}).get("role", "")).strip().lower()
        content = collapse_text((item or {}).get("content", ""))
        if role not in {"user", "assistant"} or not content:
            continue
        normalized_history.append({"role": role, "content": content[:MAX_HISTORY_CHARS]})
    normalized_history = normalized_history[-MAX_HISTORY_MESSAGES:]
    messages.extend(normalized_history)
    messages.append({"role": "user", "content": collapse_text(message)[:MAX_HISTORY_CHARS]})
    return messages


def build_chat_messages(*, config: AssistantProviderConfig, message: str, history, sources):
    system_prompt = collapse_text(config.system_prompt) or (
        "你是 AlgoWiki 站内助手。你只能依据提供给你的站内公开内容作答。"
        "如果证据不足，请明确说当前站内没有足够信息，不要编造。"
        "回答尽量使用简洁清晰的中文，可以使用 Markdown 列表，但不要捏造链接或规则。"
    )
    source_blocks = []
    for index, item in enumerate(sources, start=1):
        excerpt = item["excerpt"][:MAX_SOURCE_CONTEXT_CHARS]
        source_blocks.append(
            f"[来源 {index}] 标题: {item['title']}\n路径: {item['url']}\n内容摘要: {excerpt}"
        )
    context_block = "\n\n".join(source_blocks)

    messages = [{"role": "system", "content": system_prompt}]
    if context_block:
        messages.append(
            {
                "role": "system",
                "content": (
                    "下面是从 AlgoWiki 站内检索到的公开内容，请优先基于这些内容回答。\n\n"
                    f"{context_block}"
                ),
            }
        )

    normalized_history = []
    for item in history or []:
        role = str((item or {}).get("role", "")).strip().lower()
        content = collapse_text((item or {}).get("content", ""))
        if role not in {"user", "assistant"} or not content:
            continue
        normalized_history.append({"role": role, "content": content[:MAX_HISTORY_CHARS]})
    normalized_history = normalized_history[-MAX_HISTORY_MESSAGES:]
    messages.extend(normalized_history)
    messages.append({"role": "user", "content": collapse_text(message)[:MAX_HISTORY_CHARS]})
    return messages


def _extract_response_text(payload):
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content", "")
    if isinstance(content, list):
        return "\n".join(str(item.get("text", "")).strip() for item in content if isinstance(item, dict))
    return str(content or "").strip()


def invoke_assistant_completion(*, config: AssistantProviderConfig, message: str, history, sources):
    api_key = config.get_api_key()
    if not api_key:
        raise AssistantProviderError("AI assistant API key is not configured.", status_code=503)

    payload = {
        "model": config.model_name,
        "messages": build_chat_messages_compact(config=config, message=message, history=history, sources=sources),
        "temperature": float(config.temperature or 0.3),
        "max_tokens": int(config.max_output_tokens or 1024),
        "stream": False,
    }
    request = urllib.request.Request(
        f"{str(config.base_url or '').rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=max(5, int(config.request_timeout_seconds or 30))) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"detail": raw}
        message_text = payload.get("error", {}).get("message") or payload.get("detail") or "Provider request failed."
        raise AssistantProviderError(str(message_text), status_code=exc.code, payload=payload) from exc
    except urllib.error.URLError as exc:
        raise AssistantProviderError(f"Provider request failed: {exc.reason}", status_code=502) from exc

    try:
        response_payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AssistantProviderError("Provider returned invalid JSON.", status_code=502) from exc

    content = _extract_response_text(response_payload)
    usage = response_payload.get("usage") or {}
    return {
        "content": content,
        "usage": {
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        },
        "model": str(response_payload.get("model") or config.model_name or "").strip(),
    }


def get_daily_usage(config: AssistantProviderConfig, *, now=None):
    reference = now or timezone.now()
    start = timezone.make_aware(datetime.combine(timezone.localtime(reference).date(), time.min), timezone.get_current_timezone())
    queryset = AssistantInteractionLog.objects.filter(config=config, created_at__gte=start)
    request_count = queryset.count()
    token_total = sum(int(item.total_tokens or 0) for item in queryset.only("total_tokens"))
    return {
        "request_count": request_count,
        "token_total": token_total,
    }


def check_daily_limits(config: AssistantProviderConfig):
    usage = get_daily_usage(config)
    if config.daily_request_limit and usage["request_count"] >= int(config.daily_request_limit):
        raise AssistantProviderError("AI assistant daily request limit reached.", status_code=429)
    if config.daily_token_limit and usage["token_total"] >= int(config.daily_token_limit):
        raise AssistantProviderError("AI assistant daily token limit reached.", status_code=429)
    return usage


def create_interaction_log(
    *,
    request,
    config: AssistantProviderConfig | None,
    success: bool,
    prompt_chars: int,
    response_chars: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    source_count: int = 0,
    response_ms: int = 0,
    session_id: str = "",
    error_message: str = "",
):
    AssistantInteractionLog.objects.create(
        config=config,
        user=request.user if getattr(request.user, "is_authenticated", False) else None,
        session_id=str(session_id or "").strip()[:64],
        provider=getattr(config, "provider", "") or "",
        model_name=getattr(config, "model_name", "") or "",
        ip_address=get_client_ip(request),
        user_agent=str(request.META.get("HTTP_USER_AGENT", "") or "")[:255],
        prompt_chars=max(0, int(prompt_chars or 0)),
        response_chars=max(0, int(response_chars or 0)),
        prompt_tokens=max(0, int(prompt_tokens or 0)),
        completion_tokens=max(0, int(completion_tokens or 0)),
        total_tokens=max(0, int(total_tokens or 0)),
        source_count=max(0, int(source_count or 0)),
        response_ms=max(0, int(response_ms or 0)),
        success=bool(success),
        error_message=str(error_message or "")[:255],
    )
