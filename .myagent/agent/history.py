"""会話履歴管理モジュール。

Codex CLI (github.com/openai/codex) の context_manager/history.rs を
Python に移植。主な改善点:
  - normalize(): tool_call/tool_result ペアの整合性を保証
  - _drop_oldest_user_turn(): ターン単位のスマートトリミング
  - for_prompt(): API 送信用に正規化した履歴を返す
"""

import json

from utils.logger import get_logger

logger = get_logger(__name__)


class ContextManager:
    """OpenAI 互換形式の会話履歴を管理するコンテキストマネージャー。

    Codex の ContextManager を Python に移植。
    トークン数が max_tokens を超えた場合、ターン境界単位で古いターンを削除する。
    system メッセージは常に保持する。
    """

    def __init__(self, max_tokens: int = 128_000) -> None:
        self.max_tokens = max_tokens
        self._items: list[dict] = []

    # ---- 設定 ----------------------------------------------------------------

    def set_system(self, content: str) -> None:
        """システムメッセージを設定（上書き）する。

        Args:
            content: システムプロンプトの内容
        """
        self._items = [m for m in self._items if m.get("role") != "system"]
        self._items.insert(0, {"role": "system", "content": content})

    # ---- 追加 ----------------------------------------------------------------

    def record_items(self, items: list[dict]) -> None:
        """アイテムを履歴に追加し、トークン上限チェックを行う。

        Codex の record_items() に相当。

        Args:
            items: 追加するメッセージのリスト
        """
        self._items.extend(items)
        self._maybe_trim()

    def add(self, role: str, content: str) -> None:
        """後方互換: user/assistant メッセージを追加する。

        Args:
            role: メッセージのロール ('user' / 'assistant')
            content: メッセージ内容
        """
        self.record_items([{"role": role, "content": content}])

    def add_raw_message(self, message: dict) -> None:
        """後方互換: 生のメッセージ dict をそのまま追加する（ツール呼び出し用）。

        Args:
            message: OpenAI 形式のメッセージ dict
        """
        self.record_items([message])

    def add_tool_results(self, tool_results: list[dict]) -> None:
        """ツール実行結果メッセージを追加する。

        Args:
            tool_results: [{"tool_call_id": str, "name": str, "result": str}] のリスト
        """
        items = [
            {
                "role": "tool",
                "tool_call_id": r["tool_call_id"],
                "content": str(r["result"]),
            }
            for r in tool_results
        ]
        self.record_items(items)

    # ---- 参照 ----------------------------------------------------------------

    def for_prompt(self) -> list[dict]:
        """API 送信用に正規化された履歴のコピーを返す。

        Codex の for_prompt() に相当。_normalize() を適用してから返す。

        Returns:
            正規化済みメッセージのリスト（コピー）
        """
        return list(self._normalize(list(self._items)))

    def get(self) -> list[dict]:
        """後方互換: for_prompt() のエイリアス。

        Returns:
            正規化済みメッセージのリスト（コピー）
        """
        return self.for_prompt()

    def clear(self) -> None:
        """後方互換: 履歴をクリアする（system メッセージは保持）。"""
        self._items = [m for m in self._items if m.get("role") == "system"]

    def token_count(self) -> int:
        """現在の履歴の推定トークン数を返す。"""
        return self.estimate_tokens()

    def estimate_tokens(self) -> int:
        """バイト数ベースのトークン数概算。

        Codex と同じ方式: 4 bytes ≈ 1 token。

        Returns:
            推定トークン数
        """
        total_bytes = sum(
            len(json.dumps(item, ensure_ascii=False).encode("utf-8"))
            for item in self._items
        )
        return total_bytes // 4

    # ---- トリミング ----------------------------------------------------------

    def _maybe_trim(self) -> None:
        """トークン上限を超えたらターン単位でトリミングする。

        Codex の drop_last_n_user_turns() に相当。
        個別メッセージではなく user ターン境界単位で削除することで
        tool_call/result ペアが壊れるのを防ぐ。
        """
        while self.estimate_tokens() > self.max_tokens:
            if not self._drop_oldest_user_turn():
                break

    def _drop_oldest_user_turn(self) -> bool:
        """最古の user ターン（user メッセージから次の user メッセージ直前まで）を削除する。

        Returns:
            削除できた場合 True、削除できなかった場合 False
        """
        # system メッセージの直後から探す
        start = 0
        for i, msg in enumerate(self._items):
            if msg.get("role") == "system":
                start = i + 1

        # start 以降の最初の user メッセージを見つける
        first_user_idx = None
        for i in range(start, len(self._items)):
            if self._items[i].get("role") == "user":
                first_user_idx = i
                break

        if first_user_idx is None:
            return False

        # 次の user メッセージの直前までを「1ターン」として削除
        next_user_idx = None
        for i in range(first_user_idx + 1, len(self._items)):
            if self._items[i].get("role") == "user":
                next_user_idx = i
                break

        end_idx = next_user_idx if next_user_idx is not None else len(self._items)
        removed_count = end_idx - first_user_idx
        self._items = self._items[:first_user_idx] + self._items[end_idx:]

        logger.debug(
            "ターントリム: %d アイテムを削除 (推定トークン: %d)",
            removed_count,
            self.estimate_tokens(),
        )
        return True

    # ---- 正規化 --------------------------------------------------------------

    @staticmethod
    def _normalize(items: list[dict]) -> list[dict]:
        """tool_call/tool_result ペアの整合性を保証する。

        Codex の normalize_history() に相当。以下の不整合を修正:
          1. tool_call に対応する tool_result がない → 合成エラー結果を追加
          2. tool_result に対応する tool_call がない → tool_result を削除

        Args:
            items: 正規化前のメッセージリスト

        Returns:
            正規化後のメッセージリスト
        """
        result: list[dict] = []
        expected_tool_ids: set[str] = set()

        for msg in items:
            role = msg.get("role")

            if role == "assistant" and msg.get("tool_calls"):
                # 前の assistant の tool_calls が未解決なら合成結果を挿入
                if expected_tool_ids:
                    for tc_id in sorted(expected_tool_ids):
                        result.append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": "(中断されました)",
                        })
                    expected_tool_ids.clear()
                result.append(msg)
                for tc in msg["tool_calls"]:
                    expected_tool_ids.add(tc["id"])

            elif role == "tool":
                tc_id = msg.get("tool_call_id", "")
                if tc_id in expected_tool_ids:
                    result.append(msg)
                    expected_tool_ids.discard(tc_id)
                else:
                    # 対応する tool_call がない孤立した tool_result → 削除
                    logger.debug("孤立した tool_result を削除: %s", tc_id)

            else:
                # 通常メッセージ: 未解決の tool_call があれば合成結果を先に挿入
                if expected_tool_ids:
                    for tc_id in sorted(expected_tool_ids):
                        result.append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": "(中断されました)",
                        })
                    expected_tool_ids.clear()
                result.append(msg)

        # 末尾に未解決の tool_call が残っていたら合成エラーを追加
        for tc_id in sorted(expected_tool_ids):
            result.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": "(中断されました)",
            })

        return result


# 後方互換エイリアス
ConversationHistory = ContextManager
