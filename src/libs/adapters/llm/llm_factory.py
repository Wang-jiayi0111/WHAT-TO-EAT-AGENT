from .base_llm import BaseLLM
from ...base.settings import Settings


class LLMFactory:
    """Factory class to create LLM instances based on configuration."""

    @staticmethod
    def get_llm(settings=None):
        """Get an LLM instance based on configuration.

        Args:
            settings: Settings object containing configuration. If None, uses default settings.

        Returns:
            BaseLLM: An instance of a class implementing BaseLLM.
        """
        if settings is None:
            settings = Settings()

        llm_config = settings.get("llm", {})
        provider = llm_config.get("provider", "openai")
        model = llm_config.get("model", "gpt-3.5-turbo")
        api_key = llm_config.get("api_key", "")
        api_base = llm_config.get("api_base", None)

        return LLMFactory.create_llm(
            provider=provider,
            model=model,
            api_key=api_key,
            api_base=api_base
        )

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