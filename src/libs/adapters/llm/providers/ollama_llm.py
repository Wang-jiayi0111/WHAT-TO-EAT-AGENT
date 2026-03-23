from ..base_llm import BaseLLM

class OllamaLLM(BaseLLM):
    """Implementation of BaseLLM for Ollama's API."""

    def __init__(self, model_path: str):
        self.model_path = model_path

    def generate(self, prompt: str) -> str:
        """Generate a response using Ollama's local model."""
        # Placeholder for actual Ollama model inference
        return f"Ollama response to: {prompt}"

    def get_model_name(self) -> str:
        return "Ollama"