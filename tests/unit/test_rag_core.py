"""
test_rag_core.py  —— RAG 检索分层测试
用途：逐层诊断 score 全为 0 的原因

运行方式（在项目根目录执行）：
    python test_rag_core.py

测试分四层：
  Layer 1: VectorStore 原始返回 —— 确认 similarity 字段存在且非 0
  Layer 2: BM25Indexer 原始返回 —— 确认 score 字段存在且非 0
  Layer 3: SemanticSearchEngine / KeywordSearchEngine 封装层
  Layer 4: HybridSearchEngine 混合合并层 —— 重点检查归一化逻辑
"""

import sys
import json
from pathlib import Path

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent 

if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src.libs.base.vector_store import VectorStore
from src.libs.base.chroma_store import ChromaStore
from src.libs.base.bm25_indexer import BM25Indexer
from src.libs.base.settings import Settings
from src.libs.adapters.embed.embed_factory import EmbedFactory
from src.rag.rag_core import (
    SemanticSearchEngine,
    KeywordSearchEngine,
    HybridSearchEngine,
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data" / "db"
CHROMA_PATH = DB_PATH
BM25_PATH = DB_PATH / "bm25_index.db"

print(f"BASE_DIR: {BASE_DIR}")
print(f"DB_PATH: {DB_PATH}")
print(f"CHROMA_PATH: {CHROMA_PATH}")
print(f"BM25_PATH: {BM25_PATH}")

settings = Settings()
embedding_fn = EmbedFactory.get_embed(settings)
bm25_indexer = BM25Indexer(db_path=str(BM25_PATH))


# ════════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════════

def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def ok(msg): print(f"  ✅ {msg}")
def warn(msg): print(f"  ⚠️  {msg}")
def fail(msg): print(f"  ❌ {msg}")


# ════════════════════════════════════════════════════════════
# Layer 1: VectorStore 原始返回
# ════════════════════════════════════════════════════════════

def test_vector_store_raw(query: str = "红烧肉", top_k: int = 5):
    section("Layer 1: VectorStore 原始返回")

    vs = ChromaStore(
        db_path=str(CHROMA_PATH),
        embedding_function=embedding_fn, 
        collection_name="recipes"
    )

    results = vs.query(query, top_k)
    print(f"  返回条数: {len(results)}")

    if not results:
        fail("VectorStore 返回空列表，请检查向量库是否已建立索引")
        return

    print(f"\n  第一条原始结果的所有 key: {list(results[0].keys())}")
    print(f"  第一条原始结果:")
    for k, v in results[0].items():
        display = str(v)[:80] + "..." if len(str(v)) > 80 else str(v)
        print(f"    {k}: {display}")

    # 关键检查：similarity 字段
    sim_key_candidates = ["similarity", "score", "distance", "_distance", "relevance_score"]
    found_key = None
    for k in sim_key_candidates:
        if k in results[0]:
            found_key = k
            break

    print(f'found: {found_key}')
    if found_key:
        scores = [r.get(found_key, 0) for r in results]
        ok(f"找到得分字段 '{found_key}'，值范围: {min(scores):.4f} ~ {max(scores):.4f}")
        if max(scores) == 0:
            warn(f"字段 '{found_key}' 存在但全为 0，可能是向量库返回的 distance 需要转换")
        if found_key != "similarity":
            warn(f"字段名是 '{found_key}' 而非 'similarity'")
            fail(f">>> rag_core.py 里用的是 result.get('similarity', 0)，字段名不匹配会导致 score 全为 0！")
    else:
        fail(f"未找到任何得分字段（检查了 {sim_key_candidates}），请查看上方原始 key 列表")

    return results


# ════════════════════════════════════════════════════════════
# Layer 2: BM25Indexer 原始返回
# ════════════════════════════════════════════════════════════

def test_bm25_raw(query: str = "红烧肉", top_k: int = 5):
    section("Layer 2: BM25Indexer 原始返回")
    settings = Settings()
    bm25 = BM25Indexer(settings)

    results = bm25.search(query, top_k)
    print(f"  返回条数: {len(results)}")

    if not results:
        fail("BM25 返回空列表，请检查 BM25 索引是否已建立")
        return

    print(f"\n  第一条原始结果的所有 key: {list(results[0].keys())}")
    scores = [r.get("score", None) for r in results]
    print(f"  score 列表: {[f'{s:.4f}' if s is not None else 'None' for s in scores]}")

    if all(s == 0 for s in scores if s is not None):
        fail("BM25 score 全为 0")
    elif None in scores:
        warn("部分结果缺少 'score' 字段")
    else:
        ok(f"BM25 score 范围: {min(scores):.4f} ~ {max(scores):.4f}")

    # 检查归一化风险
    unique_scores = set(s for s in scores if s is not None)
    if len(unique_scores) == 1:
        warn("所有 BM25 score 完全相同 → HybridSearch 归一化时 (k_max - k_min) = 0，结果全为 0")

    return results


# ════════════════════════════════════════════════════════════
# Layer 3: 封装层 SemanticSearchEngine / KeywordSearchEngine
# ════════════════════════════════════════════════════════════

def test_search_engines(query: str = "红烧肉", top_k: int = 5):
    section("Layer 3: 封装层 SearchEngine")
    settings = Settings()

    # Semantic
    vs = VectorStore(settings)
    semantic = SemanticSearchEngine(vs)
    s_results = semantic.search(query, top_k)
    print(f"\n  [SemanticSearchEngine] 返回条数: {len(s_results)}")
    if s_results:
        s_scores = [r.score for r in s_results]
        print(f"  score 列表: {[f'{s:.4f}' for s in s_scores]}")
        if max(s_scores) == 0:
            fail("SemanticSearchEngine.score 全为 0 → 见 Layer 1 诊断")
        else:
            ok(f"SemanticSearchEngine score 范围: {min(s_scores):.4f} ~ {max(s_scores):.4f}")

    # Keyword
    bm25 = BM25Indexer(settings)
    keyword = KeywordSearchEngine(bm25)
    k_results = keyword.search(query, top_k)
    print(f"\n  [KeywordSearchEngine] 返回条数: {len(k_results)}")
    if k_results:
        k_scores = [r.score for r in k_results]
        print(f"  score 列表: {[f'{s:.4f}' for s in k_scores]}")
        if max(k_scores) == 0:
            fail("KeywordSearchEngine.score 全为 0 → 见 Layer 2 诊断")
        else:
            ok(f"KeywordSearchEngine score 范围: {min(k_scores):.4f} ~ {max(k_scores):.4f}")

    return s_results, k_results


# ════════════════════════════════════════════════════════════
# Layer 4: HybridSearchEngine 混合合并
# ════════════════════════════════════════════════════════════

def test_hybrid_engine(query: str = "红烧肉", top_k: int = 5):
    section("Layer 4: HybridSearchEngine 混合合并")
    settings = Settings()

    vs = VectorStore(settings)
    bm25 = BM25Indexer(settings)
    semantic = SemanticSearchEngine(vs)
    keyword = KeywordSearchEngine(bm25)
    hybrid = HybridSearchEngine(semantic, keyword)

    results = hybrid.search(query, top_k)
    print(f"  返回条数: {len(results)}")

    if not results:
        fail("HybridSearchEngine 返回空列表")
        return

    scores = [r.score for r in results]
    print(f"  combined score 列表: {[f'{s:.4f}' for s in scores]}")

    if max(scores) == 0:
        fail("HybridSearchEngine 最终 score 全为 0")
        print("\n  可能原因汇总：")
        print("    1. VectorStore 返回的字段名不是 'similarity'（见 Layer 1）")
        print("    2. BM25 所有 score 相同，归一化后全变 0（见 Layer 2）")
        print("    3. 两者同时为 0")
    else:
        ok(f"HybridSearchEngine score 范围: {min(scores):.4f} ~ {max(scores):.4f}")
        for i, r in enumerate(results):
            print(f"    [{i+1}] score={r.score:.4f}  {r.content[:40]}...")

    return results


# ════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    QUERY = "红烧肉"   # 改成你数据库里确认存在的菜名

    print(f"\n🔍 测试查询: '{QUERY}'")
    print("逐层诊断，找到 score=0 的根本原因\n")

    try:
        test_vector_store_raw(QUERY)
    except Exception as e:
        fail(f"Layer 1 异常: {e}")

    try:
        test_bm25_raw(QUERY)
    except Exception as e:
        fail(f"Layer 2 异常: {e}")

    try:
        test_search_engines(QUERY)
    except Exception as e:
        fail(f"Layer 3 异常: {e}")

    try:
        test_hybrid_engine(QUERY)
    except Exception as e:
        fail(f"Layer 4 异常: {e}")

    print(f"\n{'='*60}")
    print("  测试完成，根据上方 ❌ 提示定位问题")
    print(f"{'='*60}\n")