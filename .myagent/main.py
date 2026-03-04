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
from utils.spinner import Spinner
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


def _read_input() -> str:
    """複数行入力をサポートする入力関数。

    行末が '\\' の場合は継続行として扱い、次の行を読み続ける。

    Returns:
        ユーザーの入力テキスト（結合・strip 済み）

    Raises:
        EOFError: EOF で入力が終了した場合
        KeyboardInterrupt: Ctrl+C が押された場合
    """
    lines: list[str] = []
    while True:
        prompt_str = f"{_C_GREEN}>{_C_RESET} " if not lines else f"{_C_DIM}...{_C_RESET} "
        line = input(prompt_str)
        if line.endswith("\\"):
            lines.append(line[:-1])
        else:
            lines.append(line)
            break
    return "\n".join(lines).strip()


def _print_token_usage(history) -> None:
    """トークン使用状況をディム表示する。

    Args:
        history: ContextManager インスタンス
    """
    used = history.estimate_tokens()
    max_t = history.max_tokens
    pct = used / max_t * 100
    print(f"{_C_DIM}[トークン: {used:,} / {max_t:,} ({pct:.1f}%)]{_C_RESET}")


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
    print(f"{dim}approval   :{reset}  {settings.approval_policy}")
    print()
    print(f"{dim}available commands:{reset}")
    print(f"  {dim}/help    {reset}  ヘルプを表示")
    print(f"  {dim}/clear   {reset}  会話履歴をクリア")
    print(f"  {dim}/tools   {reset}  登録済みツール一覧")
    print(f"  {dim}/compact {reset}  会話履歴を要約・圧縮")
    print(f"  {dim}/reload  {reset}  コアプロンプトをリロード")
    print(f"  {dim}/exit    {reset}  終了")
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
            "  /help     このヘルプを表示\n"
            "  /clear    会話履歴をクリア\n"
            "  /tools    登録済みツール一覧を表示\n"
            "  /compact  会話履歴を要約・圧縮\n"
            "  /reload   コアプロンプトをリロード\n"
            "  /exit     ツールを終了\n"
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

    if cmd == "/compact":
        count = agent.history.compactable_item_count()
        if count == 0:
            print("圧縮対象の履歴がありません（直近 4 ターン以下）。")
            return True

        # 要約対象アイテムを収集
        all_msgs = agent.history.for_prompt()
        non_system = [m for m in all_msgs if m.get("role") != "system"]
        to_summarize = non_system[:count]

        # 会話テキストを構築
        parts: list[str] = []
        for m in to_summarize:
            role = m.get("role", "")
            content = m.get("content") or ""
            if role == "user" and content:
                parts.append(f"ユーザー: {content[:500]}")
            elif role == "assistant":
                if content:
                    parts.append(f"AI: {content[:500]}")
                elif m.get("tool_calls"):
                    names = [
                        tc.get("function", {}).get("name", "?")
                        for tc in m["tool_calls"]
                    ]
                    parts.append(f"AI: ツール呼び出し: {', '.join(names)}")
            elif role == "tool" and content:
                parts.append(f"ツール結果: {content[:200]}")

        history_text = "\n".join(parts)
        summary_prompt = (
            "以下の会話履歴を簡潔に要約してください。"
            "ユーザーの要求・AIのアクション・重要な決定事項を含めてください。\n\n"
            f"{history_text}"
        )

        print(f"{_C_DIM}[ 要約を生成中... ({count} アイテム) ]{_C_RESET}")
        try:
            with Spinner("要約中"):
                llm_resp = agent.llm.chat(
                    [{"role": "user", "content": summary_prompt}]
                )
            summary = llm_resp.content or ""
            if not summary:
                print("要約の生成に失敗しました。")
                return True
            compacted = agent.history.compact(summary)
            if compacted:
                used = agent.history.estimate_tokens()
                print(
                    f"{_C_DIM}[ 履歴を圧縮しました"
                    f" (残り: {used:,} トークン) ]{_C_RESET}"
                )
            else:
                print("圧縮できませんでした。")
        except Exception as e:
            print(f"エラー: 要約生成失敗: {e}")
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
            user_input = _read_input()
        except EOFError:
            status_bar.stop()
            print("\n終了します。")
            break
        except KeyboardInterrupt:
            print()
            continue

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
            _print_token_usage(agent.history)
        except RuntimeError as e:
            print(f"\n\033[31mエラー: {e}\033[0m", file=sys.stderr)
            logger.error("エージェント実行エラー: %s", e)
        except KeyboardInterrupt:
            agent.cancel_current_turn()
            print("\n(中断しました)")


if __name__ == "__main__":
    main()
