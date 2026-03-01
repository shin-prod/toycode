"""Chainlit モード エントリーポイント。

run_agent.py --mode chainlit から起動される。
コアエージェントロジックは CLI モードと同一のものを使用する。
"""

import asyncio
import os
import sys

# .myagent/ を sys.path に追加（このファイルは .myagent/ 内にある）
_AI_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_AI_DIR)
for _p in (_AI_DIR, _PROJECT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import chainlit as cl

from agent import Agent
from config import settings
from llm import get_client
from tools import build_registry
from utils.logger import get_logger

logger = get_logger(__name__)

# Chainlit モードでは端末ストリーミングを無効化（ブラウザ UI が出力を担う）
settings.stream = False

# ── コアプロンプト関連（main.py と同一ロジック） ──────────────────────────────
_COREPROMPT_PATH = os.path.join(_PROJECT_ROOT, "coreprompt.md")
_EXTRA_PROMPTS: dict[str, tuple[frozenset[str], str]] = {
    "coreprompt_ppt.md": (
        frozenset(["ppt", "pptx", "powerpoint", "スライド", "プレゼン"]),
        "PPT ガイドラインを読み込みました",
    ),
}


def _load_coreprompt() -> str | None:
    if not os.path.isfile(_COREPROMPT_PATH):
        return None
    with open(_COREPROMPT_PATH, encoding="utf-8") as f:
        return f.read().strip()


def _load_extra_coreprompt(filename: str) -> str | None:
    path = os.path.join(_PROJECT_ROOT, filename)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def _brief_args(args: dict) -> str:
    """ツール引数を 60 文字以内に短縮して返す。"""
    parts = []
    for k, v in args.items():
        sv = str(v)
        if len(sv) > 60:
            sv = sv[:60] + "…"
        parts.append(f"{k}={sv!r}")
    return ", ".join(parts)


# ── Chainlit ハンドラ ─────────────────────────────────────────────────────────

@cl.on_chat_start
async def on_chat_start() -> None:
    """セッション開始時にエージェントを初期化する。"""
    try:
        llm = get_client()
    except ValueError as e:
        await cl.Message(content=f"❌ LLM 初期化エラー: {e}").send()
        return

    registry = build_registry()
    system_prompt = _load_coreprompt()
    agent = Agent(llm, registry, system_prompt=system_prompt)

    cl.user_session.set("agent", agent)
    cl.user_session.set("system_sections", [system_prompt] if system_prompt else [])
    cl.user_session.set("extra_loaded", set())

    model = (
        settings.openrouter_model
        if settings.provider == "openrouter"
        else settings.azure_deployment
    )
    await cl.Message(
        content=(
            f"**Claude-Like AI Tool**\n\n"
            f"- provider: `{settings.provider.upper()}`\n"
            f"- model: `{model}`\n\n"
            "準備完了です。何でも話しかけてください。"
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """ユーザーメッセージを受け取りエージェントを実行する。"""
    agent: Agent | None = cl.user_session.get("agent")
    if agent is None:
        await cl.Message(
            content="❌ セッションが初期化されていません。ページをリロードしてください。"
        ).send()
        return

    system_sections: list[str] = cl.user_session.get("system_sections")
    extra_loaded: set[str] = cl.user_session.get("extra_loaded")

    # キーワードに応じて追加コアプロンプトを遅延ロード
    low = message.content.lower()
    for filename, (keywords, notice) in _EXTRA_PROMPTS.items():
        if filename not in extra_loaded and any(kw in low for kw in keywords):
            content = _load_extra_coreprompt(filename)
            if content:
                system_sections.append(content)
                agent.history.set_system("\n\n---\n\n".join(system_sections))
                extra_loaded.add(filename)
                await cl.Message(content=f"*{notice}*").send()

    # ── ツール表示コールバック（スレッド → asyncio ブリッジ） ────────────────
    loop = asyncio.get_event_loop()
    current_step: list[cl.Step | None] = [None]

    def on_tool_start(name: str, args: dict) -> None:
        """ツール開始時に Chainlit Step を作成する（同期スレッドから呼び出し）。"""
        async def _create() -> None:
            step = cl.Step(name=name, type="tool")
            step.input = _brief_args(args)
            await step.send()
            current_step[0] = step

        asyncio.run_coroutine_threadsafe(_create(), loop).result(timeout=30)

    def on_tool_end(name: str, result: str) -> None:
        """ツール完了時に Step の出力を更新する。"""
        step = current_step[0]
        if step is None:
            return

        async def _update() -> None:
            step.output = result[:500] + ("…" if len(result) > 500 else "")
            await step.update()

        asyncio.run_coroutine_threadsafe(_update(), loop).result(timeout=30)
        current_step[0] = None

    agent.on_tool_start = on_tool_start
    agent.on_tool_end = on_tool_end

    # async with cl.Step を使うと、ブロック実行中はスピナーが表示される。
    # ツール呼び出し Step はここにネストされて表示される。
    response = f"❌ エラーが発生しました（不明）"
    async with cl.Step(name="考え中...", type="run", show_input=False) as thinking:
        try:
            response = await asyncio.to_thread(agent.run, message.content)
        except Exception as e:
            logger.error("エージェント実行エラー: %s", e, exc_info=True)
            response = f"❌ エラーが発生しました: {e}"
            thinking.is_error = True
        finally:
            agent.on_tool_start = None
            agent.on_tool_end = None

    # ツール実行ステップが折り畳まれた後、最終回答を平文メッセージで送信
    await cl.Message(content=response).send()
