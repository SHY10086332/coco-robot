"""
Coco 导购机器人 — 摄像头采集

支持 USB 摄像头（生产模式）和模拟图像（DEBUG 模式）。
线程安全的帧读取，避免阻塞主循环。
"""

import logging
import threading
import time
from typing import Optional, Tuple

import numpy as np

log = logging.getLogger("coco.vision.camera")

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    log.warning("OpenCV 未安装，摄像头不可用")

from config import CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS, DEBUG


class Camera:
    """
    USB 摄像头采集，后台线程持续抓帧。

    用法:
        cam = Camera(device=0)
        cam.start()
        frame = cam.read()  # 非阻塞，读最新帧
        cam.stop()
    """

    def __init__(self, device: int = 0,
                 width: int = CAMERA_WIDTH,
                 height: int = CAMERA_HEIGHT,
                 fps: int = CAMERA_FPS,
                 debug: bool = DEBUG):
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self.debug = debug
        self._cap = None
        self._frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._frame_count = 0

    @property
    def is_open(self) -> bool:
        return self._cap is not None and (self.debug or self._cap.isOpened())

    def start(self):
        """启动摄像头采集线程"""
        if not self.debug:
            if not CV2_AVAILABLE:
                log.error("OpenCV 不可用，无法打开摄像头")
                return
            self._cap = cv2.VideoCapture(self.device)
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self._cap.set(cv2.CAP_PROP_FPS, self.fps)
            if not self._cap.isOpened():
                log.error(f"无法打开摄像头 device={self.device}")
                self._cap = None
                return
            actual_w = self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_h = self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            log.info(f"摄像头已打开 {actual_w:.0f}x{actual_h:.0f} @ device={self.device}")

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True,
                                        name="camera")
        self._thread.start()
        log.info("摄像头采集线程已启动")

    def stop(self):
        """停止采集并释放摄像头"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._cap:
            self._cap.release()
            self._cap = None
        log.info("摄像头已关闭")

    def read(self) -> Optional[np.ndarray]:
        """非阻塞读取最新帧（返回副本）"""
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    def _capture_loop(self):
        """后台采集循环"""
        interval = 1.0 / max(self.fps, 1)

        while self._running:
            frame = None

            if self.debug:
                frame = self._debug_frame()
            elif self._cap and self._cap.isOpened():
                ret, frame = self._cap.read()
                if not ret:
                    log.warning("读取帧失败")
                    time.sleep(0.01)
                    continue

            if frame is not None:
                with self._lock:
                    self._frame = frame
                self._frame_count += 1

            elapsed = time.time() % interval
            time.sleep(max(0, interval - elapsed * 0.001))

    def _debug_frame(self) -> np.ndarray:
        """生成模拟帧：彩色条纹 + 帧号"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # 渐变色背景 — 模拟货架场景
        for y in range(self.height):
            r = int(40 + 20 * np.sin(y * 0.01 + time.time()))
            g = int(60 + 30 * np.sin(y * 0.015 + time.time() * 0.7))
            b = int(80 + 40 * np.sin(y * 0.008 + time.time() * 1.3))
            frame[y, :] = (b, g, r)

        # 画几个"货架"矩形
        shelf_colors = [(180, 120, 60), (120, 80, 40), (200, 150, 100)]
        for shelf_y, color in zip([100, 240, 380], shelf_colors):
            cv2.rectangle(frame, (40, shelf_y), (600, shelf_y + 80), color, -1)
            cv2.rectangle(frame, (40, shelf_y), (600, shelf_y + 80), (255, 255, 255), 1)

        # 画一些"商品"小方块
        import random
        rng = random.Random(int(time.time() * 10) % 10000)
        for shelf_y in [120, 260, 400]:
            for i in range(6):
                x = 60 + i * 95
                c = (rng.randint(50, 255), rng.randint(50, 255), rng.randint(50, 255))
                cv2.rectangle(frame, (x, shelf_y - 20), (x + 70, shelf_y + 30), c, -1)
                cv2.rectangle(frame, (x, shelf_y - 20), (x + 70, shelf_y + 30),
                              (255, 255, 255), 1)

        # 帧号
        cv2.putText(frame, f"SIM #{self._frame_count}",
                    (10, self.height - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return frame


class DebugImageFeed:
    """单张图片模拟（用于检测调试）"""

    _test_images = {
        "shelf": "模拟货架场景（彩色方块）",
        "face": "模拟含人脸场景",
        "empty": "空场景",
    }

    @staticmethod
    def generate(mode: str = "shelf",
                 width: int = CAMERA_WIDTH,
                 height: int = CAMERA_HEIGHT) -> np.ndarray:
        """生成测试图像"""
        if mode == "shelf":
            cam = Camera(debug=True, width=width, height=height)
            # 临时启动后台线程拿一帧
            cam._running = True
            frame = cam._debug_frame()
            return frame
        elif mode == "face":
            # 纯色背景 + 模拟人脸区域（椭圆）
            frame = np.ones((height, width, 3), dtype=np.uint8) * 200
            cx, cy = width // 2, height // 2
            cv2.ellipse(frame, (cx, cy), (80, 100), 0, 0, 360, (180, 140, 120), -1)
            cv2.circle(frame, (cx - 30, cy - 20), 8, (50, 50, 50), -1)
            cv2.circle(frame, (cx + 30, cy - 20), 8, (50, 50, 50), -1)
            cv2.ellipse(frame, (cx, cy + 30), (25, 12), 0, 0, 180, (80, 60, 60), 2)
            return frame
        else:  # empty
            return np.ones((height, width, 3), dtype=np.uint8) * 180
