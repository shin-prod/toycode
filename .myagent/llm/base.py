"""LLM クライアント基底クラスと共通データ型の定義。"""

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generator, Optional


@dataclass
class ToolCallData:
    """LLM が要求したツール呼び出しの情報。"""

    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    """LLM の応答を表すデータクラス。"""

    content: Optional[str]
    finish_reason: str
    tool_calls: Optional[list[ToolCallData]] = None
    # OpenAI 互換形式の生アシスタントメッセージ（履歴に追加するために使用）
    raw_message: dict = field(default_factory=dict)


class BaseLLMClient(ABC):
    """OpenRouter / Azure OpenAI 共通インターフェース。"""

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
    ) -> LLMResponse:
        """非ストリーミングで LLM を呼び出す。

        Args:
            messages: 会話履歴（OpenAI 形式）
            tools: Function Calling スキーマ一覧

        Returns:
            LLMResponse オブジェクト
        """
        ...

    @abstractmethod
    def stream_chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
    ) -> Generator[tuple, None, None]:
        """ストリーミングで LLM を呼び出す。

        Yields:
            ('text', str)       : テキストチャンク
            ('done', str, dict) : 終了イベント (finish_reason, tool_calls_data)
        """
        ...

    # ------------------------------------------------------------------
    # 共通ユーティリティ（サブクラスで使用）
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response_body(body: dict) -> LLMResponse:
        """OpenAI 互換レスポンス dict を LLMResponse に変換する共通処理。

        Args:
            body: /chat/completions レスポンスの dict

        Returns:
            LLMResponse オブジェクト
        """
        choice = body["choices"][0]
        message = choice["message"]
        finish_reason = choice.get("finish_reason", "stop")

        tool_calls = None
        raw_tool_calls = message.get("tool_calls")
        if raw_tool_calls:
            tool_calls = [
                ToolCallData(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(tc["function"].get("arguments", "{}")),
                )
                for tc in raw_tool_calls
            ]

        return LLMResponse(
            content=message.get("content"),
            finish_reason=finish_reason,
            tool_calls=tool_calls,
            raw_message=message,
        )

    @staticmethod
    def _iter_sse_stream(
        req: urllib.request.Request,
    ) -> Generator[tuple, None, None]:
        """SSE ストリームを読み取り、テキストチャンクとツール呼び出しを yield する。

        OpenRouter / Azure OpenAI の両方で共通の SSE 形式をパースする。

        Args:
            req: 送信済み urllib.request.Request オブジェクト

        Yields:
            ('text', str)           : テキストチャンク
            ('done', str, dict)     : 完了 (finish_reason, tool_calls_data)

        Raises:
            RuntimeError: HTTP エラーが発生した場合
        """
        tool_calls_accumulator: dict[int, dict] = {}
        finish_reason = "stop"

        try:
            with urllib.request.urlopen(req) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choice = chunk.get("choices", [{}])[0]
                    delta = choice.get("delta", {})
                    finish_reason = choice.get("finish_reason") or finish_reason

                    content = delta.get("content")
                    if content:
                        yield ("text", content)

                    for tc in delta.get("tool_calls", []):
                        idx = tc.get("index", 0)
                        if idx not in tool_calls_accumulator:
                            tool_calls_accumulator[idx] = {
                                "id": "",
                                "name": "",
                                "arguments": "",
                            }
                        acc = tool_calls_accumulator[idx]
                        if tc.get("id"):
                            acc["id"] = tc["id"]
                        func = tc.get("function", {})
                        if func.get("name"):
                            acc["name"] = func["name"]
                        if func.get("arguments"):
                            acc["arguments"] += func["arguments"]

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise RuntimeError(f"API エラー {e.code}: {error_body}") from e

        yield ("done", finish_reason, tool_calls_accumulator)
