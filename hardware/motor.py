"""
Coco 导购机器人 — 电机控制模块

L298N 双H桥驱动 + 差速履带底盘控制。
支持 DEBUG 模式（PC模拟）和生产模式（gpiod / Orange Pi 5 / 树莓派 GPIO）。

L298N 控制逻辑（每路）:
    IN1=HIGH, IN2=LOW  → 正转（前进）
    IN1=LOW,  IN2=HIGH → 反转（后退）
    IN1=LOW,  IN2=LOW  → 刹车（短路制动）
    PWM 占空比 0~100%  → 速度调节
"""

import logging
import math
import time
import sys
import threading
from dataclasses import dataclass, field
from typing import Optional, Tuple, Callable

log = logging.getLogger("coco.motor")

from config import (
    DEBUG,
    PIN_MOTOR_LEFT_PWM, PIN_MOTOR_LEFT_IN1, PIN_MOTOR_LEFT_IN2,
    PIN_MOTOR_RIGHT_PWM, PIN_MOTOR_RIGHT_IN1, PIN_MOTOR_RIGHT_IN2,
    PIN_ULTRASONIC_TRIG, PIN_ULTRASONIC_ECHO,
    MOTOR_RATED_RPM, WHEEL_RADIUS, TRACK_WIDTH, ODOMETRY_INTERVAL,
    MAX_LINEAR_SPEED, MAX_ANGULAR_SPEED, EMERGENCY_STOP_DISTANCE,
    PID_KP, PID_KI, PID_KD,
)
from kinematics import DifferentialKinematics, PIDController, WheelSpeed

# 尝试导入真实 GPIO（使用 Linux 标准 gpiod 接口，兼容 Orange Pi 5 / 树莓派等）
GPIO_AVAILABLE = False
if not DEBUG:
    try:
        import gpiod
        GPIO_AVAILABLE = True
    except ImportError:
        log.warning("gpiod 不可用，回退到模拟模式。安装: pip install gpiod")


# ============================================================
# GPIO 抽象层
# ============================================================

class GPIOWrapper:
    """GPIO 抽象：DEBUG 模式打印日志，生产模式通过 gpiod 操作真实引脚。

    pin 参数统一使用 (chip, line) 元组，如 (4, 18) 对应 /dev/gpiochip4 line 18。
    软件 PWM 通过后台线程实现（兼容没有硬件 PWM 的 SBC）。
    """

    PWM_FREQ = 1000  # 软件 PWM 默认频率 (Hz)

    def __init__(self, debug: bool = True):
        self.debug = debug
        self._pin_outputs = {}      # pin → bool (模拟输出状态)
        self._pwm_duties = {}       # pin → float (PWM 占空比 0~100)
        self._pwm_stop_flags = {}   # pin → threading.Event
        self._pwm_threads = {}      # pin → threading.Thread
        self._lines = {}            # pin → (gpiod.Chip, gpiod.Line) 真实 GPIO

    # ----------------------------------------------------------
    # 内部：获取/缓存 gpiod line
    # ----------------------------------------------------------
    def _get_line(self, pin: tuple):
        """返回已缓存的 gpiod Line 对象，必要时打开 chip 并请求。"""
        if pin not in self._lines:
            chip_num, line_num = pin
            chip = gpiod.Chip(f'/dev/gpiochip{chip_num}')
            line = chip.get_line(line_num)
            self._lines[pin] = (chip, line)
        return self._lines[pin]

    # ----------------------------------------------------------
    # 公共 API（与旧版 RPi.GPIO 版完全兼容）
    # ----------------------------------------------------------
    def setup(self, pin, mode: str, initial=None):
        if self.debug:
            self._pin_outputs[pin] = initial if initial is not None else False
            log.debug(f"[SIM] GPIO{pin} 初始化 mode={mode}")
            return

        chip, line = self._get_line(pin)
        if mode == "OUT":
            default_val = 1 if initial else 0
            line.request('coco', gpiod.LineRequest.DIRECTION_OUTPUT,
                         default_vals=[default_val])
        else:
            line.request('coco', gpiod.LineRequest.DIRECTION_INPUT)

    def output(self, pin, state: bool):
        if self.debug:
            self._pin_outputs[pin] = state
            return
        _, line = self._lines[pin]
        line.set_value(1 if state else 0)

    def input(self, pin) -> bool:
        if self.debug:
            return self._pin_outputs.get(pin, False)
        _, line = self._lines[pin]
        return line.get_value() == 1

    def pwm_start(self, pin, duty: float):
        """duty: 0~100。软件 PWM 通过后台线程实现。"""
        duty = max(0, min(100, duty))
        self._pwm_duties[pin] = duty

        if self.debug:
            return

        # 停止旧 PWM 线程（如果存在）
        self.pwm_stop(pin)

        # 确保 GPIO 已初始化为输出
        chip, line = self._get_line(pin)
        if not line.is_requested():
            line.request('coco', gpiod.LineRequest.DIRECTION_OUTPUT,
                         default_vals=[0])

        # 启动 PWM 线程
        stop_flag = threading.Event()
        self._pwm_stop_flags[pin] = stop_flag

        t = threading.Thread(
            target=self._pwm_worker,
            args=(pin,),
            daemon=True
        )
        self._pwm_threads[pin] = t
        t.start()

    def pwm_stop(self, pin):
        if self.debug:
            self._pwm_duties[pin] = 0
            return

        # 发送停止信号
        if pin in self._pwm_stop_flags:
            self._pwm_stop_flags[pin].set()

        # 等待线程结束
        if pin in self._pwm_threads:
            self._pwm_threads[pin].join(timeout=0.5)
            del self._pwm_threads[pin]

        if pin in self._pwm_stop_flags:
            del self._pwm_stop_flags[pin]

        # 输出置低
        if pin in self._lines:
            try:
                _, line = self._lines[pin]
                line.set_value(0)
            except Exception:
                pass

        self._pwm_duties[pin] = 0

    def get_pwm(self, pin) -> float:
        """返回当前 PWM 占空比"""
        return self._pwm_duties.get(pin, 0)

    def cleanup(self):
        # 停止所有 PWM
        for pin in list(self._pwm_threads):
            self.pwm_stop(pin)

        # 释放所有 GPIO lines
        for pin in list(self._lines):
            try:
                _, line = self._lines[pin]
                line.set_value(0)
                line.release()
            except Exception:
                pass
        self._lines.clear()
        log.info("GPIO 已清理")

    # ----------------------------------------------------------
    # 软件 PWM 工作线程
    # ----------------------------------------------------------
    def _pwm_worker(self, pin):
        """后台线程：按占空比翻转 GPIO 实现软件 PWM。"""
        period = 1.0 / self.PWM_FREQ
        _, line = self._lines[pin]
        stop_flag = self._pwm_stop_flags[pin]

        while not stop_flag.is_set():
            duty = self._pwm_duties.get(pin, 0)
            if duty <= 0:
                line.set_value(0)
                stop_flag.wait(period)  # 休眠一个周期后再检查
            elif duty >= 100:
                line.set_value(1)
                stop_flag.wait(period)
            else:
                on_time = period * duty / 100.0
                off_time = period - on_time
                line.set_value(1)
                stop_flag.wait(on_time)
                if stop_flag.is_set():
                    break
                line.set_value(0)
                stop_flag.wait(off_time)


# ============================================================
# 单路电机控制（L298N 单通道）
# ============================================================

@dataclass
class MotorStatus:
    """电机状态"""
    target_speed: float = 0.0    # 目标轮速 (m/s)
    actual_speed: float = 0.0    # 实际轮速 (m/s，编码器测算)
    pwm_duty: float = 0.0        # 当前 PWM 占空比 (%)
    direction: int = 0           # 1=正转, 0=停止, -1=反转
    fault: bool = False          # 故障标志


class SingleMotor:
    """
    L298N 单路电机控制。

    每个电机需要 3 个 GPIO:
    - pwm_pin:   PWM 速度控制（使能脚 ENA/ENB）
    - in1_pin:   方向控制 1
    - in2_pin:   方向控制 2
    """

    def __init__(self, name: str, pwm_pin: int, in1_pin: int, in2_pin: int,
                 gpio: GPIOWrapper, wheel_radius: float = 0.032):
        self.name = name
        self.pwm_pin = pwm_pin
        self.in1_pin = in1_pin
        self.in2_pin = in2_pin
        self.gpio = gpio
        self.wheel_radius = wheel_radius
        self.status = MotorStatus()

        # 初始化 GPIO
        self.gpio.setup(pwm_pin, "OUT", initial=False)
        self.gpio.setup(in1_pin, "OUT", initial=False)
        self.gpio.setup(in2_pin, "OUT", initial=False)

    def set_speed(self, linear_speed: float):
        """
        设置轮子线速度。

        Args:
            linear_speed: 轮子线速度 (m/s)，正=前进，负=后退
        """
        self.status.target_speed = linear_speed

        if abs(linear_speed) < 0.001:
            self._brake()
            return

        # 方向判断
        forward = linear_speed > 0

        # 线速度 → 需要占空比
        # 电机额定转速 100 RPM，额定电压 12V
        # 轮子周长 = 2πr = 2*3.14*0.032 ≈ 0.201m
        # 额定线速度 = 100 RPM * 0.201m / 60s ≈ 0.335 m/s
        max_linear = (MOTOR_RATED_RPM / 60.0) * (2 * math.pi * self.wheel_radius)
        duty = (abs(linear_speed) / max_linear) * 100.0
        duty = max(0, min(100, duty))

        # L298N 控制信号
        if forward:
            self.gpio.output(self.in1_pin, True)
            self.gpio.output(self.in2_pin, False)
            self.status.direction = 1
        else:
            self.gpio.output(self.in1_pin, False)
            self.gpio.output(self.in2_pin, True)
            self.status.direction = -1

        self.gpio.pwm_start(self.pwm_pin, duty)
        self.status.pwm_duty = duty

    def _brake(self):
        """短路制动：IN1=LOW, IN2=LOW（L298N 快速刹车）"""
        self.gpio.output(self.in1_pin, False)
        self.gpio.output(self.in2_pin, False)
        self.gpio.pwm_start(self.pwm_pin, 0)
        self.status.direction = 0
        self.status.pwm_duty = 0
        self.status.target_speed = 0

    def stop(self):
        """停止并释放"""
        self._brake()
        self.gpio.pwm_stop(self.pwm_pin)


# ============================================================
# 超声波距离传感器（HC-SR04）
# ============================================================

class UltrasonicSensor:
    """
    HC-SR04 超声波距离传感器。

    工作原理：
    1. Trig 发 10μs 高电平脉冲
    2. 模块自动发 8 个 40kHz 超声波
    3. Echo 收到回波后拉高，高电平持续时间 = 声波往返时间
    4. 距离 = (高电平时间 × 340m/s) / 2
    """

    def __init__(self, trig_pin: int, echo_pin: int,
                 gpio: GPIOWrapper, debug: bool = True):
        self.trig_pin = trig_pin
        self.echo_pin = echo_pin
        self.gpio = gpio
        self.debug = debug
        self._last_distance: float = 999.0
        self._sim_obstacle_distance: Optional[float] = None  # 模拟用

        self.gpio.setup(trig_pin, "OUT", initial=False)
        self.gpio.setup(echo_pin, "IN")

    def set_sim_distance(self, distance_m: Optional[float]):
        """模拟模式下设置"障碍物距离"（None=无障碍）"""
        self._sim_obstacle_distance = distance_m

    def read_distance(self) -> float:
        """
        读取距离 (m)。返回 999.0 表示未检测到障碍物。

        Returns:
            距离 (m)，范围约 0.02~4.0m
        """
        if self.debug:
            if self._sim_obstacle_distance is not None:
                self._last_distance = self._sim_obstacle_distance
            else:
                self._last_distance = 999.0
            return self._last_distance

        # 发送 10μs 触发脉冲
        self.gpio.output(self.trig_pin, True)
        time.sleep(0.00001)  # 10μs
        self.gpio.output(self.trig_pin, False)

        # 测量 Echo 高电平持续时间
        timeout = time.time() + 0.04  # 40ms 超时（≈6.8m）
        pulse_start = None
        pulse_end = None

        while time.time() < timeout:
            if self.gpio.input(self.echo_pin) and pulse_start is None:
                pulse_start = time.time()
            elif not self.gpio.input(self.echo_pin) and pulse_start is not None:
                pulse_end = time.time()
                break
            time.sleep(0.00001)

        if pulse_start is not None and pulse_end is not None:
            duration = pulse_end - pulse_start
            distance = (duration * 343.0) / 2.0  # 声速 343m/s
            self._last_distance = distance
            return distance

        self._last_distance = 999.0
        return 999.0

    def is_obstacle_near(self, threshold_m: float = None) -> bool:
        """检查是否有障碍物在阈值距离内"""
        if threshold_m is None:
            threshold_m = EMERGENCY_STOP_DISTANCE
        return self.read_distance() < threshold_m


# ============================================================
# 差速底盘控制器
# ============================================================

@dataclass
class ChassisState:
    """底盘完整状态（调试/上报用）"""
    v_target: float = 0.0         # 目标线速度 (m/s)
    w_target: float = 0.0         # 目标角速度 (rad/s)
    left: MotorStatus = field(default_factory=MotorStatus)
    right: MotorStatus = field(default_factory=MotorStatus)
    emergency_stop: bool = False
    distance_to_obstacle: float = 999.0


class MotorController:
    """
    差速底盘控制器 — 顶层接口。

    用法:
        mc = MotorController(debug=True)
        mc.set_velocity(0.2, 0.0)   # 0.2 m/s 直行
        mc.set_velocity(0.0, 1.0)   # 原地左转
        mc.emergency_stop()         # 急停
        mc.stop()                   # 释放所有电机

    控制循环（50Hz）:
        while running:
            mc.update()             # 读传感器 + 急停检测
            mc.set_velocity(v, w)   # 根据导航指令驱动
            time.sleep(0.02)
    """

    def __init__(self, debug: bool = True):
        self.debug = debug
        self.gpio = GPIOWrapper(debug=debug)

        # 运动学模型
        self.kinematics = DifferentialKinematics(
            wheel_radius=WHEEL_RADIUS,
            track_width=TRACK_WIDTH
        )

        # 左右电机
        self.motor_left = SingleMotor(
            "左电机",
            PIN_MOTOR_LEFT_PWM, PIN_MOTOR_LEFT_IN1, PIN_MOTOR_LEFT_IN2,
            self.gpio, WHEEL_RADIUS
        )
        self.motor_right = SingleMotor(
            "右电机",
            PIN_MOTOR_RIGHT_PWM, PIN_MOTOR_RIGHT_IN1, PIN_MOTOR_RIGHT_IN2,
            self.gpio, WHEEL_RADIUS
        )

        # 超声波传感器
        self.ultrasonic = UltrasonicSensor(
            PIN_ULTRASONIC_TRIG, PIN_ULTRASONIC_ECHO,
            self.gpio, debug=debug
        )

        # PID 速度环（左右各一个）
        self.pid_left = PIDController(
            kp=PID_KP, ki=PID_KI, kd=PID_KD,
            output_min=-1.0, output_max=1.0
        )
        self.pid_right = PIDController(
            kp=PID_KP, ki=PID_KI, kd=PID_KD,
            output_min=-1.0, output_max=1.0
        )

        # 状态
        self.state = ChassisState()
        self._emergency = False
        self._on_obstacle: Optional[Callable[[float], None]] = None

    # ---- 主接口 ----

    def set_velocity(self, v: float, w: float):
        """
        设置机器人整体速度。

        Args:
            v: 线速度 (m/s)，前进为正，范围 [-MAX_LINEAR_SPEED, MAX_LINEAR_SPEED]
            w: 角速度 (rad/s)，逆时针为正，范围 [-MAX_ANGULAR_SPEED, MAX_ANGULAR_SPEED]
        """
        if self._emergency:
            return

        # 限幅
        v = max(-MAX_LINEAR_SPEED, min(MAX_LINEAR_SPEED, v))
        w = max(-MAX_ANGULAR_SPEED, min(MAX_ANGULAR_SPEED, w))

        self.state.v_target = v
        self.state.w_target = w

        # 逆运动学 → 轮速
        wheel_speeds = self.kinematics.inverse(v, w)

        # 驱动电机
        self.motor_left.set_speed(wheel_speeds.left)
        self.motor_right.set_speed(wheel_speeds.right)

        self.state.left = self.motor_left.status
        self.state.right = self.motor_right.status

    def update(self):
        """
        周期性更新（在 50Hz 控制循环中调用）。
        读取传感器、检查急停条件。
        """
        dist = self.ultrasonic.read_distance()
        self.state.distance_to_obstacle = dist

        if dist < EMERGENCY_STOP_DISTANCE:
            if not self._emergency:
                log.warning(f"检测到障碍物距离 {dist:.2f}m，触发急停！")
                self._emergency = True
                self._hard_brake()
                if self._on_obstacle:
                    self._on_obstacle(dist)

    def emergency_stop(self):
        """紧急停止（超声波触发或手动调用）"""
        log.warning("紧急停止！")
        self._emergency = True
        self._hard_brake()
        self.state.emergency_stop = True

    def clear_emergency(self):
        """清除急停状态，恢复正常控制"""
        self._emergency = False
        self.state.emergency_stop = False
        log.info("急停已解除")

    def stop(self):
        """正常停止，释放所有电机"""
        self.motor_left.stop()
        self.motor_right.stop()
        self.gpio.cleanup()
        log.info("电机控制器已停止")

    def on_obstacle(self, callback: Callable[[float], None]):
        """注册障碍物回调：callback(distance_m)"""
        self._on_obstacle = callback

    # ---- 内部 ----

    def _hard_brake(self):
        """所有电机急刹"""
        self.motor_left._brake()
        self.motor_right._brake()
        self.state.v_target = 0
        self.state.w_target = 0

    def _estimate_actual_speed(self, motor: SingleMotor) -> float:
        """
        从 PWM 占空比估算实际轮速（无编码器时的开环估算）。

        有编码器时应替换为真实测量。
        """
        max_linear = (MOTOR_RATED_RPM / 60.0) * (2 * math.pi * motor.wheel_radius)
        duty_fraction = motor.status.pwm_duty / 100.0
        speed = duty_fraction * max_linear
        if motor.status.direction < 0:
            speed = -speed
        return speed

    @property
    def is_emergency(self) -> bool:
        return self._emergency

    def get_state(self) -> ChassisState:
        """获取底盘当前状态快照"""
        return ChassisState(
            v_target=self.state.v_target,
            w_target=self.state.w_target,
            left=MotorStatus(
                target_speed=self.motor_left.status.target_speed,
                actual_speed=self._estimate_actual_speed(self.motor_left),
                pwm_duty=self.motor_left.status.pwm_duty,
                direction=self.motor_left.status.direction,
            ),
            right=MotorStatus(
                target_speed=self.motor_right.status.target_speed,
                actual_speed=self._estimate_actual_speed(self.motor_right),
                pwm_duty=self.motor_right.status.pwm_duty,
                direction=self.motor_right.status.direction,
            ),
            emergency_stop=self._emergency,
            distance_to_obstacle=self.state.distance_to_obstacle,
        )


# ============================================================
# 导航执行器 — 连接 MotionPlanner 和 MotorController
# ============================================================

class NavigationExecutor:
    """
    将 MotionPlanner 的 (v, w) 指令发送到 MotorController，
    同时整合里程计更新和障碍物检测。

    控制循环（50Hz）:
        executor = NavigationExecutor(motor_ctrl, odometry)
        while executor.running:
            executor.step(target_x, target_y)
            time.sleep(0.02)
    """

    def __init__(self, motor: MotorController,
                 odometry,  # OdometryTracker
                 event_bus=None):  # 可选 EventBus
        self.motor = motor
        self.odometry = odometry
        self.bus = event_bus
        self.running = False
        self._target: Optional[Tuple[float, float]] = None

    def set_target(self, x: float, y: float):
        """设置导航目标点"""
        self._target = (x, y)

    def cancel(self):
        """取消当前导航任务"""
        self._target = None
        self.motor.set_velocity(0, 0)

    def step(self) -> bool:
        """
        执行一帧导航控制。

        Returns:
            True 表示仍在导航中，False 表示已到达或已取消
        """
        from kinematics import MotionPlanner

        self.motor.update()

        if self.motor.is_emergency:
            return False

        if self._target is None:
            self.motor.set_velocity(0, 0)
            return False

        tx, ty = self._target
        pose = self.odometry.get_pose()

        # 计算距离
        dist = math.sqrt((tx - pose.x) ** 2 + (ty - pose.y) ** 2)
        if dist < 0.05:
            log.info(f"到达目标 ({tx:.2f}, {ty:.2f})")
            self.motor.set_velocity(0, 0)
            self._target = None
            if self.bus:
                from controller import EventType
                self.bus.publish_simple(EventType.POSITION_REACHED)
            return False

        # MotionPlanner 生成速度指令
        v, w = MotionPlanner.go_to_position(pose, tx, ty)
        self.motor.set_velocity(v, w)

        # 更新里程计（用估算轮速）
        left_speed = self.motor._estimate_actual_speed(self.motor.motor_left)
        right_speed = self.motor._estimate_actual_speed(self.motor.motor_right)
        from config import ODOMETRY_INTERVAL
        self.odometry.update(left_speed, right_speed, ODOMETRY_INTERVAL)

        return True

    def run_to_target(self, x: float, y: float,
                      on_progress: Callable = None) -> bool:
        """
        阻塞式导航到目标点。

        Args:
            x, y: 目标世界坐标 (m)
            on_progress: 可选进度回调，每帧调用

        Returns:
            True=成功到达, False=被中断（障碍/急停）
        """
        self.set_target(x, y)
        self.running = True

        while self.running:
            if not self.step():
                break
            if on_progress:
                on_progress(self.odometry.get_pose(), self.motor.get_state())
            time.sleep(ODOMETRY_INTERVAL)

        self.running = False
        return self._target is None  # True=已到达


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                        datefmt="%H:%M:%S")

    print("=" * 60)
    print("电机控制模块自测（模拟模式）")
    print("=" * 60)

    # 1. 基础驱动测试
    print("\n[1] 单电机基础测试")
    gpio = GPIOWrapper(debug=True)
    motor = SingleMotor("测试电机", 12, 5, 6, gpio)
    motor.set_speed(0.1)
    print(f"    目标速度=0.1 m/s → PWM={motor.status.pwm_duty:.1f}%, "
          f"方向={'正转' if motor.status.direction==1 else '反转'}")
    motor.set_speed(-0.1)
    print(f"    目标速度=-0.1 m/s → PWM={motor.status.pwm_duty:.1f}%, "
          f"方向={'正转' if motor.status.direction==1 else '反转'}")
    motor._brake()
    print(f"    刹车 → PWM={motor.status.pwm_duty:.1f}%, 方向=停止")

    # 2. 底盘控制器测试
    print("\n[2] 底盘控制器测试")
    mc = MotorController(debug=True)

    print("  直行 0.2 m/s ...")
    mc.set_velocity(0.2, 0.0)
    s = mc.get_state()
    print(f"    左轮: {s.left.pwm_duty:.1f}% {s.left.direction:+d}")
    print(f"    右轮: {s.right.pwm_duty:.1f}% {s.right.direction:+d}")

    print("  原地左转 (CCW) ...")
    mc.set_velocity(0.0, 1.0)
    s = mc.get_state()
    print(f"    左轮: {s.left.pwm_duty:.1f}% {s.left.direction:+d}")
    print(f"    右轮: {s.right.pwm_duty:.1f}% {s.right.direction:+d}")
    print(f"    预期: 左轮反转(-1), 右轮正转(+1) = 逆时针")

    print("  原地右转 (CW) ...")
    mc.set_velocity(0.0, -1.0)
    s = mc.get_state()
    print(f"    左轮: {s.left.pwm_duty:.1f}% {s.left.direction:+d}")
    print(f"    右轮: {s.right.pwm_duty:.1f}% {s.right.direction:+d}")
    print(f"    预期: 左轮正转(+1), 右轮反转(-1) = 顺时针")

    # 3. 超声波传感器测试（模拟）
    print("\n[3] 超声波传感器测试")
    mc.ultrasonic.set_sim_distance(0.15)
    mc.update()
    print(f"    障碍物 0.15m → 急停={'触发' if mc.is_emergency else '未触发'}")

    mc.clear_emergency()
    mc.ultrasonic.set_sim_distance(1.0)
    mc.update()
    print(f"    障碍物 1.0m  → 急停={'触发' if mc.is_emergency else '未触发'}")

    mc.ultrasonic.set_sim_distance(None)
    print(f"    无障碍物     → 距离={mc.ultrasonic.read_distance():.1f}m")

    # 4. 导航执行器测试
    print("\n[4] 导航执行器测试")
    from kinematics import OdometryTracker
    odo = OdometryTracker(mc.kinematics)
    nav = NavigationExecutor(mc, odo)
    nav.set_target(0.5, 0.0)
    print(f"    从 (0,0,0°) 导航到 (0.5, 0.0)")

    pose_start = odo.get_pose()
    steps = 0
    while nav.step() and steps < 200:
        steps += 1
        if steps % 20 == 0:
            pose = odo.get_pose()
            print(f"    步骤{steps:3d}: 位姿=({pose.x:.3f}, {pose.y:.3f}, "
                  f"{pose.heading_deg():.1f}°)")

    pose_end = odo.get_pose()
    print(f"    完成: {steps}步, 最终=({pose_end.x:.3f}, {pose_end.y:.3f})")
    print(f"    期望到达 x≈0.5m, y≈0.0m")

    mc.stop()

    print("\n" + "=" * 60)
    print("电机控制模块自测完成！")
    print("=" * 60)
