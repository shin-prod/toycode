"""設定管理モジュール。

.env ファイルを標準ライブラリのみでパースし、全設定値を保持する。
"""

import os


class Settings:
    """アプリケーション設定。.env を手動パースして os.environ に反映する。"""

    def __init__(self) -> None:
        self._load_dotenv(".env")

        # LLM プロバイダー
        self.provider: str = os.getenv("LLM_PROVIDER", "openrouter")

        # OpenRouter 設定
        self.openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
        self.openrouter_model: str = os.getenv(
            "OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet"
        )
        self.openrouter_base_url: str = os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        )
        self.openrouter_site_url: str = os.getenv("OPENROUTER_SITE_URL", "")
        self.openrouter_app_name: str = os.getenv("OPENROUTER_APP_NAME", "CLITool")

        # Azure OpenAI 設定
        self.azure_api_key: str = os.getenv("AZURE_OPENAI_API_KEY", "")
        self.azure_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        self.azure_deployment: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        self.azure_api_version: str = os.getenv(
            "AZURE_OPENAI_API_VERSION", "2024-02-01"
        )

        # エージェント動作設定
        self.max_context_tokens: int = int(os.getenv("MAX_CONTEXT_TOKENS", "128000"))
        self.max_output_tokens: int = int(os.getenv("MAX_OUTPUT_TOKENS", "8192"))
        self.temperature: float = float(os.getenv("TEMPERATURE", "0.7"))
        self.stream: bool = os.getenv("STREAM", "true").lower() == "true"

        # エージェントループ設定
        self.max_agent_loops: int = int(os.getenv("MAX_AGENT_LOOPS", "20"))

        # ツール設定
        self.allow_shell_exec: bool = (
            os.getenv("ALLOW_SHELL_EXEC", "true").lower() == "true"
        )
        self.allow_code_exec: bool = (
            os.getenv("ALLOW_CODE_EXEC", "true").lower() == "true"
        )
        self.workspace_dir: str = os.path.abspath(
            os.getenv("WORKSPACE_DIR", ".")
        )

        # ログ設定
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
        self.log_file: str = os.getenv("LOG_FILE", "agent.log")

    def _load_dotenv(self, path: str) -> None:
        """シンプルな .env パーサー（標準ライブラリのみ）。

        Args:
            path: .env ファイルのパス
        """
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                os.environ.setdefault(key, val)
