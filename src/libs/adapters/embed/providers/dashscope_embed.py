import requests
from ..base_embed import BaseEmbed

class DashscopeEmbed(BaseEmbed):
    """
    Implementation of Dashscope's text-embedding-v4 model provider.
    """

    def __init__(self, api_base: str, api_key: str, model: str, timeout: int = 60):
        """
        Initialize the DashscopeEmbed instance.

        Args:
            api_base (str): The base URL for the Dashscope API.
            api_key (str): The API key for authentication.
            model (str): The model identifier (e.g., 'text-embedding-v4').
            timeout (int): Request timeout in seconds.
        """
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def embed(self, text: str) -> list:
        """
        Generate embeddings for the given text.

        Args:
            text (str): The input text to embed.

        Returns:
            list: The generated embeddings as a list of floats.

        Raises:
            Exception: If the API request fails.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "input": text
        }

        try:
            response = requests.post(f"{self.api_base}/embeddings", json=payload, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            return result.get("data", {}).get("embedding", [])
        except requests.RequestException as e:
            raise Exception(f"Failed to generate embeddings: {e}")

    def get_dimensions(self) -> int:
        return 1024