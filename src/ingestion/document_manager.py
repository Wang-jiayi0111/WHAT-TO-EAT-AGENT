"""
Module for managing documents across different storage systems (vector store, BM25, etc.).
Coordinates operations across different storage backends to maintain consistency.
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import uuid
from datetime import datetime

from src.ingestion.processors.splitter import Chunk
from src.libs.base.vector_store import VectorStore
from src.libs.base.chroma_store import ChromaStore
from src.libs.base.bm25_indexer import BM25Indexer

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def flatten_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten nested metadata dictionaries to ensure compatibility with ChromaDB.
    ChromaDB only supports str, int, float, bool, list, and None as metadata values.
    """
    flattened = {}

    for key, value in metadata.items():
        if isinstance(value, dict):
            # Convert nested dictionary to string representation
            flattened[key] = str(value)
        elif isinstance(value, (list, tuple)):
            # Process lists/tuples - if they contain dicts, convert those to strings
            flattened_list = []
            for item in value:
                if isinstance(item, dict):
                    flattened_list.append(str(item))
                else:
                    flattened_list.append(item)
            flattened[key] = flattened_list
        else:
            # Keep primitive values as they are
            flattened[key] = value

    return flattened


@dataclass
class DocumentRecord:
    """Represents a document across all storage systems."""
    id: str
    content: str
    metadata: Dict[str, Any]
    vector_store_ids: List[str]  # IDs in vector store
    bm25_doc_ids: List[str]      # IDs in BM25 index
    created_at: datetime
    updated_at: datetime
    status: str  # 'indexed', 'partial', 'failed'


class DocumentManager:
    """Manages documents across vector store, BM25 index, and other storage systems."""

    def __init__(
        self,
        vector_store: ChromaStore,
        bm25_indexer: Optional[BM25Indexer] = None,
        collection_name: str = "recipes"
    ):
        """
        Initialize the document manager.

        Args:
            vector_store: Vector store for semantic search
            bm25_indexer: BM25 indexer for keyword search (optional)
            collection_name: Name of the collection to manage
        """
        self.vector_store = vector_store
        self.bm25_indexer = bm25_indexer
        self.collection_name = collection_name

        # In-memory record of documents across systems
        self.document_records: Dict[str, DocumentRecord] = {}

    def index_document(self, chunk: Chunk) -> DocumentRecord:
        """
        Index a document chunk in all available storage systems.

        Args:
            chunk: The chunk to index

        Returns:
            DocumentRecord representing the indexed document
        """
        doc_id = str(uuid.uuid4())
        vector_store_ids = []
        bm25_doc_ids = []

        # Add to vector store
        try:
            vector_store_id = self._index_in_vector_store(chunk, doc_id)
            vector_store_ids.append(vector_store_id)
        except Exception as e:
            print(f"Error indexing in vector store: {e}")
            # Continue with other indexing systems

        # Add to BM25 index if available
        if self.bm25_indexer:
            try:
                bm25_doc_id = self._index_in_bm25(chunk, doc_id)
                bm25_doc_ids.append(bm25_doc_id)
            except Exception as e:
                print(f"Error indexing in BM25: {e}")

        # Determine status based on successful indexing
        status = "partial"
        if vector_store_ids and (not self.bm25_indexer or bm25_doc_ids):
            status = "indexed"
        elif not vector_store_ids and not bm25_doc_ids:
            status = "failed"

        # Create document record
        doc_record = DocumentRecord(
            id=doc_id,
            content=chunk.content,
            metadata=chunk.metadata,
            vector_store_ids=vector_store_ids,
            bm25_doc_ids=bm25_doc_ids,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            status=status
        )

        self.document_records[doc_id] = doc_record
        return doc_record

    def _index_in_vector_store(self, chunk: Chunk, doc_id: str) -> str:
        """Index a chunk in the vector store."""
        # Prepare metadata for vector store
        vs_metadata = flatten_metadata(chunk.metadata.copy())
        vs_metadata['original_chunk_id'] = chunk.id
        vs_metadata['document_manager_id'] = doc_id
        vs_metadata['indexed_at'] = datetime.now().isoformat()

        # Generate vector store ID
        vector_store_id = f"vs_{doc_id}_{chunk.chunk_index}"

        # Add to vector store
        self.vector_store.add_texts(
            texts=[chunk.content],
            metadatas=[vs_metadata],
            ids=[vector_store_id]
        )

        return vector_store_id

    def _index_in_bm25(self, chunk: Chunk, doc_id: str) -> str:
        """Index a chunk in the BM25 index."""
        if not self.bm25_indexer:
            raise ValueError("BM25 indexer not available")

        # Prepare document for BM25
        bm25_doc = {
            'id': f"bm25_{doc_id}_{chunk.chunk_index}",
            'content': chunk.content,
            'metadata': {                                  # ✅ 传入需要的字段
                'source_document_id': chunk.metadata.get('source_document_id'),
                'file_path': chunk.metadata.get('file_path'),
                'section_type': chunk.metadata.get('section_type'),
            }
        }

        # Add important metadata fields to the content for keyword search
        if 'source_file' in chunk.metadata:
            bm25_doc['source_file'] = chunk.metadata['source_file']
        if 'section_type' in chunk.metadata:
            bm25_doc['section_type'] = chunk.metadata['section_type']

        # Index the document
        self.bm25_indexer.index_documents([bm25_doc])

        return bm25_doc['id']

    def bulk_index_documents(self, chunks: List[Chunk]) -> List[DocumentRecord]:
        """
        Bulk index multiple document chunks.

        Args:
            chunks: List of chunks to index

        Returns:
            List of DocumentRecords for the indexed documents
        """
        records = []
        for chunk in chunks:
            record = self.index_document(chunk)
            records.append(record)
        return records

    # def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    #     """
    #     Search across all storage systems and return combined results.

    #     Args:
    #         query: Search query
    #         top_k: Number of top results to return

    #     Returns:
    #         Combined search results from all storage systems
    #     """
    #     results = []

    #     # Search in vector store
    #     if hasattr(self.vector_store, '_embed'):
    #         try:
    #             query_vector = self.vector_store._embed(query)
    #             vs_results = self.vector_store.query(query_vector, top_k)

    #             # Format vector store results
    #             for result in vs_results:
    #                 formatted_result = {
    #                     'content': result.get('content', result.get('metadata', {}).get('content', '')),
    #                     'source': 'vector_store',
    #                     'similarity': result.get('similarity', 0),
    #                     'metadata': result.get('metadata', {}),
    #                     'query_type': 'semantic'
    #                 }
    #                 results.append(formatted_result)
    #         except Exception as e:
    #             print(f"Error searching vector store: {e}")

    #     # Search in BM25 if available
    #     if self.bm25_indexer:
    #         try:
    #             bm25_results = self.bm25_indexer.search(query, top_k)

    #             # Format BM25 results
    #             for result in bm25_results:
    #                 formatted_result = {
    #                     'content': result.get('content', ''),
    #                     'source': 'bm25',
    #                     'score': result.get('score', 0),
    #                     'metadata': result.get('metadata', {}),
    #                     'query_type': 'keyword'
    #                 }
    #                 results.append(formatted_result)
    #         except Exception as e:
    #             print(f"Error searching BM25: {e}")

    #     return results[:top_k]

    # 修改 search 方法的参数，增加 search_type，默认依然是 hybrid 保证向前兼容
    def search(self, query: str, top_k: int = 5, search_type: str = 'hybrid') -> List[Dict[str, Any]]:
        """
        Search across storage systems.
        search_type 可以是: 'hybrid', 'semantic', 'keyword'
        """
        results = []

        # 1. Search in vector store (当模式为 hybrid 或 semantic 时触发)
        if search_type in ['hybrid', 'semantic'] and hasattr(self.vector_store, '_embed'):
            try:
                query_vector = self.vector_store._embed(query)
                vs_results = self.vector_store.query(query_vector, top_k)

                for result in vs_results:
                    results.append({
                        'content': result.get('content', result.get('metadata', {}).get('content', '')),
                        'source': 'vector_store',
                        'score': result.get('similarity', 0), # 这里统一叫 score，方便后续统一处理
                        'metadata': result.get('metadata', {}),
                        'query_type': 'semantic'
                    })
            except Exception as e:
                print(f"Error searching vector store: {e}")

        # 2. Search in BM25 (当模式为 hybrid 或 keyword 时触发)
        if search_type in ['hybrid', 'keyword'] and self.bm25_indexer:
            logger.info(f"正在使用 BM25 搜索，查询: '{query}'")
            try:
                bm25_results = self.bm25_indexer.search(query, top_k)
                logger.info(f"BM25 搜索完成，找到 {len(bm25_results)} 条结果, results: {bm25_results}")

                for result in bm25_results:
                    results.append({
                        'content': result.get('content', ''),
                        'source': 'bm25',
                        'score': result.get('score', 0),
                        'metadata': result.get('metadata', {}),
                        'query_type': 'keyword'
                    })
            except Exception as e:
                print(f"Error searching BM25: {e}")

        # 如果是 hybrid，可以在这里加一段按 score 重新排序的逻辑
        if search_type == 'hybrid':
             results = sorted(results, key=lambda x: x['score'], reverse=True)

        return results[:top_k]

    def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document from all storage systems.

        Args:
            doc_id: ID of the document to delete

        Returns:
            True if deletion was successful
        """
        if doc_id not in self.document_records:
            return False

        doc_record = self.document_records[doc_id]
        success = True

        # Delete from vector store
        try:
            for vs_id in doc_record.vector_store_ids:
                self.vector_store.delete_by_metadata({'document_manager_id': doc_id})
        except Exception as e:
            print(f"Error deleting from vector store: {e}")
            success = False

        # Delete from BM25 if available
        if self.bm25_indexer:
            try:
                for bm25_id in doc_record.bm25_doc_ids:
                    # The BM25 indexer might have a delete method in a full implementation
                    pass  # Placeholder - would need implementation in BM25Indexer
            except Exception as e:
                print(f"Error deleting from BM25: {e}")
                success = False

        # Remove from internal records
        if success:
            del self.document_records[doc_id]

        return success

    def get_document_status(self, doc_id: str) -> Optional[DocumentRecord]:
        """
        Get the status of a document across storage systems.

        Args:
            doc_id: ID of the document

        Returns:
            DocumentRecord if found, None otherwise
        """
        return self.document_records.get(doc_id)

    def get_source_by_name(self, recipe_name: str, threshold: float = 0.6) -> str:
        """
        通过recipe_name获取metadata中的source_document_id（文件路径）
        """
        result = self.search(query=recipe_name, top_k=1, search_type='keyword')

        logger.info(f"Searching for recipe '{recipe_name}'. Found {len(result)} results. results: {result}")
        if not result:
            return None
        best_match_meta = result[0].get('metadata', {})
        
        # 兼容你的键名：优先取 file_path，如果没有再取 source_document_id
        best_match_path = best_match_meta.get('file_path') or best_match_meta.get('source_document_id')
        
        return best_match_path

    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get statistics about storage utilization.

        Returns:
            Dictionary with storage statistics
        """
        stats = {
            'total_documents': len(self.document_records),
            'vector_store_records': 0,
            'bm25_records': 0,
            'fully_indexed': 0,
            'partially_indexed': 0,
            'failed_indexing': 0
        }

        for record in self.document_records.values():
            stats['vector_store_records'] += len(record.vector_store_ids)
            if self.bm25_indexer:
                stats['bm25_records'] += len(record.bm25_doc_ids)

            if record.status == 'indexed':
                stats['fully_indexed'] += 1
            elif record.status == 'partial':
                stats['partially_indexed'] += 1
            elif record.status == 'failed':
                stats['failed_indexing'] += 1

        return stats