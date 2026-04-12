"""
InventoryManager - 厨房库存管理
 
表结构：
  inventory
    name       TEXT PRIMARY KEY  食材名称
    amount     REAL              当前数量
    unit       TEXT              单位
    updated_at TEXT
"""
import sqlite3
import os
from typing import Dict, List, Optional, Any
from datetime import datetime


class InventoryManager:
    """Manages user's ingredient inventory including quantities, expiration dates, and categories."""

    def __init__(self, db_path: str = "data/db/inventory.db"):
        """
        Initialize the InventoryManager.

        Args:
            db_path: Path to the SQLite database for storing inventory
        """
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                name       TEXT PRIMARY KEY,
                amount     REAL NOT NULL DEFAULT 0,
                unit       TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

    # ── 读取 ──────────────────────────────────────────────
 
    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """
        获取用户全部库存。
 
        Returns:
            { "五花肉": {"amount": 500, "unit": "g"}, ... }
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, amount, unit FROM inventory"
        )
        rows = cursor.fetchall()
        conn.close()
        return {row[0]: {"amount": row[1], "unit": row[2]} for row in rows}

    def get_item(self, name: str) -> Optional[Dict[str, Any]]:
        """获取单个食材库存，不存在返回 None。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT amount, unit FROM inventory WHERE name = ?", (name,)
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
            cursor.execute('''
                INSERT INTO inventory (name, amount, unit, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    amount     = excluded.amount,
                    unit       = excluded.unit,
                    updated_at = excluded.updated_at
            ''', (name, amount, unit, datetime.now().isoformat()))
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
            self.upsert(item["name"], item["amount"], item["unit"])
            for item in items
        )
 
    def batch_deduct(self, items: List[Dict[str, Any]]) -> bool:
        """批量扣减库存。"""
        return all(
            self.deduct(item["name"], item["amount"], item["unit"])
            for item in items
        )
 
    def delete_item(self, name: str) -> bool:
        """删除某个食材记录。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM inventory WHERE name = ?", (name,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"inventory delete error: {e}")
            return False
        finally:
            conn.close()
 