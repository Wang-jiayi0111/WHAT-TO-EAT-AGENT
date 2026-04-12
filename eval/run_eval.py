"""
膳食助手评估框架

运行方式：
  python eval/run_eval.py --level all        # 全部评估
  python eval/run_eval.py --level l1         # 只评估意图识别
  python eval/run_eval.py --level l2         # 只评估检索质量
  python eval/run_eval.py --level l3         # 只评估记忆与库存
  python eval/run_eval.py --level l4         # 只评估端到端
"""

import asyncio
import json
import sys
import argparse
import tempfile
import os
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field, asdict

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


# ════════════════════════════════════════════════════════════
# 数据结构
# ════════════════════════════════════════════════════════════

INTENT_TASK_MAPPING = {
    "profile_sync": "TASK_PROFILE_SYNC",
    "recipe_search": "TASK_SEARCH",
    "inventory_check": "TASK_INV_CHECK",
    "inventory_commit": "TASK_INV_COMMIT",
    "inventory_add": "TASK_INV_ADD",
    "shopping_list": "TASK_GAP_CALC",
    "user_clarify": "TASK_CLARIFY",
    "general_chat": "TASK_DIRECT_REPLY"
}

@dataclass
class EvalResult:
    level: str
    metric: str
    score: float
    detail: Dict = field(default_factory=dict)
    passed: bool = True
    latency_ms: Optional[float] = None  # ✅ 新增


@dataclass
class EvalReport:
    timestamp: str
    results: List[EvalResult] = field(default_factory=list)

    def add(self, result: EvalResult):
        self.results.append(result)

    def summary(self) -> Dict:
        by_level = {}
        for r in self.results:
            by_level.setdefault(r.level, []).append(r.score)
        return {
            level: round(sum(scores) / len(scores), 3)
            for level, scores in by_level.items()
        }

    def print(self):
        print("\n" + "=" * 60)
        print(f"评估报告  {self.timestamp}")
        print("=" * 60)
        for r in self.results:
            status = "✅" if r.passed else "❌"
            latency_str = f" | ⏱ {r.latency_ms:.0f}ms" if r.latency_ms is not None else ""  # ✅ 新增
            print(f"{status} [{r.level}] {r.metric}: {r.score:.3f}{latency_str}")
            if r.detail:
                for k, v in r.detail.items():
                    print(f"     {k}: {v}")

        print("\n汇总分数：")
        for level, avg in self.summary().items():
            print(f"  {level}: {avg:.3f}")
        print("=" * 60)

    def save(self, path: str = "eval/report.json"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {"timestamp": self.timestamp,
                 "summary": self.summary(),
                 "results": [asdict(r) for r in self.results]},
                f, ensure_ascii=False, indent=2
            )
        print(f"\n报告已保存: {path}")


# ════════════════════════════════════════════════════════════
# L1：意图识别评估
# ════════════════════════════════════════════════════════════

# 测试用例：(用户输入, 期望意图列表, 期望实体关键词)
L1_TEST_CASES = [
    # 明确菜谱搜索
    ("红烧肉怎么做",          ["recipe_search"],          {"recipe_name": "红烧肉"}),
    ("帮我找个番茄炒蛋的菜谱", ["recipe_search"],          {"recipe_name": "番茄炒蛋"}),
    ("我想吃清蒸鱼",           ["recipe_search"],          {"recipe_name": "清蒸鱼"}),

    # 模糊饮食需求（需要查询改写）
    ("最近感冒了想吃清淡的",   ["recipe_search"],          {}),
    ("减脂期间吃什么好",       ["recipe_search"],          {}),
    ("想吃点下饭的辣菜",       ["recipe_search"],          {}),

    # 库存查询
    ("家里还有什么食材",       ["inventory_check"],        {}),
    ("冰箱里有鸡蛋吗",         ["inventory_check"],        {"ingredients": ["鸡蛋"]}),
    ("我的食材库存",           ["inventory_check"],        {}),

    # 补货入库
    ("刚买了半斤五花肉",       ["inventory_add"],          {"ingredients": ["五花肉"]}),
    ("买了两根胡萝卜和一盒鸡蛋", ["inventory_add"],        {"ingredients": ["胡萝卜", "鸡蛋"]}),
    ("超市买回来一袋大米",     ["inventory_add"],          {"ingredients": ["大米"]}),

    # 烹饪确认扣减
    ("红烧肉做好了",           ["inventory_commit"],       {"recipe_name": "红烧肉"}),
    ("刚才的清蒸鱼做完了",     ["inventory_commit"],       {"recipe_name": "清蒸鱼"}),

    # 偏好同步
    ("我不吃香菜",             ["profile_sync"],           {}),
    ("我对花生过敏",           ["profile_sync"],           {}),
    ("最近在减脂",             ["profile_sync"],           {}),

    # 购物清单
    ("帮我列出做红烧肉还缺什么", ["recipe_search", "shopping_list"], {"recipe_name": "红烧肉"}),

    # 闲聊
    ("你好",                   ["general_chat"],           {}),
    ("今天天气真好",           ["general_chat"],           {}),

    # 边界：买了食材 + 想做菜（多意图）
    ("买了猪肉想做红烧肉",     ["inventory_add", "recipe_search"], {"recipe_name": "红烧肉"}),

    ("我最近开始减肥了，推荐一道低脂的菜", ["profile_sync", "recipe_search"], {}),

    # 2. 偏好更新 + 库存添加
    ("医生说我尿酸高不能吃海鲜了。对了，我刚买了两斤排骨回来", ["profile_sync", "inventory_add"], {"ingredients": ["排骨"]}),

    # 3. 菜谱完成扣减 + 偏好更新（用户反馈）
    ("红烧肉做完了，不过我不喜欢吃太甜的，以后我的菜谱里少放糖", ["inventory_commit", "profile_sync"], 
     {"recipe_name": "红烧肉"}),

    # 4. 库存添加 + 库存查询
    ("我买了一袋大米，你顺便帮我查查家里还有没有鸡蛋", ["inventory_add", "inventory_check"], {"ingredients": ["大米", "鸡蛋"]}),

    # 5. 菜谱搜索 + 购物清单计算
    ("晚上想做个糖醋排骨，帮我看看家里食材够不够，不够的列个单子", 
     ["recipe_search", "shopping_list"], 
     {"recipe_name": "糖醋排骨"}),
]


async def eval_l1(report: EvalReport):
    """L1：意图识别准确率评估"""
    print("\n[L1] 评估意图识别...")

    from src.agent.nodes.router import IntentClassifier
    from langchain_core.messages import HumanMessage

    classifier = IntentClassifier()

    intent_correct = 0
    entity_scores = []
    false_clarify = 0
    total = len(L1_TEST_CASES)

    errors = []
    for user_input, expected_intents, expected_entities in L1_TEST_CASES:
        state = {
            "messages": [HumanMessage(content=user_input)],
            "active_user_id": "eval_user",
            "logistics_buffer": {"extracted_entities": {}},
            "task_stack": [],
        }
        try:
            result = classifier.get_intent_details(state)
            predicted_intent = result.get("intent", "general_chat")
            predicted_tasks = result.get("task_stack", [])
            predicted_entities = result.get("entities", {})

            expected_tasks = [INTENT_TASK_MAPPING.get(i) for i in expected_intents]
            is_intent_perfect = all(task in predicted_tasks for task in expected_tasks)

            # 意图准确：预测意图在期望列表里
            if is_intent_perfect:
                intent_correct += 1
            else:
                errors.append({
                    "input": user_input,
                    "expected": expected_intents,
                    "got": predicted_tasks
                })

            # 实体提取：期望实体关键词是否出现在预测实体中
            if expected_entities:
                matched = 0
                for key, val in expected_entities.items():
                    pred_val = predicted_entities.get(key)
                    if isinstance(val, list) and isinstance(pred_val, list):
                        # 检查每个期望元素是否在预测列表里
                        matched += sum(1 for v in val if v in pred_val) / len(val)
                    elif val and pred_val and str(val) in str(pred_val):
                        matched += 1
                entity_scores.append(matched / len(expected_entities))
            else:
                entity_scores.append(1.0)  # 无期望实体，视为满分

            # 不必要的歧义触发
            if "TASK_CLARIFY" in predicted_tasks and "TASK_CLARIFY" not in [
                t for intent in expected_intents
                for t in (["TASK_CLARIFY"] if intent == "user_clarify" else [])
            ]:
                false_clarify += 1

        except Exception as e:
            errors.append({"input": user_input, "error": str(e)})
            entity_scores.append(0.0)

    intent_acc = intent_correct / total
    entity_f1 = sum(entity_scores) / len(entity_scores)
    false_clarify_rate = false_clarify / total

    report.add(EvalResult("L1", "意图分类准确率", intent_acc,
                           {"正确": intent_correct, "总数": total, "错误样例": errors[:3]}))
    report.add(EvalResult("L1", "实体提取 F1", entity_f1,
                           {"平均得分": round(entity_f1, 3)}))
    report.add(EvalResult("L1", "歧义误触发率", 1 - false_clarify_rate,
                           {"误触发次数": false_clarify, "总数": total},
                           passed=false_clarify_rate < 0.1))

    print(f"  意图准确率: {intent_acc:.3f} ({intent_correct}/{total})")
    print(f"  实体提取 F1: {entity_f1:.3f}")
    print(f"  歧义误触发率: {false_clarify_rate:.3f}")


# ════════════════════════════════════════════════════════════
# L3：记忆与库存准确性评估
# ════════════════════════════════════════════════════════════

async def eval_l3(report: EvalReport):
    """L3：记忆管理 + 库存计算准确性"""
    print("\n[L3] 评估记忆与库存管理...")

    from src.libs.base.inventory import InventoryManager
    from src.libs.utils.unit_converter import UnitConverter
    from src.libs.base.user_profiles import UserProfileManager

    tmp_db = tempfile.mktemp(suffix=".db")
    tmp_profile_db = tempfile.mktemp(suffix=".db")

    try:
        # ── 3.1 库存扣减准确性 ──────────────────────────────
        inv = InventoryManager(db_path=tmp_db)
        inv.upsert("五花肉", 500, "g")
        inv.upsert("酱油", 100, "ml")
        inv.upsert("鸡蛋", 6, "个")

        inv.batch_deduct([
            {"name": "五花肉", "amount": 300, "unit": "g"},
            {"name": "酱油",   "amount": 30,  "unit": "ml"},
            {"name": "鸡蛋",   "amount": 2,   "unit": "个"},
        ])

        deduct_cases = [
            ("五花肉", 200, "g"),
            ("酱油",   70,  "ml"),
            ("鸡蛋",   4,   "个"),
        ]
        deduct_correct = sum(
            1 for name, expected, _ in deduct_cases
            if abs(inv.get_item(name)["amount"] - expected) < 0.01
        )
        deduct_acc = deduct_correct / len(deduct_cases)

        # ── 3.2 购物清单缺口计算 ────────────────────────────
        uc = UnitConverter()
        gap_cases = [
            # (需求量, 需求单位, 库存量, 库存单位, 期望缺口, 期望单位)
            (500, "g",  200, "g",   300, "g"),
            (1,   "kg", 800, "g",   200, "g"),
            (3,   "个", 5,   "个",  0,   "个"),   # 充足
            (2,   "汤匙", 40, "ml", 0,   "ml"),   # 2汤匙=30ml < 40ml
        ]
        gap_correct = 0
        for req_a, req_u, avail_a, avail_u, exp_gap, _ in gap_cases:
            got_gap, _ = uc.gap(req_a, req_u, avail_a, avail_u)
            if abs(got_gap - exp_gap) < 0.5:
                gap_correct += 1
        gap_acc = gap_correct / len(gap_cases)

        # ── 3.3 TTL 过期状态不干扰 ──────────────────────────
        from datetime import timedelta
        import sqlite3

        upm = UserProfileManager(db_path=tmp_profile_db)
        upm.add_short_term_state("eval_user", "感冒需清淡", ttl_days=7)

        # 写入一条已过期状态
        conn = sqlite3.connect(tmp_profile_db)
        cursor = conn.cursor()
        past = (datetime.now() - timedelta(days=1)).isoformat()
        cursor.execute(
            "INSERT INTO user_short_term_states (user_id, condition, created_at, expires_at, is_active) VALUES (?,?,?,?,1)",
            ("eval_user", "已过期状态", past, past)
        )
        conn.commit()
        conn.close()

        active = upm.get_active_short_term_states("eval_user")
        ttl_ok = "已过期状态" not in active and "感冒需清淡" in active

        # ── 3.4 长期偏好写入与读取 ──────────────────────────
        upm.upsert_long_term_profile("eval_user", {
            "allergens": ["花生", "海鲜"],
            "taste_tags": {"like": ["清淡"], "dislike": ["香菜"]},
            "cooking_habits": ["快手菜"],
            "medical_restrictions": [],
        })
        profile = upm.get_long_term_profile("eval_user")
        profile_ok = (
            profile is not None and
            "花生" in profile.get("allergens", []) and
            "香菜" in profile.get("taste_tags", {}).get("dislike", [])
        )

        report.add(EvalResult("L3", "库存扣减准确率", deduct_acc,
                               {"正确": deduct_correct, "总数": len(deduct_cases)}))
        report.add(EvalResult("L3", "购物缺口计算准确率", gap_acc,
                               {"正确": gap_correct, "总数": len(gap_cases)}))
        report.add(EvalResult("L3", "TTL 过期状态过滤", 1.0 if ttl_ok else 0.0,
                               {"活跃状态": active}, passed=ttl_ok))
        report.add(EvalResult("L3", "长期偏好写入读取", 1.0 if profile_ok else 0.0,
                               {"画像": profile}, passed=profile_ok))

        print(f"  库存扣减准确率: {deduct_acc:.3f}")
        print(f"  购物缺口计算准确率: {gap_acc:.3f}")
        print(f"  TTL 过期过滤: {'通过' if ttl_ok else '失败'}")
        print(f"  长期偏好读写: {'通过' if profile_ok else '失败'}")

    finally:
        for p in [tmp_db, tmp_profile_db]:
            try:
                os.remove(p)
            except Exception:
                pass


# ════════════════════════════════════════════════════════════
# L4：端到端评估
# ════════════════════════════════════════════════════════════

# 每个场景：(场景名, 对话轮列表, 成功判断函数)
async def eval_l4(report: EvalReport):
    """L4：端到端对话流评估"""
    print("\n[L4] 评估端到端对话...")

    from src.agent.workflow import create_agent, run_turn

    agent = create_agent(persist=True)
    scenarios = [
        {
            "name": "直接菜谱搜索",
            "turns": ["红烧肉怎么做"],
            "success": lambda replies: any(
                "红烧肉" in r or "五花肉" in r or "步骤" in r
                for r in replies
            ),
        },
        {
            "name": "模糊需求推荐",
            "turns": ["感冒了想吃清淡的"],
            "success": lambda replies: any(
                any(kw in r for kw in ["汤", "粥", "清淡", "蔬菜", "菜谱"])
                for r in replies
            ),
        },
        {
            "name": "补货入库流程",
            "turns": ["买了500克五花肉"],
            "success": lambda replies: any(
                any(kw in r for kw in ["添加", "库存", "五花肉", "记录"])
                for r in replies
            ),
        },
        {
            "name": "库存查询",
            "turns": ["家里有什么食材"],
            "success": lambda replies: any(
                any(kw in r for kw in ["库存", "食材", "克", "个", "空的"])
                for r in replies
            ),
        },
        {
            "name": "偏好记忆",
            "turns": ["我不吃香菜", "推荐一道蔬菜菜谱"],
            "success": lambda replies: len(replies) >= 2 and any(
                any(kw in r for kw in ["记录", "偏好", "好的"])
                for r in replies[:1]
            ),
        },
        {
            "name": "多任务处理",
            "turns": ["我买了500克五花肉，想做红烧肉"],
            "success": lambda replies: any(
                all(kw in r for kw in ["五花肉", "红烧肉", "菜谱"])
                for r in replies
            ),
        }
    ]

    task_complete = 0
    total_turns = 0
    total_scenarios = len(scenarios)
    scenario_results = []

    for scenario in scenarios:
        thread_id = f"eval_{scenario['name']}_{datetime.now().strftime('%H%M%S')}"
        replies = []
        scenario_start = time.time()
        try:
            for turn in scenario["turns"]:
                turn_start = time.time()  # ✅ 每轮计时
                reply = await run_turn(agent, turn, thread_id=thread_id)
                turn_ms = (time.time() - turn_start) * 1000
                replies.append(reply)
                total_turns += 1
                print(f"    └ 本轮耗时: {turn_ms:.0f}ms")

            scenario_ms = (time.time() - scenario_start) * 1000
            success = scenario["success"](replies)
            if success:
                task_complete += 1

            scenario_results.append({
                "场景": scenario["name"],
                "成功": success,
                "轮次": len(scenario["turns"]),
                "耗时ms": round(scenario_ms),  
                "最终回复": replies[-1][:60] if replies else ""
            })
            print(f"  {'✅' if success else '❌'} {scenario['name']}: {replies[-1][:50] if replies else '无回复'}... | ⏱ {scenario_ms:.0f}ms")

        except Exception as e:
            scenario_ms = (time.time() - scenario_start) * 1000
            print(f"  ❌ {scenario['name']} 执行失败: {e} | ⏱ {scenario_ms:.0f}ms")
            scenario_results.append({"场景": scenario["name"], "成功": False, "错误": str(e)})
    
    # 4. 最终汇总耗时写入 EvalResult
    task_rate = task_complete / total_scenarios
    avg_turns = total_turns / total_scenarios
    total_latency = sum(s.get("耗时ms", 0) for s in scenario_results)
    avg_latency = total_latency / total_scenarios

    report.add(EvalResult("L4", "任务完成率", task_rate,
                        {"完成": task_complete, "总数": total_scenarios,
                            "场景详情": scenario_results},
                        latency_ms=avg_latency))  # ✅ 写入平均耗时
    report.add(EvalResult("L4", "平均对话轮数（越少越好）",
                        max(0, 1 - (avg_turns - 1) / 3),
                        {"平均轮数": round(avg_turns, 2),
                            "总耗时ms": round(total_latency)}))

    print(f"  任务完成率: {task_rate:.3f} ({task_complete}/{total_scenarios})")
    print(f"  平均对话轮数: {avg_turns:.1f}")
    print(f"  平均场景耗时: {avg_latency:.0f}ms")  # ✅ 新增
    print(f"  端到端总耗时: {total_latency:.0f}ms")  # ✅ 新增


# ════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════

async def main(level: str = "all"):
    report = EvalReport(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    if level in ("all", "l1"):
        await eval_l1(report)
    # if level in ("all", "l2"):
    #     await eval_l2(report)
    if level in ("all", "l3"):
        await eval_l3(report)
    if level in ("all", "l4"):
        await eval_l4(report)

    report.print()
    report.save(f"eval/report_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{level}.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="膳食助手评估框架")
    parser.add_argument(
        "--level",
        choices=["all", "l1", "l2", "l3", "l4"],
        default="all",
        help="评估层次"
    )
    args = parser.parse_args()
    asyncio.run(main(args.level))