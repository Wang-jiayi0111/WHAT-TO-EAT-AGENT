"""T-014 / IR-05：`apply_long_term_patch`、长期画像幂等与遗留 `default_user` 迁移。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from src.libs.base.user_profiles import UserProfileManager, _LEGACY_SCOPE_USER_ID


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "t014_profiles.db"


def _long_term_last_updated(db: Path, user_id: str) -> str | None:
    conn = sqlite3.connect(str(db))
    cur = conn.cursor()
    cur.execute(
        "SELECT last_updated FROM user_long_term_profile WHERE user_id=?",
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def test_passive_extract_merge_union_allergens(tmp_db: Path):
    mgr = UserProfileManager(db_path=str(tmp_db))
    assert mgr.apply_long_term_patch(
        "user_a",
        {"allergens": ["peanut", "soy"]},
        "passive_extract",
    )
    lt = mgr.get_long_term_profile("user_a")
    assert lt is not None
    assert "peanut" in lt["allergens"]
    assert "soy" in lt["allergens"]


def test_apply_long_term_patch_idempotent_second_call_skips_upsert(tmp_db: Path):
    mgr = UserProfileManager(db_path=str(tmp_db))
    mgr.apply_long_term_patch(
        "user_b",
        {"allergens": ["milk"]},
        "passive_extract",
    )
    t1 = _long_term_last_updated(tmp_db, "user_b")
    assert t1 is not None

    mgr.apply_long_term_patch(
        "user_b",
        {"allergens": ["milk"]},
        "passive_extract",
    )
    t2 = _long_term_last_updated(tmp_db, "user_b")
    assert t2 == t1


def test_explicit_correction_replaces_allergens(tmp_db: Path):
    mgr = UserProfileManager(db_path=str(tmp_db))
    mgr.apply_long_term_patch(
        "user_c",
        {"allergens": ["a", "b"]},
        "passive_extract",
    )
    mgr.apply_long_term_patch(
        "user_c",
        {"allergens": ["egg"]},
        "explicit_correction",
    )
    lt = mgr.get_long_term_profile("user_c")
    assert lt["allergens"] == ["egg"]


def test_explicit_correction_can_clear_dietary_target(tmp_db: Path):
    mgr = UserProfileManager(db_path=str(tmp_db))
    mgr.apply_long_term_patch(
        "user_d",
        {"dietary_target": "low carb"},
        "explicit_correction",
    )
    mgr.apply_long_term_patch(
        "user_d",
        {"dietary_target": None},
        "explicit_correction",
    )
    lt = mgr.get_long_term_profile("user_d")
    assert lt["dietary_target"] == ""


def test_explicit_taste_tags_partial_replace_like(tmp_db: Path):
    mgr = UserProfileManager(db_path=str(tmp_db))
    mgr.apply_long_term_patch(
        "user_e",
        {"taste_tags": {"like": ["sweet"], "dislike": ["bitter"]}},
        "explicit_correction",
    )
    mgr.apply_long_term_patch(
        "user_e",
        {"taste_tags": {"like": ["mild"]}},
        "explicit_correction",
    )
    lt = mgr.get_long_term_profile("user_e")
    assert lt["taste_tags"]["like"] == ["mild"]
    assert lt["taste_tags"]["dislike"] == ["bitter"]


def test_migrate_legacy_default_user_to_scope_long_term(tmp_db: Path):
    UserProfileManager(db_path=str(tmp_db))

    conn = sqlite3.connect(str(tmp_db))
    now = "2020-01-01T00:00:00"
    conn.execute(
        """
        INSERT INTO user_long_term_profile
        (user_id, allergens, medical_restrictions, dietary_target,
         taste_like, taste_dislike, cooking_habits, created_at, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _LEGACY_SCOPE_USER_ID,
            json.dumps(["walnut"]),
            "[]",
            "",
            "[]",
            "[]",
            "[]",
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()

    target = "household_scope_99"
    UserProfileManager(db_path=str(tmp_db), scope_id_for_migration=target)

    mgr = UserProfileManager(db_path=str(tmp_db))
    legacy = mgr.get_long_term_profile(_LEGACY_SCOPE_USER_ID)
    scoped = mgr.get_long_term_profile(target)
    assert legacy is None
    assert scoped is not None
    assert "walnut" in scoped["allergens"]


def test_migrate_when_target_exists_deletes_legacy_row(tmp_db: Path):
    UserProfileManager(db_path=str(tmp_db))

    conn = sqlite3.connect(str(tmp_db))
    now = "2020-01-01T00:00:00"
    for uid, allergen in [( _LEGACY_SCOPE_USER_ID, '["x"]'), ("hh_dup", '["y"]')]:
        conn.execute(
            """
            INSERT INTO user_long_term_profile
            (user_id, allergens, medical_restrictions, dietary_target,
             taste_like, taste_dislike, cooking_habits, created_at, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (uid, allergen, "[]", "", "[]", "[]", "[]", now, now),
        )
    conn.commit()
    conn.close()

    UserProfileManager(db_path=str(tmp_db), scope_id_for_migration="hh_dup")

    mgr = UserProfileManager(db_path=str(tmp_db))
    assert mgr.get_long_term_profile(_LEGACY_SCOPE_USER_ID) is None
    lt = mgr.get_long_term_profile("hh_dup")
    assert lt is not None
    assert "y" in lt["allergens"]
