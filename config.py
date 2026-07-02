"""
Coco 导购机器人 — 全局配置
所有可调参数集中在这里，方便标定和调试。
"""

# ============================================================
# 底盘 & 运动学参数（JGA25-370 直流减速电机 + 履带底盘）
# ============================================================

# 电机参数
MOTOR_RATED_RPM = 100          # 额定转速 (revolutions per minute)
MOTOR_RATED_VOLTAGE = 12.0     # 额定电压 (V)
MOTOR_ENCODER_PPR = 11         # 编码器线数 (pulses per revolution，实测值)
MOTOR_GEAR_RATIO = 1.0         # 减速比（电机自带减速箱，100转已是输出转速）

# 轮子 & 履带参数
WHEEL_RADIUS = 0.032           # 驱动轮半径 (m)，32mm
TRACK_WIDTH = 0.20             # 左右履带中心距 / 轮距 (m)，200mm
TRACK_GROUND_LENGTH = 0.25     # 履带接地长度 (m)，250mm — 决定爬台阶能力

# 里程计更新周期 (s)
ODOMETRY_INTERVAL = 0.02       # 50Hz

# PID 速度环参数（初值，需实车标定）
PID_KP = 1.0
PID_KI = 0.1
PID_KD = 0.02

# 速度限制（安全）
MAX_LINEAR_SPEED = 0.5         # 最大线速度 (m/s)
MAX_ANGULAR_SPEED = 1.0        # 最大角速度 (rad/s)
EMERGENCY_STOP_DISTANCE = 0.3  # 超声波急停距离 (m)


# ============================================================
# 音频参数
# ============================================================

SAMPLE_RATE = 16000            # Whisper 输入采样率
CHANNELS = 1                   # 单声道
CHUNK_DURATION = 0.03          # 每次录音块时长 (s)，30ms
WAKE_WORD = "你好coco"          # 唤醒词
WAKE_WORD_SENSITIVITY = 0.5    # Porcupine 灵敏度 (0~1)

# Whisper 模型: "tiny" | "base" | "small" | "medium" | "large"
# tiny=39M参数, base=74M, 树莓派5推荐 tiny 或 base
WHISPER_MODEL = "tiny"
WHISPER_LANGUAGE = "zh"


# ============================================================
# LLM & RAG 参数
# ============================================================

OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:0.5b"              # 0.5B 够树莓派跑，换 1.5B 也行
OLLAMA_TIMEOUT = 30.0                       # 推理超时 (s)

CHROMA_DB_PATH = "data/chroma_db"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"       # Sentence-Transformers 向量化

# RAG 检索参数
RAG_TOP_K = 5                               # 检索返回条数
RAG_SIMILARITY_THRESHOLD = 0.6              # 相似度阈值（低于此值认为无匹配）


# ============================================================
# TTS 参数
# ============================================================

TTS_ENGINE = "edge-tts"                     # Microsoft Edge TTS（免费）
TTS_VOICE = "zh-CN-XiaoxiaoNeural"          # 最活泼女声，+pitch模拟童声
TTS_SPEED = "+10%"                          # 语速
TTS_PITCH = "+15Hz"                         # 音调偏高→接近童声效果


# ============================================================
# 视觉参数
# ============================================================

CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 10

YOLO_MODEL = "yolov8n.pt"                   # nano 版本，树莓派可跑
YOLO_CONFIDENCE = 0.5

# 人脸检测（用于判断"有人在看屏幕"）
FACE_DETECTION_INTERVAL = 0.5               # 每 0.5s 检测一次


# ============================================================
# UI / 屏幕参数
# ============================================================

SCREEN_WIDTH = 800                          # 8寸圆形屏可用像素区
SCREEN_HEIGHT = 800
SCREEN_DIAMETER_MM = 200                    # 屏幕物理直径

# 动画帧率
ANIMATION_FPS = 24

# 状态对应颜色
COLOR_IDLE = "#00FFD0"                      # 青色（待机）
COLOR_LISTENING = "#00BFFF"                 # 深天蓝（聆听中）
COLOR_THINKING = "#FFD700"                  # 金色（思考中）
COLOR_SPEAKING = "#00FF88"                  # 绿色（说话中）
COLOR_WARNING = "#FF4444"                   # 红色（警告）


# ============================================================
# MQTT 参数
# ============================================================

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_STATE = "coco/state"             # 状态上报
MQTT_TOPIC_ALERT = "coco/alert"             # 异常告警 → 店长手机
MQTT_TOPIC_STATS = "coco/stats"             # 统计数据
MQTT_KEEPALIVE = 60


# ============================================================
# GPIO 引脚定义 (树莓派5 BCM编号)
# ============================================================

PIN_MOTOR_LEFT_PWM = 12                     # 左电机 PWM
PIN_MOTOR_LEFT_IN1 = 5
PIN_MOTOR_LEFT_IN2 = 6
PIN_MOTOR_RIGHT_PWM = 13                    # 右电机 PWM
PIN_MOTOR_RIGHT_IN1 = 7
PIN_MOTOR_RIGHT_IN2 = 8

PIN_LED_STRIP = 18                          # LED 灯带 PWM
PIN_ANTENNA_LED = 23                        # 天线 LED

PIN_ULTRASONIC_TRIG = 17
PIN_ULTRASONIC_ECHO = 27


# ============================================================
# 调试 & 开发模式
# ============================================================

DEBUG = True                                # True → 模拟硬件，可在PC上跑
LOG_LEVEL = "INFO"                          # DEBUG | INFO | WARNING | ERROR
