"""Claude-Like CLI Tool エントリーポイント。

起動順序:
  1. .env を手動パースして AI_DIR を確認
  2. AI_DIR を sys.path に追加
  3. coreprompt.md を読み込む
  4. LLM クライアント・ツールレジストリ・エージェントを初期化
  5. REPL ループ開始
"""

import os
import sys


# ------------------------------------------------------------------
# ブートストラップ: .env から AI_DIR を読み取り sys.path に追加
# ------------------------------------------------------------------

def _bootstrap_ai_dir() -> str:
    """AI_DIR を .env から解決し、モジュール検索パスに追加する。

    .env が存在しない場合や AI_DIR が未定義の場合は '.myagent' を使用する。

    Returns:
        解決済みの AI ディレクトリ絶対パス
    """
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    ai_dir_rel = ".myagent"  # デフォルト値

    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                if key.strip() == "AI_DIR":
                    ai_dir_rel = val.strip().strip('"').strip("'")
                    break

    base = os.path.dirname(os.path.abspath(__file__))
    ai_dir = os.path.join(base, ai_dir_rel)

    if not os.path.isdir(ai_dir):
        print(
            f"エラー: AI_DIR が存在しません: {ai_dir}\n"
            f"  AI_DIR={ai_dir_rel} を確認してください。",
            file=sys.stderr,
        )
        sys.exit(1)

    if ai_dir not in sys.path:
        sys.path.insert(0, ai_dir)

    # プロジェクトルートも追加（.env 読み込み用）
    if base not in sys.path:
        sys.path.insert(1, base)

    return ai_dir


# AI_DIR をブートストラップしてから各モジュールを import
_AI_DIR = _bootstrap_ai_dir()

from config import settings  # noqa: E402  (sys.path 追加後に import)
from llm import get_client  # noqa: E402
from tools import build_registry  # noqa: E402
from agent import Agent  # noqa: E402
from utils.logger import get_logger  # noqa: E402

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

_COREPROMPT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "coreprompt.md"
)


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
