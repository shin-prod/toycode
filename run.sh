#!/bin/bash
# Claude-Like CLI Tool 起動スクリプト

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 仮想環境の確認・アクティベート
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif conda info --envs 2>/dev/null | grep -q "toy2"; then
    conda activate toy2
fi

# 依存パッケージのインストール確認
python3 -c "import pptx, docx, openpyxl" 2>/dev/null || {
    echo "[INFO] 依存パッケージをインストールします..."
    pip install -r requirements.txt
}

# アプリ起動
python3 main.py "$@"
