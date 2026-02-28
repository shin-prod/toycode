"""Claude-Like CLI Tool メインモジュール。

起動順序:
  1. coreprompt.md（プロジェクトルート）を読み込む
  2. LLM クライアント・ツールレジストリ・エージェントを初期化
  3. REPL ループ開始
"""

import os
import sys

from config import settings
from llm import get_client
from tools import build_registry
from agent import Agent
from agent.stream import print_ai_header
from utils.logger import get_logger
from utils.status_bar import status_bar

logger = get_logger(__name__)

# ANSI カラー定数
_B = "\033[1m"
_C_DIM = "\033[2m"
_C_GREEN = "\033[32m"
_C_ERR = "\033[31m"
_C_RESET = "\033[0m"

# coreprompt.md はプロジェクトルート（.myagent の親ディレクトリ）に配置
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_COREPROMPT_PATH = os.path.join(_PROJECT_ROOT, "coreprompt.md")


def _load_coreprompt() -> str | None:
    """coreprompt.md を読み込んでシステムプロンプトとして返す。

    ファイルが存在しない場合は None を返す（Agent はデフォルトを使用）。

    Returns:
        coreprompt.md の内容、またはファイルがない場合は None
    """
    if not os.path.isfile(_COREPROMPT_PATH):
        logger.warning("coreprompt.md が見つかりません: %s", _COREPROMPT_PATH)
        return None
    with open(_COREPROMPT_PATH, encoding="utf-8") as f:
        content = f.read().strip()
    logger.info("coreprompt.md を読み込みました (%d 文字)", len(content))
    return content


def print_banner() -> None:
    """バナーを表示する（llama.cpp スタイル）。"""
    model = (
        settings.openrouter_model
        if settings.provider == "openrouter"
        else settings.azure_deployment
    )
    stream_label = "true" if settings.stream else "false"

    dim = _C_DIM
    reset = _C_RESET

    print(f"\n{_B}Claude-Like CLI Tool{reset}  {dim}v1.1{reset}")
    print(f"{dim}{'─' * 40}{reset}")
    print(f"{dim}provider   :{reset}  {settings.provider.upper()}")
    print(f"{dim}model      :{reset}  {model}")
    print(f"{dim}stream     :{reset}  {stream_label}")
    print(f"{dim}max loops  :{reset}  {settings.max_agent_loops}")
    print()
    print(f"{dim}available commands:{reset}")
    print(f"  {dim}/help   {reset}  ヘルプを表示")
    print(f"  {dim}/clear  {reset}  会話履歴をクリア")
    print(f"  {dim}/tools  {reset}  登録済みツール一覧")
    print(f"  {dim}/reload {reset}  コアプロンプトをリロード")
    print(f"  {dim}/exit   {reset}  終了")
    print()


def handle_command(command: str, agent: "Agent") -> bool:
    """スラッシュコマンドを処理する。

    Args:
        command: 入力されたコマンド文字列（先頭 '/' 含む）
        agent: 現在のエージェントインスタンス

    Returns:
        True: REPL ループを継続 / False: REPL ループを終了
    """
    cmd = command.strip().lower()

    if cmd in ("/exit", "/quit", "/bye"):
        print("終了します。")
        return False

    if cmd == "/help":
        print(
            "\n利用可能なコマンド:\n"
            "  /help   このヘルプを表示\n"
            "  /clear  会話履歴をクリア\n"
            "  /tools  登録済みツール一覧を表示\n"
            "  /exit   ツールを終了\n"
        )
        return True

    if cmd == "/clear":
        agent.history.clear()
        print("会話履歴をクリアしました。")
        return True

    if cmd == "/tools":
        tools = agent.registry.list_tools()
        print(f"\n登録済みツール ({len(tools)} 件):")
        for name in tools:
            print(f"  - {name}")
        print()
        return True

    if cmd == "/reload":
        # coreprompt.md をリロードしてシステムプロンプトを更新
        new_prompt = _load_coreprompt()
        if new_prompt:
            agent.history.set_system(new_prompt)
            print("coreprompt.md をリロードしました。")
        else:
            print("coreprompt.md が見つかりませんでした。")
        return True

    print(f"不明なコマンド: {command}  (/help でヘルプを確認)")
    return True


def main() -> None:
    """メイン関数。設定を読み込み、エージェントを初期化して REPL を開始する。"""
    logger.info("起動開始: provider=%s ai_dir=%s", settings.provider, settings.ai_dir)

    try:
        llm = get_client()
    except ValueError as e:
        print(f"エラー: LLM クライアントの初期化に失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    registry = build_registry()
    system_prompt = _load_coreprompt()
    agent = Agent(llm, registry, system_prompt=system_prompt)

    print_banner()
    logger.info("エージェント初期化完了")
    status_bar.start()

    # REPL ループ
    while True:
        print()
        status_bar.set("待機中")
        try:
            user_input = input(f"{_C_GREEN}>{_C_RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            status_bar.stop()
            print("\n終了します。")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            if not handle_command(user_input, agent):
                status_bar.stop()
                break
            continue

        logger.debug("ユーザー入力: %s", user_input[:100])
        try:
            response = agent.run(user_input)
            if not settings.stream:
                # 非ストリーミング: run() はテキストのみ返すので表示する
                print_ai_header()
                if response.startswith("⚠"):
                    print(f"{_C_ERR}{response}{_C_RESET}")
                else:
                    print(response)
            elif response.startswith("⚠"):
                # ストリーミング: print_stream が最終回答を表示済み
                # ⚠ 警告（ループ上限）だけ別途表示する
                print(f"{_C_ERR}{response}{_C_RESET}")
        except RuntimeError as e:
            print(f"\n\033[31mエラー: {e}\033[0m", file=sys.stderr)
            logger.error("エージェント実行エラー: %s", e)
        except KeyboardInterrupt:
            print("\n(中断しました)")


if __name__ == "__main__":
    main()
