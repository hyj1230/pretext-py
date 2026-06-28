import pygame
import math
import random
import sys
import numpy as np
from functools import lru_cache
from pretext_py.layout import prepareWithSegments, layoutWithLines
from pretext_py.measurement import getMeasureContext
from pretext_py.intl_segmenter_py import String

# ---------- 配置 ----------
cfg = {
    'dragonSegments': 60,
    'dragonSpeed': 0.18,
    'dragonScale': 1.0,
    'showWings': True,
    'showSpines': True,
    'pushForce': 6,
    'springStrength': 0.015,
    'damping': 0.93,
    'burnGravity': 0.8,
    'fireRadius': 120,
    'fireForce': 25,
    'screenShake': True,
    'showEmbers': True,
    'showParticles': True,
    'showRunes': True,
    'showCursor': True,
    'textOpacity': 1.0,
    'showEnemies': True,
    'enemyCount': 8,
    'enemySpeed': 0.6,
}

PRESETS = {
    'Default': {},
    'Gentle': {'dragonSpeed': 0.10, 'pushForce': 5, 'fireForce': 10, 'fireRadius': 60, 'screenShake': False, 'burnGravity': 0.2, 'springStrength': 0.03},
    'Chaos': {'pushForce': 25, 'fireForce': 50, 'fireRadius': 200, 'burnGravity': 2.5, 'springStrength': 0.005, 'damping': 0.96, 'screenShake': True},
    'Zen': {'showParticles': False, 'showEmbers': False, 'screenShake': False, 'showRunes': False, 'pushForce': 4, 'fireForce': 8, 'springStrength': 0.04, 'burnGravity': 0},
    'Tiny': {'dragonSegments': 20, 'dragonScale': 0.6, 'fireRadius': 50, 'pushForce': 6},
    'Leviathan': {'dragonSegments': 80, 'dragonScale': 2.0, 'dragonSpeed': 0.08, 'pushForce': 20, 'fireRadius': 180},
}

DEFAULT_CFG = cfg.copy()

def apply_preset(name):
    """应用预设配置并重建龙"""
    global cfg  # pylint:disable=W0603
    cfg = {**DEFAULT_CFG, **PRESETS[name]}
    rebuildDragon()

# ---------- Pygame 初始化 ----------
pygame.init()
info = pygame.display.Info()
W, H = info.current_w, info.current_h - 44  # 留出任务栏高度（近似）
screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
clock = pygame.time.Clock()

ctx = getMeasureContext()
registry = ctx.registry
registry.register('monospace', './CHSansSC.ttf')

InterFont = pygame.font.Font('./Inter.ttf', 14)

# ---------- 鼠标状态 ----------
mouse_x, mouse_y = W//2, H//2

# ---------- 屏幕抖动 ----------
shakeIntensity = shakeX = shakeY = 0

def triggerShake(intensity):
    global shakeIntensity  # pylint:disable=W0603
    if not cfg['screenShake']:
        return
    shakeIntensity = max(shakeIntensity, min(intensity, 8))

def updateShake():
    global shakeIntensity, shakeX, shakeY  # pylint:disable=W0603
    if shakeIntensity > 0.1:
        shakeX = (random.random() - 0.5) * shakeIntensity
        shakeY = (random.random() - 0.5) * shakeIntensity
        shakeIntensity *= 0.85
    else:
        shakeIntensity = shakeX = shakeY = 0


# ─── 字母 (SoA — 数组结构可提高缓存/内存效率) ─

# Instead of an array of objects, use parallel typed arrays.
# This eliminates per-letter object overhead and GC pressure.
MAX_LETTERS = 2000
letterCount = 0

# Per-letter data in typed arrays (no object allocation per letter)
lHomeX = np.zeros(MAX_LETTERS, dtype=np.float32)
lHomeY = np.zeros(MAX_LETTERS, dtype=np.float32)
lX = np.zeros(MAX_LETTERS, dtype=np.float32)
lY = np.zeros(MAX_LETTERS, dtype=np.float32)
lVx = np.zeros(MAX_LETTERS, dtype=np.float32)
lVy = np.zeros(MAX_LETTERS, dtype=np.float32)
lAngle = np.zeros(MAX_LETTERS, dtype=np.float32)
lAngVel = np.zeros(MAX_LETTERS, dtype=np.float32)
lCharW = np.zeros(MAX_LETTERS, dtype=np.float32)
lBaseAlpha = np.zeros(MAX_LETTERS, dtype=np.float32)
lFontSize = np.zeros(MAX_LETTERS, dtype=np.float32)
lBurnTimer = np.zeros(MAX_LETTERS, dtype=np.float32)
lScaleMul = np.zeros(MAX_LETTERS, dtype=np.float32)
lGravity = np.zeros(MAX_LETTERS, dtype=np.float32)

# These can't be typed arrays (strings) — but we intern them to avoid duplication
lChar = [None] * MAX_LETTERS
lFont = [None] * MAX_LETTERS  # index into fontPool
lColor = np.zeros((MAX_LETTERS, 3), dtype=np.uint8)  # index into colorPool

# ─── Embers + Particles — pooled with fixed max ────────────
MAX_EMBERS = 60
emberCount = 0
emX = np.zeros(MAX_EMBERS, dtype=np.float32)
emY = np.zeros(MAX_EMBERS, dtype=np.float32)
emVx = np.zeros(MAX_EMBERS, dtype=np.float32)
emVy = np.zeros(MAX_EMBERS, dtype=np.float32)
emLife = np.zeros(MAX_EMBERS, dtype=np.float32)
emSize = np.zeros(MAX_EMBERS, dtype=np.float32)
emCharIndex = np.zeros(MAX_EMBERS, dtype=np.uint8)
emColorIndex = np.zeros(MAX_EMBERS, dtype=np.uint8)
emberChars = ['·', '•', '∘', '˚']
emberColors = [(0xff, 0x66, 0), (0xff, 0xaa, 0), (0xff, 0x44, 0)]

def spawnEmber(x, y):
    global emberCount  # pylint:disable=W0603
    if not cfg['showEmbers'] or emberCount >= MAX_EMBERS: return
    i = emberCount
    emberCount += 1
    a = random.random() * math.pi * 2
    emX[i], emY[i] = x, y
    emVx[i] = math.cos(a) * (1 + random.random() * 3)
    emVy[i] = math.sin(a) * (1 + random.random() * 3) - 2
    emLife[i] = 0.3 + random.random() * 0.6
    emSize[i] = 4 + random.random() * 7
    emCharIndex[i] = random.randint(0, len(emberChars) - 1)
    emColorIndex[i] = random.randint(0, len(emberColors) - 1)


MAX_PARTICLES = 150
particleCount = 0
pX = np.zeros(MAX_PARTICLES, dtype=np.float32)
pY = np.zeros(MAX_PARTICLES, dtype=np.float32)
pVx = np.zeros(MAX_PARTICLES, dtype=np.float32)
pVy = np.zeros(MAX_PARTICLES, dtype=np.float32)
pLife = np.zeros(MAX_PARTICLES, dtype=np.float32)
pMaxLife = np.zeros(MAX_PARTICLES, dtype=np.float32)
pSize = np.zeros(MAX_PARTICLES, dtype=np.float32)
pCharIndex = np.zeros(MAX_PARTICLES, dtype=np.uint8)
fireChars = list('*✦✧⁕❋✺◌•∘˚⋆·')

# ---------- 文本排版 ----------
textEntries = [
  {'text': 'PRETEXT', 'font': 'monospace', 'fontSize': 120, 'color': (0x22, 0x22, 0x22), 'alpha': 0.5, 'yOffset': -20, 'maxWidth': 1200, 'lineHeight': 130, 'style': 'huge', 'column': 'center' },
  {'text': 'HERE BE DRAGONS', 'font': 'monospace', 'fontSize': 54, 'color': (0xf0, 0xf0, 0xf0), 'alpha': 1.0, 'yOffset': 100, 'maxWidth': 900, 'lineHeight': 64, 'style': 'heading', 'column': 'left' },
  {'text': 'Text measurement without DOM reflow — pure arithmetic, pure fire', 'font': 'monospace', 'fontSize': 18, 'color': (0x99, 0x99, 0x99), 'alpha': 0.75, 'yOffset': 175, 'maxWidth': 700, 'lineHeight': 26, 'style': 'body', 'column': 'left' },
  {'text': 'In the age of AI, text layout was the last and biggest bottleneck for unlocking much more interesting UIs. No longer do we have to choose between the flashiness of a WebGL landing page versus the practicality of a blog article. The engine is tiny, aware of browser quirks, and supports every language you will ever need.', 'font': 'monospace', 'fontSize': 14, 'color': (0xbb, 0xbb, 0xbb), 'alpha': 0.65, 'yOffset': 225, 'maxWidth': 500, 'lineHeight': 21, 'style': 'body', 'column': 'left' },
  {'text': '春天到了 — 龍が目を覚ます。بدأت الرحلة الكبرى 🐉🔥 prepare() once, layout() forever. 每一个文字都是一个粒子。', 'font': 'monospace', 'fontSize': 16, 'color': (0xee, 0x99, 0x44), 'alpha': 0.8, 'yOffset': 460, 'maxWidth': 520, 'lineHeight': 24, 'style': 'cjk', 'column': 'left' },
  {'text': "import { prepare, layout } from '@chenglou/pretext'\nconst prepared = prepare(text, '16px Inter')\nconst { height } = layout(prepared, width, 20)\n// ~0.0002ms per layout call. Pure math.", 'font': 'monospace', 'fontSize': 13, 'color': (0x77, 0xcc, 0x77), 'alpha': 0.6, 'yOffset': 550, 'maxWidth': 520, 'lineHeight': 18, 'style': 'code', 'column': 'left' },
  {'text': '"Fast, accurate and comprehensive userland text measurement algorithm in pure TypeScript, usable for laying out entire web pages without CSS"', 'font': 'monospace', 'fontSize': 14, 'color': (0xcc, 0x99, 0x66), 'alpha': 0.65, 'yOffset': 120, 'maxWidth': 380, 'lineHeight': 21, 'style': 'quote', 'column': 'right' },
  {'text': 'Shrinkwrapped chat bubbles. Responsive magazine layouts. Variable font width ASCII art. Canvas, SVG, WebGL — render anywhere. 120fps masonry with 100k items.', 'font': 'monospace', 'fontSize': 13, 'color': (0xbb, 0xbb, 0xbb), 'alpha': 0.6, 'yOffset': 310, 'maxWidth': 380, 'lineHeight': 19, 'style': 'body', 'column': 'right' },
  {'text': '✦ CJK per-character breaking\n✦ Arabic/Hebrew bidi\n✦ Emoji correction\n✦ Soft hyphens & tab stops\n✦ overflow-wrap: break-word\n✦ Grapheme-level breaking', 'font': 'monospace', 'fontSize': 12, 'color': (0xff, 0x99, 0x55), 'alpha': 0.55, 'yOffset': 470, 'maxWidth': 350, 'lineHeight': 17, 'style': 'code', 'column': 'right' },
  {'text': 'The serpent coils through canvas. Each scale a character. Each breath a particle. The text scatters and reforms.', 'font': 'monospace', 'fontSize': 15, 'color': (0x99, 0x88, 0x77), 'alpha': 0.5, 'yOffset': 680, 'maxWidth': 800, 'lineHeight': 22, 'style': 'quote', 'column': 'center' },
]


def layoutAllText():
    global letterCount, lChar, lFont, lColor  # pylint:disable=W0603
    letterCount = 0
    lChar = [None] * MAX_LETTERS
    lFont = [None] * MAX_LETTERS  # index into fontPool
    lColor = [None] * MAX_LETTERS  # index into colorPool

    mx = max(50, W * 0.06)
    my = max(60, H * 0.06)
    cw = W - mx * 2
    twoCol = cw > 700
    col2X = mx + cw * 0.56 if twoCol else mx

    for entry in textEntries:
        fontStr = f'{entry["fontSize"]}px {entry["font"]}'
        if entry['column'] == 'right':
            baseX = col2X if twoCol else mx
            maxW = min(entry['maxWidth'], cw * 0.4 if twoCol else cw)
        elif entry['column'] == 'center':
            maxW = min(entry['maxWidth'], cw)
            baseX = mx + (cw - maxW) / 2
        else:
            baseX = mx
            maxW = min(entry['maxWidth'], cw * 0.5 if twoCol else cw)
        baseY = my + entry['yOffset']
    
        if 1:  # try:
            prepared = prepareWithSegments(
                String(entry['text']), fontStr, 
                {'whiteSpace': 'pre-wrap'} if entry['style'] == 'code' else None
            )
            lines = layoutWithLines(prepared, maxW, entry['lineHeight'])['lines']
            for li in range(len(lines)):
                xc = baseX
                y = baseY + li * entry['lineHeight']
                ctx.font = fontStr
                # print(lines[li]['text'])
                for char in str(lines[li]['text']):
                    if char == '\n' or letterCount >= MAX_LETTERS: continue
                    cw2 = ctx.measureText(char)['width']
                    i = letterCount
                    letterCount += 1
                    lHomeX[i] = xc + cw2 / 2
                    lHomeY[i] = y + entry['lineHeight'] / 2
                    lX[i] = lHomeX[i]
                    lY[i] = lHomeY[i]
                    lVx[i] = lVy[i] = 0
                    lAngle[i] = lAngVel[i] = 0
                    lCharW[i] = cw2
                    lBaseAlpha[i] = entry['alpha']
                    lFontSize[i] = entry['fontSize']
                    lBurnTimer[i] = 0
                    lScaleMul[i] = 1
                    lGravity[i] = 0
                    lChar[i] = char
                    lFont[i] = fontStr
                    lColor[i] = entry['color']
                    xc += cw2
        # except Exception as e:
        #     print(e)


# ---------- 龙链 ----------

SEG_SPACING = 10
# SoA for chain too
chainN = 0
chX = np.zeros(80, dtype=np.float32)
chY = np.zeros(80, dtype=np.float32)
chPx = np.zeros(80, dtype=np.float32)
chPy = np.zeros(80, dtype=np.float32)

def rebuildDragon():
    global chainN, chX, chY, chPx, chPy  # pylint:disable=W0603
    chainN = cfg['dragonSegments']
    if len(chX) < chainN:
        chX = np.zeros(chainN, dtype=np.float32)
        chY = np.zeros(chainN, dtype=np.float32)
        chPx = np.zeros(chainN, dtype=np.float32)
        chPy = np.zeros(chainN, dtype=np.float32)
    chX[:chainN] = W / 2
    chY[:chainN] = H / 2 + np.arange(chainN) * SEG_SPACING
    chPx[:chainN] = chX[:chainN]
    chPy[:chainN] = chY[:chainN]


rebuildDragon()

dragonChars = list('◆◆◇▼█▓▓▒╬╬╬╬╬╬╬╬╬╬╫╫╫╪╪╪╧╧╤╤╥╥║║││┃┃╎╎╏╏::····..')

def segScale(i):
    if i < 3: return (2.5 - i * 0.15) * cfg['dragonScale']
    t = (i - 3) / (chainN - 3)
    return (2.0 * (1 - t * t) + 0.2) * cfg['dragonScale']


def updateChain():
    chPx[:chainN] = chX[:chainN]
    chPy[:chainN] = chY[:chainN]
    chX[0] += (mouse_x - chX[0]) * cfg['dragonSpeed']
    chY[0] += (mouse_y - chY[0]) * cfg['dragonSpeed']
    for i in range(1, chainN):
        dx = chX[i] - chX[i - 1]
        dy = chY[i] - chY[i - 1]
        d = math.sqrt(dx * dx + dy * dy)
        if d > SEG_SPACING:
            r = SEG_SPACING / d
            chX[i] = chX[i - 1] + dx * r
            chY[i] = chY[i - 1] + dy * r


# ---------- 物理模拟 ----------
def interactLetters(dt):
    # 实际活跃字母数量
    checkSegs = min(round(chainN * 0.4), chainN)
    scales = np.array([segScale(i) for i in range(chainN)], dtype=np.float32)
    n = letterCount
    if n <= 0:
        return

    # 获取视图（仅前 n 个元素）
    lX_act = lX[:n]
    lY_act = lY[:n]
    lVx_act = lVx[:n]
    lVy_act = lVy[:n]
    lAngle_act = lAngle[:n]
    lAngVel_act = lAngVel[:n]
    lBurnTimer_act = lBurnTimer[:n]
    lScaleMul_act = lScaleMul[:n]
    lGravity_act = lGravity[:n]
    lHomeX_act = lHomeX[:n]
    lHomeY_act = lHomeY[:n]
    lCharW_act = lCharW[:n]

    # 常量
    damp = cfg['damping']
    spring = cfg['springStrength']
    push = cfg['pushForce']
    bGrav = cfg['burnGravity']

    # ---- 龙身碰撞（前 checkSegs 个段）----
    checkSegs = min(round(chainN * 0.4), chainN)
    if checkSegs > 0:
        chX_check = chX[:checkSegs]
        chY_check = chY[:checkSegs]
        chPx_check = chPx[:checkSegs]
        chPy_check = chPy[:checkSegs]
        scales_check = scales[:checkSegs]

        # 广播计算所有字母与所有段的坐标差 (n, checkSegs)
        dx = lX_act[:, np.newaxis] - chX_check[np.newaxis, :]
        dy = lY_act[:, np.newaxis] - chY_check[np.newaxis, :]
        dSq = dx * dx + dy * dy

        # 最小距离
        rad = 14.0 * scales_check * 0.45
        minD = rad + lCharW_act[:, np.newaxis] * 0.4 + 4.0

        collide = (dSq < minD * minD) & (dSq > 0.01)
        if np.any(collide):
            d = np.zeros_like(dSq)
            np.sqrt(dSq, where=collide, out=d)
            f = np.zeros_like(dSq)
            np.divide((minD - d), minD, where=collide, out=f)
            f *= push * scales_check

            nx = np.divide(dx, d, where=collide, out=np.zeros_like(dx))
            ny = np.divide(dy, d, where=collide, out=np.zeros_like(dy))

            # 段速度贡献（仅碰撞对）
            speed_contrib_x = (chX_check - chPx_check) * 0.4
            speed_contrib_y = (chY_check - chPy_check) * 0.4
            delta_vx = nx * f + speed_contrib_x * collide
            delta_vy = ny * f + speed_contrib_y * collide
            delta_av = (nx * 0.3 - ny * 0.2) * f * 0.12

            lVx_act += np.sum(delta_vx, axis=1)
            lVy_act += np.sum(delta_vy, axis=1)
            lAngVel_act += np.sum(delta_av, axis=1)

    # ---- 尾迹效应（每5个段）----
    wake_indices = np.arange(5, chainN, 5)
    if len(wake_indices) > 0:
        chX_wake = chX[wake_indices]
        chY_wake = chY[wake_indices]
        chPx_wake = chPx[wake_indices]
        chPy_wake = chPy[wake_indices]

        dx_w = lX_act[:, np.newaxis] - chX_wake[np.newaxis, :]
        dy_w = lY_act[:, np.newaxis] - chY_wake[np.newaxis, :]
        dSq_w = dx_w * dx_w + dy_w * dy_w

        # 距离在 (10, 40) 之间
        wake_mask = (dSq_w > 100) & (dSq_w < 1600)
        if np.any(wake_mask):
            d_w = np.zeros_like(dSq_w)
            np.sqrt(dSq_w, where=wake_mask, out=d_w)
            w = (1.0 - d_w / 40.0) * 0.12
            w[~wake_mask] = 0.0

            vel_dx = (chX_wake - chPx_wake)[np.newaxis, :] * w
            vel_dy = (chY_wake - chPy_wake)[np.newaxis, :] * w
            lVx_act += np.sum(vel_dx, axis=1)
            lVy_act += np.sum(vel_dy, axis=1)

    # ---- 燃烧逻辑 ----
    burning = lBurnTimer_act > 0
    if np.any(burning):
        lBurnTimer_act[burning] -= dt
        lScaleMul_act[burning] = 1.0 + lBurnTimer_act[burning] * 0.4
        lGravity_act[burning] = bGrav

        # 随机生成火星
        r = np.random.rand(n)
        spawn = burning & (r < dt * 2.0)
        for idx in np.where(spawn)[0]:
            spawnEmber(lX_act[idx], lY_act[idx])

        # 燃烧结束
        expired = (lBurnTimer_act <= 0) & burning
        if np.any(expired):
            lBurnTimer_act[expired] = 0.0
            lScaleMul_act[expired] = 1.0
            lGravity_act[expired] = 0.0

    # ---- 弹簧回拉 ----
    hdx = lHomeX_act - lX_act
    hdy = lHomeY_act - lY_act
    hd = np.sqrt(hdx * hdx + hdy * hdy)
    far = hd > 0.5
    if np.any(far):
        sf = spring * (1.0 + hd[far] * 0.001)
        lVx_act[far] += hdx[far] * sf
        lVy_act[far] += hdy[far] * sf
        lAngVel_act[far] -= lAngle_act[far] * 0.05
    near = ~far
    if np.any(near):
        lAngle_act[near] *= 0.9

    # ---- 重力、阻尼与积分 ----
    lVy_act += lGravity_act
    lVx_act *= damp
    lVy_act *= damp
    lAngVel_act *= 0.91
    lX_act += lVx_act
    lY_act += lVy_act
    lAngle_act += lAngVel_act


def fireBlastAt(bx, by, dx, dy):
    hits = 0
    rSq = cfg['fireRadius'] ** 2
    ff = cfg['fireForce']
    fr = cfg['fireRadius']

    for li in range(letterCount):
        ldx = lX[li] - bx
        ldy = lY[li] - by
        dSq = ldx * ldx + ldy * ldy
        if dSq < rSq and dSq > 0.01:
            d = math.sqrt(dSq)
            f = ff * ((1 - d / fr) ** 2)
            lVx[li] += (ldx / d * 0.4 + dx * 0.6) * f
            lVy[li] += (ldy / d * 0.4 + dy * 0.6) * f - f * 0.2
            lAngVel[li] += (random.random() - 0.5) * f * 0.3
            lBurnTimer[li] = max(lBurnTimer[li], 0.5 + random.random() * 1.2)
            hits += 1
    if hits > 3:
        triggerShake(min(hits * 0.4, 6))
        for _ in range(min(hits, 4)):
            spawnEmber(bx, by)


@lru_cache(maxsize=None)
def get_pic(text, size, fgcolor):
    return ctx.get_font().render(text, size=float(size), fgcolor=fgcolor)[0]


def drawLetters(surface):
    opMul = cfg['textOpacity']
    
    ctx.font = '15px monospace'
    font = ctx.get_font()
    
    burnings = lBurnTimer[:letterCount] > 0
    alphas = lBaseAlpha[:letterCount] * opMul

    h = np.minimum(1, lBurnTimer[:letterCount])
    burn_alphas = np.minimum(1, alphas[:letterCount] + 0.5)
    
    burn_color = np.zeros((letterCount, 3), dtype=np.uint8)
    burn_color[:, 0] = 255
    burn_color[:, 1] = (80 + 175 * h).astype(np.uint8)
    burn_color[:, 2] = (60 * h).astype(np.uint8)
    
    colors = np.where(burnings[:, np.newaxis], burn_color, lColor[:letterCount])
    alphas = (np.where(burnings, burn_alphas, alphas) * 255).astype(np.uint8)
    colors = np.column_stack((colors, alphas))
    
    light_masks = burnings & (lBurnTimer[:letterCount] > 0.3)
    angles = -lAngle[:letterCount] * 180 / math.pi
    
    light_colors = np.zeros_like(colors)
    light_colors[:, 0], light_colors[:, 1] = 0xff, 0xaa
    light_colors[:, 3] = (0.2 * lBurnTimer[:letterCount] * 255).astype(np.uint8)
    
    font_size = lFontSize[:letterCount] * lScaleMul[:letterCount]
    final_x = shakeX + lX[:letterCount]
    final_y = shakeY + lY[:letterCount]
    
    # --- 保留的逐字母绘制循环 ---
    for i in range(letterCount):
        # sf = get_pic(lChar[i], font_size[i], tuple(colors[i]))
        sf, _ = font.render(lChar[i], size=float(font_size[i]), fgcolor=tuple(colors[i]))
        sf = pygame.transform.rotate(sf, float(angles[i]))
        surface.blit(sf, sf.get_rect(center=(int(final_x[i]), int(final_y[i]))))
        
        if light_masks[i]:
            # sf = get_pic(lChar[i], font_size[i], tuple(light_colors[i]))
            sf, _ = font.render(lChar[i], size=float(font_size[i]), fgcolor=tuple(light_colors[i]))
            sf = pygame.transform.rotate(sf, float(angles[i]))
            surface.blit(sf, sf.get_rect(center=(int(final_x[i]), int(final_y[i]))))


# ---------- 发射火焰 & 粒子更新 ----------
isBreathingFire = False
fireAccum = 0
totalFireTime = 0

def emitFire(dt):
    global totalFireTime, fireAccum, particleCount  # pylint:disable=W0603
    if not isBreathingFire:
        totalFireTime = 0
        return
    fireAccum += dt
    totalFireTime += dt
    hx, hy = chX[0], chY[0]
    ni = min(3, chainN - 1)
    fdx = hx - chX[ni]
    fdy = hy - chY[ni]
    length = math.sqrt(fdx * fdx + fdy * fdy) or 1
    dx = fdx / length
    dy = fdy / length
    angle = math.atan2(fdy, fdx)

    if cfg['showParticles']:
        while fireAccum > 0.025:
            fireAccum -= 0.025
            if particleCount >= MAX_PARTICLES: break
            for _ in range(2):
                if particleCount >= MAX_PARTICLES: break
                i = particleCount
                particleCount += 1
                sp = random.random() - 0.5
                spd = 5 + random.random() * 7
                pX[i] = hx + dx * 15; pY[i] = hy + dy * 15
                pVx[i] = math.cos(angle + sp) * spd
                pVy[i] = math.sin(angle + sp) * spd - random.random()
                pLife[i] = 1
                pMaxLife[i] = 0.3 + random.random() * 0.4
                pSize[i] = 6 + random.random() * 12
                pCharIndex[i] = random.randint(0, len(fireChars) - 1)
    else:
        fireAccum = 0

    bx = hx + dx * 50
    by = hy + dy * 50
    fireBlastAt(bx, by, dx, dy)
    hitEnemiesWithFire(bx, by)
    triggerShake(min(1 + totalFireTime * 0.2, 3))


def updateParticlesAndEmbers(dt):
    global particleCount, emberCount  # pylint:disable=W0603

    # Particles
    pX[:particleCount] += pVx[:particleCount]
    pY[:particleCount] += pVy[:particleCount]
    pVy[:particleCount] -= 0.25
    pVx[:particleCount] *= 0.97
    pLife[:particleCount] -= dt / pMaxLife[:particleCount]
    
    # 筛选存活粒子
    alive = pLife[:particleCount] > 0
    new_count = np.count_nonzero(alive)
    
    # 压缩：将存活数据移到前面
    if new_count < particleCount:
        # 对每个属性分别压缩（或使用结构化数组）
        pX[:new_count] = pX[:particleCount][alive]
        pY[:new_count] = pY[:particleCount][alive]
        pVx[:new_count] = pVx[:particleCount][alive]
        pVy[:new_count] = pVy[:particleCount][alive]
        pLife[:new_count] = pLife[:particleCount][alive]
        pMaxLife[:new_count] = pMaxLife[:particleCount][alive]
        pSize[:new_count] = pSize[:particleCount][alive]
        pCharIndex[:new_count] = pCharIndex[:particleCount][alive]
        # 若还有颜色、字符等数组，同样压缩
    particleCount = new_count

    # Embers — swap-remove
    emX[:emberCount] += emVx[:emberCount]
    emY[:emberCount] += emVy[:emberCount]
    emVy[:emberCount] += 0.15
    emVx[:emberCount] *= 0.97
    emLife[:emberCount] -= dt
    
    ember_alive = emLife[:emberCount] > 0
    new_ember_count = np.count_nonzero(ember_alive)
    
    if new_ember_count < emberCount:
        emX[:new_ember_count] = emX[:emberCount][ember_alive]
        emY[:new_ember_count] = emY[:emberCount][ember_alive]
        emVx[:new_ember_count] = emVx[:emberCount][ember_alive]
        emVy[:new_ember_count] = emVy[:emberCount][ember_alive]
        emLife[:new_ember_count] = emLife[:emberCount][ember_alive]
        emColorIndex[:new_ember_count] = emColorIndex[:emberCount][ember_alive]
        emSize[:new_ember_count] = emSize[:emberCount][ember_alive]
        emCharIndex[:new_ember_count] = emCharIndex[:emberCount][ember_alive]
    emberCount = new_ember_count
            

def drawParticles(_time, surface):
    font: pygame.freetype.Font = ctx.get_font()
    if cfg['showEmbers']:
        for i in range(emberCount):
            sf, _ = font.render(emberChars[emCharIndex[i]], size=int(emSize[i]), fgcolor=(*emberColors[emColorIndex[i]], int(255 * min(1, emLife[i] * 2))))
            surface.blit(sf, sf.get_rect(center=(int(shakeX + emX[i]), int(shakeY + emY[i]))))

    if cfg['showParticles']:
        for i in range(particleCount):
            t = 1 - pLife[i]
            if t < 0.15:
                r = 255; g = 255; b = int(255 * (1 - t * 6.67))
            elif t < 0.4:
                r = 255; g = int(255 * (1 - (t - 0.15) * 3.2)) ; b = 0
            else:
                f = (t - 0.4) * 1.67; r = int(255 * (1 - f * 0.6)); g = int(80 * (1 - f)); b = 0
            sz = pSize[i] * (0.4 + pLife[i] * 0.6)
            sf, _ = font.render(fireChars[pCharIndex[i]], size=int(sz), fgcolor=(r,g,b,int(255 * pLife[i] * 0.85)))
            surface.blit(sf, sf.get_rect(center=(int(shakeX + pX[i]), int(shakeY + pY[i]))))


# ---------- 敌人 ----------
enemies = []
score = 0
scoreFlash = 0

EK = [
  {'char': '◈', 'color': (0xff, 0x44, 0x66), 'hp': 1, 'size': 22, 'speed': 1.0 },
  {'char': '⬢', 'color': (0xff, 0x66, 0x88), 'hp': 3, 'size': 28, 'speed': 0.5 },
  {'char': '◇', 'color': (0x44, 0xdd, 0xff), 'hp': 1, 'size': 16, 'speed': 2.2 },
  {'char': '◌', 'color': (0xaa, 0x88, 0xff), 'hp': 2, 'size': 20, 'speed': 0.8 },
]

def spawnEnemy():
    ki = int(random.random() * len(EK))
    k = EK[ki]
    edge = int(random.random() * 4)
    x = 0
    y = 0
    if edge == 0:
        x = -30
        y = random.random() * H
    elif edge == 1:
        x = W + 30
        y = random.random() * H
    elif edge == 2:
        x = random.random() * W
        y = -30
    else:
        x = random.random() * W
        y = H + 30
    enemies.append({
      'x': x, 'y': y, 'vx': (random.random() - 0.5) * k['speed'] * 2, 
      'vy': (random.random() - 0.5) * k['speed'] * 2, 'hp': k['hp'], 
      'maxHp': k['hp'], 'char': k['char'], 'size': k['size'], 'color': k['color'], 
      'phase': random.random() * math.pi * 2, 'dying': False, 'deathTimer': 0, 'kind': ki
    })


def updateEnemies(dt, _time):
    global scoreFlash  # pylint:disable=W0603
    if not cfg['showEnemies']: return
    # Count alive
    alive = 0
    for i in range(len(enemies)):
        if not enemies[i]['dying']: alive += 1
    while alive < cfg['enemyCount']:
        spawnEnemy()
        alive += 1

    for i in range(len(enemies) - 1, -1, -1):
        e = enemies[i]
        if e['dying']:
            e['deathTimer'] -= dt
            e['x'] += e['vx']
            e['y'] += e['vy']
            e['vx'] *= 0.95
            e['vy'] *= 0.95
            if e['deathTimer'] <= 0:
                enemies[i] = enemies[len(enemies) - 1]
                enemies.pop()
            continue
        spd = cfg['enemySpeed']
        if e['kind'] == 3:
            e['x'] += math.sin(_time * 1.5 + e['phase']) * spd * 1.2
            e['y'] += math.cos(_time * 1.2 + e['phase'] * 1.3) * spd * 0.8
        elif e['kind'] == 2:
            e['x'] += e['vx'] * spd
            e['y'] += e['vy'] * spd
            if random.random() < dt * 0.5:
                e['vx'] += (random.random() - 0.5) * 3
                e['vy'] += (random.random() - 0.5) * 3
            e['vx'] *= 0.99
            e['vy'] *= 0.99
        else:
            e['vx'] += (W / 2 - e['x']) * 0.0001 + (random.random() - 0.5) * 0.1
            e['vy'] += (H / 2 - e['y']) * 0.0001 + (random.random() - 0.5) * 0.1
            e['vx'] *= 0.995
            e['vy'] *= 0.995
            e['x'] += e['vx'] * spd
            e['y'] += e['vy'] * spd
        if e['x'] < -50:
            e['x'] = W + 40
        if e['x'] > W + 50:
            e['x'] = -40
        if e['y'] < -50:
            e['y'] = H + 40
        if e['y'] > H + 50:
            e['y'] = -40
        dx, dy = e['x'] - chX[0], e['y'] - chY[0]
        dSq = dx * dx + dy * dy
        if dSq < 15000:
            d = math.sqrt(dSq) or 1
            fl = 1.5 * (1 - d / 122)
            e['vx'] += (dx / d) * fl
            e['vy'] += (dy / d) * fl
    if scoreFlash > 0:
        scoreFlash -= dt * 3


def hitEnemiesWithFire(fx, fy):
    global score, scoreFlash  # pylint:disable=W0603
    if not cfg['showEnemies']: return
    hr = cfg['fireRadius'] * 0.6
    hrSq = hr * hr
    for e in enemies:
        if e['dying']: continue
        dx = e['x'] - fx
        dy = e['y'] - fy
        dSq = dx * dx + dy * dy
        if dSq < hrSq:
            d = math.sqrt(dSq) or 1
            e['hp'] -= 1
            e['vx'] += (dx / d) * 5
            e['vy'] += (dy / d) * 5
            if e['hp'] <= 0:
                e['dying'] = True
                e['deathTimer'] = 0.5
                e['vx'] = (dx / d) * 8
                e['vy'] = (dy / d) * 8 - 3
                _scores = {1: 30, 2: 20, 3: 25}
                score += _scores.get(e['kind'], 10)
                scoreFlash = 1
                for _ in range(3): spawnEmber(e['x'], e['y'])

def drawEnemies(_time, surface):
    if not cfg['showEnemies']: return
    font = ctx.get_font()
    for e in enemies:
        if e['dying']:
            t = e['deathTimer'] / 0.5
            _size = int(e['size'] * t)
            if _size == 0:
                continue
            sf, _ = font.render(e['char'], size=_size, fgcolor=(0xff, 0xaa, 0, int(t * 0.8 * 255)))
            sf = pygame.transform.rotate(sf, float(-_time * 15 * 180 / math.pi))
            surface.blit(sf, sf.get_rect(center=(int(shakeX + e['x']), int(shakeY + e['y']))))
        else:
            bob = math.sin(_time * 2.5 + e['phase']) * 4
            alpha = 0.4 + math.sin(_time * 3 + e['phase']) * 0.2 if e['kind'] == 3 else 0.75
            sf, _ = font.render(e['char'], size=e['size'], fgcolor=(*e['color'], int(alpha * 255)))
            surface.blit(sf, sf.get_rect(center=(int(shakeX + e['x']), int(shakeY + e['y'] + bob))))
            # pygame.draw.rect(surface, (255,0,0),(e['x'], e['y'], 10, 10))
    if score > 0:
        alpha = int((0.3 + scoreFlash * 0.4) * 255)
        color = (0xff, 0xaa, 0x33, alpha) if scoreFlash > 0 else (0x66, 0x66, 0x66, alpha)
        surface.blit(InterFont.render(f'SCORE {score}', True, color), (int(shakeX + 20), int(shakeY + 20)))

# ---------- 渲染 ----------
tunnelTexts = [
  'PRETEXT — pure text measurement',
  '春天到了 — テキストレイアウト革命',
  'prepare() → layout() → render',
  'بدأت الرحلة · Начало пути · 시작',
  'No DOM. No reflow. Pure math.',
  'CJK · Bidi · Emoji · Graphemes',
]
tunnelFont = '13px monospace'
TUNNEL_RINGS = 12
TUNNEL_DEPTH = 1200

tunnelZ = np.zeros(TUNNEL_RINGS, dtype=np.float32)
tunnelSide = np.zeros(TUNNEL_RINGS, dtype=np.uint8)
tunnelTextIdx = np.zeros(TUNNEL_RINGS, dtype=np.uint8)

def buildTunnel():
  for i in range(TUNNEL_RINGS):
        tunnelZ[i] = (i / TUNNEL_RINGS) * TUNNEL_DEPTH
        tunnelSide[i] = i % 4
        tunnelTextIdx[i] = i % len(tunnelTexts)


buildTunnel()


def drawTunnel(surface):
    cx = W * 0.5
    cy = H * 0.5
    ctx.font = tunnelFont
    font: pygame.freetype.Font = ctx.get_font()
    
    for i in range(TUNNEL_RINGS):
        tunnelZ[i] -= 0.67
        if tunnelZ[i] < 10:
            tunnelZ[i] += TUNNEL_DEPTH
            tunnelSide[i] = (tunnelSide[i] + 1) % 4
            tunnelTextIdx[i] = int(random.random() * len(tunnelTexts))
        scale = 400 / (400 + tunnelZ[i])
        alpha = max(0, min(0.06, 0.08 * scale - 0.01))
        if alpha < 0.003: continue
        spread = 350 * scale
        s = tunnelSide[i]
        if s == 0:
            x = cx; y = cy - spread
        elif s == 1:
            x = cx + spread; y = cy
        elif s == 2:
            x = cx; y = cy + spread
        else:
            x = cx - spread; y = cy
        sf, _ = font.render(tunnelTexts[tunnelTextIdx[i]], size=13, fgcolor=(0xff, 0x88, 0x44, int(255 * alpha)))
        surface.blit(sf, sf.get_rect(center=(int(shakeX + x), int(shakeY + y))))


RUNE_N = 8
runeChars = list('龍火竜鱗焔ᚱᚦᛏ')
runeX = [random.random() * W for _ in range(RUNE_N)]
runeY = [random.random() * H for _ in range(RUNE_N)]
runeSpd = [0.1 + random.random() * 0.4 for _ in range(RUNE_N)]
runePhase = [random.random() * math.pi * 2 for _ in range(RUNE_N)]
runeSz = [14 + random.random() * 14 for _ in range(RUNE_N)]
runeOp = [0.02 + random.random() * 0.04 for _ in range(RUNE_N)]
runeC = [random.choice(runeChars) for _ in range(RUNE_N)]

def drawRunes(_time, surface):
    if not cfg['showRunes']: return
    ctx.font = '10px monospace'
    font: pygame.freetype.Font = ctx.get_font()
    for i in range(RUNE_N):
        runeY[i] -= runeSpd[i]
        if runeY[i] < -30:
            runeY[i] = H + 30
            runeX[i] = random.random() * W
        alpha = int(255 * runeOp[i] * (0.5 + math.sin(_time * 0.4 + runePhase[i]) * 0.5))
        sf, _ = font.render(runeC[i], size=int(runeSz[i]), fgcolor=(0xff, 0x66, 0x00, alpha))
        surface.blit(sf, sf.get_rect(center=(int(shakeX + runeX[i] + math.sin(_time * 0.7 + runePhase[i]) * 12), int(shakeY + runeY[i]))))
        # pygame.draw.rect(surface, (255,0,0),(runeX[i], runeY[i], 10, 10))

def drawDragon(_time, surface):
    ctx.font = '16px monospace'
    font: pygame.freetype.Font = ctx.get_font()
    for i in range(chainN - 1, -1, -1):
        sc = segScale(i)
        ci = min(i, len(dragonChars) - 1)
        size = 14 * sc
        t = i / chainN
        p = math.sin(_time * 3 + i * 0.3) * 0.12
        if i < 3:
            color = (255, int(180 + p * 60), int(40 + p * 30), 255)
        else:
            w = math.sin(_time * 2 - i * 0.15) * 0.15
            color = (int(255 * (1 - t * 0.5) + p * 20), int(140 * (1 - t * 0.8) + w * 60), int(30 * (1 - t) + w * 20), 255 * (1 - t * 0.45))
        
        angle = math.atan2(mouse_y - chY[0], mouse_x - chX[0]) if i == 0 else math.atan2(chY[i - 1] - chY[i], chX[i - 1] - chX[i])
        color = tuple(min(max(c, 0), 255) for c in color)
        
        if i < 4:
            r = int(size * 1.1)
            circle_sf = pygame.Surface((2*r, 2*r), pygame.SRCALPHA)
            pygame.draw.circle(circle_sf, (0xff, 0x66, 0x00, int(255 * 0.06 * (2 if isBreathingFire else 1))), (r, r), r)
            surface.blit(circle_sf, (int(shakeX + chX[i] - r), int(shakeY + chY[i] - r)))

        if cfg['showSpines'] and i >= 4 and i <= 30 and i % 3 == 0:
            sa = angle + math.pi / 2
            _size = int(size * (0.6 + math.sin(_time * 3 + i) * 0.15))
            sf, _ = font.render('▴', size=_size, fgcolor=(*color[:3], int(color[3] * 0.35)))
            surface.blit(sf, sf.get_rect(center=(int(shakeX + chX[i] + math.cos(sa) * size * 0.35), int(shakeY + chY[i] + math.sin(sa) * size * 0.35))))
    
        if cfg['showWings'] and i >= 7 and i <= 16 and i % 2 == 0:
            wp = math.sin(_time * 3.5 + i * 0.4) * 0.5
            ws = size * (1.8 - abs(i - 11.5) * 0.12)
            wd = size * 1.4
            w1 = angle + math.pi / 2 + wp
            w2 = angle - math.pi / 2 - wp
            
            sf, _ = font.render('<', size=int(ws), fgcolor=(*color[:3], int(color[3] * 0.4)))
            surface.blit(sf, sf.get_rect(center=(int(shakeX + chX[i] + math.cos(w1) * wd), int(shakeY + chY[i] + math.sin(w1) * wd))))
            
            sf, _ = font.render('>', size=int(ws), fgcolor=(*color[:3], int(color[3] * 0.4)))
            surface.blit(sf, sf.get_rect(center=(int(shakeX + chX[i] + math.cos(w2) * wd), int(shakeY + chY[i] + math.sin(w2) * wd))))
 
        sf, _ = font.render(dragonChars[ci], size=int(size), fgcolor=color)
        sf = pygame.transform.rotate(sf, float(-angle * 180 / math.pi))
        offset = math.sin(_time * 5 + i * 0.35) * 1.5
        off_x, off_y = -offset * math.sin(angle), offset * math.cos(angle)
        surface.blit(sf, sf.get_rect(center=(int(shakeX + chX[i] + off_x), int(shakeY + chY[i] + off_y))))
        
        
        if isBreathingFire and i < 3:
            sf, _ = font.render(dragonChars[ci], size=int(ws), fgcolor=(0xff, 0xcc, 0, int(255 * 0.3)))
            surface.blit(sf, sf.get_rect(center=(int(shakeX + chX[i] + off_x), int(shakeY + chY[i] + off_y))))
 

    # Eyes
    ha = math.atan2(mouse_y - chY[0], mouse_x - chX[0])
    ex = chX[0] + math.cos(ha + 0.5) * 10
    ey = chY[0] + math.sin(ha + 0.5) * 10
    r = 18 if isBreathingFire else 12
    circle_sf = pygame.Surface((2*r, 2*r), pygame.SRCALPHA)
    pygame.draw.circle(circle_sf, (0xff, 0x88, 0, int(255 * (0.2 if isBreathingFire else 0.1))), (r, r), r)
    surface.blit(circle_sf, (int(shakeX + ex - r), int(shakeY + ey - r)))

    _text = '—' if _time % 5 > 4.7 else ('◉' if isBreathingFire else '⊙')
    _color = (255, 255, 255) if isBreathingFire else (255, 204, 0)
    sf, _ = font.render(_text, size=16, fgcolor=_color)
    surface.blit(sf, sf.get_rect(center=(int(shakeX + ex), int(shakeY + ey))))


def drawCursor(_time: float, surface: pygame.Surface):
    if not cfg['showCursor']:
        return

    mx, my = mouse_x, mouse_y
    rot = _time * 0.4

    # 光标活动范围：最大偏移量 ±24（十字线） + 半径16 ≈ 40 像素，取余量 5 -> 边长 90
    offset = 45
    size = offset * 2
    # 创建小 surface（支持透明）
    cursor_surf = pygame.Surface((size, size), pygame.SRCALPHA)

    # 将鼠标位置作为局部表面的中心点 (offset, offset)
    cx, cy = offset, offset

    # 1. 画两个圆弧 (半径16)
    radius = 16
    rect = pygame.Rect(cx - radius, cy - radius, radius * 2, radius * 2)
    arc_color = (255, 136, 68, 64)          # alpha 0.25
    start1 = 0 + rot
    end1 = math.pi * 0.5 + rot
    pygame.draw.arc(cursor_surf, arc_color, rect, start1, end1, 1)
    start2 = math.pi + rot
    end2 = math.pi * 1.5 + rot
    pygame.draw.arc(cursor_surf, arc_color, rect, start2, end2, 1)

    # 2. 中心圆点
    center_alpha = 0.8 if isBreathingFire else 0.5
    center_color = (255, 170, 51, int(center_alpha * 255)) if isBreathingFire else (255, 136, 68, int(center_alpha * 255))
    center_radius = 3 if isBreathingFire else 2
    pygame.draw.circle(cursor_surf, center_color, (cx, cy), center_radius)

    # 3. 十字准线 (四条短线)
    cross_color = (255, 136, 68, int(0.15 * 255))
    # 水平
    pygame.draw.line(cursor_surf, cross_color, (cx - 24, cy), (cx - 8, cy), 1)
    pygame.draw.line(cursor_surf, cross_color, (cx + 8, cy), (cx + 24, cy), 1)
    # 垂直
    pygame.draw.line(cursor_surf, cross_color, (cx, cy - 24), (cx, cy - 8), 1)
    pygame.draw.line(cursor_surf, cross_color, (cx, cy + 8), (cx, cy + 24), 1)

    # 将小 surface 贴到屏幕的对应位置 (左上角对准鼠标位置减去偏移)
    surface.blit(cursor_surf, (int(shakeX + mx - offset), int(shakeY + my - offset)))

def drawFPS(surface):
    img = InterFont.render(str(round(clock.get_fps())) + ' FPS', True, (0x66, 0x66, 0x66))
    surface.blit(img, (int(shakeX + 20), int(shakeY + 40)))

# ---------- 主循环 ----------
running = True
last_time = pygame.time.get_ticks() / 1000.0
__time = 0

apply_preset('Default')
layoutAllText()

while running:
    __dt = min((pygame.time.get_ticks()/1000.0 - last_time), 0.05)
    last_time = pygame.time.get_ticks() / 1000.0
    __time += __dt
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_1:
                apply_preset('Default')
            elif event.key == pygame.K_2:
                apply_preset('Gentle')
            elif event.key == pygame.K_3:
                apply_preset('Chaos')
            elif event.key == pygame.K_4:
                apply_preset('Zen')
            elif event.key == pygame.K_5:
                apply_preset('Tiny')
            elif event.key == pygame.K_6:
                apply_preset('Leviathan')
            elif event.key == pygame.K_r:  # 手动重新排版
                layoutAllText()
        elif event.type == pygame.VIDEORESIZE:
            W, H = event.w, event.h
            screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
            layoutAllText()
            rebuildDragon()
        elif event.type == pygame.MOUSEMOTION:
            mouse_x, mouse_y = event.pos
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                isBreathingFire = True
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                isBreathingFire = False

    updateShake()
    screen.fill((10, 10, 10))
    
    drawTunnel(screen)
    drawRunes(__time, screen)
    updateChain()
    interactLetters(__dt)
    emitFire(__dt)
    updateParticlesAndEmbers(__dt)
    updateEnemies(__dt, __time)
    drawLetters(screen)
    drawEnemies(__time, screen)
    drawDragon(__time, screen)
    drawParticles(__time, screen)
    drawCursor(__time, screen)
    drawFPS(screen)

    pygame.display.flip()
    clock.tick(114514)

pygame.quit()
sys.exit()