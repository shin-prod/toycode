#!/bin/bash
# ================================================================
# プロジェクト用エージェント起動テンプレート
#
# 使い方:
#   1. このファイルを AGENTS.md と一緒にプロジェクトフォルダに置く
#   2. chmod +x run.sh
#   3. ./run.sh で起動
#
# AI はこのスクリプトがあるフォルダ以下のみアクセス可能。
# ================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# toy2 のインストールパス（環境変数 TOY2_DIR で上書き可能）
TOY2_DIR="${TOY2_DIR:-$HOME/myprogram/toy2}"

if [ ! -d "$TOY2_DIR" ]; then
    echo "[ERROR] toy2 が見つかりません: ${TOY2_DIR}" >&2
    echo "        環境変数 TOY2_DIR にインストール先を指定してください。" >&2
    exit 1
fi

VENV_ACTIVATE="${TOY2_DIR}/.myagent/venv/bin/activate"
if [ ! -f "$VENV_ACTIVATE" ]; then
    echo "[ERROR] 仮想環境が見つかりません。先に ${TOY2_DIR}/run.sh を実行してください。" >&2
    exit 1
fi

# このフォルダをワークスペースとして設定（AI はここ以下しか触れない）
export WORKSPACE_DIR="$SCRIPT_DIR"

source "$VENV_ACTIVATE"
cd "$TOY2_DIR"
exec python run_agent.py "$@"
