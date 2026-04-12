"""
L2 检索质量评估 + RAG 专项评估

运行方式：
  python eval/eval_rag.py --mode l2       # 只跑 L2 基础检索评估
  python eval/eval_rag.py --mode rag      # 只跑 RAG 专项评估
  python eval/eval_rag.py --mode all      # 全部
"""

import asyncio
import json
import sys
import argparse
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


# ════════════════════════════════════════════════════════════
# 数据结构
# ════════════════════════════════════════════════════════════

@dataclass
class MetricResult:
    name: str
    score: float
    detail: Dict = field(default_factory=dict)

    def __str__(self):
        status = "✅" if self.score >= 0.6 else "⚠️" if self.score >= 0.4 else "❌"
        return f"{status} {self.name}: {self.score:.3f}"


# ════════════════════════════════════════════════════════════
# L2 测试用例
# (查询文本, 期望出现在结果 title 中的关键词列表)
# ════════════════════════════════════════════════════════════

L2_CASES: List[Tuple[str, List[str]]] = [
    # 精确菜名查询
    ("红烧肉",          ["红烧肉"]),
    ("桂鱼",            ["葱油桂鱼"]),
    ("番茄蛋花汤",       ["番茄蛋花汤", "西红柿蛋花汤", "西红柿鸡蛋汤"]),
    ("凉拌鸡丝",        ["凉拌鸡丝"]),
    ("玉米排骨汤",      ["玉米排骨汤", "排骨汤"]),

    # 食材导向查询
    ("鸡胸肉",          ["鸡胸肉", "鸡肉"]),
    ("豆腐",            ["豆腐"]),
    ("猪肉",            ["红烧肉", "回锅肉", "猪肉"]),

    # 口味/场景导向查询（模糊）
    ("清淡",            ["汤", "蔬菜", "清淡", "蒸"]),
    ("辣",              ["辣", "川", "麻"]),
    ("快手菜",          ["快", "简单", "分钟", "速食"]),
    ("汤",              ["汤", "羹"]),
]


async def eval_l2_basic(researcher) -> List[MetricResult]:
    """
    L2 基础检索指标（不依赖查询改写）：
    - Hit@1: top1 命中率
    - Hit@3: top3 命中率
    - MRR:   平均倒数排名
    - score 分布：top1 与 top2 的平均分差
    """
    results = []
    hit1_list, hit3_list, mrr_list, gap_list = [], [], [], []

    print("\n[L2] 逐条检索结果：")
    for query, keywords in L2_CASES:
        try:
            resp = await researcher.search_recipes(query, "eval_user")
            recipes = resp.get("recipes", [])

            # Hit@K
            def hit(k):
                for r in recipes[:k]:
                    title = r.get("title", "").lower()
                    if any(kw.lower() in title for kw in keywords):
                        return 1.0
                return 0.0

            # MRR：第一个命中的倒数排名
            mrr = 0.0
            for i, r in enumerate(recipes[:5]):
                title = r.get("title", "").lower()
                if any(kw.lower() in title for kw in keywords):
                    mrr = 1.0 / (i + 1)
                    break

            # top1 vs top2 score gap
            if len(recipes) >= 2:
                gap = recipes[0].get("score", 0) - recipes[1].get("score", 0)
            else:
                gap = 0.0

            h1, h3 = hit(1), hit(3)
            hit1_list.append(h1)
            hit3_list.append(h3)
            mrr_list.append(mrr)
            gap_list.append(gap)

            status = "✅" if h3 else "❌"
            top1_title = recipes[0].get("title", "无")[:20] if recipes else "无结果"
            print(f"  {status} [{query}] top1={top1_title}  Hit@1={h1:.0f} Hit@3={h3:.0f} MRR={mrr:.2f}")

        except Exception as e:
            print(f"  ❌ [{query}] 检索失败: {e}")
            hit1_list.append(0.0)
            hit3_list.append(0.0)
            mrr_list.append(0.0)
            gap_list.append(0.0)

    n = len(L2_CASES)
    results.append(MetricResult("Hit@1", sum(hit1_list) / n,
                                 {"命中数": int(sum(hit1_list)), "总数": n}))
    results.append(MetricResult("Hit@3", sum(hit3_list) / n,
                                 {"命中数": int(sum(hit3_list)), "总数": n}))
    results.append(MetricResult("MRR（平均倒数排名）", sum(mrr_list) / n))
    results.append(MetricResult("top1-top2 平均分差", sum(gap_list) / n,
                                 {"含义": "越大说明 top1 区分度越高"}))
    return results


# ════════════════════════════════════════════════════════════
# RAG 专项评估
# ════════════════════════════════════════════════════════════

# RAG 评估用例：每条包含查询、期望检索到的文档片段关键词、以及标准答案（食材或步骤关键词）
RAG_CASES = [
    {
        "query": "红烧肉",
        "expected_doc_keywords": ["五花肉", "酱油", "冰糖"],   # chunk 应包含这些词
        "expected_answer_keywords": ["五花肉", "料酒", "酱油", "冰糖"],  # LLM 解析结果应包含
        "recipe_name": "红烧肉",
    },
    {
        "query": "凉拌鸡丝",
        "expected_doc_keywords": ["鸡胸肉", "麻油", "香醋"],
        "expected_answer_keywords": ["鸡胸肉", "生抽", "香醋"],
        "recipe_name": "凉拌鸡丝",
    },
    {
        "query": "玉米排骨汤",
        "expected_doc_keywords": ["排骨", "玉米"],
        "expected_answer_keywords": ["排骨", "玉米"],
        "recipe_name": "玉米排骨汤",
    },
]


async def eval_rag_retrieval(researcher) -> MetricResult:
    """
    RAG 评估 Step1：检索阶段
    检查 chunk 内容是否包含期望的文档关键词（context relevance）
    """
    scores = []
    print("\n[RAG Step1] 检索相关性评估：")

    for case in RAG_CASES:
        try:
            resp = await researcher.search_recipes(case["query"], "eval_user")
            recipes = resp.get("recipes", [])

            if not recipes:
                scores.append(0.0)
                print(f"  ❌ [{case['query']}] 无结果")
                continue

            # 把所有返回 chunk 的 title 拼在一起检查覆盖度
            all_titles = " ".join(r.get("title", "") for r in recipes[:5])

            matched = sum(
                1 for kw in case["expected_doc_keywords"]
                if kw in all_titles
            )
            score = matched / len(case["expected_doc_keywords"])
            scores.append(score)

            print(f"  {'✅' if score >= 0.6 else '❌'} [{case['query']}] "
                  f"关键词命中 {matched}/{len(case['expected_doc_keywords'])}")

        except Exception as e:
            print(f"  ❌ [{case['query']}] 失败: {e}")
            scores.append(0.0)

    avg = sum(scores) / len(scores)
    return MetricResult("检索相关性（context relevance）", avg,
                         {"各查询得分": [round(s, 2) for s in scores]})


async def eval_rag_parsing(researcher) -> MetricResult:
    """
    RAG 评估 Step2：解析阶段
    调用 get_recipe_details + parse_recipe_content，检查 LLM 解析的食材是否覆盖期望关键词
    （faithfulness：答案是否忠实于检索到的文档）
    """
    scores = []
    print("\n[RAG Step2] 解析忠实性评估（Faithfulness）：")

    for case in RAG_CASES:
        try:
            # 先搜索，取 top1 做详情获取
            resp = await researcher.search_recipes(case["query"], "eval_user")
            recipes = resp.get("recipes", [])

            if not recipes:
                scores.append(0.0)
                print(f"  ❌ [{case['query']}] 检索无结果，跳过解析")
                continue

            top = recipes[0]
            details = await researcher.get_recipe_details(
                recipe_name=top.get("title", case["recipe_name"]),
                file_path=top.get("source")
            )

            full_content = details.get("full_content", "")
            if not full_content:
                scores.append(0.0)
                print(f"  ❌ [{case['query']}] 详情内容为空")
                continue

            # 解析结构化菜谱
            structured = await researcher.parse_recipe_content(full_content)
            ingredient_names = [ing.name for ing in structured.ingredients]
            ingredient_text = " ".join(ingredient_names)

            matched = sum(
                1 for kw in case["expected_answer_keywords"]
                if kw in ingredient_text
            )
            score = matched / len(case["expected_answer_keywords"])
            scores.append(score)

            print(f"  {'✅' if score >= 0.6 else '❌'} [{case['query']}] "
                  f"食材命中 {matched}/{len(case['expected_answer_keywords'])}  "
                  f"解析到: {ingredient_names[:4]}")

        except Exception as e:
            print(f"  ❌ [{case['query']}] 解析失败: {e}")
            scores.append(0.0)

    avg = sum(scores) / len(scores)
    return MetricResult("解析忠实性（faithfulness）", avg,
                         {"各查询得分": [round(s, 2) for s in scores]})


async def eval_rag_score_distribution(researcher) -> MetricResult:
    """
    RAG 评估 Step3：score 分布分析
    评估置信度区分能力：精确查询的 top1 score 是否明显高于模糊查询
    """
    print("\n[RAG Step3] Score 分布分析：")

    precise_scores = []  # 精确菜名查询的 top1 score
    fuzzy_scores = []    # 模糊查询的 top1 score

    precise_queries = ["红烧肉", "凉拌鸡丝", "玉米排骨汤"]
    fuzzy_queries = ["清淡", "辣", "快手菜"]

    for q in precise_queries:
        try:
            resp = await researcher.search_recipes(q, "eval_user")
            recipes = resp.get("recipes", [])
            if recipes:
                precise_scores.append(recipes[0].get("score", 0))
        except Exception:
            pass

    for q in fuzzy_queries:
        try:
            resp = await researcher.search_recipes(q, "eval_user")
            recipes = resp.get("recipes", [])
            if recipes:
                fuzzy_scores.append(recipes[0].get("score", 0))
        except Exception:
            pass

    avg_precise = sum(precise_scores) / len(precise_scores) if precise_scores else 0
    avg_fuzzy = sum(fuzzy_scores) / len(fuzzy_scores) if fuzzy_scores else 0
    separation = avg_precise - avg_fuzzy  # 正值越大越好

    print(f"  精确查询平均 top1 score: {avg_precise:.3f}")
    print(f"  模糊查询平均 top1 score: {avg_fuzzy:.3f}")
    print(f"  区分度（越大越好）: {separation:+.3f}")

    # 归一化：分差 > 0.05 视为良好
    normalized = min(1.0, max(0.0, separation / 0.1))
    return MetricResult("Score 区分度（精确 vs 模糊）", normalized,
                         {"精确平均": round(avg_precise, 3),
                          "模糊平均": round(avg_fuzzy, 3),
                          "分差": round(separation, 3)})


async def eval_rag_chunk_quality() -> MetricResult:
    """
    RAG 评估 Step4：Chunk 质量检查
    直接查 Chroma，检查 chunk 内容是否包含 # 标题（结构是否正确）
    """
    print("\n[RAG Step4] Chunk 质量检查：")

    try:
        from src.libs.base.chroma_store import ChromaStore
        from src.libs.adapters.embed.embed_factory import EmbedFactory
        from src.libs.base.settings import Settings

        settings = Settings()
        embedding_fn = EmbedFactory.get_embed(settings)
        store = ChromaStore(
            db_path=str(project_root / "data" / "db"),
            embedding_function=embedding_fn,
            collection_name="recipes"
        )

        # 随机抽样 20 个 chunk 检查质量
        sample_results = store.query("红烧肉 鸡蛋 番茄 豆腐", top_k=20)

        has_title = 0        # chunk 包含 # 标题
        has_newline = 0      # chunk 包含换行符（结构完整）
        is_fragment = 0      # chunk 是碎片（内容 < 50 字）

        for r in sample_results:
            content = r.get("content", "")
            if "#" in content:
                has_title += 1
            if "\n" in content:
                has_newline += 1
            if len(content) < 50:
                is_fragment += 1

        n = len(sample_results)
        title_rate = has_title / n if n > 0 else 0
        newline_rate = has_newline / n if n > 0 else 0
        fragment_rate = is_fragment / n if n > 0 else 0

        print(f"  抽样 chunk 数: {n}")
        print(f"  包含标题(#): {has_title}/{n}  ({title_rate:.1%})")
        print(f"  包含换行符: {has_newline}/{n}  ({newline_rate:.1%})")
        print(f"  碎片 chunk(<50字): {is_fragment}/{n}  ({fragment_rate:.1%})")

        # 综合质量分：标题率高、换行率高、碎片率低
        quality = (title_rate * 0.4 + newline_rate * 0.4 + (1 - fragment_rate) * 0.2)
        return MetricResult("Chunk 质量综合分", quality,
                             {"标题率": f"{title_rate:.1%}",
                              "换行率": f"{newline_rate:.1%}",
                              "碎片率": f"{fragment_rate:.1%}"})

    except Exception as e:
        print(f"  ❌ Chunk 质量检查失败: {e}")
        return MetricResult("Chunk 质量综合分", 0.0, {"error": str(e)})


# ════════════════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════════════════

def print_results(title: str, results: List[MetricResult]):
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")
    for r in results:
        print(f"  {r}")
        if r.detail:
            for k, v in r.detail.items():
                print(f"     {k}: {v}")
    avg = sum(r.score for r in results) / len(results)
    print(f"  平均分: {avg:.3f}")


def save_report(all_results: Dict[str, List[MetricResult]]):
    os.makedirs("eval", exist_ok=True)
    path = f"eval/rag_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    data = {
        "timestamp": datetime.now().isoformat(),
        "results": {
            section: [asdict(r) for r in items]
            for section, items in all_results.items()
        },
        "summary": {
            section: round(sum(r.score for r in items) / len(items), 3)
            for section, items in all_results.items()
        }
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存: {path}")


async def main(mode: str):
    from src.agent.nodes.researcher import RecipeResearcher
    researcher = RecipeResearcher()

    all_results = {}

    if mode in ("l2", "all"):
        print("\n" + "=" * 55)
        print("L2 基础检索质量评估")
        print("=" * 55)
        l2_results = await eval_l2_basic(researcher)
        print_results("L2 汇总", l2_results)
        all_results["L2_基础检索"] = l2_results

    if mode in ("rag", "all"):
        print("\n" + "=" * 55)
        print("RAG 专项评估")
        print("=" * 55)

        r1 = await eval_rag_retrieval(researcher)
        r2 = await eval_rag_parsing(researcher)
        r3 = await eval_rag_score_distribution(researcher)
        r4 = await eval_rag_chunk_quality()

        rag_results = [r1, r2, r3, r4]
        print_results("RAG 汇总", rag_results)
        all_results["RAG_专项"] = rag_results

    save_report(all_results)

    print("\n" + "=" * 55)
    print("总体评分")
    print("=" * 55)
    for section, items in all_results.items():
        avg = sum(r.score for r in items) / len(items)
        print(f"  {section}: {avg:.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["l2", "rag", "all"], default="all")
    args = parser.parse_args()
    asyncio.run(main(args.mode))