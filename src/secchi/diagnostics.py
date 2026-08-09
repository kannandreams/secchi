"""Readable, structured diagnostics shared by CLI and dashboard surfaces."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Lock


class DiagnosticStatus(str, Enum):
    SUCCESS = "SUCCESS"
    WARN = "WARN"
    FAILURE = "FAILURE"


@dataclass(frozen=True)
class DiagnosticEvent:
    """One user-facing process or HTTP diagnostic event."""

    timestamp: datetime
    status: DiagnosticStatus
    source: str
    message: str
    url: str = ""
    status_code: int | None = None

    def format(self) -> str:
        time = self.timestamp.astimezone(timezone.utc).strftime("%H:%M:%S")
        suffix = f" -> {self.status_code}" if self.status_code is not None else ""
        target = f" {self.url}" if self.url else ""
        return f"{time} {self.status.value:<7} [{self.source}] {self.message}{target}{suffix}"


class DiagnosticLog:
    """Bounded session log with optional human-readable file output."""

    def __init__(
        self,
        *,
        path: Path | None = None,
        max_events: int = 1000,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = path
        self.max_events = max_events
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._events: list[DiagnosticEvent] = []
        self._lock = Lock()
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("")

    def record(
        self,
        status: DiagnosticStatus,
        source: str,
        message: str,
        *,
        url: str = "",
        status_code: int | None = None,
    ) -> DiagnosticEvent:
        event = DiagnosticEvent(
            timestamp=self.clock(),
            status=status,
            source=source,
            message=message,
            url=url,
            status_code=status_code,
        )
        with self._lock:
            self._events.append(event)
            del self._events[: max(0, len(self._events) - self.max_events)]
            if self.path is not None:
                with self.path.open("a") as output:
                    output.write(event.format() + "\n")
        return event

    def snapshot(self) -> list[DiagnosticEvent]:
        with self._lock:
            return list(self._events)

    def has_status(self, *statuses: DiagnosticStatus) -> bool:
        wanted = set(statuses)
        return any(event.status in wanted for event in self.snapshot())


def diagnostic_for_http_error(exc: Exception) -> str:
    """Return a concise, stable message without a traceback."""
    if hasattr(exc, "response"):
        response = exc.response
        reason = response.reason_phrase or "HTTP error"
        return f"HTTP {response.status_code} {reason}"
    message = str(exc).strip()
    return message or exc.__class__.__name__
