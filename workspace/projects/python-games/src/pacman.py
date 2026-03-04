#!/usr/bin/env python3
"""
パックマンゲーム - Pygame版
"""

import pygame
import sys
import math
from enum import Enum
from typing import List, Tuple

# 初期化
pygame.init()

# 定数
TILE_SIZE = 32
SCREEN_WIDTH = 28 * TILE_SIZE  # 28タイル幅
SCREEN_HEIGHT = 31 * TILE_SIZE + 50  # 31タイル高さ + スコア表示
FPS = 60

# 色定義
BLACK = (0, 0, 0)
BLUE = (33, 33, 222)
YELLOW = (255, 255, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
PINK = (255, 184, 255)
CYAN = (0, 255, 255)
ORANGE = (255, 184, 82)
PEACH = (255, 213, 170)

# マップ (0:空間, 1:壁, 2:ドット, 3:パワードット)
MAP = [
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
    [1,2,2,2,2,2,2,2,2,2,2,2,2,1,1,2,2,2,2,2,2,2,2,2,2,2,2,1],
    [1,2,1,1,1,1,2,1,1,1,1,1,2,1,1,2,1,1,1,1,1,2,1,1,1,1,2,1],
    [1,3,1,1,1,1,2,1,1,1,1,1,2,1,1,2,1,1,1,1,1,2,1,1,1,1,3,1],
    [1,2,1,1,1,1,2,1,1,1,1,1,2,1,1,2,1,1,1,1,1,2,1,1,1,1,2,1],
    [1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1],
    [1,2,1,1,1,1,2,1,1,2,1,1,1,1,1,1,1,1,2,1,1,2,1,1,1,1,2,1],
    [1,2,1,1,1,1,2,1,1,2,1,1,1,1,1,1,1,1,2,1,1,2,1,1,1,1,2,1],
    [1,2,2,2,2,2,2,1,1,2,2,2,2,1,1,2,2,2,2,1,1,2,2,2,2,2,2,1],
    [1,1,1,1,1,1,2,1,1,1,1,1,0,1,1,0,1,1,1,1,1,2,1,1,1,1,1,1],
    [0,0,0,0,0,1,2,1,1,1,1,1,0,1,1,0,1,1,1,1,1,2,1,0,0,0,0,0],
    [0,0,0,0,0,1,2,1,1,0,0,0,0,0,0,0,0,0,0,1,1,2,1,0,0,0,0,0],
    [0,0,0,0,0,1,2,1,1,0,1,1,1,0,0,1,1,1,0,1,1,2,1,0,0,0,0,0],
    [1,1,1,1,1,1,2,1,1,0,1,0,0,0,0,0,0,1,0,1,1,2,1,1,1,1,1,1],
    [0,0,0,0,0,0,2,0,0,0,1,0,0,0,0,0,0,1,0,0,0,2,0,0,0,0,0,0],
    [1,1,1,1,1,1,2,1,1,0,1,0,0,0,0,0,0,1,0,1,1,2,1,1,1,1,1,1],
    [0,0,0,0,0,1,2,1,1,0,1,1,1,1,1,1,1,1,0,1,1,2,1,0,0,0,0,0],
    [0,0,0,0,0,1,2,1,1,0,0,0,0,0,0,0,0,0,0,1,1,2,1,0,0,0,0,0],
    [0,0,0,0,0,1,2,1,1,0,1,1,1,1,1,1,1,1,0,1,1,2,1,0,0,0,0,0],
    [1,1,1,1,1,1,2,1,1,0,1,1,1,1,1,1,1,1,0,1,1,2,1,1,1,1,1,1],
    [1,2,2,2,2,2,2,2,2,2,2,2,2,1,1,2,2,2,2,2,2,2,2,2,2,2,2,1],
    [1,2,1,1,1,1,2,1,1,1,1,1,2,1,1,2,1,1,1,1,1,2,1,1,1,1,2,1],
    [1,2,1,1,1,1,2,1,1,1,1,1,2,1,1,2,1,1,1,1,1,2,1,1,1,1,2,1],
    [1,3,2,2,1,1,2,2,2,2,2,2,2,0,0,2,2,2,2,2,2,2,1,1,2,2,3,1],
    [1,1,1,2,1,1,2,1,1,2,1,1,1,1,1,1,1,1,2,1,1,2,1,1,2,1,1,1],
    [1,1,1,2,1,1,2,1,1,2,1,1,1,1,1,1,1,1,2,1,1,2,1,1,2,1,1,1],
    [1,2,2,2,2,2,2,1,1,2,2,2,2,1,1,2,2,2,2,1,1,2,2,2,2,2,2,1],
    [1,2,1,1,1,1,1,1,1,1,1,1,2,1,1,2,1,1,1,1,1,1,1,1,1,1,2,1],
    [1,2,1,1,1,1,1,1,1,1,1,1,2,1,1,2,1,1,1,1,1,1,1,1,1,1,2,1],
    [1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1],
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
]


class Direction(Enum):
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)
    NONE = (0, 0)


class Entity:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.direction = Direction.NONE
        self.next_direction = Direction.NONE
        self.speed = 2
    
    def get_tile_pos(self) -> Tuple[int, int]:
        return int(self.x), int(self.y)
    
    def can_move(self, direction: Direction, game_map: List[List[int]]) -> bool:
        next_x = self.x + direction.value[0] * 0.5
        next_y = self.y + direction.value[1] * 0.5
        
        # 画面端のワープチェック
        if next_x < 0:
            return game_map[int(self.y)][27] != 1
        if next_x >= 28:
            return game_map[int(self.y)][0] != 1
        
        tile_x = int(next_x)
        tile_y = int(next_y)
        
        if 0 <= tile_y < len(game_map) and 0 <= tile_x < len(game_map[0]):
            return game_map[tile_y][tile_x] != 1
        return False
    
    def move(self):
        self.x += self.direction.value[0] * self.speed / TILE_SIZE
        self.y += self.direction.value[1] * self.speed / TILE_SIZE
        
        # 画面端のワープ
        if self.x < -0.5:
            self.x = 28
        elif self.x > 28.5:
            self.x = -1


class Pacman(Entity):
    def __init__(self, x: float, y: float):
        super().__init__(x, y)
        self.speed = 2.5
        self.mouth_angle = 0
        self.mouth_speed = 0.2
        self.dead = False
        self.death_timer = 0
    
    def update(self, game_map: List[List[int]]):
        if self.dead:
            self.death_timer += 1
            return
        
        # 次の方向に変更可能かチェック
        if self.next_direction != Direction.NONE and self.can_move(self.next_direction, game_map):
            # タイルの中心に近いときに方向転換
            center_x = self.x - int(self.x)
            center_y = self.y - int(self.y)
            if abs(center_x - 0.5) < 0.2 and abs(center_y - 0.5) < 0.2:
                self.direction = self.next_direction
        
        # 現在の方向に進めるかチェック
        if self.can_move(self.direction, game_map):
            self.move()
        
        # 口のアニメーション
        self.mouth_angle += self.mouth_speed
        if self.mouth_angle > 0.4 or self.mouth_angle < 0:
            self.mouth_speed *= -1
    
    def draw(self, screen: pygame.Surface):
        if self.dead:
            return
        
        pixel_x = int(self.x * TILE_SIZE + TILE_SIZE // 2)
        pixel_y = int(self.y * TILE_SIZE + TILE_SIZE // 2)
        
        # 口の向き
        start_angle = 0
        if self.direction == Direction.RIGHT:
            start_angle = self.mouth_angle
        elif self.direction == Direction.LEFT:
            start_angle = math.pi + self.mouth_angle
        elif self.direction == Direction.UP:
            start_angle = -math.pi/2 + self.mouth_angle
        elif self.direction == Direction.DOWN:
            start_angle = math.pi/2 + self.mouth_angle
        else:
            start_angle = self.mouth_angle
        
        end_angle = start_angle + 2 * math.pi - 2 * self.mouth_angle
        
        pygame.draw.circle(screen, YELLOW, (pixel_x, pixel_y), TILE_SIZE // 2 - 2)
        
        # 口の三角形
        if self.mouth_angle > 0.1:
            points = [(pixel_x, pixel_y)]
            for angle in [start_angle, end_angle]:
                px = pixel_x + math.cos(angle) * (TILE_SIZE // 2)
                py = pixel_y + math.sin(angle) * (TILE_SIZE // 2)
                points.append((px, py))
            pygame.draw.polygon(screen, BLACK, points)


class Ghost(Entity):
    def __init__(self, x: float, y: float, color: Tuple[int, int, int]):
        super().__init__(x, y)
        self.color = color
        self.speed = 1.8
        self.frightened = False
        self.frightened_timer = 0
        self.eyes_only = False
    
    def update(self, game_map: List[List[int]], pacman: Pacman):
        if self.frightened:
            self.frightened_timer -= 1
            if self.frightened_timer <= 0:
                self.frightened = False
            self.speed = 1.0
        else:
            self.speed = 1.8
        
        # ランダム方向選択（簡易AI）
        possible_directions = []
        for direction in [Direction.UP, Direction.DOWN, Direction.LEFT, Direction.RIGHT]:
            if self.can_move(direction, game_map) and direction != self.get_opposite_direction():
                possible_directions.append(direction)
        
        if possible_directions:
            if self.frightened:
                # 逃げる動き（ランダム）
                self.direction = possible_directions[pygame.time.get_ticks() % len(possible_directions)]
            else:
                # パックマンに近づく
                best_direction = possible_directions[0]
                best_distance = float('inf')
                
                for direction in possible_directions:
                    next_x = self.x + direction.value[0]
                    next_y = self.y + direction.value[1]
                    distance = math.sqrt((next_x - pacman.x) ** 2 + (next_y - pacman.y) ** 2)
                    
                    if distance < best_distance:
                        best_distance = distance
                        best_direction = direction
                
                self.direction = best_direction
        
        if self.can_move(self.direction, game_map):
            self.move()
    
    def get_opposite_direction(self) -> Direction:
        if self.direction == Direction.UP:
            return Direction.DOWN
        if self.direction == Direction.DOWN:
            return Direction.UP
        if self.direction == Direction.LEFT:
            return Direction.RIGHT
        if self.direction == Direction.RIGHT:
            return Direction.LEFT
        return Direction.NONE
    
    def draw(self, screen: pygame.Surface):
        pixel_x = int(self.x * TILE_SIZE + TILE_SIZE // 2)
        pixel_y = int(self.y * TILE_SIZE + TILE_SIZE // 2)
        
        if self.frightened:
            color = CYAN if self.frightened_timer < 120 and self.frightened_timer // 15 % 2 == 0 else BLUE
        else:
            color = self.color
        
        # ゴーストの体（上は円、下は波）
        radius = TILE_SIZE // 2 - 2
        pygame.draw.circle(screen, color, (pixel_x, pixel_y - 2), radius)
        pygame.draw.rect(screen, color, (pixel_x - radius, pixel_y - 2, radius * 2, radius + 2))
        
        # 足の波
        wave_points = []
        for i in range(5):
            wx = pixel_x - radius + i * (radius * 2 // 4)
            wy = pixel_y + radius - 2 if i % 2 == 0 else pixel_y + radius - 6
            wave_points.append((wx, wy))
        wave_points.append((pixel_x + radius, pixel_y - 2))
        pygame.draw.polygon(screen, color, wave_points)
        
        # 目
        if not self.frightened:
            eye_color = WHITE
            pupil_color = BLUE
        else:
            eye_color = WHITE
            pupil_color = WHITE
        
        # 左目
        pygame.draw.circle(screen, eye_color, (pixel_x - 5, pixel_y - 5), 4)
        pygame.draw.circle(screen, pupil_color, (pixel_x - 4, pixel_y - 5), 2)
        
        # 右目
        pygame.draw.circle(screen, eye_color, (pixel_x + 5, pixel_y - 5), 4)
        pygame.draw.circle(screen, pupil_color, (pixel_x + 6, pixel_y - 5), 2)


class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("パックマン")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.reset_game()
    
    def reset_game(self):
        self.map = [row[:] for row in MAP]
        self.pacman = Pacman(13.5, 23)
        self.ghosts = [
            Ghost(13.5, 11, RED),      # ブリンキー
            Ghost(11.5, 14, PINK),     # ピンキー
            Ghost(13.5, 14, CYAN),     # インキー
            Ghost(15.5, 14, ORANGE),   # クライド
        ]
        self.score = 0
        self.lives = 3
        self.level = 1
        self.game_over = False
        self.win = False
        self.dots_count = sum(row.count(2) + row.count(3) for row in self.map)
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            if event.type == pygame.KEYDOWN:
                if self.game_over or self.win:
                    if event.key == pygame.K_r:
                        self.reset_game()
                    continue
                
                if event.key == pygame.K_UP:
                    self.pacman.next_direction = Direction.UP
                elif event.key == pygame.K_DOWN:
                    self.pacman.next_direction = Direction.DOWN
                elif event.key == pygame.K_LEFT:
                    self.pacman.next_direction = Direction.LEFT
                elif event.key == pygame.K_RIGHT:
                    self.pacman.next_direction = Direction.RIGHT
        
        return True
    
    def update(self):
        if self.game_over or self.win:
            return
        
        self.pacman.update(self.map)
        
        # ドットを食べる
        tile_x, tile_y = self.pacman.get_tile_pos()
        if 0 <= tile_y < len(self.map) and 0 <= tile_x < len(self.map[0]):
            if self.map[tile_y][tile_x] == 2:
                self.map[tile_y][tile_x] = 0
                self.score += 10
                self.dots_count -= 1
            elif self.map[tile_y][tile_x] == 3:
                self.map[tile_y][tile_x] = 0
                self.score += 50
                self.dots_count -= 1
                # パワードットでゴーストを弱体化
                for ghost in self.ghosts:
                    ghost.frightened = True
                    ghost.frightened_timer = 600  # 10秒
        
        # ゴーストの更新
        for ghost in self.ghosts:
            ghost.update(self.map, self.pacman)
            
            # 衝突判定
            distance = math.sqrt((ghost.x - self.pacman.x) ** 2 + (ghost.y - self.pacman.y) ** 2)
            if distance < 0.8:
                if ghost.frightened:
                    # ゴーストを食べる
                    ghost.x = 13.5
                    ghost.y = 14
                    ghost.frightened = False
                    self.score += 200
                elif not self.pacman.dead:
                    # パックマンがやられる
                    self.pacman.dead = True
                    self.lives -= 1
                    if self.lives <= 0:
                        self.game_over = True
        
        # パックマンの復活
        if self.pacman.dead and self.pacman.death_timer > 60:
            self.pacman = Pacman(13.5, 23)
            for ghost in self.ghosts:
                ghost.x = 13.5
                ghost.y = 14
        
        # クリア判定
        if self.dots_count <= 0:
            self.win = True
    
    def draw_map(self):
        for y, row in enumerate(self.map):
            for x, tile in enumerate(row):
                rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                
                if tile == 1:  # 壁
                    pygame.draw.rect(self.screen, BLUE, rect)
                    pygame.draw.rect(self.screen, BLACK, rect, 2)
                elif tile == 2:  # ドット
                    center = (x * TILE_SIZE + TILE_SIZE // 2, y * TILE_SIZE + TILE_SIZE // 2)
                    pygame.draw.circle(self.screen, PEACH, center, 3)
                elif tile == 3:  # パワードット
                    center = (x * TILE_SIZE + TILE_SIZE // 2, y * TILE_SIZE + TILE_SIZE // 2)
                    pygame.draw.circle(self.screen, PEACH, center, 8)
    
    def draw(self):
        self.screen.fill(BLACK)
        
        # マップ
        self.draw_map()
        
        # パックマン
        self.pacman.draw(self.screen)
        
        # ゴースト
        for ghost in self.ghosts:
            ghost.draw(self.screen)
        
        # スコア表示
        score_text = self.font.render(f"SCORE: {self.score}", True, WHITE)
        self.screen.blit(score_text, (10, 31 * TILE_SIZE + 10))
        
        # 残機表示
        lives_text = self.font.render(f"LIVES: {self.lives}", True, WHITE)
        self.screen.blit(lives_text, (200, 31 * TILE_SIZE + 10))
        
        # ゲームオーバー
        if self.game_over:
            over_text = self.font.render("GAME OVER - Press R to Restart", True, RED)
            text_rect = over_text.get_rect(center=(SCREEN_WIDTH // 2, 31 * TILE_SIZE // 2))
            self.screen.blit(over_text, text_rect)
        
        # クリア
        if self.win:
            win_text = self.font.render("YOU WIN! - Press R to Restart", True, YELLOW)
            text_rect = win_text.get_rect(center=(SCREEN_WIDTH // 2, 31 * TILE_SIZE // 2))
            self.screen.blit(win_text, text_rect)
        
        pygame.display.flip()
    
    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)
        
        pygame.quit()
        sys.exit()


def main():
    print("=" * 50)
    print("  パックマン")
    print("=" * 50)
    print("操作: 矢印キーで移動")
    print("目標: ドットを全部食べる！")
    print("パワードット(大きい丸)を取るとゴーストを食べられる！")
    print("=" * 50)
    
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
