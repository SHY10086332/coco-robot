"""
Coco 导购机器人 — 商品信息展示

在圆形屏幕上展示商品卡片：名称、价格、规格、货架位置。
支持滚入/滚出动画过渡。
"""

import logging
from typing import Optional

from PyQt5.QtCore import Qt, QRectF, QPointF, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QRadialGradient,
)
from PyQt5.QtWidgets import QWidget

from config import SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_SPEAKING

log = logging.getLogger("coco.ui.product_view")

# 配色
CARD_BG = QColor("#FFFFFF")
CARD_BORDER = QColor("#E0E0E0")
PRICE_COLOR = QColor("#FF4444")
TITLE_COLOR = QColor("#1A1A2E")
INFO_COLOR = QColor("#666666")
SHELF_COLOR = QColor("#0088CC")
TAG_BG = QColor("#FFF3E0")
TAG_BORDER = QColor("#FFB74D")


class ProductData:
    """商品展示数据"""

    def __init__(self, name: str = "", price: float = 0, unit: str = "",
                 spec: str = "", shelf: str = "", stock: int = 0,
                 description: str = "", category: str = ""):
        self.name = name
        self.price = price
        self.unit = unit
        self.spec = spec
        self.shelf = shelf
        self.stock = stock
        self.description = description
        self.category = category

    @classmethod
    def from_product(cls, product) -> "ProductData":
        return cls(
            name=product.name,
            price=product.price,
            unit=product.unit,
            spec=product.spec,
            shelf=product.shelf,
            stock=product.stock,
            description=product.description,
            category=getattr(product, "category", ""),
        )


class ProductView(QWidget):
    """商品信息卡片"""

    MAX_TITLE_LEN = 12   # 超过这个长度自动缩小字号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._product: Optional[ProductData] = None
        self._opacity = 1.0

    def set_product(self, product: ProductData):
        self._product = product
        self.update()

    def clear(self):
        self._product = None
        self.update()

    @property
    def has_product(self) -> bool:
        return self._product is not None

    def paintEvent(self, event):
        if self._product is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(self._opacity)

        # 圆形裁剪
        center = QPointF(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
        r = min(SCREEN_WIDTH, SCREEN_HEIGHT) / 2 - 5
        clip = QPainterPath()
        clip.addEllipse(center, r, r)
        painter.setClipPath(clip)

        # 背景
        painter.setBrush(QBrush(QColor(COLOR_SPEAKING)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, r, r)

        p = self._product

        # 顶部留空给 Coco 表情（上方 0~30% 留给 face widget）
        content_top = SCREEN_HEIGHT * 0.30
        content_h = SCREEN_HEIGHT * 0.70
        card_rect = QRectF(30, content_top, SCREEN_WIDTH - 60, content_h)

        # 白色内容卡片
        painter.setBrush(QBrush(CARD_BG))
        painter.setPen(QPen(CARD_BORDER, 2))
        painter.drawRoundedRect(card_rect, 20, 20)

        # 分类标签
        if p.category:
            tag_rect = QRectF(card_rect.x() + 15, card_rect.y() + 15, 80, 26)
            painter.setBrush(QBrush(TAG_BG))
            painter.setPen(QPen(TAG_BORDER, 1))
            painter.drawRoundedRect(tag_rect, 13, 13)
            painter.setFont(QFont("Microsoft YaHei", 10))
            painter.setPen(QColor("#E65100"))
            painter.drawText(tag_rect, Qt.AlignCenter, p.category)

        # 商品名
        name_font_size = 28 if len(p.name) <= 6 else (22 if len(p.name) <= 10 else 18)
        name_font = QFont("Microsoft YaHei", name_font_size, QFont.Bold)
        painter.setFont(name_font)
        painter.setPen(TITLE_COLOR)
        name_rect = QRectF(card_rect.x() + 20, card_rect.y() + 55,
                           card_rect.width() - 40, 45)
        painter.drawText(name_rect, Qt.AlignLeft | Qt.AlignVCenter, p.name)

        # 价格 — 大字突出
        price_font = QFont("Arial", 42, QFont.Bold)
        painter.setFont(price_font)
        painter.setPen(PRICE_COLOR)
        price_text = f"¥{p.price:.2f}"
        price_rect = QRectF(card_rect.x() + 20, card_rect.y() + 110,
                            card_rect.width() - 40, 55)
        painter.drawText(price_rect, Qt.AlignLeft | Qt.AlignVCenter, price_text)

        # 单位/规格
        if p.unit or p.spec:
            spec_text = f"/{p.unit}" if p.unit else ""
            if p.spec:
                spec_text += f"  {p.spec}"
            info_font = QFont("Microsoft YaHei", 14)
            painter.setFont(info_font)
            painter.setPen(INFO_COLOR)
            spec_rect = QRectF(card_rect.x() + 20, card_rect.y() + 165,
                               card_rect.width() - 40, 25)
            painter.drawText(spec_rect, Qt.AlignLeft | Qt.AlignVCenter, spec_text)

        # 分隔线
        line_y = card_rect.y() + 200
        painter.setPen(QPen(QColor("#EEEEEE"), 1))
        painter.drawLine(
            QPointF(card_rect.x() + 20, line_y),
            QPointF(card_rect.right() - 20, line_y),
        )

        # 货架位置 — 醒目
        shelf_font = QFont("Microsoft YaHei", 16)
        painter.setFont(shelf_font)
        painter.setPen(SHELF_COLOR)
        shelf_rect = QRectF(card_rect.x() + 20, line_y + 15,
                            card_rect.width() - 40, 30)
        painter.drawText(shelf_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         f"📍 货架 {p.shelf}")

        # 库存信息
        stock_text = f"库存: {p.stock}件"
        stock_color = QColor("#FF6600") if p.stock < 10 else INFO_COLOR
        painter.setFont(QFont("Microsoft YaHei", 12))
        painter.setPen(stock_color)
        stock_rect = QRectF(card_rect.x() + 20, line_y + 50,
                            card_rect.width() - 40, 22)
        painter.drawText(stock_rect, Qt.AlignLeft | Qt.AlignVCenter, stock_text)

        # 描述
        if p.description:
            desc_font = QFont("Microsoft YaHei", 11)
            painter.setFont(desc_font)
            painter.setPen(INFO_COLOR)
            desc_rect = QRectF(card_rect.x() + 20, line_y + 80,
                               card_rect.width() - 40, 40)
            desc_text = p.description[:50] + ".." if len(p.description) > 50 else p.description
            painter.drawText(desc_rect, Qt.AlignLeft | Qt.TextWordWrap, desc_text)

        painter.end()
