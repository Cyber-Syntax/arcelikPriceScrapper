from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("scrapper.report")


class Report:
    def __init__(self, command: str):
        self._start = datetime.now(UTC)
        self.data: dict[str, Any] = {
            "command": command,
            "started_at": self._start.isoformat(timespec="seconds"),
            "warnings": [],
        }

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def warn(self, msg: str) -> None:
        log.warning(msg)
        self.data["warnings"].append(msg)

    def mark_finished(self, exit_code: int) -> None:
        if "finished_at" not in self.data:
            end = datetime.now(UTC)
            self.data["finished_at"] = end.isoformat(timespec="seconds")
            self.data["duration_s"] = round(
                (end - self._start).total_seconds(), 1
            )
        self.data["exit_code"] = exit_code

    def finish(self, path: Path, exit_code: int) -> None:
        self.mark_finished(exit_code)
        path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            lines = [
                f"## scrapper `{self.data['command']}`",
                "",
                f"- exit code: **{exit_code}**",
                f"- duration: {self.data['duration_s']} s",
            ]
            for key in (
                "abort_reason",
                "products",
                "missing_count",
                "empty_price_count",
                "campaigns",
                "warranty_rows",
                "specs_products",
                "specs_rows",
                "features_rows",
            ):
                if key in self.data and self.data[key] not in (None, ""):
                    lines.append(f"- {key}: {self.data[key]}")
            if self.data.get("http_status"):
                lines.append(f"- http: `{self.data['http_status']}`")
            lines.append(f"- warnings: {len(self.data['warnings'])}")
            with open(summary, "a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
