import sqlite3
import os

db_path = "data/db/bm25_index.db"

print(f"文件是否存在: {os.path.exists(db_path)}")
print(f"当前工作目录: {os.getcwd()}")


conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 查看所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("表列表:", cursor.fetchall())

# 查看 recipe_fts 表结构
cursor.execute("PRAGMA table_info(recipe_fts)")
print("recipe_fts 列结构:", cursor.fetchall())

# 查看前3条实际数据
cursor.execute("SELECT * FROM recipe_fts LIMIT 3")
rows = cursor.fetchall()
for i, row in enumerate(rows):
    print(f"\n第{i+1}条数据: {row}")

conn.close()