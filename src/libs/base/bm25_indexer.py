# src/libs/base/bm25_indexer.py
import sqlite3
import json

class BM25Indexer:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Create FTS5 virtual table for full text search
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS recipe_fts USING fts5(
                content,              -- 菜谱切片文本内容
                recipe_id UNINDEXED,  -- 关联业务 ID (不参与分词索引)
                metadata UNINDEXED,
                tokenize='unicode61'  -- 推荐使用支持中文的分词器插件（如 jieba）
            );
        ''')
        # Statistics table for BM25 calculations
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bm25_stats (
                recipe_id TEXT PRIMARY KEY,
                doc_len INTEGER,      -- 该切片的总词数 (dl)
                file_hash TEXT,       -- 关联文件指纹，支持同步删除
                FOREIGN KEY(recipe_id) REFERENCES recipe_fts(recipe_id)
            );
        ''')
        # Global parameters table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS global_params (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                avg_dl REAL,          -- 全库平均文档长度 (avgdl)
                total_docs INTEGER    -- 库中切片总数 (N)
            );
        ''')
        # Insert default values if table is empty
        cursor.execute("INSERT OR IGNORE INTO global_params (id, avg_dl, total_docs) VALUES (1, 0.0, 0)")
        conn.commit()
        conn.close()

    def create_table(self, collection_name: str = "recipes"):
        """Create tables if they don't exist (for compatibility with pipeline controller)"""
        # Tables are already created in _init_db, so this is a no-op
        pass

    def index_content(self, recipe_id: str, content: str, file_hash: str = None, metadata: dict = None):
        """Index content for BM25 search"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        metadata_str = json.dumps(metadata or {}, ensure_ascii=False)
        # Insert into FTS5 table
        cursor.execute(
            "INSERT OR IGNORE INTO recipe_fts (content, recipe_id, metadata) VALUES (?, ?, ?)",
            (content, recipe_id, metadata_str)
            )
        # Calculate and store document length
        doc_len = len(content.split())
        cursor.execute("INSERT OR REPLACE INTO bm25_stats (recipe_id, doc_len, file_hash) VALUES (?, ?, ?)",
                       (recipe_id, doc_len, file_hash))
        # Update global stats
        cursor.execute("UPDATE global_params SET total_docs = total_docs + 1 WHERE id = 1")
        conn.commit()
        conn.close()

    def index_documents(self, documents: list):
        """Index multiple documents"""
        for doc in documents:
            self.index_content(
                recipe_id=doc.get('id', ''),
                content=doc.get('content', ''),
                file_hash=doc.get('file_hash'),
                metadata=doc.get('metadata', {}),  
            )

    def search(self, query: str, top_k: int = 10) -> list:
        """Perform BM25 search and return ranked results"""

        cleaned_query = query.replace('"', ' ').replace('.', ' ').replace('*', ' ').strip()
        if not cleaned_query:
            return []
        
        # 用双引号包裹，避免 FTS5 把词语解析为操作符
        safe_query = f'"{cleaned_query}"'
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Use FTS5's built-in bm25() function for ranking
        cursor.execute('''
            SELECT recipe_id, content, metadata, bm25(recipe_fts) AS rank_score
            FROM recipe_fts
            WHERE content MATCH ?
            ORDER BY rank_score ASC
            LIMIT ?
        ''', (safe_query, top_k))
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'content': row[1],
                'metadata': json.loads(row[2] or '{}'),   # ✅ 反序列化
                'score': -row[3],
            })
        conn.close()
        return results