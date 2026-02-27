"""Claude-Like CLI Tool エントリーポイント。

REPL ループを提供し、ユーザー入力を受け取ってエージェントに渡す。
"""

import sys

from config import settings
from llm import get_client
from tools import build_registry
from agent import Agent
from utils.logger import get_logger

logger = get_logger(__name__)

_BANNER = """
╔══════════════════════════════════════════════════════╗
║          Claude-Like CLI Tool  v1.0                  ║
║  Python AI エージェント / OpenRouter・Azure 対応     ║
╠══════════════════════════════════════════════════════╣
║  /help  ヘルプ表示   /clear  履歴クリア              ║
║  /tools ツール一覧   /exit   終了                    ║
╚══════════════════════════════════════════════════════╝
"""


def print_banner() -> None:
    """バナーを表示する。"""
    print(_BANNER)
    print(f"  プロバイダー: {settings.provider.upper()}")
    if settings.provider == "openrouter":
        print(f"  モデル      : {settings.openrouter_model}")
    else:
        print(f"  デプロイ    : {settings.azure_deployment}")
    print(f"  ストリーム  : {'有効' if settings.stream else '無効'}")
    print(f"  最大ループ  : {settings.max_agent_loops} 回")
    print()


def handle_command(command: str, agent: Agent) -> bool:
    """スラッシュコマンドを処理する。

    Args:
        command: 入力されたコマンド文字列（先頭 '/' 含む）
        agent: 現在のエージェントインスタンス

    Returns:
        True: REPL ループを継続
        False: REPL ループを終了
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

    print(f"不明なコマンド: {command}  (/help でヘルプを確認)")
    return True


def main() -> None:
    """メイン関数。設定を読み込み、エージェントを初期化して REPL を開始する。"""
    # 起動シーケンス
    logger.info("起動開始: provider=%s", settings.provider)

    try:
        llm = get_client()
    except ValueError as e:
        print(f"エラー: LLM クライアントの初期化に失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    registry = build_registry()
    agent = Agent(llm, registry)

    print_banner()
    logger.info("エージェント初期化完了")

    # REPL ループ
    while True:
        try:
            user_input = input("\033[32m> \033[0m").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n終了します。")
            break

        if not user_input:
            continue

        # スラッシュコマンド処理
        if user_input.startswith("/"):
            should_continue = handle_command(user_input, agent)
            if not should_continue:
                break
            continue

        # エージェントに入力を渡す
        logger.debug("ユーザー入力: %s", user_input[:100])
        try:
            if not settings.stream:
                # 非ストリーミング: run() 内で応答を取得してから表示
                response = agent.run(user_input)
                # ループ上限警告は赤色で表示
                if response.startswith("⚠"):
                    print(f"\n\033[31m{response}\033[0m")
                else:
                    print(f"\n{response}")
            else:
                # ストリーミング: agent.run() 内でリアルタイム表示
                print()  # 出力前に空行
                agent.run(user_input)
        except RuntimeError as e:
            print(f"\n\033[31mエラー: {e}\033[0m", file=sys.stderr)
            logger.error("エージェント実行エラー: %s", e)
        except KeyboardInterrupt:
            print("\n(中断しました)")


if __name__ == "__main__":
    main()
