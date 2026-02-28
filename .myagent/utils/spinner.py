"""ターミナル用スピナー。LLM 呼び出し中に回転アニメーションを表示する。"""

import sys
import threading
import time
from itertools import cycle

_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
_INTERVAL = 0.08


class Spinner:
    """スレッドベースのスピナー。コンテキストマネージャとしても使用可能。

    Example:
        with Spinner("思考中"):
            result = llm.chat(...)
    """

    def __init__(self, message: str = "思考中") -> None:
        self._message = message
        self._running = False
        self._thread: threading.Thread | None = None
        self._clear_width = len(message) + 16

    def start(self) -> "Spinner":
        """スピナーを開始する。"""
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        """スピナーを停止し、行をクリアする。"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
        sys.stdout.write(f"\r{' ' * self._clear_width}\r")
        sys.stdout.flush()

    def _run(self) -> None:
        for frame in cycle(_FRAMES):
            if not self._running:
                break
            sys.stdout.write(
                f"\r\033[33m{frame}\033[0m  \033[2m{self._message}...\033[0m"
            )
            sys.stdout.flush()
            time.sleep(_INTERVAL)

    def __enter__(self) -> "Spinner":
        return self.start()

    def __exit__(self, *_: object) -> None:
        self.stop()
