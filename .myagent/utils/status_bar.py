"""AIステータス表示。

llama.cpp スタイル: スクロール領域を使わず、チャットの流れに沿ってインライン表示。
  - waiting → 入力プロンプトの直前に [ ○ waiting ] を1行表示
  - thinking / running → スピナーやストリーミング出力に委ねる（no-op）
"""

import sys

# ステータス定義: (アイコン, ANSIカラー)
_STATUS_STYLES: dict[str, tuple[str, str]] = {
    "waiting":  ("○", "\033[2m"),     # 暗い（控えめ）
    "thinking": ("●", "\033[36m"),    # シアン
    "running":  ("▶", "\033[32m"),    # 緑
}
_DEFAULT_STYLE = ("·", "\033[2m")
_C_RESET = "\033[0m"


class StatusBar:
    """チャット末尾にAI状態をインライン表示するクラス。

    waiting のみ1行印字し、入力プロンプトの直前に常に表示される。
    他の状態はスピナー・ストリーミング出力が担当するため no-op。
    """

    def __init__(self) -> None:
        self._enabled = sys.stdout.isatty()

    def start(self) -> None:
        """初期化（インライン方式では何もしない）。"""

    def stop(self) -> None:
        """後処理（インライン方式では何もしない）。"""

    def set(self, status: str) -> None:
        """ステータスを表示する。

        waiting のみ印字し、入力プロンプトの直前に1行表示される。
        他の状態はスピナー・ストリーミング出力に委ねる。

        Args:
            status: "waiting" / "thinking" / "running"
        """
        if not self._enabled or status != "waiting":
            return
        icon, color = _STATUS_STYLES.get(status, _DEFAULT_STYLE)
        print(f"{color}[ {icon} {status} ]{_C_RESET}")


# モジュールレベルのシングルトン
status_bar = StatusBar()
