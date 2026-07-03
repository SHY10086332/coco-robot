"""
Coco 导购机器人 — 舵机驱动（头部云台）

SG90 微型舵机，50Hz PWM 控制：
- 脉宽 500μs  → 0°
- 脉宽 1500μs → 90°（中位）
- 脉宽 2500μs → 180°

在独立线程中持续发送 PWM 脉冲以保持舵机角度。
支持平滑过渡（限制转速）和扫描模式（搜索人时用）。
"""

import logging
import threading
import time
import math
from typing import Optional

log = logging.getLogger("coco.servo")

from config import (
    DEBUG,
    PIN_SERVO_PAN,
    SERVO_MIN_ANGLE, SERVO_MAX_ANGLE, SERVO_CENTER_ANGLE,
    SERVO_MIN_PULSE_US, SERVO_MAX_PULSE_US,
    SERVO_SPEED_DEG_PER_S,
)

# 尝试导入真实 GPIO
GPIO_AVAILABLE = False
if not DEBUG:
    try:
        import gpiod
        GPIO_AVAILABLE = True
    except ImportError:
        log.warning("gpiod 不可用，舵机回退到模拟模式")


class Servo:
    """
    SG90 舵机控制。

    用法:
        s = Servo(debug=False)
        s.start()                       # 启动后台 PWM 线程
        s.set_angle(90)                 # 转到 90°（中位）
        s.sweep(60, 120, period=2.0)    # 在 60°~120° 间来回扫描
        s.stop()                        # 停止并释放
    """

    def __init__(self, pin=PIN_SERVO_PAN,
                 min_angle=SERVO_MIN_ANGLE, max_angle=SERVO_MAX_ANGLE,
                 min_pulse_us=SERVO_MIN_PULSE_US, max_pulse_us=SERVO_MAX_PULSE_US,
                 speed_dps=SERVO_SPEED_DEG_PER_S,
                 debug: bool = DEBUG):
        self.pin = pin
        self.min_angle = min_angle
        self.max_angle = max_angle
        self.min_pulse_us = min_pulse_us
        self.max_pulse_us = max_pulse_us
        self.speed_dps = speed_dps       # 最大转速 (°/s)
        self.debug = debug

        # 状态
        self._current_angle = SERVO_CENTER_ANGLE
        self._target_angle = SERVO_CENTER_ANGLE
        self._pulse_us = self._angle_to_pulse(self._target_angle)

        # 扫描模式
        self._sweeping = False
        self._sweep_start = 0
        self._sweep_end = 0
        self._sweep_period = 2.0
        self._sweep_t0 = 0.0

        # 后台线程
        self._running = False
        self._stop_flag = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # GPIO
        self._chip = None
        self._line = None

    # ================================================================
    # 公共 API
    # ================================================================

    def start(self):
        """启动舵机 PWM 线程"""
        if not self.debug and GPIO_AVAILABLE:
            try:
                chip_num, line_num = self.pin
                self._chip = gpiod.Chip(f'/dev/gpiochip{chip_num}')
                self._line = self._chip.get_line(line_num)
                self._line.request('coco-servo',
                                   gpiod.LineRequest.DIRECTION_OUTPUT,
                                   default_vals=[0])
            except Exception as e:
                log.error(f"舵机 GPIO 初始化失败: {e}")
                self._line = None

        self._running = True
        self._stop_flag.clear()
        self._thread = threading.Thread(target=self._pwm_loop, daemon=True,
                                        name="servo-pan")
        self._thread.start()
        log.info(f"舵机已启动 (pin={self.pin}, debug={self.debug})")

    def stop(self):
        """停止 PWM 并释放 GPIO"""
        self._running = False
        self._stop_flag.set()
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._line:
            try:
                self._line.set_value(0)
                self._line.release()
            except Exception:
                pass
            self._line = None
        if self._chip:
            try:
                self._chip.close()
            except Exception:
                pass
            self._chip = None
        log.info("舵机已停止")

    def set_angle(self, angle: float):
        """
        设置目标角度。舵机会以 speed_dps 的速度平滑转过去。

        Args:
            angle: 目标角度 0~180°
        """
        self._sweeping = False
        self._target_angle = max(self.min_angle, min(self.max_angle, angle))

    def center(self):
        """回到中位 90°"""
        self.set_angle(SERVO_CENTER_ANGLE)

    def sweep(self, start_angle: float, end_angle: float, period: float = 2.0):
        """
        在两角之间来回扫描（搜索人时用）。

        Args:
            start_angle: 扫描起始角度
            end_angle:   扫描结束角度
            period:      一个完整来回的周期 (秒)
        """
        self._sweeping = True
        self._sweep_start = max(self.min_angle, min(self.max_angle, start_angle))
        self._sweep_end = max(self.min_angle, min(self.max_angle, end_angle))
        self._sweep_period = max(0.5, period)
        self._sweep_t0 = time.time()

    def stop_sweep(self):
        """停止扫描，保持在当前位置"""
        self._sweeping = False

    @property
    def angle(self) -> float:
        return self._current_angle

    @property
    def is_moving(self) -> bool:
        """是否还在转动（未到达目标）"""
        if self._sweeping:
            return True
        return abs(self._current_angle - self._target_angle) > 0.5

    # ================================================================
    # 内部
    # ================================================================

    def _angle_to_pulse(self, angle: float) -> float:
        """角度 → 脉宽 (μs)"""
        fraction = (angle - self.min_angle) / (self.max_angle - self.min_angle)
        return self.min_pulse_us + fraction * (self.max_pulse_us - self.min_pulse_us)

    def _pwm_loop(self):
        """后台 50Hz PWM 循环。每 20ms 发一个脉冲。"""
        PERIOD = 0.020  # 20ms = 50Hz

        while self._running and not self._stop_flag.is_set():
            t_start = time.time()

            # 更新角度
            self._update_angle()

            # 发送脉冲
            self._send_pulse()

            # 等待到下一个周期
            elapsed = time.time() - t_start
            sleep_time = PERIOD - elapsed
            if sleep_time > 0:
                self._stop_flag.wait(sleep_time)

    def _update_angle(self):
        """更新当前角度（平滑逼近目标 / 扫描模式）"""
        now = time.time()

        if self._sweeping:
            elapsed = now - self._sweep_t0
            phase = (elapsed % self._sweep_period) / self._sweep_period
            # 三角形波: 0→1→0→1...
            triangle = 2.0 * abs(phase - 0.5)
            self._target_angle = (self._sweep_start +
                                  triangle * (self._sweep_end - self._sweep_start))

        # 平滑移动（限速）
        error = self._target_angle - self._current_angle
        if abs(error) < 0.3:
            self._current_angle = self._target_angle
        else:
            max_step = self.speed_dps * 0.020  # 每帧最大旋转量
            step = max(-max_step, min(max_step, error))
            self._current_angle += step

        self._pulse_us = self._angle_to_pulse(self._current_angle)

    def _send_pulse(self):
        """发送一次 50Hz 脉冲"""
        if self.debug or self._line is None:
            return

        pulse_s = self._pulse_us / 1_000_000.0  # μs → s
        try:
            self._line.set_value(1)
            time.sleep(pulse_s)
            self._line.set_value(0)
        except Exception as e:
            log.error(f"舵机脉冲发送失败: {e}")


# ================================================================
# 自测
# ================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                        datefmt="%H:%M:%S")

    print("=" * 50)
    print("舵机模块自测（模拟模式）")
    print("=" * 50)

    s = Servo(debug=True)

    print("\n[1] 启动 + 中位")
    s.start()
    time.sleep(0.1)
    print(f"    当前角度: {s.angle:.1f}°")

    print("\n[2] 转到 45°（左看）")
    s.set_angle(45)
    for _ in range(20):
        time.sleep(0.02)
    print(f"    当前角度: {s.angle:.1f}°")

    print("\n[3] 转到 135°（右看）")
    s.set_angle(135)
    for _ in range(20):
        time.sleep(0.02)
    print(f"    当前角度: {s.angle:.1f}°")

    print("\n[4] 回中")
    s.center()
    for _ in range(20):
        time.sleep(0.02)
    print(f"    当前角度: {s.angle:.1f}°")

    print("\n[5] 扫描模式 (60°~120°, 周期1秒)")
    s.sweep(60, 120, period=1.0)
    prev = s.angle
    for i in range(50):
        time.sleep(0.02)
        cur = s.angle
        if abs(cur - prev) > 2:
            direction = "→" if cur > prev else "←"
            print(f"    {direction} {cur:.1f}°")
        prev = cur

    s.stop_sweep()
    s.stop()

    print("\n" + "=" * 50)
    print("舵机模块自测完成！")
    print("=" * 50)
