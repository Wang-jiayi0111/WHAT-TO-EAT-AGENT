"""
LangChain Adapter for LLM providers to enable structured output and other LangChain features.
This module provides wrappers that make custom LLM implementations compatible with LangChain.
"""

from typing import Dict, List, Optional, Any, Mapping, Union
from langchain_core.language_models.llms import LLM
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.outputs import GenerationChunk
import requests
import json


class LangChainLLMAdapter(LLM):
    """
    Adapter to make custom LLM implementations compatible with LangChain.
    This allows the use of structured output and other LangChain features.
    """

    # Define the fields that will be passed to the constructor
    api_base: str
    api_key: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 2000
    timeout: int = 60

    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "custom_langchain_adapter"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Run the LLM on the given prompt and return the result."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Prepare the payload for the API call
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

        # Add any additional parameters from kwargs
        for key, value in kwargs.items():
            if key not in payload:
                payload[key] = value

        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()

            result = response.json()
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")
        except requests.RequestException as e:
            raise Exception(f"Failed to generate response: {e}")

    def _stream(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ):
        """Stream the LLM on the given prompt and return the result."""
        # For now, just return the full response since streaming implementation
        # would require more complex handling
        result = self._call(prompt, stop, run_manager, **kwargs)
        yield GenerationChunk(text=result)

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        return {
            "model": self.model,
            "api_base": self.api_base,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }