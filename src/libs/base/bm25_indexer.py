# src/libs/base/bm25_indexer.py
import re
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

    @staticmethod
    def _sanitize_fts5_match_text(query: str) -> str:
        """
        检索串可能含 `[饮食约束]`、列举用的逗号、括号等；直接传入 FTS5 MATCH 会语法错误
        （如 near "["、near ","）。去掉会破坏解析的字符，保留中文与常规检索用词。
        """
        # 运算符/引号 + 中英文逗号分号顿号（增强 query 里极常见）
        s = re.sub(r'[\[\](){}^*:"|&!<>~,;，；、]', " ", query)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _run_fts(self, cursor: sqlite3.Cursor, match_pattern: str, top_k: int) -> list:
        cursor.execute(
            """
            SELECT recipe_id, content, metadata, bm25(recipe_fts) AS rank_score
            FROM recipe_fts
            WHERE content MATCH ?
            ORDER BY rank_score ASC
            LIMIT ?
            """,
            (match_pattern, top_k),
        )
        out = []
        for row in cursor.fetchall():
            out.append(
                {
                    "id": row[0],
                    "content": row[1],
                    "metadata": json.loads(row[2] or "{}"),
                    "score": -row[3],
                }
            )
        return out

    def _run_fts_safe(
        self, cursor: sqlite3.Cursor, match_pattern: str, top_k: int
    ) -> list:
        """MATCH 语法出错时不抛异常，避免拖垮混合检索（语义侧仍可返回结果）。"""
        try:
            return self._run_fts(cursor, match_pattern, top_k)
        except sqlite3.OperationalError as e:
            msg = str(e).lower()
            if "fts5" in msg or "syntax" in msg or "malformed" in msg:
                return []
            raise

    def search(self, query: str, top_k: int = 10) -> list:
        """Perform BM25 search and return ranked results"""

        cleaned_query = query.replace('"', ' ').replace('.', ' ').replace('*', ' ').strip()
        cleaned_query = self._sanitize_fts5_match_text(cleaned_query)
        if not cleaned_query:
            return []

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 1) 整句短语：命中时排序最准；中文整词连写时常能直接命中标题行
        inner = cleaned_query.replace('"', " ")
        phrase = f'"{inner}"'
        results = self._run_fts_safe(cursor, phrase, top_k)

        # 2) 短语无命中时：先试整串 MATCH（FTS5 对空格分词多为 AND，长 query 易全不命中）
        if not results:
            results = self._run_fts_safe(cursor, cleaned_query, top_k)

        # 3) 仍无命中且 query 含多个词片时，用 OR 放宽（否则混合检索无 BM25 信号，退化为纯向量序）
        if not results:
            parts = [p.strip() for p in cleaned_query.split() if len(p.strip()) >= 2]
            if len(parts) >= 2:
                esc: list[str] = []
                for p in parts[:14]:
                    p2 = re.sub(r'[\[\](){}^*:"|&!<>~]', " ", p).strip()
                    if len(p2) >= 2:
                        esc.append(p2)
                if len(esc) >= 2:
                    or_pat = " OR ".join(esc)
                    results = self._run_fts_safe(cursor, or_pat, top_k)

        conn.close()
        return results