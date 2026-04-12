from .base_embed import BaseEmbed
from ...base.settings import Settings


class EmbedFactory:
    """Factory class to create embedding instances based on configuration."""

    @staticmethod
    def get_embed(settings=None):
        """Get an embedding instance based on configuration.

        Args:
            settings: Settings object containing configuration. If None, uses default settings.

        Returns:
            BaseEmbed: An instance of a class implementing BaseEmbed.
        """
        if settings is None:
            settings = Settings()

        embed_config = settings.get("embedding", {})  # Using "embedding" as the key in settings
        provider = embed_config.get("provider", "dashscope")  # Default to dashscope for embedding
        model = embed_config.get("model", "text-embedding-v4")
        api_key = embed_config.get("api_key", "")
        api_base = embed_config.get("api_base", None)

        return EmbedFactory.create_embed(
            provider=provider,
            model=model,
            api_key=api_key
        )


    @staticmethod
    def create_embed(provider: str, **kwargs) -> BaseEmbed:
        """Create an embedding instance based on the provider name.

        Args:
            provider (str): The name of the embedding provider (e.g., 'openai', 'azure', 'dashscope').
            **kwargs: Additional arguments for the embedding initialization.

        Returns:
            BaseEmbed: An instance of a class implementing BaseEmbed.

        Raises:
            ValueError: If the provider is not supported.
        """
        if provider == "openai":
            from .providers.openai_embed import OpenAIEmbed
            return OpenAIEmbed(**kwargs)
        elif provider == "dashscope":
            from .providers.dashscope_embed import DashscopeEmbed
            return DashscopeEmbed(**kwargs)
        else:
            raise ValueError(f"Unsupported embedding provider: {provider}")