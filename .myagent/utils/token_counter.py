"""トークン数カウントユーティリティ。

外部ライブラリ（tiktoken 等）を使わず、文字数 / 4 で近似する。
日本語テキストは 1 文字 = 1.5 トークン程度で計算する。
"""

import json
from typing import Any


def estimate_tokens(data: Any) -> int:
    """データのトークン数を概算する。

    Args:
        data: 文字列、dict、list など任意の Python オブジェクト

    Returns:
        推定トークン数
    """
    if isinstance(data, str):
        return _count_text(data)
    if isinstance(data, (dict, list)):
        text = json.dumps(data, ensure_ascii=False)
        return _count_text(text)
    return _count_text(str(data))


def _count_text(text: str) -> int:
    """テキストのトークン数を概算する。

    ASCII 文字: 4 文字 = 1 トークン
    非 ASCII 文字（日本語等）: 1 文字 = 1.5 トークン

    Args:
        text: カウント対象テキスト

    Returns:
        推定トークン数
    """
    ascii_count = sum(1 for c in text if ord(c) < 128)
    non_ascii_count = len(text) - ascii_count
    return int(ascii_count / 4 + non_ascii_count * 1.5)
