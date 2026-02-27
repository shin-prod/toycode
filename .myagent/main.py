"""Claude-Like CLI Tool メインモジュール。

run_agent.py（ランチャー）から呼ばれる。sys.path は呼び出し元で設定済み。

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
    """バナーを表示する。"""
    print(_BANNER)
    print(f"  プロバイダー: {settings.provider.upper()}")
    if settings.provider == "openrouter":
        print(f"  モデル      : {settings.openrouter_model}")
    else:
        print(f"  デプロイ    : {settings.azure_deployment}")
    print(f"  AI ディレクトリ: {settings.ai_dir}")
    print(f"  ストリーム  : {'有効' if settings.stream else '無効'}")
    print(f"  最大ループ  : {settings.max_agent_loops} 回")
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

    # REPL ループ
    while True:
        try:
            user_input = input("\033[32m> \033[0m").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n終了します。")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            if not handle_command(user_input, agent):
                break
            continue

        logger.debug("ユーザー入力: %s", user_input[:100])
        try:
            if not settings.stream:
                response = agent.run(user_input)
                if response.startswith("⚠"):
                    print(f"\n\033[31m{response}\033[0m")
                else:
                    print(f"\n{response}")
            else:
                print()
                agent.run(user_input)
        except RuntimeError as e:
            print(f"\n\033[31mエラー: {e}\033[0m", file=sys.stderr)
            logger.error("エージェント実行エラー: %s", e)
        except KeyboardInterrupt:
            print("\n(中断しました)")


if __name__ == "__main__":
    main()
