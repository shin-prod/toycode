#!/usr/bin/env python3
"""
テトリス - Pygame版
"""

import pygame
import sys
import random
from typing import List, Tuple

# 初期化
pygame.init()

# 定数
CELL_SIZE = 30
BOARD_WIDTH = 10
BOARD_HEIGHT = 20
SCREEN_WIDTH = CELL_SIZE * (BOARD_WIDTH + 8)
SCREEN_HEIGHT = CELL_SIZE * BOARD_HEIGHT
FPS = 60

# 色定義
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (128, 128, 128)
DARK_GRAY = (64, 64, 64)
LIGHT_GRAY = (192, 192, 192)

# テトリミノの色
COLORS = {
    'I': (0, 255, 255),      # シアン
    'O': (255, 255, 0),      # イエロー
    'T': (128, 0, 128),      # パープル
    'S': (0, 255, 0),        # グリーン
    'Z': (255, 0, 0),        # レッド
    'J': (0, 0, 255),        # ブルー
    'L': (255, 165, 0),      # オレンジ
}

# テトリミノの形状（各回転状態）
SHAPES = {
    'I': [
        [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]],
        [[0, 0, 1, 0], [0, 0, 1, 0], [0, 0, 1, 0], [0, 0, 1, 0]],
        [[0, 0, 0, 0], [0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0]],
        [[0, 1, 0, 0], [0, 1, 0, 0], [0, 1, 0, 0], [0, 1, 0, 0]],
    ],
    'O': [
        [[1, 1], [1, 1]],
        [[1, 1], [1, 1]],
        [[1, 1], [1, 1]],
        [[1, 1], [1, 1]],
    ],
    'T': [
        [[0, 1, 0], [1, 1, 1], [0, 0, 0]],
        [[0, 1, 0], [0, 1, 1], [0, 1, 0]],
        [[0, 0, 0], [1, 1, 1], [0, 1, 0]],
        [[0, 1, 0], [1, 1, 0], [0, 1, 0]],
    ],
    'S': [
        [[0, 1, 1], [1, 1, 0], [0, 0, 0]],
        [[0, 1, 0], [0, 1, 1], [0, 0, 1]],
        [[0, 0, 0], [0, 1, 1], [1, 1, 0]],
        [[1, 0, 0], [1, 1, 0], [0, 1, 0]],
    ],
    'Z': [
        [[1, 1, 0], [0, 1, 1], [0, 0, 0]],
        [[0, 0, 1], [0, 1, 1], [0, 1, 0]],
        [[0, 0, 0], [1, 1, 0], [0, 1, 1]],
        [[0, 1, 0], [1, 1, 0], [1, 0, 0]],
    ],
    'J': [
        [[1, 0, 0], [1, 1, 1], [0, 0, 0]],
        [[0, 1, 1], [0, 1, 0], [0, 1, 0]],
        [[0, 0, 0], [1, 1, 1], [0, 0, 1]],
        [[0, 1, 0], [0, 1, 0], [1, 1, 0]],
    ],
    'L': [
        [[0, 0, 1], [1, 1, 1], [0, 0, 0]],
        [[0, 1, 0], [0, 1, 0], [0, 1, 1]],
        [[0, 0, 0], [1, 1, 1], [1, 0, 0]],
        [[1, 1, 0], [0, 1, 0], [0, 1, 0]],
    ],
}


class Tetromino:
    def __init__(self, shape_type: str):
        self.type = shape_type
        self.shape = SHAPES[shape_type]
        self.rotation = 0
        self.x = BOARD_WIDTH // 2 - 2
        self.y = 0
        self.color = COLORS[shape_type]
    
    def get_current_shape(self) -> List[List[int]]:
        return self.shape[self.rotation]
    
    def rotate_clockwise(self):
        self.rotation = (self.rotation + 1) % 4
    
    def rotate_counter_clockwise(self):
        self.rotation = (self.rotation - 1) % 4
    
    def get_positions(self) -> List[Tuple[int, int]]:
        positions = []
        shape = self.get_current_shape()
        for y, row in enumerate(shape):
            for x, cell in enumerate(row):
                if cell:
                    positions.append((self.x + x, self.y + y))
        return positions


class TetrisGame:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("テトリス")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)
        self.reset_game()
    
    def reset_game(self):
        # ボードの初期化（0は空、色のタプルはブロック）
        self.board: List[List[Tuple[int, int, int] | int]] = [
            [0 for _ in range(BOARD_WIDTH)] for _ in range(BOARD_HEIGHT)
        ]
        self.score = 0
        self.lines_cleared = 0
        self.level = 1
        self.game_over = False
        self.paused = False
        
        # 次のピースのキュー
        self.bag = []
        self.next_piece_type = None
        
        # 現在のピース
        self.current_piece = self.spawn_piece()
        self.next_piece_type = self.get_next_from_bag()
        
        # 落下タイマー
        self.fall_timer = 0
        self.fall_speed = 1000  # ミリ秒
        self.lock_delay = 500  # 接地後のロックまでの時間
        self.lock_timer = 0
        self.locking = False
        
        # キー入力のリピート制御
        self.key_repeat_delay = 150
        self.key_repeat_interval = 50
        self.last_key_time = {}
    
    def get_next_from_bag(self) -> str:
        # 7-bagシステム
        if len(self.bag) == 0:
            self.bag = list(SHAPES.keys())
            random.shuffle(self.bag)
        return self.bag.pop()
    
    def spawn_piece(self) -> Tetromino:
        if self.next_piece_type is None:
            shape_type = self.get_next_from_bag()
        else:
            shape_type = self.next_piece_type
        
        piece = Tetromino(shape_type)
        
        # スポーン位置で衝突していたらゲームオーバー
        if self.check_collision(piece, piece.x, piece.y):
            self.game_over = True
        
        return piece
    
    def check_collision(self, piece: Tetromino, offset_x: int, offset_y: int) -> bool:
        shape = piece.get_current_shape()
        for y, row in enumerate(shape):
            for x, cell in enumerate(row):
                if cell:
                    new_x = offset_x + x
                    new_y = offset_y + y
                    
                    # 壁や床との衝突
                    if new_x < 0 or new_x >= BOARD_WIDTH or new_y >= BOARD_HEIGHT:
                        return True
                    
                    # ボード上のブロックとの衝突
                    if new_y >= 0 and self.board[new_y][new_x] != 0:
                        return True
        return False
    
    def lock_piece(self):
        # ピースをボードに固定
        for x, y in self.current_piece.get_positions():
            if 0 <= y < BOARD_HEIGHT and 0 <= x < BOARD_WIDTH:
                self.board[y][x] = self.current_piece.color
        
        # ライン消去
        self.clear_lines()
        
        # 新しいピースをスポーン
        self.next_piece_type = self.get_next_from_bag()
        self.current_piece = self.spawn_piece()
        self.locking = False
        self.lock_timer = 0
    
    def clear_lines(self):
        lines = 0
        y = BOARD_HEIGHT - 1
        while y >= 0:
            # 行が埋まっているかチェック
            if all(cell != 0 for cell in self.board[y]):
                # 行を削除して上を下にずらす
                del self.board[y]
                self.board.insert(0, [0 for _ in range(BOARD_WIDTH)])
                lines += 1
            else:
                y -= 1
        
        if lines > 0:
            self.lines_cleared += lines
            # スコア計算
            points = {1: 100, 2: 300, 3: 500, 4: 800}
            self.score += points.get(lines, 800) * self.level
            
            # レベルアップ
            new_level = self.lines_cleared // 10 + 1
            if new_level > self.level:
                self.level = new_level
                self.fall_speed = max(100, 1000 - (self.level - 1) * 80)
    
    def move_piece(self, dx: int, dy: int) -> bool:
        if not self.check_collision(self.current_piece, self.current_piece.x + dx, self.current_piece.y + dy):
            self.current_piece.x += dx
            self.current_piece.y += dy
            if dy > 0:
                self.locking = False
                self.lock_timer = 0
            return True
        return False
    
    def rotate_piece(self, clockwise: bool = True):
        original_rotation = self.current_piece.rotation
        
        if clockwise:
            self.current_piece.rotate_clockwise()
        else:
            self.current_piece.rotate_counter_clockwise()
        
        # 基本の回転を試す
        if not self.check_collision(self.current_piece, self.current_piece.x, self.current_piece.y):
            return
        
        # 壁キックを試す（SRS簡易版）
        kicks = [-1, 1, -2, 2]
        for kick in kicks:
            if not self.check_collision(self.current_piece, self.current_piece.x + kick, self.current_piece.y):
                self.current_piece.x += kick
                return
        
        # 回転できない場合は元に戻す
        self.current_piece.rotation = original_rotation
    
    def hard_drop(self):
        # 最下まで落とす
        while self.move_piece(0, 1):
            pass
        self.lock_piece()
        self.score += 2
    
    def update(self, dt: int):
        if self.game_over or self.paused:
            return
        
        self.fall_timer += dt
        
        # 自動落下
        if self.fall_timer >= self.fall_speed:
            self.fall_timer = 0
            if not self.move_piece(0, 1):
                # 下に移動できない場合
                if not self.locking:
                    self.locking = True
                    self.lock_timer = 0
        
        # ロック遅延
        if self.locking:
            self.lock_timer += dt
            if self.lock_timer >= self.lock_delay:
                self.lock_piece()
    
    def handle_key_repeat(self, key: int, action):
        current_time = pygame.time.get_ticks()
        if key not in self.last_key_time:
            self.last_key_time[key] = 0
        
        if current_time - self.last_key_time[key] > self.key_repeat_delay:
            action()
            self.last_key_time[key] = current_time - self.key_repeat_delay + self.key_repeat_interval
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r and self.game_over:
                    self.reset_game()
                    continue
                
                if event.key == pygame.K_p:
                    self.paused = not self.paused
                    continue
                
                if self.game_over or self.paused:
                    continue
                
                if event.key == pygame.K_LEFT:
                    self.move_piece(-1, 0)
                    self.last_key_time[pygame.K_LEFT] = pygame.time.get_ticks()
                elif event.key == pygame.K_RIGHT:
                    self.move_piece(1, 0)
                    self.last_key_time[pygame.K_RIGHT] = pygame.time.get_ticks()
                elif event.key == pygame.K_DOWN:
                    if self.move_piece(0, 1):
                        self.score += 1
                    self.last_key_time[pygame.K_DOWN] = pygame.time.get_ticks()
                elif event.key == pygame.K_UP or event.key == pygame.K_x:
                    self.rotate_piece(clockwise=True)
                elif event.key == pygame.K_z:
                    self.rotate_piece(clockwise=False)
                elif event.key == pygame.K_SPACE:
                    self.hard_drop()
            
            if event.type == pygame.KEYUP:
                if event.key in self.last_key_time:
                    del self.last_key_time[event.key]
        
        # キーリピート
        keys = pygame.key.get_pressed()
        if not self.game_over and not self.paused:
            if keys[pygame.K_LEFT]:
                self.handle_key_repeat(pygame.K_LEFT, lambda: self.move_piece(-1, 0))
            if keys[pygame.K_RIGHT]:
                self.handle_key_repeat(pygame.K_RIGHT, lambda: self.move_piece(1, 0))
            if keys[pygame.K_DOWN]:
                self.handle_key_repeat(pygame.K_DOWN, lambda: self.move_piece(0, 1) and self.score + 1)
        
        return True
    
    def draw_board(self):
        # ボードの背景
        board_rect = pygame.Rect(0, 0, BOARD_WIDTH * CELL_SIZE, BOARD_HEIGHT * CELL_SIZE)
        pygame.draw.rect(self.screen, BLACK, board_rect)
        
        # グリッド線
        for x in range(BOARD_WIDTH + 1):
            pygame.draw.line(self.screen, DARK_GRAY, 
                           (x * CELL_SIZE, 0), 
                           (x * CELL_SIZE, BOARD_HEIGHT * CELL_SIZE))
        for y in range(BOARD_HEIGHT + 1):
            pygame.draw.line(self.screen, DARK_GRAY, 
                           (0, y * CELL_SIZE), 
                           (BOARD_WIDTH * CELL_SIZE, y * CELL_SIZE))
        
        # 固定されたブロック
        for y, row in enumerate(self.board):
            for x, cell in enumerate(row):
                if cell != 0:
                    self.draw_block(x, y, cell)
        
        # 現在のピースのゴースト
        if not self.game_over:
            self.draw_ghost()
        
        # 現在のピース
        if not self.game_over:
            for x, y in self.current_piece.get_positions():
                if y >= 0:
                    self.draw_block(x, y, self.current_piece.color)
    
    def draw_ghost(self):
        # ハードドロップ位置の表示
        ghost_y = self.current_piece.y
        while not self.check_collision(self.current_piece, self.current_piece.x, ghost_y + 1):
            ghost_y += 1
        
        shape = self.current_piece.get_current_shape()
        for y, row in enumerate(shape):
            for x, cell in enumerate(row):
                if cell:
                    draw_x = (self.current_piece.x + x) * CELL_SIZE
                    draw_y = (ghost_y + y) * CELL_SIZE
                    # 半透明の枠を描画
                    rect = pygame.Rect(draw_x + 1, draw_y + 1, CELL_SIZE - 2, CELL_SIZE - 2)
                    pygame.draw.rect(self.screen, GRAY, rect, 2)
    
    def draw_block(self, x: int, y: int, color: Tuple[int, int, int]):
        rect = pygame.Rect(x * CELL_SIZE + 1, y * CELL_SIZE + 1, CELL_SIZE - 2, CELL_SIZE - 2)
        pygame.draw.rect(self.screen, color, rect)
        
        # ハイライト（3D効果）
        highlight = tuple(min(255, c + 40) for c in color)
        pygame.draw.rect(self.screen, highlight, (rect.x, rect.y, rect.width - 1, 2))
        pygame.draw.rect(self.screen, highlight, (rect.x, rect.y, 2, rect.height - 1))
        
        # シャドウ
        shadow = tuple(max(0, c - 40) for c in color)
        pygame.draw.rect(self.screen, shadow, (rect.x + rect.width - 2, rect.y + 1, 2, rect.height - 2))
        pygame.draw.rect(self.screen, shadow, (rect.x + 1, rect.y + rect.height - 2, rect.width - 2, 2))
    
    def draw_next_piece(self):
        # 次のピース表示エリア
        next_x = BOARD_WIDTH * CELL_SIZE + 20
        next_y = 20
        
        title = self.font.render("NEXT", True, WHITE)
        self.screen.blit(title, (next_x, next_y))
        
        # 次のピースを描画
        if self.next_piece_type:
            preview = Tetromino(self.next_piece_type)
            shape = preview.get_current_shape()
            
            offset_x = next_x + 20
            offset_y = next_y + 40
            
            for y, row in enumerate(shape):
                for x, cell in enumerate(row):
                    if cell:
                        rect = pygame.Rect(
                            offset_x + x * CELL_SIZE,
                            offset_y + y * CELL_SIZE,
                            CELL_SIZE - 2, CELL_SIZE - 2
                        )
                        pygame.draw.rect(self.screen, preview.color, rect)
    
    def draw_info(self):
        info_x = BOARD_WIDTH * CELL_SIZE + 20
        
        # スコア
        score_text = self.font.render(f"SCORE", True, WHITE)
        self.screen.blit(score_text, (info_x, 150))
        score_val = self.small_font.render(str(self.score), True, WHITE)
        self.screen.blit(score_val, (info_x, 180))
        
        # レベル
        level_text = self.font.render(f"LEVEL", True, WHITE)
        self.screen.blit(level_text, (info_x, 230))
        level_val = self.small_font.render(str(self.level), True, WHITE)
        self.screen.blit(level_val, (info_x, 260))
        
        # ライン数
        lines_text = self.font.render(f"LINES", True, WHITE)
        self.screen.blit(lines_text, (info_x, 310))
        lines_val = self.small_font.render(str(self.lines_cleared), True, WHITE)
        self.screen.blit(lines_val, (info_x, 340))
    
    def draw_controls(self):
        info_x = BOARD_WIDTH * CELL_SIZE + 20
        controls_y = SCREEN_HEIGHT - 180
        
        controls = [
            "Controls:",
            "← → : Move",
            "↓ : Soft Drop",
            "↑/X : Rotate",
            "Z : Rotate L",
            "Space : Hard Drop",
            "P : Pause",
        ]
        
        for i, text in enumerate(controls):
            color = GRAY if i == 0 else WHITE
            font = self.small_font if i > 0 else self.font
            surf = font.render(text, True, color)
            self.screen.blit(surf, (info_x, controls_y + i * 22))
    
    def draw(self):
        self.screen.fill(BLACK)
        
        # ゲームボード
        self.draw_board()
        
        # サイドパネル
        self.draw_next_piece()
        self.draw_info()
        self.draw_controls()
        
        # ポーズ表示
        if self.paused:
            pause_text = self.font.render("PAUSED", True, WHITE)
            text_rect = pause_text.get_rect(center=(BOARD_WIDTH * CELL_SIZE // 2, SCREEN_HEIGHT // 2))
            self.screen.blit(pause_text, text_rect)
        
        # ゲームオーバー
        if self.game_over:
            overlay = pygame.Surface((BOARD_WIDTH * CELL_SIZE, SCREEN_HEIGHT))
            overlay.set_alpha(180)
            overlay.fill(BLACK)
            self.screen.blit(overlay, (0, 0))
            
            over_text = self.font.render("GAME OVER", True, (255, 0, 0))
            text_rect = over_text.get_rect(center=(BOARD_WIDTH * CELL_SIZE // 2, SCREEN_HEIGHT // 2 - 30))
            self.screen.blit(over_text, text_rect)
            
            restart_text = self.small_font.render("Press R to Restart", True, WHITE)
            text_rect = restart_text.get_rect(center=(BOARD_WIDTH * CELL_SIZE // 2, SCREEN_HEIGHT // 2 + 20))
            self.screen.blit(restart_text, text_rect)
        
        pygame.display.flip()
    
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS)
            
            running = self.handle_events()
            self.update(dt)
            self.draw()
        
        pygame.quit()
        sys.exit()


def main():
    print("=" * 50)
    print("  テトリス")
    print("=" * 50)
    print("操作:")
    print("  ← →    : 左右移動")
    print("  ↓      : ソフトドロップ")
    print("  ↑ または X : 右回転")
    print("  Z      : 左回転")
    print("  SPACE  : ハードドロップ")
    print("  P      : ポーズ")
    print("=" * 50)
    
    game = TetrisGame()
    game.run()


if __name__ == "__main__":
    main()
