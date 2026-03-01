"""Claude-Like CLI Tool ランチャー。

AI_DIR（デフォルト: .myagent）を sys.path に追加してから起動する。
このファイル自体はロジックを持たない薄いエントリーポイント。

使い方:
  python run_agent.py               # CLI モード（デフォルト）
  python run_agent.py --mode cli    # CLI モード（明示指定）
  python run_agent.py --mode chainlit [--port PORT]  # Chainlit Web UI モード
"""

import argparse
import os
import subprocess
import sys


def _get_ai_dir() -> str:
    """.env から AI_DIR を読み取り、絶対パスを返す。"""
    base = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(base, ".env")
    ai_dir_rel = ".myagent"

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

    ai_dir = os.path.join(base, ai_dir_rel)
    if not os.path.isdir(ai_dir):
        print(f"エラー: AI_DIR が存在しません: {ai_dir}", file=sys.stderr)
        sys.exit(1)
    return ai_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Claude-Like CLI Tool ランチャー")
    parser.add_argument(
        "--mode",
        choices=["cli", "chainlit"],
        default="cli",
        help="起動モード: cli（ターミナル）または chainlit（Web UI）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Chainlit モードのポート番号（デフォルト: 8000）",
    )
    args = parser.parse_args()

    ai_dir = _get_ai_dir()
    base = os.path.dirname(os.path.abspath(__file__))

    if args.mode == "chainlit":
        # Chainlit がインストールされているか確認
        try:
            import importlib
            importlib.import_module("chainlit")
        except ImportError:
            print(
                "エラー: chainlit がインストールされていません。\n"
                "  pip install chainlit  を実行してください。",
                file=sys.stderr,
            )
            sys.exit(1)

        chainlit_app = os.path.join(ai_dir, "chainlit_app.py")
        if not os.path.isfile(chainlit_app):
            print(f"エラー: chainlit_app.py が見つかりません: {chainlit_app}", file=sys.stderr)
            sys.exit(1)

        print(f"Chainlit Web UI を起動します: http://localhost:{args.port}")
        subprocess.run(
            [
                sys.executable, "-m", "chainlit", "run",
                chainlit_app,
                "--port", str(args.port),
            ],
            cwd=base,
        )

    else:
        # CLI モード（既存の動作）
        if ai_dir not in sys.path:
            sys.path.insert(0, ai_dir)
        if base not in sys.path:
            sys.path.insert(1, base)

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "main", os.path.join(ai_dir, "main.py")
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.main()
