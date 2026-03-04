import random
import sys
from collections import deque

import pygame

# ----------------------
# Config
# ----------------------
W, H = 6, 12
CELL = 40
MARGIN = 20
PANEL_W = 220
FPS = 60

DROP_INTERVAL_MS = 550
SOFT_DROP_INTERVAL_MS = 35
LOCK_DELAY_MS = 220

COLORS = {
    0: (0, 0, 0),
    1: (220, 80, 80),   # red
    2: (80, 190, 80),   # green
    3: (80, 120, 220),  # blue
    4: (220, 200, 80),  # yellow
    5: (180, 80, 200),  # purple
}
PUYO_TYPES = [1, 2, 3, 4, 5]

BG = (18, 18, 22)
GRID = (55, 55, 68)
TEXT = (235, 235, 245)

SCREEN_W = MARGIN * 2 + W * CELL + PANEL_W
SCREEN_H = MARGIN * 2 + H * CELL

# ----------------------
# Helpers
# ----------------------

def clamp(x, a, b):
    return max(a, min(b, x))


def new_grid():
    return [[0 for _ in range(W)] for _ in range(H)]


def inside(x, y):
    return 0 <= x < W and 0 <= y < H


# ----------------------
# Puyo Pair
# ----------------------
# orientation: 0=up, 1=right, 2=down, 3=left (relative to pivot)
# pivot at (x,y), child at pivot + offset
OFFSETS = {
    0: (0, -1),
    1: (1, 0),
    2: (0, 1),
    3: (-1, 0),
}


class Pair:
    def __init__(self, x, y, a, b, ori=0):
        self.x = x
        self.y = y
        self.a = a  # pivot color
        self.b = b  # child color
        self.ori = ori

    def cells(self):
        ox, oy = OFFSETS[self.ori]
        return [(self.x, self.y, self.a), (self.x + ox, self.y + oy, self.b)]

    def moved(self, dx, dy):
        return Pair(self.x + dx, self.y + dy, self.a, self.b, self.ori)

    def rotated(self, dori):
        return Pair(self.x, self.y, self.a, self.b, (self.ori + dori) % 4)


# ----------------------
# Game
# ----------------------

class Game:
    def __init__(self):
        self.reset()

    def reset(self):
        self.grid = new_grid()
        self.next_queue = deque()
        for _ in range(3):
            self.next_queue.append(self._random_pair_colors())
        self.cur = None
        self.game_over = False

        self.score = 0
        self.chain = 0

        self._spawn()
        self.drop_timer = 0
        self.lock_timer = 0
        self.soft_drop = False

    def _random_pair_colors(self):
        return (random.choice(PUYO_TYPES), random.choice(PUYO_TYPES))

    def _spawn(self):
        a, b = self.next_queue.popleft()
        self.next_queue.append(self._random_pair_colors())

        # Spawn near top center. y=1 so that child (ori=0) at y=0.
        self.cur = Pair(W // 2, 1, a, b, ori=0)
        if not self._valid(self.cur):
            self.game_over = True

    def _valid(self, pair: Pair):
        for x, y, c in pair.cells():
            if not inside(x, y):
                return False
            if self.grid[y][x] != 0:
                return False
        return True

    def _try_move(self, dx, dy):
        if self.game_over:
            return False
        nxt = self.cur.moved(dx, dy)
        if self._valid(nxt):
            self.cur = nxt
            return True
        return False

    def _try_rotate(self, dori):
        if self.game_over:
            return False
        # Basic rotation + simple wall kicks
        cand = []
        r = self.cur.rotated(dori)
        cand.append(r)
        cand.append(r.moved(1, 0))
        cand.append(r.moved(-1, 0))
        cand.append(r.moved(0, -1))
        cand.append(r.moved(0, 1))
        for p in cand:
            if self._valid(p):
                self.cur = p
                return True
        return False

    def hard_drop(self):
        if self.game_over:
            return
        moved = 0
        while self._try_move(0, 1):
            moved += 1
        # lock immediately
        self._lock()

    def _lock(self):
        # Place puyos
        for x, y, c in self.cur.cells():
            if inside(x, y):
                self.grid[y][x] = c
        # Resolve chains
        self._resolve()
        if not self.game_over:
            self._spawn()
        self.lock_timer = 0

    def _resolve(self):
        self.chain = 0
        while True:
            groups = self._find_pop_groups(min_size=4)
            if not groups:
                break
            self.chain += 1
            popped = 0
            for cells in groups:
                for x, y in cells:
                    self.grid[y][x] = 0
                    popped += 1
            self.score += popped * 10 * self.chain
            self._apply_gravity()

    def _apply_gravity(self):
        for x in range(W):
            write_y = H - 1
            for y in range(H - 1, -1, -1):
                if self.grid[y][x] != 0:
                    if y != write_y:
                        self.grid[write_y][x] = self.grid[y][x]
                        self.grid[y][x] = 0
                    write_y -= 1

    def _find_pop_groups(self, min_size=4):
        visited = [[False for _ in range(W)] for _ in range(H)]
        groups = []
        for y in range(H):
            for x in range(W):
                c = self.grid[y][x]
                if c == 0 or visited[y][x]:
                    continue
                q = deque([(x, y)])
                visited[y][x] = True
                comp = [(x, y)]
                while q:
                    cx, cy = q.popleft()
                    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                        nx, ny = cx + dx, cy + dy
                        if inside(nx, ny) and not visited[ny][nx] and self.grid[ny][nx] == c:
                            visited[ny][nx] = True
                            q.append((nx, ny))
                            comp.append((nx, ny))
                if len(comp) >= min_size:
                    groups.append(comp)
        return groups

    def update(self, dt_ms):
        if self.game_over:
            return

        self.drop_timer += dt_ms

        interval = SOFT_DROP_INTERVAL_MS if self.soft_drop else DROP_INTERVAL_MS
        moved_down = False
        while self.drop_timer >= interval:
            self.drop_timer -= interval
            if self._try_move(0, 1):
                moved_down = True
                self.lock_timer = 0
            else:
                # can't move down, start lock delay
                pass

        if moved_down:
            return

        # If touching ground, count lock delay
        if not self._valid(self.cur.moved(0, 1)):
            self.lock_timer += dt_ms
            if self.lock_timer >= LOCK_DELAY_MS:
                self._lock()


# ----------------------
# Rendering
# ----------------------

def draw_cell(surf, x, y, color, alpha=255):
    r = pygame.Rect(MARGIN + x * CELL, MARGIN + y * CELL, CELL, CELL)
    # background cell
    pygame.draw.rect(surf, GRID, r, 1)
    if color == 0:
        return

    fill = (*COLORS[color], alpha)
    puyo = pygame.Surface((CELL, CELL), pygame.SRCALPHA)

    # body
    pygame.draw.ellipse(puyo, fill, (4, 4, CELL - 8, CELL - 8))
    # highlight
    pygame.draw.ellipse(puyo, (255, 255, 255, int(alpha * 0.25)), (10, 8, CELL * 0.35, CELL * 0.28))
    # outline
    pygame.draw.ellipse(puyo, (0, 0, 0, int(alpha * 0.35)), (4, 4, CELL - 8, CELL - 8), 2)

    surf.blit(puyo, r.topleft)


def draw_panel(surf, font, game: Game):
    ox = MARGIN + W * CELL + 20
    oy = MARGIN

    def text(line, y, size=22, bold=False):
        f = pygame.font.SysFont(None, size, bold=bold)
        s = f.render(line, True, TEXT)
        surf.blit(s, (ox, oy + y))

    text("NEXT", 0, size=26, bold=True)
    # Draw next 2 pairs
    for i, (a, b) in enumerate(list(game.next_queue)[:2]):
        base_y = 40 + i * 90
        # mini 2-stack
        for j, c in enumerate([a, b]):
            mini = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
            pygame.draw.ellipse(mini, (*COLORS[c], 255), (6, 6, CELL - 12, CELL - 12))
            pygame.draw.ellipse(mini, (0, 0, 0, 90), (6, 6, CELL - 12, CELL - 12), 2)
            surf.blit(mini, (ox, oy + base_y + j * (CELL - 6)))

    text(f"SCORE: {game.score}", 240, size=24, bold=True)
    text(f"CHAIN: {game.chain}", 270, size=22)
    if game.game_over:
        text("GAME OVER", 330, size=32, bold=True)
        text("Press R", 365, size=22)


def main():
    pygame.init()
    pygame.display.set_caption("PuyoPuyo (minimal) - pygame")
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock = pygame.time.Clock()

    font = pygame.font.SysFont(None, 24)

    game = Game()

    running = True
    while running:
        dt = clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_r:
                    game.reset()
                if game.game_over:
                    continue

                if event.key == pygame.K_LEFT:
                    game._try_move(-1, 0)
                elif event.key == pygame.K_RIGHT:
                    game._try_move(1, 0)
                elif event.key == pygame.K_DOWN:
                    game.soft_drop = True
                elif event.key == pygame.K_z:
                    game._try_rotate(-1)
                elif event.key == pygame.K_x:
                    game._try_rotate(1)
                elif event.key == pygame.K_SPACE:
                    game.hard_drop()

            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_DOWN:
                    game.soft_drop = False

        # continuous move (optional): handle held keys slightly
        keys = pygame.key.get_pressed()
        if not game.game_over:
            if keys[pygame.K_LEFT]:
                # small repeat
                pass

        game.update(dt)

        # Draw
        screen.fill(BG)
        # board
        for y in range(H):
            for x in range(W):
                draw_cell(screen, x, y, game.grid[y][x])

        # current falling
        if not game.game_over and game.cur is not None:
            for x, y, c in game.cur.cells():
                if inside(x, y):
                    draw_cell(screen, x, y, c)

        # border around playfield
        pf = pygame.Rect(MARGIN, MARGIN, W * CELL, H * CELL)
        pygame.draw.rect(screen, (120, 120, 140), pf, 2)

        draw_panel(screen, font, game)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
