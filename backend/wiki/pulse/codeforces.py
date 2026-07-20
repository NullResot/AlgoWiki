import json
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.core.cache import cache


class CodeforcesError(Exception):
    """Base error for a predictable Codeforces failure."""


class CodeforcesNotFound(CodeforcesError):
    pass


class CodeforcesUnavailable(CodeforcesError):
    pass


class CodeforcesClient:
    API_BASE = "https://codeforces.com/api"
    RATE_SECONDS = 2.05

    def __init__(self, *, timeout=8):
        self.timeout = timeout

    def _acquire_rate_slot(self):
        token = uuid.uuid4().hex
        lock_key = "pulse:codeforces:rate-lock"
        deadline = time.monotonic() + 8
        while not cache.add(lock_key, token, timeout=10):
            if time.monotonic() >= deadline:
                raise CodeforcesUnavailable("Codeforces 请求队列繁忙，请稍后重试。")
            time.sleep(0.05)
        try:
            last_request = float(cache.get("pulse:codeforces:last-request") or 0)
            wait_for = self.RATE_SECONDS - (time.time() - last_request)
            if wait_for > 0:
                time.sleep(wait_for)
            cache.set("pulse:codeforces:last-request", time.time(), timeout=30)
        finally:
            if cache.get(lock_key) == token:
                cache.delete(lock_key)

    def _request(self, method, params=None):
        query = urlencode(params or {})
        url = f"{self.API_BASE}/{method}"
        if query:
            url = f"{url}?{query}"
        self._acquire_rate_slot()
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "AlgoWiki-Midnight-Pulse/1.0",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise CodeforcesUnavailable("Codeforces 暂时不可用，请稍后重试。") from exc
        if payload.get("status") != "OK":
            comment = str(payload.get("comment") or "Codeforces API rejected request")
            if "not found" in comment.lower():
                raise CodeforcesNotFound("没有找到这个 Codeforces Handle。")
            raise CodeforcesUnavailable("Codeforces 暂时无法完成该请求。")
        return payload.get("result")

    def user_info(self, handle):
        key = f"pulse:codeforces:user-info:{handle.casefold()}"
        cached = cache.get(key)
        if cached is not None:
            return cached
        result = self._request("user.info", {"handles": handle, "checkHistoricHandles": "false"})
        if not result:
            raise CodeforcesNotFound("没有找到这个 Codeforces Handle。")
        info = result[0]
        cache.set(key, info, timeout=300)
        return info

    def user_status(self, handle, *, count=10000):
        count = max(1, min(int(count), 10000))
        key = f"pulse:codeforces:user-status:{handle.casefold()}:{count}"
        cached = cache.get(key)
        if cached is not None:
            return cached
        result = self._request("user.status", {"handle": handle, "from": 1, "count": count})
        result = list(result or [])
        cache.set(key, result, timeout=15)
        return result

    def user_status_all(self, handle):
        """Read the complete public submission history in API-sized pages."""

        rows = []
        page_size = 10000
        for page in range(20):
            start = page * page_size + 1
            batch = list(
                self._request(
                    "user.status",
                    {"handle": handle, "from": start, "count": page_size},
                )
                or []
            )
            rows.extend(batch)
            if len(batch) < page_size:
                return rows
        raise CodeforcesUnavailable("Codeforces 提交历史过大，暂时无法完成同步。")

    def problemset(self):
        key = "pulse:codeforces:problemset"
        cached = cache.get(key)
        if cached is not None:
            return cached
        result = self._request("problemset.problems") or {}
        cache.set(key, result, timeout=21600)
        return result

    def contests(self):
        key = "pulse:codeforces:contests"
        cached = cache.get(key)
        if cached is not None:
            return cached
        result = list(self._request("contest.list", {"gym": "false"}) or [])
        cache.set(key, result, timeout=3600)
        return result

    def contest_standings(self, contest_id):
        key = f"pulse:codeforces:contest:{int(contest_id)}:problems"
        cached = cache.get(key)
        if cached is not None:
            return cached
        result = self._request(
            "contest.standings",
            {"contestId": int(contest_id), "from": 1, "count": 1, "showUnofficial": "false"},
        ) or {}
        problems = list(result.get("problems") or [])
        cache.set(key, problems, timeout=86400)
        return problems
