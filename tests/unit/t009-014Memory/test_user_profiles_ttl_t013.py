"""T-013 / FR-13 / 规格 §3.4：`user_short_term_states` TTL、懒清理与物理 purge。"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.libs.base.user_profiles import DEFAULT_SHORT_TERM_TTL_DAYS, UserProfileManager


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    p = tmp_path / "profiles_ttl_t013.db"
    return p


def test_add_short_term_state_inserts_with_future_expires(tmp_db: Path):
    mgr = UserProfileManager(db_path=str(tmp_db))
    assert mgr.add_short_term_state("u_ttl", "cold", ttl_days=DEFAULT_SHORT_TERM_TTL_DAYS)

    conn = sqlite3.connect(str(tmp_db))
    cur = conn.cursor()
    cur.execute(
        "SELECT expires_at, is_active FROM user_short_term_states WHERE user_id=? AND condition=?",
        ("u_ttl", "cold"),
    )
    row = cur.fetchone()
    conn.close()
    assert row is not None
    expires_at, is_active = row
    assert is_active == 1
    assert expires_at > datetime.now().isoformat()


def test_get_active_short_term_states_excludes_expired_lazy_deactivate(tmp_db: Path):
    mgr = UserProfileManager(db_path=str(tmp_db))
    mgr.add_short_term_state("u2", "toothache", ttl_days=7)

    past = (datetime.now() - timedelta(days=1)).isoformat()
    conn = sqlite3.connect(str(tmp_db))
    conn.execute(
        "UPDATE user_short_term_states SET expires_at = ? WHERE user_id=? AND condition=?",
        (past, "u2", "toothache"),
    )
    conn.commit()
    conn.close()

    active = mgr.get_active_short_term_states("u2")
    assert active == []

    conn = sqlite3.connect(str(tmp_db))
    cur = conn.cursor()
    cur.execute(
        "SELECT is_active FROM user_short_term_states WHERE user_id=? AND condition=?",
        ("u2", "toothache"),
    )
    row = cur.fetchone()
    conn.close()
    assert row is not None and row[0] == 0


def test_get_active_returns_only_non_expired(tmp_db: Path):
    mgr = UserProfileManager(db_path=str(tmp_db))
    mgr.add_short_term_state("u3", "active_ok", ttl_days=30)

    conn = sqlite3.connect(str(tmp_db))
    conn.execute(
        "UPDATE user_short_term_states SET expires_at = ? WHERE user_id=? AND condition=?",
        ((datetime.now() - timedelta(hours=1)).isoformat(), "u3", "active_ok"),
    )
    conn.commit()
    conn.close()

    assert mgr.get_active_short_term_states("u3") == []

    mgr.add_short_term_state("u3", "fresh", ttl_days=7)
    names = mgr.get_active_short_term_states("u3")
    assert "fresh" in names
    assert "active_ok" not in names


def test_purge_expired_states_deletes_rows(tmp_db: Path):
    mgr = UserProfileManager(db_path=str(tmp_db))
    mgr.add_short_term_state("u4", "gone", ttl_days=1)

    conn = sqlite3.connect(str(tmp_db))
    conn.execute(
        "UPDATE user_short_term_states SET expires_at = ? WHERE user_id=?",
        ((datetime.now() - timedelta(days=2)).isoformat(), "u4"),
    )
    conn.commit()
    conn.close()

    n = mgr.purge_expired_states(user_id="u4")
    assert n >= 1

    conn = sqlite3.connect(str(tmp_db))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM user_short_term_states WHERE user_id=?", ("u4",))
    cnt = cur.fetchone()[0]
    conn.close()
    assert cnt == 0


def test_add_duplicate_active_condition_skips_insert(tmp_db: Path):
    mgr = UserProfileManager(db_path=str(tmp_db))
    assert mgr.add_short_term_state("u5", "same", ttl_days=7)
    assert mgr.add_short_term_state("u5", "same", ttl_days=7)

    conn = sqlite3.connect(str(tmp_db))
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM user_short_term_states WHERE user_id=? AND condition=?",
        ("u5", "same"),
    )
    cnt = cur.fetchone()[0]
    conn.close()
    assert cnt == 1


def test_deactivate_short_term_state(tmp_db: Path):
    mgr = UserProfileManager(db_path=str(tmp_db))
    mgr.add_short_term_state("u6", "manual_off", ttl_days=7)
    assert mgr.deactivate_short_term_state("u6", "manual_off")
    assert mgr.get_active_short_term_states("u6") == []
