"""
ドンキーコング風ゲーム
Pygameで実装したシンプルなアーケードゲーム
"""

import pygame
import random
import sys

# 初期化
pygame.init()

# 画面サイズ
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("ドンキーコング風ゲーム")

# 色定義
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
BROWN = (139, 69, 19)
YELLOW = (255, 255, 0)
GREEN = (0, 255, 0)
GRAY = (128, 128, 128)

# フォント
font = pygame.font.Font(None, 36)
game_over_font = pygame.font.Font(None, 72)

# フレームレート
clock = pygame.time.Clock()
FPS = 60


class Player:
    """プレイヤー（マリオ）クラス"""
    def __init__(self):
        self.width = 30
        self.height = 40
        self.x = 50
        self.y = SCREEN_HEIGHT - 100
        self.velocity_x = 0
        self.velocity_y = 0
        self.speed = 5
        self.jump_power = -12
        self.gravity = 0.5
        self.on_ground = False
        self.on_ladder = False
        self.lives = 3
        
    def move(self, keys, platforms, ladders):
        # 左右移動
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.velocity_x = -self.speed
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.velocity_x = self.speed
        else:
            self.velocity_x = 0
            
        # ハシゴ登り
        self.on_ladder = False
        for ladder in ladders:
            if self.rect.colliderect(ladder):
                self.on_ladder = True
                self.velocity_y = 0
                if keys[pygame.K_UP] or keys[pygame.K_w]:
                    self.y -= 3
                if keys[pygame.K_DOWN] or keys[pygame.K_s]:
                    self.y += 3
                break
        
        # ジャンプ
        if (keys[pygame.K_SPACE] or keys[pygame.K_UP]) and self.on_ground:
            self.velocity_y = self.jump_power
            self.on_ground = False
            
        # 重力
        if not self.on_ladder:
            self.velocity_y += self.gravity
            
        # 位置更新
        self.x += self.velocity_x
        self.y += self.velocity_y
        
        # 画面端の制限
        self.x = max(0, min(SCREEN_WIDTH - self.width, self.x))
        
        # プラットフォームとの当たり判定
        self.on_ground = False
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
        
        for platform in platforms:
            if self.rect.colliderect(platform):
                # 上から着地
                if self.velocity_y > 0 and self.y < platform.y:
                    self.y = platform.y - self.height
                    self.velocity_y = 0
                    self.on_ground = True
                    
        # 画面下に落ちたらゲームオーバー扱い
        if self.y > SCREEN_HEIGHT:
            self.lives -= 1
            self.reset_position()
            
    def reset_position(self):
        """初期位置に戻る"""
        self.x = 50
        self.y = SCREEN_HEIGHT - 100
        self.velocity_x = 0
        self.velocity_y = 0
        
    def draw(self, screen):
        # シンプルなキャラクター表示（赤い四角）
        pygame.draw.rect(screen, RED, (self.x, self.y, self.width, self.height))
        # 帽子
        pygame.draw.rect(screen, RED, (self.x - 2, self.y - 5, self.width + 4, 5))
        # 顔
        pygame.draw.rect(screen, (255, 200, 150), (self.x + 5, self.y + 5, 20, 15))
        
    @property
    def rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)


class Barrel:
    """バレルクラス"""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.radius = 15
        self.velocity_x = random.choice([-3, 3])
        self.velocity_y = 0
        self.gravity = 0.3
        
    def update(self, platforms):
        self.velocity_y += self.gravity
        self.x += self.velocity_x
        self.y += self.velocity_y
        
        # プラットフォームとの当たり判定
        barrel_rect = pygame.Rect(self.x - self.radius, self.y - self.radius, 
                                  self.radius * 2, self.radius * 2)
        
        for platform in platforms:
            if barrel_rect.colliderect(platform):
                if self.velocity_y > 0:
                    self.y = platform.y - self.radius
                    self.velocity_y = -5  # バウンド
                    break
                    
        # 画面端で反転
        if self.x <= self.radius or self.x >= SCREEN_WIDTH - self.radius:
            self.velocity_x *= -1
            
        # 画面下に落ちたら削除対象
        return self.y < SCREEN_HEIGHT + 50
        
    def draw(self, screen):
        pygame.draw.circle(screen, BROWN, (int(self.x), int(self.y)), self.radius)
        # バレルの縞模様
        pygame.draw.line(screen, BLACK, 
                        (int(self.x - 10), int(self.y)),
                        (int(self.x + 10), int(self.y)), 2)
        pygame.draw.line(screen, BLACK,
                        (int(self.x), int(self.y - 10)),
                        (int(self.x), int(self.y + 10)), 2)
                        
    def get_rect(self):
        return pygame.Rect(self.x - self.radius, self.y - self.radius,
                          self.radius * 2, self.radius * 2)


class DonkeyKong:
    """ドンキーコングクラス"""
    def __init__(self):
        self.x = 100
        self.y = 80
        self.width = 60
        self.height = 60
        self.throw_timer = 0
        self.throw_interval = 120  # 2秒間隔
        
    def update(self):
        self.throw_timer += 1
        
    def should_throw(self):
        if self.throw_timer >= self.throw_interval:
            self.throw_timer = 0
            return True
        return False
        
    def draw(self, screen):
        # 体
        pygame.draw.rect(screen, BROWN, (self.x, self.y, self.width, self.height))
        # 頭
        pygame.draw.circle(screen, BROWN, (self.x + 30, self.y - 10), 25)
        # 目
        pygame.draw.circle(screen, WHITE, (self.x + 20, self.y - 15), 8)
        pygame.draw.circle(screen, WHITE, (self.x + 40, self.y - 15), 8)
        pygame.draw.circle(screen, BLACK, (self.x + 22, self.y - 15), 4)
        pygame.draw.circle(screen, BLACK, (self.x + 42, self.y - 15), 4)
        # ネクタイ
        pygame.draw.polygon(screen, RED, [
            (self.x + 30, self.y + 10),
            (self.x + 25, self.y + 30),
            (self.x + 30, self.y + 40),
            (self.x + 35, self.y + 30)
        ])
        # 「DK」文字
        text = font.render("DK", True, YELLOW)
        screen.blit(text, (self.x + 10, self.y + 15))
        
    def get_throw_position(self):
        return (self.x + 30, self.y + 60)


class Princess:
    """ピーチ姫クラス"""
    def __init__(self):
        self.x = SCREEN_WIDTH - 100
        self.y = 80
        self.width = 30
        self.height = 50
        
    def draw(self, screen):
        # ドレス
        pygame.draw.polygon(screen, PINK, [
            (self.x + 15, self.y),
            (self.x, self.y + 50),
            (self.x + 30, self.y + 50)
        ])
        # 頭
        pygame.draw.circle(screen, (255, 200, 150), (self.x + 15, self.y + 10), 12)
        # 髪
        pygame.draw.ellipse(screen, YELLOW, (self.x + 5, self.y - 5, 20, 15))
        
    def get_rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)


# 色の追加
PINK = (255, 192, 203)


def create_stage():
    """ステージの作成"""
    platforms = []
    ladders = []
    
    # 段々のプラットフォーム
    # 1段目（最下段）
    platforms.append(pygame.Rect(0, SCREEN_HEIGHT - 50, SCREEN_WIDTH, 20))
    # 2段目
    platforms.append(pygame.Rect(100, SCREEN_HEIGHT - 150, 600, 20))
    # 3段目
    platforms.append(pygame.Rect(50, SCREEN_HEIGHT - 250, 600, 20))
    # 4段目
    platforms.append(pygame.Rect(150, SCREEN_HEIGHT - 350, 500, 20))
    # 5段目（最上段）
    platforms.append(pygame.Rect(0, 150, SCREEN_WIDTH, 20))
    
    # ハシゴ
    ladders.append(pygame.Rect(200, SCREEN_HEIGHT - 150, 30, 100))
    ladders.append(pygame.Rect(500, SCREEN_HEIGHT - 250, 30, 100))
    ladders.append(pygame.Rect(300, SCREEN_HEIGHT - 350, 30, 100))
    ladders.append(pygame.Rect(600, SCREEN_HEIGHT - 350, 30, 200))
    
    return platforms, ladders


def draw_stage(screen, platforms, ladders):
    """ステージの描画"""
    # 背景
    screen.fill(BLACK)
    
    # プラットフォーム
    for platform in platforms:
        pygame.draw.rect(screen, BLUE, platform)
        pygame.draw.rect(screen, WHITE, platform, 2)
        
    # ハシゴ
    for ladder in ladders:
        pygame.draw.rect(screen, YELLOW, ladder)
        # ハシゴの横棒
        for i in range(ladder.top, ladder.bottom, 15):
            pygame.draw.line(screen, BROWN, 
                           (ladder.left, i), (ladder.right, i), 2)


def main():
    """メインゲームループ"""
    player = Player()
    donkey_kong = DonkeyKong()
    princess = Princess()
    barrels = []
    platforms, ladders = create_stage()
    
    score = 0
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
                    player = Player()
                    donkey_kong = DonkeyKong()
                    barrels = []
                    score = 0
                    game_over = False
                    win = False
                    
        if not game_over and not win:
            # 入力処理
            keys = pygame.key.get_pressed()
            player.move(keys, platforms, ladders)
            
            # ドンキーコングの更新
            donkey_kong.update()
            if donkey_kong.should_throw():
                x, y = donkey_kong.get_throw_position()
                barrels.append(Barrel(x, y))
                
            # バレルの更新
            for barrel in barrels[:]:
                if not barrel.update(platforms):
                    barrels.remove(barrel)
                    score += 10
                    
            # 当たり判定（プレイヤー vs バレル）
            for barrel in barrels:
                if player.rect.colliderect(barrel.get_rect()):
                    player.lives -= 1
                    player.reset_position()
                    barrels.clear()
                    if player.lives <= 0:
                        game_over = True
                    break
                    
            # クリア判定（プレイヤーがピーチ姫に到達）
            if player.rect.colliderect(princess.get_rect()):
                win = True
                
        # 描画
        draw_stage(screen, platforms, ladders)
        
        # キャラクター描画
        donkey_kong.draw(screen)
        princess.draw(screen)
        player.draw(screen)
        
        for barrel in barrels:
            barrel.draw(screen)
            
        # UI表示
        lives_text = font.render(f"LIVES: {player.lives}", True, WHITE)
        screen.blit(lives_text, (10, 10))
        
        score_text = font.render(f"SCORE: {score}", True, WHITE)
        screen.blit(score_text, (SCREEN_WIDTH - 150, 10))
        
        # ゲームオーバー表示
        if game_over:
            game_over_text = game_over_font.render("GAME OVER", True, RED)
            text_rect = game_over_text.get_rect(center=(SCREEN_WIDTH/2, SCREEN_HEIGHT/2))
            screen.blit(game_over_text, text_rect)
            
            restart_text = font.render("Press R to Restart", True, WHITE)
            restart_rect = restart_text.get_rect(center=(SCREEN_WIDTH/2, SCREEN_HEIGHT/2 + 50))
            screen.blit(restart_text, restart_rect)
            
        # クリア表示
        if win:
            win_text = game_over_font.render("YOU WIN!", True, GREEN)
            text_rect = win_text.get_rect(center=(SCREEN_WIDTH/2, SCREEN_HEIGHT/2))
            screen.blit(win_text, text_rect)
            
            restart_text = font.render("Press R to Restart", True, WHITE)
            restart_rect = restart_text.get_rect(center=(SCREEN_WIDTH/2, SCREEN_HEIGHT/2 + 50))
            screen.blit(restart_text, restart_rect)
            
        # 操作説明
        help_text = font.render("ARROWS/WASD: Move/Climb  SPACE: Jump", True, GRAY)
        screen.blit(help_text, (10, SCREEN_HEIGHT - 30))
        
        pygame.display.flip()
        clock.tick(FPS)
        
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    print("ドンキーコング風ゲームを起動します...")
    print("操作: 矢印キー/WASD = 移動/ハシゴ登り, スペース = ジャンプ")
    print("ESC = 終了, R = リスタート")
    main()
