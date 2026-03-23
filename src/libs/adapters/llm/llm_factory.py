from .base_llm import BaseLLM

class LLMFactory:
    """Factory class to create LLM instances based on configuration."""

    @staticmethod
    def create_llm(provider: str, **kwargs) -> BaseLLM:
        """Create an LLM instance based on the provider name.

        Args:
            provider (str): The name of the LLM provider (e.g., 'openai', 'ollama', 'dashscope').
            **kwargs: Additional arguments for the LLM initialization.

        Returns:
            BaseLLM: An instance of a class implementing BaseLLM.

        Raises:
            ValueError: If the provider is not supported.
        """
        if provider == "openai":
            from .providers.openai_llm import OpenAILLM
            return OpenAILLM(**kwargs)
        elif provider == "ollama":
            from .providers.ollama_llm import OllamaLLM
            return OllamaLLM(**kwargs)
        elif provider == "dashscope":
            from .providers.dashscope_llm import DashscopeLLM
            return DashscopeLLM(**kwargs)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")