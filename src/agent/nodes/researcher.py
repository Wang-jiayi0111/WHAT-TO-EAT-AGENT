"""
Recipe Researcher Node for the WHAT-TO-EAT-AGENT system.

This module implements the recipe researcher functionality that communicates with
the MCP server to retrieve recipe information.
"""
import asyncio
import copy
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from typing import Any, Dict, List, Optional
import logging
import sys
import json
import os
import subprocess
from pathlib import Path
from string import Template
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters


from ..state import AgentState
from ..state_accessors import get_runtime_bundle
from ..effective_constraint import (
    augment_search_query,
    build_effective_constraint,
    effective_constraint_has_retryable_soft_signals,
    relaxed_effective_constraint_for_search_retry,
)
from ..recipe_ambiguity import build_ambiguity_candidates
from ..state_sync import (
    CLEAR_ERROR_STATE,
    error_state_from_expert_payloads,
    recipe_state_from_logistics_buffer,
    runtime_bundle_to_slice_patches,
)
from ..task_stack import consume_tasks
from .schema import StructuredRecipe
from ...libs.adapters.llm.llm_factory import LLMFactory
from ...libs.base.settings import Settings
from ...mcp.protocol import is_mcp_error_response

logger = logging.getLogger(__name__)

# 规格 §5.3
RECIPE_PARSER_VERSION = "llm_structured_v1"


def coerce_mcp_recipe_path(raw: Any) -> str:
    """统一 MCP `get_recipe_source` 返回值（str / null / 错误 dict）为本地路径字符串。"""
    if raw is None:
        return ""
    if isinstance(raw, dict):
        if raw.get("error") or raw.get("status") == "error":
            return ""
        return str(
            raw.get("file_path")
            or raw.get("source")
            or raw.get("path")
            or raw.get("source_document_id")
            or ""
        ).strip()
    if isinstance(raw, str):
        return raw.strip()
    return str(raw).strip()


def stage1_high_confidence(recipes: List[Dict[str, Any]], gap: float) -> bool:
    """规格 §5.1：单候选必锁；多候选看 top1 相对 top2 分差。"""
    if not recipes:
        return False
    if len(recipes) == 1:
        return True
    if len(recipes) >= 2:
        s1 = float(recipes[0].get("score") or 0)
        s2 = float(recipes[1].get("score") or 0)
        return (s1 - s2) / (s2 + 1e-6) > gap
    return False


async def resolve_authoritative_structured_recipe(
    research: "RecipeResearcher",
    locked_title: str,
) -> tuple:
    """
    规格 §5.2：权威 **R** 仅来自 `recipe_file_ref` 指向的全文 Markdown + LLM 结构化抽取；
    禁止仅用 `search_recipes` 返回的 content 片段定稿。
    返回 `(StructuredRecipe|None, file_ref_str, err_kind)`；err_kind 为 '' | 'source_not_found' | 'empty_r'。
    """
    title = (locked_title or "").strip()
    if not title:
        return None, "", "source_not_found"

    raw = await research.get_recipe_source(recipe_name=title)

    if isinstance(raw, dict) and (raw.get("error") or raw.get("status") == "error"):
        return None, "", "source_not_found"

    path = coerce_mcp_recipe_path(raw)
    if not path or not os.path.exists(path):
        return None, path or "", "source_not_found"

    structured_recipe = await research.parse_recipe_content(file_path=path)

    if not structured_recipe.ingredients:
        return None, path, "empty_r"

    return structured_recipe, path, ""


def _recoverable_recipe_fault(
    state: AgentState,
    logistics_buffer: Dict[str, Any],
    current_stack: List[str],
    effective_c: Dict[str, Any],
    *,
    user_hint: str,
    detail: str,
    error_code: str,
) -> Dict[str, Any]:
    """§5.2 失败：可恢复错误 + 清空 R，避免进入扣减链路。"""
    stack = consume_tasks(current_stack.copy(), ["TASK_SEARCH"])
    if "TASK_DIRECT_REPLY" not in stack:
        stack.append("TASK_DIRECT_REPLY")
    logistics_buffer["degraded_reply"] = user_hint
    logistics_buffer["recipe_requirements"] = []
    logistics_buffer["recipe_candidates"] = []
    logistics_buffer["selected_recipe_id"] = None
    logistics_buffer["recipe_title_locked"] = None
    logistics_buffer["recipe_parser_version"] = None
    expert_payloads = {
        **(state.get("expert_payloads") or {}),
        "error": detail,
        "status": "recoverable_error",
        "error_code": error_code,
    }
    result: Dict[str, Any] = {"task_stack": stack, "expert_payloads": expert_payloads}
    result.update(runtime_bundle_to_slice_patches(logistics_buffer))
    result.update(_recipe_error_slice_patch(logistics_buffer, expert_payloads))
    _merge_effective_constraint_into_memory_patch(result, effective_c)
    return result


def _merge_effective_constraint_into_memory_patch(
    patch: Dict[str, Any], c: Dict[str, Any]
) -> Dict[str, Any]:
    """规格 §3.5：将本轮 **C** 写入 memory_state，供下游只读。"""
    mp = dict(patch.get("memory_state") or {})
    mp["effective_constraint"] = c
    patch["memory_state"] = mp
    return patch


def _recipe_error_slice_patch(bundle: Dict[str, Any], expert: Dict[str, Any]) -> Dict[str, Any]:
    """方案 A：同步 recipe_state / error_state（T-030）。"""
    patch: Dict[str, Any] = {"recipe_state": recipe_state_from_logistics_buffer(bundle)}
    err = error_state_from_expert_payloads(expert)
    patch["error_state"] = err if err else CLEAR_ERROR_STATE
    return patch


class RecipeResearcher:
    """
    Implements the Recipe Researcher node that acts as an MCP Client to communicate
    with the recipe RAG service.
    """

    def __init__(self):
        try:
            current_file = Path(__file__).resolve()
            project_root = current_file.parents[3] 
            server_script = project_root / "src" / "mcp" / "server.py"
            full_env = os.environ.copy()  # 完整继承父进程所有环境变量
            full_env["PYTHONPATH"] = str(project_root) + os.pathsep + full_env.get("PYTHONPATH", "")

            self.server_params = StdioServerParameters(
                command=sys.executable,  # 使用当前的 Python 解释器
                args=[str(server_script)], # 服务端脚本路径
                env=full_env
            )

            # ============ 调试用 ===============
            proc = subprocess.Popen(
                [sys.executable, str(server_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=full_env
            )
            import time
            time.sleep(3)  # 等3秒让它初始化
            proc.terminate()
            out, err = proc.communicate()
            print(f"🔍 Server stdout: {out[:1000]}")
            print(f"🔍 Server stderr: {err[:1000]}")
            
            settings = Settings()
            # 获取主力模型并注入结构化输出能力
            base_llm = LLMFactory.get_llm(settings)
            self.llm = base_llm.with_structured_output(StructuredRecipe)
            
            # 加载外部 Prompt 模板
            prompt_path = Path(__file__).parent.parent / "prompts" / "recipe_extraction.md"
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.template = f.read()
            print(f"🛠️ MCP Server 路径已设定: {server_script}")
        except Exception as e:
            logger.error(f"RecipeResearcher 初始化失败: {e}")
            raise

    async def _call_mcp_tool(self, tool_name: str, arguments: Dict) -> Dict:
        try:
            async with stdio_client(self.server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    print(f"✅ 初始化完成，正在调用工具: {tool_name}")
                    result = await session.call_tool(tool_name, arguments)
                    if result.content and len(result.content) > 0:
                        raw_text = result.content[0].text
                        print(f"🔍 Server 原始返回: {repr(raw_text[:200])}")  # ← 加这行
                        try:
                            return json.loads(raw_text)
                        except json.JSONDecodeError as je:
                            logger.warning("MCP invalid JSON: %s", je)
                            return {
                                "status": "error",
                                "error": f"invalid JSON from MCP server: {je}",
                            }
                    return {
                        "error": "Empty response from MCP server",
                        "status": "error",
                    }
        except Exception as e:
            import traceback
            # 判断是否是 ExceptionGroup
            if hasattr(e, 'exceptions'):
                print(f"❌ ExceptionGroup，子异常数量: {len(e.exceptions)}")
                for i, sub in enumerate(e.exceptions):
                    print(f"  子异常[{i}]: {type(sub).__name__}: {sub}")
                    print(f"  详细: {''.join(traceback.format_exception(type(sub), sub, sub.__traceback__))}")
            else:
                print(f"❌ 普通异常: {type(e).__name__}: {e}")
                traceback.print_exc()
            return {"error": str(e), "status": "error"}

    async def search_recipes(
        self,
        query: str,
        user_id: str = "default_user",
        *,
        effective_constraint: Optional[Dict[str, Any]] = None,
        top_k: int = 15,
    ) -> Dict:
        """通过 stdio 调用 MCP `search_recipes`；传入 **C** 与检索侧统一（T-015）。"""
        args: Dict[str, Any] = {
            "query": query,
            "user_id": user_id,
            "top_k": top_k,
        }
        if effective_constraint is not None:
            args["effective_constraint"] = effective_constraint
        result = await self._call_mcp_tool("search_recipes", args)
        print(f"📥 收到MCP服务器响应: {result}")  # 调试信息
        return result

    async def get_recipe_source(self, recipe_name: str, file_path: Optional[str] = None) -> Dict:
        """执行第二阶段：获取完整菜谱文档"""
        return await self._call_mcp_tool("get_recipe_source", {
            "recipe_name": recipe_name
        })
    
    async def parse_recipe_content(self, file_path: str) -> StructuredRecipe:
        """
        根据传入的文件路径读取 Markdown 内容，并实时转化为结构化 JSON 对象。
        """
        
        try:
            if not file_path or not os.path.exists(file_path):
                print(f"⚠️ 解析失败：文件路径无效或不存在 -> {file_path}")
                return StructuredRecipe(title="文件未找到", ingredients=[], steps=[])
            
            with open(file_path, "r", encoding="utf-8") as f:
                raw_markdown = f.read()
            
            if not raw_markdown.strip():
                print(f"⚠️ 解析失败：文件内容为空 -> {file_path}")
                return StructuredRecipe(title="内容为空", ingredients=[], steps=[])
            
            prompt = Template(self.template).safe_substitute(raw_markdown=raw_markdown)
        
            result: StructuredRecipe = await self.llm.ainvoke(prompt)

            return result
        
        except Exception as e:
            print(f"解析菜谱失败: {e}")
            return StructuredRecipe(title="解析失败", ingredients=[], steps=[])
            
    
async def researcher_node(state: AgentState) -> AgentState:
    """
    菜谱检索专家节点决策流
    """
    current_stack = state.get("task_stack", []).copy()

    research = RecipeResearcher()
    logistics_buffer = copy.deepcopy(get_runtime_bundle(state))
    entities = logistics_buffer.get("extracted_entities", {})

    active_user_id = state.get("active_user_id", "default_user")
    # §3.5 / §5.1：合并 **C**（L2+L3+画像）；MCP user_id 使用 C.scope_id（SCOPE_ID）
    effective_c = build_effective_constraint(state)
    scope_for_mcp = effective_c.get("scope_id") or active_user_id
    _settings = Settings()
    _rel_gap = _settings.get_retrieval_top2_relative_gap()

    if logistics_buffer.get("selected_recipe_title"):
        locked_title = str(logistics_buffer["selected_recipe_title"]).strip()
        print(f"🔍 [Researcher] 已有选定菜谱标题「{locked_title}」，§5.2 全文解析 → **R**")

        structured_recipe, file_path, err_kind = await resolve_authoritative_structured_recipe(
            research, locked_title
        )

        if err_kind == "source_not_found":
            return _recoverable_recipe_fault(
                state,
                logistics_buffer,
                current_stack,
                effective_c,
                user_hint="未找到该菜谱的完整文档路径，请确认菜名或稍后再试。",
                detail="get_recipe_source 未返回可读的本地文件（§5.1～5.2）",
                error_code="RECIPE_SOURCE_NOT_FOUND",
            )
        if err_kind == "empty_r":
            return _recoverable_recipe_fault(
                state,
                logistics_buffer,
                current_stack,
                effective_c,
                user_hint="未能从菜谱全文解析出用料清单，暂无法继续后续步骤；请换一道菜或稍后再试。",
                detail="StructuredRecipe.ingredients 为空（§5.2）",
                error_code="RECIPE_PARSE_FAILED",
            )

        logistics_buffer["recipe_title_locked"] = locked_title
        logistics_buffer["selected_recipe_title"] = locked_title
        logistics_buffer["recipe_requirements"] = [
            ing.model_dump() for ing in structured_recipe.ingredients
        ]
        logistics_buffer["recipe_cook_step"] = structured_recipe.steps
        logistics_buffer["recipe_candidates"] = []
        logistics_buffer["selected_recipe_id"] = file_path
        logistics_buffer["recipe_parser_version"] = RECIPE_PARSER_VERSION
        # §6.3：新锁定 **R** → 需重新「采纳」后才能扣减
        logistics_buffer["recipe_use_confirmed"] = False

        current_stack = consume_tasks(current_stack, ["TASK_SEARCH"])
        current_stack.append("TASK_SUMMARIZE")  # 获取详情后直接进入总结阶段

        result = {
            "task_stack": current_stack,
            "expert_payloads": {
                **state.get("expert_payloads", {}),
                "recipe_detail": structured_recipe.model_dump(),
                "status": "success",
            },
        }
        result.update(runtime_bundle_to_slice_patches(logistics_buffer))
        result.update(_recipe_error_slice_patch(logistics_buffer, result["expert_payloads"]))
        _merge_effective_constraint_into_memory_patch(result, effective_c)
        return result

    else:
        base_query_raw = str(
            entities.get("recipe_name")
            or (state["messages"][-1].content if state.get("messages") else "")
            or ""
        ).strip()

        query = augment_search_query(base_query_raw, effective_c, state)
        search_res = await research.search_recipes(
            query,
            scope_for_mcp,
            effective_constraint=effective_c,
        )
    
        print(f"🔍 [Researcher] 没有选定菜谱标题，开始检索菜谱，query: {query}, user_id: {scope_for_mcp}")  # 调试信息

        if not isinstance(search_res, dict) or is_mcp_error_response(search_res):
            current_stack = consume_tasks(current_stack, ["TASK_SEARCH"])
            if "TASK_DIRECT_REPLY" not in current_stack:
                current_stack.append("TASK_DIRECT_REPLY")
            logistics_buffer["degraded_reply"] = "检索服务暂时不可用，我先根据常见做法给您一些通用建议，或您可以稍后再试。"
            result = {
                "task_stack": current_stack,
                "expert_payloads": {
                    **state.get("expert_payloads", {}),
                    "error": search_res.get("error"),
                    "status": "recoverable_error",
                },
            }
            result.update(runtime_bundle_to_slice_patches(logistics_buffer))
            result.update(_recipe_error_slice_patch(logistics_buffer, result["expert_payloads"]))
            _merge_effective_constraint_into_memory_patch(result, effective_c)
            return result

        recipes = search_res.get("recipes") or []

        # FR-24：首轮无结果且存在软约束 → 保留 hard_exclusions，清空软字段后重试（次数可配置）
        soft_retry_attempted = False
        remaining_soft_retries = _settings.get_recipe_search_soft_retry_max()
        while (
            not recipes
            and remaining_soft_retries > 0
            and effective_constraint_has_retryable_soft_signals(effective_c)
        ):
            relaxed_c = relaxed_effective_constraint_for_search_retry(effective_c)
            query_r = augment_search_query(base_query_raw, relaxed_c, state)
            logger.info(
                "FR-24: empty recipe search, retry with relaxed soft constraint (hard_exclusions unchanged)"
            )
            search_res_r = await research.search_recipes(
                query_r,
                scope_for_mcp,
                effective_constraint=relaxed_c,
            )
            soft_retry_attempted = True
            remaining_soft_retries -= 1
            if not isinstance(search_res_r, dict) or is_mcp_error_response(search_res_r):
                break
            recipes = search_res_r.get("recipes") or []

        print(f"📋 [Researcher] 搜索结果数量: {len(recipes)}, 分数最高的结果: {recipes[0] if recipes else 'None'}")  # 调试信息

        if not recipes:
            current_stack = consume_tasks(current_stack, ["TASK_SEARCH"])
            if "TASK_DIRECT_REPLY" not in current_stack:
                current_stack.append("TASK_DIRECT_REPLY")
            if soft_retry_attempted:
                logistics_buffer["degraded_reply"] = (
                    "没有找到匹配的菜谱；已自动放宽口味偏好、近期饮食状态与摘要中的偏好描述后再次检索，仍未找到结果。"
                    "您可以换个菜名或说法再试；若有食材禁忌，结果也会被过滤，可选范围会相应变窄。"
                )
            else:
                logistics_buffer["degraded_reply"] = (
                    "暂时没有找到匹配的菜谱，您可以换个菜名、口味或食材再试试。"
                )
            result = {
                "task_stack": current_stack,
                "expert_payloads": {
                    **state.get("expert_payloads", {}),
                    "error": "No recipes found",
                    "status": "recoverable_error",
                    "error_code": "RECIPE_SEARCH_EMPTY",
                    "recipe_search_soft_retry_attempted": soft_retry_attempted,
                },
            }
            print(f"❌ [Researcher] 未找到菜谱，返回: {result}")  # 调试信息
            result.update(runtime_bundle_to_slice_patches(logistics_buffer))
            result.update(_recipe_error_slice_patch(logistics_buffer, result["expert_payloads"]))
            _merge_effective_constraint_into_memory_patch(result, effective_c)
            return result

        top_recipe = recipes[0]  # 取分数最高
        top_score = top_recipe["score"]
        locked_title = str(top_recipe.get("title") or "").strip()
        print(f"🎯 [Researcher] 最高分候选: {locked_title} (评分: {top_score})")

        is_confident = stage1_high_confidence(recipes, _rel_gap)

        if is_confident:
            # §5.1：高置信仅锁定 title；§5.2：**R** 必须通过 get_recipe_source(锁定 title) → 全文解析
            structured_recipe, file_path, err_kind = await resolve_authoritative_structured_recipe(
                research, locked_title
            )

            if err_kind == "source_not_found":
                return _recoverable_recipe_fault(
                    state,
                    logistics_buffer,
                    current_stack,
                    effective_c,
                    user_hint="未找到该菜谱的完整文档路径，请换个菜名或稍后再试。",
                    detail="get_recipe_source 未返回可读的本地文件（§5.1～5.2）",
                    error_code="RECIPE_SOURCE_NOT_FOUND",
                )
            if err_kind == "empty_r":
                return _recoverable_recipe_fault(
                    state,
                    logistics_buffer,
                    current_stack,
                    effective_c,
                    user_hint="未能从菜谱全文解析出用料清单，暂无法生成购物建议；请换一道菜或稍后再试。",
                    detail="StructuredRecipe.ingredients 为空（§5.2）",
                    error_code="RECIPE_PARSE_FAILED",
                )

            logistics_buffer["recipe_title_locked"] = locked_title
            logistics_buffer["selected_recipe_title"] = locked_title
            logistics_buffer["recipe_requirements"] = [
                ing.model_dump() for ing in structured_recipe.ingredients
            ]
            logistics_buffer["recipe_cook_step"] = structured_recipe.steps
            logistics_buffer["selected_recipe_id"] = file_path
            logistics_buffer["recipe_candidates"] = []
            logistics_buffer["recipe_parser_version"] = RECIPE_PARSER_VERSION
            logistics_buffer["recipe_use_confirmed"] = False

            current_stack = consume_tasks(current_stack, ["TASK_SEARCH"])

            result = {
                "task_stack": current_stack,
                "expert_payloads": {
                    **state.get("expert_payloads", {}),
                    "recipe_detail": structured_recipe.model_dump(),
                    "status": "success",
                },
            }
            print(f"✅ §5.2 权威 R：{len(logistics_buffer['recipe_requirements'])} 项食材")
            result.update(runtime_bundle_to_slice_patches(logistics_buffer))
            result.update(_recipe_error_slice_patch(logistics_buffer, result["expert_payloads"]))
            _merge_effective_constraint_into_memory_patch(result, effective_c)
            return result

        else:
            # 低置信度（§5.1）：歧义 → 有限候选 + TASK_CLARIFY，**不** 调用阶段二（FR-22）
            _ambig_cap = Settings().get_ambiguity_max_candidates()
            capped = build_ambiguity_candidates(recipes, _ambig_cap)
            logistics_buffer["recipe_candidates"] = capped
            logistics_buffer["selected_recipe_id"] = None
            logistics_buffer["clarification_kind"] = "recipe_pick"

            logistics_buffer["pending_tasks"] = [
                t for t in current_stack if t not in ("TASK_CLARIFY", "TASK_SEARCH")
            ]
            print(
                f"🔍 [Researcher] 低置信度歧义：展示 {len(capped)} 项候选（上限 {_ambig_cap}），"
                f"pending_tasks={logistics_buffer['pending_tasks']}"
            )

            current_stack = ["TASK_SEARCH", "TASK_CLARIFY"]

            result = {
                "expert_payloads": {
                    **state.get("expert_payloads", {}),
                    "search_results": recipes,
                    "status": "ambiguous",
                    "ambiguity_candidate_count": len(capped),
                },
                "task_stack": current_stack,
            }
            print(f"⚠️ 歧义分支：原始检索 {len(recipes)} 条，展示 {len(capped)} 条")  # 调试信息
            result.update(runtime_bundle_to_slice_patches(logistics_buffer))
            result.update(_recipe_error_slice_patch(logistics_buffer, result["expert_payloads"]))
            _merge_effective_constraint_into_memory_patch(result, effective_c)
            return result
