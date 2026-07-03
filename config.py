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
# tiny=39M参数, base=74M, Orange Pi 5 推荐 tiny 或 base
WHISPER_MODEL = "base"
WHISPER_LANGUAGE = "zh"


# ============================================================
# LLM & RAG 参数
# ============================================================

OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:1.5b"              # 1.5B，Orange Pi 5 可跑，回答质量比0.5B好很多
OLLAMA_TIMEOUT = 30.0                       # 推理超时 (s)

CHROMA_DB_PATH = "data/chroma_db"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"       # Sentence-Transformers 向量化

# RAG 检索参数
RAG_TOP_K = 5                               # 检索返回条数
RAG_SIMILARITY_THRESHOLD = 0.6              # 相似度阈值（低于此值认为无匹配）


# ============================================================
# TTS 参数
# ============================================================

TTS_ENGINE = "cosyvoice"                   # 语音引擎: "edge-tts" / "cosyvoice" / "system"
                                             # edge-tts = 微软免费在线（默认，无需GPU）
                                             # cosyvoice = 阿里语音克隆（需GPU，音色还原度高）
                                             # system = Windows/macOS 自带 TTS
TTS_PRESET = "coco_child"                   # Edge-TTS 预设（见 audio/tts.py VOICE_PRESETS）
TTS_VOICE = "zh-CN-XiaoxiaoNeural"          # 底层音色（被 TTS_PRESET 覆盖）
TTS_SPEED = "+15%"                          # 语速（被预设覆盖）
TTS_PITCH = "+35Hz"                         # 音调（被预设覆盖）

# CosyVoice 参数（仅当 TTS_ENGINE="cosyvoice" 时生效）
COSY_MODEL_TYPE = "instruct"                # instruct / sft / base
COSY_MODEL_CACHE = "D:/coco_venv/models"     # 模型缓存目录（CosyVoice-300M 所在父目录）
COSY_REF_WAV = "data/voices/coco_ref_short.wav"   # Coco 参考音频（5s片段）
COSY_REF_TEXT = "你好我是Coco503号履带式钛合金派克型考古机器人"


# ============================================================
# 视觉参数
# ============================================================

CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 10

YOLO_MODEL = "yolov8n.pt"                   # nano 版本，Orange Pi / 树莓派可跑
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
# GPIO 引脚定义 (Orange Pi 5, RK3588)
# ============================================================

# 格式: (gpiochip, line)
# 例: (4, 18) → /dev/gpiochip4 line 18 → 物理引脚7 = GPIO4_C2
# 实际接线时请对照 Orange Pi 5 40pin 引脚图调整
PIN_MOTOR_LEFT_PWM  = (4, 18)    # 物理引脚7  = GPIO4_C2
PIN_MOTOR_LEFT_IN1  = (4, 19)    # 物理引脚11 = GPIO4_C3
PIN_MOTOR_LEFT_IN2  = (4, 21)    # 物理引脚12 = GPIO4_C5
PIN_MOTOR_RIGHT_PWM = (4, 22)    # 物理引脚13 = GPIO4_C6
PIN_MOTOR_RIGHT_IN1 = (4, 8)     # 物理引脚16 = GPIO4_B0
PIN_MOTOR_RIGHT_IN2 = (4, 10)    # 物理引脚18 = GPIO4_B2

PIN_LED_STRIP       = (1, 27)    # 物理引脚22 = GPIO1_D3
PIN_ANTENNA_LED     = (4, 11)    # 物理引脚15 = GPIO4_B3

PIN_ULTRASONIC_TRIG = (0, 14)    # 物理引脚8  = GPIO0_C6
PIN_ULTRASONIC_ECHO = (0, 15)    # 物理引脚10 = GPIO0_C7

PIN_SERVO_PAN = (1, 28)          # 物理引脚24 = GPIO1_D4（头水平旋转舵机）


# ============================================================
# 舵机参数（SG90，头部云台）
# ============================================================

SERVO_MIN_ANGLE = 0              # 最小角度
SERVO_MAX_ANGLE = 180            # 最大角度
SERVO_CENTER_ANGLE = 90          # 中心角度（正对前方）
SERVO_MIN_PULSE_US = 500         # 0° 对应脉宽 (μs)
SERVO_MAX_PULSE_US = 2500        # 180° 对应脉宽 (μs)
SERVO_SPEED_DEG_PER_S = 300      # 舵机转动速度 (°/s)，SG90 约 0.12s/60°


# ============================================================
# 视觉追踪参数
# ============================================================

TRACKER_ANGLE_P_GAIN = 0.08      # 水平偏差 → 舵机角度的 P 增益
TRACKER_HEAD_RANGE = 30          # 头可转范围 ±30°（在此范围内只转头）
TRACKER_CHASSIS_W_GAIN = 0.6     # 超出头范围后，底盘的角速度增益
TRACKER_PERSON_MIN_AREA = 3000   # 目标框最小面积（低于此值 → 前进靠近）
TRACKER_PERSON_MAX_AREA = 25000  # 目标框最大面积（超过此值 → 后退）
TRACKER_FOLLOW_SPEED = 0.15      # 跟随线速度 (m/s)
TRACKER_LOST_TIMEOUT = 3.0       # 丢失目标后几秒开始扫描搜索
TRACKER_SWEEP_SPEED = 60         # 扫描时舵机扫速 (°/s)


# ============================================================
# 调试 & 开发模式
# ============================================================

DEBUG = True                                # True → 模拟硬件，可在PC上跑
LOG_LEVEL = "INFO"                          # DEBUG | INFO | WARNING | ERROR
