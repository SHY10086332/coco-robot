"""
Coco 导购机器人 — 目标检测 & 人脸检测

- YOLOv8n: 轻量目标检测（商品、人等）
- Haar Cascade: 人脸检测（判断有无顾客在看屏幕）
- 统一检测结果数据结构
"""

import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

log = logging.getLogger("coco.vision.detect")

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from config import (
    YOLO_MODEL, YOLO_CONFIDENCE,
    CAMERA_WIDTH, CAMERA_HEIGHT,
    FACE_DETECTION_INTERVAL, DEBUG,
)


# ============================================================
# 检测结果
# ============================================================

@dataclass
class BBox:
    """边界框"""
    x: int
    y: int
    w: int
    h: int
    confidence: float = 1.0
    class_name: str = ""
    class_id: int = -1

    def area(self) -> int:
        return self.w * self.h

    def center(self) -> Tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2


@dataclass
class DetectionResult:
    """一帧的检测结果"""
    timestamp: float = field(default_factory=time.time)
    objects: List[BBox] = field(default_factory=list)   # YOLO 检测到的物体
    faces: List[BBox] = field(default_factory=list)     # 检测到的人脸
    has_person: bool = False
    has_face: bool = False


# ============================================================
# YOLO 目标检测
# ============================================================

class YOLODetector:
    """
    YOLOv8 目标检测器。

    用 ultralytics 库加载 YOLO 模型，树莓派5 推荐 yolov8n.pt（nano）。
    首次推理前会自动下载模型到本地。
    """

    def __init__(self, model_name: str = YOLO_MODEL,
                 confidence: float = YOLO_CONFIDENCE,
                 device: str = "cpu"):
        self.model_name = model_name
        self.confidence = confidence
        self.device = device
        self._model = None
        self._available = False
        self._total_inferences = 0
        self._total_time = 0.0

    def initialize(self):
        """加载 YOLO 模型"""
        try:
            from ultralytics import YOLO
            self._model = YOLO(self.model_name)
            self._available = True
            log.info(f"YOLO 模型 {self.model_name} 已加载 (device={self.device})")
        except ImportError:
            log.warning("ultralytics 未安装，目标检测不可用")
            self._available = False
        except Exception as e:
            log.error(f"YOLO 模型加载失败: {e}")
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def detect(self, image: np.ndarray) -> List[BBox]:
        """
        对单帧图像做目标检测。

        Returns:
            检测到的物体列表 (BBox)
        """
        if not self._available or self._model is None:
            return []

        t0 = time.time()
        try:
            results = self._model(image, conf=self.confidence, device=self.device,
                                  verbose=False)
        except Exception as e:
            log.error(f"YOLO 推理失败: {e}")
            return []

        self._total_inferences += 1
        self._total_time += time.time() - t0

        objects = []
        for r in results:
            boxes = r.boxes
            if boxes is None:
                continue
            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                cls_name = self._model.names.get(cls_id, str(cls_id))
                conf = float(boxes.conf[i].item())
                xyxy = boxes.xyxy[i].cpu().numpy()
                x1, y1, x2, y2 = map(int, xyxy)
                objects.append(BBox(
                    x=x1, y=y1, w=x2 - x1, h=y2 - y1,
                    confidence=conf, class_name=cls_name, class_id=cls_id,
                ))

        # 按置信度降序
        objects.sort(key=lambda b: b.confidence, reverse=True)
        return objects

    @property
    def avg_inference_time(self) -> float:
        if self._total_inferences == 0:
            return 0
        return self._total_time / self._total_inferences


# ============================================================
# 人脸检测 (Haar Cascade — 轻量、无需GPU)
# ============================================================

class FaceDetector:
    """
    基于 OpenCV Haar Cascade 的人脸检测。

    比深度学习方法更快、更省资源，适合树莓派。
    用于判断"有顾客在看屏幕"从而触发互动。

    用法:
        fd = FaceDetector()
        faces = fd.detect(frame)  # → List[BBox]
        if faces:
            trigger_greeting()
    """

    def __init__(self, scale_factor: float = 1.1,
                 min_neighbors: int = 5,
                 min_size: Tuple[int, int] = (60, 60)):
        self.scale_factor = scale_factor
        self.min_neighbors = min_neighbors
        self.min_size = min_size
        self._cascade = None
        self._available = False

        if CV2_AVAILABLE:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self._cascade = cv2.CascadeClassifier(cascade_path)
            self._available = not self._cascade.empty()

        if self._available:
            log.info("人脸检测器已就绪 (Haar Cascade)")
        else:
            log.warning("人脸检测器不可用")

    @property
    def available(self) -> bool:
        return self._available

    def detect(self, image: np.ndarray) -> List[BBox]:
        """
        检测图片中的人脸。

        Args:
            image: BGR 格式帧 (numpy array)

        Returns:
            人脸边界框列表
        """
        if not self._available or self._cascade is None:
            return []

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)  # 直方图均衡，提升低光照下的准确率

        rects = self._cascade.detectMultiScale(
            gray,
            scaleFactor=self.scale_factor,
            minNeighbors=self.min_neighbors,
            minSize=self.min_size,
            flags=cv2.CASCADE_SCALE_IMAGE,
        )

        faces = []
        for (x, y, w, h) in rects:
            faces.append(BBox(x=int(x), y=int(y), w=int(w), h=int(h),
                              class_name="face"))

        return faces


# ============================================================
# 视觉管道 — 组装 camera + detect
# ============================================================

class VisionPipeline:
    """
    整合摄像头 + 目标检测 + 人脸检测的完整管道。

    人脸检测每 N 帧跑一次（节省 CPU），目标检测按需触发。

    用法:
        vp = VisionPipeline()
        vp.initialize()
        vp.start()

        while running:
            result = vp.process_frame()  # 读帧+检测
            if result.has_face:
                print("检测到人脸！")
    """

    def __init__(self, camera_device: int = 0,
                 debug: bool = DEBUG,
                 enable_yolo: bool = True,
                 enable_face: bool = True):
        self.debug = debug
        self.enable_yolo = enable_yolo
        self.enable_face = enable_face

        # 延迟创建 — 让调用方控制
        from vision.camera import Camera
        self.camera = Camera(device=camera_device, debug=debug)

        self.yolo = YOLODetector() if enable_yolo else None
        self.face_detector = FaceDetector() if enable_face else None

        self._frame_idx = 0
        self._last_face_check = 0.0
        self._last_result = DetectionResult()
        self._on_detect_callbacks = []

    def initialize(self):
        """初始化所有检测模型"""
        if self.yolo:
            self.yolo.initialize()
        log.info("视觉管道初始化完成")

    def start(self):
        self.camera.start()

    def stop(self):
        self.camera.stop()

    def read_frame(self) -> Optional[np.ndarray]:
        """读取最新帧（不检测）"""
        return self.camera.read()

    def process_frame(self, force_detect: bool = False) -> DetectionResult:
        """
        读取一帧并执行检测。

        Args:
            force_detect: True=强制运行目标检测

        Returns:
            当前帧的检测结果
        """
        frame = self.camera.read()
        if frame is None:
            return self._last_result

        self._frame_idx += 1
        result = DetectionResult()

        # YOLO 目标检测（按需或每 30 帧）
        if self.yolo and self.yolo.available:
            if force_detect or self._frame_idx % 30 == 0:
                result.objects = self.yolo.detect(frame)

        # 人脸检测（每 0.5s 一次，节省 CPU）
        now = time.time()
        if self.face_detector and self.face_detector.available:
            if now - self._last_face_check >= FACE_DETECTION_INTERVAL:
                result.faces = self.face_detector.detect(frame)
                self._last_face_check = now

        result.has_person = any(
            obj.class_name in ("person", "人") for obj in result.objects
        ) or len(result.faces) > 0
        result.has_face = len(result.faces) > 0

        self._last_result = result

        # 触发回调
        for cb in self._on_detect_callbacks:
            try:
                cb(result)
            except Exception as e:
                log.error(f"检测回调异常: {e}")

        return result

    def on_detect(self, callback):
        """注册检测结果回调：callback(DetectionResult)"""
        self._on_detect_callbacks.append(callback)

    def get_latest_result(self) -> DetectionResult:
        return self._last_result


# ============================================================
# 绘制工具
# ============================================================

def draw_detections(frame: np.ndarray, result: DetectionResult,
                    show_labels: bool = True) -> np.ndarray:
    """
    在图像上绘制检测框。

    Args:
        frame: 原始帧 (BGR)
        result: 检测结果
        show_labels: 是否显示标签

    Returns:
        带标注的图像副本
    """
    if not CV2_AVAILABLE:
        return frame

    drawn = frame.copy()

    # 人脸框 — 蓝色
    for face in result.faces:
        cv2.rectangle(drawn, (face.x, face.y),
                      (face.x + face.w, face.y + face.h),
                      (255, 150, 50), 2)
        if show_labels:
            cv2.putText(drawn, "face", (face.x, face.y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 150, 50), 1)

    # 物体框 — 绿色 + 标签
    for obj in result.objects:
        color = (0, 255, 0) if obj.class_name == "person" else (0, 200, 100)
        cv2.rectangle(drawn, (obj.x, obj.y),
                      (obj.x + obj.w, obj.y + obj.h), color, 2)
        if show_labels:
            label = f"{obj.class_name} {obj.confidence:.2f}"
            cv2.putText(drawn, label, (obj.x, obj.y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

    # 状态栏
    status = []
    if result.has_face:
        status.append("FACE")
    if result.has_person:
        status.append("PERSON")
    status_text = " | ".join(status) if status else "IDLE"
    color = (0, 255, 0) if status else (128, 128, 128)
    cv2.putText(drawn, status_text, (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    return drawn


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    from vision.camera import Camera, DebugImageFeed

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                        datefmt="%H:%M:%S")

    print("=" * 60)
    print("视觉模块自测")
    print("=" * 60)

    # 1. 摄像头测试
    print("\n[1] 摄像头测试（模拟模式）")
    cam = Camera(debug=True)
    cam.start()
    time.sleep(0.5)
    frame = cam.read()
    cam.stop()
    if frame is not None:
        print(f"  分辨率: {frame.shape[1]}x{frame.shape[0]}")
        print(f"  通道数: {frame.shape[2]}")
        print(f"  数据类型: {frame.dtype}")
    else:
        print("  读取帧失败！")

    # 2. 人脸检测测试
    print("\n[2] 人脸检测测试")
    fd = FaceDetector()
    if fd.available:
        face_img = DebugImageFeed.generate("face")
        faces = fd.detect(face_img)
        print(f"  模拟人脸图 → 检测到 {len(faces)} 张脸")
        for i, f in enumerate(faces):
            print(f"    脸#{i+1}: ({f.x}, {f.y}) {f.w}x{f.h}")
    else:
        print("  人脸检测不可用（缺少 OpenCV）")

    # 3. YOLO 检测测试
    print("\n[3] YOLO 目标检测测试")
    yolo = YOLODetector()
    yolo.initialize()
    if yolo.available:
        print(f"  模型: {YOLO_MODEL}, 置信度阈值: {YOLO_CONFIDENCE}")
        shelf_img = DebugImageFeed.generate("shelf")
        objects = yolo.detect(shelf_img)
        print(f"  模拟货架 → 检测到 {len(objects)} 个物体")
        for obj in objects[:5]:
            print(f"    {obj.class_name} conf={obj.confidence:.2f} "
                  f"@ ({obj.x},{obj.y}) {obj.w}x{obj.h}")
    else:
        print("  YOLO 不可用（需安装 ultralytics），跳过")

    # 4. VisionPipeline 集成测试
    print("\n[4] VisionPipeline 集成测试")
    vp = VisionPipeline(debug=True, enable_yolo=False)
    vp.initialize()
    vp.start()

    results = []
    for _ in range(10):
        result = vp.process_frame()
        results.append(result)
        time.sleep(0.05)

    vp.stop()

    faces_detected = sum(1 for r in results if r.has_face)
    print(f"  处理 10 帧: {faces_detected} 帧检测到人脸（模拟模式下应为0）")
    print(f"  管道运行正常")

    # 5. 绘制测试
    print("\n[5] 绘制工具测试")
    if CV2_AVAILABLE:
        test_frame = DebugImageFeed.generate("shelf")
        fake_result = DetectionResult(
            objects=[
                BBox(100, 150, 80, 60, 0.85, "bottle"),
                BBox(300, 200, 50, 50, 0.72, "can"),
            ],
            faces=[],
            has_person=False,
            has_face=False,
        )
        annotated = draw_detections(test_frame, fake_result)
        print(f"  标注帧分辨率: {annotated.shape[1]}x{annotated.shape[0]}")
        print(f"  检测框已绘制")
    else:
        print("  跳过（无 OpenCV）")

    print("\n" + "=" * 60)
    print("视觉模块自测完成！")
    print("=" * 60)
