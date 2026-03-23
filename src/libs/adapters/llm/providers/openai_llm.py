from ..base_llm import BaseLLM

class OpenAILLM(BaseLLM):
    """Implementation of BaseLLM for OpenAI's API."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def generate(self, prompt: str) -> str:
        """Generate a response using OpenAI's API."""
        # Placeholder for actual OpenAI API call
        return f"OpenAI response to: {prompt}"

    def get_model_name(self) -> str:
        return "OpenAI"