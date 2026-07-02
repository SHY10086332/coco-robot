"""
Coco 导购机器人 — 主屏幕管理器

全屏无边框窗口 + 圆形遮罩，根据机器人状态切换视图:
    IDLE      → 表情动画（全屏）
    LISTENING → 表情 + 聆听提示
    THINKING  → 表情 + 思考动画
    PRICING   → 上半表情 + 下半商品卡片
    DIALOG    → 表情动画（全屏）
    PAYMENT   → 全屏收款码
    MOVING    → 表情 + 移动提示
    ALERT     → 红色警告 + 表情

所有视图切换通过 QStackedWidget 管理。
"""

import logging
import sys
from typing import Optional

from PyQt5.QtCore import (
    Qt, QTimer, QRectF, QPointF, QPropertyAnimation, QEasingCurve,
)
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QRegion,
    QRadialGradient,
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)

from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, ANIMATION_FPS, DEBUG,
    COLOR_IDLE, COLOR_LISTENING, COLOR_THINKING, COLOR_SPEAKING, COLOR_WARNING,
)
from ui.face import CocoFaceWidget
from ui.product_view import ProductView, ProductData
from ui.qr_view import QRView

log = logging.getLogger("coco.ui.screen")

# 机器人状态 → NLS 名称映射
STATE_TO_CHINESE = {
    "idle": "待机中",
    "listening": "聆听中...",
    "thinking": "思考中...",
    "pricing": "商品信息",
    "dialog": "聊天中",
    "moving": "移动中...",
    "payment": "请付款",
    "alert": "⚠ 故障",
}


class CircularWindow(QMainWindow):
    """
    圆形无边框全屏窗口。

    在树莓派上直接显示到 8 寸圆形 LCD。
    PC 上调试时显示为方形窗口 + 圆形内容区。
    """

    def __init__(self, debug: bool = DEBUG):
        super().__init__()

        self.debug = debug
        self._state = "idle"

        # 窗口设置
        self.setWindowTitle("Coco 导购机器人")
        if debug:
            # PC 调试：方形窗口，尺寸稍大以便观察
            self.setFixedSize(SCREEN_WIDTH + 40, SCREEN_HEIGHT + 100)
        else:
            # 生产：全屏无边框
            self.setWindowFlags(
                Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
            )
            self.setFixedSize(SCREEN_WIDTH, SCREEN_HEIGHT)
            self.showFullScreen()

        self.setStyleSheet("background-color: #0D1117;")

        # 中心 Widget
        central = QWidget(self)
        self.setCentralWidget(central)

        # 层叠布局 — 底层到顶层
        # z-order: bg → product_view → qr_view → face → status_label
        self.face_widget = CocoFaceWidget(central)
        self.face_widget.setGeometry(
            (self.width() - SCREEN_WIDTH) // 2, 10,
            SCREEN_WIDTH, SCREEN_HEIGHT
        )
        self.face_widget.clicked.connect(self._on_face_clicked)

        self.product_view = ProductView(central)
        self.product_view.setGeometry(
            (self.width() - SCREEN_WIDTH) // 2, 10,
            SCREEN_WIDTH, SCREEN_HEIGHT
        )

        self.qr_view = QRView(central)
        self.qr_view.setGeometry(
            (self.width() - SCREEN_WIDTH) // 2, 10,
            SCREEN_WIDTH, SCREEN_HEIGHT
        )

        # 状态标签（底部）
        self.status_label = QLabel("待机中", central)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(
            "QLabel { color: white; font-size: 14px; font-weight: bold; "
            "background-color: rgba(0,0,0,0.5); border-radius: 8px; padding: 4px 16px; }"
        )
        self.status_label.setFixedHeight(28)
        self.status_label.setFixedWidth(120)
        self.status_label.move(
            (self.width() - 120) // 2,
            SCREEN_HEIGHT + 10
        )
        self.status_label.raise_()

        # 语音文本标签（叠加在表情上）
        self.speech_label = QLabel("", central)
        self.speech_label.setAlignment(Qt.AlignCenter)
        self.speech_label.setWordWrap(True)
        self.speech_label.setStyleSheet(
            "QLabel { color: white; font-size: 15px; "
            "background-color: rgba(0,0,0,0.65); border-radius: 12px; "
            "padding: 10px 16px; }"
        )
        self.speech_label.setFixedWidth(SCREEN_WIDTH - 80)
        self.speech_label.setMinimumHeight(36)
        self.speech_label.move(
            (self.width() - SCREEN_WIDTH + 80) // 2,
            20 + SCREEN_HEIGHT - 100
        )
        self.speech_label.hide()

        # 事件总线连接（延迟绑定）
        self._event_bus = None
        self._state_machine = None

        log.info(f"Coco 屏幕初始化完成 ({SCREEN_WIDTH}x{SCREEN_HEIGHT}, "
                 f"debug={debug})")

    # ---- 公共接口 ----

    def set_state(self, state: str):
        """根据机器人状态切换视图"""
        old = self._state
        self._state = state

        # 更新表情
        face_state = state
        if state == "pricing":
            face_state = "speaking"  # pricing 复用 speaking 表情
        self.face_widget.set_state(face_state)

        # 更新状态标签
        self.status_label.setText(STATE_TO_CHINESE.get(state, state))

        # 视图切换
        self.product_view.clear()
        self.qr_view.hide_payment()

        if state == "pricing":
            self.product_view.setVisible(True)
            self.qr_view.setVisible(False)
        elif state == "payment":
            self.product_view.setVisible(False)
            self.qr_view.setVisible(True)
        else:
            self.product_view.setVisible(False)
            self.qr_view.setVisible(False)

        log.debug(f"屏幕状态: {old} → {state}")

    def show_product(self, product: ProductData):
        """显示商品信息卡片"""
        self.product_view.set_product(product)
        self.set_state("pricing")

    def show_payment(self, amount: float, item_name: str = ""):
        """显示收款码"""
        self.qr_view.show_payment(amount, item_name)
        self.set_state("payment")

    def show_speech_text(self, text: str, duration_ms: int = 4000):
        """在底部显示语音播报文字（自动隐藏）"""
        self.speech_label.setText(text)
        self.speech_label.show()
        self.speech_label.raise_()
        QTimer.singleShot(duration_ms, self.speech_label.hide)

    def bind(self, event_bus, state_machine=None):
        """绑定事件总线和状态机"""
        self._event_bus = event_bus
        self._state_machine = state_machine

        if state_machine:
            state_machine.on_change(self._on_state_change)

    def _on_state_change(self, from_state, to_state):
        """状态机回调"""
        self.set_state(to_state.value)

    def _on_face_clicked(self):
        """点击 Coco 面部"""
        if self._event_bus:
            from controller import EventType
            self._event_bus.publish_simple(EventType.WAKE_WORD_DETECTED)

    # ---- 鼠标拖拽（PC 调试时移动窗口） ----

    def mousePressEvent(self, event):
        if self.debug and event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.debug and hasattr(self, '_drag_pos'):
            self.move(event.globalPos() - self._drag_pos)
        super().mouseMoveEvent(event)


# ============================================================
# 应用入口
# ============================================================

class CocoScreenApp:
    """
    Coco UI 应用封装。

    用法:
        app = CocoScreenApp()
        app.bind(event_bus, state_machine)
        app.run()   # 阻塞，进入 Qt 事件循环
    """

    def __init__(self, debug: bool = DEBUG):
        self.debug = debug
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setApplicationName("Coco")

        self.window = CircularWindow(debug=debug)

    def bind(self, event_bus, state_machine=None):
        self.window.bind(event_bus, state_machine)

    def show_product(self, product):
        data = ProductData.from_product(product) if not isinstance(product, ProductData) else product
        self.window.show_product(data)

    def show_payment(self, amount: float, item_name: str = ""):
        self.window.show_payment(amount, item_name)

    def show_speech(self, text: str, duration_ms: int = 4000):
        self.window.show_speech_text(text, duration_ms)

    def set_state(self, state: str):
        self.window.set_state(state)

    def run(self):
        """进入 Qt 主循环（阻塞）"""
        self.window.show()
        log.info("Coco UI 主循环启动")
        sys.exit(self.qt_app.exec_())


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                        datefmt="%H:%M:%S")

    print("=" * 60)
    print("Coco UI 屏幕自测")
    print("=" * 60)
    print("\n启动测试窗口...")
    print("  - 点击 Coco 脸切换状态")
    print("  - 关闭窗口退出\n")

    # 测试：自动循环切换状态
    screen = CocoScreenApp(debug=True)

    # 每 3 秒循环切换状态
    states = ["idle", "listening", "thinking", "pricing", "dialog",
              "moving", "payment", "alert"]
    state_idx = [0]

    def cycle_state():
        s = states[state_idx[0] % len(states)]
        state_idx[0] += 1
        screen.set_state(s)
        print(f"  状态: {s}  ({STATE_TO_CHINESE.get(s, '')})")

    # 立即设置一个状态
    screen.set_state("idle")

    timer = QTimer()
    timer.timeout.connect(cycle_state)
    timer.start(3000)

    # 启动
    screen.run()
