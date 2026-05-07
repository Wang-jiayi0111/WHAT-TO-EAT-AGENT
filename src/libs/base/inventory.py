"""
InventoryManager - 厨房库存管理

表结构（规格 §6.2）：复合主键 (household_id, name)；所有读写带
`WHERE household_id = ?`；`household_id` 使用配置 `household.default_id`（SCOPE_ID）。

规格 §6.2 禁止：用 thread_id 作为库存归属键（本模块仅接受显式 household_id / SCOPE_ID）。
"""
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .settings import Settings


def _pragma_columns(cursor: sqlite3.Cursor, table: str) -> Dict[str, str]:
    cursor.execute(f"PRAGMA table_info({table})")
    return {str(row[1]): str(row[2]) for row in cursor.fetchall()}


def _create_inventory_v62(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE inventory (
            household_id TEXT NOT NULL DEFAULT 'default',
            name         TEXT NOT NULL,
            amount       REAL NOT NULL DEFAULT 0,
            unit         TEXT NOT NULL,
            updated_at   TEXT NOT NULL,
            PRIMARY KEY (household_id, name)
        )
        """
    )


def _migrate_to_v62(conn: sqlite3.Connection, household_id: str) -> None:
    """
    自旧表迁移至 §6.2：INSERT 时 legacy 行写入当前迁移所用 SCOPE_ID（参数 household_id）。
    支持：旧 InventoryManager（name PRIMARY KEY）；旧 integrity（user_id/item_name/quantity）。
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='inventory'"
    )
    if not cursor.fetchone():
        _create_inventory_v62(cursor)
        conn.commit()
        return

    cols = _pragma_columns(cursor, "inventory")
    if "household_id" in cols:
        conn.commit()
        return

    cursor.execute("ALTER TABLE inventory RENAME TO inventory_legacy")
    _create_inventory_v62(cursor)
    legacy_cols = _pragma_columns(cursor, "inventory_legacy")
    now_iso = datetime.now().isoformat()

    if "item_name" in legacy_cols and "quantity" in legacy_cols:
        if "user_id" in legacy_cols:
            cols = ["user_id", "item_name", "quantity"]
            if "unit" in legacy_cols:
                cols.append("unit")
            if "updated_at" in legacy_cols:
                cols.append("updated_at")
            cursor.execute("SELECT " + ", ".join(cols) + " FROM inventory_legacy")
            for row in cursor.fetchall():
                d = dict(zip(cols, row))
                uid = d["user_id"]
                iname = d["item_name"]
                qty = d["quantity"]
                unit = d.get("unit")
                ut = d.get("updated_at")
                hid = (
                    str(uid).strip()
                    if uid is not None and str(uid).strip()
                    else household_id
                )
                u = str(unit).strip() if unit is not None else ""
                ts = str(ut) if ut is not None else now_iso
                cursor.execute(
                    """
                    INSERT INTO inventory (household_id, name, amount, unit, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (hid, str(iname).strip(), float(qty or 0), u, ts),
                )
        else:
            cols = ["item_name", "quantity"]
            if "unit" in legacy_cols:
                cols.append("unit")
            if "updated_at" in legacy_cols:
                cols.append("updated_at")
            cursor.execute("SELECT " + ", ".join(cols) + " FROM inventory_legacy")
            for row in cursor.fetchall():
                d = dict(zip(cols, row))
                iname = d["item_name"]
                qty = d["quantity"]
                unit = d.get("unit")
                ut = d.get("updated_at")
                u = str(unit).strip() if unit is not None else ""
                ts = str(ut) if ut is not None else now_iso
                cursor.execute(
                    """
                    INSERT INTO inventory (household_id, name, amount, unit, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (household_id, str(iname).strip(), float(qty or 0), u, ts),
                )
    else:
        cols = ["name", "amount", "unit"]
        if "updated_at" in legacy_cols:
            cols.append("updated_at")
        cursor.execute("SELECT " + ", ".join(cols) + " FROM inventory_legacy")
        for row in cursor.fetchall():
            if "updated_at" in legacy_cols:
                name, amount, unit, ut = row
            else:
                name, amount, unit = row
                ut = None
            u = str(unit).strip() if unit is not None else ""
            ts = str(ut) if ut is not None else now_iso
            cursor.execute(
                """
                INSERT INTO inventory (household_id, name, amount, unit, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (household_id, str(name).strip(), float(amount or 0), u, ts),
            )

    cursor.execute("DROP TABLE inventory_legacy")
    conn.commit()


class InventoryManager:
    """按 household_id（SCOPE_ID）隔离的 SQLite 库存。"""

    def __init__(
        self,
        db_path: Optional[str] = None,
        *,
        household_id: Optional[str] = None,
    ):
        settings = Settings()
        self.db_path = db_path or settings.get_inventory_db_path()
        self.household_id = (
            str(household_id).strip()
            if household_id is not None and str(household_id).strip()
            else settings.get_scope_id()
        )
        os.makedirs(
            os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else ".",
            exist_ok=True,
        )
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            _migrate_to_v62(conn, self.household_id)
        finally:
            conn.close()

    # ── 读取 ──────────────────────────────────────────────

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """
        获取当前 SCOPE 下全部库存（规格 §6.1 I 形态）。

        Returns:
            { "五花肉": {"amount": 500, "unit": "g"}, ... }
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, amount, unit FROM inventory WHERE household_id = ?",
            (self.household_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return {row[0]: {"amount": row[1], "unit": row[2]} for row in rows}

    def get_inventory_snapshot_i(self) -> Dict[str, Dict[str, Any]]:
        """
        FR-30 / 规格 §6.1：**I** 的规范快照 API。

        返回 ``Dict[食材名, {"amount": float, "unit": str}]``；查询带
        ``WHERE household_id = ?``（与 ``self.household_id`` / SCOPE_ID 一致）。
        """
        out: Dict[str, Dict[str, Any]] = {}
        for name, row in self.get_all().items():
            key = str(name).strip()
            if not key:
                continue
            try:
                amt = float(row.get("amount", 0))
            except (TypeError, ValueError):
                amt = 0.0
            out[key] = {"amount": amt, "unit": str(row.get("unit") or "")}
        return out

    def get_item(self, name: str) -> Optional[Dict[str, Any]]:
        """获取单个食材库存，不存在返回 None。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT amount, unit FROM inventory WHERE household_id = ? AND name = ?",
            (self.household_id, name),
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"amount": row[0], "unit": row[1]}
        return None

    # ── 写入 ──────────────────────────────────────────────

    def upsert(self, name: str, amount: float, unit: str) -> bool:
        """新增或更新单个食材。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            now = datetime.now().isoformat()
            cursor.execute(
                """
                INSERT INTO inventory (household_id, name, amount, unit, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(household_id, name) DO UPDATE SET
                    amount     = excluded.amount,
                    unit       = excluded.unit,
                    updated_at = excluded.updated_at
                """,
                (self.household_id, name, amount, unit, now),
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"inventory upsert error: {e}")
            return False
        finally:
            conn.close()

    def add_amount(self, name: str, delta: float, unit: str) -> bool:
        """在已有库存基础上增加数量，不存在则新建。"""
        existing = self.get_item(name)
        if existing is None:
            return self.upsert(name, delta, unit)
        return self.upsert(name, existing["amount"] + delta, existing["unit"])

    def deduct(self, name: str, amount: float, unit: str) -> bool:
        """扣减库存，不足则置为 0。"""
        existing = self.get_item(name)
        if existing is None:
            return True  # 库存里没有，跳过
        new_amount = max(0.0, existing["amount"] - amount)
        return self.upsert(name, new_amount, existing["unit"])

    def batch_upsert(self, items: List[Dict[str, Any]]) -> bool:
        """批量写入。items: [{"name":..., "amount":..., "unit":...}]"""
        return all(
            self.upsert(item["name"], item["amount"], item["unit"]) for item in items
        )

    def batch_deduct(self, items: List[Dict[str, Any]]) -> bool:
        """批量扣减库存。"""
        return all(
            self.deduct(item["name"], item["amount"], item["unit"]) for item in items
        )

    def batch_deduct_report(self, items: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
        """
        FR-32 / §6.4：逐条扣减并汇总 ``success`` | ``partial_success`` | ``failed``。

        仅对 ``name`` 非空且 ``amount>0`` 的行计入尝试次数；写库失败（upsert 失败）
        或无效数值记入 ``failed``。**规格 §6.4**：禁止对失败假装全体成功。
        """
        failed: List[str] = []
        attempted = 0
        for item in items:
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            try:
                amt = float(item.get("amount") or 0)
            except (TypeError, ValueError):
                failed.append(name)
                attempted += 1
                continue
            if amt <= 0:
                continue
            attempted += 1
            unit = str(item.get("unit") or "g").strip() or "g"
            ok = self.deduct(name, amt, unit)
            if not ok:
                failed.append(name)
        if attempted == 0:
            return "success", []
        if not failed:
            return "success", []
        if len(failed) < attempted:
            return "partial_success", failed
        return "failed", failed

    def apply_restock(
        self, name: str, delta_or_value: float, unit: str, merge_mode: str
    ) -> bool:
        """
        规格 §6.5.2：`merge_mode=add` 累加；`set` 设为绝对值。
        """
        mode = (merge_mode or "add").strip().lower()
        if mode == "set":
            return self.upsert(name, float(delta_or_value), str(unit))
        return self.add_amount(name, float(delta_or_value), str(unit))

    def delete_item(self, name: str) -> bool:
        """删除某个食材记录。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM inventory WHERE household_id = ? AND name = ?",
                (self.household_id, name),
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"inventory delete error: {e}")
            return False
        finally:
            conn.close()
