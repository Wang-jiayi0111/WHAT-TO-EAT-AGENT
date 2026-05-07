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
)
from ..state_sync import (
    CLEAR_ERROR_STATE,
    error_state_from_expert_payloads,
    recipe_state_from_logistics_buffer,
    runtime_bundle_to_slice_patches,
)
from ..task_stack import consume_tasks
from .schema import StructuredRecipe
from ...libs.adapters.llm.llm_factory import LLMFactory
from .schema import StructuredRecipe
from ...libs.base.settings import Settings

logger = logging.getLogger(__name__)


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
                        return json.loads(raw_text)
                    return {"error": "Empty response from MCP server"}
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

    if logistics_buffer.get("selected_recipe_title"):
        query = logistics_buffer["selected_recipe_title"]
        print(f"🔍 [Researcher] 已有选定菜谱标题{query}，直接获取菜谱")  # 调试信息

        file_path = await research.get_recipe_source(query, "")
        print(f"🔍获取菜谱文件路径：{file_path}，提取菜谱所需食材")

        if isinstance(file_path, dict):
            file_path = file_path.get("file_path") or file_path.get("source") or ""
        structured_recipe = await research.parse_recipe_content(file_path=file_path)
        print(f"📊 解析结果: {structured_recipe.title}, 食材数量: {len(structured_recipe.ingredients)}")  # 调试信息

        logistics_buffer["recipe_requirements"] = [
                ing.model_dump() for ing in structured_recipe.ingredients
            ]
        logistics_buffer["recipe_cook_step"] = structured_recipe.steps
        logistics_buffer["recipe_candidates"] = []
        logistics_buffer["selected_recipe_id"] = file_path

        current_stack = consume_tasks(current_stack, ["TASK_SEARCH"])
        current_stack.append("TASK_SUMMARIZE")  # 获取详情后直接进入总结阶段

        result = {
            "task_stack": current_stack,  
            "expert_payloads": {
                **state.get("expert_payloads", {}),
                "recipe_detail": structured_recipe.model_dump(),
                "status": "success"
            }
        }
        result.update(runtime_bundle_to_slice_patches(logistics_buffer))
        result.update(_recipe_error_slice_patch(logistics_buffer, result["expert_payloads"]))
        _merge_effective_constraint_into_memory_patch(result, effective_c)
        return result

    else:
        query = entities.get("recipe_name") or (state["messages"][-1].content if state.get("messages") else "")
        query = augment_search_query(
            str(query) if query is not None else "",
            effective_c,
            state,
        )
        search_res = await research.search_recipes(
            query,
            scope_for_mcp,
            effective_constraint=effective_c,
        )
    
        print(f"🔍 [Researcher] 没有选定菜谱标题，开始检索菜谱，query: {query}, user_id: {scope_for_mcp}")  # 调试信息

        if search_res.get("error"):
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

        print(f"📋 [Researcher] 搜索结果数量: {len(recipes)}, 分数最高的结果: {recipes[0] if recipes else 'None'}")  # 调试信息

        if not recipes:
            current_stack = consume_tasks(current_stack, ["TASK_SEARCH"])
            if "TASK_DIRECT_REPLY" not in current_stack:
                current_stack.append("TASK_DIRECT_REPLY")
            logistics_buffer["degraded_reply"] = "暂时没有找到匹配的菜谱，您可以换个菜名、口味或食材再试试。"
            result = {
                        "task_stack": current_stack,
                        "expert_payloads": {
                            **state.get("expert_payloads", {}),
                            "error": "No recipes found",
                            "status": "recoverable_error",
                        }
                    }
            print(f"❌ [Researcher] 未找到菜谱，返回: {result}")  # 调试信息
            result.update(runtime_bundle_to_slice_patches(logistics_buffer))
            result.update(_recipe_error_slice_patch(logistics_buffer, result["expert_payloads"]))
            _merge_effective_constraint_into_memory_patch(result, effective_c)
            return result

        top_recipe = recipes[0]  # 取分数最高
        top_score = top_recipe["score"]
        print(f"🎯 [Researcher] 选择最高评分菜谱: {top_recipe['title']} (评分: {top_score})")  # 调试信息

        # 判断置信度is_confident：如果只有一个结果，或者 top1 明显领先于 top2，则认为高置信度
        if len(recipes) == 1:
            is_confident = True

        elif len(recipes) >= 2:
            second_score = recipes[1]["score"]
            # top1 比 top2 分数高出 15%（相对差距），认为明显领先
            is_confident = (top_score - second_score) / (second_score + 1e-6) > 0.15
        else:
            is_confident = False


        if is_confident:
            # 高置信度，直接获取详情
            file_path = top_recipe.get("source", "")
            if not file_path:
                file_path = await research.get_recipe_source(recipe_name=top_recipe["title"])

            print(f"获取文件路径：{file_path}")
            
            structured_recipe = await research.parse_recipe_content(file_path=file_path)
            print(f"📊 解析结果: {structured_recipe.title}, 食材数量: {len(structured_recipe.ingredients)}")  # 调试信息

            logistics_buffer["recipe_requirements"] = [
                ing.model_dump() for ing in structured_recipe.ingredients
            ]
            logistics_buffer["selected_recipe_id"] = top_recipe.get("source")
            logistics_buffer["recipe_candidates"] = []

            current_stack = consume_tasks(current_stack, ["TASK_SEARCH"])

            result = {
                # 第一个结果置信度足够高，提供菜谱信息
                "task_stack": current_stack,  
                "expert_payloads": {
                    **state.get("expert_payloads", {}),
                    "recipe_detail": structured_recipe.model_dump(),
                    "status": "success"
                }
            }
            print(f"✅ 成功返回结果，包含 {len(logistics_buffer['recipe_requirements'])} 项食材")  # 调试信息
            result.update(runtime_bundle_to_slice_patches(logistics_buffer))
            result.update(_recipe_error_slice_patch(logistics_buffer, result["expert_payloads"]))
            _merge_effective_constraint_into_memory_patch(result, effective_c)
            return result

        else:
            # 低置信度，返回候选列表
            extracted_names = []
            for r in recipes:
                recipe_id = r.get("id", "")
                if ".md" in recipe_id:
                    file_name = recipe_id.replace('\\', '/').split('/')[-1] 
                    pure_name = file_name.split('.md')[0] 
                    extracted_names.append(pure_name)
                else:
                    extracted_names.append(r.get("title", "未知菜谱"))
            
            # 去重
            unique_candidate_names = list(dict.fromkeys(extracted_names))
            logistics_buffer["recipe_candidates"] = unique_candidate_names
            logistics_buffer["selected_recipe_id"] = None
        
            logistics_buffer["pending_tasks"] = [t for t in current_stack if t not in ("TASK_CLARIFY", "TASK_SEARCH")]
            print(f"🔍 [Researcher] 低置信度，准备进入歧义处理，保留待办任务: {logistics_buffer['pending_tasks']}")  # 调试信息

            current_stack = ["TASK_SEARCH", "TASK_CLARIFY"]  # 追加歧义解决任务

            result = {
                # 第一个结果置信度不足，返回所有候选菜谱
                "expert_payloads": {
                    **state.get("expert_payloads", {}),
                    "search_results": recipes, # 供 Generator 展示给用户
                    "status": "ambiguous"      # 标记为歧义状态
                },
                # 追加任务栈，引导 Generator 询问用户选哪个
                "task_stack": current_stack
            }
            print(f"⚠️ 低置信度返回，候选菜谱数量: {len(recipes)}, 状态: ambiguous")  # 调试信息
            result.update(runtime_bundle_to_slice_patches(logistics_buffer))
            result.update(_recipe_error_slice_patch(logistics_buffer, result["expert_payloads"]))
            _merge_effective_constraint_into_memory_patch(result, effective_c)
            return result
