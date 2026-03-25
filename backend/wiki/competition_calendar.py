from __future__ import annotations

import html
import http.cookiejar
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from urllib.parse import unquote, urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener
from zoneinfo import ZoneInfo

from django.utils import timezone

from .models import CompetitionCalendarEvent

LOGGER = logging.getLogger("algowiki.api")

DEFAULT_TIMEOUT_SECONDS = 20
ATCODER_TZ = ZoneInfo("Asia/Tokyo")
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

ATCODER_SECTION_PATTERN = r"<h3[^>]*>\s*{heading}\s*</h3>.*?<tbody>(.*?)</tbody>"
ATCODER_ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
ATCODER_CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
ATCODER_LINK_RE = re.compile(r'<a href="(?P<href>/contests/[^"]+)">(?P<title>.*?)</a>', re.S)
ATCODER_TIME_RE = re.compile(r"<time[^>]*>([^<]+)</time>", re.S)
NOWCODER_ITEM_RE = re.compile(r'<div[^>]+class="platform-item js-item[^"]*"[^>]+data-json="([^"]+)"', re.S)
LUOGU_INJECTION_RE = re.compile(
    r'window\._feInjection\s*=\s*JSON\.parse\(decodeURIComponent\("([^"]+)"\)\);'
)


@dataclass(slots=True)
class NormalizedCompetitionEvent:
    source_site: str
    source_id: str
    title: str
    url: str
    start_time: datetime
    end_time: datetime
    duration_seconds: int
    organizer: str = ""
    extra: dict = field(default_factory=dict)


def _request_text(url: str, *, opener=None, headers: dict | None = None) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (AlgoWiki Calendar Sync)",
            **(headers or {}),
        },
    )
    if opener is None:
        with build_opener().open(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            return response.read().decode("utf-8", errors="ignore")
    with opener.open(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", errors="ignore")


def _strip_tags(value: str) -> str:
    cleaned = re.sub(r"<[^>]+>", "", value or "")
    return re.sub(r"\s+", " ", html.unescape(cleaned)).strip()


def _parse_duration_hhmm(value: str) -> int:
    match = re.match(r"^\s*(\d+):(\d{2})\s*$", value or "")
    if not match:
        return 0
    hours = int(match.group(1))
    minutes = int(match.group(2))
    return hours * 3600 + minutes * 60


def _ensure_aware(value: datetime, fallback_tz: ZoneInfo = SHANGHAI_TZ) -> datetime:
    if timezone.is_aware(value):
        return value.astimezone(UTC)
    return value.replace(tzinfo=fallback_tz).astimezone(UTC)


def _decode_embedded_json_attr(value: str) -> dict:
    decoded = value or ""
    for _ in range(3):
        next_value = html.unescape(decoded)
        if next_value == decoded:
            break
        decoded = next_value
    return json.loads(decoded)


def _build_event(
    *,
    source_site: str,
    source_id: str,
    title: str,
    url: str,
    start_time: datetime,
    end_time: datetime,
    duration_seconds: int,
    organizer: str = "",
    extra: dict | None = None,
) -> NormalizedCompetitionEvent | None:
    if not source_id or not title or not url:
        return None

    start_at = _ensure_aware(start_time)
    end_at = _ensure_aware(end_time)
    if end_at <= start_at:
        return None

    normalized_duration = int(duration_seconds or 0)
    if normalized_duration <= 0:
        normalized_duration = int((end_at - start_at).total_seconds())
    if normalized_duration <= 0:
        return None

    return NormalizedCompetitionEvent(
        source_site=source_site,
        source_id=str(source_id).strip(),
        title=str(title).strip()[:300],
        url=str(url).strip()[:500],
        start_time=start_at,
        end_time=end_at,
        duration_seconds=normalized_duration,
        organizer=str(organizer or "").strip()[:200],
        extra=extra or {},
    )


def fetch_codeforces_events() -> list[NormalizedCompetitionEvent]:
    raw = _request_text("https://codeforces.com/api/contest.list?gym=false")
    payload = json.loads(raw)
    if payload.get("status") != "OK":
        raise ValueError("Codeforces API returned non-OK status.")

    events = []
    for item in payload.get("result", []):
        start_seconds = item.get("startTimeSeconds")
        duration_seconds = int(item.get("durationSeconds") or 0)
        if not start_seconds or duration_seconds <= 0:
            continue
        start_time = datetime.fromtimestamp(int(start_seconds), tz=UTC)
        end_time = start_time + timedelta(seconds=duration_seconds)
        event = _build_event(
            source_site=CompetitionCalendarEvent.SourceSite.CODEFORCES,
            source_id=str(item.get("id", "")).strip(),
            title=item.get("name", ""),
            url=f"https://codeforces.com/contest/{item.get('id')}",
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration_seconds,
            organizer="Codeforces",
            extra={
                "phase": item.get("phase", ""),
                "type": item.get("type", ""),
            },
        )
        if event is not None:
            events.append(event)
    return events


def _parse_atcoder_section(html_text: str, heading: str, section_key: str) -> list[NormalizedCompetitionEvent]:
    section_match = re.search(ATCODER_SECTION_PATTERN.format(heading=re.escape(heading)), html_text, re.S)
    if not section_match:
        return []

    events = []
    for row_html in ATCODER_ROW_RE.findall(section_match.group(1)):
        cells = ATCODER_CELL_RE.findall(row_html)
        if len(cells) < 3:
            continue

        time_match = ATCODER_TIME_RE.search(cells[0])
        contest_links = ATCODER_LINK_RE.findall(cells[1])
        if not time_match or not contest_links:
            continue

        href, title = contest_links[-1]
        start_time = datetime.strptime(time_match.group(1).strip(), "%Y-%m-%d %H:%M:%S%z")
        duration_seconds = _parse_duration_hhmm(_strip_tags(cells[2]))
        if duration_seconds <= 0:
            continue
        end_time = start_time + timedelta(seconds=duration_seconds)
        source_id = href.rstrip("/").split("/")[-1]
        event = _build_event(
            source_site=CompetitionCalendarEvent.SourceSite.ATCODER,
            source_id=source_id,
            title=_strip_tags(title),
            url=urljoin("https://atcoder.jp", href),
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration_seconds,
            organizer="AtCoder",
            extra={"section": section_key},
        )
        if event is not None:
            events.append(event)
    return events


def fetch_atcoder_events() -> list[NormalizedCompetitionEvent]:
    html_text = _request_text("https://atcoder.jp/contests/?lang=en")
    events = []
    events.extend(_parse_atcoder_section(html_text, "Upcoming Contests", "upcoming"))
    events.extend(_parse_atcoder_section(html_text, "Recent Contests", "recent"))
    return events


def fetch_nowcoder_events() -> list[NormalizedCompetitionEvent]:
    html_text = _request_text("https://ac.nowcoder.com/acm/contest/vip-index")
    events = []
    seen_ids = set()
    for raw_json in NOWCODER_ITEM_RE.findall(html_text):
        payload = _decode_embedded_json_attr(raw_json)
        contest_id = str(payload.get("contestId", "")).strip()
        if not contest_id or contest_id in seen_ids:
            continue
        seen_ids.add(contest_id)

        start_ms = payload.get("contestStartTime")
        end_ms = payload.get("contestEndTime")
        if not start_ms or not end_ms:
            continue

        start_time = datetime.fromtimestamp(int(start_ms) / 1000, tz=SHANGHAI_TZ)
        end_time = datetime.fromtimestamp(int(end_ms) / 1000, tz=SHANGHAI_TZ)
        organizer = (
            payload.get("settingInfo", {}).get("organizerName")
            or payload.get("creatorName")
            or "牛客"
        )
        event = _build_event(
            source_site=CompetitionCalendarEvent.SourceSite.NOWCODER,
            source_id=contest_id,
            title=payload.get("contestName", ""),
            url=f"https://ac.nowcoder.com/acm/contest/{contest_id}",
            start_time=start_time,
            end_time=end_time,
            duration_seconds=int((payload.get("contestDuration") or 0) / 1000),
            organizer=organizer,
            extra={
                "type": payload.get("type"),
                "topCategoryId": payload.get("topCategoryId"),
            },
        )
        if event is not None:
            events.append(event)
    return events


def fetch_luogu_events() -> list[NormalizedCompetitionEvent]:
    opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    _request_text("https://www.luogu.com.cn/", opener=opener)
    html_text = _request_text(
        "https://www.luogu.com.cn/contest/list",
        opener=opener,
        headers={"Referer": "https://www.luogu.com.cn/"},
    )
    match = LUOGU_INJECTION_RE.search(html_text)
    if not match:
        raise ValueError("Luogu contest list payload not found.")

    payload = json.loads(unquote(match.group(1)))
    contests = payload.get("currentData", {}).get("contests", {}).get("result", [])
    events = []
    for item in contests:
        contest_id = str(item.get("id", "")).strip()
        start_seconds = item.get("startTime")
        end_seconds = item.get("endTime")
        if not contest_id or not start_seconds or not end_seconds:
            continue

        start_time = datetime.fromtimestamp(int(start_seconds), tz=UTC)
        end_time = datetime.fromtimestamp(int(end_seconds), tz=UTC)
        event = _build_event(
            source_site=CompetitionCalendarEvent.SourceSite.LUOGU,
            source_id=contest_id,
            title=item.get("name", ""),
            url=f"https://www.luogu.com.cn/contest/{contest_id}",
            start_time=start_time,
            end_time=end_time,
            duration_seconds=int(end_seconds) - int(start_seconds),
            organizer=(item.get("host") or {}).get("name", "洛谷"),
            extra={
                "ruleType": item.get("ruleType"),
                "visibilityType": item.get("visibilityType"),
                "rated": item.get("rated"),
            },
        )
        if event is not None:
            events.append(event)
    return events


SOURCE_FETCHERS = {
    CompetitionCalendarEvent.SourceSite.CODEFORCES: fetch_codeforces_events,
    CompetitionCalendarEvent.SourceSite.ATCODER: fetch_atcoder_events,
    CompetitionCalendarEvent.SourceSite.NOWCODER: fetch_nowcoder_events,
    CompetitionCalendarEvent.SourceSite.LUOGU: fetch_luogu_events,
}


def normalize_source_sites(source_sites: list[str] | tuple[str, ...] | None = None) -> list[str]:
    valid_sites = [key for key, _label in CompetitionCalendarEvent.SourceSite.choices]
    if not source_sites:
        return valid_sites

    selected = []
    for item in source_sites:
        normalized = str(item or "").strip().lower()
        if normalized in valid_sites and normalized not in selected:
            selected.append(normalized)
    return selected or valid_sites


def sync_competition_calendar(
    *,
    source_sites: list[str] | tuple[str, ...] | None = None,
    past_days: int = 180,
    future_days: int = 365,
) -> dict:
    selected_sites = normalize_source_sites(source_sites)
    now = timezone.now()
    earliest_end_time = now - timedelta(days=max(int(past_days), 0))
    latest_start_time = now + timedelta(days=max(int(future_days), 0))

    summary = {
        "sites": {},
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "failed_sites": [],
    }

    for site in selected_sites:
        fetcher = SOURCE_FETCHERS[site]
        site_summary = {
            "fetched": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "error": "",
        }
        try:
            rows = fetcher()
            site_summary["fetched"] = len(rows)
            for row in rows:
                if row.end_time < earliest_end_time or row.start_time > latest_start_time:
                    site_summary["skipped"] += 1
                    summary["skipped"] += 1
                    continue

                _, created = CompetitionCalendarEvent.objects.update_or_create(
                    source_site=row.source_site,
                    source_id=row.source_id,
                    defaults={
                        "title": row.title,
                        "organizer": row.organizer,
                        "url": row.url,
                        "start_time": row.start_time,
                        "end_time": row.end_time,
                        "duration_seconds": row.duration_seconds,
                        "last_synced_at": now,
                        "extra": row.extra,
                    },
                )
                if created:
                    site_summary["created"] += 1
                    summary["created"] += 1
                else:
                    site_summary["updated"] += 1
                    summary["updated"] += 1
        except Exception as exc:
            site_summary["error"] = str(exc)
            summary["failed_sites"].append(site)
            LOGGER.warning("Competition calendar sync failed for %s: %s", site, exc)

        summary["sites"][site] = site_summary

    return summary
