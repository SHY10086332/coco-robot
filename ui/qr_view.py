"""
Coco 导购机器人 — 收款码展示

全屏显示收款二维码 + 金额信息。
支持从 EventBus 接收支付信息。
"""

import logging
from typing import Optional

from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath,
)
from PyQt5.QtWidgets import QWidget

from config import SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_SPEAKING

log = logging.getLogger("coco.ui.qr_view")


class QRView(QWidget):
    """收款码全屏视图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._amount: float = 0
        self._item_name: str = ""
        self._qr_image = None  # PIL/PyQt image
        self._active = False

    def show_payment(self, amount: float, item_name: str = "",
                     qr_image=None):
        """显示收款界面"""
        self._amount = amount
        self._item_name = item_name
        self._qr_image = qr_image
        self._active = True
        self.update()

    def hide_payment(self):
        self._active = False
        self.update()

    @property
    def is_active(self) -> bool:
        return self._active

    def paintEvent(self, event):
        if not self._active:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 圆形裁剪
        center = QPointF(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
        r = min(SCREEN_WIDTH, SCREEN_HEIGHT) / 2 - 5
        clip = QPainterPath()
        clip.addEllipse(center, r, r)
        painter.setClipPath(clip)

        # 绿色背景（支付主题）
        bg_color = QColor("#07C160")  # 微信绿
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, r, r)

        # 顶部文字
        title_font = QFont("Microsoft YaHei", 24, QFont.Bold)
        painter.setFont(title_font)
        painter.setPen(Qt.white)
        title_rect = QRectF(40, 60, SCREEN_WIDTH - 80, 45)
        painter.drawText(title_rect, Qt.AlignCenter, "请扫码支付")

        # 金额
        amount_font = QFont("Arial", 52, QFont.Bold)
        painter.setFont(amount_font)
        painter.setPen(Qt.white)
        amount_text = f"¥{self._amount:.2f}"
        amount_rect = QRectF(40, 120, SCREEN_WIDTH - 80, 70)
        painter.drawText(amount_rect, Qt.AlignCenter, amount_text)

        # 商品名
        if self._item_name:
            item_font = QFont("Microsoft YaHei", 16)
            painter.setFont(item_font)
            painter.setPen(QColor("#EEEEEE"))
            item_rect = QRectF(40, 200, SCREEN_WIDTH - 80, 30)
            painter.drawText(item_rect, Qt.AlignCenter, self._item_name)

        # 二维码区域（白色方块 + 占位图案）
        qr_size = 260
        qr_x = (SCREEN_WIDTH - qr_size) / 2
        qr_y = SCREEN_HEIGHT / 2 - qr_size / 2 + 20
        qr_rect = QRectF(qr_x, qr_y, qr_size, qr_size)

        # 白色背景
        painter.setBrush(QBrush(Qt.white))
        painter.setPen(QPen(QColor("#E0E0E0"), 2))
        painter.drawRoundedRect(qr_rect, 16, 16)

        if self._qr_image:
            painter.drawImage(qr_rect, self._qr_image)
        else:
            # 占位 QR 码图案（Coco 风格二维码示意图）
            self._draw_placeholder_qr(painter, qr_rect)

        # 底部提示
        hint_font = QFont("Microsoft YaHei", 14)
        painter.setFont(hint_font)
        painter.setPen(QColor("#CCFFDD"))
        hint_rect = QRectF(40, qr_y + qr_size + 20, SCREEN_WIDTH - 80, 30)
        painter.drawText(hint_rect, Qt.AlignCenter, "支付完成后，Coco 会语音提示 ~")

        painter.end()

    def _draw_placeholder_qr(self, painter: QPainter, rect: QRectF):
        """绘制占位二维码图案（Coco 主题）"""
        margin = 20
        x, y = rect.x() + margin, rect.y() + margin
        w, h = rect.width() - 2 * margin, rect.height() - 2 * margin
        cell_count = 7
        cell_size = w / cell_count

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#1A1A2E")))

        # 左上角定位图案
        for row in range(3):
            for col in range(3):
                if not (row == 1 and col == 1):
                    r = QRectF(x + col * cell_size, y + row * cell_size,
                               cell_size, cell_size)
                    painter.drawRect(r)

        # 右上角定位图案
        rx = x + (cell_count - 3) * cell_size
        for row in range(3):
            for col in range(3):
                if not (row == 1 and col == 1):
                    r = QRectF(rx + col * cell_size, y + row * cell_size,
                               cell_size, cell_size)
                    painter.drawRect(r)

        # 左下角定位图案
        ry = y + (cell_count - 3) * cell_size
        for row in range(3):
            for col in range(3):
                if not (row == 1 and col == 1):
                    r = QRectF(x + col * cell_size, ry + row * cell_size,
                               cell_size, cell_size)
                    painter.drawRect(r)

        # 中间 Coco 头像位置（空白圆）
        cx, cy = x + w / 2, y + h / 2
        avatar_r = cell_size * 1.2
        painter.setBrush(QBrush(QColor("#F5F0E8")))
        painter.setPen(QPen(QColor("#E0D8C8"), 2))
        painter.drawEllipse(QPointF(cx, cy), avatar_r, avatar_r)

        # 眼睛点
        eye_r = 3
        painter.setBrush(QBrush(QColor("#1A1A2E")))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx - 8, cy - 3), eye_r, eye_r)
        painter.drawEllipse(QPointF(cx + 8, cy - 3), eye_r, eye_r)

        # 微笑弧线
        painter.setPen(QPen(QColor("#1A1A2E"), 2, Qt.SolidLine, Qt.RoundCap))
        path = QPainterPath()
        path.moveTo(cx - 8, cy + 5)
        path.quadTo(cx, cy + 14, cx + 8, cy + 5)
        painter.drawPath(path)
