import math
import sys
import pygame
import numpy as np
from PIL import Image, ImageFilter
from pretext_py import layout, prepareWithSegments, layoutWithLines, layoutNextLine, walkLineRanges, set_custom_canvas
from pretext_py.measurement import getMeasureContext
from custom_canvas_pg_font import Context

set_custom_canvas(Context)
ctx = getMeasureContext()
ctx.registry.register('serif', 'Domitian-Roman.otf', bold='Domitian-Bold.otf', italic='Domitian-Italic.otf')
BODY_FONT = '18px serif'
BODY_LINE_HEIGHT = 30
HEADLINE_FONT_FAMILY = 'serif'
HEADLINE_TEXT = "THE FUTURE OF TEXT LAYOUT IS NOT CSS"
GUTTER = 48
COL_GAP = 40
STATS_BAR_HEIGHT = 42
DROP_CAP_LINES = 3
MIN_SLOT_WIDTH = 50

def carveTextLineSlots(base, blocked):
    slots = [base]
    for iv in blocked:
        next_slots = []
        for s in slots:
            if iv['right'] <= s['left'] or iv['left'] >= s['right']:
                next_slots.append(s)
                continue
            if iv['left'] > s['left']:
                next_slots.append({'left': s['left'], 'right': iv['left']})
            if iv['right'] < s['right']:
                next_slots.append({'left': iv['right'], 'right': s['right']})
        slots = next_slots
    return [s for s in slots if s['right'] - s['left'] >= MIN_SLOT_WIDTH]


BODY_TEXT = '''The web renders text through a pipeline that was designed thirty years ago for static documents. A browser loads a font, shapes the text into glyphs, measures their combined width, determines where lines break, and positions each line vertically. Every step depends on the previous one. Every step requires the rendering engine to consult its internal layout tree — a structure so expensive to maintain that browsers guard access to it behind synchronous reflow barriers that can freeze the main thread for tens of milliseconds at a time.

For a paragraph in a blog post, this pipeline is invisible. The browser loads, lays out, and paints before the reader’s eye has traveled from the address bar to the first word. But the web is no longer a collection of static documents. It is a platform for applications, and those applications need to know about text in ways the original pipeline never anticipated.

A messaging application needs to know the exact height of every message bubble before rendering a virtualized list. A masonry layout needs the height of every card to position them without overlap. An editorial page needs text to flow around images, advertisements, and interactive elements. A responsive dashboard needs to resize and reflow text in real time as the user drags a panel divider.

Every one of these operations requires text measurement. And every text measurement on the web today requires a synchronous layout reflow. The cost is devastating. Measuring the height of a single text block forces the browser to recalculate the position of every element on the page. When you measure five hundred text blocks in sequence, you trigger five hundred full layout passes. This pattern, known as layout thrashing, is the single largest source of jank on the modern web.

Chrome DevTools will flag it with angry red bars. Lighthouse will dock your performance score. But the developer has no alternative — CSS provides no API for computing text height without rendering it. The information is locked behind the DOM, and the DOM makes you pay for every answer.

Developers have invented increasingly desperate workarounds. Estimated heights replace real measurements with guesses, causing content to visibly jump when the guess is wrong. ResizeObserver watches elements for size changes, but it fires asynchronously and always at least one frame too late. IntersectionObserver tracks visibility but says nothing about dimensions. Content-visibility allows the browser to skip rendering off-screen elements, but it breaks scroll position and accessibility. Each workaround addresses one symptom while introducing new problems.

The CSS Shapes specification, finalized in 2014, was supposed to bring magazine-style text wrap to the web. It allows text to flow around a defined shape — a circle, an ellipse, a polygon, even an image alpha channel. On paper, it was the answer. In practice, it is remarkably limited. CSS Shapes only works with floated elements. Text can only wrap on one side of the shape. The shape must be defined statically in CSS — you cannot animate it or change it dynamically without triggering a full layout reflow. And because it operates within the browser’s layout engine, you have no access to the resulting line geometry. You cannot determine where each line of text starts and ends, how many lines were generated, or what the total height of the shaped text block is.

The editorial layouts we see in print magazines — text flowing around photographs, pull quotes interrupting the column, multiple columns with seamless text handoff — have remained out of reach for the web. Not because they are conceptually difficult, but because the performance cost of implementing them with DOM measurement makes them impractical. A two-column editorial layout that reflows text around three obstacle shapes requires measuring and positioning hundreds of text lines. At thirty milliseconds per measurement, this would take seconds — an eternity for a render frame.

What if text measurement did not require the DOM at all? What if you could compute exactly where every line of text would break, exactly how wide each line would be, and exactly how tall the entire text block would be, using nothing but arithmetic?

This is the core insight of pretext. The browser’s canvas API includes a measureText method that returns the width of any string in any font without triggering a layout reflow. Canvas measurement uses the same font engine as DOM rendering — the results are identical. But because it operates outside the layout tree, it carries no reflow penalty.

Pretext exploits this asymmetry. When text first appears, pretext measures every word once via canvas and caches the widths. After this preparation phase, layout is pure arithmetic: walk the cached widths, track the running line width, insert line breaks when the width exceeds the maximum, and sum the line heights. No DOM. No reflow. No layout tree access.

The performance improvement is not incremental. Measuring five hundred text blocks with DOM methods costs fifteen to thirty milliseconds and triggers five hundred layout reflows. With pretext, the same operation costs 0.05 milliseconds and triggers zero reflows. This is a three hundred to six hundred times improvement. But even that number understates the impact, because pretext’s cost does not scale with page complexity — it is independent of how many other elements exist on the page.

With DOM-free text measurement, an entire class of previously impractical interfaces becomes trivial. Text can flow around arbitrary shapes, not because the browser’s layout engine supports it, but because you control the line widths directly. For each line of text, you compute which horizontal intervals are blocked by obstacles, subtract them from the available width, and pass the remaining width to the layout engine. The engine returns the text that fits, and you position the line at the correct offset.

This is exactly what CSS Shapes tried to accomplish, but with none of its limitations. Obstacles can be any shape — rectangles, circles, arbitrary polygons, even the alpha channel of an image. Text wraps on both sides simultaneously. Obstacles can move, animate, or be dragged by the user, and the text reflows instantly because the layout computation takes less than a millisecond.

Shrinkwrap is another capability that CSS cannot express. Given a block of multiline text, what is the narrowest width that preserves the current line count? CSS offers fit-content, which works for single lines but always leaves dead space for multiline text. Pretext solves this with a binary search over widths: narrow until the line count increases, then back off. The result is the tightest possible bounding box — perfect for chat message bubbles, image captions, and tooltip text.

Virtualized text rendering becomes exact rather than estimated. A virtual list needs to know the height of items before they enter the viewport, so it can position them correctly and calculate scroll extent. Without pretext, you must either render items off-screen to measure them (defeating the purpose of virtualization) or estimate heights and accept visual jumping when items enter the viewport with different heights than predicted. Pretext computes exact heights without creating any DOM elements, enabling perfect virtualization with zero visual artifacts.

Multi-column text flow with cursor handoff is perhaps the most striking capability. The left column consumes text until it reaches the bottom, then hands its cursor to the right column. The right column picks up exactly where the left column stopped, with no duplication, no gap, and perfect line breaking at the column boundary. This is how newspapers and magazines work on paper, but it has never been achievable on the web without extreme hacks involving multiple elements, hidden overflow, and JavaScript-managed content splitting.

Pretext makes it trivial. Call layoutNextLine in a loop for the first column, using the column width. When the column is full, take the returned cursor and start a new loop for the second column. The cursor carries the exact position in the prepared text — which segment, which grapheme within that segment. The second column continues seamlessly from the first.

Adaptive headline sizing is a detail that separates professional typography from amateur layout. The headline should be as large as possible without breaking any word across lines. This requires a binary search: try a font size, measure the text, check if any line breaks occur within a word, and adjust. With DOM measurement, each iteration costs a reflow. With pretext, each iteration is a microsecond of arithmetic.

Real-time text reflow around animated obstacles is the ultimate stress test. The demonstration you are reading right now renders text that flows around multiple moving objects simultaneously, every frame, at sixty frames per second. Each frame, the layout engine computes obstacle intersections for every line of text, determines the available horizontal slots, lays out each line at the correct width and position, and updates the DOM with the results. The total computation time is typically under half a millisecond.

The glowing orbs drifting across this page are not decorative — they are the demonstration. Each orb is a circular obstacle. For every line of text, the engine checks whether the line’s vertical band intersects each orb. If it does, it computes the blocked horizontal interval and subtracts it from the available width. The remaining width might be split into two or more segments — and the engine fills every viable slot, flowing text on both sides of the obstacle simultaneously. This is something CSS Shapes cannot do at all.

All of this runs without a single DOM measurement. The line positions, widths, and text contents are computed entirely in JavaScript using cached font metrics. The only DOM writes are setting the left, top, and textContent of each line element — the absolute minimum required to show text on screen. The browser never needs to compute layout because all positioning is explicit.

This performance characteristic has profound implications for the web platform. For thirty years, the browser has been the gatekeeper of text information. If you wanted to know anything about how text would render — its width, its height, where its lines break — you had to ask the browser, and the browser made you pay for the answer with a layout reflow. This created an artificial scarcity of text information that constrained what interfaces could do.

Pretext removes that constraint. Text information becomes abundant and cheap. You can ask how text would look at a thousand different widths in the time it used to take to ask about one. You can recompute text layout every frame, every drag event, every pixel of window resize, without any performance concern.

The implications extend beyond layout into composition. When you have instant text measurement, you can build compositing engines that combine text with graphics, animation, and interaction in ways that were previously reserved for game engines and native applications. Text becomes a first-class participant in the visual composition, not a static block that the rest of the interface must work around.

Imagine a data visualization where labels reflow around chart elements as the user zooms and pans. Imagine a collaborative document editor where text flows around embedded widgets, images, and annotations placed by other users, updating live as they move things around. Imagine a map application where place names wrap intelligently around geographic features rather than overlapping them. These are not hypothetical — they are engineering problems that become solvable when text measurement costs a microsecond instead of thirty milliseconds.

The open web deserves typography that matches its ambition. We build applications that rival native software in every dimension except text. Our animations are smooth, our interactions are responsive, our graphics are stunning — but our text sits in rigid boxes, unable to flow around obstacles, unable to adapt to dynamic layouts, unable to participate in the fluid compositions that define modern interface design.

This is what changes when text measurement becomes free. Not slightly better — categorically different. The interfaces that were too expensive to build become trivial. The layouts that existed only in print become interactive. The text that sat in boxes begins to flow.

The web has been waiting thirty years for this. A fifteen kilobyte library with zero dependencies delivers it. No browser API changes needed. No specification process. No multi-year standardization timeline. Just math, cached measurements, and the audacity to ask: what if we simply stopped asking the DOM?

Fifteen kilobytes. Zero dependencies. Zero DOM reads. And the text flows.'''

PULLQUOTE_TEXTS = [
  "“The performance improvement is not incremental — it is categorical. 0.05ms versus 30ms. Zero reflows versus five hundred.”",
  "“Text becomes a first-class participant in the visual composition — not a static block, but a fluid material that adapts in real time.”"
]


orbDefs = [
    {'fx': 0.52, 'fy': 0.22, 'r': 110, 'vx': 24, 'vy': 16, 'color': [196, 163, 90]},
    {'fx': 0.18, 'fy': 0.48, 'r': 85, 'vx': -19, 'vy': 26, 'color': [100, 140, 255]},
    {'fx': 0.74, 'fy': 0.58, 'r': 95, 'vx': 16, 'vy': -21, 'color': [232, 100, 130]},
    {'fx': 0.38, 'fy': 0.72, 'r': 75, 'vx': -26, 'vy': -14, 'color': [80, 200, 140]},
    {'fx': 0.86, 'fy': 0.18, 'r': 65, 'vx': -13, 'vy': 19, 'color': [150, 100, 220]}
]


pygame.init()
info = pygame.display.Info()
W0, H0 = info.current_w, info.current_h - 44
# W0, H0 = 1200, 1000
screen = pygame.display.set_mode((W0, H0), pygame.RESIZABLE)
clock = pygame.time.Clock()

def blur_surface(surf, blur_radius):
    """对 Pygame 透明表面做高斯模糊，返回新表面"""
    raw = pygame.image.tobytes(surf.convert_alpha(), 'RGBA')
    pil_img = Image.frombytes('RGBA', surf.get_size(), raw)
    pil_img = pil_img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    return pil_img

def create_shadow_layer(radius, spread, blur, color, alpha):
    """
    创建一层发光（阴影）
    :param radius: 原始圆的半径
    :param spread:  阴影扩展距离（CSS 的 spread）
    :param blur:    高斯模糊半径（CSS 的 blur）
    :param color:   (r, g, b)
    :param alpha:   透明度（0~1，如 0.18）
    :return:        Pygame Surface（带透明通道）
    """
    shadow_r = radius + spread                 # 阴影圆的半径
    margin = int(blur * 3)                     # 留出模糊距离
    size = (shadow_r + margin) * 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)

    center = size // 2
    rgba = (*color, int(alpha * 255))
    pygame.draw.circle(surf, rgba, (center, center), shadow_r)

    return blur_surface(surf, blur)

def create_circle_surf(color, radius):
    R, G, B = color
    size = 2 * radius          # 正方形边长
    cx = 0.35 * size           # 渐变圆心 x
    cy = 0.35 * size           # 渐变圆心 y
    center_x = radius          # 元素中心 x
    center_y = radius          # 元素中心 y

    # 创建坐标网格
    x = np.arange(size, dtype=np.float32)
    y = np.arange(size, dtype=np.float32)
    X, Y = np.meshgrid(x, y)

    # 到渐变圆心的距离
    dx = X - cx
    dy = Y - cy
    dist = np.sqrt(dx*dx + dy*dy)

    # 渐变半径（最远角）
    grad_radius = np.sqrt((size - cx)**2 + (size - cy)**2)

    # 归一化距离 t ∈ [0, 1]
    t = dist / grad_radius
    # 防止除零（当圆心在角上时），但此处不会
    t = np.clip(t, 0.0, 1.0)

    # 计算透明度 alpha (0~255)
    alpha = np.zeros_like(t, dtype=np.float32)

    # 分段线性插值
    # t <= 0.55: 0.35 -> 0.12
    mask1 = t <= 0.55
    alpha[mask1] = 0.35 + (0.12 - 0.35) * (t[mask1] / 0.55)

    # 0.55 < t <= 0.72: 0.12 -> 0
    mask2 = (t > 0.55) & (t <= 0.72)
    t2 = (t[mask2] - 0.55) / (0.72 - 0.55)
    alpha[mask2] = 0.12 * (1.0 - t2)   # 线性到0

    # t > 0.72 保持为0

    # 圆形裁剪：只保留以 (radius, radius) 为圆心、半径 radius 的圆内像素
    dx_center = X - center_x
    dy_center = Y - center_y
    inside = np.sqrt(dx_center*dx_center + dy_center*dy_center) <= radius
    alpha = alpha * inside.astype(np.float32)

    # 转为 uint8
    alpha = np.clip(alpha * 255, 0, 255).astype(np.uint8)
    
    shadow1 = create_shadow_layer(radius, spread=15, blur=60, color=color, alpha=0.18)
    # shadow2 = create_shadow_layer(radius, spread=40, blur=120, color=color, alpha=0.07)
    # shadow2.alpha_composite(shadow1, dest=((shadow2.width - shadow1.width) // 2, (shadow2.height - shadow1.height) // 2))
    shadow2 = shadow1
    shadow_surf = pygame.image.fromstring(shadow2.tobytes(), shadow2.size, shadow2.mode)
    shadow_arr = pygame.surfarray.pixels3d(shadow_surf)
    shadow_alpha = pygame.surfarray.pixels_alpha(shadow_surf)
    sw, sh = shadow_surf.get_size()
    left, top = (sw - size) // 2, (sh - size) // 2
    shadow_arr[left: left + size, top: top + size, 0][inside] = R
    shadow_arr[left: left + size, top: top + size, 1][inside] = G
    shadow_arr[left: left + size, top: top + size, 2][inside] = B
    shadow_alpha[left: left + size, top: top + size][inside] = alpha[inside]
    
    return shadow_surf


def create_orb_surf(d):
    sf = create_circle_surf(d['color'], d['r'])
    new_sf = sf.copy()
    arr = pygame.surfarray.pixels_alpha(new_sf)
    arr[:, :] = (arr * 0.45).astype(np.uint8)
    return sf.convert_alpha(), new_sf.convert_alpha()

orbs = [
    {
        'x': d['fx'] * W0,
        'y': d['fy'] * H0,
        'r': d['r'],
        'vx': d['vx'],
        'vy': d['vy'],
        'color': d['color'],
        'paused': False,
        'dragging': False,
        'dragStartX': 0,
        'dragStartY': 0,
        'dragStartOrbX': 0,
        'dragStartOrbY': 0,
        'surface': create_orb_surf(d)
    }
    for d in orbDefs
]

preparedBody = prepareWithSegments(BODY_TEXT, BODY_FONT)
PQ_FONT = f'italic 19px {HEADLINE_FONT_FAMILY}'
PQ_LINE_HEIGHT = 27

preparedPQ = [prepareWithSegments(t, PQ_FONT) for t in PULLQUOTE_TEXTS]

def get_clip_rows(surface):
    height = surface.get_height()

    alpha_arr = pygame.surfarray.array_alpha(surface).swapaxes(0, 1)
    
    top = 0
    while top < height and np.all(alpha_arr[top] == 0):
        top += 1
    
    bottom = height - 1
    while bottom >= 0 and np.all(alpha_arr[bottom] == 0):
        bottom -= 1
    
    if top == height and bottom == -1:
        raise RuntimeError

    return bottom + top

DROP_CAP_SIZE = BODY_LINE_HEIGHT * DROP_CAP_LINES - 4
DROP_CAP_FONT = f"700 {DROP_CAP_SIZE}px {HEADLINE_FONT_FAMILY}"
preparedDropCap = prepareWithSegments(BODY_TEXT[0], DROP_CAP_FONT)
dropCapWidth = 0

def capture_width(line):
    global dropCapWidth
    dropCapWidth = line['width']

walkLineRanges(preparedDropCap, 9999, capture_width)
DROP_CAP_TOTAL_W = math.ceil(dropCapWidth) + 10

ctx.font = DROP_CAP_FONT
font = ctx.get_font()
drop_sf = font.render(BODY_TEXT[0], True, (0xc4, 0xa3, 0x5a))
drop_sf = drop_sf.subsurface(pygame.Rect(0, 0, drop_sf.get_width(), get_clip_rows(drop_sf)))

cachedHeadlineKey = ""
cachedHeadlineFontSize = 24
cachedHeadlineLines = []

def fitHeadline(maxWidth, maxHeight):
    global cachedHeadlineKey, cachedHeadlineFontSize, cachedHeadlineLines
    key = f"{maxWidth}:{maxHeight}"
    if key == cachedHeadlineKey:
        return {'fontSize': cachedHeadlineFontSize, 'lines': cachedHeadlineLines}
    cachedHeadlineKey = key
    lo, hi = 24, 120
    best = lo
    bestLines = []
    while lo <= hi:
        size = (lo + hi) // 2
        font = f"700 {size}px {HEADLINE_FONT_FAMILY}"
        lh = round(size * 0.93)
        prepared = prepareWithSegments(HEADLINE_TEXT, font)
        breaksWord = False
        lineCount = 0

        def line_callback(line):
            nonlocal lineCount, breaksWord
            lineCount += 1
            if line['end']['graphemeIndex'] != 0:
                breaksWord = True

        walkLineRanges(prepared, maxWidth, line_callback)
        totalH = lineCount * lh
        if not breaksWord and totalH <= maxHeight:
            best = size
            result = layoutWithLines(prepared, maxWidth, lh)
            bestLines = [
                {'x': 0, 'y': i * lh, 'text': line['text'], 'width': line['width']}
                for i, line in enumerate(result['lines'])
            ]
            lo = size + 1
        else:
            hi = size - 1
    cachedHeadlineFontSize = best
    cachedHeadlineLines = bestLines
    return {'fontSize': best, 'lines': bestLines}


def layoutColumn(prepared, startCursor, regionX, regionY, regionW, regionH, lineHeight, circleObs, rectObstacles):
    cursor = startCursor.copy()
    lineTop = regionY
    lines = []
    textExhausted = False

    while lineTop + lineHeight <= regionY + regionH and not textExhausted:
        bandTop = lineTop
        bandBottom = lineTop + lineHeight
        blocked = []

        for c in circleObs:
            cx, cy, r, hPad, vPad = c['cx'], c['cy'], c['r'], c['hPad'], c['vPad']
            top = bandTop - vPad
            bottom = bandBottom + vPad
            if top >= cy + r or bottom <= cy - r:
                continue
            if cy >= top and cy <= bottom:
                minDy = 0
            elif cy < top:
                minDy = top - cy
            else:
                minDy = cy - bottom
            if minDy >= r:
                continue
            maxDx = (r * r - minDy * minDy) ** 0.5
            iv = {'left': cx - maxDx - hPad, 'right': cx + maxDx + hPad}
            blocked.append(iv)

        for r in rectObstacles:
            if bandBottom <= r['y'] or bandTop >= r['y'] + r['h']:
                continue
            blocked.append({'left': r['x'], 'right': r['x'] + r['w']})

        slots = carveTextLineSlots({'left': regionX, 'right': regionX + regionW}, blocked)
        if not slots:
            lineTop += lineHeight
            continue

        slots.sort(key=lambda s: s['left'])
        for slot in slots:
            slotWidth = slot['right'] - slot['left']
            line = layoutNextLine(prepared, cursor, slotWidth)
            if line is None:
                textExhausted = True
                break
            lines.append({
                'x': round(slot['left']),
                'y': round(lineTop),
                'text': line['text'],
                'width': line['width']
            })
            cursor = line['end'].copy()

        lineTop += lineHeight

    return {'lines': lines, 'cursor': cursor}

activeOrb: dict = None
pointerX = -9999
pointerY = -9999

def hitTestOrbs(px, py):
    for i in range(len(orbs) - 1, -1, -1):
        o = orbs[i]
        dx = px - o['x']
        dy = py - o['y']
        if dx * dx + dy * dy <= o['r'] * o['r']:
            return o
    return None

def pointerdown(_event):
    global activeOrb
    orb = hitTestOrbs(*_event.pos);
    if orb:
        activeOrb = orb
        orb['dragging'] = True
        orb['dragStartX'], orb['dragStartY'] = _event.pos
        orb['dragStartOrbX'] = orb['x']
        orb['dragStartOrbY'] = orb['y']


def pointermove(_event):
    global pointerX, pointerY
    pointerX, pointerY = _event.pos
    if activeOrb:
        activeOrb['x'] = activeOrb['dragStartOrbX'] + (_event.pos[0] - activeOrb['dragStartX'])
        activeOrb['y'] = activeOrb['dragStartOrbY'] + (_event.pos[1] - activeOrb['dragStartY'])


def pointerup(_event):
    global activeOrb
    if activeOrb is not None:
        dx = _event.pos[0] - activeOrb['dragStartX']
        dy = _event.pos[1] - activeOrb['dragStartY']
        if dx * dx + dy * dy < 16:
            activeOrb['paused'] = not activeOrb['paused']

        activeOrb['dragging'] = False
        clear_active_orb()


def clear_active_orb():
    global activeOrb
    activeOrb = None
    

_current_cursor_state = None
def update_cursor():
    global _current_cursor_state
    
    if activeOrb:
        new_state = "grabbing"
        cursor_type = pygame.SYSTEM_CURSOR_SIZEALL  
    elif hitTestOrbs(pointerX, pointerY):
        new_state = "grab"
        cursor_type = pygame.SYSTEM_CURSOR_HAND
    else:
        new_state = "default"
        cursor_type = pygame.SYSTEM_CURSOR_ARROW

    if _current_cursor_state != new_state:
        pygame.mouse.set_cursor(cursor_type)
        _current_cursor_state = new_state


lastTime = 0
def animate(surface, now):
    global lastTime
    dt = min((now - lastTime) / 1000, 0.05)
    lastTime = now
    pw = W0
    ph = H0
    for i in range(len(orbs)):
        o = orbs[i]
        if o['paused'] or o['dragging']:
            continue
        o['x'] += o['vx'] * dt
        o['y'] += o['vy'] * dt
        if o['x'] - o['r'] < 0:
            o['x'] = o['r']
            o['vx'] = abs(o['vx'])
        if o['x'] + o['r'] > pw:
            o['x'] = pw - o['r']
            o['vx'] = -abs(o['vx'])
        if o['y'] - o['r'] < GUTTER * 0.5:
            o['y'] = o['r'] + GUTTER * 0.5
            o['vy'] = abs(o['vy'])
        if o['y'] + o['r'] > ph - STATS_BAR_HEIGHT:
            o['y'] = ph - STATS_BAR_HEIGHT - o['r']
            o['vy'] = -abs(o['vy'])
    
    for i in range(len(orbs)):
        a = orbs[i]
        for j in range(i + 1, len(orbs)):
            b = orbs[j]
            dx = b['x'] - a['x']
            dy = b['y'] - a['y']
            dist = math.sqrt(dx * dx + dy * dy)
            minDist = a['r'] + b['r'] + 20
            if dist < minDist and dist > 0.1:
                force = (minDist - dist) * 0.8
                nx = dx / dist
                ny = dy / dist
                if not a['paused'] and not a['dragging']:
                    a['vx'] -= nx * force * dt
                    a['vy'] -= ny * force * dt
                if not b['paused'] and not b['dragging']:
                    b['vx'] += nx * force * dt
                    b['vy'] += ny * force * dt
    
    circleObs = []
    for o in orbs:
        circleObs.append({
            'cx': o['x'],
            'cy': o['y'],
            'r': o['r'],
            'hPad': 14,
            'vPad': 4
        })
    # t0 = pygame.time.get_ticks()
    headlineWidth = min(pw - GUTTER * 2, 1000)
    maxHeadlineH = math.floor(ph * 0.35)
    result = fitHeadline(headlineWidth, maxHeadlineH)
    hlSize = result['fontSize']
    hlLines = result['lines']
    hlLineHeight = round(hlSize * 0.93)
    hlFont = f"700 {hlSize}px {HEADLINE_FONT_FAMILY}"
    hlHeight = len(hlLines) * hlLineHeight
    ctx.font = hlFont
    font = ctx.get_font()
    
    for line in hlLines:
        sf = font.render(str(line['text']), True, (255,255,255))
        surface.blit(sf, sf.get_rect(left=int(GUTTER), centery=int(GUTTER + line['y'] + hlLineHeight / 2)))
    
    bodyTop = GUTTER + hlHeight + 20
    bodyHeight = ph - bodyTop - STATS_BAR_HEIGHT - 8
    colCount = 3 if pw > 1000 else (2 if pw > 640 else 1)
    totalGutter = GUTTER * 2 + COL_GAP * (colCount - 1)
    maxContentW = min(pw, 1500)
    colWidth = math.floor((maxContentW - totalGutter) / colCount)
    contentLeft = round((pw - (colCount * colWidth + (colCount - 1) * COL_GAP)) / 2)
    col0X = contentLeft
    dropCapRect = {
        'x': col0X - 2,
        'y': bodyTop - 2,
        'w': DROP_CAP_TOTAL_W,
        'h': DROP_CAP_LINES * BODY_LINE_HEIGHT + 2
    }
    # pygame.draw.rect(surface, 'red', pygame.Rect(dropCapRect['x'], dropCapRect['y'], dropCapRect['w'], dropCapRect['h']))
    
    surface.blit(drop_sf, drop_sf.get_rect(left=int(col0X), centery=int(bodyTop + DROP_CAP_SIZE / 2)))
 
    pqPlacements = [
        {"colIdx": 0, "yFrac": 0.48, "wFrac": 0.52, "side": "right"},
        {"colIdx": min(1, colCount - 1), "yFrac": 0.32, "wFrac": 0.5, "side": "left"}
    ]
    
    pqRects = []
    for pi in range(len(pqPlacements)):
        p = pqPlacements[pi]
        if p["colIdx"] >= colCount:
            continue
        pqW = round(colWidth * p["wFrac"])
        prepared = preparedPQ[pi]
        result = layout(prepared, pqW - 20, PQ_LINE_HEIGHT)
        pqH = result["height"] + 16
        colX = contentLeft + p["colIdx"] * (colWidth + COL_GAP)
        pqX = colX + colWidth - pqW if p["side"] == "right" else colX
        pqY = round(bodyTop + bodyHeight * p["yFrac"])
        pqLayoutLines = layoutWithLines(prepared, pqW - 20, PQ_LINE_HEIGHT)
        pqPosLines = [
            {
                "x": pqX + 20,
                "y": pqY + 8 + i * PQ_LINE_HEIGHT,
                "text": l["text"],
                "width": l["width"]
            }
            for i, l in enumerate(pqLayoutLines["lines"])
        ]
        pqRects.append({
            "x": pqX,
            "y": pqY,
            "w": pqW,
            "h": pqH,
            "lines": pqPosLines,
            "colIdx": p["colIdx"]
        })
    
    allBodyLines = []
    cursor = {"segmentIndex": 0, "graphemeIndex": 1}
    # return 
    
    for col in range(colCount):
        colX = contentLeft + col * (colWidth + COL_GAP)
        rects = []
        if col == 0:
            rects.append(dropCapRect)
        for pq in pqRects:
            if pq["colIdx"] == col:
                rects.append({"x": pq["x"], "y": pq["y"], "w": pq["w"], "h": pq["h"]})
        result = layoutColumn(
            preparedBody, cursor, colX, bodyTop, colWidth, bodyHeight,
            BODY_LINE_HEIGHT, circleObs, rects
        )
        allBodyLines.extend(result["lines"])
        cursor = result["cursor"]
     
    # reflowTime = pygame.time.get_ticks() - t0;
    # return
    ctx.font = BODY_FONT
    font = ctx.get_font() 
    
    for line in allBodyLines:
        sf = font.render(str(line['text']), True, (0xe8, 0xe4, 0xdc))
        surface.blit(sf, sf.get_rect(left=int(line['x']), centery=int(line['y'] + BODY_LINE_HEIGHT / 2)))
    
    for o in orbs:
        _paused = o['paused']
        _sf = o['surface'][_paused]
        surface.blit(_sf, _sf.get_rect(center=(int(o['x']), int(o['y']))))
        
    totalPQLines = 0
    for pqr in pqRects:
        totalPQLines += len(pqr['lines'])

    ctx.font = PQ_FONT
    font = ctx.get_font()
    for pq in pqRects:
        pygame.draw.rect(surface, (0x6b, 0x5a, 0x3d), (pq['x'], pq['y'], 3, pq['h']))
        
        for line in pq['lines']:
            sf = font.render(str(line['text']), True, (0xb8, 0xa0, 0x70))
            surface.blit(sf, sf.get_rect(left=int(line['x']), centery=int(line['y'] + PQ_LINE_HEIGHT / 2)))
    
    update_cursor()


def drawFPS(surface):
    ctx.font = BODY_FONT
    font = ctx.get_font()
    img = font.render(str(round(clock.get_fps())) + ' FPS', True, (0x66, 0x66, 0x66))
    surface.blit(img, (20, 40))


running = True
# _w0, _h0 = W0, H0
while running:
    # _scale = (math.sin(lastTime * 0.001) - 1) * 500
    # _scale1 = (math.sin((lastTime + 30) * 0.002) - 1) * 500
    # assert _scale <= 0
    # assert _scale1 <= 0
    # W0, H0 = _w0 + _scale, _h0 + _scale1
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.VIDEORESIZE:
            W0, H0 = event.w, event.h
            screen = pygame.display.set_mode((W0, H0), pygame.RESIZABLE)
        elif event.type == pygame.MOUSEMOTION:
            pointermove(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            pointerdown(event)
        elif event.type == pygame.MOUSEBUTTONUP:
            pointerup(event)

    screen.fill((0x0f, 0x0f, 0x14))
    
    animate(screen, pygame.time.get_ticks())
    drawFPS(screen)
    # pygame.draw.rect(screen, (255, 0, 0), (0, 0, W0, H0), 2)
    pygame.display.flip()
    clock.tick(114514)

pygame.quit()
sys.exit()
