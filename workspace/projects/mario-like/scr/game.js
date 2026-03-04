/*
  mario-like (オリジナル)
  - Canvas 2D
  - タイルベース（32px）
  - 簡易物理 + 1ステージ

  ルール
  - コイン取得でスコア
  - 敵に横から当たるとダメージ、上から踏むと撃破
  - 旗に触れるとクリア
*/

(() => {
  'use strict';

  const canvas = document.getElementById('game');
  const ctx = canvas.getContext('2d');
  const hud = document.getElementById('hud');

  // --- Config ---
  const TILE = 32;
  const GRAVITY = 2200;      // px/s^2
  const MOVE_ACC = 5200;     // px/s^2
  const MOVE_MAX = 340;      // px/s
  const FRICTION = 4200;     // px/s^2
  const JUMP_V = 760;        // px/s
  const COYOTE_TIME = 0.10;  // seconds
  const JUMP_BUFFER = 0.10;  // seconds

  const VIEW_W = canvas.width;
  const VIEW_H = canvas.height;

  // Tile legend:
  //  # = solid
  //  . = empty
  //  o = coin
  //  e = enemy spawn
  //  f = flag/goal
  //  p = player spawn
  const LEVEL = [
    '........................................................................',
    '........................................................................',
    '........................................................................',
    '........................................................................',
    '........................................................................',
    '........................................................................',
    '..................o.....o...............................................',
    '..............#####...............o..............o......................',
    '..................................####..................................',
    '...........o......................................................f.....',
    '........#########......................o..............#####..............',
    '.....................................#####..............................',
    '.....p....................e.............................................',
    '####################..#############..###############################..###',
  ];

  // --- Helpers ---
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  function rectsOverlap(a, b) {
    return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
  }

  // Swept AABB-ish resolution: move separately in X and Y with tile collisions.
  function moveWithCollisions(entity, dt, world) {
    entity.onGround = false;

    // X
    entity.x += entity.vx * dt;
    let hitX = world.collideEntity(entity);
    if (hitX) {
      // push out
      entity.x = hitX.fixX;
      entity.vx = 0;
    }

    // Y
    entity.y += entity.vy * dt;
    let hitY = world.collideEntity(entity);
    if (hitY) {
      entity.y = hitY.fixY;
      if (hitY.fromAbove) {
        entity.onGround = true;
      }
      entity.vy = 0;
    }
  }

  // --- Input ---
  const keys = new Set();
  window.addEventListener('keydown', (e) => {
    if (['ArrowLeft','ArrowRight','ArrowUp','Space','KeyR'].includes(e.code)) e.preventDefault();
    keys.add(e.code);
  }, { passive: false });
  window.addEventListener('keyup', (e) => {
    keys.delete(e.code);
  });

  function isDown(code) { return keys.has(code); }

  // --- World parsing ---
  function buildWorld(levelLines) {
    const h = levelLines.length;
    const w = levelLines[0].length;

    const solids = new Set();
    const coins = [];
    const enemies = [];
    let flag = null;
    let spawn = { x: 2*TILE, y: 2*TILE };

    for (let y = 0; y < h; y++) {
      const line = levelLines[y];
      for (let x = 0; x < w; x++) {
        const c = line[x];
        const key = `${x},${y}`;
        if (c === '#') solids.add(key);
        if (c === 'o') coins.push({ x: x*TILE + 10, y: y*TILE + 10, w: 12, h: 12, taken: false });
        if (c === 'e') enemies.push(makeEnemy(x*TILE + 4, y*TILE + 6));
        if (c === 'f') flag = { x: x*TILE + 10, y: y*TILE - 64, w: 16, h: 96 };
        if (c === 'p') spawn = { x: x*TILE + 6, y: y*TILE - 20 };
      }
    }

    const world = {
      wTiles: w,
      hTiles: h,
      wPx: w*TILE,
      hPx: h*TILE,
      solids,
      coins,
      enemies,
      flag,
      spawn,

      tileAt(tx, ty) {
        if (tx < 0 || ty < 0 || tx >= w || ty >= h) return '#'; // out = solid
        return solids.has(`${tx},${ty}`) ? '#' : '.';
      },

      collideEntity(ent) {
        // Find nearby tile range
        const left = Math.floor(ent.x / TILE);
        const right = Math.floor((ent.x + ent.w) / TILE);
        const top = Math.floor(ent.y / TILE);
        const bottom = Math.floor((ent.y + ent.h) / TILE);

        for (let ty = top; ty <= bottom; ty++) {
          for (let tx = left; tx <= right; tx++) {
            if (this.tileAt(tx, ty) !== '#') continue;
            const tileRect = { x: tx*TILE, y: ty*TILE, w: TILE, h: TILE };
            if (!rectsOverlap(ent, tileRect)) continue;

            // Determine minimal separation axis based on previous motion direction.
            // We resolve by looking at penetration depth on both axes.
            const dx1 = (tileRect.x + tileRect.w) - ent.x;        // tile right - ent left
            const dx2 = (ent.x + ent.w) - tileRect.x;             // ent right - tile left
            const dy1 = (tileRect.y + tileRect.h) - ent.y;        // tile bottom - ent top
            const dy2 = (ent.y + ent.h) - tileRect.y;             // ent bottom - tile top
            const penX = Math.min(dx1, dx2);
            const penY = Math.min(dy1, dy2);

            if (penX < penY) {
              // resolve X
              if (dx1 < dx2) {
                // tile is left of entity -> push entity right
                return { fixX: tileRect.x + tileRect.w, fixY: ent.y, fromAbove: false };
              } else {
                // tile is right -> push entity left
                return { fixX: tileRect.x - ent.w, fixY: ent.y, fromAbove: false };
              }
            } else {
              // resolve Y
              if (dy1 < dy2) {
                // tile is above entity? Actually tile bottom closer to ent top -> push ent down
                return { fixX: ent.x, fixY: tileRect.y + tileRect.h, fromAbove: false };
              } else {
                // push ent up (standing on tile)
                return { fixX: ent.x, fixY: tileRect.y - ent.h, fromAbove: true };
              }
            }
          }
        }
        return null;
      }
    };

    return world;
  }

  // --- Entities ---
  function makePlayer(spawn) {
    return {
      x: spawn.x,
      y: spawn.y,
      w: 22,
      h: 28,
      vx: 0,
      vy: 0,
      onGround: false,
      facing: 1,
      coyote: 0,
      jumpBuf: 0,
      invuln: 0,
      lives: 3,
      score: 0,
      cleared: false,
      dead: false,
    };
  }

  function makeEnemy(x, y) {
    return {
      x, y,
      w: 24,
      h: 18,
      vx: -80,
      vy: 0,
      onGround: false,
      alive: true,
    };
  }

  // --- Game state ---
  let world = buildWorld(LEVEL);
  let player = makePlayer(world.spawn);
  let cameraX = 0;
  let msg = '';

  function restart() {
    world = buildWorld(LEVEL);
    player = makePlayer(world.spawn);
    cameraX = 0;
    msg = '';
  }

  // --- Update ---
  function update(dt) {
    if (isDown('KeyR')) {
      restart();
      return;
    }

    if (player.cleared || player.dead) {
      // allow small idle
      if (player.invuln > 0) player.invuln -= dt;
      return;
    }

    // Timers
    player.invuln = Math.max(0, player.invuln - dt);
    player.coyote = Math.max(0, player.coyote - dt);
    player.jumpBuf = Math.max(0, player.jumpBuf - dt);

    // Input -> horizontal acceleration
    const left = isDown('ArrowLeft');
    const right = isDown('ArrowRight');
    const jumpPressed = isDown('Space') || isDown('ArrowUp');

    if (left && !right) {
      player.vx -= MOVE_ACC * dt;
      player.facing = -1;
    } else if (right && !left) {
      player.vx += MOVE_ACC * dt;
      player.facing = 1;
    } else {
      // friction
      if (player.vx > 0) player.vx = Math.max(0, player.vx - FRICTION * dt);
      if (player.vx < 0) player.vx = Math.min(0, player.vx + FRICTION * dt);
    }
    player.vx = clamp(player.vx, -MOVE_MAX, MOVE_MAX);

    // Jump buffer
    if (jumpPressed) {
      player.jumpBuf = JUMP_BUFFER;
    }

    // Gravity
    player.vy += GRAVITY * dt;

    // Move with collisions
    const wasOnGround = player.onGround;
    moveWithCollisions(player, dt, world);

    if (player.onGround) {
      player.coyote = COYOTE_TIME;
    } else if (wasOnGround && !player.onGround) {
      // just left ground
      // keep coyote from the previous set
    }

    // Execute jump if buffered and allowed
    if (player.jumpBuf > 0 && player.coyote > 0) {
      player.vy = -JUMP_V;
      player.onGround = false;
      player.coyote = 0;
      player.jumpBuf = 0;
    }

    // If fell out of world
    if (player.y > world.hPx + 300) {
      takeDamage(true);
    }

    // Collect coins
    for (const coin of world.coins) {
      if (coin.taken) continue;
      if (rectsOverlap(player, coin)) {
        coin.taken = true;
        player.score += 10;
      }
    }

    // Enemies update
    for (const e of world.enemies) {
      if (!e.alive) continue;
      e.vy += GRAVITY * dt;
      // simple AI: walk; turn around if hits wall or about to fall
      // predict next X
      const next = { ...e, x: e.x + e.vx * dt, y: e.y, onGround: false };
      // move X and resolve
      next.x = e.x + e.vx * dt;
      const hitX = world.collideEntity(next);
      if (hitX) {
        e.vx *= -1;
      }

      // ledge detect: sample tile ahead under feet
      const aheadX = e.vx < 0 ? (e.x - 2) : (e.x + e.w + 2);
      const footY = e.y + e.h + 2;
      const tx = Math.floor(aheadX / TILE);
      const ty = Math.floor(footY / TILE);
      if (world.tileAt(tx, ty) !== '#') {
        // if on ground, turn
        // (avoid jitter if airborne)
        // We'll approximate: if close to ground
        //
        // keep a small threshold: if entity bottom is near tile grid
        if (Math.abs((e.y + e.h) % TILE) < 6) {
          e.vx *= -1;
        }
      }

      moveWithCollisions(e, dt, world);

      // Collision with player
      if (e.alive && rectsOverlap(player, e)) {
        const playerBottomPrev = player.y + player.h - player.vy * dt;
        const enemyTop = e.y;
        const comingFromAbove = playerBottomPrev <= enemyTop + 6 && player.vy > 0;

        if (comingFromAbove) {
          e.alive = false;
          player.vy = -520; // bounce
          player.score += 50;
        } else {
          if (player.invuln <= 0) {
            takeDamage(false);
          }
        }
      }
    }

    // Goal
    if (world.flag && rectsOverlap(player, world.flag)) {
      player.cleared = true;
      msg = 'CLEAR! (Rでリスタート)';
    }

    // Camera follow
    const target = player.x + player.w/2 - VIEW_W/2;
    cameraX = clamp(target, 0, Math.max(0, world.wPx - VIEW_W));
  }

  function takeDamage(fell) {
    player.lives -= 1;
    player.invuln = 1.0;
    player.vx = 0;
    player.vy = 0;

    if (player.lives <= 0) {
      player.dead = true;
      msg = 'GAME OVER (Rでリスタート)';
      return;
    }

    // respawn
    player.x = world.spawn.x;
    player.y = world.spawn.y;

    if (fell) {
      // small penalty
      player.score = Math.max(0, player.score - 20);
    }
  }

  // --- Render ---
  function draw() {
    ctx.clearRect(0, 0, VIEW_W, VIEW_H);

    // Background clouds (parallax)
    drawClouds();

    ctx.save();
    ctx.translate(-cameraX, 0);

    // Ground tiles
    drawTiles();

    // Coins
    for (const coin of world.coins) {
      if (coin.taken) continue;
      ctx.fillStyle = '#ffdd55';
      ctx.beginPath();
      ctx.roundRect(coin.x, coin.y, coin.w, coin.h, 4);
      ctx.fill();
      ctx.strokeStyle = '#b8860b';
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    // Flag
    if (world.flag) {
      const f = world.flag;
      // pole
      ctx.fillStyle = '#dfe6f6';
      ctx.fillRect(f.x + 6, f.y, 4, f.h);
      // flag cloth
      ctx.fillStyle = '#ff4d4d';
      ctx.beginPath();
      ctx.moveTo(f.x + 10, f.y + 8);
      ctx.lineTo(f.x + 44, f.y + 18);
      ctx.lineTo(f.x + 10, f.y + 28);
      ctx.closePath();
      ctx.fill();
      // base
      ctx.fillStyle = '#6b4b2a';
      ctx.fillRect(f.x - 8, f.y + f.h - 8, 32, 8);
    }

    // Enemies
    for (const e of world.enemies) {
      if (!e.alive) continue;
      // slime body
      ctx.fillStyle = '#7b5cff';
      ctx.beginPath();
      ctx.roundRect(e.x, e.y, e.w, e.h, 8);
      ctx.fill();
      // eyes
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(e.x + 8, e.y + 7, 3, 0, Math.PI*2);
      ctx.arc(e.x + 16, e.y + 7, 3, 0, Math.PI*2);
      ctx.fill();
      ctx.fillStyle = '#111827';
      ctx.beginPath();
      ctx.arc(e.x + 8, e.y + 7, 1.6, 0, Math.PI*2);
      ctx.arc(e.x + 16, e.y + 7, 1.6, 0, Math.PI*2);
      ctx.fill();
    }

    // Player
    drawPlayer();

    ctx.restore();

    // HUD
    const coinsTaken = world.coins.filter(c => c.taken).length;
    hud.textContent = `SCORE: ${player.score}   COINS: ${coinsTaken}/${world.coins.length}   LIVES: ${player.lives}   ${msg}`;

    if (player.invuln > 0 && !player.dead && !player.cleared) {
      ctx.fillStyle = 'rgba(255,255,255,0.12)';
      ctx.fillRect(0, 0, VIEW_W, VIEW_H);
    }

    if (player.dead || player.cleared) {
      ctx.fillStyle = 'rgba(0,0,0,0.35)';
      ctx.fillRect(0, 0, VIEW_W, VIEW_H);
      ctx.fillStyle = '#ffffff';
      ctx.font = '700 42px system-ui';
      ctx.textAlign = 'center';
      ctx.fillText(player.dead ? 'GAME OVER' : 'CLEAR!', VIEW_W/2, VIEW_H/2 - 10);
      ctx.font = '16px system-ui';
      ctx.fillText('R キーでリスタート', VIEW_W/2, VIEW_H/2 + 26);
      ctx.textAlign = 'start';
    }
  }

  function drawTiles() {
    const startTx = Math.floor(cameraX / TILE) - 1;
    const endTx = Math.floor((cameraX + VIEW_W) / TILE) + 1;

    for (let ty = 0; ty < world.hTiles; ty++) {
      for (let tx = startTx; tx <= endTx; tx++) {
        if (world.tileAt(tx, ty) !== '#') continue;
        const x = tx*TILE;
        const y = ty*TILE;

        // Dirt block with simple shading
        ctx.fillStyle = '#8b5a2b';
        ctx.fillRect(x, y, TILE, TILE);
        ctx.fillStyle = '#7a4d25';
        ctx.fillRect(x, y + TILE*0.55, TILE, TILE*0.45);
        ctx.strokeStyle = 'rgba(0,0,0,0.25)';
        ctx.lineWidth = 2;
        ctx.strokeRect(x+1, y+1, TILE-2, TILE-2);
      }
    }
  }

  function drawPlayer() {
    // blink if invuln
    if (player.invuln > 0 && Math.floor(player.invuln * 20) % 2 === 0) return;

    // body
    ctx.fillStyle = '#ffb000';
    ctx.beginPath();
    ctx.roundRect(player.x, player.y, player.w, player.h, 8);
    ctx.fill();

    // cap
    ctx.fillStyle = '#ff3b3b';
    ctx.beginPath();
    ctx.roundRect(player.x - 2, player.y - 2, player.w + 4, 10, 6);
    ctx.fill();

    // face direction marker
    ctx.fillStyle = 'rgba(0,0,0,0.25)';
    if (player.facing > 0) {
      ctx.fillRect(player.x + player.w - 6, player.y + 12, 4, 10);
    } else {
      ctx.fillRect(player.x + 2, player.y + 12, 4, 10);
    }
  }

  function drawClouds() {
    const t = performance.now() / 1000;
    ctx.save();
    ctx.globalAlpha = 0.25;
    ctx.fillStyle = '#ffffff';

    const clouds = [
      { x: (t*18) % (VIEW_W+200) - 200, y: 60, s: 1.2 },
      { x: (t*12) % (VIEW_W+240) - 240, y: 110, s: 0.9 },
      { x: (t*9) % (VIEW_W+320) - 320, y: 40, s: 1.6 },
    ];
    for (const c of clouds) {
      const x = c.x, y = c.y, s = c.s;
      ctx.beginPath();
      ctx.arc(x + 30*s, y + 12*s, 14*s, 0, Math.PI*2);
      ctx.arc(x + 50*s, y + 10*s, 18*s, 0, Math.PI*2);
      ctx.arc(x + 70*s, y + 14*s, 14*s, 0, Math.PI*2);
      ctx.arc(x + 50*s, y + 22*s, 16*s, 0, Math.PI*2);
      ctx.fill();
    }
    ctx.restore();
  }

  // --- Main loop ---
  let last = performance.now();
  function frame(now) {
    const dt = clamp((now - last) / 1000, 0, 1/20); // avoid huge steps
    last = now;

    update(dt);
    draw();

    requestAnimationFrame(frame);
  }

  // Polyfill for roundRect on older browsers
  if (!CanvasRenderingContext2D.prototype.roundRect) {
    CanvasRenderingContext2D.prototype.roundRect = function(x, y, w, h, r) {
      r = Math.min(r, w/2, h/2);
      this.beginPath();
      this.moveTo(x+r, y);
      this.arcTo(x+w, y, x+w, y+h, r);
      this.arcTo(x+w, y+h, x, y+h, r);
      this.arcTo(x, y+h, x, y, r);
      this.arcTo(x, y, x+w, y, r);
      this.closePath();
      return this;
    };
  }

  restart();
  requestAnimationFrame(frame);
})();
