"""Exercise the actual Alembic chain against an isolated, populated legacy database."""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from chase201.profile_defaults import expanded_profile

API = Path(__file__).parents[1]


def test_populated_v1_upgrade_backfill_and_reversible_empty_v2_schema(tmp_path):
    path = tmp_path / "migration.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite+aiosqlite:///{path.as_posix()}",
        "ENVIRONMENT": "test",
    }

    def alembic(*args, success=True):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=API,
            env=env,
            capture_output=True,
            text=True,
        )
        assert (result.returncode == 0) == success, result.stdout + result.stderr
        return result

    alembic("upgrade", "c95af1b9cdb8")
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO catalog_versions VALUES ('old', 'fixture', 'test', 0, '2026-09-10')"
        )
        db.execute("INSERT INTO players VALUES ('old:p1', 'old', 'Original Player', 'BATTER', 80)")
        db.execute("INSERT INTO simulation_profiles VALUES ('old:p1', 81.0, 39.0)")
        db.execute(
            "INSERT INTO drafts VALUES ('d', NULL, NULL, 'old', 0, 'CONFIRMED', '[]', '2026-09-10')"
        )
        db.execute("INSERT INTO teams VALUES ('t', 'd')")
        db.execute(
            "INSERT INTO matches VALUES ('m', 't', NULL, NULL, '[]', 'seed', 'v1.0', 1, ?, '2026-09-10', NULL)",
            (json.dumps({"runs": 32, "balls": 18}),),
        )
        db.execute("INSERT INTO decisions VALUES ('m', 1, 'ROTATE', 'BALANCED', '2026-09-10')")
        db.execute(
            "INSERT INTO match_events VALUES ('m', 1, 0, ?)",
            (json.dumps({"label": "Original event"}),),
        )
    alembic("upgrade", "head")
    alembic("check")
    for version in ("v3.0", "v3.1", "v3.2", "v3.3", "v3.4", "v3.5"):
        with sqlite3.connect(path) as db:
            db.execute("UPDATE matches SET ruleset = ?", (version,))
        failure = alembic("downgrade", "f31b72d4c905", success=False)
        assert "Cannot downgrade while v3" in failure.stderr
    with sqlite3.connect(path) as db:
        db.execute("UPDATE matches SET ruleset = 'v1.0'")
    for table in ("drafts", "catalog_versions"):
        with sqlite3.connect(path) as db:
            db.execute(f"UPDATE {table} SET selection_ruleset = 'real-players-v1'")
        failure = alembic("downgrade", "f31b72d4c905", success=False)
        assert "Cannot downgrade while v3" in failure.stderr
        with sqlite3.connect(path) as db:
            db.execute(f"UPDATE {table} SET selection_ruleset = 'open-v1'")
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        profile = dict(db.execute("SELECT * FROM simulation_profiles").fetchone())
        assert profile["batting"] == 81 and profile["bowling"] == 39
        assert {
            key: profile[key] for key in expanded_profile("old:p1", 81, 39)
        } == expanded_profile("old:p1", 81, 39)
        saved = db.execute("SELECT ruleset, state FROM matches").fetchone()
        assert saved["ruleset"] == "v1.0" and json.loads(saved["state"]) == {
            "runs": 32,
            "balls": 18,
        }
        assert db.execute("SELECT strategy FROM decisions").fetchone()[0] is None
        assert db.execute("SELECT selection_ruleset FROM drafts").fetchone()[0] == "open-v1"
        assert json.loads(db.execute("SELECT payload FROM match_events").fetchone()[0]) == {
            "label": "Original event"
        }
        db.execute("UPDATE matches SET ruleset = 'v2.0'")
        db.execute("UPDATE drafts SET selection_ruleset = 'balanced-v1'")
    failure = alembic("downgrade", "e20a91d8f672", success=False)
    assert "Cannot downgrade while rating-limited drafts exist" in failure.stderr
    with sqlite3.connect(path) as db:
        db.execute("UPDATE drafts SET selection_ruleset = 'open-v1'")
    failure = alembic("downgrade", "c95af1b9cdb8", success=False)
    assert "Cannot downgrade while v2 matches exist" in failure.stderr
    with sqlite3.connect(path) as db:
        db.execute("UPDATE matches SET ruleset = 'v1.0'")
    alembic("downgrade", "c95af1b9cdb8")
    alembic("upgrade", "head")
    alembic("check")
