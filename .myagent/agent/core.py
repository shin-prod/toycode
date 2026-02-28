"""エージェントコア。

会話ループ・ツール呼び出し・履歴管理の中核となるモジュール。
エージェントループの最大反復回数は settings.max_agent_loops で制御する。
"""

import json
from typing import Optional

from agent.history import ConversationHistory
from agent.stream import (
    print_ai_header,
    print_stream,
    print_summary,
    print_thinking_header,
    print_thinking_text,
    print_tool_call,
    print_tool_result,
)
from llm.base import BaseLLMClient, LLMResponse, ToolCallData
from tools.registry import ToolRegistry
from utils.logger import get_logger
from utils.spinner import Spinner
from utils.status_bar import status_bar

logger = get_logger(__name__)

_C_ERR = "\033[31m"
_C_RESET = "\033[0m"

_SYSTEM_PROMPT = """あなたは有能な AI アシスタントです。
ユーザーの要求を達成するために、提供されたツールを積極的に活用してください。
コーディング補助、ファイル操作、Office ファイル編集など幅広いタスクに対応できます。
回答は簡潔かつ正確に、日本語で行ってください。"""


class Agent:
    """LLM とツールを統合したエージェントクラス。

    ツール呼び出しが不要になるまでループし、最終回答を返す。
    最大ループ数 (max_agent_loops) を超えた場合はループを打ち切る。
    """

    def __init__(
        self,
        llm: BaseLLMClient,
        registry: ToolRegistry,
        system_prompt: Optional[str] = None,
    ) -> None:
        from config import settings

        self._settings = settings
        self.llm = llm
        self.registry = registry
        self.history = ConversationHistory(max_tokens=settings.max_context_tokens)
        self.history.set_system(system_prompt or _SYSTEM_PROMPT)

    def run(self, user_input: str) -> str:
        """ユーザー入力を受け取り、ツール呼び出しループを経て最終回答を返す。

        エージェントループ:
          1. LLM にメッセージ + ツールスキーマを送信
          2. finish_reason == 'tool_calls' の場合:
             - ツールを実行し結果を履歴に追加
             - ループを継続（max_agent_loops まで）
          3. それ以外の場合は最終回答として返す

        Args:
            user_input: ユーザーの入力テキスト

        Returns:
            アシスタントの最終回答文字列
        """
        self.history.add("user", user_input)
        max_loops = self._settings.max_agent_loops
        loop_count = 0
        tool_log: list[tuple[str, dict]] = []  # サマリー用ツールログ

        while loop_count < max_loops:
            loop_count += 1
            logger.debug("エージェントループ %d/%d", loop_count, max_loops)

            # 2回目以降は「思考 N」ヘッダーを表示
            if loop_count > 1:
                print_thinking_header(loop_count)

            if self._settings.stream:
                content, finish_reason, tool_calls_data = self._call_stream()
            else:
                response = self._call_chat()
                content = response.content or ""
                finish_reason = response.finish_reason
                tool_calls_data = self._response_to_tool_calls_data(response)

            if finish_reason == "tool_calls" and tool_calls_data:
                # 非ストリーミング時: ツール呼び出し前の中間テキストを表示
                if content and not self._settings.stream:
                    print_thinking_text(content)

                # ツール呼び出しを処理
                tool_call_objects = self._build_tool_call_objects(tool_calls_data)

                # アシスタントメッセージ（tool_calls 付き）を履歴に追加
                self.history.add_raw_message(
                    self._build_assistant_tool_message(tool_call_objects)
                )

                # ツールを実行して結果を履歴に追加
                tool_results = self._execute_tools(tool_call_objects, tool_log)
                self.history.add_tool_results(tool_results)
                # ループ継続
                continue

            # 最終回答 — ツールを1件以上使った場合はサマリーを表示
            if tool_log:
                print_summary(tool_log)
            if content:
                self.history.add("assistant", content)
            return content or "(応答なし)"

        # 最大ループ数に達した場合（サマリーを表示してから警告）
        if tool_log:
            print_summary(tool_log)
        logger.warning("エージェントループが最大回数 (%d) に達しました", max_loops)
        warning_msg = (
            f"⚠ エージェントループが上限 ({max_loops} 回) に達しました。"
            "処理を打ち切ります。"
        )
        # ストリーミングモードでは run() 内でメッセージを出力する（main.py は再表示しない）
        if self._settings.stream:
            print(f"\n{_C_ERR}{warning_msg}{_C_RESET}", flush=True)
        self.history.add("assistant", warning_msg)
        return warning_msg

    def _call_chat(self) -> LLMResponse:
        """非ストリーミングで LLM を呼び出す。呼び出し中はスピナーを表示する。"""
        status_bar.set("思案中")
        with Spinner("思考中"):
            return self.llm.chat(
                messages=self.history.get(),
                tools=self.registry.get_schemas(),
            )

    def _call_stream(self) -> tuple[str, str, dict]:
        """ストリーミングで LLM を呼び出し、結果を返す。

        テキストはバッファリングし、最終回答のときだけ表示する。

        Returns:
            (accumulated_text, finish_reason, tool_calls_data) のタプル
        """
        status_bar.set("思案中")
        spinner = Spinner("思案中").start()
        generator = self.llm.stream_chat(
            messages=self.history.get(),
            tools=self.registry.get_schemas(),
        )
        return print_stream(generator, spinner=spinner)

    def _response_to_tool_calls_data(self, response: LLMResponse) -> dict:
        """LLMResponse の tool_calls を tool_calls_data dict 形式に変換する。

        Args:
            response: LLMResponse オブジェクト

        Returns:
            {index: {"id": ..., "name": ..., "arguments": ...}} 形式の dict
        """
        if not response.tool_calls:
            return {}
        return {
            i: {
                "id": tc.id,
                "name": tc.name,
                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
            }
            for i, tc in enumerate(response.tool_calls)
        }

    def _build_tool_call_objects(self, tool_calls_data: dict) -> list[ToolCallData]:
        """tool_calls_data dict から ToolCallData のリストを構築する。

        Args:
            tool_calls_data: {index: {"id": ..., "name": ..., "arguments": ...}}

        Returns:
            ToolCallData のリスト
        """
        result = []
        for idx in sorted(tool_calls_data.keys()):
            tc = tool_calls_data[idx]
            try:
                args = json.loads(tc.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            result.append(
                ToolCallData(id=tc["id"], name=tc["name"], arguments=args)
            )
        return result

    def _build_assistant_tool_message(self, tool_calls: list[ToolCallData]) -> dict:
        """ツール呼び出しを含むアシスタントメッセージを構築する。

        Args:
            tool_calls: ToolCallData のリスト

        Returns:
            OpenAI 互換形式のアシスタントメッセージ dict
        """
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in tool_calls
            ],
        }

    def _execute_tools(
        self,
        tool_calls: list[ToolCallData],
        tool_log: list[tuple[str, dict]],
    ) -> list[dict]:
        """ツールを実行して結果リストを返す。

        Args:
            tool_calls: 実行するツール呼び出しのリスト
            tool_log: サマリー用にツール呼び出しを蓄積するリスト

        Returns:
            [{"tool_call_id": str, "name": str, "result": str}] のリスト
        """
        results = []
        for tc in tool_calls:
            status_bar.set("実行中")
            tool_log.append((tc.name, tc.arguments))  # サマリー用に記録
            print_tool_call(tc.name, tc.arguments)
            try:
                with Spinner("作業中"):
                    result = self.registry.dispatch(tc.name, tc.arguments)
            except KeyError as e:
                result = f"エラー: 未登録のツール {e}"
            except TypeError as e:
                result = f"エラー: 引数が不正です: {e}"
            except Exception as e:
                logger.error("ツール実行エラー %s: %s", tc.name, e)
                result = f"エラー: ツール実行失敗: {e}"
            print_tool_result(tc.name, result)
            results.append(
                {"tool_call_id": tc.id, "name": tc.name, "result": result}
            )
        return results
