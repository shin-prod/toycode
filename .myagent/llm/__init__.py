from llm.base import BaseLLMClient, LLMResponse, ToolCallData
from llm.openrouter import OpenRouterClient
from llm.azure import AzureOpenAIClient


def get_client() -> BaseLLMClient:
    """LLM_PROVIDER に応じてクライアントを返すファクトリ関数。"""
    from config import settings

    provider = settings.provider.lower()
    if provider == "azure":
        return AzureOpenAIClient()
    elif provider == "openrouter":
        return OpenRouterClient()
    else:
        raise ValueError(f"未対応の LLM_PROVIDER: {provider}")


__all__ = [
    "BaseLLMClient",
    "LLMResponse",
    "ToolCallData",
    "OpenRouterClient",
    "AzureOpenAIClient",
    "get_client",
]
