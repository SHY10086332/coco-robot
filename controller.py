"""
Coco 导购机器人 — 事件总线 & 状态机

架构：
    EventBus   — 线程安全的发布/订阅，替代 queue.Queue 的星型通信
    StateMachine — 管理机器人行为状态及合法转移

状态流转图：
    IDLE ──唤醒词──→ LISTENING ──意图识别──→ PRICING ──结果展示──→ IDLE
     │                                       │
     │                                       ├──→ DIALOG ──对话结束──→ IDLE
     │                                       │
     └──────────────── ALL ← 异常/超时 ──────┘

    PAYMENT: 独立状态，由扫码/店长指令触发，完成后回 IDLE
"""

import threading
import queue
import time
import logging
from enum import Enum, auto
from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("coco.controller")


# ============================================================
# 事件定义
# ============================================================

class EventType(Enum):
    """事件类型枚举"""
    # 音频
    WAKE_WORD_DETECTED = auto()     # 唤醒词"你好Coco" 检测到
    SPEECH_RECOGNIZED = auto()      # Whisper 识别结果就绪
    TTS_FINISHED = auto()           # 语音播报完成

    # 视觉
    PERSON_APPEARED = auto()        # 有人进入视野
    PERSON_LEFT = auto()            # 人离开
    QR_CODE_SCANNED = auto()        # 扫描到支付二维码

    # 意图 & LLM
    INTENT_PARSED = auto()          # 意图解析完成
    LLM_REPLY_READY = auto()        # LLM 回复就绪
    RAG_RESULT_READY = auto()       # RAG 检索完成

    # UI
    UI_BUTTON_CLICKED = auto()      # 屏幕按钮点击
    UI_ANIMATION_DONE = auto()      # 动画播放完毕

    # 运动
    MOTOR_FAULT = auto()            # 电机故障
    OBSTACLE_DETECTED = auto()      # 检测到障碍物
    POSITION_REACHED = auto()       # 到达目标位置

    # 系统
    SYSTEM_SHUTDOWN = auto()        # 关闭系统
    SYSTEM_ERROR = auto()           # 系统错误
    LOW_BATTERY = auto()            # 电量低
    TIMEOUT = auto()                # 超时（如对话无人回应）


@dataclass
class Event:
    """事件数据包"""
    type: EventType
    data: Any = None
    timestamp: float = field(default_factory=time.time)

    def __repr__(self):
        return f"Event({self.type.name}, data={self.data!r})"


# ============================================================
# 事件总线 — 线程安全的发布/订阅
# ============================================================

class EventBus:
    """
    订阅发布模式，所有模块间通信都通过这个总线。

    比直接 queue 的好处：
    - 松耦合：发布者不知道谁是订阅者
    - 多对多：一个事件可以被多个模块同时订阅
    - 可观测：方便加日志/回放/canary

    内部用 threading + queue 实现线程安全。
    """

    def __init__(self):
        # 每个事件类型 → 订阅者列表（每个订阅者有自己的队列）
        self._subscribers: Dict[EventType, List[queue.Queue]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: EventType) -> queue.Queue:
        """
        订阅某类事件，返回一个专属队列。

        用法：
            my_queue = bus.subscribe(EventType.WAKE_WORD_DETECTED)
            event = my_queue.get(timeout=1.0)  # 阻塞等待
        """
        q = queue.Queue(maxsize=256)  # maxsize 防内存泄漏
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(q)
        return q

    def unsubscribe(self, event_type: EventType, q: queue.Queue):
        """取消订阅（模块退出时调用）"""
        with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(q)
                except ValueError:
                    pass

    def publish(self, event: Event):
        """发布事件给所有订阅者"""
        with self._lock:
            subscribers = self._subscribers.get(event.type, [])
        # 在锁外发送，避免死锁
        for q in subscribers:
            try:
                q.put_nowait(event)
            except queue.Full:
                # 订阅者消费太慢，丢弃旧事件
                try:
                    q.get_nowait()       # 丢最旧的
                    q.put_nowait(event)  # 放新的
                except (queue.Empty, queue.Full):
                    pass

    def publish_simple(self, event_type: EventType, data: Any = None):
        """快捷发布"""
        self.publish(Event(event_type, data))


# ============================================================
# 状态机
# ============================================================

class RobotState(Enum):
    """机器人行为状态"""
    IDLE = "idle"                   # 待机：显示笑脸动画
    LISTENING = "listening"         # 聆听：已唤醒，等待用户说话
    THINKING = "thinking"           # 思考：LLM 推理中
    PRICING = "pricing"             # 查价：展示商品信息+价格
    DIALOG = "dialog"               # 对话：闲聊模式
    PAYMENT = "payment"             # 付款：全屏收款码
    MOVING = "moving"               # 移动：巡航/跟随
    ALERT = "alert"                 # 告警：故障/电量低


class StateMachine:
    """
    机器人状态机。

    管理合法状态转移，防止非法转换（比如在 PAYMENT 时直接跳 PRICING）。
    """

    # 合法转移表：当前状态 → 允许进入的状态集合
    TRANSITIONS: Dict[RobotState, set] = {
        RobotState.IDLE:      {RobotState.LISTENING, RobotState.MOVING,
                               RobotState.PAYMENT, RobotState.ALERT},
        RobotState.LISTENING: {RobotState.THINKING, RobotState.IDLE,
                               RobotState.ALERT},
        RobotState.THINKING:  {RobotState.PRICING, RobotState.DIALOG,
                               RobotState.IDLE, RobotState.ALERT},
        RobotState.PRICING:   {RobotState.IDLE, RobotState.PAYMENT,
                               RobotState.DIALOG, RobotState.ALERT},
        RobotState.DIALOG:    {RobotState.IDLE, RobotState.LISTENING,
                               RobotState.PRICING, RobotState.ALERT},
        RobotState.MOVING:    {RobotState.IDLE, RobotState.ALERT},
        RobotState.PAYMENT:   {RobotState.IDLE, RobotState.ALERT},
        RobotState.ALERT:     {RobotState.IDLE},           # 只能手动解除
    }

    def __init__(self, initial: RobotState = RobotState.IDLE):
        self.state = initial
        self._lock = threading.Lock()
        self._on_state_change: List[Callable[[RobotState, RobotState], None]] = []

    def on_change(self, callback: Callable[[RobotState, RobotState], None]):
        """注册状态变更回调：callback(from_state, to_state)"""
        self._on_state_change.append(callback)

    @property
    def current(self) -> RobotState:
        return self.state

    def can_transition(self, target: RobotState) -> bool:
        """检查是否可以切换到目标状态"""
        return target in self.TRANSITIONS.get(self.state, set())

    def allowed_states(self) -> set:
        """当前状态下允许跳转到哪些状态"""
        return self.TRANSITIONS.get(self.state, set()).copy()

    def transition(self, target: RobotState) -> bool:
        """
        尝试切换到目标状态。成功返回 True，非法转移返回 False。
        """
        with self._lock:
            if not self.can_transition(target):
                logger.warning(
                    f"非法状态转移: {self.state.value} → {target.value}"
                )
                return False

            old = self.state
            self.state = target
            logger.info(f"状态: {old.value} → {target.value}")

        # 回调在锁外执行，防止死锁
        for cb in self._on_state_change:
            try:
                cb(old, target)
            except Exception as e:
                logger.error(f"状态回调异常: {e}")

        return True

    def force_transition(self, target: RobotState):
        """强制转移（绕过转移表检查，仅用于紧急停止等场景）"""
        with self._lock:
            old = self.state
            self.state = target
            logger.warning(f"强制状态转移: {old.value} → {target.value}")


# ============================================================
# 主控制器 — 把 EventBus 和 StateMachine 串起来
# ============================================================

class CocoController:
    """
    Coco 主控制器。

    职责：
    - 持有 EventBus 和 StateMachine
    - 根据状态机决定哪些事件触发状态跳转
    - 不负责具体业务逻辑（LLM/音频由对应模块自己处理）
    """

    def __init__(self, event_bus: EventBus, state_machine: StateMachine):
        self.bus = event_bus
        self.sm = state_machine
        self.running = False

        # 订阅核心事件
        self._wake_queue = self.bus.subscribe(EventType.WAKE_WORD_DETECTED)
        self._speech_queue = self.bus.subscribe(EventType.SPEECH_RECOGNIZED)
        self._intent_queue = self.bus.subscribe(EventType.INTENT_PARSED)
        self._llm_queue = self.bus.subscribe(EventType.LLM_REPLY_READY)
        self._timeout_queue = self.bus.subscribe(EventType.TIMEOUT)
        self._error_queue = self.bus.subscribe(EventType.SYSTEM_ERROR)
        self._shutdown_queue = self.bus.subscribe(EventType.SYSTEM_SHUTDOWN)

        # 状态事件映射：在某个状态下收到某个事件 → 做什么
        self._setup_state_handlers()

    def _setup_state_handlers(self):
        """配置在不同状态下收到事件时的行为"""
        self._handlers = {
            # IDLE 状态：只响应唤醒词
            (RobotState.IDLE, EventType.WAKE_WORD_DETECTED): self._on_wake,
            # LISTENING 状态：收到语音识别结果 → 解析意图
            (RobotState.LISTENING, EventType.SPEECH_RECOGNIZED): self._on_speech,
            # THINKING 状态：LLM回复好了 → 展示结果
            (RobotState.THINKING, EventType.LLM_REPLY_READY): self._on_llm_reply,
            # 任何状态都可响应超时和错误
            (None, EventType.TIMEOUT): self._on_timeout,
            (None, EventType.SYSTEM_ERROR): self._on_error,
            (None, EventType.SYSTEM_SHUTDOWN): self._on_shutdown,
        }

    def start(self):
        """启动主循环"""
        self.running = True
        logger.info("Coco 控制器启动")

    def stop(self):
        """停止控制器"""
        self.running = False
        logger.info("Coco 控制器停止")

    def process_events(self, timeout: float = 0.1):
        """
        排空所有待处理事件（非阻塞）。

        在 UI 事件循环中周期性调用：
            while running:
                controller.process_events()
                app.processEvents()
        """
        queues = [
            (self._wake_queue, EventType.WAKE_WORD_DETECTED),
            (self._speech_queue, EventType.SPEECH_RECOGNIZED),
            (self._intent_queue, EventType.INTENT_PARSED),
            (self._llm_queue, EventType.LLM_REPLY_READY),
            (self._timeout_queue, EventType.TIMEOUT),
            (self._error_queue, EventType.SYSTEM_ERROR),
            (self._shutdown_queue, EventType.SYSTEM_SHUTDOWN),
        ]

        # 持续排空直到所有队列都为空
        while True:
            handled = False
            for q, evt_type in queues:
                try:
                    event = q.get_nowait()
                except queue.Empty:
                    continue
                handled = True

                # 先查精确匹配（当前状态 + 此事件类型）
                key = (self.sm.current, evt_type)
                handler = self._handlers.get(key)
                if handler is None:
                    # 再查通配匹配（任何状态 + 此事件类型）
                    key = (None, evt_type)
                    handler = self._handlers.get(key)

                if handler:
                    handler(event)
            if not handled:
                break

    # ---- 状态处理函数 ----

    def _on_wake(self, event: Event):
        """唤醒词检测 → 进入聆听状态"""
        self.sm.transition(RobotState.LISTENING)
        logger.info("Coco 被唤醒！")

    def _on_speech(self, event: Event):
        """语音识别完成 → 进入思考状态，解析意图"""
        self.sm.transition(RobotState.THINKING)
        text = event.data.get("text", "") if isinstance(event.data, dict) else str(event.data)
        logger.info(f"用户说: {text}")
        # 发布意图解析请求（nlp/intent.py 会处理）
        self.bus.publish_simple(EventType.INTENT_PARSED, data={"text": text})

    def _on_llm_reply(self, event: Event):
        """LLM回复就绪 → 根据意图进入对应状态"""
        intent = event.data.get("intent", "dialog") if isinstance(event.data, dict) else "dialog"

        intent_to_state = {
            "check_price": RobotState.PRICING,
            "ask_question": RobotState.DIALOG,
            "dialog": RobotState.DIALOG,
            "pay": RobotState.PAYMENT,
        }
        target = intent_to_state.get(intent, RobotState.DIALOG)
        self.sm.transition(target)

    def _on_timeout(self, event: Event):
        """超时 → 回到 IDLE"""
        logger.info("超时，回到待机状态")
        self.sm.transition(RobotState.IDLE)

    def _on_error(self, event: Event):
        """系统错误 → 告警状态"""
        logger.error(f"系统错误: {event.data}")
        self.sm.transition(RobotState.ALERT)

    def _on_shutdown(self, event: Event):
        """关闭系统"""
        logger.info("收到关闭指令")
        self.stop()


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")

    print("=" * 50)
    print("控制器模块自测")
    print("=" * 50)

    # 测试 EventBus
    print("\n[EventBus 发布/订阅]")
    bus = EventBus()

    q1 = bus.subscribe(EventType.WAKE_WORD_DETECTED)
    q2 = bus.subscribe(EventType.WAKE_WORD_DETECTED)  # 两人都订阅

    bus.publish(Event(EventType.WAKE_WORD_DETECTED, data={"score": 0.95}))

    e1 = q1.get(timeout=1.0)
    e2 = q2.get(timeout=1.0)
    print(f"  订阅者1收到: {e1}")
    print(f"  订阅者2收到: {e2}")

    # 测试 StateMachine
    print("\n[StateMachine 状态转移]")
    sm = StateMachine(RobotState.IDLE)
    assert sm.current == RobotState.IDLE

    # 正常转移
    assert sm.transition(RobotState.LISTENING) == True
    print(f"  IDLE → LISTENING: OK")
    assert sm.transition(RobotState.THINKING) == True
    print(f"  LISTENING → THINKING: OK")
    assert sm.transition(RobotState.PRICING) == True
    print(f"  THINKING → PRICING: OK")
    assert sm.transition(RobotState.IDLE) == True
    print(f"  PRICING → IDLE: OK")

    # 非法转移：IDLE 不能直接到 DIALOG（必须先经过 LISTENING→THINKING）
    assert sm.transition(RobotState.DIALOG) == False
    print(f"  IDLE → DIALOG(非法): 正确拦截")

    # 强制转移
    sm.force_transition(RobotState.ALERT)
    assert sm.current == RobotState.ALERT
    print(f"  IDLE → ALERT(强制): OK")

    # 测试 Controller 集成
    print("\n[CocoController 集成]")
    bus2 = EventBus()
    sm2 = StateMachine(RobotState.IDLE)
    ctrl = CocoController(bus2, sm2)
    ctrl.start()

    # 模拟唤醒
    bus2.publish(Event(EventType.WAKE_WORD_DETECTED, data={"score": 0.9}))
    ctrl.process_events()
    print(f"  唤醒后状态: {sm2.current.value}")

    # 模拟用户说话
    bus2.publish(Event(EventType.SPEECH_RECOGNIZED, data={"text": "这个多少钱"}))
    ctrl.process_events()
    print(f"  语音识别后状态: {sm2.current.value}")

    # 模拟 LLM 回复（查价意图）
    bus2.publish(Event(EventType.LLM_REPLY_READY,
                       data={"intent": "check_price", "reply": "这件商品39.9元"}))
    ctrl.process_events()
    print(f"  LLM回复后状态: {sm2.current.value}")

    # 模拟超时
    bus2.publish(Event(EventType.TIMEOUT))
    ctrl.process_events()
    print(f"  超时后状态: {sm2.current.value}")

    print("\n" + "=" * 50)
    print("自测完成！")
    print("=" * 50)
