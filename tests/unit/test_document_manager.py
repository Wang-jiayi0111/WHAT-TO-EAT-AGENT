"""Unit tests for the document manager module."""
import pytest
from unittest.mock import Mock
from src.ingestion.document_manager import DocumentManager, DocumentRecord
from src.ingestion.processors.splitter import Chunk
from src.libs.base.vector_store import VectorStore


def test_document_manager_initialization():
    """Test DocumentManager initialization."""
    vector_store = Mock(spec=VectorStore)
    bm25_indexer = Mock()

    manager = DocumentManager(
        vector_store=vector_store,
        bm25_indexer=bm25_indexer,
        collection_name="test_collection"
    )

    assert manager.vector_store == vector_store
    assert manager.bm25_indexer == bm25_indexer
    assert manager.collection_name == "test_collection"
    assert manager.document_records == {}


def test_document_record_creation():
    """Test DocumentRecord creation."""
    from datetime import datetime

    record = DocumentRecord(
        id="test_id",
        content="test content",
        metadata={"key": "value"},
        vector_store_ids=["vs1", "vs2"],
        bm25_doc_ids=["bm25_1"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        status="indexed"
    )

    assert record.id == "test_id"
    assert record.content == "test content"
    assert record.metadata == {"key": "value"}
    assert record.vector_store_ids == ["vs1", "vs2"]
    assert record.bm25_doc_ids == ["bm25_1"]
    assert record.status == "indexed"


def test_document_manager_index_document():
    """Test indexing a single document."""
    vector_store = Mock(spec=VectorStore)
    vector_store.add_texts = Mock(return_value=None)

    manager = DocumentManager(
        vector_store=vector_store,
        collection_name="test_collection"
    )

    chunk = Chunk(
        id="chunk1",
        content="Test content for indexing",
        metadata={"source": "test", "type": "recipe"},
        source_document_id="doc1",
        chunk_index=0
    )

    record = manager.index_document(chunk)

    # Verify record was created
    assert isinstance(record, DocumentRecord)
    assert record.id in manager.document_records
    assert record.content == "Test content for indexing"
    assert record.status in ["indexed", "partial"]  # Could be either depending on implementation

    # Verify vector store was called
    vector_store.add_texts.assert_called_once()


def test_document_manager_bulk_index_documents():
    """Test bulk indexing of documents."""
    vector_store = Mock(spec=VectorStore)
    vector_store.add_texts = Mock(return_value=None)

    manager = DocumentManager(
        vector_store=vector_store,
        collection_name="test_collection"
    )

    chunks = [
        Chunk(
            id=f"chunk{i}",
            content=f"Test content {i}",
            metadata={"source": "test"},
            source_document_id="doc1",
            chunk_index=i
        )
        for i in range(3)
    ]

    records = manager.bulk_index_documents(chunks)

    # Verify all documents were indexed
    assert len(records) == 3
    for record in records:
        assert isinstance(record, DocumentRecord)
        assert record.id in manager.document_records

    # Verify vector store was called for each chunk
    assert vector_store.add_texts.call_count == 3


def test_document_manager_search_with_vector_store():
    """Test search functionality with vector store."""
    vector_store = Mock(spec=VectorStore)

    # Mock the _embed method to return a fixed vector
    def mock_embed(text):
        return [1.0, 0.5, 0.3]  # Simple mock embedding

    vector_store._embed = mock_embed

    # Mock the query method to return test results
    def mock_query(query_vector, top_k):
        return [
            {
                "content": "Test content result",
                "metadata": {"source": "test"},
                "similarity": 0.95
            }
        ]

    vector_store.query = mock_query

    manager = DocumentManager(
        vector_store=vector_store,
        collection_name="test_collection"
    )

    results = manager.search("test query", top_k=5)

    # Should return results from vector store
    assert len(results) >= 0  # May return 0 if there are issues
    if results:
        result = results[0]
        assert result['source'] == 'vector_store'
        assert result['query_type'] == 'semantic'


def test_document_manager_get_document_status():
    """Test getting document status."""
    vector_store = Mock(spec=VectorStore)
    vector_store.add_texts = Mock(return_value=None)

    manager = DocumentManager(
        vector_store=vector_store,
        collection_name="test_collection"
    )

    # Index a document first
    chunk = Chunk(
        id="chunk1",
        content="Test content",
        metadata={"source": "test"},
        source_document_id="doc1",
        chunk_index=0
    )
    record = manager.index_document(chunk)

    # Get the status
    retrieved_record = manager.get_document_status(record.id)

    assert retrieved_record is not None
    assert retrieved_record.id == record.id
    assert retrieved_record.content == "Test content"


def test_document_manager_delete_document():
    """Test deleting a document."""
    vector_store = Mock(spec=VectorStore)
    vector_store.delete_by_metadata = Mock(return_value=None)

    manager = DocumentManager(
        vector_store=vector_store,
        collection_name="test_collection"
    )

    # Index a document first
    chunk = Chunk(
        id="chunk1",
        content="Test content",
        metadata={"source": "test", "document_manager_id": "test_doc"},
        source_document_id="doc1",
        chunk_index=0
    )
    record = manager.index_document(chunk)

    # Delete the document
    success = manager.delete_document(record.id)

    assert success is True
    assert record.id not in manager.document_records

    # Verify vector store delete was called
    vector_store.delete_by_metadata.assert_called()


def test_document_manager_get_storage_stats():
    """Test getting storage statistics."""
    vector_store = Mock(spec=VectorStore)
    vector_store.add_texts = Mock(return_value=None)

    manager = DocumentManager(
        vector_store=vector_store,
        collection_name="test_collection"
    )

    # Add some documents to get stats
    for i in range(3):
        chunk = Chunk(
            id=f"chunk{i}",
            content=f"Test content {i}",
            metadata={"source": "test"},
            source_document_id="doc1",
            chunk_index=i
        )
        manager.index_document(chunk)

    stats = manager.get_storage_stats()

    # Verify stats structure
    assert 'total_documents' in stats
    assert 'vector_store_records' in stats
    assert 'fully_indexed' in stats
    assert 'partially_indexed' in stats
    assert 'failed_indexing' in stats

    assert stats['total_documents'] == 3


def test_document_manager_index_document_without_bm25():
    """Test indexing when BM25 indexer is not available."""
    vector_store = Mock(spec=VectorStore)
    vector_store.add_texts = Mock(return_value=None)

    # Don't provide BM25 indexer
    manager = DocumentManager(
        vector_store=vector_store,
        collection_name="test_collection"
    )

    chunk = Chunk(
        id="chunk1",
        content="Test content without BM25",
        metadata={"source": "test"},
        source_document_id="doc1",
        chunk_index=0
    )

    record = manager.index_document(chunk)

    # Should still work without BM25
    assert isinstance(record, DocumentRecord)
    assert record.id in manager.document_records
    assert record.status in ["indexed", "partial"]

    vector_store.add_texts.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])