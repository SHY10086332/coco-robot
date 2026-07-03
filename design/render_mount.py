"""
Coco v5 — 屏幕安装示意图
"""

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1400, 900
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# 颜色
C_BG = (30, 35, 50)
C_WHITE = (245, 245, 250)
C_GRAY = (180, 185, 195)
C_DK_GRAY = (50, 52, 58)
C_CYAN = (0, 255, 208)
C_GOLD = (255, 215, 0)
C_RED = (255, 90, 70)

# 背景
for y in range(H):
    t = y / H
    r = int(30 + 25*t); g = int(35 + 25*t); b = int(50 + 25*t)
    draw.line([(0, y), (W, y)], fill=(r, g, b))

try:
    font_lg = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 36)
    font_md = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 20)
    font_sm = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 15)
except Exception:
    font_lg = font_md = font_sm = ImageFont.load_default()

title = "屏幕安装示意图 — 侧剖"
tb = draw.textbbox((0, 0), title, font=font_lg)
draw.text((W//2 - (tb[2]-tb[0])//2, 25), title, fill=(255, 255, 255, 230), font=font_lg)

# ===== 机身壳体剖面 =====
body_lx, body_rx = 250, 700
body_top, body_bot = 100, 780
body_mid_x = 520

# 机身前脸 (竖直，右侧)
front_x = body_rx - 40

# ===== 屏幕组件 (倾斜) =====
screen_cx = front_x + 10
screen_cy = 440
screen_r = 110
tilt = 28
import math
tilt_r = math.radians(tilt)
thick = 18

# 屏幕面板 (侧视厚度线)
top_x = screen_cx + screen_r * math.sin(tilt_r)
top_y = screen_cy - screen_r * math.cos(tilt_r)
bot_x = screen_cx - screen_r * math.sin(tilt_r)
bot_y = screen_cy + screen_r * math.cos(tilt_r)

# 后壳轮廓
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.polygon([
    (body_lx, body_top + 50),        # 左顶
    (body_lx, body_bot - 20),        # 左底
    (body_mid_x, body_bot),          # 中底
    (front_x, body_bot - 40),        # 前底
    (front_x, body_top + 80),        # 前顶
], fill=(60, 63, 72))
img.paste(ov, (0, 0), ov)

# 机身前壳 (剖线)
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
# 白色壳壁
od.polygon([
    (front_x, body_top + 80),
    (front_x - 6, body_top + 80),
    (front_x - 6, body_bot - 40),
    (front_x, body_bot - 40),
], fill=C_WHITE)
img.paste(ov, (0, 0), ov)

# ===== 屏幕组件 =====

# 屏幕背板
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.polygon([
    (top_x - thick, top_y - 3),
    (bot_x - thick, bot_y + 3),
    (bot_x + thick, bot_y - 3),
    (top_x + thick, top_y + 3),
], fill=C_GRAY)
img.paste(ov, (0, 0), ov)

# 屏幕外框
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.polygon([
    (top_x - thick + 3, top_y - 1),
    (bot_x - thick + 3, bot_y + 1),
    (bot_x + thick - 3, bot_y - 1),
    (top_x + thick - 3, top_y + 1),
], fill=(220, 225, 235))
img.paste(ov, (0, 0), ov)

# LCD 面板 (玻璃/发光层)
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.line([(top_x - 2, top_y), (bot_x - 2, bot_y)],
        fill=C_CYAN, width=4)
img.paste(ov, (0, 0), ov)

# 显示面标注
draw.line([(top_x - 5, top_y - 2), (top_x - 50, top_y - 75)],
          fill=(255, 255, 255, 100), width=1)
draw.text((top_x - 140, top_y - 95), "显示面\n(朝外)", fill=C_CYAN, font=font_md)

# ===== 安装支耳 (上) =====
ear_top_y = top_y - 20
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.rectangle([top_x - 10, ear_top_y - 8, top_x + 20, ear_top_y + 8],
             fill=C_GRAY)
img.paste(ov, (0, 0), ov)
# 螺丝
draw.ellipse([top_x + 8, ear_top_y - 3, top_x + 14, ear_top_y + 3], fill=C_RED)

# ===== 安装支耳 (下) =====
ear_bot_y = bot_y + 20
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.rectangle([bot_x - 20, ear_bot_y - 8, bot_x + 10, ear_bot_y + 8],
             fill=C_GRAY)
img.paste(ov, (0, 0), ov)
# 螺丝
draw.ellipse([bot_x - 14, ear_bot_y - 3, bot_x - 8, ear_bot_y + 3], fill=C_RED)

# ===== 角度标注 =====
arc_r = 60
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.arc([front_x - arc_r, top_y - arc_r, front_x + arc_r, top_y + arc_r],
       240, 270, fill=C_GOLD, width=3)
od.arc([front_x - arc_r + 1, top_y - arc_r + 1, front_x + arc_r + 1, top_y + arc_r + 1],
       270, 270 + tilt, fill=C_GOLD, width=3)
img.paste(ov, (0, 0), ov)
draw.text((front_x + 40, top_y - 30), f"{tilt}°", fill=C_GOLD, font=font_md)

# 水平虚线
for lx in range(front_x - 80, front_x + 30, 8):
    draw.line([(lx, top_y), (lx + 4, top_y)], fill=(255, 255, 255, 40), width=1)

# ===== HDMI 驱动板 =====
pcb_x = screen_cx - 60
pcb_y = screen_cy + 20
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.rectangle([pcb_x - 35, pcb_y - 15, pcb_x + 35, pcb_y + 15],
             fill=(20, 80, 40))
img.paste(ov, (0, 0), ov)
draw.text((pcb_x - 30, pcb_y - 10), "HDMI\n驱动板", fill=(255, 255, 255, 180), font=font_sm)

# 排线
draw.line([(pcb_x + 10, pcb_y - 15), (screen_cx, top_y)],
          fill=(255, 200, 50, 180), width=2)

# ===== HDMI线 =====
draw.line([(pcb_x - 5, pcb_y + 15), (pcb_x - 5, pcb_y + 60),
           (body_mid_x - 40, pcb_y + 60)],
          fill=(80, 80, 100, 180), width=3)
draw.text((body_mid_x - 120, pcb_y + 50), "→ 树莓派 HDMI", fill=(255, 255, 255, 120), font=font_sm)

# ===== M3 螺丝标注 =====
# 上安装点
draw.line([(top_x + 20, ear_top_y), (top_x + 70, ear_top_y - 40)],
          fill=C_RED, width=1)
draw.ellipse([top_x + 68, ear_top_y - 43, top_x + 78, ear_top_y - 33],
             fill=C_RED)
draw.text((top_x + 82, ear_top_y - 46), "M3×8mm\n螺丝 ×4", fill=C_RED, font=font_sm)

# ===== 麦克风 =====
mic_y = bot_y + 30
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
od.rounded_rectangle([bot_x - 32, mic_y - 6, bot_x + 32, mic_y + 6],
                     radius=4, fill=(30, 33, 37))
img.paste(ov, (0, 0), ov)
for i in range(4):
    draw.ellipse([bot_x - 18 + i*12, mic_y - 2, bot_x - 14 + i*12, mic_y + 2],
                 fill=(80, 82, 86))
draw.text((bot_x + 40, mic_y - 8), "Mic Array", fill=(255, 255, 255, 100), font=font_sm)

# ===== 说明文字 =====
notes = [
    "① 3D打印屏幕外框 (PLA+, 白色)",
    "② 200mm圆屏卡入框内，背后2颗螺丝固定",
    "③ 4个M3安装支耳锁到机身内壁预留的螺丝柱",
    "④ HDMI排线连接驱动板 → 树莓派",
    "⑤ 麦克风卡入下方预留槽位",
]
for i, note in enumerate(notes):
    draw.text((body_lx + 10, body_top + 100 + i * 30), note,
              fill=(255, 255, 255, 150), font=font_sm)

# ===== 导出 =====
output = "D:/claude/coco/design/screen_mount_guide.png"
img_rgb = Image.new("RGB", (W, H), C_BG)
img_rgb.paste(img, (0, 0), img)
img_rgb.save(output, "PNG", quality=95)
print(f"Saved: {output}")
