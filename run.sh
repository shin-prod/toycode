#!/bin/bash
# Claude-Like CLI Tool 起動スクリプト

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# AI_DIR を .env から取得（デフォルト: .myagent）
AI_DIR="$(grep -E '^AI_DIR=' .env 2>/dev/null | head -1 | cut -d'=' -f2 | tr -d '"' | tr -d "'")"
AI_DIR="${AI_DIR:-.myagent}"
VENV_DIR="${AI_DIR}/venv"

# WORKSPACE_DIR を .env から取得（デフォルト: このスクリプトがあるフォルダ）
WORKSPACE_DIR="$(grep -E '^WORKSPACE_DIR=' .env 2>/dev/null | head -1 | cut -d'=' -f2 | tr -d '"' | tr -d "'")"
WORKSPACE_DIR="${WORKSPACE_DIR:-$SCRIPT_DIR}"

# WORKSPACE_DIR の存在確認
if [ ! -d "$WORKSPACE_DIR" ]; then
    echo "[ERROR] WORKSPACE_DIR が存在しません: ${WORKSPACE_DIR}" >&2
    echo "        .env の WORKSPACE_DIR を確認してください。" >&2
    exit 1
fi

# 仮想環境を AI_DIR/venv に作成（初回のみ）
if [ ! -d "$VENV_DIR" ]; then
    echo "[INFO] 仮想環境を作成しています: ${VENV_DIR}"
    python3 -m venv "$VENV_DIR"
fi

# 仮想環境をアクティベート
source "${VENV_DIR}/bin/activate"

# 依存パッケージのインストール確認（初回 or requirements.txt 更新時）
python -c "import pptx, docx, openpyxl" 2>/dev/null || {
    echo "[INFO] 依存パッケージをインストールします..."
    pip install -r requirements.txt
}

# アプリ起動
python run_agent.py "$@"
