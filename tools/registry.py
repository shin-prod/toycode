"""ツール登録・ディスパッチャ。"""

from typing import Any, Callable

from utils.logger import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """ツールのスキーマとハンドラを管理するレジストリ。"""

    def __init__(self) -> None:
        self._tools: dict[str, dict] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable[..., str],
    ) -> None:
        """ツールを登録する。

        Args:
            name: ツール名（LLM が呼び出す名前）
            description: ツールの説明
            parameters: JSON Schema 形式のパラメータ定義
            handler: 実際の処理を行う Python 関数
        """
        self._tools[name] = {
            "schema": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            },
            "handler": handler,
        }
        logger.debug("ツール登録: %s", name)

    def get_schemas(self) -> list[dict]:
        """LLM に渡すツールスキーマ一覧を返す。

        Returns:
            Function Calling スキーマのリスト
        """
        return [t["schema"] for t in self._tools.values()]

    def dispatch(self, name: str, args: dict) -> str:
        """ツール名と引数でハンドラを呼び出す。

        Args:
            name: ツール名
            args: ツール引数

        Returns:
            ツール実行結果の文字列

        Raises:
            KeyError: 未登録のツール名が指定された場合
        """
        if name not in self._tools:
            raise KeyError(f"未登録のツール: {name}")
        handler = self._tools[name]["handler"]
        logger.info("ツール実行: %s(%s)", name, args)
        return handler(**args)

    def list_tools(self) -> list[str]:
        """登録済みツール名の一覧を返す。"""
        return list(self._tools.keys())
