"""
マリオ風プラットフォーマーゲーム
Pygameで実装した横スクロールアクションゲーム
"""

import pygame
import sys
import json
import math

# 初期化
pygame.init()

# 画面サイズ
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# 色定義
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
SKY_BLUE = (135, 206, 235)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
BROWN = (139, 69, 19)
GREEN = (34, 139, 34)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)
GRAY = (128, 128, 128)
BRICK_RED = (178, 34, 34)

# 画面設定
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("マリオ風アドベンチャー")
clock = pygame.time.Clock()

# フォント
font = pygame.font.Font(None, 36)
big_font = pygame.font.Font(None, 72)


class Camera:
    """カメラクラス - 画面スクロール管理"""
    def __init__(self, width):
        self.offset_x = 0
        self.width = width
        
    def update(self, target_x):
        # プレイヤーが画面中央を超えたらスクロール
        target_offset = target_x - SCREEN_WIDTH // 3
        self.offset_x = max(0, min(target_offset, self.width - SCREEN_WIDTH))
        
    def apply(self, rect):
        """座標をカメラ座標に変換"""
        return pygame.Rect(rect.x - self.offset_x, rect.y, rect.width, rect.height)


class Particle:
    """パーティクルエフェクト"""
    def __init__(self, x, y, color, velocity):
        self.x = x
        self.y = y
        self.color = color
        self.vx, self.vy = velocity
        self.life = 30
        self.size = 5
        
    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.3  # 重力
        self.life -= 1
        return self.life > 0
        
    def draw(self, screen, camera):
        pos = (int(self.x - camera.offset_x), int(self.y))
        pygame.draw.circle(screen, self.color, pos, self.size)


class Player:
    """プレイヤー（マリオ）クラス"""
    def __init__(self, x, y):
        self.width = 32
        self.height = 48
        self.x = x
        self.y = y
        self.vx = 0
        self.vy = 0
        self.speed = 5
        self.jump_power = -14
        self.gravity = 0.6
        self.on_ground = False
        self.facing_right = True
        self.invincible = 0
        self.coins = 0
        self.lives = 3
        self.anim_frame = 0
        
    def update(self, blocks, enemies, coins, powerups):
        keys = pygame.key.get_pressed()
        
        # 左右移動
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.vx = -self.speed
            self.facing_right = False
            self.anim_frame += 0.2
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.vx = self.speed
            self.facing_right = True
            self.anim_frame += 0.2
        else:
            self.vx = 0
            self.anim_frame = 0
            
        # ジャンプ
        if (keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]) and self.on_ground:
            self.vy = self.jump_power
            self.on_ground = False
            
        # 重力
        self.vy += self.gravity
        
        # 位置更新
        self.x += self.vx
        self.check_collision_x(blocks)
        
        self.y += self.vy
        self.on_ground = False
        self.check_collision_y(blocks)
        
        # 無敵時間減少
        if self.invincible > 0:
            self.invincible -= 1
            
        # 画面下に落ちたら
        if self.y > SCREEN_HEIGHT:
            self.die()
            
    def check_collision_x(self, blocks):
        """X方向の衝突判定"""
        player_rect = self.get_rect()
        for block in blocks:
            if player_rect.colliderect(block.rect):
                if self.vx > 0:
                    self.x = block.rect.left - self.width
                elif self.vx < 0:
                    self.x = block.rect.right
                self.vx = 0
                
    def check_collision_y(self, blocks):
        """Y方向の衝突判定"""
        player_rect = self.get_rect()
        for block in blocks:
            if player_rect.colliderect(block.rect):
                if self.vy > 0:
                    self.y = block.rect.top - self.height
                    self.vy = 0
                    self.on_ground = True
                elif self.vy < 0:
                    self.y = block.rect.bottom
                    self.vy = 0
                    # ブロックを叩く
                    block.hit()
                    
    def die(self):
        """死亡処理"""
        self.lives -= 1
        self.x = 100
        self.y = 300
        self.vx = 0
        self.vy = 0
        self.invincible = 120
        
    def get_rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)
        
    def draw(self, screen, camera):
        if self.invincible > 0 and self.invincible % 10 < 5:
            return  # 点滅
            
        screen_x = self.x - camera.offset_x
        
        # 体（赤い丸）
        body_color = RED
        pygame.draw.ellipse(screen, body_color, 
                          (screen_x, self.y + 15, self.width, self.height - 15))
        
        # 頭
        head_color = (255, 200, 150)
        pygame.draw.ellipse(screen, head_color,
                          (screen_x + 4, self.y, 24, 20))
        
        # 帽子
        hat_color = RED
        if self.facing_right:
            pygame.draw.ellipse(screen, hat_color,
                              (screen_x + 2, self.y - 5, 28, 15))
        else:
            pygame.draw.ellipse(screen, hat_color,
                              (screen_x + 2, self.y - 5, 28, 15))
        
        # 目
        eye_color = BLACK
        eye_x = screen_x + 20 if self.facing_right else screen_x + 8
        pygame.draw.circle(screen, eye_color, (eye_x, self.y + 10), 3)
        
        # 口ひげ
        mustache_color = BLACK
        mustache_y = self.y + 16
        if self.facing_right:
            pygame.draw.rect(screen, mustache_color,
                           (screen_x + 18, mustache_y, 10, 3))
        else:
            pygame.draw.rect(screen, mustache_color,
                           (screen_x + 4, mustache_y, 10, 3))
        
        # ボタン（青）
        pygame.draw.circle(screen, BLUE, 
                         (int(screen_x + self.width/2), self.y + 30), 4)


class Block:
    """ブロッククラス"""
    def __init__(self, x, y, block_type='brick'):
        self.rect = pygame.Rect(x, y, 40, 40)
        self.block_type = block_type  # 'brick', 'question', 'solid', 'pipe'
        self.active = True
        self.bump_offset = 0
        
    def hit(self):
        """ブロックを叩かれた時"""
        if self.block_type == 'question' and self.active:
            self.active = False
            return 'coin'
        elif self.block_type == 'brick':
            self.bump_offset = 10
        return None
        
    def update(self):
        if self.bump_offset > 0:
            self.bump_offset -= 2
            
    def draw(self, screen, camera):
        screen_rect = camera.apply(self.rect)
        screen_rect.y -= self.bump_offset
        
        if self.block_type == 'brick':
            pygame.draw.rect(screen, BRICK_RED, screen_rect)
            # レンガの模様
            pygame.draw.line(screen, BLACK, 
                           (screen_rect.left, screen_rect.centery),
                           (screen_rect.right, screen_rect.centery), 1)
            pygame.draw.line(screen, BLACK,
                           (screen_rect.centerx, screen_rect.top),
                           (screen_rect.centerx, screen_rect.bottom), 1)
                           
        elif self.block_type == 'question':
            if self.active:
                color = YELLOW
                pygame.draw.rect(screen, color, screen_rect)
                pygame.draw.rect(screen, ORANGE, screen_rect, 3)
                # ?マーク
                text = font.render("?", True, BLACK)
                text_rect = text.get_rect(center=screen_rect.center)
                screen.blit(text, text_rect)
            else:
                pygame.draw.rect(screen, BROWN, screen_rect)
                
        elif self.block_type == 'solid':
            pygame.draw.rect(screen, BROWN, screen_rect)
            pygame.draw.rect(screen, (101, 67, 33), screen_rect, 2)
            
        elif self.block_type == 'pipe':
            # 土管
            pygame.draw.rect(screen, GREEN, screen_rect)
            pygame.draw.rect(screen, (0, 100, 0), 
                           (screen_rect.x - 5, screen_rect.y, 
                            screen_rect.width + 10, 20))


class Enemy:
    """敵（クリボー）クラス"""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 32
        self.height = 32
        self.vx = -1
        self.vy = 0
        self.gravity = 0.5
        self.alive = True
        self.walk_frame = 0
        
    def update(self, blocks, player):
        if not self.alive:
            return
            
        self.vy += self.gravity
        
        # X方向の移動
        self.x += self.vx
        self_rect = self.get_rect()
        
        for block in blocks:
            if self_rect.colliderect(block.rect):
                if self.vx > 0:
                    self.x = block.rect.left - self.width
                else:
                    self.x = block.rect.right
                self.vx *= -1
                break
                
        # Y方向の移動
        old_y = self.y
        self.y += self.vy
        self_rect = self.get_rect()
        
        for block in blocks:
            if self_rect.colliderect(block.rect):
                if self.vy > 0:
                    self.y = block.rect.top - self.height
                    self.vy = 0
                break
                
        # 画面外に出たら削除
        if self.x < -100 or self.x > 3000:
            self.alive = False
            
        self.walk_frame += 0.1
        
    def get_rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)
        
    def draw(self, screen, camera):
        if not self.alive:
            return
            
        screen_x = self.x - camera.offset_x
        
        # 体（茶色の丸）
        pygame.draw.ellipse(screen, BROWN,
                          (screen_x, self.y, self.width, self.height))
        
        # 足
        foot_offset = int(abs(pygame.math.sin(self.walk_frame)) * 5)
        pygame.draw.ellipse(screen, BROWN,
                          (screen_x + 2, self.y + 25 + foot_offset, 10, 12))
        pygame.draw.ellipse(screen, BROWN,
                          (screen_x + 20, self.y + 25 - foot_offset, 10, 12))
        
        # 目（白い点）
        pygame.draw.circle(screen, WHITE, 
                         (int(screen_x + 8), self.y + 10), 4)
        pygame.draw.circle(screen, WHITE,
                         (int(screen_x + 24), self.y + 10), 4)
        
        # 眉毛（怒った表情）
        pygame.draw.line(screen, BLACK,
                        (screen_x + 4, self.y + 6),
                        (screen_x + 12, self.y + 10), 2)
        pygame.draw.line(screen, BLACK,
                        (screen_x + 28, self.y + 6),
                        (screen_x + 20, self.y + 10), 2)


class Coin:
    """コインクラス"""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 24
        self.height = 24
        self.collected = False
        self.anim_frame = 0
        
    def update(self):
        self.anim_frame += 0.2
        
    def get_rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)
        
    def draw(self, screen, camera):
        if self.collected:
            return
            
        screen_x = self.x - camera.offset_x
        
        # コインのアニメーション（左右に傾く）
        offset = int(pygame.math.sin(self.anim_frame) * 4)
        
        pygame.draw.ellipse(screen, YELLOW,
                          (screen_x + offset, self.y, 
                           self.width - offset * 2, self.height))
        pygame.draw.ellipse(screen, ORANGE,
                          (screen_x + offset + 4, self.y + 4,
                           self.width - offset * 2 - 8, self.height - 8))


class Flag:
    """ゴールの旗クラス"""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 10
        self.height = 150
        
    def get_rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)
        
    def draw(self, screen, camera):
        screen_x = self.x - camera.offset_x
        
        # ポール
        pygame.draw.rect(screen, GRAY,
                        (screen_x, self.y, self.width, self.height))
        
        # 旗
        flag_points = [
            (screen_x + self.width, self.y),
            (screen_x + self.width + 40, self.y + 20),
            (screen_x + self.width, self.y + 40)
        ]
        pygame.draw.polygon(screen, GREEN, flag_points)


def create_stage():
    """ステージの作成"""
    blocks = []
    enemies = []
    coins = []
    
    # 地面
    for i in range(0, 2000, 40):
        blocks.append(Block(i, 550, 'solid'))
        blocks.append(Block(i, 510, 'solid'))
        
    # 穴
    for i in range(600, 720, 40):
        for block in blocks[:]:
            if block.rect.x == i and block.rect.y >= 510:
                blocks.remove(block)
                
    # ブロック配置
    blocks.append(Block(300, 400, 'question'))
    blocks.append(Block(340, 400, 'brick'))
    blocks.append(Block(380, 400, 'question'))
    blocks.append(Block(420, 400, 'brick'))
    blocks.append(Block(460, 400, 'question'))
    
    blocks.append(Block(600, 300, 'brick'))
    blocks.append(Block(640, 300, 'brick'))
    blocks.append(Block(680, 300, 'brick'))
    
    blocks.append(Block(900, 400, 'question'))
    blocks.append(Block(940, 400, 'brick'))
    
    blocks.append(Block(1200, 350, 'solid'))
    blocks.append(Block(1240, 350, 'solid'))
    blocks.append(Block(1280, 350, 'solid'))
    
    blocks.append(Block(1500, 400, 'brick'))
    blocks.append(Block(1540, 400, 'question'))
    blocks.append(Block(1580, 400, 'brick'))
    
    # 土管
    blocks.append(Block(800, 470, 'pipe'))
    blocks.append(Block(1000, 430, 'pipe'))
    
    # 敵
    enemies.append(Enemy(500, 518))
    enemies.append(Enemy(800, 438))
    enemies.append(Enemy(1100, 518))
    enemies.append(Enemy(1400, 518))
    
    # コイン
    for i in range(5):
        coins.append(Coin(320 + i * 50, 350))
    coins.append(Coin(620, 250))
    coins.append(Coin(660, 250))
    coins.append(Coin(1220, 300))
    coins.append(Coin(1520, 350))
    
    # ゴール
    flag = Flag(1800, 400)
    
    return blocks, enemies, coins, flag


def draw_background(screen, camera):
    """背景の描画"""
    # 空
    screen.fill(SKY_BLUE)
    
    # 遠くの山
    for i in range(-1, 3):
        x = i * 400 - (camera.offset_x // 4) % 400
        mountain_points = [
            (x, 550),
            (x + 200, 300),
            (x + 400, 550)
        ]
        pygame.draw.polygon(screen, GREEN, mountain_points)
        
    # 雲
    for i in range(-1, 5):
        x = i * 300 - (camera.offset_x // 8) % 300
        y = 100 + (i % 2) * 50
        pygame.draw.ellipse(screen, WHITE, (x, y, 80, 40))
        pygame.draw.ellipse(screen, WHITE, (x + 20, y - 15, 50, 35))
        pygame.draw.ellipse(screen, WHITE, (x + 40, y, 60, 35))


def main():
    """メインゲームループ"""
    print("マリオ風アドベンチャーを起動します...")
    print("操作: WASD/矢印キー = 移動, スペース = ジャンプ")
    print("ゴールの旗に触れたらクリア！")
    
    player = Player(100, 400)
    blocks, enemies, coins, flag = create_stage()
    camera = Camera(2000)
    
    particles = []
    game_over = False
    win = False
    
    running = True
    while running:
        # イベント処理
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_r and (game_over or win):
                    # リセット
                    player = Player(100, 400)
                    blocks, enemies, coins, flag = create_stage()
                    camera = Camera(2000)
                    particles = []
                    game_over = False
                    win = False
                    
        if not game_over and not win:
            # 更新
            player.update(blocks, enemies, coins, None)
            camera.update(player.x)
            
            # ブロック更新
            for block in blocks:
                block.update()
                
            # 敵更新
            for enemy in enemies:
                enemy.update(blocks, player)
                
                # プレイヤーと敵の当たり判定
                if enemy.alive and player.get_rect().colliderect(enemy.get_rect()):
                    # 上から踏んだか
                    if player.vy > 0 and player.y < enemy.y:
                        enemy.alive = False
                        player.vy = -8  # バウンド
                        player.coins += 10
                        # パーティクル
                        for _ in range(4):
                            particles.append(Particle(
                                enemy.x + 16, enemy.y + 16,
                                BROWN, 
                                (random.randint(-3, 3), random.randint(-5, -2))
                            ))
                    elif player.invincible == 0:
                        player.die()
                        if player.lives <= 0:
                            game_over = True
                            
            # コイン収集
            for coin in coins:
                coin.update()
                if not coin.collected and player.get_rect().colliderect(coin.get_rect()):
                    coin.collected = True
                    player.coins += 1
                    # パーティクル
                    for _ in range(3):
                        particles.append(Particle(
                            coin.x + 12, coin.y + 12,
                            YELLOW,
                            (random.randint(-2, 2), random.randint(-4, -1))
                        ))
                        
            # ゴール判定
            if player.get_rect().colliderect(flag.get_rect()):
                win = True
                
            # パーティクル更新
            for particle in particles[:]:
                if not particle.update():
                    particles.remove(particle)
                    
        # 描画
        draw_background(screen, camera)
        
        # ブロック描画
        for block in blocks:
            if block.rect.right > camera.offset_x and block.rect.left < camera.offset_x + SCREEN_WIDTH:
                block.draw(screen, camera)
                
        # ゴール描画
        flag.draw(screen, camera)
        
        # コイン描画
        for coin in coins:
            if coin.get_rect().right > camera.offset_x and coin.get_rect().left < camera.offset_x + SCREEN_WIDTH:
                coin.draw(screen, camera)
                
        # 敵描画
        for enemy in enemies:
            if enemy.get_rect().right > camera.offset_x and enemy.get_rect().left < camera.offset_x + SCREEN_WIDTH:
                enemy.draw(screen, camera)
                
        # プレイヤー描画
        player.draw(screen, camera)
        
        # パーティクル描画
        for particle in particles:
            particle.draw(screen, camera)
            
        # UI
        # コイン数
        coin_text = font.render(f"COINS: {player.coins}", True, WHITE)
        screen.blit(coin_text, (10, 10))
        
        # ライフ
        lives_text = font.render(f"x {player.lives}", True, WHITE)
        screen.blit(lives_text, (10, 50))
        
        # 操作説明
        help_text = font.render("ARROWS/WASD: Move  SPACE: Jump", True, WHITE)
        screen.blit(help_text, (10, SCREEN_HEIGHT - 30))
        
        # ゲームオーバー
        if game_over:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            overlay.set_alpha(180)
            overlay.fill(BLACK)
            screen.blit(overlay, (0, 0))
            
            over_text = big_font.render("GAME OVER", True, RED)
            text_rect = over_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2))
            screen.blit(over_text, text_rect)
            
            restart_text = font.render("Press R to Restart", True, WHITE)
            restart_rect = restart_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 + 60))
            screen.blit(restart_text, restart_rect)
            
        # クリア
        if win:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            overlay.set_alpha(180)
            overlay.fill(BLACK)
            screen.blit(overlay, (0, 0))
            
            win_text = big_font.render("STAGE CLEAR!", True, YELLOW)
            text_rect = win_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2))
            screen.blit(win_text, text_rect)
            
            score_text = font.render(f"COINS: {player.coins}", True, WHITE)
            score_rect = score_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 + 50))
            screen.blit(score_text, score_rect)
            
            restart_text = font.render("Press R to Restart", True, WHITE)
            restart_rect = restart_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 + 90))
            screen.blit(restart_text, restart_rect)
            
        pygame.display.flip()
        clock.tick(FPS)
        
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    import random
    main()
