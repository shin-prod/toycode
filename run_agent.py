"""Claude-Like CLI Tool ランチャー。

AI_DIR（デフォルト: .myagent）を sys.path に追加してから main.py を起動する。
このファイル自体はロジックを持たない薄いエントリーポイント。
"""

import os
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
    ai_dir = _get_ai_dir()
    base = os.path.dirname(os.path.abspath(__file__))

    if ai_dir not in sys.path:
        sys.path.insert(0, ai_dir)
    if base not in sys.path:
        sys.path.insert(1, base)

    # main モジュールを AI_DIR から読み込んで実行
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "main", os.path.join(ai_dir, "main.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()
