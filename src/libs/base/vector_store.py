from abc import ABC, abstractmethod
import numpy as np

class VectorStore(ABC):
    """
    Abstract base class for vector storage.
    """

    @abstractmethod
    def add(self, chunks, metadata):
        """
        Add chunks to the vector store.

        Args:
            chunks (list): List of text chunks to be added.
            metadata (dict): Metadata associated with the chunks (e.g., recipe ID).
        """
        pass

    @abstractmethod
    def query(self, vector, top_k):
        """
        Query the vector store with an input vector.

        Args:
            vector (list): Input vector for similarity search.
            top_k (int): Number of top results to return.

        Returns:
            list: List of results with their metadata and similarity scores.
        """
        pass

    @abstractmethod
    def delete_by_metadata(self, metadata):
        """
        Delete entries from the vector store based on metadata.

        Args:
            metadata (dict): Metadata criteria for deletion (e.g., recipe ID).
        """
        pass


class ConcreteVectorStore(VectorStore):
    """
    Concrete implementation of vector storage.
    """

    def __init__(self):
        """
        Initialize the vector store with in-memory storage.
        """
        self.vectors = []  # List to store vectors
        self.metadata = []  # List to store metadata associated with vectors

    def add(self, chunks, metadata):
        """
        Add chunks to the vector store.

        Args:
            chunks (list): List of text chunks to be added.
            metadata (dict): Metadata associated with the chunks (e.g., recipe ID).
        """
        for chunk in chunks:
            vector = self._embed(chunk)  # Convert chunk to vector
            self.vectors.append(vector)
            self.metadata.append(metadata)

    def query(self, vector, top_k):
        """
        Query the vector store with an input vector.

        Args:
            vector (list): Input vector for similarity search.
            top_k (int): Number of top results to return.

        Returns:
            list: List of results with their metadata and similarity scores.
        """
        similarities = [self._cosine_similarity(vector, v) for v in self.vectors]
        top_indices = np.argsort(similarities)[-top_k:][::-1]  # Get top_k indices sorted by similarity
        results = [
            {
                "metadata": self.metadata[i],
                "similarity": similarities[i]
            }
            for i in top_indices
        ]
        return results

    def delete_by_metadata(self, metadata):
        """
        Delete entries from the vector store based on metadata.

        Args:
            metadata (dict): Metadata criteria for deletion (e.g., recipe ID).
        """
        indices_to_delete = [i for i, meta in enumerate(self.metadata) if all(meta.get(k) == v for k, v in metadata.items())]
        for index in sorted(indices_to_delete, reverse=True):
            del self.vectors[index]
            del self.metadata[index]

    def _embed(self, text):
        """
        Placeholder for embedding generation. Replace with actual embedding logic.

        Args:
            text (str): Input text to embed.

        Returns:
            list: Generated embedding vector.
        """
        return np.random.rand(300).tolist()  # Example: Random 300-dimensional vector

    def _cosine_similarity(self, vec1, vec2):
        """
        Compute cosine similarity between two vectors.

        Args:
            vec1 (list): First vector.
            vec2 (list): Second vector.

        Returns:
            float: Cosine similarity score.
        """
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))