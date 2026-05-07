import json
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

from src.agent.effective_constraint import filter_recipes_by_hard_exclusions

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 业务类：负责检索(chunk)
class SearchRecipesService:
    def __init__(self, rag_engine, user_profile_manager):
        self.rag_engine = rag_engine
        self.user_profile_manager = user_profile_manager

    @staticmethod
    def extract_title(content: str, metadata: dict = None) -> str:
        import re
        # 优先从metadata里取 recipe_name（如果有的话）
        if metadata:
            recipe_name = metadata.get("recipe_name")
            if recipe_name:
                return str(recipe_name).strip()
            # 优先级 2：从文件路径中提取文件名（最稳妥的保底方案）
            doc_id = metadata.get("source_document_id", "")
            if doc_id:
                stem = Path(doc_id).stem
                # 去掉 _chunk_xxx 后缀
                stem = re.sub(r'_chunk_\d+$', '', stem)
                if stem:
                    return stem
                
            # 优先级 3：尝试从 LangChain 分割器留下的 header_info 中读取
            header_info = metadata.get("header_info", {})
            if isinstance(header_info, str):
                try:
                    header_info = json.loads(header_info.replace("'", '"'))
                except Exception:
                    header_info = {}
            # 只取一级或二级标题作为主菜名
            for key in ["Header 1", "Header 2"]:
                val = header_info.get(key, "")
                if val:
                    return str(val).strip()
                
            return content[:20].strip()

        # 优先级 4：只有在没有任何元数据时，才尝试从文本提取（防爆改）
        match = re.search(r'#+\s+([^#\n]+?)(?:\s*##|\s*$)', content)
        if match:
            title = match.group(1).strip()
            if len(title) > 2:
                return title
            
        

    async def execute(
        self,
        query: str,
        user_id: str = "default_user",
        top_k: int = 10,
        effective_constraint: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """
        RAG 检索。若传入 **effective_constraint**（与 researcher **C** 一致），
        按 §5.4 对候选执行 hard_exclusions 过滤（FR-11 / FR-20 / T-015）。
        """
        profile = self.user_profile_manager.get_user_profile(user_id)

        enhanced_query = query
        if profile and profile.get("preferred_cuisines"):
            enhanced_query += f" cuisine: {', '.join(profile['preferred_cuisines'])}"

        results = self.rag_engine.get_detailed_results(enhanced_query, top_k=top_k)
        raw_list = results.get("results", []) if isinstance(results, dict) else []

        if effective_constraint:
            filtered: List[Dict[str, Any]] = []
            for r in raw_list:
                content_full = r.get("content", "") or ""
                md = r.get("metadata") or {}
                recipe_data = {
                    "id": r.get("id", ""),
                    "title": self.extract_title(content_full, md),
                    "score": r.get("score", 0),
                    "content": content_full,
                    "source": md.get("source_document_id") or "",
                }
                filtered.append(recipe_data)

            hx = effective_constraint.get("hard_exclusions") or []
            filtered = filter_recipes_by_hard_exclusions(filtered, hx)
            for item in filtered:
                item.pop("content", None)

            return {
                "recipes": filtered,
                "query_used": enhanced_query,
                "effective_constraint_applied": True,
            }

        dietary_restrictions = profile.get("dietary_restrictions", []) if profile else []
        if not isinstance(dietary_restrictions, list):
            dietary_restrictions = []

        filtered_legacy: List[Dict[str, Any]] = []
        for r in raw_list:
            content_lower = (r.get("content", "") or "").lower()
            if not any(str(rest).lower() in content_lower for rest in dietary_restrictions):
                recipe_data = {
                    "id": r.get("id", ""),
                    "title": self.extract_title(
                        r.get("content", ""),
                        r.get("metadata", {}),
                    ),
                    "score": r.get("score", 0),
                }
                filtered_legacy.append(recipe_data)

        return {"recipes": filtered_legacy, "query_used": enhanced_query}

# 业务类：获取路径
class RecipeSourceService:
    """读取完整文档并提取食材"""
    def __init__(self, document_manager):
        self.document_manager = document_manager

    async def execute(self, recipe_name: str) -> Dict[str, Any]:
        """
        根据logistics_buffer[extracted_entities[recipe_name]]，获取对应菜谱的路径
        """
        logger.info(f"正在获取菜谱 '{recipe_name}' 的源文件路径...")
        file_source = self.document_manager.get_source_by_name(recipe_name)

        logging.info(f"获取到的文件路径: {file_source}")
        return file_source

    