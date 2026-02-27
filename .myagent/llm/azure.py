"""Azure OpenAI LLM クライアント。urllib.request のみを使用して実装する。"""

import json
import urllib.error
import urllib.request
from typing import Generator, Optional

from llm.base import BaseLLMClient, LLMResponse
from utils.logger import get_logger

logger = get_logger(__name__)


class AzureOpenAIClient(BaseLLMClient):
    """Azure OpenAI API クライアント。"""

    def __init__(self) -> None:
        from config import settings

        self._settings = settings

    def _build_url(self) -> str:
        """Azure OpenAI エンドポイント URL を構築する。"""
        base = self._settings.azure_endpoint.rstrip("/")
        deployment = self._settings.azure_deployment
        version = self._settings.azure_api_version
        return (
            f"{base}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={version}"
        )

    def _build_headers(self) -> dict:
        """リクエストヘッダーを構築する。"""
        return {
            "api-key": self._settings.azure_api_key,
            "Content-Type": "application/json",
        }

    def _build_payload(
        self,
        messages: list[dict],
        tools: Optional[list[dict]],
        stream: bool = False,
    ) -> dict:
        """リクエストボディを構築する。"""
        payload: dict = {
            "messages": messages,
            "max_tokens": self._settings.max_output_tokens,
            "temperature": self._settings.temperature,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
        return payload

    def _make_request(self, payload: dict) -> urllib.request.Request:
        """urllib.request.Request オブジェクトを生成する。"""
        url = self._build_url()
        data = json.dumps(payload).encode("utf-8")
        return urllib.request.Request(
            url, data=data, headers=self._build_headers(), method="POST"
        )

    def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
    ) -> LLMResponse:
        """非ストリーミングで Azure OpenAI を呼び出す。"""
        payload = self._build_payload(messages, tools, stream=False)
        req = self._make_request(payload)
        logger.debug(
            "Azure OpenAI chat リクエスト送信: deployment=%s",
            self._settings.azure_deployment,
        )
        try:
            with urllib.request.urlopen(req, context=self._ssl_context()) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            logger.error("Azure OpenAI API エラー: %s %s", e.code, error_body)
            raise RuntimeError(
                f"Azure OpenAI API エラー {e.code}: {error_body}"
            ) from e

        return self._parse_response_body(body)

    def stream_chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
    ) -> Generator[tuple, None, None]:
        """ストリーミングで Azure OpenAI を呼び出す。

        Yields:
            ('text', str)           : テキストチャンク
            ('done', str, dict)     : 完了 (finish_reason, tool_calls_data)
        """
        payload = self._build_payload(messages, tools, stream=True)
        req = self._make_request(payload)
        logger.debug("Azure OpenAI stream_chat リクエスト送信")
        try:
            yield from self._iter_sse_stream(req)
        except RuntimeError as e:
            logger.error("Azure OpenAI ストリーミングエラー: %s", e)
            raise
