"""ファイル操作ツール。

read_file / write_file / edit_file / list_directory / search_files を提供する。

書き込み系操作（write_file / edit_file）は AI_DIR（.myagent/）以下に制限される。
読み取り系操作（read_file / list_directory / search_files）は制限なし。
"""

import os
import re

from utils.logger import get_logger

logger = get_logger(__name__)


def _resolve_path(path: str) -> str:
    """パスを解決する（絶対パスはそのまま、相対パスは CWD 基準）。

    Args:
        path: 入力パス

    Returns:
        解決済みの絶対パス
    """
    return os.path.abspath(path)


def _check_write_allowed(resolved: str) -> str | None:
    """書き込みパスが AI_DIR 以下かどうかを確認する。

    ログファイルはルートへの書き込みを許可する。

    Args:
        resolved: 書き込み先の絶対パス

    Returns:
        許可される場合は None、拒否される場合はエラーメッセージ文字列
    """
    from config import settings

    ai_dir = settings.ai_dir
    log_file = os.path.abspath(settings.log_file)

    # ログファイルは許可
    if resolved == log_file:
        return None

    # AI_DIR 以下であれば許可
    common = os.path.commonpath([resolved, ai_dir])
    if common == ai_dir:
        return None

    return (
        f"エラー: AI_DIR 外への書き込みは禁止されています。\n"
        f"  対象パス : {resolved}\n"
        f"  許可範囲 : {ai_dir}\n"
        "  AI_DIR 外のファイルを変更したい場合はユーザーに確認してください。"
    )


def read_file(path: str) -> str:
    """ファイルの内容を読み込む。

    Args:
        path: 読み込むファイルのパス

    Returns:
        ファイルの内容。ファイルが存在しない場合はエラーメッセージ。
    """
    resolved = _resolve_path(path)
    logger.debug("read_file: %s", resolved)
    if not os.path.exists(resolved):
        return f"エラー: ファイルが存在しません: {resolved}"
    if not os.path.isfile(resolved):
        return f"エラー: パスはファイルではありません: {resolved}"
    try:
        with open(resolved, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as e:
        logger.error("read_file エラー: %s", e)
        return f"エラー: ファイル読み込み失敗: {e}"


def write_file(path: str, content: str) -> str:
    """ファイルに内容を書き込む（新規作成・上書き）。

    AI_DIR 外への書き込みは拒否される。

    Args:
        path: 書き込み先ファイルのパス
        content: 書き込む内容

    Returns:
        成功メッセージまたはエラーメッセージ
    """
    resolved = _resolve_path(path)
    if err := _check_write_allowed(resolved):
        logger.warning("write_file: 書き込み拒否 %s", resolved)
        return err
    logger.debug("write_file: %s", resolved)
    try:
        os.makedirs(os.path.dirname(resolved) or ".", exist_ok=True)
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(content)
        return f"ファイルに書き込みました: {resolved}"
    except OSError as e:
        logger.error("write_file エラー: %s", e)
        return f"エラー: ファイル書き込み失敗: {e}"


def edit_file(path: str, old_string: str, new_string: str) -> str:
    """既存ファイルの old_string を new_string に置換して編集する。

    AI_DIR 外への書き込みは拒否される。

    Args:
        path: 編集するファイルのパス
        old_string: 置換前の文字列
        new_string: 置換後の文字列

    Returns:
        成功メッセージまたはエラーメッセージ
    """
    resolved = _resolve_path(path)
    if err := _check_write_allowed(resolved):
        logger.warning("edit_file: 書き込み拒否 %s", resolved)
        return err
    logger.debug("edit_file: %s", resolved)
    if not os.path.isfile(resolved):
        return f"エラー: ファイルが存在しません: {resolved}"
    try:
        with open(resolved, encoding="utf-8", errors="replace") as f:
            content = f.read()
        if old_string not in content:
            return f"エラー: 指定の文字列がファイル内に見つかりません: {repr(old_string)}"
        new_content = content.replace(old_string, new_string, 1)
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(new_content)
        return f"ファイルを編集しました: {resolved}"
    except OSError as e:
        logger.error("edit_file エラー: %s", e)
        return f"エラー: ファイル編集失敗: {e}"


def list_directory(path: str) -> str:
    """ディレクトリの一覧を取得する。

    Args:
        path: 一覧を取得するディレクトリのパス

    Returns:
        ファイル・ディレクトリ一覧の文字列
    """
    resolved = _resolve_path(path)
    logger.debug("list_directory: %s", resolved)
    if not os.path.exists(resolved):
        return f"エラー: パスが存在しません: {resolved}"
    if not os.path.isdir(resolved):
        return f"エラー: パスはディレクトリではありません: {resolved}"
    try:
        entries = sorted(os.listdir(resolved))
        lines = []
        for entry in entries:
            full = os.path.join(resolved, entry)
            suffix = "/" if os.path.isdir(full) else ""
            lines.append(f"{entry}{suffix}")
        return "\n".join(lines) if lines else "(空のディレクトリ)"
    except OSError as e:
        logger.error("list_directory エラー: %s", e)
        return f"エラー: ディレクトリ読み込み失敗: {e}"


def search_files(pattern: str, path: str) -> str:
    """ファイル内容をパターン検索する（grep 相当）。

    Args:
        pattern: 検索する正規表現パターン
        path: 検索対象のディレクトリまたはファイルパス

    Returns:
        マッチした行の一覧（ファイル名:行番号:内容 形式）
    """
    resolved = _resolve_path(path)
    logger.debug("search_files: pattern=%s path=%s", pattern, resolved)
    try:
        compiled = re.compile(pattern)
    except re.error as e:
        return f"エラー: 無効な正規表現: {e}"

    results: list[str] = []

    def _search_file(filepath: str) -> None:
        try:
            with open(filepath, encoding="utf-8", errors="replace") as f:
                for lineno, line in enumerate(f, 1):
                    if compiled.search(line):
                        display = line.rstrip()
                        results.append(f"{filepath}:{lineno}:{display}")
        except OSError:
            pass

    if os.path.isfile(resolved):
        _search_file(resolved)
    elif os.path.isdir(resolved):
        for root, _dirs, files in os.walk(resolved):
            for fname in files:
                _search_file(os.path.join(root, fname))
    else:
        return f"エラー: パスが存在しません: {resolved}"

    if not results:
        return "マッチするものは見つかりませんでした。"
    return "\n".join(results[:200])  # 最大 200 件に制限
