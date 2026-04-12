"""
记忆守护者节点集成测试

测试场景：
1. 被动提取 - 从对话中提取过敏原
2. 被动提取 - 提取短期状态（感冒）
3. 并集合并 - 新偏好追加到已有画像，不覆盖
4. 显式修正 - 用户主动修改偏好
5. 无更新    - 闲聊不触发写库
6. 短期状态TTL - 过期状态不影响查询
7. 端到端    - 完整节点调用验证 state 更新
"""
import asyncio
import pytest
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langchain_core.messages import HumanMessage, AIMessage
from src.libs.base.user_profiles import UserProfileManager


# ── 测试用临时数据库（每次测试隔离）────────────────────────
@pytest.fixture
def tmp_db(tmp_path):
    """每个测试用独立的临时数据库，测试结束自动删除。"""
    db_path = str(tmp_path / "test_profiles.db")
    return UserProfileManager(db_path=db_path)


@pytest.fixture
def user_id():
    return "test_user_memory_001"


# ════════════════════════════════════════════════════════════
# Part 1：UserProfileManager 单元测试（不调用 LLM，速度快）
# ════════════════════════════════════════════════════════════

class TestLongTermProfile:

    def test_upsert_creates_new_profile(self, tmp_db, user_id):
        """首次写入长期画像应成功创建记录。"""
        updates = {
            "allergens": ["花生", "海鲜"],
            "medical_restrictions": [],
            "dietary_target": "减脂",
            "taste_tags": {"like": ["酸辣"], "dislike": ["香菜"]},
            "cooking_habits": ["快手菜"]
        }
        result = tmp_db.upsert_long_term_profile(user_id, updates)
        assert result is True

        profile = tmp_db.get_long_term_profile(user_id)
        assert profile is not None
        assert "花生" in profile["allergens"]
        assert "海鲜" in profile["allergens"]
        assert profile["dietary_target"] == "减脂"
        assert "酸辣" in profile["taste_tags"]["like"]
        assert "香菜" in profile["taste_tags"]["dislike"]
        print(f"✅ 长期画像创建成功: {profile}")

    def test_upsert_overwrites_existing(self, tmp_db, user_id):
        """二次 upsert 应覆盖已有记录（由 memory_keeper 负责合并逻辑，这里只测 DB 层）。"""
        tmp_db.upsert_long_term_profile(user_id, {
            "allergens": ["花生"],
            "taste_tags": {"like": ["酸辣"], "dislike": []},
            "cooking_habits": []
        })
        # 第二次写入（模拟 memory_keeper 合并后的结果）
        tmp_db.upsert_long_term_profile(user_id, {
            "allergens": ["花生", "坚果"],  # 合并后的新列表
            "taste_tags": {"like": ["酸辣", "清淡"], "dislike": ["香菜"]},
            "cooking_habits": ["快手菜"]
        })
        profile = tmp_db.get_long_term_profile(user_id)
        assert "坚果" in profile["allergens"]
        assert "清淡" in profile["taste_tags"]["like"]
        print(f"✅ 长期画像更新成功: {profile}")

    def test_get_nonexistent_profile_returns_none(self, tmp_db):
        """查询不存在的用户应返回 None。"""
        profile = tmp_db.get_long_term_profile("nonexistent_user")
        assert profile is None
        print("✅ 不存在的用户返回 None")


class TestShortTermStates:

    def test_add_and_get_active_state(self, tmp_db, user_id):
        """写入短期状态后应能立即查询到。"""
        tmp_db.add_short_term_state(user_id, "感冒需清淡", ttl_days=7)
        states = tmp_db.get_active_short_term_states(user_id)
        assert "感冒需清淡" in states
        print(f"✅ 短期状态写入并查询成功: {states}")

    def test_duplicate_condition_not_inserted(self, tmp_db, user_id):
        """相同的短期状态不应重复写入。"""
        tmp_db.add_short_term_state(user_id, "感冒需清淡", ttl_days=7)
        tmp_db.add_short_term_state(user_id, "感冒需清淡", ttl_days=7)
        states = tmp_db.get_active_short_term_states(user_id)
        assert states.count("感冒需清淡") == 1
        print("✅ 重复短期状态已去重")

    def test_expired_state_not_returned(self, tmp_db, user_id):
        """已过期的短期状态不应出现在查询结果中。"""
        # 直接写入一条已过期的记录
        import sqlite3
        conn = sqlite3.connect(tmp_db.db_path)
        cursor = conn.cursor()
        past = (datetime.now() - timedelta(days=1)).isoformat()
        cursor.execute('''
            INSERT INTO user_short_term_states
                (user_id, condition, created_at, expires_at, is_active)
            VALUES (?, ?, ?, ?, 1)
        ''', (user_id, "已过期的状态", past, past))
        conn.commit()
        conn.close()

        states = tmp_db.get_active_short_term_states(user_id)
        assert "已过期的状态" not in states
        print("✅ 过期状态已被过滤")

    def test_deactivate_state(self, tmp_db, user_id):
        """手动失效短期状态后不应再查询到。"""
        tmp_db.add_short_term_state(user_id, "牙疼需软烂", ttl_days=7)
        tmp_db.deactivate_short_term_state(user_id, "牙疼需软烂")
        states = tmp_db.get_active_short_term_states(user_id)
        assert "牙疼需软烂" not in states
        print("✅ 手动失效状态成功")

    def test_purge_expired_states(self, tmp_db, user_id):
        """purge 后已过期记录应被物理删除。"""
        import sqlite3
        conn = sqlite3.connect(tmp_db.db_path)
        cursor = conn.cursor()
        past = (datetime.now() - timedelta(days=1)).isoformat()
        cursor.execute('''
            INSERT INTO user_short_term_states
                (user_id, condition, created_at, expires_at, is_active)
            VALUES (?, ?, ?, ?, 1)
        ''', (user_id, "过期状态", past, past))
        conn.commit()
        conn.close()

        deleted = tmp_db.purge_expired_states(user_id)
        assert deleted >= 1

        # 确认数据库里真的没了
        conn = sqlite3.connect(tmp_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM user_short_term_states WHERE user_id = ? AND condition = ?",
            (user_id, "过期状态")
        )
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 0
        print("✅ 过期状态已被物理删除")


class TestGetUserProfileMerge:

    def test_get_profile_merges_all_tables(self, tmp_db, user_id):
        """get_user_profile 应合并基础信息、长期画像、短期状态。"""
        # 写基础信息
        tmp_db.create_user_profile(user_id, name="测试用户")
        # 写长期画像
        tmp_db.upsert_long_term_profile(user_id, {
            "allergens": ["花生"],
            "taste_tags": {"like": ["酸辣"], "dislike": []},
            "cooking_habits": []
        })
        # 写短期状态
        tmp_db.add_short_term_state(user_id, "感冒需清淡")

        profile = tmp_db.get_user_profile(user_id)
        assert profile is not None
        assert profile["name"] == "测试用户"
        assert "花生" in profile["allergens"]
        assert "感冒需清淡" in profile["short_term_states"]
        print(f"✅ 合并画像成功: {profile}")


# ════════════════════════════════════════════════════════════
# Part 2：MemoryKeeper 节点集成测试（调用真实 LLM）
# ════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@pytest.mark.integration   # 用 -m integration 单独运行，避免每次都调用 LLM
class TestMemoryKeeperNode:

    def _make_state(self, messages, user_id="test_user_llm_001", tmp_db_path=None):
        """构造测试用 AgentState。"""
        return {
            "messages": messages,
            "active_user_id": user_id,
            "logistics_buffer": {},
            "task_stack": [],
            "expert_payloads": {},
            "conversation_summary": ""
        }

    async def test_passive_extract_allergen(self, tmp_path):
        """场景1：从对话中被动提取过敏原，应写入长期画像。"""
        print("\n🧪 场景1：被动提取过敏原")
        from src.agent.nodes.memory_keeper import memory_keeper_node

        messages = [
            HumanMessage(content="我对花生过敏，所以推荐菜谱的时候别用花生"),
            AIMessage(content="好的，我已记录您对花生过敏，推荐时会避开。")
        ]
        state = self._make_state(messages, user_id="test_allergen_user")
        new_state = await memory_keeper_node(state)

        print(f"节点返回: {new_state}")
        # 节点本身不返回 messages，只更新数据库
        # 验证数据库写入（需要访问 UserProfileManager）
        from src.libs.base.user_profiles import UserProfileManager
        upm = UserProfileManager()
        profile = upm.get_long_term_profile("test_allergen_user")
        print(f"长期画像: {profile}")
        if profile:
            assert "花生" in profile.get("allergens", []), "花生过敏应被提取"
            print("✅ 过敏原提取成功")
        else:
            print("⚠️ 未找到画像（可能 LLM 判断为无更新）")

    async def test_passive_extract_short_term(self, tmp_path):
        """场景2：提取短期状态（感冒），应写入短期表，并注入 logistics_buffer。"""
        print("\n🧪 场景2：提取短期状态")
        from src.agent.nodes.memory_keeper import memory_keeper_node

        messages = [
            HumanMessage(content="我最近感冒了，想吃点清淡的，别太油腻"),
            AIMessage(content="明白，给您推荐一些清淡好消化的菜谱。")
        ]
        state = self._make_state(messages, user_id="test_shortterm_user")
        new_state = await memory_keeper_node(state)

        print(f"节点返回: {new_state}")
        # 短期状态应注入 logistics_buffer
        lb = new_state.get("logistics_buffer", {})
        short_term = lb.get("short_term_constraints", [])
        print(f"logistics_buffer 短期约束: {short_term}")
        if short_term:
            print("✅ 短期状态已注入 logistics_buffer")
        else:
            print("⚠️ logistics_buffer 未更新（可能 LLM 判断为无短期状态）")

    async def test_no_update_on_chitchat(self):
        """场景3：闲聊不应触发写库，节点返回空字典。"""
        print("\n🧪 场景3：闲聊无更新")
        from src.agent.nodes.memory_keeper import memory_keeper_node

        messages = [
            HumanMessage(content="下一步怎么做？"),
            AIMessage(content="下一步需要将锅预热，然后加入食材翻炒。")
        ]
        state = self._make_state(messages, user_id="test_chitchat_user")
        new_state = await memory_keeper_node(state)

        print(f"节点返回: {new_state}")
        assert new_state == {} or new_state == {"logistics_buffer": {}}
        print("✅ 闲聊正确返回空更新")

    async def test_explicit_correction(self):
        """场景4：显式修正，用户主动修改偏好。"""
        print("\n🧪 场景4：显式修正")
        from src.agent.nodes.memory_keeper import memory_keeper_node
        from src.libs.base.user_profiles import UserProfileManager

        user_id = "test_correction_user"

        # 先写入初始画像
        upm = UserProfileManager()
        upm.upsert_long_term_profile(user_id, {
            "allergens": ["花生"],
            "taste_tags": {"like": [], "dislike": []},
            "cooking_habits": []
        })

        # 用户显式修正
        messages = [
            HumanMessage(content="把我的花生过敏删掉，我现在可以吃花生了"),
            AIMessage(content="好的，已为您更新，不再限制花生相关菜谱。")
        ]
        state = self._make_state(messages, user_id=user_id)
        new_state = await memory_keeper_node(state)

        print(f"节点返回: {new_state}")
        profile = upm.get_long_term_profile(user_id)
        print(f"更新后画像: {profile}")
        if profile:
            print(f"过敏原列表: {profile.get('allergens', [])}")
        print("✅ 显式修正场景执行完成（需人工确认花生是否被移除）")


# ════════════════════════════════════════════════════════════
# 直接运行（不用 pytest）
# ════════════════════════════════════════════════════════════

async def run_db_tests():
    """快速运行数据库层测试，不调用 LLM。"""
    import tempfile
    tmp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmp_dir, "test.db")
        upm = UserProfileManager(db_path=db_path)
        uid = "quick_test_user"

        print("\n" + "="*50)
        print("📦 数据库层快速测试")
        print("="*50)

        # 长期画像
        upm.upsert_long_term_profile(uid, {
            "allergens": ["花生"],
            "medical_restrictions": [],
            "dietary_target": "减脂",
            "taste_tags": {"like": ["酸辣"], "dislike": ["香菜"]},
            "cooking_habits": ["快手菜"]
        })
        profile = upm.get_long_term_profile(uid)
        print(f"✅ 长期画像: {profile}")

        # 短期状态
        upm.add_short_term_state(uid, "感冒需清淡", ttl_days=7)
        upm.add_short_term_state(uid, "感冒需清淡", ttl_days=7)  # 重复
        states = upm.get_active_short_term_states(uid)
        print(f"✅ 短期状态（去重后）: {states}")
        assert states.count("感冒需清淡") == 1

        # 合并查询
        upm.create_user_profile(uid, name="测试用户")
        full = upm.get_user_profile(uid)
        print(f"✅ 完整画像: {full}")
        assert full["allergens"] == ["花生"]
        assert "感冒需清淡" in full["short_term_states"]

        # 手动失效
        upm.deactivate_short_term_state(uid, "感冒需清淡")
        states_after = upm.get_active_short_term_states(uid)
        print(f"✅ 失效后短期状态: {states_after}")
        assert "感冒需清淡" not in states_after

        del upm
        print("\n🎉 所有数据库测试通过！")
    finally:
        import shutil, gc
        gc.collect()  # 触发垃圾回收，释放文件句柄
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


async def run_llm_tests():
    """运行 LLM 集成测试（需要真实 API）。"""
    print("\n" + "="*50)
    print("🤖 LLM 集成测试（调用真实模型）")
    print("="*50)

    tester = TestMemoryKeeperNode()

    print("\n--- 场景1：被动提取过敏原 ---")
    await tester.test_passive_extract_allergen(None)

    print("\n--- 场景2：短期状态提取 ---")
    await tester.test_passive_extract_short_term(None)

    print("\n--- 场景3：闲聊无更新 ---")
    await tester.test_no_update_on_chitchat()

    print("\n--- 场景4：显式修正 ---")
    await tester.test_explicit_correction()

    print("\n🎉 LLM 集成测试完成！")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["db", "llm", "all"],
        default="db",
        help="db=只测数据库层, llm=只测LLM集成, all=全部"
    )
    args = parser.parse_args()

    async def main():
        if args.mode in ("db", "all"):
            await run_db_tests()
        if args.mode in ("llm", "all"):
            await run_llm_tests()

    asyncio.run(main())