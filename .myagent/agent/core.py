"""エージェントコア。

Codex CLI (github.com/openai/codex) のエージェントループアーキテクチャを
Python に移植したモジュール。

主な変更点 (Codex から移植):
  - TurnContext: ターンごとの独立した状態管理（ループ制御・キャンセル）
  - run_turn(): コアループを独立した関数として分離（Codex の run_turn() に相当）
  - Agent.run(): TurnContext を生成して run_turn() に委譲するシンプルな設計
  - ContextManager: history.py で履歴の正規化・スマートトリミングを実現
"""

import json
import threading
from dataclasses import dataclass, field
from typing import Optional

from agent.history import ContextManager
from agent.stream import (
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


# ---------------------------------------------------------------------------
# TurnContext  (Codex TurnContext の Python 移植)
# ---------------------------------------------------------------------------


@dataclass
class TurnContext:
    """1ターン分の実行コンテキスト。

    Codex の TurnContext を Python に移植。
    ターンごとに独立した状態を保持し、ループ制御・キャンセルを管理する。

    Attributes:
        max_loops: エージェントループの最大反復回数
        cancel_event: キャンセルシグナル（threading.Event）
        loop_count: 現在のループカウント（内部状態、__init__ 対象外）
        tool_log: サマリー表示用ツール呼び出しログ
    """

    max_loops: int
    cancel_event: threading.Event = field(default_factory=threading.Event)
    loop_count: int = field(default=0, init=False)
    tool_log: list[tuple[str, dict]] = field(default_factory=list)

    def is_cancelled(self) -> bool:
        """キャンセルされているか確認する。"""
        return self.cancel_event.is_set()

    def increment_loop(self) -> bool:
        """ループカウンタをインクリメントし、上限内なら True を返す。

        Returns:
            loop_count <= max_loops なら True
        """
        self.loop_count += 1
        return self.loop_count <= self.max_loops


# ---------------------------------------------------------------------------
# run_turn()  (Codex run_turn() の Python 移植)
# ---------------------------------------------------------------------------


def run_turn(
    llm: BaseLLMClient,
    registry: ToolRegistry,
    context: ContextManager,
    turn_ctx: TurnContext,
    stream: bool,
) -> str:
    """エージェントループのコア関数。

    Codex の run_turn() に相当。tool_calls が不要になるまでループし、
    最終回答を返す。

    Args:
        llm: LLM クライアント
        registry: ツールレジストリ
        context: コンテキストマネージャー（会話履歴を含む）
        turn_ctx: ターンコンテキスト（ループ制御・キャンセル）
        stream: ストリーミングモードか否か

    Returns:
        アシスタントの最終回答文字列
    """
    while turn_ctx.increment_loop():
        if turn_ctx.is_cancelled():
            logger.info("ターンがキャンセルされました")
            return "(キャンセルされました)"

        loop_count = turn_ctx.loop_count
        logger.debug("エージェントループ %d/%d", loop_count, turn_ctx.max_loops)

        # 2回目以降は「思考 N」ヘッダーを表示
        if loop_count > 1:
            print_thinking_header(loop_count)

        # LLM 呼び出し
        if stream:
            content, finish_reason, tool_calls_data = _call_stream(
                llm, context, registry
            )
        else:
            response = _call_chat(llm, context, registry)
            content = response.content or ""
            finish_reason = response.finish_reason
            tool_calls_data = _response_to_tool_calls_data(response)

        # ツール呼び出しの処理
        if finish_reason == "tool_calls" and tool_calls_data:
            # 非ストリーミング時: ツール呼び出し前の中間テキストを表示
            if content and not stream:
                print_thinking_text(content)

            tool_call_objects = _build_tool_call_objects(tool_calls_data)

            # アシスタントメッセージ（tool_calls 付き）を履歴に追加
            context.add_raw_message(_build_assistant_tool_message(tool_call_objects))

            # ツールを実行して結果を履歴に追加
            tool_results = _execute_tools(
                tool_call_objects, registry, turn_ctx.tool_log
            )
            context.add_tool_results(tool_results)
            continue

        # 最終回答
        if turn_ctx.tool_log:
            print_summary(turn_ctx.tool_log)
        if content:
            context.add("assistant", content)
        return content or "(応答なし)"

    # 最大ループ数超過
    if turn_ctx.tool_log:
        print_summary(turn_ctx.tool_log)
    logger.warning("エージェントループが最大回数 (%d) に達しました", turn_ctx.max_loops)
    warning_msg = (
        f"⚠ エージェントループが上限 ({turn_ctx.max_loops} 回) に達しました。"
        "処理を打ち切ります。"
    )
    if stream:
        print(f"\n{_C_ERR}{warning_msg}{_C_RESET}", flush=True)
    context.add("assistant", warning_msg)
    return warning_msg


# ---------------------------------------------------------------------------
# Agent  (セッションレベルのラッパー)
# ---------------------------------------------------------------------------


class Agent:
    """LLM とツールを統合したエージェントクラス。

    Codex の Session/RegularTask を Python に移植。
    セッションレベルの状態（履歴・設定）を管理し、
    各ユーザー入力に対して TurnContext を生成して run_turn() に委譲する。
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
        self.history = ContextManager(max_tokens=settings.max_context_tokens)
        self.history.set_system(system_prompt or _SYSTEM_PROMPT)
        self._current_turn_ctx: Optional[TurnContext] = None

    def cancel_current_turn(self) -> None:
        """実行中のターンをキャンセルする。

        TurnContext の cancel_event をセットする。
        run_turn() は次の is_cancelled() チェックで "(キャンセルされました)" を返す。
        """
        if self._current_turn_ctx is not None:
            self._current_turn_ctx.cancel_event.set()

    def run(self, user_input: str) -> str:
        """ユーザー入力を受け取り、ターンを実行して最終回答を返す。

        Codex の Session が UserTurn Op を受け取り RegularTask.run() を
        呼び出すフローに相当。

        Args:
            user_input: ユーザーの入力テキスト

        Returns:
            アシスタントの最終回答文字列
        """
        self.history.add("user", user_input)
        turn_ctx = TurnContext(max_loops=self._settings.max_agent_loops)
        self._current_turn_ctx = turn_ctx
        try:
            return run_turn(
                llm=self.llm,
                registry=self.registry,
                context=self.history,
                turn_ctx=turn_ctx,
                stream=self._settings.stream,
            )
        finally:
            self._current_turn_ctx = None


# ---------------------------------------------------------------------------
# 内部ヘルパー関数
# ---------------------------------------------------------------------------


def _call_chat(
    llm: BaseLLMClient,
    context: ContextManager,
    registry: ToolRegistry,
) -> LLMResponse:
    """非ストリーミングで LLM を呼び出す。呼び出し中はスピナーを表示する。"""
    status_bar.set("思案中")
    with Spinner("思考中"):
        return llm.chat(
            messages=context.for_prompt(),
            tools=registry.get_schemas(),
        )


def _call_stream(
    llm: BaseLLMClient,
    context: ContextManager,
    registry: ToolRegistry,
) -> tuple[str, str, dict]:
    """ストリーミングで LLM を呼び出し、結果を返す。

    Returns:
        (accumulated_text, finish_reason, tool_calls_data) のタプル
    """
    status_bar.set("思案中")
    spinner = Spinner("思案中").start()
    generator = llm.stream_chat(
        messages=context.for_prompt(),
        tools=registry.get_schemas(),
    )
    return print_stream(generator, spinner=spinner)


def _response_to_tool_calls_data(response: LLMResponse) -> dict:
    """LLMResponse の tool_calls を tool_calls_data dict 形式に変換する。

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


def _build_tool_call_objects(tool_calls_data: dict) -> list[ToolCallData]:
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
        result.append(ToolCallData(id=tc["id"], name=tc["name"], arguments=args))
    return result


def _build_assistant_tool_message(tool_calls: list[ToolCallData]) -> dict:
    """ツール呼び出しを含むアシスタントメッセージを構築する。

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
    tool_calls: list[ToolCallData],
    registry: ToolRegistry,
    tool_log: list[tuple[str, dict]],
) -> list[dict]:
    """ツールを実行して結果リストを返す。

    Args:
        tool_calls: 実行するツール呼び出しのリスト
        registry: ツールレジストリ
        tool_log: サマリー用にツール呼び出しを蓄積するリスト

    Returns:
        [{"tool_call_id": str, "name": str, "result": str}] のリスト
    """
    results = []
    for tc in tool_calls:
        status_bar.set("実行中")
        tool_log.append((tc.name, tc.arguments))
        print_tool_call(tc.name, tc.arguments)
        try:
            with Spinner("作業中"):
                result = registry.dispatch(tc.name, tc.arguments)
        except KeyError as e:
            result = f"エラー: 未登録のツール {e}"
        except TypeError as e:
            result = f"エラー: 引数が不正です: {e}"
        except Exception as e:
            logger.error("ツール実行エラー %s: %s", tc.name, e)
            result = f"エラー: ツール実行失敗: {e}"
        print_tool_result(tc.name, result)
        results.append({"tool_call_id": tc.id, "name": tc.name, "result": result})
    return results
