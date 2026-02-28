"""ロギングユーティリティ。"""

import logging
import os
from typing import Optional


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """名前付きロガーを返す。初回呼び出し時にハンドラを設定する。

    Args:
        name: ロガー名（通常は __name__）
        level: ログレベル文字列。省略時は設定ファイルの値を使用。

    Returns:
        設定済みの Logger インスタンス
    """
    logger = logging.getLogger(name)

    # 既にハンドラが設定済みならスキップ
    if logger.handlers:
        return logger

    try:
        from config import settings as _settings
        log_level_str = level or _settings.log_level
        log_file = _settings.log_file
    except Exception:
        log_level_str = level or os.getenv("LOG_LEVEL", "INFO")
        log_file = os.getenv("LOG_FILE", "agent.log")

    log_level = getattr(logging, log_level_str, logging.INFO)
    logger.setLevel(log_level)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # コンソールハンドラ: WARNING 以上のみ表示（INFO/DEBUG はチャットに混入させない）
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # ファイルハンドラ: 設定レベルをすべて記録
    try:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(log_level)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError as e:
        logger.warning("ログファイルを開けません (%s): %s", log_file, e)

    return logger
