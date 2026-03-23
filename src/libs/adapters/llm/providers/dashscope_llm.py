import requests
from ..base_llm import BaseLLM

class DashscopeLLM(BaseLLM):
    """
    Implementation of Dashscope's Qwen3-Max model provider.
    """

    def __init__(self, api_base: str, api_key: str, model: str, temperature: float = 0.7, max_tokens: int = 2000, timeout: int = 60):
        """
        Initialize the DashscopeLLM instance.

        Args:
            api_base (str): The base URL for the Dashscope API.
            api_key (str): The API key for authentication.
            model (str): The model identifier (e.g., 'qwen3-max').
            temperature (float): Sampling temperature.
            max_tokens (int): Maximum number of tokens to generate.
            timeout (int): Request timeout in seconds.
        """
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        """
        Generate a response from the Qwen3-Max model.

        Args:
            prompt (str): The input prompt for the model.

        Returns:
            str: The generated response.

        Raises:
            Exception: If the API request fails.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

        try:
            response = requests.post(f"{self.api_base}/completions", json=payload, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            return result.get("choices", [{}])[0].get("text", "")
        except requests.RequestException as e:
            raise Exception(f"Failed to generate response: {e}")
        

    def get_model_name(self) -> str:
        return "Dashscope"