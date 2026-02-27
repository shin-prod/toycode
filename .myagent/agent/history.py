"""会話履歴管理モジュール。

トークン上限に収まるよう古いメッセージを自動削除する。
"""

import json
from typing import Optional

from utils.logger import get_logger
from utils.token_counter import estimate_tokens

logger = get_logger(__name__)


class ConversationHistory:
    """OpenAI 互換形式の会話履歴を管理するクラス。

    トークン数が max_tokens を超えた場合、古いメッセージから削除する。
    ただし system メッセージは常に保持する。
    """

    def __init__(self, max_tokens: int = 128000) -> None:
        self.max_tokens = max_tokens
        self._messages: list[dict] = []

    def set_system(self, content: str) -> None:
        """システムメッセージを設定（上書き）する。

        Args:
            content: システムプロンプトの内容
        """
        # 既存の system メッセージを削除してから先頭に追加
        self._messages = [m for m in self._messages if m.get("role") != "system"]
        self._messages.insert(0, {"role": "system", "content": content})

    def add(self, role: str, content: str) -> None:
        """ユーザーまたはアシスタントのメッセージを追加する。

        Args:
            role: メッセージのロール ('user' / 'assistant')
            content: メッセージ内容
        """
        self._messages.append({"role": role, "content": content})
        self._trim()

    def add_raw_message(self, message: dict) -> None:
        """生のメッセージ dict をそのまま追加する（ツール呼び出し用）。

        Args:
            message: OpenAI 形式のメッセージ dict
        """
        self._messages.append(message)
        self._trim()

    def add_tool_results(self, tool_results: list[dict]) -> None:
        """ツール実行結果メッセージを追加する。

        Args:
            tool_results: [{"tool_call_id": str, "name": str, "result": str}] のリスト
        """
        for result in tool_results:
            self._messages.append(
                {
                    "role": "tool",
                    "tool_call_id": result["tool_call_id"],
                    "content": str(result["result"]),
                }
            )
        self._trim()

    def get(self) -> list[dict]:
        """現在の会話履歴を返す。

        Returns:
            メッセージのリスト（コピー）
        """
        return list(self._messages)

    def clear(self) -> None:
        """会話履歴をクリアする（system メッセージは保持）。"""
        system_msgs = [m for m in self._messages if m.get("role") == "system"]
        self._messages = system_msgs

    def token_count(self) -> int:
        """現在の履歴のトークン数を概算する。"""
        return estimate_tokens(self._messages)

    def _trim(self) -> None:
        """トークン上限を超えた場合、古いメッセージから削除する。

        system メッセージと最新のメッセージは保持する。
        """
        while self.token_count() > self.max_tokens and len(self._messages) > 2:
            # system メッセージ以外の最古のメッセージを削除
            for i, msg in enumerate(self._messages):
                if msg.get("role") != "system":
                    logger.debug("履歴トリム: index=%d role=%s", i, msg.get("role"))
                    self._messages.pop(i)
                    break
            else:
                break
