"""Shared fixtures for bookkeeper tests."""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# Ensure the project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    """Redirect bookkeeper DB to a temp directory for every test."""
    import bookkeeper

    db_dir = tmp_path / "data"
    db_dir.mkdir()
    monkeypatch.setattr(bookkeeper, "DB_DIR", db_dir)
    monkeypatch.setattr(bookkeeper, "DB_PATH", db_dir / "test_books.db")


@pytest.fixture
def run_cli():
    """Run bookkeeper.py as a subprocess and return (returncode, stdout, stderr).

    Usage: rc, out, err = run_cli("add-revenue", "--count", "10")
    """
    script = str(PROJECT_ROOT / "bookkeeper.py")

    def _run(*args):
        result = subprocess.run(
            [sys.executable, script] + list(args),
            capture_output=True,
            text=True,
            env={"HERMES_HOME": "/tmp/_test_hermes_unused"},
        )
        return result.returncode, result.stdout, result.stderr

    return _run


def make_args(**kwargs):
    """Build a SimpleNamespace that looks like argparse output."""
    defaults = {"date": None, "note": None}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


@pytest.fixture
def args_factory():
    """Fixture that returns the make_args helper."""
    return make_args
