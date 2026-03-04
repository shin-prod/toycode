#!/bin/bash
# install.sh - myagent をグローバルコマンドとしてインストールする
#
# 使い方:
#   ./install.sh          # デフォルト名 "myagent" でインストール
#   ./install.sh ai       # 任意のコマンド名を指定

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMAND_NAME="${1:-myagent}"
INSTALL_DIR="$HOME/.local/bin"
INSTALL_PATH="${INSTALL_DIR}/${COMMAND_NAME}"

# AI_DIR を .env から取得（デフォルト: .myagent）
AI_DIR_REL="$(grep -E '^AI_DIR=' "${SCRIPT_DIR}/.env" 2>/dev/null | head -1 | cut -d'=' -f2 | tr -d '"' | tr -d "'")"
AI_DIR_REL="${AI_DIR_REL:-.myagent}"
VENV_ACTIVATE="${SCRIPT_DIR}/${AI_DIR_REL}/venv/bin/activate"

# インストール先ディレクトリを作成
mkdir -p "$INSTALL_DIR"

# グローバル wrapper スクリプトを生成
cat > "$INSTALL_PATH" << WRAPPER
#!/bin/bash
# ${COMMAND_NAME} - toy2 AI エージェント グローバル wrapper
# 生成元: ${SCRIPT_DIR}/install.sh

TOY2_DIR="${SCRIPT_DIR}"
VENV_ACTIVATE="${VENV_ACTIVATE}"

# 呼び出し元のカレントディレクトリをワークスペースとして渡す
export WORKSPACE_DIR="\$(pwd)"

# 仮想環境をアクティベート
if [ ! -f "\$VENV_ACTIVATE" ]; then
    echo "[ERROR] venv が見つかりません: \${VENV_ACTIVATE}" >&2
    echo "        先に \${TOY2_DIR}/run.sh を一度実行してください。" >&2
    exit 1
fi
source "\$VENV_ACTIVATE"

# toy2 ルートへ移動（.env から API キーを読み込むため）
cd "\$TOY2_DIR"

exec python run_agent.py "\$@"
WRAPPER

chmod +x "$INSTALL_PATH"

echo ""
echo "インストール完了: ${INSTALL_PATH}"
echo ""

# PATH に ~/.local/bin が含まれているか確認
if echo "$PATH" | grep -q "$INSTALL_DIR"; then
    echo "  使い方: ${COMMAND_NAME}"
else
    echo "  ※ PATH に ${INSTALL_DIR} が含まれていません。"
    echo "  以下を ~/.zshrc または ~/.bashrc に追加してください:"
    echo ""
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "  追加後: source ~/.zshrc && ${COMMAND_NAME}"
fi
echo ""
