"""
User Profile Manager for WHAT-TO-EAT-AGENT
 
表结构设计：
- user_profiles:            原始用户基础信息（姓名、邮箱等），保持兼容
- user_long_term_profile:   记忆守护者写入的长期饮食画像（过敏、偏好、目标）
- user_short_term_states:   带 TTL 的短期状态（感冒、牙疼等），自动过期
"""
import sqlite3
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

# 短期状态默认存活天数
DEFAULT_SHORT_TERM_TTL_DAYS = 7


class UserProfileManager:
    """Manages user profiles including preferences, dietary restrictions, and personal information."""

    def __init__(self, db_path: str = "data/db/user_profiles.db"):
        self.db_path = db_path
        os.makedirs(
            os.path.dirname(db_path) if os.path.dirname(db_path) else '.',
            exist_ok=True
        )
        self._init_db()

    # ─────────────────────────────────────────────────────────
    # 初始化
    # ─────────────────────────────────────────────────────────
 
    def _init_db(self):
        """建表，三张表放在同一个 SQLite 文件里。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
 
        # 原始基础信息表user_profiles（保持兼容）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                dietary_restrictions TEXT,
                preferred_cuisines TEXT,
                disliked_foods TEXT,
                cooking_experience TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
 
        # 长期饮食画像表user_long_term_profile（memory_keeper 写入，永久保存）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_long_term_profile (
                user_id             TEXT PRIMARY KEY,
                allergens           TEXT DEFAULT '[]',
                medical_restrictions TEXT DEFAULT '[]',
                dietary_target      TEXT DEFAULT '',
                taste_like          TEXT DEFAULT '[]',
                taste_dislike       TEXT DEFAULT '[]',
                cooking_habits      TEXT DEFAULT '[]',
                created_at          TEXT NOT NULL,
                last_updated        TEXT NOT NULL
            )
        ''')
 
        # 短期状态表user_short_term_states（带 TTL，自动过期）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_short_term_states (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT NOT NULL,
                condition   TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                expires_at  TEXT NOT NULL,
                is_active   INTEGER DEFAULT 1
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON user_profiles(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_lt_user_id ON user_long_term_profile(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_st_user_id ON user_short_term_states(user_id)')
 
        conn.commit()
        conn.close()

    def create_user_profile(self,
                            user_id: str,
                            name: str,
                            dietary_restrictions: Optional[List[str]] = None,
                            preferred_cuisines: Optional[List[str]] = None,
                            disliked_foods: Optional[List[str]] = None,
                            cooking_experience: str = "intermediate") -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO user_profiles
                (user_id, name, dietary_restrictions, preferred_cuisines, disliked_foods, cooking_experience)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, name, 
                json.dumps(dietary_restrictions or []),
                json.dumps(preferred_cuisines or []),
                json.dumps(disliked_foods or []),
                cooking_experience
            ))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        except Exception as e:
            print(f"Error creating user profile: {e}")
            return False
        finally:
            conn.close()

    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用户完整画像：基础信息 + 长期画像 + 未过期的短期状态。
        返回合并后的字典，供 researcher 节点直接使用。
        """
        basic = self._get_basic_profile(user_id)
        long_term = self.get_long_term_profile(user_id)
        short_term = self.get_active_short_term_states(user_id)
 
        if not basic and not long_term:
            return None
 
        result = basic or {"user_id": user_id}
        if long_term:
            result.update(long_term)
        result["short_term_states"] = short_term
        return result
 
    def _get_basic_profile(self, user_id: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, name, dietary_restrictions,
                   preferred_cuisines, disliked_foods, cooking_experience,
                   created_at, updated_at
            FROM user_profiles WHERE user_id = ?
        ''', (user_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {
            'user_id': row[0],
            'name': row[1],
            'dietary_restrictions': json.loads(row[2]) if row[2] else [],
            'preferred_cuisines': json.loads(row[3]) if row[3] else [],
            'disliked_foods': json.loads(row[4]) if row[4] else [],
            'cooking_experience': row[5],
            'created_at': row[6],
            'updated_at': row[7],
        }
    
    def update_user_profile(self,
                            user_id: str,
                            name: Optional[str] = None,
                            dietary_restrictions: Optional[List[str]] = None,
                            preferred_cuisines: Optional[List[str]] = None,
                            disliked_foods: Optional[List[str]] = None,
                            cooking_experience: Optional[str] = None) -> bool:
        current = self._get_basic_profile(user_id)
        if not current:
            return False
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            update_fields, params = [], []
            for field, value in [
                ('name', name),
                ('dietary_restrictions', json.dumps(dietary_restrictions) if dietary_restrictions is not None else None),
                ('preferred_cuisines', json.dumps(preferred_cuisines) if preferred_cuisines is not None else None),
                ('disliked_foods', json.dumps(disliked_foods) if disliked_foods is not None else None),
                ('cooking_experience', cooking_experience),
            ]:
                if value is not None:
                    update_fields.append(f"{field} = ?")
                    params.append(value)
 
            if not update_fields:
                return False
 
            params.extend([datetime.now().isoformat(), user_id])
            cursor.execute(
                f"UPDATE user_profiles SET {', '.join(update_fields)}, updated_at = ? WHERE user_id = ?",
                params
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating user profile: {e}")
            return False
        finally:
            conn.close()
 
    def delete_user_profile(self, user_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM user_profiles WHERE user_id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting user profile: {e}")
            return False
        finally:
            conn.close()

    def get_all_users(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, name, dietary_restrictions,
                   preferred_cuisines, disliked_foods, cooking_experience,
                   created_at, updated_at
            FROM user_profiles ORDER BY created_at DESC
        ''')
        rows = cursor.fetchall()
        conn.close()
        return [{
            'user_id': r[0], 'name': r[1], 
            'dietary_restrictions': json.loads(r[2]) if r[2] else [],
            'preferred_cuisines': json.loads(r[3]) if r[3] else [],
            'disliked_foods': json.loads(r[4]) if r[4] else [],
            'cooking_experience': r[5], 'created_at': r[6], 'updated_at': r[7],
        } for r in rows]
    
   # ─────────────────────────────────────────────────────────
    # 长期画像接口（memory_keeper 调用）
    # ─────────────────────────────────────────────────────────
 
    def get_long_term_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """读取长期画像，返回结构化字典。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT allergens, medical_restrictions, dietary_target,
                   taste_like, taste_dislike, cooking_habits, last_updated
            FROM user_long_term_profile WHERE user_id = ?
        ''', (user_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {
            'allergens': json.loads(row[0]) if row[0] else [],
            'medical_restrictions': json.loads(row[1]) if row[1] else [],
            'dietary_target': row[2] or '',
            'taste_tags': {
                'like': json.loads(row[3]) if row[3] else [],
                'dislike': json.loads(row[4]) if row[4] else [],
            },
            'cooking_habits': json.loads(row[5]) if row[5] else [],
            'last_updated': row[6],
        }
 
    def upsert_long_term_profile(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """
        写入或更新长期画像（UPSERT）。
        updates 结构与 MemoryKeeperOutput.long_term_updates 的 model_dump() 一致：
        {
            "allergens": [...],
            "medical_restrictions": [...],
            "dietary_target": "...",
            "taste_tags": {"like": [...], "dislike": [...]},
            "cooking_habits": [...]
        }
        """
        now = datetime.now().isoformat()
        taste = updates.get("taste_tags", {})
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO user_long_term_profile
                    (user_id, allergens, medical_restrictions, dietary_target,
                     taste_like, taste_dislike, cooking_habits, created_at, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    allergens            = excluded.allergens,
                    medical_restrictions = excluded.medical_restrictions,
                    dietary_target       = excluded.dietary_target,
                    taste_like           = excluded.taste_like,
                    taste_dislike        = excluded.taste_dislike,
                    cooking_habits       = excluded.cooking_habits,
                    last_updated         = excluded.last_updated
            ''', (
                user_id,
                json.dumps(updates.get("allergens", []), ensure_ascii=False),
                json.dumps(updates.get("medical_restrictions", []), ensure_ascii=False),
                updates.get("dietary_target", ""),
                json.dumps(taste.get("like", []), ensure_ascii=False),
                json.dumps(taste.get("dislike", []), ensure_ascii=False),
                json.dumps(updates.get("cooking_habits", []), ensure_ascii=False),
                now, now
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error upserting long term profile: {e}")
            return False
        finally:
            conn.close()
 
    # ─────────────────────────────────────────────────────────
    # 短期状态接口（memory_keeper 调用）
    # ─────────────────────────────────────────────────────────
 
    def add_short_term_state(
        self,
        user_id: str,
        condition: str,
        ttl_days: int = DEFAULT_SHORT_TERM_TTL_DAYS
    ) -> bool:
        """
        写入一条短期状态，自动计算过期时间。
        如果相同 condition 已存在且未过期，跳过重复写入。
        """
        now = datetime.now()
        expires_at = (now + timedelta(days=ttl_days)).isoformat()
 
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # 检查是否已有未过期的相同状态
            cursor.execute('''
                SELECT id FROM user_short_term_states
                WHERE user_id = ? AND condition = ? AND expires_at > ? AND is_active = 1
            ''', (user_id, condition, now.isoformat()))
            if cursor.fetchone():
                return True  # 已存在，跳过
 
            cursor.execute('''
                INSERT INTO user_short_term_states
                    (user_id, condition, created_at, expires_at, is_active)
                VALUES (?, ?, ?, ?, 1)
            ''', (user_id, condition, now.isoformat(), expires_at))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding short term state: {e}")
            return False
        finally:
            conn.close()
 
    def get_active_short_term_states(self, user_id: str) -> List[str]:
        """
        获取用户所有未过期的短期状态，返回 condition 字符串列表。
        同时自动将已过期的记录标记为 is_active=0（懒清理）。
        """
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # 懒清理：标记过期记录
            cursor.execute('''
                UPDATE user_short_term_states
                SET is_active = 0
                WHERE user_id = ? AND expires_at <= ? AND is_active = 1
            ''', (user_id, now))
 
            # 读取有效状态
            cursor.execute('''
                SELECT condition FROM user_short_term_states
                WHERE user_id = ? AND expires_at > ? AND is_active = 1
                ORDER BY created_at DESC
            ''', (user_id, now))
            rows = cursor.fetchall()
            conn.commit()
            return [row[0] for row in rows]
        except Exception as e:
            print(f"Error getting short term states: {e}")
            return []
        finally:
            conn.close()
 
    def deactivate_short_term_state(self, user_id: str, condition: str) -> bool:
        """手动使某条短期状态失效（用于用户说"我已经好了"）。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE user_short_term_states
                SET is_active = 0
                WHERE user_id = ? AND condition = ? AND is_active = 1
            ''', (user_id, condition))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deactivating short term state: {e}")
            return False
        finally:
            conn.close()
 
    def purge_expired_states(self, user_id: Optional[str] = None) -> int:
        """
        物理删除所有已过期的短期状态（可定期调用做真正的清理）。
        user_id 为 None 时清理所有用户。
        返回删除的行数。
        """
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            if user_id:
                cursor.execute('''
                    DELETE FROM user_short_term_states
                    WHERE user_id = ? AND (expires_at <= ? OR is_active = 0)
                ''', (user_id, now))
            else:
                cursor.execute('''
                    DELETE FROM user_short_term_states
                    WHERE expires_at <= ? OR is_active = 0
                ''', (now,))
            conn.commit()
            return cursor.rowcount
        except Exception as e:
            print(f"Error purging expired states: {e}")
            return 0
        finally:
            conn.close()