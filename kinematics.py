"""
Coco 导购机器人 — 差速驱动运动学 & 里程计

履带式差速底盘的运动模型。两个履带独立驱动：
- 同速同向 = 直线前进/后退
- 差速 = 转弯（弧线）
- 反向 = 原地掉头（零转弯半径）

坐标系约定（右手系）：
    +x → 前方（机器人朝向）
    +y → 左方
    +θ → 逆时针旋转为正

所有单位采用 SI：米(m)、弧度(rad)、秒(s)
"""

import math
import time
from dataclasses import dataclass, field
from typing import Tuple


# ============================================================
# 数据类型
# ============================================================

@dataclass
class WheelSpeed:
    """单轮速度 (m/s)"""
    left: float = 0.0
    right: float = 0.0

    def __repr__(self):
        return f"WheelSpeed(L={self.left:.3f}, R={self.right:.3f}) m/s"


@dataclass
class RobotVelocity:
    """机器人整体速度 — 世界坐标系下"""
    v: float = 0.0       # 线速度 (m/s)，前进为正
    w: float = 0.0       # 角速度 (rad/s)，逆时针为正

    def __repr__(self):
        return f"RobotVelocity(v={self.v:.3f} m/s, w={self.w:.4f} rad/s)"


@dataclass
class Odometry:
    """里程计位姿 — 世界坐标系下的位置 + 朝向"""
    x: float = 0.0       # 世界坐标 X (m)
    y: float = 0.0       # 世界坐标 Y (m)
    theta: float = 0.0   # 朝向角 (rad)，0 = 朝 +x 方向

    def heading_deg(self) -> float:
        """返回朝向角的度数 (0~360)"""
        deg = math.degrees(self.theta) % 360
        return deg

    def __repr__(self):
        return (f"Odometry(x={self.x:.4f}, y={self.y:.4f}, "
                f"θ={self.theta:.4f} rad = {self.heading_deg():.1f}°)")


# ============================================================
# 运动学核心
# ============================================================

class DifferentialKinematics:
    """
    差速驱动机器人运动学。

    关键公式（教材级推导）：

    假设左右轮的速度分别为 v_L 和 v_R，轮距为 L：

        线速度（机器人中心点的前进速度）：
            v = (v_L + v_R) / 2          ... (1)

        角速度（绕中心的旋转速度）：
            ω = (v_R - v_L) / L          ... (2)

    公式(1)直观理解：左右轮平均速度 = 整体前进速度。
    公式(2)直观理解：右轮比左轮快 → 逆时针转（ω>0）；
                   右轮比左轮慢 → 顺时针转（ω<0）；
                   两轮相同     → 直线走（ω=0）。

    逆解（知道想要的 v 和 ω，反算轮速）：
        v_L = v - ω*L/2                ... (3)
        v_R = v + ω*L/2                ... (4)
    """

    def __init__(self, wheel_radius: float = 0.032, track_width: float = 0.20):
        """
        Args:
            wheel_radius: 驱动轮半径 (m)
            track_width:  左右履带中心距 / 轮距 (m)
        """
        self.r = wheel_radius
        self.L = track_width

    # ---- 正运动学：轮速 → 机器人速度 ----

    def forward(self, v_left: float, v_right: float) -> RobotVelocity:
        """
        正运动学：已知左右轮线速度，求机器人整体速度。

        Example:
            v_L=0.1, v_R=0.1  → v=0.1,  w=0     (直行)
            v_L=0.0, v_R=0.1  → v=0.05, w=0.5   (左转)
            v_L=0.1, v_R=-0.1 → v=0.0,  w=1.0   (原地右转)
        """
        v = (v_left + v_right) / 2.0
        w = (v_right - v_left) / self.L
        return RobotVelocity(v=v, w=w)

    # ---- 逆运动学：期望速度 → 轮速 ----

    def inverse(self, v: float, w: float) -> WheelSpeed:
        """
        逆运动学：已知期望的线速度 v 和角速度 w，计算左右轮需要转多快。

        Args:
            v: 期望线速度 (m/s)，前进为正
            w: 期望角速度 (rad/s)，逆时针为正

        Returns:
            WheelSpeed: 左右轮的线速度 (m/s)
        """
        left = v - w * self.L / 2.0
        right = v + w * self.L / 2.0
        return WheelSpeed(left=left, right=right)

    # ---- 单位换算助手 ----

    def wheel_speed_to_rpm(self, linear_speed: float) -> float:
        """轮子线速度 (m/s) → 电机转速 (RPM)"""
        # RPM = (线速度 / 轮子周长) * 60
        return (linear_speed / (2 * math.pi * self.r)) * 60.0

    def rpm_to_wheel_speed(self, rpm: float) -> float:
        """电机转速 (RPM) → 轮子线速度 (m/s)"""
        return (rpm / 60.0) * (2 * math.pi * self.r)


# ============================================================
# 里程计推算
# ============================================================

class OdometryTracker:
    """
    基于差速运动学的里程计。

    每 dt 秒，根据当前速度推算位姿变化：

        Δθ = ω * dt
        Δx = v * cos(θ) * dt         ← 只有在机器人朝向方向上的速度分量
        Δy = v * sin(θ) * dt         ← 会改变世界坐标系下的位置

        x_new  = x + Δx
        y_new  = y + Δy
        θ_new  = θ + Δθ

    然后累加这些增量就得到了里程计。

    ⚠️ 里程计的固有缺陷：
    - 轮子打滑会导致误差累积（履带比轮式好一些但仍存在）
    - 误差随时间发散，每走1米大约漂移1-5cm
    - 这个误差在 ROS 里叫 odometry drift
    - 解决方案：里程计 + IMU + 视觉/激光 SLAM 融合（大二进阶）
    """

    def __init__(self, kinematics: DifferentialKinematics):
        self.kinematics = kinematics
        self.pose = Odometry()                            # 当前位姿
        self.total_distance = 0.0                          # 累计行驶距离 (m)
        self.total_rotation = 0.0                          # 累计旋转角度 (rad)

    def update(self, v_left: float, v_right: float, dt: float):
        """
        根据左右轮速度和时间增量更新位姿。

        Args:
            v_left:  左轮线速度 (m/s)
            v_right: 右轮线速度 (m/s)
            dt:      时间增量 (s)，即采样间隔
        """
        if dt <= 0:
            return

        vel = self.kinematics.forward(v_left, v_right)
        v, w = vel.v, vel.w

        # 小角度近似（dt 很小时可用）
        # 更精确的中点法：
        delta_theta = w * dt
        delta_x = v * math.cos(self.pose.theta + delta_theta / 2) * dt
        delta_y = v * math.sin(self.pose.theta + delta_theta / 2) * dt

        self.pose.x += delta_x
        self.pose.y += delta_y
        self.pose.theta += delta_theta

        # 归一化角度到 [-π, π]
        self.pose.theta = math.atan2(
            math.sin(self.pose.theta),
            math.cos(self.pose.theta)
        )

        # 累计统计
        self.total_distance += abs(v) * dt
        self.total_rotation += abs(w) * dt

    def reset(self, x: float = 0.0, y: float = 0.0, theta: float = 0.0):
        """重置里程计到指定位置"""
        self.pose = Odometry(x=x, y=y, theta=theta)
        self.total_distance = 0.0
        self.total_rotation = 0.0

    def get_pose(self) -> Odometry:
        """返回当前位姿（副本，防止意外修改）"""
        return Odometry(
            x=self.pose.x,
            y=self.pose.y,
            theta=self.pose.theta
        )


# ============================================================
# PID 速度控制器
# ============================================================

class PIDController:
    """
    离散型 PID 控制器 — 用于电机速度闭环。

    PID 三个分量：
        P(比例): 现在误差多大 → 立即反应
        I(积分): 过去的累积误差 → 消除稳态误差
        D(微分): 误差变化趋势 → 抑制震荡/过冲

    输出 = Kp*err + Ki*∫err·dt + Kd*d(err)/dt

    实际使用时加了 anti-windup（积分限幅），防止积分项无限累积。
    """

    def __init__(self, kp: float, ki: float, kd: float,
                 output_min: float = -1.0, output_max: float = 1.0):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max
        self._prev_error = 0.0
        self._integral = 0.0
        self._last_time = None

    def reset(self):
        self._prev_error = 0.0
        self._integral = 0.0
        self._last_time = None

    def update(self, setpoint: float, measurement: float) -> float:
        """
        计算一次 PID 输出。

        Args:
            setpoint:    目标值（比如目标转速 100 RPM）
            measurement: 当前测量值（编码器实测 95 RPM）

        Returns:
            控制输出（比如 PWM 占空比 -1.0 ~ 1.0）
        """
        now = time.time()
        dt = now - self._last_time if self._last_time else 0.02
        self._last_time = now

        # 如果 dt 过大（刚启动）则限制
        if dt > 0.1:
            dt = 0.02

        error = setpoint - measurement

        # P
        p_out = self.kp * error

        # I（带积分限幅 anti-windup）
        self._integral += error * dt
        # 限幅：积分项不能超过输出范围
        i_limit = (self.output_max - p_out) / max(self.ki, 1e-6)
        self._integral = max(-abs(i_limit), min(abs(i_limit), self._integral))
        i_out = self.ki * self._integral

        # D（对测量值微分比误差微分更平滑，避免 setpoint 突变导致的微分冲击）
        d_out = self.kd * (error - self._prev_error) / dt if dt > 0 else 0.0
        self._prev_error = error

        output = p_out + i_out + d_out
        return max(self.output_min, min(self.output_max, output))


# ============================================================
# 轨迹生成器 — 用于路径规划
# ============================================================

class MotionPlanner:
    """
    简单轨迹生成器：给定终点，生成一系列速度指令。
    真正的轨迹优化是大二课题（MPC / 时间最优控制），
    这里先做最基础的"转过去 → 直走到"。
    """

    @staticmethod
    def go_to_position(current: Odometry, target_x: float, target_y: float,
                       linear_speed: float = 0.2) -> Tuple[float, float]:
        """
        计算前往目标点所需的 v 和 w。

        策略：
        1. 先转（原地）对准目标方向
        2. 再直走

        Returns:
            (v, w) 当前这一帧推荐的速度
        """
        dx = target_x - current.x
        dy = target_y - current.y
        distance = math.sqrt(dx * dx + dy * dy)
        target_heading = math.atan2(dy, dx)               # 目标方向角
        heading_error = target_heading - current.theta

        # 归一化到 [-π, π]
        heading_error = math.atan2(
            math.sin(heading_error), math.cos(heading_error)
        )

        # 角度误差大 → 先转；误差小 → 直走
        ANGLE_THRESHOLD = math.radians(10)                # 10度内直走

        if abs(heading_error) > ANGLE_THRESHOLD and distance > 0.05:
            # 原地旋转对准方向
            w = 0.5 if heading_error > 0 else -0.5        # 固定角速度
            return 0.0, w
        elif distance > 0.05:
            # 直走，同时微调方向
            w = 0.3 * heading_error                       # P 控制微调朝向
            v = min(linear_speed, distance * 0.5)          # 靠近时减速
            return v, w
        else:
            return 0.0, 0.0                               # 到达


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("运动学模块自测")
    print("=" * 50)

    # 用 config 中的真实参数
    kin = DifferentialKinematics(wheel_radius=0.032, track_width=0.20)

    # 测试正运动学
    print("\n[正运动学]")
    ws = WheelSpeed(left=0.1, right=0.1)
    vel = kin.forward(ws.left, ws.right)
    print(f"  输入: {ws}")
    print(f"  输出: {vel}")
    print(f"  → 两轮同速，预期 v=0.100, w=0.000")

    ws2 = WheelSpeed(left=0.0, right=0.1)
    vel2 = kin.forward(ws2.left, ws2.right)
    print(f"\n  输入: {ws2}")
    print(f"  输出: {vel2}")
    print(f"  → 左停右走, 预期 v=0.050, w=0.500")

    # 测试逆运动学
    print("\n[逆运动学]")
    # 期望 0.2 m/s 直行
    ws3 = kin.inverse(v=0.2, w=0.0)
    print(f"  输入: v=0.2, w=0.0 → 输出: {ws3}")
    print(f"  → 预期 L=R=0.2 m/s")

    # 期望原地转圈
    ws4 = kin.inverse(v=0.0, w=1.0)
    print(f"  输入: v=0.0, w=1.0 → 输出: {ws4}")
    print(f"  → 预期 L=-0.1, R=0.1 (左逆右顺=CCW左转)")

    # 测试里程计
    print("\n[里程计]")
    odo = OdometryTracker(kin)
    print(f"  初始: {odo.get_pose()}")

    # 模拟 2 秒直线行驶
    for _ in range(100):
        odo.update(v_left=0.1, v_right=0.1, dt=0.02)
    print(f"  直行2秒后: {odo.get_pose()}")
    print(f"  预期: x≈0.2m, y≈0.0m, θ≈0°")

    # 模拟 1 秒原地旋转
    odo.reset()
    for _ in range(50):
        odo.update(v_left=-0.1, v_right=0.1, dt=0.02)
    print(f"  原地旋转1秒后: {odo.get_pose()}")
    print(f"  预期: x≈0.0m, y≈0.0m, θ≈1.0 rad (w=1.0 * 1s)")

    # 测试 PID
    print("\n[PID 控制器]")
    pid = PIDController(kp=1.0, ki=0.1, kd=0.02, output_min=-1.0, output_max=1.0)
    outputs = []
    measurement = 0.0
    setpoint = 100.0       # 目标 100 RPM
    for _ in range(100):
        out = pid.update(setpoint, measurement)
        measurement += out * 5.0           # 模拟电机响应
        outputs.append(out)
    print(f"  稳态输出: {outputs[-1]:.4f} (预期趋近 0——达到目标后停止输出)")
    print(f"  稳态转速: {measurement:.1f} RPM (预期 ≈100)")

    # 测试轨迹生成
    print("\n[轨迹生成]")
    current = Odometry(x=0.0, y=0.0, theta=0.0)
    v, w = MotionPlanner.go_to_position(current, target_x=1.0, target_y=0.5)
    print(f"  从 (0,0,0°) 到 (1.0,0.5)")
    print(f"  推荐速度: v={v:.3f}, w={w:.3f}")

    print("\n" + "=" * 50)
    print("自测完成！")
    print("=" * 50)
