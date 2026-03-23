import pytest
from src.libs.base.chroma_store import ChromaStore

def test_chroma_store_add_and_query():
    store = ChromaStore(db_path="test_db")

    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]]
    metadata = ["vector1", "vector2", "vector3"]

    store.add(vectors, metadata)

    query_vector = [0.1, 0.2, 0.3]
    results = store.query(query_vector, top_k=2)

    assert len(results) == 2
    assert results[0][1] == "vector1"
    assert results[1][1] == "vector2"