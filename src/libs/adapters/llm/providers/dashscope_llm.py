import requests
from langchain_openai import ChatOpenAI

class DashscopeLLM(ChatOpenAI):
    """
    Implementation of Dashscope's Qwen3-Max model provider.
    """

    def __init__(
        self, 
        api_base: str, 
        api_key: str, 
        model: str, 
        temperature: float = 0.7, 
        max_tokens: int = 2000, 
        timeout: int = 60,
        **kwargs
    ):
        # 核心逻辑：将你的自定义参数映射到 ChatOpenAI 的标准参数名上
        super().__init__(
            model=model,
            openai_api_key=api_key,
            openai_api_base=api_base, # 必须是百炼的 v1 兼容地址
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            **kwargs
        )

    # def generate(self, prompt: str) -> str:
    #     """
    #     Generate a response from the Qwen3-Max model.

    #     Args:
    #         prompt (str): The input prompt for the model.

    #     Returns:
    #         str: The generated response.

    #     Raises:
    #         Exception: If the API request fails.
    #     """
    #     headers = {
    #         "Authorization": f"Bearer {self.api_key}",
    #         "Content-Type": "application/json"
    #     }
    #     payload = {
    #         "model": self.model,
    #         "prompt": prompt,
    #         "temperature": self.temperature,
    #         "max_tokens": self.max_tokens
    #     }

    #     try:
    #         response = requests.post(f"{self.api_base}/completions", json=payload, headers=headers, timeout=self.timeout)
    #         response.raise_for_status()
    #         result = response.json()
    #         return result.get("choices", [{}])[0].get("text", "")
    #     except requests.RequestException as e:
    #         raise Exception(f"Failed to generate response: {e}")
        

    # def get_model_name(self) -> str:
    #     return "Dashscope"