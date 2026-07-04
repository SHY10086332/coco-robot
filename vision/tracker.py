"""
Coco 导购机器人 — 视觉人体追踪器 (v6.2 双轴云台)

通过 YOLO 检测结果追踪顾客位置，协调双轴云台(pan+tilt)和履带底盘：
- 人在画面中间 ±30° → 只转头，底盘不动
- 人超出头可转范围 → 头转到极限 + 底盘缓慢转
- 垂直方向: 检测人脸的纵向位置 → 调整屏幕仰角(TILT_MIN~TILT_MAX)
- 无人时: 屏幕降到最低仰角(5°)"低头"待机
- 人太远（框小）→ 前进靠近
- 人太近（框大）→ 后退/停止
- 目标丢失 → pan扫瞄搜索, tilt降到最低

需要配合 VisionPipeline（YOLO 检测）和 Servo ×2（pan + tilt舵机）。
底盘指令以 (v, w) 形式输出，可直接送到 MotorController.set_velocity()。
"""

import logging
import time
import math
from typing import Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto

log = logging.getLogger("coco.tracker")

from config import (
    CAMERA_WIDTH, CAMERA_HEIGHT,
    SERVO_CENTER_ANGLE,
    TRACKER_ANGLE_P_GAIN, TRACKER_TILT_P_GAIN,
    TRACKER_HEAD_RANGE, TRACKER_CHASSIS_W_GAIN,
    TRACKER_FOLLOW_SPEED,
    TRACKER_PERSON_MIN_AREA, TRACKER_PERSON_MAX_AREA,
    TRACKER_LOST_TIMEOUT, TRACKER_SWEEP_SPEED,
    TRACKER_TILT_LOST_ANGLE, TRACKER_TILT_SMOOTH,
    TILT_MIN, TILT_MAX, TILT_SERVO_NEUTRAL, TILT_SERVO_RANGE,
)
from vision.detect import DetectionResult, BBox


# ============================================================
# 追踪器状态
# ============================================================

class TrackerState(Enum):
    IDLE = "idle"              # 未启用追踪
    SCANNING = "scanning"      # 丢失目标，扫瞄搜索中
    TRACKING = "tracking"      # 已锁定，头颅追踪中
    FOLLOWING = "following"    # 人在远处，驱底盘靠近


@dataclass
class TrackTarget:
    """追踪目标信息"""
    cx: float = 0.0                      # 目标在画面中的中心 X (像素)
    cy: float = 0.0                      # 目标在画面中的中心 Y (像素)
    area: float = 0.0                    # 边界框面积 (像素²)
    distance_est: float = 0.0            # 估算距离 (m)
    confidence: float = 0.0              # 检测置信度
    timestamp: float = 0.0               # 最后更新时间


@dataclass
class ChassisCmd:
    """底盘运动指令"""
    v: float = 0.0                       # 线速度 (m/s)
    w: float = 0.0                       # 角速度 (rad/s)


# ============================================================
# 人体追踪器
# ============================================================

class PersonTracker:
    """
    视觉人体追踪器。

    用法:
        # 在主循环中
        tracker = PersonTracker(servo)
        tracker.enable()

        vp = VisionPipeline()
        vp.on_detect(tracker.on_detection)   # 注册检测回调

        while running:
            cmd = tracker.step()
            if cmd:
                motor_controller.set_velocity(cmd.v, cmd.w)

    控制策略:
        ┌─────────────────────────────────────────────────┐
        │  画面坐标映射                                    │
        │                                                  │
        │  x=0 ──────────────── x=320 ──────────── x=640  │
        │  ├──── 头左转 ──────┤← 正前方 →├── 头右转 ────┤ │
        │  │  底盘逆时针      │  只动头   │  底盘顺时针    │ │
        │  └─────────────────────────────────────────────┘ │
        │                                                  │
        │  y=0 ─── 人近(框大) ─── y=240 ─── 人远(框小) ── │
        │          后退/停止               前进靠近        │
        └─────────────────────────────────────────────────┘
    """

    def __init__(self, servo_pan, servo_tilt=None,  # Servo 实例 (pan必需, tilt可选)
                 frame_width: int = CAMERA_WIDTH,
                 frame_height: int = CAMERA_HEIGHT,
                 head_range: float = TRACKER_HEAD_RANGE,
                 lost_timeout: float = TRACKER_LOST_TIMEOUT,
                 debug: bool = False):
        self.servo_pan = servo_pan
        self.servo_tilt = servo_tilt      # None = 单轴模式
        self.frame_w = frame_width
        self.frame_h = frame_height
        self.head_range = head_range
        self.lost_timeout = lost_timeout
        self.debug = debug

        self._frame_cx = frame_width / 2.0
        self._frame_cy = frame_height / 2.0  # 画面中心 Y

        # 当前追踪目标
        self.target = TrackTarget()

        # 状态机
        self._state = TrackerState.IDLE
        self._enabled = False

        # 丢失计时
        self._lost_at: Optional[float] = None

        # 平滑滤波
        self._smooth_cx = 0.0
        self._smooth_cy = 0.0               # 垂直方向平滑
        self._smooth_area = 0.0
        self._smooth_alpha = 0.3
        self._smooth_tilt_angle = float(TILT_MIN)  # 俯仰角平滑（起始低头）

        # 输出
        self.cmd = ChassisCmd()

    # ================================================================
    # 公共 API
    # ================================================================

    @property
    def state(self) -> TrackerState:
        return self._state

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def has_target(self) -> bool:
        """当前是否锁定目标"""
        return self._state in (TrackerState.TRACKING, TrackerState.FOLLOWING)

    def enable(self):
        """启用追踪"""
        self._enabled = True
        self._lost_at = None
        self._state = TrackerState.SCANNING
        self.servo_pan.sweep(90 - 40, 90 + 40, period=2.0)
        # tilt: 默认仰角等待
        if self.servo_tilt:
            self.servo_tilt.set_angle(TILT_SERVO_NEUTRAL)
        log.info("人体追踪已启用（双轴云台），开始扫瞄搜索")

    def disable(self):
        """禁用追踪，回到中位"""
        self._enabled = False
        self._state = TrackerState.IDLE
        self._lost_at = None
        self.servo_pan.stop_sweep()
        self.servo_pan.center()
        if self.servo_tilt:
            self.servo_tilt.set_angle(TILT_SERVO_NEUTRAL)
        self.cmd = ChassisCmd()
        log.info("人体追踪已禁用")

    def on_detection(self, result: DetectionResult):
        """
        检测结果回调 — 由 VisionPipeline 调用。

        每次收到新检测帧时，更新内部追踪目标。
        """
        if not self._enabled:
            return

        person = self._find_best_person(result)
        if person is not None:
            cx, cy = person.center()
            self._smooth_cx += self._smooth_alpha * (cx - self._smooth_cx)
            self._smooth_cy += self._smooth_alpha * (cy - self._smooth_cy)
            self._smooth_area += self._smooth_alpha * (person.area() - self._smooth_area)

            self.target = TrackTarget(
                cx=cx,
                cy=cy,
                area=person.area(),
                distance_est=self._estimate_distance(person.area()),
                confidence=person.confidence,
                timestamp=time.time(),
            )
            self._lost_at = None
        else:
            # 这一帧没检测到人
            if self._lost_at is None:
                self._lost_at = time.time()

    def step(self) -> ChassisCmd:
        """
        主循环每帧调用一次。

        Returns:
            给底盘的 (v, w) 指令，状态为 IDLE 时返回零指令。
        """
        if not self._enabled or self._state == TrackerState.IDLE:
            return ChassisCmd()

        now = time.time()

        # 判断目标是否丢失
        if self._lost_at is not None:
            lost_duration = now - self._lost_at
            if lost_duration > self.lost_timeout and self._state != TrackerState.SCANNING:
                log.info(f"目标丢失 {lost_duration:.1f}s，进入扫描模式")
                self._state = TrackerState.SCANNING
                self.servo_pan.sweep(90 - 50, 90 + 50, period=2.5)
                # 低头表示"失落"
                if self.servo_tilt:
                    self._set_tilt_angle(float(TILT_MIN))
        else:
            # 有目标 → 追踪
            self.servo_pan.stop_sweep()
            self._track(now)

        return self.cmd

    # ================================================================
    # 内部 — 目标选择
    # ================================================================

    def _find_best_person(self, result: DetectionResult) -> Optional[BBox]:
        """
        从检测结果中选出最佳追踪目标。

        策略：选画面中最大的 person（默认离我最近）。
        多人场景下未来可以加人脸匹配来锁定特定顾客。
        """
        persons = [obj for obj in result.objects
                   if obj.class_name in ("person", "人")]
        if not persons:
            return None
        # 按面积降序，取最大的
        persons.sort(key=lambda b: b.area(), reverse=True)
        return persons[0]

    # ================================================================
    # 内部 — 追踪控制
    # ================================================================

    def _track(self, now: float):
        """锁定目标后的追踪控制（双轴）。"""
        cx = self._smooth_cx
        cy = self._smooth_cy
        area = self._smooth_area

        # ---- 1. 水平偏差 → pan 舵机角度 ----
        pixel_error_x = cx - self._frame_cx
        normalized_error_x = pixel_error_x / (self.frame_w / 2.0)

        angle_offset = normalized_error_x * TRACKER_ANGLE_P_GAIN * 180
        target_pan_angle = SERVO_CENTER_ANGLE + angle_offset
        self.servo_pan.set_angle(target_pan_angle)

        # ---- 2. 垂直偏差 → tilt 舵机角度 ----
        if self.servo_tilt:
            # cy 越小 = 人越高（头顶在画面顶部）
            # cy 越大 = 人越低（脚在画面底部）
            pixel_error_y = cy - self._frame_cy
            normalized_error_y = pixel_error_y / (self.frame_h / 2.0)

            # 人偏上（cy小）→ 仰角增大（抬头看高个子/远处）
            # 人偏下（cy大）→ 仰角减小（低头看近处/小孩）
            tilt_angle = TILT_NEUTRAL - normalized_error_y * TRACKER_TILT_P_GAIN * 180
            tilt_angle = max(TILT_MIN, min(TILT_MAX, tilt_angle))
            self._set_tilt_angle(tilt_angle)

        # ---- 3. 判断是否需要转底盘 ----
        actual_angle = self.servo_pan.angle
        head_offset = actual_angle - SERVO_CENTER_ANGLE

        v, w = 0.0, 0.0

        if abs(head_offset) > self.head_range:
            w = math.copysign(TRACKER_CHASSIS_W_GAIN, head_offset)
            self._state = TrackerState.TRACKING

        # ---- 4. 距离控制（基于框面积） ----
        if area > 0:
            if area < TRACKER_PERSON_MIN_AREA:
                v = TRACKER_FOLLOW_SPEED
                self._state = TrackerState.FOLLOWING
            elif area > TRACKER_PERSON_MAX_AREA:
                v = -TRACKER_FOLLOW_SPEED * 0.5
                self._state = TrackerState.TRACKING
            else:
                if self._state in (TrackerState.FOLLOWING, TrackerState.SCANNING):
                    self._state = TrackerState.TRACKING

        self.cmd = ChassisCmd(v=v, w=w)

    # ================================================================
    # 内部 — 俯仰控制
    # ================================================================

    def _set_tilt_angle(self, target_deg: float):
        """设置俯仰仰角，平滑过渡并转换为舵机角度。"""
        # 一阶低通平滑
        self._smooth_tilt_angle += TRACKER_TILT_SMOOTH * (target_deg - self._smooth_tilt_angle)
        # 仰角 → 舵机角度 (TILT_SERVO_NEUTRAL = 28°, TILT_SERVO_RANGE = 50°)
        servo_angle = TILT_SERVO_NEUTRAL + (self._smooth_tilt_angle - TILT_NEUTRAL) * (TILT_SERVO_RANGE / (TILT_MAX - TILT_NEUTRAL))
        self.servo_tilt.set_angle(servo_angle)

    # ================================================================
    # 内部 — 距离估算
    # ================================================================

    def _estimate_distance(self, area: float) -> float:
        """
        从边界框面积粗略估计距离。

        原理：同一个人，距离越远，成像越小。
        设参考面积 A₀（人在 1m 处的像素面积），则:
            distance ≈ sqrt(A₀ / area)

        这是个粗略估计，受人体体型差异影响。用于"靠近/远离"判断足够，
        不建议用于精确导航。
        """
        if area <= 0:
            return 999.0
        # 经验值：一个中等身材的人站在 1 米处，YOLO 框约 15000 px²
        REF_AREA = 15000.0
        return math.sqrt(REF_AREA / area)

    # ================================================================
    # 诊断
    # ================================================================

    def status_str(self) -> str:
        """单行状态摘要，方便打 log"""
        t = self.target
        tilt_str = f"tilt={self._smooth_tilt_angle:.0f}°" if self.servo_tilt else ""
        return (f"[{self._state.value}] "
                f"bbox=({t.cx:.0f},{t.cy:.0f}) area={t.area:.0f} "
                f"dist≈{t.distance_est:.2f}m "
                f"pan={self.servo_pan.angle:.0f}° {tilt_str} "
                f"cmd=(v={self.cmd.v:.2f}, w={self.cmd.w:.2f})")


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    import random
    from hardware.servo import Servo

    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                        datefmt="%H:%M:%S")

    print("=" * 60)
    print("人体追踪器自测（模拟模式）")
    print("=" * 60)

    # 创建模拟舵机（双轴）
    servo_pan = Servo(debug=True)
    servo_pan.start()
    servo_tilt = Servo(debug=True)
    servo_tilt.start()

    tracker = PersonTracker(servo_pan, servo_tilt, debug=True, lost_timeout=0.0)
    tracker.enable()

    print("\n[1] 模拟检测到人在画面中央（正常距离）")
    center_person = BBox(
        x=290, y=150, w=60, h=150,
        confidence=0.85, class_name="person"
    )
    result = DetectionResult(objects=[center_person])
    tracker.on_detection(result)
    cmd = tracker.step()
    print(f"    目标: cx={tracker.target.cx:.0f}, area={tracker.target.area:.0f}")
    print(f"    pan舵机: {tracker.servo_pan.angle:.0f}°")
    print(f"    tilt仰角: {tracker._smooth_tilt_angle:.0f}°")
    print(f"    底盘: v={cmd.v:.3f}, w={cmd.w:.3f}")
    print(f"    预期: pan≈90°(中位), tilt≈28°(默认), 底盘不动")

    print("\n[2] 模拟人在画面右边 + 偏上（需头右转+抬头）")
    for _ in range(5):
        right_high_person = BBox(
            x=480, y=80, w=60, h=150,
            confidence=0.8, class_name="person"
        )
        result = DetectionResult(objects=[right_high_person])
        tracker.on_detection(result)
        tracker.step()
        time.sleep(0.05)
    print(f"    目标cx: {tracker.target.cx:.0f}, cy: {tracker.target.cy:.0f}")
    print(f"    pan舵机: {tracker.servo_pan.angle:.0f}°")
    print(f"    tilt仰角: {tracker._smooth_tilt_angle:.0f}°")
    print(f"    预期: pan>90°(右偏), tilt>28°(抬头看高处)")

    print("\n[3] 模拟人太远（小框 → 前进靠近）")
    for _ in range(5):
        far_person = BBox(
            x=310, y=200, w=25, h=60,
            confidence=0.7, class_name="person"
        )
        result = DetectionResult(objects=[far_person])
        tracker.on_detection(result)
        cmd = tracker.step()
    print(f"    面积: {tracker.target.area:.0f} px² (阈值 {TRACKER_PERSON_MIN_AREA})")
    print(f"    底盘: v={cmd.v:.3f}, w={cmd.w:.3f}")
    print(f"    预期: v>0 (前进), 状态=FOLLOWING")

    print("\n[4] 模拟目标丢失 → 扫描 + 低头")
    for i in range(10):
        empty_result = DetectionResult(objects=[])
        tracker.on_detection(empty_result)
        cmd = tracker.step()
        if tracker.state == TrackerState.SCANNING:
            break
        time.sleep(0.02)
    print(f"    状态: {tracker.state.value}")
    print(f"    pan舵机: {tracker.servo_pan.angle:.0f}° (应在扫瞄中)")
    print(f"    tilt仰角: {tracker._smooth_tilt_angle:.0f}°")
    print(f"    预期: SCANNING, tilt→{TILT_MIN}°(低头)")

    print("\n[5] 扫描中重新发现目标")
    found_person = BBox(
        x=320, y=200, w=50, h=130,
        confidence=0.8, class_name="person"
    )
    result = DetectionResult(objects=[found_person])
    tracker.on_detection(result)
    cmd = tracker.step()
    print(f"    状态: {tracker.state.value}")
    print(f"    预期: TRACKING, 退出扫描")

    print("\n[6] 禁用追踪")
    tracker.disable()
    print(f"    状态: {tracker.state.value}")
    print(f"    pan舵机: {tracker.servo_pan.angle:.0f}°")
    print(f"    预期: IDLE, 舵机回到 90°")

    servo_pan.stop()
    servo_tilt.stop()

    print("\n" + "=" * 60)
    print("人体追踪器自测完成！")
    print("=" * 60)
