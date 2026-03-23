import pytest
import yaml
from src.libs.adapters.embed.embed_factory import EmbedFactory
from src.libs.adapters.embed.providers.openai_embed import OpenAIEmbed
from src.libs.adapters.embed.providers.dashscope_embed import DashscopeEmbed

# Load settings from the YAML configuration file
with open("config/setting.yaml", "r", encoding="utf-8") as file:
    settings = yaml.safe_load(file)

def test_create_openai_embed():
    embed = EmbedFactory.create_embed("openai", api_key="test_key")
    assert isinstance(embed, OpenAIEmbed)
    assert embed.get_dimensions() == 1536

def test_invalid_provider():
    with pytest.raises(ValueError):
        EmbedFactory.create_embed("invalid_provider")

def test_create_dashscope_embed():
    """Test the creation of a DashscopeEmbed instance using the factory with settings from the configuration file."""
    embed_config = settings["embedding"]

    provider = embed_config["provider"]
    api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key = "test_api_key"  # Replace with a mock or test key
    model = embed_config["model"]
    timeout = 60

    embed = EmbedFactory.create_embed(
        provider=provider,
        api_base=api_base,
        api_key=api_key,
        model=model,
        timeout=timeout
    )

    assert isinstance(embed, DashscopeEmbed)
    assert embed.api_base == api_base
    assert embed.api_key == api_key
    assert embed.model == model
    assert embed.timeout == timeout