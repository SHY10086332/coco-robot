"""
Coco 导购机器人 — 2D 概念效果图 v6.2 (双轴云台 pan+tilt)
总高 ~1060mm, 200mm圆屏, 屏高~840mm, 履带底盘, SG90×2双轴追踪
"""

import math
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1200, 1900
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# ===== 颜色 =====
C_BG_TOP = (30, 35, 50)
C_BG_BOT = (60, 65, 80)
C_WHITE = (245, 245, 250)
C_BLUE = (74, 144, 217)
C_BLUE_DK = (44, 95, 138)
C_BLUE_LT = (100, 170, 240)
C_CYAN = (0, 255, 208)
C_SCREEN_BG = (10, 12, 18)
C_BLACK = (20, 20, 25)
C_DK_GRAY = (40, 42, 48)
C_GRAY = (60, 62, 68)
C_LT_GRAY = (130, 135, 145)
C_SILVER = (220, 225, 235)
C_GOLD = (255, 215, 0)
C_GOLD_LT = (255, 240, 100)
C_TRACK = (28, 30, 33)
C_RUBBER = (22, 22, 25)
C_SENSOR = (50, 52, 58)
C_RED = (255, 80, 60)


def gradient_bg(draw, top, bottom, c_top, c_bot):
    for y in range(top, bottom):
        t = (y - top) / (bottom - top)
        r = int(c_top[0] + (c_bot[0] - c_top[0]) * t)
        g = int(c_top[1] + (c_bot[1] - c_top[1]) * t)
        b = int(c_top[2] + (c_bot[2] - c_top[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

def soft_circle(draw, center, radius, fill_color, blur_radius=2):
    radius = int(radius)
    size = int(radius * 6)
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    ox, oy = size // 2, size // 2
    odraw.ellipse([ox - radius, oy - radius, ox + radius, oy + radius], fill=fill_color)
    blurred = overlay.filter(ImageFilter.GaussianBlur(blur_radius))
    px = int(center[0] - size // 2)
    py = int(center[1] - size // 2)
    img.paste(blurred, (px, py), blurred)

def draw_round_rect(draw, bbox, radius, fill):
    x0, y0, x1, y1 = bbox
    r = radius
    draw.rectangle([x0 + r, y0, x1 - r, y1], fill=fill)
    draw.rectangle([x0, y0 + r, x1, y1 - r], fill=fill)
    draw.pieslice([x0, y0, x0 + 2*r, y0 + 2*r], 180, 270, fill=fill)
    draw.pieslice([x1 - 2*r, y0, x1, y0 + 2*r], 270, 360, fill=fill)
    draw.pieslice([x0, y1 - 2*r, x0 + 2*r, y1], 90, 180, fill=fill)
    draw.pieslice([x1 - 2*r, y1 - 2*r, x1, y1], 0, 90, fill=fill)


# ===== 1. 背景 =====
gradient_bg(draw, 0, H, C_BG_TOP, C_BG_BOT)
soft_circle(draw, (W // 2, 550), 380, (74, 144, 217, 20), blur_radius=40)
soft_circle(draw, (W // 2, 550), 220, (0, 255, 208, 12), blur_radius=30)
overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
odraw = ImageDraw.Draw(overlay)
odraw.ellipse([W//2 - 300, 1520, W//2 + 300, 1620], fill=(100, 160, 220, 18))
img.paste(overlay, (0, 0), overlay)

# ===== 2. 地面投影 =====
overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
odraw = ImageDraw.Draw(overlay)
odraw.ellipse([W//2 - 240, 1540, W//2 + 240, 1610], fill=(0, 0, 0, 70))
img.paste(overlay.filter(ImageFilter.GaussianBlur(15)), (0, 0),
          overlay.filter(ImageFilter.GaussianBlur(15)))

# ===== 3. 履带底盘 =====
cx = W // 2
chassis_top = 1320
chassis_w = 460
chassis_h = 105

draw_round_rect(draw,
    [cx - chassis_w//2, chassis_top, cx + chassis_w//2, chassis_top + chassis_h],
    16, C_DK_GRAY)

overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
odraw = ImageDraw.Draw(overlay)
odraw.rounded_rectangle(
    [cx - chassis_w//2 + 8, chassis_top + 4, cx + chassis_w//2 - 8, chassis_top + 48],
    radius=12, fill=(80, 85, 95, 90))
img.paste(overlay, (0, 0), overlay)

for side in [-1, 1]:
    sx = cx + side * 190
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.rounded_rectangle(
        [sx - 28, chassis_top + 10, sx + 28, chassis_top + chassis_h - 10],
        radius=22, fill=C_TRACK)
    img.paste(overlay, (0, 0), overlay)
    for y_offset in range(0, chassis_h - 20, 13):
        draw.line([(sx - 24, chassis_top + 14 + y_offset),
                   (sx + 24, chassis_top + 14 + y_offset)],
                  fill=(48, 50, 53), width=2)
    for wy in [chassis_top + 30, chassis_top + chassis_h - 30]:
        draw.ellipse([sx - 20, wy - 20, sx + 20, wy + 20], fill=(58, 60, 66))
        draw.ellipse([sx - 16, wy - 16, sx + 16, wy + 16], fill=(48, 50, 54))
        draw.ellipse([sx - 5, wy - 5, sx + 5, wy + 5], fill=C_LT_GRAY)
        for a in range(6):
            angle = a * math.pi / 3
            hx = sx + int(10 * math.cos(angle))
            hy = wy + int(10 * math.sin(angle))
            draw.ellipse([hx - 4, hy - 4, hx + 4, hy + 4], fill=(38, 40, 44))
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.rounded_rectangle(
        [sx - 24, chassis_top + 20, sx + 24, chassis_top + chassis_h - 20],
        radius=18, fill=None, outline=C_RUBBER, width=6)
    img.paste(overlay, (0, 0), overlay)

# ===== 4. 机身主体 (v6.2: 更高, 700mm) =====
body_top = 640
body_w = 400
body_h = 700
body_cx = cx
body_bottom = chassis_top + 20

overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
odraw = ImageDraw.Draw(overlay)
odraw.rounded_rectangle(
    [body_cx - body_w//2, body_top, body_cx + body_w//2, body_bottom],
    radius=55, fill=C_WHITE)
img.paste(overlay, (0, 0), overlay)

overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
odraw = ImageDraw.Draw(overlay)
odraw.rounded_rectangle(
    [body_cx - body_w//2 + 5, body_top + 10, body_cx + 5, body_bottom - 10],
    radius=45, fill=(190, 195, 205, 50))
img.paste(overlay, (0, 0), overlay)

overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
odraw = ImageDraw.Draw(overlay)
odraw.ellipse([body_cx + 50, body_top + 20, body_cx + 180, body_top + 250],
              fill=(255, 255, 255, 35))
img.paste(overlay, (0, 0), overlay)

# 正面内凹面板
overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
odraw = ImageDraw.Draw(overlay)
odraw.ellipse([body_cx - 170, body_top + 15, body_cx + 170, body_top + 240],
              fill=(235, 238, 243, 100))
img.paste(overlay, (0, 0), overlay)

# 装饰环
def trim_ring(y, w_scale=1.0):
    rw = int((body_w + 40) * w_scale)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.rounded_rectangle([body_cx - rw//2, y - 6, body_cx + rw//2, y + 6],
                            radius=10, fill=C_BLUE)
    odraw.rounded_rectangle([body_cx - rw//2 + 15, y - 2, body_cx + rw//2 - 15, y + 1],
                            radius=4, fill=C_BLUE_LT)
    img.paste(overlay, (0, 0), overlay)

trim_ring(body_top + 8)
trim_ring(body_bottom - 8)
trim_ring(body_top + 300)   # 分段标记环
trim_ring(body_top + 530)   # 分段标记环

# ===== 5. 蝴蝶结 =====
bow_y = body_top + body_h * 0.55 + 30  # 下移适配更高机身
bow_cx = body_cx + body_w//2 - 55

draw.ellipse([bow_cx - 50, bow_y - 32, bow_cx - 5, bow_y + 30], fill=C_BLUE_DK)
draw.ellipse([bow_cx - 42, bow_y - 22, bow_cx - 13, bow_y + 20], fill=(55, 110, 160))
draw.ellipse([bow_cx + 5, bow_y - 32, bow_cx + 50, bow_y + 30], fill=C_BLUE_DK)
draw.ellipse([bow_cx + 13, bow_y - 22, bow_cx + 42, bow_y + 20], fill=(55, 110, 160))
draw.ellipse([bow_cx - 14, bow_y - 14, bow_cx + 14, bow_y + 14], fill=C_BLUE_DK)
draw.ellipse([bow_cx - 8, bow_y - 8, bow_cx + 8, bow_y + 8], fill=(55, 110, 160))
for dx in [-1, 1]:
    draw.polygon([
        (bow_cx + dx * 5, bow_y + 10),
        (bow_cx + dx * 22, bow_y + 55),
        (bow_cx + dx * 12, bow_y + 60),
        (bow_cx + dx * 2, bow_y + 18),
    ], fill=C_BLUE_DK)

# ===== 6. 头部后壳 (v6.2: pan-tilt云台) =====
head_cy = body_top - 30
head_rx = 220
head_ry = 150

overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
odraw = ImageDraw.Draw(overlay)
odraw.ellipse([cx - head_rx, head_cy - head_ry, cx + head_rx, head_cy + head_ry],
              fill=C_WHITE)
img.paste(overlay, (0, 0), overlay)

overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
odraw = ImageDraw.Draw(overlay)
odraw.ellipse([cx - head_rx + 5, head_cy - head_ry + 10, cx - 10, head_cy + head_ry - 10],
              fill=(195, 200, 210, 45))
img.paste(overlay, (0, 0), overlay)

# ===== 7. 屏幕面板 (28°仰角, 双轴云台自适应5°~55°) =====
tilt = 28  # 当前仰角
vf = math.cos(math.radians(tilt))  # 纵向压缩因子 ≈ 0.883
screen_cx = cx - 15
screen_cy = body_top + 80   # v6.2: 屏幕在pan-tilt云台上, 中心高~840mm
screen_rx = 148          # 水平半径 (不变)
screen_ry = 148 * vf     # 垂直半径 (压缩)

def draw_tilted_ellipse(cx, cy, rx, ry, fill, outline=None, width=1):
    """绘制倾斜屏幕中的椭圆（纵向压缩）"""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    bbox = [cx - rx, cy - ry, cx + rx, cy + ry]
    if fill:
        odraw.ellipse(bbox, fill=fill)
    if outline:
        odraw.ellipse(bbox, fill=None, outline=outline, width=width)
    img.paste(overlay, (0, 0), overlay)

# 凹陷阴影（屏幕上方内部阴影，表明显屏倾斜陷入）
overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
odraw = ImageDraw.Draw(overlay)
# 顶部深色弧形 — 屏幕上方陷入机身
for i in range(20):
    t = i / 20
    alpha = int(25 * (1 - t))
    odraw.ellipse([
        screen_cx - screen_rx - 17 + i*0.5, screen_cy - screen_ry - 15 + i,
        screen_cx + screen_rx + 17 - i*0.5, screen_cy - screen_ry + 8 + i
    ], fill=(0, 0, 0, alpha))
img.paste(overlay, (0, 0), overlay)

# 外框投影
soft_circle(draw, (screen_cx + 3, screen_cy + 5), int(screen_rx + 18),
            (0, 0, 0, 30), blur_radius=5)

# 外框（银色金属 — 倾斜所以用椭圆）
draw_tilted_ellipse(screen_cx, screen_cy, screen_rx + 16, screen_ry + 16,
                    fill=C_SILVER)
draw_tilted_ellipse(screen_cx, screen_cy, screen_rx + 12, screen_ry + 12,
                    fill=None, outline=(255, 255, 255, 55), width=3)
draw_tilted_ellipse(screen_cx, screen_cy, screen_rx + 4, screen_ry + 4,
                    fill=(180, 185, 195))
draw_tilted_ellipse(screen_cx, screen_cy, screen_rx, screen_ry,
                    fill=C_SCREEN_BG)

# 屏幕底部高光（倾斜后底部更突出，受光更多）
overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
odraw = ImageDraw.Draw(overlay)
odraw.ellipse([screen_cx - screen_rx + 40, screen_cy + screen_ry*0.3,
               screen_cx + screen_rx - 40, screen_cy + screen_ry + 2],
              fill=(255, 255, 255, 12))
img.paste(overlay, (0, 0), overlay)

# === Coco 表情 (纵轴压缩匹配倾斜) ===
eye_rx = screen_rx * 0.24
eye_ry = screen_ry * 0.24

for ex in [-1, 1]:
    exc = screen_cx + ex * screen_rx * 0.32
    eyc = screen_cy - screen_ry * 0.05

    # 眼睛
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.ellipse([exc - eye_rx, eyc - eye_ry * 1.25,
                   exc + eye_rx, eyc + eye_ry * 1.25],
                  fill=(0, 255, 208, 225))
    img.paste(overlay, (0, 0), overlay)

    # 瞳孔
    prx = screen_rx * 0.09
    pry = screen_ry * 0.09
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.ellipse([exc - prx, eyc - pry + 1, exc + prx, eyc + pry + 1], fill=C_BLACK)
    img.paste(overlay, (0, 0), overlay)

    # 高光
    hrx = screen_rx * 0.04
    hry = screen_ry * 0.04
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.ellipse([exc + prx * 0.3 - hrx, eyc - pry * 0.5 - hry,
                   exc + prx * 0.3 + hrx, eyc - pry * 0.5 + hry],
                  fill=(255, 255, 255, 235))
    img.paste(overlay, (0, 0), overlay)

# 微笑
sm_rx = screen_rx * 0.30
sm_ry = screen_ry * 0.30
sm_x = screen_cx
sm_y = screen_cy + screen_ry * 0.28
overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
odraw = ImageDraw.Draw(overlay)
odraw.ellipse([sm_x - sm_rx, sm_y - sm_ry, sm_x + sm_rx, sm_y + sm_ry],
              fill=(0, 255, 208, 215))
img.paste(overlay, (0, 0), overlay)
overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
odraw = ImageDraw.Draw(overlay)
odraw.ellipse([sm_x - sm_rx * 1.1, sm_y - sm_ry * 0.8,
               sm_x + sm_rx * 1.1, sm_y + sm_ry * 1.1],
              fill=C_SCREEN_BG)
img.paste(overlay, (0, 0), overlay)

# 腮红
for ex in [-1, 1]:
    soft_circle(draw, (screen_cx + ex * screen_rx * 0.58, screen_cy + screen_ry * 0.45),
                int(screen_rx * 0.10), (255, 120, 140, 35), blur_radius=3)

# ===== 8. 麦克风阵列 (屏幕下方，不倾斜保持水平) =====
mic_cx = screen_cx
mic_cy = screen_cy + screen_ry + 28
overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
odraw = ImageDraw.Draw(overlay)
odraw.rounded_rectangle([mic_cx - 38, mic_cy - 10, mic_cx + 38, mic_cy + 10],
                        radius=6, fill=(25, 28, 32))
img.paste(overlay, (0, 0), overlay)
overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
odraw = ImageDraw.Draw(overlay)
odraw.rounded_rectangle([mic_cx - 36, mic_cy - 8, mic_cx + 36, mic_cy + 2],
                        radius=4, fill=(40, 43, 48))
img.paste(overlay, (0, 0), overlay)
for i in range(4):
    hx = mic_cx - 22 + i * 15
    hy = mic_cy + 4
    draw.ellipse([hx - 3, hy - 3, hx + 3, hy + 3], fill=(10, 11, 13))
    draw.ellipse([hx - 2, hy - 2, hx + 2, hy + 2], fill=(20, 21, 23))
draw.ellipse([mic_cx - 33, mic_cy - 7, mic_cx - 28, mic_cy - 2],
             fill=(0, 255, 136, 210))

# ===== 9. 传感器 =====
for angle in [-50, -130]:
    sens_x = body_cx + body_w//2 + 8
    sens_y = body_top + 65
    draw.ellipse([sens_x - 8, sens_y - 8, sens_x + 8, sens_y + 8], fill=C_SENSOR)
    draw.ellipse([sens_x - 4, sens_y - 4, sens_x + 4, sens_y + 4], fill=(100, 10, 10))

# ===== 10. 天线 =====
ant_base_x = cx
ant_base_y = head_cy - head_ry + 25
overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
odraw = ImageDraw.Draw(overlay)
odraw.ellipse([ant_base_x - 16, ant_base_y - 8, ant_base_x + 16, ant_base_y + 16],
              fill=C_BLUE_DK)
img.paste(overlay, (0, 0), overlay)
ant_top = ant_base_y - 75
draw.polygon([
    (ant_base_x - 6, ant_base_y),
    (ant_base_x + 6, ant_base_y),
    (ant_base_x + 3, ant_top),
    (ant_base_x - 3, ant_top),
], fill=C_BLUE_DK)
draw.line([(ant_base_x + 1, ant_base_y - 2), (ant_base_x + 1, ant_top + 2)],
          fill=C_BLUE_LT, width=2)
soft_circle(draw, (ant_base_x, ant_top - 12), 18, C_GOLD, blur_radius=1)
overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
odraw = ImageDraw.Draw(overlay)
odraw.ellipse([ant_base_x - 16, ant_top - 26, ant_base_x + 16, ant_top + 2], fill=C_GOLD)
img.paste(overlay, (0, 0), overlay)
overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
odraw = ImageDraw.Draw(overlay)
odraw.ellipse([ant_base_x - 6, ant_top - 22, ant_base_x + 8, ant_top - 12],
              fill=C_GOLD_LT)
img.paste(overlay, (0, 0), overlay)
soft_circle(draw, (ant_base_x, ant_top - 8), 32, (255, 215, 0, 25), blur_radius=8)

# ===== 11. 机械臂 =====
for side in [-1, 1]:
    abx = body_cx + side * (body_w//2 - 12)
    aby = body_top + 280
    draw.ellipse([abx - 26, aby - 26, abx + 26, aby + 26], fill=(80, 82, 88))
    draw.ellipse([abx - 22, aby - 22, abx + 22, aby + 22], fill=(100, 102, 108))
    for dx in [-1, 1]:
        for dy in [-1, 1]:
            draw.ellipse([abx + dx * 13 - 3, aby + dy * 13 - 3,
                          abx + dx * 13 + 3, aby + dy * 13 + 3], fill=(50, 52, 56))
    draw.polygon([
        (abx - 10, aby + 20), (abx + 10, aby + 20),
        (abx + 8, aby + 110), (abx - 8, aby + 110),
    ], fill=(60, 62, 68))
    draw.ellipse([abx - 14, aby + 105, abx + 14, aby + 133], fill=(70, 72, 78))
    ey = aby + 119
    fax = abx + side * 15
    draw.polygon([
        (fax - 7, ey), (fax + 7, ey),
        (fax + side * 25 + 5, ey + 65), (fax + side * 25 - 5, ey + 65),
    ], fill=(85, 87, 93))
    cw_x = fax + side * 25
    cw_y = ey + 70
    draw.ellipse([cw_x - 14, cw_y - 14, cw_x + 14, cw_y + 14], fill=C_RED)
    draw.ellipse([cw_x - 10, cw_y - 10, cw_x + 10, cw_y + 10], fill=(255, 130, 100))
    for a in [-1, 1]:
        draw.polygon([
            (cw_x + a * 4, cw_y - 10),
            (cw_x + a * 15, cw_y + 30),
            (cw_x + a * 8, cw_y + 30),
            (cw_x + a * 1, cw_y - 10),
        ], fill=C_RED)

# ===== 12. 文字 =====
try:
    font_lg = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 48)
    font_md = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 26)
    font_sm = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
except Exception:
    font_lg = font_md = font_sm = ImageFont.load_default()

title = "Coco v6.2 立式导购机器人 (双轴云台 Pan+Tilt 自适应追踪)"
tb = draw.textbbox((0, 0), title, font=font_lg)
tw = tb[2] - tb[0]
draw.text((cx - tw // 2, 50), title, fill=(255, 255, 255, 230), font=font_lg)

specs = [
    ("8寸圆屏 (5°~55°仰角)", screen_cx - screen_rx - 30, screen_cy),
    ("履带底盘", cx - 180, chassis_top + chassis_h // 2),
    ("麦克风", mic_cx + 50, mic_cy),
    ("天线", ant_base_x + 45, ant_top - 12),
    ("机械臂", body_cx - body_w//2 - 55, body_top + 320),
]
for label, lx, ly in specs:
    draw.ellipse([lx - 4, ly - 4, lx + 4, ly + 4], fill=(255, 255, 255, 200))
    draw.text((lx + 2, ly - 28), label, fill=(255, 255, 255, 170), font=font_sm)

footer = "v6.2 Floor-Standing  ·  8\" Screen @ ~840mm  ·  Dual-Axis Pan-Tilt (±50° pan, 5°~55° tilt)  ·  SG90×2 Servo Tracking  ·  Whisper + Qwen2.5 + CosyVoice"
fb = draw.textbbox((0, 0), footer, font=font_sm)
fw = fb[2] - fb[0]
draw.text((cx - fw // 2, H - 55), footer, fill=(255, 255, 255, 90), font=font_sm)

# ===== 13. 高度标尺 =====
# 总高标注线 (左侧)
lx = 30
top_y = ant_top - 18
bot_y = chassis_top + chassis_h
draw.line([(lx, top_y), (lx, bot_y)], fill=(255, 255, 255, 80), width=2)
draw.line([(lx - 10, top_y), (lx + 10, top_y)], fill=(255, 255, 255, 80), width=2)
draw.line([(lx - 10, bot_y), (lx + 10, bot_y)], fill=(255, 255, 255, 80), width=2)
h_label = f"~1060mm"
draw.text((lx + 12, (top_y + bot_y)//2 - 12), h_label, fill=(255, 255, 255, 130), font=font_md)

# ===== 导出 =====
output = "D:/claude/coco/design/coco_concept.png"
img_rgb = Image.new("RGB", (W, H), (30, 35, 50))
img_rgb.paste(img, (0, 0), img)
img_rgb.save(output, "PNG", quality=95)
print(f"Saved: {output}  ({W}×{H})")
