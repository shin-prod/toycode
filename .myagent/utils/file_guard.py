"""ファイル書き込みガード。

WORKSPACE_DIR 外への書き込みを禁止する共通チェック関数を提供する。
ログファイルのみ例外としてルートへの書き込みを許可する。
"""

import os

from utils.logger import get_logger

logger = get_logger(__name__)


def check_write_allowed(resolved: str) -> str | None:
    """書き込みパスが WORKSPACE_DIR 以下かどうかを確認する。

    Args:
        resolved: 書き込み先の絶対パス（os.path.abspath 済み）

    Returns:
        許可される場合は None。
        拒否される場合はユーザーに示すエラーメッセージ文字列。
    """
    from config import settings

    workspace = settings.workspace_dir
    log_file = os.path.abspath(settings.log_file)

    # ログファイルは場所を問わず許可
    if resolved == log_file:
        return None

    # WORKSPACE_DIR 以下であれば許可
    try:
        common = os.path.commonpath([resolved, workspace])
    except ValueError:
        # Windows でドライブが異なる場合など
        common = ""

    if common == workspace:
        return None

    logger.warning("書き込み拒否: %s (workspace=%s)", resolved, workspace)
    return (
        f"エラー: WORKSPACE_DIR 外への書き込みは禁止されています。\n"
        f"  対象パス     : {resolved}\n"
        f"  許可範囲     : {workspace}\n"
        f"  WORKSPACE_DIR を .env で変更するか、ユーザーに確認してください。"
    )
