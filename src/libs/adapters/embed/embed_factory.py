from .base_embed import BaseEmbed

class EmbedFactory:
    """Factory class to create embedding instances based on configuration."""

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