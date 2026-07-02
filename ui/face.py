"""
Coco 导购机器人 — Coco 角色表情动画

在圆形屏幕上绘制 Coco（熊出没风格白色蛋形机器人）的表情。
每个状态有对应的表情和动画效果。

状态-表情映射:
    IDLE      → 眨眼 + 微笑（等待中）
    LISTENING → 大眼睛 + 天线发光（聆听中）
    THINKING  → 眼睛转圈（思考中）
    SPEAKING  → 嘴巴张合（说话中）
    PRICING   → 眼睛变¥（查价中）
    MOVING    → 眯眯眼 + 身体晃动（移动中）
    ALERT     → X眼 + 红色（故障）
"""

import math
import time
import logging
from dataclasses import dataclass
from typing import Tuple

from PyQt5.QtCore import (
    Qt, QTimer, QRectF, QPointF, pyqtSignal, QObject
)
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QRadialGradient,
    QLinearGradient, QPainterPath, QPolygonF,
)
from PyQt5.QtWidgets import QWidget

from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, ANIMATION_FPS,
    COLOR_IDLE, COLOR_LISTENING, COLOR_THINKING, COLOR_SPEAKING, COLOR_WARNING,
)

log = logging.getLogger("coco.ui.face")

# Coco 角色配色
COCO_BODY = QColor("#F5F0E8")         # 蛋壳白
COCO_BODY_SHADOW = QColor("#E0D8C8")  # 身体阴影
COCO_EYE = QColor("#2C2416")          # 深棕色眼睛
COCO_EYE_HIGHLIGHT = QColor("#FFFFFF")  # 眼睛高光
COCO_MOUTH = QColor("#3C3020")        # 嘴巴
COCO_ANTENNA = QColor("#FFD700")      # 金色天线
COCO_ANTENNA_GLOW = QColor("#FFA500") # 天线发光
COCO_CHEEK = QColor("#FFB5B5")        # 腮红
COCO_NOSE = QColor("#FF8C00")         # 橙色小鼻子


# ============================================================
# 表情状态
# ============================================================

@dataclass
class ExpressionState:
    """一帧的表情参数"""
    eye_radius: float = 30          # 眼球半径
    eye_spacing: float = 35         # 眼距（离中线）
    eye_height_offset: float = -15  # 眼睛高度偏移（负=偏上）
    mouth_type: str = "smile"       # smile / open / round / flat / x
    mouth_size: float = 1.0         # 嘴巴缩放
    cheek_alpha: float = 0.5        # 腮红透明度
    antenna_glow: float = 0.3       # 天线发光强度 (0~1)
    antenna_pulse: bool = False     # 天线是否脉冲动画
    body_bounce: float = 0.0        # 身体弹跳偏移
    pupil_offset: Tuple[float, float] = (0, 0)  # 瞳孔偏移（看方向）
    blink: float = 0.0              # 眨眼程度 (0=睁眼, 1=闭眼)


def expression_for_state(state_name: str, anim_t: float) -> ExpressionState:
    """根据状态名生成表情参数，anim_t 用于周期性动画"""
    t = anim_t  # 0~1 循环

    if state_name == "idle":
        # 眨眼 + 微笑，每 3 秒眨一次
        blink_cycle = (t * 10) % 3.0  # 3秒周期
        blink = max(0, 1 - abs(blink_cycle - 1.5) * 6) if blink_cycle > 1.2 else 0
        blink = min(1.0, blink)
        return ExpressionState(
            eye_radius=28, eye_spacing=35, eye_height_offset=-15,
            mouth_type="smile", mouth_size=0.8,
            cheek_alpha=0.4, antenna_glow=0.3,
            blink=blink,
        )

    elif state_name == "listening":
        # 大眼睛，天线脉冲发光
        pulse = 0.5 + 0.5 * math.sin(t * math.pi * 4)
        return ExpressionState(
            eye_radius=35, eye_spacing=30, eye_height_offset=-18,
            mouth_type="round", mouth_size=0.5,
            cheek_alpha=0.3, antenna_glow=pulse,
            antenna_pulse=True,
        )

    elif state_name == "thinking":
        # 眼睛看右上角（思考状），轻轻晃动
        look_x = 5 + 3 * math.sin(t * math.pi * 3)
        look_y = -5 - 3 * abs(math.cos(t * math.pi * 2))
        return ExpressionState(
            eye_radius=26, eye_spacing=36, eye_height_offset=-14,
            mouth_type="flat", mouth_size=0.6,
            cheek_alpha=0.2, antenna_glow=0.6,
            antenna_pulse=True,
            pupil_offset=(look_x, look_y),
        )

    elif state_name in ("speaking", "pricing"):
        # 嘴巴张合模拟说话 (快频)
        mouth_open = 0.3 + 0.7 * abs(math.sin(t * math.pi * 8))
        return ExpressionState(
            eye_radius=30, eye_spacing=34, eye_height_offset=-15,
            mouth_type="open", mouth_size=mouth_open,
            cheek_alpha=0.5, antenna_glow=0.4,
        )

    elif state_name == "moving":
        # 眯眯眼开心状
        bounce = 2 * math.sin(t * math.pi * 3)
        return ExpressionState(
            eye_radius=20, eye_spacing=38, eye_height_offset=-12,
            mouth_type="smile", mouth_size=1.2,
            cheek_alpha=0.6, antenna_glow=0.5,
            body_bounce=bounce,
        )

    elif state_name == "dialog":
        # 日常对话，温和表情
        return ExpressionState(
            eye_radius=30, eye_spacing=34, eye_height_offset=-15,
            mouth_type="smile", mouth_size=0.9,
            cheek_alpha=0.45, antenna_glow=0.35,
        )

    elif state_name == "payment":
        # 期待表情（等待付款）
        return ExpressionState(
            eye_radius=30, eye_spacing=34, eye_height_offset=-15,
            mouth_type="smile", mouth_size=1.0,
            cheek_alpha=0.5, antenna_glow=0.5,
            antenna_pulse=True,
        )

    elif state_name == "alert":
        # X眼 + 红色调
        pulse = 0.6 + 0.4 * math.sin(t * math.pi * 6)
        return ExpressionState(
            eye_radius=25, eye_spacing=35, eye_height_offset=-14,
            mouth_type="flat", mouth_size=0.3,
            cheek_alpha=0.0, antenna_glow=pulse, antenna_pulse=True,
        )

    else:
        return ExpressionState()


# ============================================================
# Coco 面部 Widget
# ============================================================

class CocoFaceWidget(QWidget):
    """Coco 面部动画 Widget — 圆形屏幕上画 Coco 的脸"""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.PointingHandCursor)

        # 动画状态
        self._state_name = "idle"
        self._anim_t = 0.0
        self._expr = ExpressionState()

        # 天线粒子（发光效果）
        self._particles = []

        # 定时器
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(int(1000 / ANIMATION_FPS))  # 24fps

        log.info(f"Coco 面部 Widget 初始化 ({SCREEN_WIDTH}x{SCREEN_HEIGHT}, "
                 f"{ANIMATION_FPS}fps)")

    # ---- 公共接口 ----

    def set_state(self, state_name: str):
        """切换表情状态"""
        if state_name != self._state_name:
            log.debug(f"表情切换: {self._state_name} → {state_name}")
            self._state_name = state_name

    def state(self) -> str:
        return self._state_name

    # ---- 动画循环 ----

    def _tick(self):
        """24fps 动画帧更新"""
        self._anim_t += 1.0 / ANIMATION_FPS
        if self._anim_t > 300:  # 防止浮点累积
            self._anim_t -= 300
        self._expr = expression_for_state(self._state_name, self._anim_t)
        self.update()  # 触发 paintEvent

    # ---- 绘制 ----

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 圆形裁剪区域
        center = QPointF(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
        radius = min(SCREEN_WIDTH, SCREEN_HEIGHT) / 2 - 5
        clip_path = QPainterPath()
        clip_path.addEllipse(center, radius, radius)
        painter.setClipPath(clip_path)

        # 背景
        bg_color = self._bg_color()
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, radius, radius)

        # Coco 身体（白色蛋形主体）
        body_y_offset = self._expr.body_bounce
        self._draw_body(painter, center + QPointF(0, body_y_offset), radius)

        # 天线
        self._draw_antenna(painter, center + QPointF(0, body_y_offset), radius)

        # 五官
        face_center = center + QPointF(0, body_y_offset)
        self._draw_eyes(painter, face_center)
        self._draw_eyebrows(painter, face_center)
        self._draw_nose(painter, face_center)
        self._draw_mouth(painter, face_center)
        self._draw_cheeks(painter, face_center)

        painter.end()

    def _bg_color(self) -> QColor:
        """根据状态返回背景色"""
        colors = {
            "alert": COLOR_WARNING,
            "listening": COLOR_LISTENING,
            "thinking": COLOR_THINKING,
            "speaking": COLOR_SPEAKING,
            "pricing": COLOR_SPEAKING,
            "moving": COLOR_IDLE,
            "dialog": COLOR_IDLE,
            "payment": COLOR_IDLE,
        }
        return QColor(colors.get(self._state_name, COLOR_IDLE))

    def _draw_body(self, painter: QPainter, center: QPointF, r: float):
        """绘制 Coco 白色蛋形身体"""
        body_rect = QRectF(
            center.x() - r * 0.82,
            center.y() - r * 0.78,
            r * 1.64,
            r * 1.56,
        )

        # 渐变身体
        gradient = QRadialGradient(center, r * 0.9)
        gradient.setColorAt(0, QColor("#FFFAF5"))
        gradient.setColorAt(0.7, COCO_BODY)
        gradient.setColorAt(1, COCO_BODY_SHADOW)

        # 圆角矩形身体
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(COCO_BODY_SHADOW.darker(120), 2))
        painter.drawRoundedRect(body_rect, r * 0.5, r * 0.5)

    def _draw_antenna(self, painter: QPainter, center: QPointF, r: float):
        """绘制顶部天线 + 发光小球"""
        expr = self._expr

        # 天线杆
        base_x, base_y = center.x(), center.y() - r * 0.7
        tip_x, tip_y = center.x(), center.y() - r * 1.05

        pen = QPen(COCO_ANTENNA.darker(130), 3)
        painter.setPen(pen)
        painter.drawLine(QPointF(base_x, base_y), QPointF(tip_x, tip_y))

        # 发光小球
        ball_r = 10
        glow_r = ball_r + 8 * expr.antenna_glow

        # 光晕
        glow_grad = QRadialGradient(QPointF(tip_x, tip_y), glow_r)
        glow_color = COCO_ANTENNA_GLOW
        glow_color.setAlphaF(0.4 * expr.antenna_glow)
        glow_grad.setColorAt(0, glow_color)
        glow_grad.setColorAt(1, QColor(255, 165, 0, 0))
        painter.setBrush(QBrush(glow_grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(tip_x, tip_y), glow_r, glow_r)

        # 实心球
        ball_grad = QRadialGradient(QPointF(tip_x - 2, tip_y - 2), ball_r)
        ball_grad.setColorAt(0, QColor("#FFEE88"))
        ball_grad.setColorAt(0.5, COCO_ANTENNA)
        ball_grad.setColorAt(1, QColor("#CC8800"))
        painter.setBrush(QBrush(ball_grad))
        painter.setPen(QPen(QColor("#AA6600"), 1))
        painter.drawEllipse(QPointF(tip_x, tip_y), ball_r, ball_r)

    def _draw_eyes(self, painter: QPainter, center: QPointF):
        """绘制双眼"""
        expr = self._expr
        cx, cy = center.x(), center.y()

        if expr.blink > 0.9:
            # 闭眼（一条线）
            for side in (-1, 1):
                eye_x = cx + side * expr.eye_spacing
                eye_y = cy + expr.eye_height_offset
                painter.setPen(QPen(COCO_EYE, 3))
                painter.setBrush(Qt.NoBrush)
                painter.drawLine(
                    QPointF(eye_x - expr.eye_radius, eye_y),
                    QPointF(eye_x + expr.eye_radius, eye_y),
                )
            return

        for side in (-1, 1):
            eye_x = cx + side * expr.eye_spacing
            eye_y = cy + expr.eye_height_offset
            eye_r = expr.eye_radius

            # 眨眼缩放
            if expr.blink > 0:
                eye_r_y = eye_r * (1 - expr.blink * 0.85)
                eye_r_x = eye_r
            else:
                eye_r_x = eye_r_y = eye_r

            # 眼白
            painter.setBrush(QBrush(Qt.white))
            painter.setPen(QPen(COCO_EYE.darker(150), 2))
            painter.drawEllipse(QPointF(eye_x, eye_y), eye_r_x, eye_r_y)

            # 瞳孔（深棕色，带偏移）
            pupil_r = eye_r * 0.55
            pupil_x = eye_x + expr.pupil_offset[0]
            pupil_y = eye_y + expr.pupil_offset[1]

            # 限制瞳孔在眼白内
            dx, dy = pupil_x - eye_x, pupil_y - eye_y
            max_offset = eye_r - pupil_r - 2
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > max_offset:
                scale = max_offset / dist if dist > 0 else 1
                pupil_x = eye_x + dx * scale
                pupil_y = eye_y + dy * scale

            painter.setBrush(QBrush(COCO_EYE))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(pupil_x, pupil_y), pupil_r, pupil_r)

            # 高光
            hl_r = pupil_r * 0.35
            hl_x = pupil_x - pupil_r * 0.3
            hl_y = pupil_y - pupil_r * 0.35
            painter.setBrush(QBrush(COCO_EYE_HIGHLIGHT))
            painter.drawEllipse(QPointF(hl_x, hl_y), hl_r, hl_r)

            # 小高光
            hl2_r = hl_r * 0.5
            hl2_x = pupil_x + pupil_r * 0.2
            hl2_y = pupil_y - pupil_r * 0.5
            painter.drawEllipse(QPointF(hl2_x, hl2_y), hl2_r, hl2_r)

    def _draw_eyebrows(self, painter: QPainter, center: QPointF):
        """绘制粗眉毛（熊出没风格）"""
        expr = self._expr
        cx, cy = center.x(), center.y()

        if self._state_name == "alert":
            # 倒八字眉（愤怒/故障）
            for side in (-1, 1):
                start_x = cx + side * (expr.eye_spacing - expr.eye_radius * 0.5)
                start_y = cy + expr.eye_height_offset - expr.eye_radius - 15
                end_x = cx + side * (expr.eye_spacing + expr.eye_radius * 0.8)
                end_y = cy + expr.eye_height_offset - expr.eye_radius + 2
                pen = QPen(QColor("#4A3020"), 4, Qt.SolidLine, Qt.RoundCap)
                painter.setPen(pen)
                painter.drawLine(QPointF(start_x, start_y), QPointF(end_x, end_y))
        elif self._state_name in ("moving",):
            # 弯眉毛（开心）
            for side in (-1, 1):
                bx = cx + side * expr.eye_spacing
                by = cy + expr.eye_height_offset - expr.eye_radius - 12
                pen = QPen(QColor("#5A4030"), 3.5, Qt.SolidLine, Qt.RoundCap)
                painter.setPen(pen)
                w = expr.eye_radius * 1.0
                painter.setBrush(Qt.NoBrush)
                path = QPainterPath()
                path.moveTo(bx - w, by + 5)
                path.quadTo(bx - w / 2, by - 8, bx + w, by + 3)
                painter.drawPath(path)
        else:
            # 正常粗眉
            for side in (-1, 1):
                bx = cx + side * expr.eye_spacing
                by = cy + expr.eye_height_offset - expr.eye_radius - 10
                w = expr.eye_radius * 1.15
                pen = QPen(QColor("#4A3020"), 3.5, Qt.SolidLine, Qt.RoundCap)
                painter.setPen(pen)
                painter.drawLine(
                    QPointF(bx - w, by),
                    QPointF(bx + w, by + (expr.eye_radius * 0.06 if side > 0 else -2))
                )

    def _draw_nose(self, painter: QPainter, center: QPointF):
        """绘制橙色小圆鼻"""
        cx, cy = center.x(), center.y()
        nose_y = cy + 10

        nose_r = 8
        nose_grad = QRadialGradient(QPointF(cx - 1, nose_y), nose_r)
        nose_grad.setColorAt(0, QColor("#FFB040"))
        nose_grad.setColorAt(0.6, COCO_NOSE)
        nose_grad.setColorAt(1, QColor("#CC6600"))
        painter.setBrush(QBrush(nose_grad))
        painter.setPen(QPen(QColor("#AA5500"), 1))
        painter.drawEllipse(QPointF(cx, nose_y), nose_r, nose_r)

    def _draw_mouth(self, painter: QPainter, center: QPointF):
        """绘制嘴巴 — 不同形状对应不同情绪"""
        expr = self._expr
        cx, cy = center.x(), center.y()
        mouth_y = cy + 30

        pen = QPen(COCO_MOUTH, 2.5, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        if self._state_name == "alert":
            # X 嘴形（用 X 代替嘴巴，在眼睛那里画 X 眼也一起处理）
            # 这里画一个扁平的小直线
            painter.drawLine(
                QPointF(cx - 15, mouth_y),
                QPointF(cx + 15, mouth_y),
            )
        elif expr.mouth_type == "smile":
            # 微笑弧线
            w = 22 * expr.mouth_size
            h = 10 * expr.mouth_size
            path = QPainterPath()
            path.moveTo(cx - w, mouth_y)
            path.quadTo(cx, mouth_y + h, cx + w, mouth_y)
            painter.drawPath(path)
        elif expr.mouth_type == "open":
            # 张嘴说话
            w = 20
            h = 12 * expr.mouth_size
            painter.setBrush(QBrush(QColor("#8B2020")))  # 口腔暗红色
            painter.drawEllipse(QPointF(cx, mouth_y), w, h)
            painter.setBrush(Qt.NoBrush)
        elif expr.mouth_type == "round":
            # 小圆嘴（惊讶/聆听）
            r = 8 * expr.mouth_size
            painter.setBrush(QBrush(QColor("#5A2810")))
            painter.drawEllipse(QPointF(cx, mouth_y), r, r)
            painter.setBrush(Qt.NoBrush)
        elif expr.mouth_type == "flat":
            # 一字嘴
            painter.drawLine(
                QPointF(cx - 16 * expr.mouth_size, mouth_y),
                QPointF(cx + 16 * expr.mouth_size, mouth_y),
            )

    def _draw_cheeks(self, painter: QPainter, center: QPointF):
        """绘制腮红"""
        expr = self._expr
        if expr.cheek_alpha <= 0:
            return
        cx, cy = center.x(), center.y()

        for side in (-1, 1):
            cheek_x = cx + side * (expr.eye_spacing + expr.eye_radius + 8)
            cheek_y = cy + 5
            cheek_r = 14

            cheek_grad = QRadialGradient(QPointF(cheek_x, cheek_y), cheek_r)
            cheek_color = QColor(COCO_CHEEK)
            cheek_color.setAlphaF(expr.cheek_alpha)
            cheek_grad.setColorAt(0, cheek_color)
            cheek_grad.setColorAt(1, QColor(255, 181, 181, 0))
            painter.setBrush(QBrush(cheek_grad))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(cheek_x, cheek_y), cheek_r, cheek_r * 0.7)

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


# ============================================================
# 独立测试窗口
# ============================================================

class FaceTestWindow(QWidget):
    """表情动画测试窗口 — 点击切换状态"""

    STATES = ["idle", "listening", "thinking", "speaking",
              "dialog", "moving", "payment", "alert"]
    _state_idx = 0

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Coco 表情动画测试")
        self.setFixedSize(SCREEN_WIDTH + 40, SCREEN_HEIGHT + 80)
        self.setStyleSheet("background-color: #1a1a2e;")

        self.face = CocoFaceWidget(self)
        self.face.move(20, 20)
        self.face.clicked.connect(self._next_state)

        self.setCursor(Qt.PointingHandCursor)
        self._update_title()

    def _next_state(self):
        self._state_idx = (self._state_idx + 1) % len(self.STATES)
        state = self.STATES[self._state_idx]
        self.face.set_state(state)
        self._update_title()

    def _update_title(self):
        colors = {
            "idle": "青色", "listening": "深天蓝", "thinking": "金色",
            "speaking": "绿色", "dialog": "青色", "moving": "青色",
            "payment": "青色", "alert": "红色",
        }
        state = self.STATES[self._state_idx]
        self.setWindowTitle(
            f"Coco 表情测试 — [{colors.get(state, '')}] {state}  "
            f"(点击切换)"
        )


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys

    logging.basicConfig(level=logging.DEBUG)

    app = QApplication(sys.argv)
    win = FaceTestWindow()
    win.show()
    sys.exit(app.exec_())
