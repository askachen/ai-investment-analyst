from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _copy_script(tmp_path: Path, relative_path: str) -> Path:
    source = PROJECT_ROOT / relative_path
    destination = tmp_path / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_generate_daily_screener_script_bootstraps_src_without_pythonpath(tmp_path: Path):
    script_path = _copy_script(tmp_path, "scripts/generate_daily_screener.py")
    _write_file(tmp_path / "src/ai_investment_analyst/__init__.py", "")
    _write_file(tmp_path / "src/ai_investment_analyst/analysis/__init__.py", "")
    _write_file(
        tmp_path / "src/ai_investment_analyst/analysis/daily_screener_job.py",
        """
from dataclasses import dataclass


@dataclass
class FakeEntry:
    rank: int
    ticker: str
    total_score: float


@dataclass
class FakeSnapshot:
    strategy_key: str
    run_date: str
    candidate_count: int
    results: list[FakeEntry]


@dataclass
class FakeResult:
    tickers: list[str]
    source_refresh: dict[str, str]
    snapshots: list[FakeSnapshot]


def run_daily_screener_job() -> FakeResult:
    return FakeResult(
        tickers=["2330"],
        source_refresh={"prices": "ok"},
        snapshots=[
            FakeSnapshot(
                strategy_key="balanced",
                run_date="2026-05-03",
                candidate_count=1,
                results=[FakeEntry(rank=1, ticker="2330", total_score=98.5)],
            )
        ],
    )
""".strip()
        + "\n",
    )

    completed = subprocess.run(
        [sys.executable, "-S", str(script_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={},
    )

    assert completed.returncode == 0, completed.stderr
    assert "Upstream refresh completed for 1 tickers: 2330" in completed.stdout
    assert "Daily screener [balanced] generated for 2026-05-03 (1 candidates)." in completed.stdout


def test_apply_daily_screener_schema_script_bootstraps_src_without_pythonpath(tmp_path: Path):
    script_path = _copy_script(tmp_path, "scripts/apply_daily_screener_schema.py")
    _write_file(tmp_path / "src/ai_investment_analyst/__init__.py", "")
    _write_file(tmp_path / "src/ai_investment_analyst/db/__init__.py", "")
    _write_file(
        tmp_path / "src/ai_investment_analyst/db/connection.py",
        """
from pathlib import Path


class FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql):
        Path('/tmp/applied_sql.txt').write_text(sql, encoding='utf-8')


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return FakeCursor()

    def commit(self):
        Path('/tmp/schema_commit.txt').write_text('committed', encoding='utf-8')


def get_connection():
    return FakeConnection()
""".strip()
        + "\n",
    )
    _write_file(
        tmp_path / "openspec/changes/stock-analysis-report/sql/006_daily_screener.sql",
        "select 1;\n",
    )

    completed = subprocess.run(
        [sys.executable, "-S", str(script_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={},
    )

    assert completed.returncode == 0, completed.stderr
    assert "Daily screener schema applied successfully." in completed.stdout
