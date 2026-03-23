from abc import ABC, abstractmethod

class BaseLLM(ABC):
    """Abstract base class for LLM implementations."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a response based on the given prompt."""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the name of the underlying model."""
        pass