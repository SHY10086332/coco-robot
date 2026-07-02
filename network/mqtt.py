"""
Coco 导购机器人 — MQTT 网络通信

通过 MQTT 协议将机器人状态、异常告警、统计数据上报到店长手机。
DEBUG 模式下仅打印日志，不连接真实 Broker。

Topics:
    coco/state     — 机器人状态（周期性上报）
    coco/alert     — 异常告警（即时推送）
    coco/stats     — 统计数据（每 5 分钟上报）
    coco/cmd       — 远程指令（订阅，可选）

依赖: pip install paho-mqtt
"""

import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Callable, Dict, Any

log = logging.getLogger("coco.mqtt")

try:
    import paho.mqtt.client as mqtt
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False
    log.warning("paho-mqtt 未安装，MQTT 功能不可用")

from config import (
    DEBUG, MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE,
    MQTT_TOPIC_STATE, MQTT_TOPIC_ALERT, MQTT_TOPIC_STATS,
)


# ============================================================
# 上报数据结构
# ============================================================

@dataclass
class StateReport:
    """状态上报数据"""
    state: str = "idle"
    battery: float = 100.0           # 电量 %
    x: float = 0.0
    y: float = 0.0
    heading: float = 0.0             # 朝向角 (deg)
    obstacle_distance: float = 999.0 # 最近障碍物距离 (m)
    emergency_stop: bool = False
    uptime_seconds: float = 0.0      # 运行时长

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


@dataclass
class AlertReport:
    """告警上报数据"""
    level: str = "warning"           # info / warning / critical
    alert_type: str = ""             # obstacle / motor_fault / low_battery / system
    message: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


@dataclass
class StatsReport:
    """统计数据上报"""
    uptime_minutes: float = 0.0
    total_distance: float = 0.0      # 累计行驶距离 (m)
    total_rotations: float = 0.0     # 累计旋转 (rad)
    queries_served: int = 0          # 导购查询次数
    payments_completed: int = 0       # 支付完成次数
    obstacle_stops: int = 0          # 急停次数
    motor_faults: int = 0            # 电机故障次数
    avg_llm_time: float = 0.0        # 平均 LLM 推理时间 (s)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


# ============================================================
# MQTT 客户端
# ============================================================

class CocoMQTT:
    """
    Coco MQTT 客户端。

    DEBUG 模式：只 log，不连接真实 broker。
    生产模式：连接 broker，自动重连，QoS=1。

    用法:
        mqtt_client = CocoMQTT()
        mqtt_client.connect()
        mqtt_client.publish_state(state_report)
        mqtt_client.publish_alert(alert_report)
        mqtt_client.start_stats_timer(odometry_tracker)
        mqtt_client.disconnect()
    """

    def __init__(self, broker: str = MQTT_BROKER,
                 port: int = MQTT_PORT,
                 keepalive: int = MQTT_KEEPALIVE,
                 debug: bool = DEBUG):
        self.broker = broker
        self.port = port
        self.keepalive = keepalive
        self.debug = debug
        self._client = None
        self._connected = False
        self._lock = threading.Lock()

        # 统计计数
        self.queries_served = 0
        self.payments_completed = 0
        self.obstacle_stops = 0
        self.motor_faults = 0
        self._start_time = time.time()

        # 后台定时器
        self._stats_timer: Optional[threading.Thread] = None
        self._stats_running = False
        self._odometry = None  # 外部注入

        if self.debug:
            log.info(f"MQTT 模拟模式启用（broker={broker}:{port})")
        elif not PAHO_AVAILABLE:
            log.warning("paho-mqtt 不可用，回退到模拟模式")
            self.debug = True

    # ---- 连接管理 ----

    def connect(self) -> bool:
        """连接 MQTT Broker"""
        if self.debug:
            log.info(f"[SIM] 连接到 MQTT Broker: {self.broker}:{self.port}")
            self._connected = True
            return True

        if not PAHO_AVAILABLE:
            return False

        try:
            self._client = mqtt.Client(client_id="coco_robot", clean_session=True)
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect

            # 登录（按需配置）
            # self._client.username_pw_set("user", "pass")

            self._client.connect_async(self.broker, self.port, self.keepalive)
            self._client.loop_start()
            log.info(f"MQTT 连接中... {self.broker}:{self.port}")
            return True
        except Exception as e:
            log.error(f"MQTT 连接失败: {e}")
            self._connected = False
            return False

    def disconnect(self):
        """断开连接"""
        self._stats_running = False
        if self._stats_timer:
            self._stats_timer.join(timeout=2.0)

        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None

        self._connected = False
        log.info("MQTT 已断开")

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            log.info(f"MQTT 已连接: {self.broker}:{self.port}")
            # 订阅远程指令
            client.subscribe("coco/cmd", qos=1)
        else:
            rc_map = {1: "协议版本错误", 2: "ClientID 被拒", 3: "服务器不可用",
                      4: "用户名/密码错误", 5: "未授权"}
            log.error(f"MQTT 连接失败: {rc_map.get(rc, rc)}")

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        if rc != 0:
            log.warning("MQTT 意外断连，将自动重连...")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ---- 发布接口 ----

    def publish_state(self, state: StateReport):
        """上报机器人状态"""
        self._publish(MQTT_TOPIC_STATE, state.to_json(), qos=1)

    def publish_alert(self, alert: AlertReport):
        """推送告警（店长手机可订阅此 topic 收到通知）"""
        self._publish(MQTT_TOPIC_ALERT, alert.to_json(), qos=1)
        log.warning(f"告警推送: [{alert.level}] {alert.alert_type}: {alert.message}")

    def publish_stats(self, stats: StatsReport):
        """上报统计数据"""
        self._publish(MQTT_TOPIC_STATS, stats.to_json(), qos=0)

    # ---- 快捷方法 ----

    def alert_obstacle(self, distance_m: float):
        """障碍物急停告警"""
        self.obstacle_stops += 1
        self.publish_alert(AlertReport(
            level="warning",
            alert_type="obstacle",
            message=f"检测到障碍物距离 {distance_m:.2f}m，已急停",
        ))

    def alert_motor_fault(self, motor_name: str, detail: str = ""):
        """电机故障告警"""
        self.motor_faults += 1
        self.publish_alert(AlertReport(
            level="critical",
            alert_type="motor_fault",
            message=f"{motor_name} 故障: {detail}",
        ))

    def alert_low_battery(self, voltage: float):
        """低电量告警"""
        self.publish_alert(AlertReport(
            level="warning",
            alert_type="low_battery",
            message=f"电量低: {voltage:.1f}V，请及时充电",
        ))

    def alert_system(self, message: str):
        """系统级告警"""
        self.publish_alert(AlertReport(
            level="critical",
            alert_type="system",
            message=message,
        ))

    # ---- 定时统计上报 ----

    def bind_odometry(self, odometry_tracker):
        """绑定里程计，供统计上报使用"""
        self._odometry = odometry_tracker

    def start_stats_timer(self, interval_minutes: float = 5.0):
        """
        启动后台统计上报定时器。

        Args:
            interval_minutes: 上报间隔（分钟），默认 5 分钟
        """
        if self._stats_running:
            return

        self._stats_running = True
        self._stats_timer = threading.Thread(
            target=self._stats_loop,
            args=(interval_minutes,),
            daemon=True,
            name="mqtt-stats",
        )
        self._stats_timer.start()
        log.info(f"统计上报定时器已启动（每 {interval_minutes} 分钟）")

    def _stats_loop(self, interval_minutes: float):
        """后台定时上报统计"""
        while self._stats_running:
            time.sleep(interval_minutes * 60)

            if not self._stats_running:
                break

            uptime_s = time.time() - self._start_time
            stats = StatsReport(
                uptime_minutes=round(uptime_s / 60, 1),
                total_distance=round(self._odometry.total_distance, 3) if self._odometry else 0,
                total_rotations=round(self._odometry.total_rotation, 2) if self._odometry else 0,
                queries_served=self.queries_served,
                payments_completed=self.payments_completed,
                obstacle_stops=self.obstacle_stops,
                motor_faults=self.motor_faults,
            )
            self.publish_stats(stats)
            log.debug(f"统计已上报: {stats.to_json()}")

    # ---- 内部 ----

    def _publish(self, topic: str, payload: str, qos: int = 1):
        """发布消息"""
        if self.debug:
            # 截断过长 payload 便于查看
            display = payload if len(payload) < 120 else payload[:110] + "..."
            log.debug(f"[SIM] PUB {topic}: {display}")
            return

        if self._client and self._connected:
            try:
                result = self._client.publish(topic, payload, qos=qos)
                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    log.warning(f"MQTT 发布失败: {topic}, rc={result.rc}")
            except Exception as e:
                log.error(f"MQTT 发布异常: {e}")
        else:
            log.debug(f"MQTT 未连接，跳过发布: {topic}")


# ============================================================
# 辅助：构造 StateReport
# ============================================================

def build_state_report(
    state_name: str,
    odometry=None,
    battery: float = 100.0,
    obstacle_distance: float = 999.0,
    emergency_stop: bool = False,
    start_time: float = 0,
) -> StateReport:
    """从各模块采集状态数据，构造上报结构"""
    x, y, heading = 0.0, 0.0, 0.0
    if odometry:
        pose = odometry.get_pose()
        x, y = pose.x, pose.y
        heading = pose.heading_deg()

    uptime = time.time() - start_time if start_time > 0 else 0

    return StateReport(
        state=state_name,
        battery=battery,
        x=round(x, 3),
        y=round(y, 3),
        heading=round(heading, 1),
        obstacle_distance=round(obstacle_distance, 2),
        emergency_stop=emergency_stop,
        uptime_seconds=round(uptime, 1),
    )


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                        datefmt="%H:%M:%S")

    print("=" * 60)
    print("MQTT 模块自测（模拟模式）")
    print("=" * 60)

    # 1. 连接
    print("\n[1] 连接测试")
    client = CocoMQTT(debug=True)
    ok = client.connect()
    print(f"  连接结果: {'成功' if ok else '失败'}")
    print(f"  连接状态: {client.is_connected}")

    # 2. 状态上报
    print("\n[2] 状态上报")
    state = StateReport(
        state="moving",
        battery=85.5,
        x=1.23, y=0.45, heading=30.0,
        obstacle_distance=999.0,
        uptime_seconds=120.0,
    )
    client.publish_state(state)

    # 3. 告警上报
    print("\n[3] 告警上报")
    client.alert_obstacle(0.25)
    client.alert_motor_fault("左电机", "堵转")
    client.alert_low_battery(10.8)
    client.alert_system("CPU 温度过高: 82°C")

    # 4. 统计上报
    print("\n[4] 统计上报")
    stats = StatsReport(
        uptime_minutes=10.0,
        total_distance=5.2,
        total_rotations=8.5,
        queries_served=15,
        payments_completed=2,
        obstacle_stops=1,
        motor_faults=0,
    )
    client.publish_stats(stats)

    # 5. 断连
    print("\n[5] 断连测试")
    client.disconnect()
    print(f"  连接状态: {client.is_connected}")

    # 6. 构建辅助
    print("\n[6] build_state_report 测试")
    report = build_state_report("idle", battery=92.0)
    print(f"  {report.to_json()}")

    print("\n" + "=" * 60)
    print("MQTT 模块自测完成！")
    print("=" * 60)
