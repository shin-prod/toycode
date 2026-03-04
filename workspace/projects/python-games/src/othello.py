"""
オセロゲーム (Othello/Reversi)
Python + tkinter で実装
"""

import tkinter as tk
from tkinter import messagebox


class OthelloGame:
    """オセロのゲームロジック"""
    
    # 方向ベクトル（8方向）
    DIRECTIONS = [
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1),         (0, 1),
        (1, -1), (1, 0), (1, 1)
    ]
    
    def __init__(self):
        self.board = [[None for _ in range(8)] for _ in range(8)]
        self.current_player = "black"  # 黒が先手
        self.initialize_board()
    
    def initialize_board(self):
        """初期配置をセット"""
        # 中央4マスに配置
        self.board[3][3] = "white"
        self.board[3][4] = "black"
        self.board[4][3] = "black"
        self.board[4][4] = "white"
    
    def get_opponent(self, player):
        """相手プレイヤーを返す"""
        return "white" if player == "black" else "black"
    
    def is_valid_move(self, row, col, player):
        """指定位置に石が置けるかチェック"""
        if self.board[row][col] is not None:
            return False
        
        opponent = self.get_opponent(player)
        
        for dr, dc in self.DIRECTIONS:
            r, c = row + dr, col + dc
            # 隣が相手の石かチェック
            if 0 <= r < 8 and 0 <= c < 8 and self.board[r][c] == opponent:
                # その方向に進んで自分の石があるか
                while 0 <= r < 8 and 0 <= c < 8:
                    if self.board[r][c] is None:
                        break
                    if self.board[r][c] == player:
                        return True
                    r += dr
                    c += dc
        return False
    
    def get_flippable_stones(self, row, col, player):
        """石を置いたときに裏返せる石のリストを返す"""
        flippable = []
        opponent = self.get_opponent(player)
        
        for dr, dc in self.DIRECTIONS:
            r, c = row + dr, col + dc
            stones_in_direction = []
            
            while 0 <= r < 8 and 0 <= c < 8:
                if self.board[r][c] is None:
                    break
                if self.board[r][c] == opponent:
                    stones_in_direction.append((r, c))
                elif self.board[r][c] == player:
                    flippable.extend(stones_in_direction)
                    break
                r += dr
                c += dc
        
        return flippable
    
    def make_move(self, row, col):
        """石を置いて裏返す。成功したらTrueを返す"""
        if not self.is_valid_move(row, col, self.current_player):
            return False
        
        # 石を置く
        self.board[row][col] = self.current_player
        
        # 裏返す
        flippable = self.get_flippable_stones(row, col, self.current_player)
        for r, c in flippable:
            self.board[r][c] = self.current_player
        
        # ターン交代
        self.current_player = self.get_opponent(self.current_player)
        
        # 相手が打てない場合はパス
        if not self.has_valid_moves(self.current_player):
            self.current_player = self.get_opponent(self.current_player)
        
        return True
    
    def has_valid_moves(self, player):
        """指定プレイヤーが打てる手があるか"""
        for row in range(8):
            for col in range(8):
                if self.is_valid_move(row, col, player):
                    return True
        return False
    
    def get_valid_moves(self, player):
        """打てる手のリストを返す"""
        moves = []
        for row in range(8):
            for col in range(8):
                if self.is_valid_move(row, col, player):
                    moves.append((row, col))
        return moves
    
    def count_stones(self):
        """石の数をカウント"""
        black = sum(row.count("black") for row in self.board)
        white = sum(row.count("white") for row in self.board)
        return black, white
    
    def is_game_over(self):
        """ゲーム終了判定"""
        return not self.has_valid_moves("black") and not self.has_valid_moves("white")


class OthelloGUI:
    """オセロのGUI表示"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("オセロ (Othello)")
        self.root.resizable(False, False)
        
        self.game = OthelloGame()
        self.cell_size = 60
        
        self.setup_ui()
        self.draw_board()
    
    def setup_ui(self):
        """UIのセットアップ"""
        # 情報表示フレーム
        info_frame = tk.Frame(self.root, bg="#2c3e50", padx=10, pady=10)
        info_frame.pack(fill=tk.X)
        
        self.status_label = tk.Label(
            info_frame, 
            text="黒の番です", 
            font=("Helvetica", 14, "bold"),
            bg="#2c3e50",
            fg="white"
        )
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        self.score_label = tk.Label(
            info_frame,
            text="黒: 2  白: 2",
            font=("Helvetica", 14),
            bg="#2c3e50",
            fg="white"
        )
        self.score_label.pack(side=tk.RIGHT, padx=10)
        
        # ボードキャンバス
        self.canvas = tk.Canvas(
            self.root,
            width=8 * self.cell_size,
            height=8 * self.cell_size,
            bg="#27ae60"
        )
        self.canvas.pack()
        
        # ハイライト表示用の長方形（初期は非表示）
        self.highlight_rect = None
        
        # クリックイベント
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_motion)
        
        # リスタートボタン
        button_frame = tk.Frame(self.root, bg="#2c3e50", pady=10)
        button_frame.pack(fill=tk.X)
        
        restart_btn = tk.Button(
            button_frame,
            text="新規ゲーム",
            font=("Helvetica", 12),
            command=self.restart_game,
            bg="#3498db",
            fg="white",
            activebackground="#2980b9"
        )
        restart_btn.pack()
    
    def draw_board(self):
        """ボードを描画"""
        self.canvas.delete("all")
        
        # マス目を描画
        for i in range(9):
            # 縦線
            self.canvas.create_line(
                i * self.cell_size, 0,
                i * self.cell_size, 8 * self.cell_size,
                fill="#1e8449", width=2
            )
            # 横線
            self.canvas.create_line(
                0, i * self.cell_size,
                8 * self.cell_size, i * self.cell_size,
                fill="#1e8449", width=2
            )
        
        # 有効な手をハイライト
        valid_moves = self.game.get_valid_moves(self.game.current_player)
        for row, col in valid_moves:
            x = col * self.cell_size + self.cell_size // 2
            y = row * self.cell_size + self.cell_size // 2
            self.canvas.create_oval(
                x - 5, y - 5, x + 5, y + 5,
                fill="#f1c40f", outline=""
            )
        
        # 石を描画
        for row in range(8):
            for col in range(8):
                stone = self.game.board[row][col]
                if stone:
                    self.draw_stone(row, col, stone)
        
        # ハイライトリセット
        self.highlight_rect = None
    
    def draw_stone(self, row, col, stone):
        """石を描画"""
        margin = 4
        x1 = col * self.cell_size + margin
        y1 = row * self.cell_size + margin
        x2 = (col + 1) * self.cell_size - margin
        y2 = (row + 1) * self.cell_size - margin
        
        color = "black" if stone == "black" else "white"
        outline = "#333" if stone == "white" else "#000"
        
        self.canvas.create_oval(
            x1, y1, x2, y2,
            fill=color,
            outline=outline,
            width=2
        )
    
    def on_motion(self, event):
        """マウス移動時のハイライト"""
        col = event.x // self.cell_size
        row = event.y // self.cell_size
        
        if 0 <= row < 8 and 0 <= col < 8:
            if self.game.is_valid_move(row, col, self.game.current_player):
                if self.highlight_rect:
                    self.canvas.delete(self.highlight_rect)
                self.highlight_rect = self.canvas.create_rectangle(
                    col * self.cell_size + 2,
                    row * self.cell_size + 2,
                    (col + 1) * self.cell_size - 2,
                    (row + 1) * self.cell_size - 2,
                    outline="#f1c40f",
                    width=3
                )
            else:
                if self.highlight_rect:
                    self.canvas.delete(self.highlight_rect)
                    self.highlight_rect = None
    
    def on_click(self, event):
        """クリック時の処理"""
        col = event.x // self.cell_size
        row = event.y // self.cell_size
        
        if 0 <= row < 8 and 0 <= col < 8:
            if self.game.make_move(row, col):
                self.draw_board()
                self.update_status()
                
                if self.game.is_game_over():
                    self.show_result()
    
    def update_status(self):
        """ステータス表示を更新"""
        black_count, white_count = self.game.count_stones()
        
        current = "黒" if self.game.current_player == "black" else "白"
        self.status_label.config(text=f"{current}の番です")
        self.score_label.config(text=f"黒: {black_count}  白: {white_count}")
    
    def show_result(self):
        """結果表示"""
        black_count, white_count = self.game.count_stones()
        
        if black_count > white_count:
            winner = "黒の勝利！"
        elif white_count > black_count:
            winner = "白の勝利！"
        else:
            winner = "引き分け！"
        
        message = f"ゲーム終了！\n\n黒: {black_count}  白: {white_count}\n\n{winner}"
        messagebox.showinfo("結果", message)
    
    def restart_game(self):
        """ゲームをリセット"""
        self.game = OthelloGame()
        self.draw_board()
        self.update_status()


def main():
    """メイン関数"""
    root = tk.Tk()
    app = OthelloGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
