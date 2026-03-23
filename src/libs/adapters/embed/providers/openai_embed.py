from ..base_embed import BaseEmbed

class OpenAIEmbed(BaseEmbed):
    """Implementation of BaseEmbed for OpenAI's embedding API."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def embed(self, text: str) -> list:
        """Generate an embedding vector using OpenAI's API."""
        # Placeholder for actual OpenAI API call
        return [0.1, 0.2, 0.3] * 512  # Example vector

    def get_dimensions(self) -> int:
        return 1536