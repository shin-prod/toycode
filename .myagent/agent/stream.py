"""ストリーミング出力ユーティリティ。"""

from typing import Generator, Optional

from utils.logger import get_logger
from utils.spinner import Spinner
from utils.status_bar import status_bar

logger = get_logger(__name__)

# ANSI カラー定数
_C_AI = "\033[36m"         # AI ヘッダー（シアン）
_C_THINK = "\033[2;3m"     # 中間思考テキスト（暗い・イタリック）
_C_TOOL = "\033[2m"        # ツール名（暗い）
_C_RESULT = "\033[2m"      # ツール結果（暗い）
_C_OK = "\033[32m"         # 成功（緑）
_C_ERR = "\033[31m"        # エラー（赤）
_C_RESET = "\033[0m"


def print_ai_header() -> None:
    """AI 応答ヘッダーを表示する。"""
    print(f"\n{_C_AI}>{_C_RESET}")


def print_stream(
    text_generator: Generator[tuple, None, None],
    spinner: Optional[Spinner] = None,
) -> tuple[str, str, dict]:
    """ストリーミングジェネレータからテキストを受け取り処理する。

    テキストはバッファリングし、finish_reason が判明してから表示を決定する。
    - tool_calls（中間ステップ）: テキストを表示しない（コード全文が出ない）
    - stop（最終回答）: AI ヘッダーとテキストをまとめて表示する

    Args:
        text_generator: ('text', str) / ('done', finish_reason, tool_calls_data)
                        を yield するジェネレータ
        spinner: 停止対象のスピナー（省略可）

    Returns:
        (accumulated_text, finish_reason, tool_calls_data) のタプル
    """
    accumulated: list[str] = []
    finish_reason = "stop"
    tool_calls_data: dict = {}

    for event in text_generator:
        if event[0] == "text":
            accumulated.append(event[1])
        elif event[0] == "done":
            finish_reason = event[1] if len(event) > 1 else "stop"
            tool_calls_data = event[2] if len(event) > 2 else {}

    # スピナーを停止
    if spinner:
        spinner.stop()

    if finish_reason == "tool_calls":
        # ツール呼び出し前の中間思考テキストを別色（暗い・イタリック）で表示
        text = "".join(accumulated).strip()
        if text:
            print(f"\n{_C_THINK}▸ {text}{_C_RESET}")
    else:
        # 最終回答
        print_ai_header()
        if accumulated:
            print("".join(accumulated))
        else:
            # モデルがテキストなしで完了した場合（ツール実行のみで応答なし）
            print(f"{_C_RESULT}done{_C_RESET}")

    return "".join(accumulated), finish_reason, tool_calls_data


_BRIEF_MAX_LEN = 72  # サマリー・引数表示の最大文字数


def _summarize_tool(name: str, args: dict) -> str:
    """ツール呼び出しの1行要約を返す。"""
    path = args.get("path", "")
    if name == "write_file":
        content = args.get("content", "")
        lines = content.count("\n") + 1 if content else 0
        return f"{path}  ({lines}行, {len(content)}文字)" if content else path
    if name == "edit_file":
        old = args.get("old_string", "")
        return f"{path}  ({len(old)}文字 → 置換)"
    if name in ("read_file", "list_directory", "search_files"):
        return path or args.get("pattern", "")
    if name == "run_shell":
        cmd = args.get("command", "")
        return cmd[:_BRIEF_MAX_LEN] + ("…" if len(cmd) > _BRIEF_MAX_LEN else "")
    if name == "run_python":
        code = args.get("code", "")
        lines = code.count("\n") + 1
        return f"Python  ({lines}行)"
    # Office ツール
    if name.startswith(("pptx_", "docx_", "xlsx_")):
        suffix = name.split("_", 1)[1] if "_" in name else name
        return f"{path}  [{suffix}]"
    return str(args)[:_BRIEF_MAX_LEN]


def print_summary(tool_log: list[tuple[str, dict]]) -> None:
    """タスク完了後の作業サマリーを表示する。

    Args:
        tool_log: [(tool_name, args_dict), ...] のリスト
    """
    if not tool_log:
        return
    sep = f"{_C_TOOL}{'─' * 42}{_C_RESET}"
    print(f"\n{sep}")
    for name, args in tool_log:
        brief = _summarize_tool(name, args)
        print(f"  {_C_TOOL}{name:<16}{_C_RESET}  {_C_RESULT}{brief}{_C_RESET}")
    print(sep)


def print_thinking_header(loop_count: int) -> None:
    """エージェントループの思考ヘッダーを表示する（2回目以降）。

    Args:
        loop_count: 現在のループ回数（1始まり）
    """
    print(f"\n{_C_TOOL}[ thinking {loop_count} ]{_C_RESET}")


def print_thinking_text(content: str) -> None:
    """非ストリーミング時にツール呼び出し前の中間テキストを表示する。

    Args:
        content: ツール呼び出しを決める前にAIが出力したテキスト
    """
    text = content.strip()
    if text:
        print(f"\n{_C_THINK}▸ {text}{_C_RESET}")


def _fmt_arg(val: object) -> str:
    """引数値を表示用にフォーマットする。

    長い文字列（80文字超）は全文を出さず行数・文字数のサマリーを返す。
    """
    if isinstance(val, str) and len(val) > 80:
        lines = val.count("\n") + 1
        return f"<{lines}行, {len(val)}文字>"
    return repr(val)[:60]


def print_tool_call(tool_name: str, args: dict) -> None:
    """ツール呼び出しをターミナルに表示する。

    Args:
        tool_name: ツール名
        args: ツール引数
    """
    args_str = ", ".join(f"{k}={_fmt_arg(v)}" for k, v in args.items())
    print(
        f"\n{_C_TOOL}[{tool_name}]  {args_str}{_C_RESET}",
        flush=True,
    )


def print_tool_result(tool_name: str, result: str, truncate: int = 200) -> None:
    """ツール実行結果をターミナルに表示する。

    Args:
        tool_name: ツール名
        result: ツール実行結果
        truncate: 表示する最大文字数
    """
    display = result if len(result) <= truncate else result[:truncate] + "…"
    is_error = result.startswith(("エラー", "error:", "Error"))
    color = _C_ERR if is_error else _C_OK
    icon = "✗" if is_error else "✓"
    print(f"  {color}{icon}{_C_RESET}  {_C_RESULT}{display}{_C_RESET}", flush=True)
