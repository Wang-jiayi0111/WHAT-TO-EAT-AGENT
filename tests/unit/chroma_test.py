"""
测试 ChromaDB 的基本功能，确保数据正确存储和检索。
"""

import chromadb
from pathlib import Path
import sys
import json
import random

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent 

if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src.libs.base.settings import Settings
from src.libs.adapters.embed.embed_factory import EmbedFactory
settings = Settings()
embedding_fn = EmbedFactory.get_embed(settings)

# 连接到你的持久化目录
client = chromadb.PersistentClient(path="data/db") # 确保路径与 pipeline 一致
collection = client.get_collection(
    name="recipes", 
    embedding_function=embedding_fn
)
# 1. 检查总数
print(f"当前库中 Chunk 总数: {collection.count()}")


# 2. 获取数据库里的所有数据
all_data = collection.get(include=["metadatas", "documents"])
total_chunks = len(all_data['ids'])

print(f"✅ 数据库中共有 {total_chunks} 个 Chunk。现在随机抽查 5 个：\n")

# 3. 随机抽取 5 个索引
# sample_indices = random.sample(range(total_chunks), min(5, total_chunks))

# for idx in range(total_chunks):
#     chunk_id = all_data['ids'][idx]
#     metadata = all_data['metadatas'][idx]
#     content = all_data['documents'][idx]
    
#     # 提取各个维度的名字
#     meta_recipe_name = metadata.get('recipe_name', '未找到')
    
#     # 打印对比
#     print(f"📦 【Chunk ID】: {chunk_id}")
#     print(f"🏷️ 【Metadata 里的菜名】: {meta_recipe_name}")
#     print("-" * 50)

sample = collection.peek(limit=1)
if sample and sample.get('metadatas') and len(sample['metadatas']) > 0:
    # 取出第一个 chunk 的 metadata 字典
    sample_metadata = sample['metadatas'][0]
    
    print("\n🔍 第一个 Chunk 的 Metadata 中包含以下字段 (Keys):")
    # 遍历并打印所有的键
    for key in sample_metadata.keys():
        print(f" - {key}")
        
    print("\n📄 具体的 Metadata 内容为:")
    import json
    # 格式化打印整个 metadata 字典，方便查看里面的值
    print(json.dumps(sample_metadata, indent=4, ensure_ascii=False))
else:
    print("\n❌ 当前数据库为空，或者该 Chunk 没有 metadata 数据。")

print("🔍 ChromaDB 返回的顶级字典结构包含以下 Key:")
print(list(sample.keys()))

# # 确保数据库里有数据
# if sample['metadatas'] and len(sample['metadatas']) > 0:
#     for i, metadata in enumerate(sample['metadatas']):
#             print(f"=== 第 {i + 1} 条数据的 Metadata (ID: {sample['ids'][i]}) ===")
            
#             # 使用 json.dumps 格式化字典：indent=4 表示缩进4格，ensure_ascii=False 防止中文变乱码
#             formatted_meta = json.dumps(metadata, indent=4, ensure_ascii=False)
#             print(formatted_meta)
#             print("-" * 40) # 打印一条分割线

# else:
#     print("数据库是空的，或者该条数据没有 metadata。")
# # # 2. 尝试检索
# # results = collection.query(
# #     query_texts=["如何做咖喱炒蟹？"],
# #     n_results=1
# # )
# # print(f"最相关的匹配内容: {results['documents'][0][0][:100]}...")