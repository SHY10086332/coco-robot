"""
Coco — 实体店智能导购机器人
熊出没风格的原型机器人，履带底盘 + 8寸圆屏 + 语音交互 + RAG商品检索
"""

from .config import *
from .kinematics import (
    DifferentialKinematics,
    OdometryTracker,
    PIDController,
    MotionPlanner,
    WheelSpeed,
    RobotVelocity,
    Odometry,
)
from .controller import (
    EventBus,
    StateMachine,
    CocoController,
    EventType,
    Event,
    RobotState,
)
