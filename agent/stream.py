"""ストリーミング出力ユーティリティ。"""

import sys
from typing import Generator

from utils.logger import get_logger

logger = get_logger(__name__)


def print_stream(text_generator: Generator[tuple, None, None]) -> tuple[str, str, dict]:
    """ストリーミングジェネレータからテキストを受け取りリアルタイム表示する。

    Args:
        text_generator: ('text', str) / ('done', finish_reason, tool_calls_data)
                        を yield するジェネレータ

    Returns:
        (accumulated_text, finish_reason, tool_calls_data) のタプル
    """
    accumulated: list[str] = []
    finish_reason = "stop"
    tool_calls_data: dict = {}

    for event in text_generator:
        if event[0] == "text":
            chunk = event[1]
            accumulated.append(chunk)
            print(chunk, end="", flush=True)
        elif event[0] == "done":
            finish_reason = event[1] if len(event) > 1 else "stop"
            tool_calls_data = event[2] if len(event) > 2 else {}

    # テキスト出力後に改行
    if accumulated:
        print()

    return "".join(accumulated), finish_reason, tool_calls_data


def print_tool_call(tool_name: str, args: dict) -> None:
    """ツール呼び出しをターミナルに表示する。

    Args:
        tool_name: ツール名
        args: ツール引数
    """
    args_str = ", ".join(f"{k}={repr(v)}" for k, v in args.items())
    print(f"\n\033[33m[ツール呼び出し] {tool_name}({args_str})\033[0m", flush=True)


def print_tool_result(tool_name: str, result: str, truncate: int = 500) -> None:
    """ツール実行結果をターミナルに表示する。

    Args:
        tool_name: ツール名
        result: ツール実行結果
        truncate: 表示する最大文字数
    """
    display = result if len(result) <= truncate else result[:truncate] + "...(省略)"
    print(f"\033[36m[{tool_name} 結果] {display}\033[0m", flush=True)
