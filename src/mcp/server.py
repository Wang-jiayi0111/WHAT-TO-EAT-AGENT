"""
Model Context Protocol (MCP) Server for WHAT-TO-EAT-AGENT
Provides standardized tools for recipe retrieval that can be consumed by AI assistants.
"""
import json
import asyncio
import logging
import sys
from pathlib import Path
import io
import os
if sys.platform == "win32":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import mcp.types as types
from mcp.server import Server

# 把启动时的环境写入日志文件
# with open("F:/WHAT-TO-EAT-AGENT/server_startup.log", "w") as f:
#     f.write(f"sys.executable: {sys.executable}\n")
#     f.write(f"sys.path: {sys.path}\n")
#     f.write(f"PYTHONPATH env: {os.environ.get('PYTHONPATH', 'NOT SET')}\n")

current_file = Path(__file__).resolve()
project_root = str(current_file.parent.parent.parent) 
if project_root not in sys.path:
    sys.path.insert(0, project_root)


from src.rag.rag_core import RAGEngine
from src.mcp.tool import SearchRecipesService, RecipeSourceService
from src.ingestion.document_manager import DocumentManager
from src.libs.base.user_profiles import UserProfileManager
from src.libs.base.chroma_store import ChromaStore
from src.libs.base.bm25_indexer import BM25Indexer
from src.libs.adapters.embed.embed_factory import EmbedFactory
from src.libs.base.settings import Settings
from src.rag.rag_core import SemanticSearchEngine, HybridSearchEngine, KeywordSearchEngine

logging.basicConfig(
    filename="mcp_debug.log", 
    level=logging.DEBUG, 
    encoding='utf-8',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filemode='a'
)
logger = logging.getLogger("mcp_server")
logger.info("--- MCP Server Starting ---")
# logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data" / "db"
CHROMA_PATH = DB_PATH
BM25_PATH = DB_PATH / "bm25_index.db"

if not CHROMA_PATH.exists():
    logger.error(f"❌ 向量库路径不存在: {CHROMA_PATH}")

settings = Settings()

try:
    # 初始化 Server 对象
    server = Server("recipe-researcher")
    embedding_fn = EmbedFactory.get_embed(settings)
    bm25_indexer = BM25Indexer(db_path=str(BM25_PATH))

    vector_store = ChromaStore(
        db_path=str(CHROMA_PATH),
        embedding_function=embedding_fn, 
        collection_name="recipes"
    )

    docu_manager = DocumentManager(vector_store=vector_store, bm25_indexer=bm25_indexer)
    user_manager = UserProfileManager()

    semantic_engine = SemanticSearchEngine(
        vector_store=vector_store,
        embed_model=embedding_fn  
    )
    keyword_engine = KeywordSearchEngine(bm25_indexer)
    hybrid_engine = HybridSearchEngine(semantic_engine=semantic_engine, keyword_engine=keyword_engine)
    rag_engine = RAGEngine(
        document_manager=docu_manager,
        search_engine=hybrid_engine,  # 也可以切换到 hybrid_engine
    ) 

    search_heandler = SearchRecipesService(rag_engine=rag_engine, user_profile_manager=user_manager)
    source_handler = RecipeSourceService(document_manager=docu_manager)
except Exception as e:
    logging.error(f"MCP 初始化崩溃: {str(e)}", exc_info=True)
    raise e


# 注册工具列表
@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_recipes",
            description="根据用户查询和用户的饮食偏好检索菜谱片段",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "user_id": {"type": "string"},
                    "top_k": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="get_recipe_source",
            description="获取特定菜谱的文件路径",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipe_name": {"type": "string"}
                },
                "required": ["recipe_name"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    try:
        logging.error(f"DEBUG: 收到工具 {name} 调用, 参数: {arguments}")
        if arguments is None:
            arguments = {}

        if name == "search_recipes":
            result = await search_heandler.execute(**arguments)
        elif name == "get_recipe_source":
            result = await source_handler.execute(**arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]  # ← 加 type="text"
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        logging.error(f"❌ 工具执行崩溃: {err_msg}")
        return [types.TextContent(type="text", text=json.dumps({  # ← 这里也加
            "error": str(e),
            "stack": err_msg,
            "status": "error"
        }, ensure_ascii=False))]

async def main():
    from mcp.server.stdio import stdio_server
    try:
        async with stdio_server() as (read, write):
            logger.info("MCP Server 管道准备就绪，开始运行...")
            await server.run(
                read,
                write,
                server.create_initialization_options()
            )
    except Exception as e:
        import traceback
        logger.error(f"❌ server.run() 崩溃: {traceback.format_exc()}")
        raise

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

