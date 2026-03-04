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
        """tool_call/tool_result ペアの整合性を保証する（2パス方式）。

        Codex の normalize_history() → ensure_call_outputs_present() +
        remove_orphan_outputs() の Python 移植。

        Pass 1 (ensure_call_outputs_present 相当):
          対応する tool_result のない tool_call の直後に合成エラー結果を挿入。
          インデックスがずれないよう逆順で挿入する。

        Pass 2 (remove_orphan_outputs 相当):
          Pass 1 完了後に、対応する tool_call のない孤立 tool_result を削除。

        Args:
            items: 正規化前のメッセージリスト（元のリストは変更しない）

        Returns:
            正規化後の新しいメッセージリスト
        """
        # Pass 1: ensure_call_outputs_present
        # 既存の tool_result の call_id セットを収集
        existing_result_ids: set[str] = {
            msg["tool_call_id"]
            for msg in items
            if msg.get("role") == "tool" and "tool_call_id" in msg
        }

        # 対応する tool_result がない tool_call を見つけ、直後への挿入を予約
        inserts: list[tuple[int, dict]] = []  # (挿入位置, 合成メッセージ)
        for idx, msg in enumerate(items):
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    tc_id = tc.get("id", "")
                    if tc_id and tc_id not in existing_result_ids:
                        logger.debug("ツール結果が存在しない: %s → 合成結果を挿入", tc_id)
                        inserts.append((idx, {
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": "(中断されました)",
                        }))

        # インデックスがずれないよう逆順に挿入
        result = list(items)
        for insert_idx, synthetic in reversed(inserts):
            result.insert(insert_idx + 1, synthetic)

        # Pass 2: remove_orphan_outputs
        # Pass 1 完了後のすべての tool_call ID を収集
        call_ids: set[str] = {
            tc.get("id", "")
            for msg in result
            if msg.get("role") == "assistant" and msg.get("tool_calls")
            for tc in msg.get("tool_calls", [])
        }

        normalized: list[dict] = []
        for msg in result:
            if msg.get("role") == "tool":
                tc_id = msg.get("tool_call_id", "")
                if tc_id in call_ids:
                    normalized.append(msg)
                else:
                    logger.debug("孤立した tool_result を削除: %s", tc_id)
            else:
                normalized.append(msg)

        return normalized


# 後方互換エイリアス
ConversationHistory = ContextManager
