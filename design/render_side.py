"""
Coco v5 立式导购机器人 — 侧面效果图
展示屏幕28°仰角、机身蛋形轮廓、履带底盘
"""

import math
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1600, 1200
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# ===== 颜色 =====
C_BG_TOP = (30, 35, 50)
C_BG_BOT = (55, 60, 75)
C_WHITE = (245, 245, 250)
C_WHITE_SHD = (200, 205, 215)
C_BLUE = (74, 144, 217)
C_BLUE_DK = (44, 95, 138)
C_BLUE_LT = (100, 170, 240)
C_CYAN = (0, 255, 208)
C_SCREEN = (10, 12, 18)
C_BLACK = (20, 20, 25)
C_DK_GRAY = (40, 42, 48)
C_GRAY = (60, 62, 68)
C_SILVER = (210, 215, 225)
C_GOLD = (255, 215, 0)
C_GOLD_LT = (255, 240, 100)
C_TRACK = (28, 30, 33)
C_RUBBER = (22, 22, 25)
C_RED = (255, 80, 60)

# ===== 尺寸 (像素, 对应侧视图) =====
# 侧视图原点在左侧
GROUND_Y = 1080
CHASSIS_H = 76       # 底盘高
CHASSIS_L = 430      # 底盘长 (前后)
BODY_D = 200         # 机身深 (前后方向)
BODY_H = 480         # 机身可见高
BODY_TOP_D = 160     # 顶部深度(收窄)
BODY_X = 560         # 机身中心X
BODY_BOT_Y = GROUND_Y - CHASSIS_H + 8
BODY_TOP_Y = BODY_BOT_Y - BODY_H

SCREEN_R = 130       # 屏幕半径
SCREEN_TILT = 28     # 仰角度数
SCREEN_CX_OFFSET = 85  # 屏幕中心在机身正面偏前
SCREEN_CY = BODY_BOT_Y - BODY_H * 0.42

HEAD_RX = 160
HEAD_RY = 120
HEAD_CX = BODY_X - 10
HEAD_CY = BODY_TOP_Y - 15

ANT_BASE_X = HEAD_CX - 10
ANT_BASE_Y = HEAD_CY - HEAD_RY + 20


def gradient_bg(draw, top, bottom, c_top, c_bot):
    for y in range(top, bottom):
        t = (y - top) / (bottom - top)
        r = int(c_top[0] + (c_bot[0] - c_top[0]) * t)
        g = int(c_top[1] + (c_bot[1] - c_top[1]) * t)
        b = int(c_top[2] + (c_bot[2] - c_top[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

def soft_circle(cx, cy, r, fill_color, blur=2):
    r = int(r)
    s = int(r * 6)
    ov = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.ellipse([s//2 - r, s//2 - r, s//2 + r, s//2 + r], fill=fill_color)
    bv = ov.filter(ImageFilter.GaussianBlur(blur))
    img.paste(bv, (int(cx - s//2), int(cy - s//2)), bv)


# ===== 背景 =====
gradient_bg(draw, 0, H, C_BG_TOP, C_BG_BOT)
soft_circle(BODY_X, 500, 350, (74, 144, 217, 15), 40)
# 地面线
draw.line([(80, GROUND_Y), (W - 80, GROUND_Y)], fill=(255, 255, 255, 25), width=1)
# 地面阴影
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.ellipse([BODY_X - 300, GROUND_Y - 5, BODY_X + 300, GROUND_Y + 30], fill=(0, 0, 0, 60))
img.paste(ov.filter(ImageFilter.GaussianBlur(12)), (0, 0),
          ov.filter(ImageFilter.GaussianBlur(12)))


# ===== 1. 履带底盘 (侧视) =====
ch_x0 = BODY_X - CHASSIS_L // 2
ch_x1 = BODY_X + CHASSIS_L // 2
ch_y0 = GROUND_Y - CHASSIS_H

# 底盘主体
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.rounded_rectangle([ch_x0, ch_y0, ch_x1, GROUND_Y], radius=14, fill=C_DK_GRAY)
img.paste(ov, (0, 0), ov)

# 履带护罩
track_r = 36
track_cx1 = BODY_X - CHASSIS_L//2 + 60   # 前轮
track_cx2 = BODY_X + CHASSIS_L//2 - 60   # 后轮
for tcx in [track_cx1, track_cx2]:
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    # 护罩
    od.ellipse([tcx - track_r - 5, ch_y0 - 6, tcx + track_r + 5, ch_y0 + CHASSIS_H + 6],
               fill=C_TRACK)
    img.paste(ov, (0, 0), ov)
    # 驱动轮
    od2 = ImageDraw.Draw(img)
    od2.ellipse([tcx - track_r, ch_y0 + 8, tcx + track_r, ch_y0 + CHASSIS_H - 8],
                fill=C_RUBBER)
    od2.ellipse([tcx - track_r + 12, ch_y0 + 20, tcx + track_r - 12, ch_y0 + CHASSIS_H - 20],
                fill=C_GRAY)
    # 轴
    od2.ellipse([tcx - 6, ch_y0 + CHASSIS_H//2 - 10, tcx + 6, ch_y0 + CHASSIS_H//2 + 10],
                fill=C_SILVER)

# 履带环 (侧视)
for tcx in [track_cx1, track_cx2]:
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.ellipse([tcx - track_r - 1, ch_y0 + 6, tcx + track_r + 1, ch_y0 + CHASSIS_H - 6],
               fill=None, outline=C_RUBBER, width=5)
    img.paste(ov, (0, 0), ov)

# 履带上下直线段
for dy in [ch_y0 + 10, ch_y0 + CHASSIS_H - 10]:
    draw.line([(track_cx1, dy), (BODY_X, dy)], fill=C_RUBBER, width=4)

# 底盘前防撞条
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.rounded_rectangle([ch_x0 - 6, ch_y0 + 14, ch_x0 + 4, GROUND_Y - 14],
                     radius=5, fill=(50, 52, 56))
img.paste(ov, (0, 0), ov)


# ===== 2. 机身主体 (侧视 — 蛋形) =====
# 底部宽 → 顶部窄
body_bot_r = BODY_D / 2       # 100
body_top_r = BODY_TOP_D / 2   # 80
body_mid_r = (body_bot_r + body_top_r) / 2 + 4  # 略鼓

# 机身轮廓：从底到顶先微鼓后收窄
pts = []
segments = 40
for i in range(segments + 1):
    t = i / segments
    y = BODY_BOT_Y - t * BODY_H
    if t < 0.35:
        # 底部到中下部：微微加宽
        r = body_bot_r + (body_mid_r - body_bot_r) * (t / 0.35)
    elif t < 0.7:
        # 中下部到中上部：最宽然后开始收
        r = body_mid_r - (body_mid_r - body_top_r) * ((t - 0.35) / 0.35) * 0.5
    else:
        # 上部：快速收窄到顶部
        r = body_mid_r - (body_mid_r - body_top_r) * ((t - 0.35) / 0.65)
    pts.append((BODY_X - r, y))
# 顶到底（右侧轮廓，倒序）
for i in range(segments, -1, -1):
    t = i / segments
    y = BODY_BOT_Y - t * BODY_H
    if t < 0.35:
        r = body_bot_r + (body_mid_r - body_bot_r) * (t / 0.35)
    elif t < 0.7:
        r = body_mid_r - (body_mid_r - body_top_r) * ((t - 0.35) / 0.35) * 0.5
    else:
        r = body_mid_r - (body_mid_r - body_top_r) * ((t - 0.35) / 0.65)
    pts.append((BODY_X + r, y))

ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.polygon(pts, fill=C_WHITE)
img.paste(ov, (0, 0), ov)

# 机身阴影 (后方)
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.polygon([(BODY_X, BODY_BOT_Y), (BODY_X + body_bot_r + 2, BODY_BOT_Y),
            (BODY_X + body_top_r + 2, BODY_TOP_Y), (BODY_X, BODY_TOP_Y)],
           fill=(190, 195, 205, 55))
img.paste(ov, (0, 0), ov)

# 机身前面高光
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
hl = [(BODY_X - body_bot_r + 20, BODY_BOT_Y - 10),
      (BODY_X - body_top_r + 15, BODY_TOP_Y + 10)]
od.ellipse([BODY_X - body_bot_r + 10, BODY_BOT_Y - 200,
            BODY_X - body_bot_r + 70, BODY_BOT_Y - 30],
           fill=(255, 255, 255, 40))
img.paste(ov, (0, 0), ov)

# 装饰环 (侧视图 — 细条)
for y_ratio, alpha in [(0.02, 200), (0.5, 120), (0.97, 200)]:
    ry = BODY_BOT_Y - BODY_H * y_ratio
    t = y_ratio
    if t < 0.35:
        r = body_bot_r + (body_mid_r - body_bot_r) * (t / 0.35)
    elif t < 0.7:
        r = body_mid_r - (body_mid_r - body_top_r) * ((t - 0.35) / 0.35) * 0.5
    else:
        r = body_mid_r - (body_mid_r - body_top_r) * ((t - 0.35) / 0.65)
    draw.line([(BODY_X - r - 1, ry), (BODY_X + r + 1, ry)], fill=C_BLUE, width=6)
    draw.line([(BODY_X - r - 1, ry - 1), (BODY_X + r + 1, ry - 1)],
              fill=C_BLUE_LT, width=2)


# ===== 3. 屏幕面板 (侧视 — 关键！展示28°仰角) =====
sr = SCREEN_R
tilt_rad = math.radians(SCREEN_TILT)
# 屏幕法线方向 (倾斜后面朝上)
nx = -math.sin(tilt_rad)  # 向后
ny = -math.cos(tilt_rad)  # 向上

screen_cx = BODY_X - body_top_r * 0.25  # 屏幕在前脸
screen_cy = SCREEN_CY

# 屏幕倾斜椭圆 (侧视看就是一条斜线)
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
# 计算倾斜屏幕的四个角
half_w = sr + 16         # 含外框
# 屏幕在侧视图里是一段斜线
top_x = screen_cx - sr * math.sin(tilt_rad)
top_y = screen_cy - sr * math.cos(tilt_rad)
bot_x = screen_cx + sr * math.sin(tilt_rad)
bot_y = screen_cy + sr * math.cos(tilt_rad)

# 外框 (侧视 — 窄条)
frame_thick = 12
# 绘制屏框
for i, (fx, fy) in enumerate([(top_x, top_y), (bot_x, bot_y)]):
    pass

# 用多边形画倾斜屏幕的侧面轮廓
# 屏幕是一个倾斜的圆盘，侧视看起来是一段倾斜的矩形
pts_screen = [
    (top_x - 6, top_y - 2),     # 顶部外框
    (top_x + 6, top_y + 2),     # 顶部内
    (bot_x + 6, bot_y - 2),     # 底部内
    (bot_x - 6, bot_y + 2),     # 底部外框
]
# 外框
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.polygon([
    (top_x - 8, top_y - 2),
    (top_x + 8, top_y + 2),
    (bot_x + 8, bot_y - 2),
    (bot_x - 8, bot_y + 2),
], fill=C_SILVER)
img.paste(ov, (0, 0), ov)

# 屏幕 (暗色)
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.polygon([
    (top_x - 2, top_y),
    (top_x + 2, top_y + 1),
    (bot_x + 2, bot_y - 1),
    (bot_x - 2, bot_y),
], fill=C_SCREEN)
img.paste(ov, (0, 0), ov)

# 屏幕发光面 (朝外的面)
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.line([(top_x - 6, top_y - 1), (bot_x - 6, bot_y + 1)],
        fill=(0, 255, 208, 80), width=3)
img.paste(ov, (0, 0), ov)


# ===== 4. 仰角标注线 =====
# 水平参考线 (虚线)
hl_y = screen_cy
for lx in range(int(screen_cx - 60), int(screen_cx + 60), 8):
    draw.line([(lx, int(hl_y)), (lx + 4, int(hl_y))], fill=(255, 255, 255, 50), width=1)

# 屏幕法线方向标注
normal_len = 80
normal_end_x = screen_cx - normal_len * math.sin(tilt_rad)
normal_end_y = screen_cy - normal_len * math.cos(tilt_rad)
draw.line([(screen_cx, screen_cy), (normal_end_x, normal_end_y)],
          fill=(0, 255, 208, 180), width=3)
# 箭头
arrow_pts = [
    (normal_end_x, normal_end_y),
    (normal_end_x - 10, normal_end_y + 15),
    (normal_end_x + 10, normal_end_y + 15),
]
draw.polygon(arrow_pts, fill=(0, 255, 208, 180))

# 角度弧
arc_r = 40
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.arc([screen_cx - arc_r, screen_cy - arc_r, screen_cx + arc_r, screen_cy + arc_r],
       270, 270 + SCREEN_TILT, fill=(255, 215, 0, 200), width=3)
img.paste(ov, (0, 0), ov)

# ===== 5. 头部后壳 =====
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.ellipse([HEAD_CX - HEAD_RX, HEAD_CY - HEAD_RY,
            HEAD_CX + HEAD_RX, HEAD_CY + HEAD_RY],
           fill=C_WHITE)
img.paste(ov, (0, 0), ov)

# 后壳阴影
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.ellipse([HEAD_CX - HEAD_RX + 5, HEAD_CY - HEAD_RY + 10,
            HEAD_CX + 5, HEAD_CY + HEAD_RY - 10],
           fill=(195, 200, 210, 45))
img.paste(ov, (0, 0), ov)

# 脖子过渡
neck_y = BODY_TOP_Y
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.polygon([
    (BODY_X - body_top_r, neck_y),
    (BODY_X + body_top_r, neck_y),
    (HEAD_CX + HEAD_RX - 10, HEAD_CY + HEAD_RY - 5),
    (HEAD_CX - HEAD_RX + 10, HEAD_CY + HEAD_RY - 5),
], fill=C_WHITE)
img.paste(ov, (0, 0), ov)


# ===== 6. 天线 =====
# 底座
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.polygon([
    (ANT_BASE_X - 10, ANT_BASE_Y + 8),
    (ANT_BASE_X + 10, ANT_BASE_Y + 8),
    (ANT_BASE_X + 5, ANT_BASE_Y - 12),
    (ANT_BASE_X - 5, ANT_BASE_Y - 12),
], fill=C_BLUE_DK)
img.paste(ov, (0, 0), ov)

# 杆
rod_top = ANT_BASE_Y - 80
draw.line([(ANT_BASE_X, ANT_BASE_Y - 10), (ANT_BASE_X, rod_top)],
          fill=C_BLUE_DK, width=5)
draw.line([(ANT_BASE_X + 1, ANT_BASE_Y - 10), (ANT_BASE_X + 1, rod_top)],
          fill=C_BLUE_LT, width=2)

# 金色球
soft_circle(ANT_BASE_X, rod_top - 15, 16, C_GOLD, 1)
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.ellipse([ANT_BASE_X - 14, rod_top - 28, ANT_BASE_X + 14, rod_top - 4], fill=C_GOLD)
img.paste(ov, (0, 0), ov)
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.ellipse([ANT_BASE_X - 5, rod_top - 25, ANT_BASE_X + 7, rod_top - 16],
           fill=C_GOLD_LT)
img.paste(ov, (0, 0), ov)


# ===== 7. 机械臂 (侧视 — 折叠) =====
arm_x = BODY_X - body_bot_r - 8
arm_y = BODY_BOT_Y - BODY_H * 0.45
# 安装座
draw.ellipse([arm_x - 22, arm_y - 22, arm_x + 22, arm_y + 22], fill=(80, 82, 88))
draw.ellipse([arm_x - 16, arm_y - 16, arm_x + 16, arm_y + 16], fill=(100, 102, 108))
# 上臂
upper_end_y = arm_y + 95
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.polygon([
    (arm_x - 9, arm_y + 18),
    (arm_x + 9, arm_y + 18),
    (arm_x + 7, upper_end_y),
    (arm_x - 7, upper_end_y),
], fill=(60, 62, 68))
img.paste(ov, (0, 0), ov)
# 肘关节
draw.ellipse([arm_x - 12, upper_end_y - 10, arm_x + 12, upper_end_y + 14],
             fill=(70, 72, 78))
# 前臂
forearm_end = upper_end_y + 70
forearm_x = arm_x - 15
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.polygon([
    (arm_x - 6, upper_end_y + 8),
    (arm_x + 6, upper_end_y + 8),
    (forearm_x + 6, forearm_end),
    (forearm_x - 6, forearm_end),
], fill=(85, 87, 93))
img.paste(ov, (0, 0), ov)
# 手爪
draw.ellipse([forearm_x - 12, forearm_end - 12, forearm_x + 12, forearm_end + 12],
             fill=C_RED)
draw.ellipse([forearm_x - 8, forearm_end - 8, forearm_x + 8, forearm_end + 8],
             fill=(255, 130, 100))


# ===== 8. 麦克风 (侧视 — 屏幕下方小凸起) =====
mic_x = screen_cx - 4
mic_y = bot_y + 22
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.rounded_rectangle([mic_x - 6, mic_y - 6, mic_x + 6, mic_y + 6],
                     radius=3, fill=(30, 33, 37))
img.paste(ov, (0, 0), ov)


# ===== 9. 文字标注 =====
try:
    font_lg = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 42)
    font_md = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 24)
    font_sm = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 17)
except Exception:
    font_lg = font_md = font_sm = ImageFont.load_default()

title = "Coco v5 — 侧面视图"
tb = draw.textbbox((0, 0), title, font=font_lg)
draw.text((W//2 - (tb[2]-tb[0])//2, 35), title, fill=(255, 255, 255, 230), font=font_lg)

# 关键标注
annotations = [
    ("屏幕 28° 仰角", screen_cx + 40, screen_cy - 50, C_CYAN),
    ("200mm 圆屏", screen_cx - 80, screen_cy + 30, (255, 255, 255, 170)),
    ("蛋形机身", BODY_X + 120, BODY_BOT_Y - BODY_H * 0.55, (255, 255, 255, 170)),
    ("头部后壳", HEAD_CX, HEAD_CY - HEAD_RY - 15, (255, 255, 255, 170)),
    ("天线", ANT_BASE_X + 30, ANT_BASE_Y - 60, C_GOLD),
    ("履带底盘", BODY_X - 140, GROUND_Y - CHASSIS_H - 12, (255, 255, 255, 170)),
    ("麦克风", mic_x - 40, mic_y + 20, (255, 255, 255, 170)),
    ("机械臂(折叠)", arm_x - 60, arm_y + 50, (255, 255, 255, 170)),
]
for label, lx, ly, color in annotations:
    try:
        r, g, b = color
    except (ValueError, TypeError):
        r, g, b, a = color
    draw.text((lx, ly), label, fill=(r, g, b) if len(color) == 3 else (r, g, b, color[3]),
              font=font_sm)

# 总高标注
lx = 60
top_y = ANT_BASE_Y - 90
bot_y = GROUND_Y
draw.line([(lx, top_y), (lx, bot_y)], fill=(255, 255, 255, 60), width=2)
draw.line([(lx - 12, top_y), (lx + 12, top_y)], fill=(255, 255, 255, 60), width=2)
draw.line([(lx - 12, bot_y), (lx + 12, bot_y)], fill=(255, 255, 255, 60), width=2)
draw.text((lx + 14, (top_y + bot_y)//2 - 12), "~900mm",
          fill=(255, 255, 255, 120), font=font_md)

# 底盘标注
draw.line([(ch_x0 + 4, GROUND_Y + 30), (ch_x1 - 4, GROUND_Y + 30)],
          fill=(255, 255, 255, 40), width=1)
draw.text((BODY_X - 40, GROUND_Y + 36), "340mm",
          fill=(255, 255, 255, 80), font=font_sm)

# 角度标注文字
draw.text((screen_cx + 50, screen_cy - 80), "28°",
          fill=(255, 215, 0, 220), font=font_md)

# 底部说明
footer = "侧视图 · 屏幕仰角设计使站立用户可自然低头查看 · 机身蛋形上窄下宽保证重心稳定"
fb = draw.textbbox((0, 0), footer, font=font_sm)
fw = fb[2] - fb[0]
draw.text((W//2 - fw//2, H - 45), footer, fill=(255, 255, 255, 80), font=font_sm)


# ===== 导出 =====
output = "D:/claude/coco/design/coco_side.png"
img_rgb = Image.new("RGB", (W, H), (30, 35, 50))
img_rgb.paste(img, (0, 0), img)
img_rgb.save(output, "PNG", quality=95)
print(f"Saved: {output}  ({W}×{H})")
