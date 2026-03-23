from abc import ABC, abstractmethod

class BaseEmbed(ABC):
    """Abstract base class for embedding implementations."""

    @abstractmethod
    def embed(self, text: str) -> list:
        """Generate an embedding vector for the given text."""
        pass

    @abstractmethod
    def get_dimensions(self) -> int:
        """Return the dimensionality of the embedding vector."""
        pass