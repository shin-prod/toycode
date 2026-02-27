"""Python コード実行サンドボックス。

危険な組み込み関数を制限した restricted globals で exec() を実行する。
"""

import io
import traceback
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)

# サンドボックスで許可する組み込み関数・定数の許可リスト
_ALLOWED_BUILTINS = {
    "abs", "all", "any", "bin", "bool", "bytes", "callable", "chr",
    "dict", "dir", "divmod", "enumerate", "filter", "float", "format",
    "frozenset", "getattr", "hasattr", "hash", "hex", "int", "isinstance",
    "issubclass", "iter", "len", "list", "map", "max", "min", "next",
    "oct", "ord", "pow", "print", "range", "repr", "reversed", "round",
    "set", "setattr", "slice", "sorted", "str", "sum", "tuple", "type",
    "vars", "zip", "True", "False", "None",
    # 例外クラス
    "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
    "AttributeError", "RuntimeError", "StopIteration", "NotImplementedError",
    "ArithmeticError", "ZeroDivisionError", "OverflowError",
}


def _build_restricted_globals() -> dict[str, Any]:
    """制限された globals 辞書を構築する。"""
    import builtins

    safe_builtins = {
        k: getattr(builtins, k)
        for k in _ALLOWED_BUILTINS
        if hasattr(builtins, k)
    }
    return {
        "__builtins__": safe_builtins,
        # 安全な標準ライブラリモジュール
        "math": __import__("math"),
        "json": __import__("json"),
        "re": __import__("re"),
        "datetime": __import__("datetime"),
        "collections": __import__("collections"),
        "itertools": __import__("itertools"),
        "functools": __import__("functools"),
        "random": __import__("random"),
        "string": __import__("string"),
        "decimal": __import__("decimal"),
        "fractions": __import__("fractions"),
        "statistics": __import__("statistics"),
    }


def run_python(code: str) -> str:
    """Python コードをサンドボックス内で実行し結果を返す。

    ALLOW_CODE_EXEC=false の場合はエラーを返す。
    __import__ / open / os / sys などの危険な操作は制限される。

    Args:
        code: 実行する Python コード

    Returns:
        標準出力 + 標準エラー出力の文字列、またはエラーメッセージ
    """
    from config import settings

    if not settings.allow_code_exec:
        return "エラー: Python コード実行は無効化されています (ALLOW_CODE_EXEC=false)"

    logger.info("run_python: コード実行 (%d 文字)", len(code))

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    restricted_globals = _build_restricted_globals()

    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exec(code, restricted_globals)  # noqa: S102
    except Exception:
        stderr_buf.write(traceback.format_exc())

    stdout_val = stdout_buf.getvalue()
    stderr_val = stderr_buf.getvalue()

    parts: list[str] = []
    if stdout_val:
        parts.append(stdout_val.rstrip())
    if stderr_val:
        parts.append(f"[stderr]\n{stderr_val.rstrip()}")
    return "\n".join(parts) if parts else "(出力なし)"
