"""シェルコマンド実行ツール。"""

import os
import subprocess

from utils.logger import get_logger

logger = get_logger(__name__)

# タイムアウト（秒）
_TIMEOUT = 30

_WARN = "\033[33m"
_RESET = "\033[0m"


def _request_shell_approval(command: str) -> bool:
    """シェルコマンドの実行承認をユーザーに求める。

    Args:
        command: 実行予定のシェルコマンド

    Returns:
        承認された場合 True、キャンセルされた場合 False
    """
    try:
        print(f"{_WARN}⚠ [シェル実行] $ {command}{_RESET}")
        answer = input("実行しますか？ [y/N]: ").strip().lower()
        return answer in ("y", "yes")
    except KeyboardInterrupt:
        print()
        return False


def run_shell(command: str) -> str:
    """シェルコマンドを実行し stdout/stderr を返す。

    ALLOW_SHELL_EXEC=false の場合はエラーを返す。
    approval_policy に従って実行前に承認を求める場合がある。
    実行は WORKSPACE_DIR をカレントディレクトリとして行う。

    Args:
        command: 実行するシェルコマンド

    Returns:
        実行結果（stdout + stderr）の文字列
    """
    from config import settings

    if not settings.allow_shell_exec:
        return "エラー: シェルコマンド実行は無効化されています (ALLOW_SHELL_EXEC=false)"

    policy = settings.approval_policy
    if policy == "never":
        return "[拒否] コマンド実行は承認ポリシーにより禁止されています"
    if policy == "ask":
        if not _request_shell_approval(command):
            return "[キャンセル] コマンド実行をキャンセルしました"
    # policy == "auto" はそのまま実行

    workspace = settings.workspace_dir
    logger.info("run_shell: %s (cwd=%s)", command, workspace)

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            cwd=workspace,
        )
        output_parts: list[str] = []
        if result.stdout:
            output_parts.append(f"[stdout]\n{result.stdout.rstrip()}")
        if result.stderr:
            output_parts.append(f"[stderr]\n{result.stderr.rstrip()}")
        if result.returncode != 0:
            output_parts.append(f"[exit code] {result.returncode}")
        return "\n".join(output_parts) if output_parts else "(出力なし)"
    except subprocess.TimeoutExpired:
        return f"エラー: コマンドがタイムアウトしました ({_TIMEOUT}秒)"
    except Exception as e:
        logger.error("run_shell エラー: %s", e)
        return f"エラー: シェル実行失敗: {e}"
