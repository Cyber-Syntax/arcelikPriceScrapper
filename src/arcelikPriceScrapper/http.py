from __future__ import annotations

import asyncio
import logging
import random
import re
from collections import Counter
from urllib.parse import urlparse

from curl_cffi.requests import AsyncSession

from .config import HttpCfg
from .report import Report

log = logging.getLogger("scrapper.http")

BASE = "https://www.arcelik.com.tr"
HEADERS = {
    "Accept-Language": "tr-TR,tr;q=0.9"
}  # User-Agent'i impersonate belirler


class AbortRun(Exception):
    """403/429 israrli -> tum kosu durdurulur."""


class RobotsRules:
    """robots.txt `User-agent: *` grubu icin wildcard (*, $) destekli Disallow eslestirici."""

    def __init__(self, text: str = ""):
        self.rules: list[re.Pattern[str]] = []
        self._parse(text)

    @staticmethod
    def _compile(pattern: str) -> re.Pattern[str]:
        anchored = pattern.endswith("$")
        if anchored:
            pattern = pattern[:-1]
        rx = re.escape(pattern).replace(r"\*", ".*")
        return re.compile("^" + rx + ("$" if anchored else ""))

    def _parse(self, text: str) -> None:
        star = False
        prev_agent = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            key, _, val = line.partition(":")
            key, val = key.strip().lower(), val.strip()
            if key == "user-agent":
                star = (star or val == "*") if prev_agent else (val == "*")
                prev_agent = True
            else:
                if key == "disallow" and star and val:
                    self.rules.append(self._compile(val))
                prev_agent = False

    def allowed(self, url: str) -> bool:
        p = urlparse(url)
        path = p.path + (f"?{p.query}" if p.query else "")
        return not any(r.match(path) for r in self.rules)


class Http:
    def __init__(self, cfg: HttpCfg, report: Report):
        self.cfg = cfg
        self.report = report
        self.sem = asyncio.Semaphore(cfg.concurrency)
        self.session: AsyncSession | None = None
        self.robots = RobotsRules()
        self.aborted: str | None = None
        self.status: Counter[str] = Counter()

    async def __aenter__(self) -> Http:
        self.session = AsyncSession(
            impersonate="chrome",
            headers=HEADERS,
            timeout=self.cfg.timeout,
            allow_redirects=True,
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self.session is not None:
            await self.session.close()

    async def load_robots(self) -> None:
        text = await self.get(f"{BASE}/robots.txt", check_robots=False)
        if text:
            self.robots = RobotsRules(text)
            log.info("robots.txt: %d disallow rule", len(self.robots.rules))
        else:
            self.report.warn("robots.txt alinamadi; kural uygulanmadi")

    async def get(self, url: str, check_robots: bool = True) -> str | None:
        assert self.session is not None
        if self.aborted:
            raise AbortRun(self.aborted)
        if check_robots and not self.robots.allowed(url):
            self.status["robots_skipped"] += 1
            log.warning("robots.txt disallows, skipped: %s", url[:120])
            return None

        last_status: int | None = None
        for attempt in range(self.cfg.retries):
            if self.aborted:
                raise AbortRun(self.aborted)
            r = None
            async with self.sem:
                await asyncio.sleep(
                    random.uniform(self.cfg.delay_min, self.cfg.delay_max)
                )
                try:
                    r = await self.session.get(url)
                except Exception as e:  # noqa: BLE001
                    self.status["exception"] += 1
                    log.warning("ERR %s %s", type(e).__name__, url[:100])
            if r is not None:
                code = r.status_code
                last_status = code
                self.status[str(code)] += 1
                if code == 200:
                    return r.text
                log.warning(
                    "HTTP %s %s (attempt %d/%d)",
                    code,
                    url[:100],
                    attempt + 1,
                    self.cfg.retries,
                )
                if code not in (403, 429) and code < 500:
                    return None
            if attempt < self.cfg.retries - 1:
                await asyncio.sleep(2**attempt * 2)

        if last_status in (403, 429):
            self.aborted = f"HTTP {last_status} persisted for {url[:120]}"
            raise AbortRun(self.aborted)
        return None
