# PuyoPuyo (minimal) - pygame

最小構成の「ぷよぷよ風」落ち物パズルです。

## セットアップ
```bash
cd projects/puyopuyo
python -m venv .venv
source .venv/bin/activate  # Windowsは .venv\\Scripts\\activate
pip install -r requirements.txt
```

## 実行
```bash
python scr/main.py
```

## 操作
- ← → : 移動
- ↓ : ソフトドロップ
- Z / X : 回転
- Space : ハードドロップ
- R : リスタート
- Esc : 終了

## 仕様（簡易）
- フィールド: 6x12
- 2個組のぷよが落下
- 4つ以上つながると消える
- 消した後、落下→再チェックで連鎖
- スコア: 消した個数×10×連鎖数

※本家ルール（細かい回転補正、同時消しボーナス、おじゃま等）は未実装です。
