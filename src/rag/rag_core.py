"""
Core components for the RAG (Retrieval Augmented Generation) engine.
Implements semantic search using vector embeddings and keyword search using BM25.
"""
from typing import List, Dict, Any, Tuple, Optional
from chromadb import logger
from dataclasses import dataclass
from abc import ABC, abstractmethod

from src.ingestion.document_manager import DocumentManager
from src.libs.base.vector_store import VectorStore
from src.libs.base.bm25_indexer import BM25Indexer
from src.libs.base.settings import Settings

@dataclass
class SearchResult:
    """Represents a search result from the RAG engine."""
    id: str
    content: str
    score: float  # Combined relevance score
    metadata: Dict[str, Any]
    source: str  # 'vector', 'bm25', or 'combined'
    similarity: float  # Individual similarity score
    rank: int  # Rank in the results list


class BaseSearchEngine(ABC):
    """Abstract base class for search engines."""

    @abstractmethod
    def search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """
        Search for relevant documents.

        Args:
            query: Search query
            top_k: Number of top results to return

        Returns:
            List of search results
        """
        pass


class SemanticSearchEngine(BaseSearchEngine):
    """Semantic search engine using vector embeddings."""

    def __init__(self, vector_store: VectorStore, embed_model=None):
        """
        Initialize the semantic search engine.

        Args:
            vector_store: Vector store for similarity search
            embed_model: Embedding model to convert text to vectors (optional)
        """
        self.vector_store = vector_store
        self.embed_model = embed_model

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """
        Perform semantic search using vector embeddings.

        Args:
            query: Search query
            top_k: Number of top results to return

        Returns:
            List of search results
        """
        # Convert query to embedding
        results = self.vector_store.query(query, top_k)

        search_results = []
        for i, result in enumerate(results):
            score = result.get('score', 0)
            
            # similarity = score  
            
            search_results.append(SearchResult(
                id=result.get('id', ""),
                content=result.get('content', ""),
                score=score, # 统一为 0-1 的得分
                metadata=result.get('metadata', {}),
                source='vector',
                similarity=score,
                rank=i
            ))

        return search_results


class KeywordSearchEngine(BaseSearchEngine):
    """Keyword search engine using BM25 algorithm."""

    def __init__(self, bm25_indexer: BM25Indexer):
        """
        Initialize the keyword search engine.

        Args:
            bm25_indexer: BM25 indexer for keyword search
        """
        self.bm25_indexer = bm25_indexer

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """
        Perform keyword search using BM25 algorithm.

        Args:
            query: Search query
            top_k: Number of top results to return

        Returns:
            List of search results
        """
        # Search in BM25 index
        results = self.bm25_indexer.search(query, top_k)

        # Convert to SearchResult format
        search_results = []
        for i, result in enumerate(results):
            search_result = SearchResult(
                id=result.get('id', f"keyword_{i}"),
                content=result.get('content', ''),
                score=result.get('score', 0),
                metadata=result.get('metadata', {}),
                source='bm25',
                similarity=result.get('score', 0),  # BM25 score serves as similarity
                rank=i
            )
            search_results.append(search_result)

        return search_results


class HybridSearchEngine(BaseSearchEngine):
    """Hybrid search engine combining semantic and keyword search."""

    def __init__(
        self,
        semantic_engine: SemanticSearchEngine,
        keyword_engine: KeywordSearchEngine,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3
    ):
        """
        Initialize the hybrid search engine.

        Args:
            semantic_engine: Semantic search engine
            keyword_engine: Keyword search engine
            semantic_weight: Weight for semantic search results (0-1)
            keyword_weight: Weight for keyword search results (0-1)
        """
        self.semantic_engine = semantic_engine
        self.keyword_engine = keyword_engine
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """
        Perform hybrid search combining semantic and keyword results.

        Args:
            query: Search query
            top_k: Number of top results to return

        Returns:
            List of combined search results
        """
        # Get results from both engines
        semantic_results = self.semantic_engine.search(query, top_k * 2)  # Get more to allow for combination
        keyword_results = self.keyword_engine.search(query, top_k * 2)

        # Combine results using weighted scoring
        combined_results = self._combine_results(semantic_results, keyword_results, top_k)

        return combined_results

    def _combine_results(
        self,
        semantic_results: List[SearchResult],
        keyword_results: List[SearchResult],
        top_k: int
    ) -> List[SearchResult]:
        """
        Combine semantic and keyword search results.

        Args:
            semantic_results: Results from semantic search
            keyword_results: Results from keyword search
            top_k: Number of top results to return

        Returns:
            Combined list of search results
        """
        print(f" [Hybrid] semantic分数范围: {[round(r.score,3) for r in semantic_results[:3]]}")
        print(f" [Hybrid] keyword分数范围: {[round(r.score,3) for r in keyword_results[:3]]}")
        logger.debug("semantic scores: %s", [round(r.score,3) for r in semantic_results[:3]])
        logger.debug("keyword scores: %s",  [round(r.score,3) for r in keyword_results[:3]])

        # Create a mapping of content to combined score
        score_map: Dict[str, Dict[str, Any]] = {}

        # Add semantic scores
        for result in semantic_results:
            content_key = result.content.strip().lower()
            if content_key not in score_map:
                score_map[content_key] = {
                    'content': result.content,
                    'metadata': result.metadata,
                    'semantic_score': 0,
                    'keyword_score': 0,
                    'source_ids': {'semantic': result.id}
                }

            score_map[content_key]['semantic_score'] = result.score
            score_map[content_key]['source_ids']['semantic'] = result.id

        # Add keyword scores
        for result in keyword_results:
            content_key = result.content.strip().lower()
            if content_key not in score_map:
                score_map[content_key] = {
                    'content': result.content,
                    'metadata': result.metadata,
                    'semantic_score': 0,
                    'keyword_score': 0,
                    'source_ids': {'keyword': result.id}
                }

            score_map[content_key]['keyword_score'] = result.score
            score_map[content_key]['source_ids']['keyword'] = result.id

        
        # ── 两个分数都做 Min-Max 归一化 ──────────────────────
        s_scores = [d['semantic_score'] for d in score_map.values() if d['semantic_score'] > 0]
        k_scores = [d['keyword_score']  for d in score_map.values() if d['keyword_score']  > 0]

        s_min, s_max = (min(s_scores), max(s_scores)) if s_scores else (0, 1)
        k_min, k_max = (min(k_scores), max(k_scores)) if k_scores else (0, 1)


        # Calculate combined scores
        combined_results = []
        for content_key, data in score_map.items():
            semantic_norm = data['semantic_score']  #  semantic_score
            keyword_norm = data['keyword_score']    #  BM25 scores 

            # Calculate weighted combined score
            combined_score = (
                self.semantic_weight * semantic_norm +
                self.keyword_weight * keyword_norm
            )

            # 只对非零分数归一化，零分（未被该引擎召回）保持 0
            # s_norm = ((data['semantic_score'] - s_min) / (s_max - s_min + 1e-9)
            #         if data['semantic_score'] > 0 else 0.0)
            # k_norm = ((data['keyword_score'] - k_min) / (k_max - k_min + 1e-9)
            #         if data['keyword_score'] > 0 else 0.0)

            # combined_score = self.semantic_weight * s_norm + self.keyword_weight * k_norm


            # Create combined result
            result = SearchResult(
                id=f"combined_{hash(content_key) % 1000000}",  # Unique ID based on content
                content=data['content'],
                score=combined_score,
                metadata=data['metadata'],
                source='combined',
                similarity=combined_score,
                rank=0  # Will be updated after sorting
            )
            combined_results.append(result)

        # Sort by combined score and assign ranks
        combined_results.sort(key=lambda x: x.score, reverse=True)
        for i, result in enumerate(combined_results[:top_k]):
            result.rank = i

        return combined_results[:top_k]


class RAGEngine:
    """Main RAG engine orchestrating search and retrieval."""

    def __init__(
        self,
        document_manager: DocumentManager,
        search_engine: BaseSearchEngine,
        reranker=None  # Optional reranking component
    ):
        """
        Initialize the RAG engine.

        Args:
            document_manager: Document manager for accessing stored documents
            search_engine: Search engine for retrieving relevant documents
            reranker: Optional reranking component for post-processing results
        """
        self.document_manager = document_manager
        self.search_engine = search_engine
        self.reranker = reranker

    def retrieve(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """
        Retrieve relevant documents for a query.

        Args:
            query: Search query
            top_k: Number of top results to return

        Returns:
            List of relevant search results
        """
        # Perform search using the configured search engine
        results = self.search_engine.search(query, top_k)

        # Optionally rerank results
        if self.reranker:
            results = self._rerank_results(results, query)

        return results

    def _rerank_results(self, results: List[SearchResult], query: str) -> List[SearchResult]:
        """
        Rerank search results using a reranking component.

        Args:
            results: Initial search results
            query: Original search query

        Returns:
            Reranked list of search results
        """
        # In a real implementation, this would use a dedicated reranking model
        # For now, we'll just return the results as-is
        return results

    def get_context_for_generation(self, query: str, top_k: int = 5) -> str:
        """
        Get context from retrieved documents for generation.

        Args:
            query: Search query
            top_k: Number of top results to use for context

        Returns:
            Context string for generation
        """
        results = self.retrieve(query, top_k)

        # Combine content from results into a context string
        context_parts = []
        for result in results:
            context_parts.append(f"Result {result.rank + 1}: {result.content}")

        return "\n\n".join(context_parts)

    def get_detailed_results(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Get detailed results including metadata and provenance.

        Args:
            query: Search query
            top_k: Number of top results to return

        Returns:
            Dictionary with detailed results and metadata
        """
        results = self.retrieve(query, top_k)

        detailed_results = {
            'query': query,
            'total_results': len(results),
            'results': [
                {
                    'rank': result.rank,
                    'id': result.id,
                    'content': result.content,
                    'score': result.score,
                    'source': result.source,
                    'similarity': result.similarity,
                    'metadata': result.metadata
                }
                for result in results
            ],
            'search_params': {
                'top_k': top_k,
                'engine_type': type(self.search_engine).__name__
            }
        }

        return detailed_results
    
    def get_full_document(self, recipe_name_or_id: str) -> str:
        """
        真正的“完整文档”返回逻辑应该在这里实现
        """
        # 利用初始化时传入的 document_manager 去文件系统或数据库读全文
        return self.document_manager.read_full_document(recipe_name_or_id)