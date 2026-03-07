"""ファイルアクセスガード。

WORKSPACE_DIR 外へのアクセス（読み書き）を禁止する共通チェック関数を提供する。
ログファイルのみ例外としてルートへの書き込みを許可する。
"""

import os

from utils.logger import get_logger

logger = get_logger(__name__)


def resolve_path(path: str) -> str:
    """パスを解決する。

    絶対パスはそのまま返す。
    相対パスは WORKSPACE_DIR を基点として解決する（CWD ではない）。

    Args:
        path: 入力パス（絶対または相対）

    Returns:
        解決済みの絶対パス
    """
    if os.path.isabs(path):
        return os.path.normpath(path)
    from config import settings
    return os.path.abspath(os.path.join(settings.workspace_dir, path))


def _is_in_workspace(resolved: str) -> bool:
    """パスが WORKSPACE_DIR 以下かどうかを判定する。"""
    from config import settings
    workspace = settings.workspace_dir
    try:
        return os.path.commonpath([resolved, workspace]) == workspace
    except ValueError:
        return False


def check_path_allowed(resolved: str) -> str | None:
    """パスが WORKSPACE_DIR 以下かどうかを確認する（読み書き共通）。

    Args:
        resolved: チェック対象の絶対パス（os.path.abspath 済み）

    Returns:
        許可される場合は None。
        拒否される場合はユーザーに示すエラーメッセージ文字列。
    """
    from config import settings
    workspace = settings.workspace_dir

    if _is_in_workspace(resolved):
        return None

    logger.warning("アクセス拒否: %s (workspace=%s)", resolved, workspace)
    return (
        f"エラー: WORKSPACE_DIR 外へのアクセスは禁止されています。\n"
        f"  対象パス : {resolved}\n"
        f"  許可範囲 : {workspace}"
    )


def check_write_allowed(resolved: str) -> str | None:
    """書き込みパスが WORKSPACE_DIR 以下かどうかを確認する。

    ログファイルは場所を問わず許可する。

    Args:
        resolved: 書き込み先の絶対パス（os.path.abspath 済み）

    Returns:
        許可される場合は None。
        拒否される場合はユーザーに示すエラーメッセージ文字列。
    """
    from config import settings

    # ログファイルは場所を問わず許可
    log_file = os.path.abspath(settings.log_file)
    if resolved == log_file:
        return None

    return check_path_allowed(resolved)
