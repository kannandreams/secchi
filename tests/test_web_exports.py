from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from secchi.models import Project
from secchi.ui.app import Secchi


def test_web_export_uses_textual_delivery(monkeypatch, tmp_path: Path) -> None:
    app = Secchi(Project("demo"), tmp_path / "secchi.toml")
    app._driver = SimpleNamespace(is_web=True)
    delivered: dict[str, object] = {}

    def deliver_text(stream, **kwargs):
        delivered["content"] = stream.read()
        delivered.update(kwargs)

    monkeypatch.setattr(app, "deliver_text", deliver_text)
    monkeypatch.setattr(app, "notify", lambda *args, **kwargs: None)

    app._deliver_export("# report", "demo", "duckdb", "markdown")

    assert delivered["content"] == "# report"
    assert delivered["save_filename"] == (
        "secchi-demo-duckdb-" + datetime.now(UTC).strftime("%Y-%m-%d") + ".md"
    )
    assert delivered["mime_type"] == "text/markdown"


def test_terminal_export_still_writes_a_file(monkeypatch, tmp_path: Path) -> None:
    app = Secchi(Project("demo"), tmp_path / "secchi.toml")
    app._driver = None
    monkeypatch.setattr(app, "notify", lambda *args, **kwargs: None)
    saved: dict[str, object] = {}

    def save_report(*args, **kwargs):
        saved["args"] = args
        saved["kwargs"] = kwargs
        return tmp_path / "report.md"

    monkeypatch.setattr("secchi.ui.app.save_report", save_report)

    app._deliver_export("# report", "demo", "duckdb", "markdown")

    assert saved["args"] == ("# report", "demo", "duckdb", "markdown")
