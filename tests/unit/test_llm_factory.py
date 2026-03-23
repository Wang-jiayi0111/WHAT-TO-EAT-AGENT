import pytest
import yaml
from src.libs.adapters.llm.llm_factory import LLMFactory
from src.libs.adapters.llm.providers.openai_llm import OpenAILLM
from src.libs.adapters.llm.providers.ollama_llm import OllamaLLM
from src.libs.adapters.llm.providers.dashscope_llm import DashscopeLLM

# Load settings from the YAML configuration file
with open("config/setting.yaml", "r", encoding="utf-8") as file:
    settings = yaml.safe_load(file)

def test_create_openai_llm():
    llm = LLMFactory.create_llm("openai", api_key="test_key")
    assert isinstance(llm, OpenAILLM)
    assert llm.get_model_name() == "OpenAI"

def test_create_ollama_llm():
    llm = LLMFactory.create_llm("ollama", model_path="/path/to/model")
    assert isinstance(llm, OllamaLLM)
    assert llm.get_model_name() == "Ollama"

def test_create_dashscope_llm():
    """Test the creation of a DashscopeLLM instance using the factory with settings from the configuration file."""
    llm_config = settings["llm"]

    provider = llm_config["provider"]
    api_base = llm_config["api_base"]
    api_key = "test_api_key"  # Replace with a mock or test key
    model = llm_config["model"]
    temperature = llm_config["temperature"]
    max_tokens = llm_config["max_tokens"]
    timeout = llm_config["timeout"]

    llm = LLMFactory.create_llm(
        provider=provider,
        api_base=api_base,
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout
    )

    assert isinstance(llm, DashscopeLLM)
    assert llm.api_base == api_base
    assert llm.api_key == api_key
    assert llm.model == model
    assert llm.temperature == temperature
    assert llm.max_tokens == max_tokens
    assert llm.timeout == timeout

def test_invalid_provider():
    with pytest.raises(ValueError):
        LLMFactory.create_llm("invalid_provider")