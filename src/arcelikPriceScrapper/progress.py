from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sys
import time
from typing import TextIO

log = logging.getLogger("scrapper.progress")


def default_enabled(force: bool = False, no_progress: bool = False) -> bool:
    """GitHub Actions/CI ve TTY olmayan ortamlarda otomatik kapanir."""
    if no_progress:
        return False
    if force:
        return True
    if os.environ.get("GITHUB_ACTIONS") or os.environ.get("CI"):
        return False
    return bool(sys.stderr.isatty())


class Progress:
    """Bagimliliksiz, throttle edilmis tek satir progress bar."""

    def __init__(self, enabled: bool, stream: TextIO | None = None) -> None:
        self.enabled = enabled
        self.stream = stream or sys.stderr
        self.label = ""
        self.total = 0
        self.done = 0
        self.products = 0
        self.detail = ""
        self._start = time.monotonic()
        self._last_render = 0.0
        self._last_len = 0
        self._active = False

    def start(self, label: str, total: int) -> None:
        if not self.enabled:
            return
        self.label = label
        self.total = max(0, total)
        self.done = 0
        self.products = 0
        self.detail = ""
        self._start = time.monotonic()
        self._active = True
        self._render(force=True)

    def set_detail(self, detail: str) -> None:
        if not self.enabled:
            return
        self.detail = detail
        self._render()

    def advance(self, products: int = 0, detail: str = "") -> None:
        if not self.enabled:
            return
        self.done += 1
        self.products += products
        if detail:
            self.detail = detail
        self._render()

    def _render(self, force: bool = False) -> None:
        if not self.enabled or not self._active:
            return
        now = time.monotonic()
        if not force and now - self._last_render < 0.1:
            return
        self._last_render = now
        elapsed = now - self._start
        total = self.total
        done = min(self.done, total) if total else self.done
        pct = (done / total * 100) if total else 0.0
        width = 20
        filled = int(width * pct / 100)
        bar = "#" * filled + "-" * (width - filled)
        detail = self.detail[:90]
        text = (
            f"\r[{bar}] {done}/{total} {self.label} | "
            f"{self.products} urun | {elapsed:.0f}s"
        )
        if detail:
            text += f" | {detail}"
        padding = max(0, self._last_len - len(text))
        self.stream.write(text + " " * padding)
        self.stream.flush()
        self._last_len = len(text)

    def close(self) -> None:
        if self.enabled and self._active:
            self.stream.write("\n")
            self.stream.flush()
            self._active = False


class LogHeartbeat:
    """TTY olmasa da uzun suren islemlerde periyodik INFO satiri yazar."""

    def __init__(self, label: str, total: int, interval: float = 30.0) -> None:
        self.label = label
        self.total = max(0, total)
        self.interval = interval
        self.done = 0
        self.fetched = 0
        self.failures = 0
        self.current = ""
        self.http_status: dict[str, int] = {}
        self._start = time.monotonic()
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._start = time.monotonic()
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.interval)
            elapsed = time.monotonic() - self._start
            rate = self.done / elapsed if elapsed else 0.0
            eta = (
                (self.total - self.done) / rate
                if rate > 0 and self.total >= self.done
                else None
            )
            log.info(
                "%s: %d/%d | gecen %.0fs | %.2f urun/sn | ETA %s | "
                "okunan=%d hata=%d | current=%s | http=%s",
                self.label,
                self.done,
                self.total,
                elapsed,
                rate,
                f"{eta:.0f}s" if eta is not None else "?",
                self.fetched,
                self.failures,
                self.current[:140] or "-",
                self.http_status or "-",
            )

    def tick(self, fetched: bool = False, failed: bool = False) -> None:
        self.done += 1
        if fetched:
            self.fetched += 1
        if failed:
            self.failures += 1

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        elapsed = time.monotonic() - self._start
        log.info(
            "%s: bitti %d/%d | gecen %.0fs | okunan=%d hata=%d",
            self.label,
            self.done,
            self.total,
            elapsed,
            self.fetched,
            self.failures,
        )
