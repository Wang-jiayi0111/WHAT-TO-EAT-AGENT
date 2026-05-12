from .vector_store import VectorStore
import chromadb
from chromadb.config import Settings

class ChromaStore(VectorStore):
    """Implementation of VectorStore using Chroma."""

    def __init__(self, db_path: str, embedding_function, collection_name: str = "recipes"):
        self.db_path = db_path
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_function
        )

    def add_texts(self, texts: list, metadatas=None, ids=None):
        """将文本直接存入 ChromaDB"""
        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in texts]
        
        if metadatas is None:
            metadatas = [{}] * len(texts)

        # ChromaDB 会自动处理 Embedding（如果配置了 embedding_function）
        self.collection.add(
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )

    def add(self, chunks: list, metadata: dict):
        """
        满足基类抽象方法要求。
        将 chunk 列表存入，所有 chunk 共享同一个 metadata 字典。
        """
        # 将单个 metadata 复制成列表以匹配 chunks 数量
        metadatas = [metadata] * len(chunks)
        # 调用我们已经实现的 add_texts
        return self.add_texts(texts=chunks, metadatas=metadatas)

    def query(self, query_text: str, top_k: int = 5):
        """执行语义搜索"""
        results = self.collection.query(
            query_texts=[query_text],
            n_results=top_k
        )
        
        # 将 Chroma 的返回格式转化为项目中统一的格式
        formatted_results = []
        for i in range(len(results['ids'][0])):
            # Chroma 的 distances：L2 / cosine 等均为「越小越相似」，与混合检索里「越大越好」的 score 相反
            d = float(results["distances"][0][i])
            relevance = 1.0 / (1.0 + d)
            formatted_results.append({
                "id": results['ids'][0][i],
                "content": results['documents'][0][i],
                "metadata": results['metadatas'][0][i],
                "score": relevance,
                "distance": d,
            })
        return formatted_results
    
    def delete_by_metadata(self, metadata: dict):
        """根据元数据删除"""
        self.collection.delete(where=metadata)