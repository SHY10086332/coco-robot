#!/usr/bin/env python3
"""
Coco 导购机器人 — 主入口

用法：
    # 开发模式（PC模拟，无硬件）
    python main.py --debug

    # 生产模式（树莓派5，带硬件）
    python main.py

    # 仅测试运动学模块
    python main.py --test-kinematics

    # 指定配置文件
    python main.py --config my_config.py
"""

import sys
import os
import time
import signal
import argparse
import logging
import math

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    DEBUG, LOG_LEVEL,
    WHEEL_RADIUS, TRACK_WIDTH, ODOMETRY_INTERVAL,
    MAX_LINEAR_SPEED, MAX_ANGULAR_SPEED,
)
from kinematics import (
    DifferentialKinematics,
    OdometryTracker,
    MotionPlanner,
    Odometry,
)
from controller import EventBus, StateMachine, CocoController, RobotState


def setup_logging(level: str = "INFO"):
    fmt = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO),
                        format=fmt, datefmt="%H:%M:%S")


def run_debug_mode():
    """
    开发/调试模式：在 PC 上模拟运行，不使用真实硬件。
    模拟里程计更新并在控制台输出状态。
    """
    log = logging.getLogger("coco.debug")
    log.info("开发模式启动（无硬件模拟）")

    # 初始化核心模块
    kin = DifferentialKinematics(wheel_radius=WHEEL_RADIUS, track_width=TRACK_WIDTH)
    odo = OdometryTracker(kin)
    bus = EventBus()
    sm = StateMachine(RobotState.IDLE)
    controller = CocoController(bus, sm)
    controller.start()

    # 模拟运动参数
    # 让机器人走一个 1m x 1m 的正方形（靠里程计）
    waypoints = [
        (1.0, 0.0),    # 向前 1m
        (1.0, 1.0),    # 向左 1m
        (0.0, 1.0),    # 向后 1m
        (0.0, 0.0),    # 回到原点
    ]
    current_waypoint = 0

    log.info("开始正方形轨迹导航...")
    log.info(f"初始位姿: {odo.get_pose()}")

    try:
        t_start = time.time()
        while controller.running:
            loop_start = time.time()

            # 处理控制事件
            controller.process_events()

            # --- 模拟导航：沿正方形走 ---
            if current_waypoint < len(waypoints):
                tx, ty = waypoints[current_waypoint]
                v, w = MotionPlanner.go_to_position(
                    odo.get_pose(), tx, ty,
                    linear_speed=MAX_LINEAR_SPEED
                )

                # 运动学逆解 → 轮速
                wheel_speeds = kin.inverse(v, w)

                # 更新里程计（模拟：假设轮速完美执行）
                odo.update(wheel_speeds.left, wheel_speeds.right, ODOMETRY_INTERVAL)

                # 检查是否到达当前目标点
                pose = odo.get_pose()
                dist = math.sqrt((tx - pose.x)**2 + (ty - pose.y)**2)
                if dist < 0.05:   # 5cm 内算到达
                    log.info(f"到达航点 {current_waypoint+1}: ({tx}, {ty})")
                    current_waypoint += 1

            # 每秒打印一次状态
            elapsed = time.time() - t_start
            if int(elapsed) != int(elapsed - ODOMETRY_INTERVAL):
                pose = odo.get_pose()
                print(f"\r[{elapsed:5.1f}s] 状态={sm.current.value:10s} | "
                      f"位姿=({pose.x:6.3f}, {pose.y:6.3f}, {pose.heading_deg():5.1f}°) | "
                      f"里程={odo.total_distance:6.3f}m",
                      end="", flush=True)

            # 完成后退出
            if current_waypoint >= len(waypoints):
                log.info("正方形轨迹完成！")
                break

            # 帧率控制（50Hz 里程计更新）
            elapsed_loop = time.time() - loop_start
            sleep_time = ODOMETRY_INTERVAL - elapsed_loop
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        log.info("用户中断")
    finally:
        controller.stop()

    # 最终状态
    pose = odo.get_pose()
    drift = math.sqrt(pose.x**2 + pose.y**2)
    print()  # 换行
    log.info(f"最终位姿: {pose}")
    log.info(f"累计行驶: {odo.total_distance:.3f}m, 累计旋转: {math.degrees(odo.total_rotation):.1f}°")
    log.info(f"回到原点误差: {drift*100:.1f}cm (理想情况下应为0，ODOMETRY_INTERVAL精度导致微小误差)")


def run_production_mode():
    """
    生产模式：树莓派5 + 真实硬件。
    初始化所有外设，启动6个线程。
    """
    log = logging.getLogger("coco.production")
    log.info("生产模式启动（真实硬件）")

    # TODO: 大二实现
    # 1. 初始化 GPIO
    # 2. 初始化摄像头
    # 3. 初始化麦克风
    # 4. 启动6个工作线程
    # 5. 启动 PyQt5 UI

    log.warning("生产模式尚未实现，请使用 --debug 模式测试")
    print("\n  生产模式将在硬件就绪后实现。")
    print("  目前可用: python main.py --debug")
    print("           python main.py --test-kinematics\n")


def run_chat():
    """交互式对话模式 — 模拟导购对话"""
    from nlp.dialogue import DialogueManager

    print("正在加载商品库和对话引擎...")
    dm = DialogueManager()
    dm.initialize()

    print(f"\n已加载 {dm.rag.total_products} 件商品，Ollama: {'在线' if dm.llm.available else '离线(fallback)'}")
    print("\n开始对话（输入 q 退出）:\n")

    while True:
        try:
            user_input = input("👤 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if user_input.lower() in ("q", "quit", "exit"):
            print("再见！欢迎下次光临～")
            break
        if not user_input:
            continue

        reply = dm.chat(user_input)

        print(f"🎯 [{reply.intent}]")
        print(f"🤖 {reply.text}")
        if reply.products:
            print(f"📦 {reply.products[0].product.name} "
                  f"¥{reply.products[0].product.price:.2f}")
        print()


def test_kinematics():
    """仅测试运动学模块"""
    from kinematics import WheelSpeed
    import kinematics as km_module

    print("运行运动学模块自测...\n")
    kin = DifferentialKinematics(wheel_radius=0.032, track_width=0.20)
    odo = OdometryTracker(kin)

    for _ in range(100):
        odo.update(0.1, 0.1, 0.02)
    print(f"直行 2s: {odo.get_pose()}")

    for _ in range(50):
        odo.update(0.0, 0.1, 0.02)
    print(f"左转 1s: {odo.get_pose()}")

    print("\n运动学模块运行正常 ✓")


def run_motor_test():
    """电机控制模块自测"""
    import hardware.motor as motor_module

    print("运行电机控制模块自测...\n")

    mc = motor_module.MotorController(debug=True)
    state = mc.get_state()
    print(f"初始状态: v={state.v_target:.2f}, w={state.w_target:.2f}, "
          f"急停={state.emergency_stop}")

    # 测试各种速度指令
    tests = [
        ("直行 0.2 m/s", 0.2, 0.0),
        ("原地左转", 0.0, 1.0),
        ("原地右转", 0.0, -1.0),
        ("弧线前进(左弯)", 0.2, 0.5),
    ]

    for name, v, w in tests:
        mc.set_velocity(v, w)
        s = mc.get_state()
        print(f"\n{name}:")
        print(f"  指令 v={v}, w={w}")
        print(f"  左轮: PWM={s.left.pwm_duty:.1f}% dir={s.left.direction:+d}")
        print(f"  右轮: PWM={s.right.pwm_duty:.1f}% dir={s.right.direction:+d}")

    # 测试急停
    print("\n急停测试:")
    mc.emergency_stop()
    s = mc.get_state()
    print(f"  急停后: PWM左={s.left.pwm_duty:.1f}% PWM右={s.right.pwm_duty:.1f}% "
          f"急停={s.emergency_stop}")
    mc.clear_emergency()

    # 测试超声波
    print("\n超声波避障测试:")
    mc.ultrasonic.set_sim_distance(0.15)
    mc.update()
    print(f"  距离=0.15m → 急停={'触发' if mc.is_emergency else '未触发'}")
    mc.clear_emergency()

    mc.ultrasonic.set_sim_distance(1.0)
    mc.update()
    print(f"  距离=1.0m → 急停={'触发' if mc.is_emergency else '未触发'}")

    mc.stop()
    print("\n电机控制模块运行正常 ✓")


def run_network_test():
    """MQTT 网络模块自测"""
    from network.mqtt import (
        CocoMQTT, StateReport, AlertReport, StatsReport, build_state_report,
    )

    print("运行 MQTT 网络模块自测（模拟模式）...\n")

    client = CocoMQTT(debug=True)
    client.connect()

    # 状态上报
    state = build_state_report("moving", battery=85.5)
    client.publish_state(state)
    print(f"  状态上报: {state.state}, 电量={state.battery}%")

    # 告警
    client.alert_obstacle(0.25)
    print(f"  障碍物告警已发送")

    client.alert_low_battery(10.8)
    print(f"  低电量告警已发送")

    # 统计
    stats = StatsReport(uptime_minutes=10, total_distance=5.2,
                        queries_served=15, payments_completed=2)
    client.publish_stats(stats)
    print(f"  统计上报: {stats.queries_served}次查询, "
          f"{stats.payments_completed}笔支付")

    client.disconnect()
    print("\nMQTT 网络模块运行正常 ✓")


def run_vision_test():
    """视觉模块自测"""
    from vision.camera import Camera, DebugImageFeed
    from vision.detect import (
        FaceDetector, YOLODetector, VisionPipeline,
        DetectionResult, BBox, draw_detections,
    )

    print("运行视觉模块自测...\n")

    # 1. 摄像头
    print("[1] 摄像头（模拟模式）")
    cam = Camera(debug=True)
    cam.start()
    time.sleep(0.3)
    frame = cam.read()
    cam.stop()
    print(f"  分辨率: {frame.shape[1]}x{frame.shape[0]}, "
          f"通道: {frame.shape[2]}, 类型: {frame.dtype}")

    # 2. 人脸检测
    print("\n[2] 人脸检测（Haar Cascade）")
    fd = FaceDetector()
    if fd.available:
        face_img = DebugImageFeed.generate("face")
        faces = fd.detect(face_img)
        print(f"  Haar Cascade 已就绪，模拟人脸检测到 {len(faces)} 张脸")
    else:
        print("  不可用（缺少 OpenCV）")

    # 3. YOLO
    print("\n[3] YOLO 目标检测")
    yolo = YOLODetector()
    yolo.initialize()
    if yolo.available:
        shelf_img = DebugImageFeed.generate("shelf")
        objects = yolo.detect(shelf_img)
        print(f"  模型={yolo.model_name}, 检测到 {len(objects)} 个物体")
        for obj in objects[:3]:
            print(f"    {obj.class_name} conf={obj.confidence:.2f}")
    else:
        print("  ultralytics 未安装，跳过（PC 开发环境正常）")

    # 4. 管道集成
    print("\n[4] VisionPipeline 集成")
    vp = VisionPipeline(debug=True, enable_yolo=False)
    vp.initialize()
    vp.start()
    for _ in range(5):
        vp.process_frame()
    vp.stop()
    print(f"  管道处理 5 帧完成")

    # 5. 绘制
    print("\n[5] 检测框绘制")
    test_frame = DebugImageFeed.generate("shelf")
    fake_result = DetectionResult(
        objects=[BBox(100, 150, 80, 60, 0.85, "bottle"),
                 BBox(300, 200, 50, 50, 0.72, "can")],
        faces=[], has_person=False, has_face=False,
    )
    annotated = draw_detections(test_frame, fake_result)
    print(f"  标注帧: {annotated.shape[1]}x{annotated.shape[0]}")

    print("\n视觉模块运行正常 ✓")


def run_ui_test():
    """UI 屏幕模块自测 — 打开窗口循环切换所有状态"""
    from ui.screen import CocoScreenApp, STATE_TO_CHINESE

    print("启动 Coco UI 测试窗口...")
    print("  窗口将自动循环切换 8 种表情状态")
    print("  关闭窗口即可退出\n")

    screen = CocoScreenApp(debug=True)
    screen.set_state("idle")

    states = ["idle", "listening", "thinking", "pricing", "dialog",
              "moving", "payment", "alert"]
    state_idx = [0]

    def cycle():
        s = states[state_idx[0] % len(states)]
        state_idx[0] += 1
        screen.set_state(s)
        label = STATE_TO_CHINESE.get(s, s)
        print(f"  [{state_idx[0]:2d}] {s:12s} → {label}")

    from PyQt5.QtCore import QTimer
    timer = QTimer()
    timer.timeout.connect(cycle)
    timer.start(2500)

    screen.run()


def run_search(query: str = None):
    """商品检索模式"""
    from nlp.rag import RAGEngine

    print("正在加载商品库...")
    engine = RAGEngine()
    engine.initialize()
    print(f"已加载 {engine.total_products} 件商品，"
          f"{len(engine.get_categories())} 个分类\n")

    if query:
        _do_search(engine, query)
    else:
        # 交互模式
        print("输入商品查询（输入 q 退出）:\n")
        while True:
            try:
                q = input("🔍 > ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if q.lower() in ("q", "quit", "exit"):
                break
            if not q:
                continue
            _do_search(engine, q)


def _do_search(engine, query: str):
    """执行一次检索并打印结果"""
    results = engine.query(query, top_k=3)
    if not results:
        print(f"  未找到与 \"{query}\" 相关的商品\n")
        # 提示可用的分类
        print(f"  可用的商品分类: {', '.join(engine.get_categories())}\n")
    else:
        for i, r in enumerate(results):
            star = "⭐" if r.score > 0.3 else "  "
            print(f"  {star} #{i+1} {r.product.to_display()}")
            print(f"      {r.product.description}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Coco 实体店智能导购机器人",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py --debug              开发模式（机器人模拟）
  python main.py --voice              语音导购（麦克风+播报）
  python main.py --chat               交互式导购对话
  python main.py --search "可乐"      商品检索
  python main.py --admin              商品管理（增删改查）
  python main.py --web                Web商品管理后台
  python main.py --test-kinematics    仅测试运动学模块
  python main.py --motor-test          测试电机控制模块（模拟）
  python main.py --vision-test         测试视觉模块（模拟）
  python main.py --ui-test             测试 UI 屏幕（表情窗口）
  python main.py --network-test        测试 MQTT 网络模块（模拟）
        """
    )
    parser.add_argument("--debug", action="store_true",
                        help="开发模式：PC模拟，无硬件")
    parser.add_argument("--test-kinematics", action="store_true",
                        help="仅测试运动学模块，然后退出")
    parser.add_argument("--motor-test", action="store_true",
                        help="测试电机控制模块（模拟），然后退出")
    parser.add_argument("--vision-test", action="store_true",
                        help="测试视觉模块（模拟），然后退出")
    parser.add_argument("--ui-test", action="store_true",
                        help="测试 UI 屏幕模块（打开窗口）")
    parser.add_argument("--network-test", action="store_true",
                        help="测试 MQTT 网络模块（模拟）")
    parser.add_argument("--search", nargs="?", const=None, metavar="QUERY",
                        help="商品检索模式（不传参数进入交互模式）")
    parser.add_argument("--admin", action="store_true",
                        help="商品管理（增删改查）")
    parser.add_argument("--web", action="store_true",
                        help="启动 Web 商品管理后台（Gradio）")
    parser.add_argument("--chat", action="store_true",
                        help="交互式导购对话模式")
    parser.add_argument("--voice", action="store_true",
                        help="语音导购模式（麦克风+语音播报）")
    parser.add_argument("--log-level", default=LOG_LEVEL,
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help=f"日志级别 (默认: {LOG_LEVEL})")
    args = parser.parse_args()

    setup_logging(args.log_level)

    print(r"""
   ╔══════════════════════════════════╗
   ║     Coco 智能导购机器人 v0.1    ║
   ║     熊出没风格 · 履带底盘       ║
   ╚══════════════════════════════════╝
    """)

    if args.web:
        from nlp.web_admin import main as web_main
        web_main()
    elif args.voice:
        from audio.audio_pipeline import AudioPipeline
        from config import TTS_PRESET
        pipeline = AudioPipeline(debug_keyboard=DEBUG, tts_preset=TTS_PRESET)
        pipeline.run()
    elif args.chat:
        run_chat()
    elif args.admin:
        from nlp.product_manager import interactive_mode
        interactive_mode()
    elif args.search is not None:
        run_search(args.search)
    elif args.test_kinematics:
        test_kinematics()
    elif args.motor_test:
        run_motor_test()
    elif args.vision_test:
        run_vision_test()
    elif args.ui_test:
        run_ui_test()
    elif args.network_test:
        run_network_test()
    elif args.debug or DEBUG:
        run_debug_mode()
    else:
        run_production_mode()


if __name__ == "__main__":
    main()
