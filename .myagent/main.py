"""Claude-Like CLI Tool メインモジュール。

起動順序:
  1. coreprompt.md（プロジェクトルート）を読み込む
  2. LLM クライアント・ツールレジストリ・エージェントを初期化
  3. WORKSPACE_DIR の AGENTS.md を収集・ロード（Codex 方式）
  4. REPL ループ開始
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

# AGENTS.md ロード設定（Codex 方式）
_AGENTS_MD_FILENAME = "AGENTS.md"
_AGENTS_MD_MAX_DEPTH = 3          # ワークスペースルートからの探索最大深度
_AGENTS_MD_SKIP_DIRS = frozenset(  # スキップするディレクトリ名
    ["venv", ".venv", "__pycache__", "node_modules", "dist", "build"]
)

# キーワードに応じて遅延ロードする追加コアプロンプト定義
# { ファイル名: (トリガーキーワード集, 通知メッセージ) }
_EXTRA_PROMPTS: dict[str, tuple[frozenset[str], str]] = {
    "coreprompt_ppt.md": (
        frozenset(["ppt", "pptx", "powerpoint", "スライド", "プレゼン"]),
        "PPT ガイドラインを読み込みました",
    ),
}


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


def _collect_agents_md(workspace_dir: str) -> list[tuple[str, str]]:
    """ワークスペースから AGENTS.md ファイルを収集する。

    Codex の AGENTS.md ロード方式に相当。
    ルートから最大 _AGENTS_MD_MAX_DEPTH 階層まで再帰探索し、
    見つかったファイルをパス順（浅い順）に返す。
    隠しディレクトリと仮想環境などはスキップする。

    Args:
        workspace_dir: 探索ルートディレクトリ

    Returns:
        [(絶対パス, 内容), ...] のリスト（ルートから深い順）
    """
    found: list[tuple[str, str]] = []
    for root, dirs, files in os.walk(workspace_dir):
        rel = os.path.relpath(root, workspace_dir)
        depth = 0 if rel == "." else len(rel.split(os.sep))
        if depth >= _AGENTS_MD_MAX_DEPTH:
            dirs.clear()
            continue
        # 隠しディレクトリ・既知の無関係ディレクトリをスキップ（安定した探索順に sort）
        dirs[:] = sorted(
            d for d in dirs
            if not d.startswith(".") and d not in _AGENTS_MD_SKIP_DIRS
        )
        if _AGENTS_MD_FILENAME not in files:
            continue
        path = os.path.join(root, _AGENTS_MD_FILENAME)
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                found.append((path, content))
                logger.info("AGENTS.md 検出: %s (%d 文字)", path, len(content))
        except OSError as e:
            logger.warning("AGENTS.md 読み込みエラー: %s: %s", path, e)
    return found


def _load_extra_coreprompt(filename: str) -> str | None:
    """追加コアプロンプトファイルをプロジェクトルートから読み込む。

    Args:
        filename: ファイル名（プロジェクトルート直下）

    Returns:
        ファイルの内容、またはファイルがない場合は None
    """
    path = os.path.join(_PROJECT_ROOT, filename)
    if not os.path.isfile(path):
        logger.warning("追加コアプロンプトが見つかりません: %s", path)
        return None
    with open(path, encoding="utf-8") as f:
        content = f.read().strip()
    logger.info("追加コアプロンプトを読み込みました: %s (%d 文字)", filename, len(content))
    return content


def _maybe_inject_extra_prompts(
    user_input: str,
    agent: "Agent",
    loaded: set[str],
    system_content: list[str],
) -> None:
    """ユーザー入力のキーワードに応じて追加コアプロンプトを遅延ロードする。

    既にロード済みのものはスキップする。
    ロードした場合はシステムプロンプトを更新してユーザーに通知する。

    Args:
        user_input: ユーザーの入力テキスト
        agent: 現在のエージェントインスタンス
        loaded: ロード済みファイル名のセット（更新される）
        system_content: システムプロンプト文字列のリスト（先頭が base）
    """
    low = user_input.lower()
    updated = False
    for filename, (keywords, notice) in _EXTRA_PROMPTS.items():
        if filename in loaded:
            continue
        if not any(kw in low for kw in keywords):
            continue
        content = _load_extra_coreprompt(filename)
        if content:
            system_content.append(content)
            agent.history.set_system("\n\n---\n\n".join(system_content))
            loaded.add(filename)
            updated = True
            print(f"{_C_DIM}[ {notice} ]{_C_RESET}")
    if updated:
        logger.debug("システムプロンプトを更新しました (sections=%d)", len(system_content))


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
    workspace_rel = os.path.relpath(settings.workspace_dir)
    print(f"{dim}provider   :{reset}  {settings.provider.upper()}")
    print(f"{dim}model      :{reset}  {model}")
    print(f"{dim}stream     :{reset}  {stream_label}")
    print(f"{dim}max loops  :{reset}  {settings.max_agent_loops}")
    print(f"{dim}workspace  :{reset}  {workspace_rel}")
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

    # システムプロンプトの各セクションを追跡（追加プロンプト結合用）
    _system_sections: list[str] = [system_prompt] if system_prompt else []
    _extra_loaded: set[str] = set()

    # AGENTS.md をワークスペースから収集・ロード（Codex 方式）
    _agents_md_entries = _collect_agents_md(settings.workspace_dir)
    for agents_path, agents_content in _agents_md_entries:
        rel_path = os.path.relpath(agents_path, settings.workspace_dir)
        _system_sections.append(f"# AGENTS.md ({rel_path})\n\n{agents_content}")
    if _agents_md_entries:
        agent.history.set_system("\n\n---\n\n".join(_system_sections))

    print_banner()
    if _agents_md_entries:
        for agents_path, _ in _agents_md_entries:
            rel_path = os.path.relpath(agents_path, settings.workspace_dir)
            print(f"{_C_DIM}[ AGENTS.md: {rel_path} ]{_C_RESET}")
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

        # キーワードに応じて追加コアプロンプトを遅延ロード
        _maybe_inject_extra_prompts(user_input, agent, _extra_loaded, _system_sections)

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
