"""
Coco 导购机器人 — 语音识别 (ASR)

基于 OpenAI Whisper，支持：
- 录音 → VAD静音检测 → Whisper转录
- DEBUG模式：键盘输入模拟语音
- VAD: 基于短时能量的简单语音活动检测

依赖: pip install sounddevice openai-whisper

Whisper模型选择：
- tiny:  39M参数, ~150MB, 树莓派5可用, 中文准确率~85%
- base:  74M参数, ~300MB, 更准确但更慢
- small: 244M参数, ~1GB, 树莓派带不动
"""

import io
import logging
import queue
import threading
import time
import os
import sys
from typing import Optional, Callable

import numpy as np

log = logging.getLogger("coco.asr")

# 检查依赖
try:
    import sounddevice as sd
    SD_AVAILABLE = True
except ImportError:
    SD_AVAILABLE = False
    log.warning("sounddevice 未安装，仅支持键盘输入模式")

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    log.warning("openai-whisper 未安装，仅支持键盘输入模式")

# 录音参数
SAMPLE_RATE = 16000          # Whisper 要求 16kHz
CHANNELS = 1                 # 单声道
DTYPE = np.int16             # 16bit PCM
BLOCK_DURATION = 0.03        # 30ms 每块


class VADDetector:
    """
    简单能量型 VAD（Voice Activity Detection）。

    原理：计算短时音频块的能量（RMS），超过阈值判定为"有人说话"。
    连续 N 块低于阈值 → 认为说完了。

    这不是深度学习方案，但在店里环境（相对安静）足够用。
    """

    def __init__(self, threshold: float = 0.002,
                 silence_blocks: int = 30,
                 speech_blocks: int = 5):
        """
        Args:
            threshold: 能量阈值 (0~1)
            silence_blocks: 连续多少块低于阈值认为说话结束
            speech_blocks: 连续多少块高于阈值认为开始说话
        """
        self.threshold = threshold
        self.silence_blocks = silence_blocks
        self.speech_blocks = speech_blocks
        self._silence_count = 0
        self._speech_count = 0
        self._is_speaking = False

    def reset(self):
        self._silence_count = 0
        self._speech_count = 0
        self._is_speaking = False

    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        """判断一个音频块是否包含语音"""
        # RMS 能量
        rms = np.sqrt(np.mean(audio_chunk.astype(np.float64) ** 2))
        # 归一化（16bit 音频最大值为 32767）
        energy = rms / 32767.0
        return energy > self.threshold

    def update(self, audio_chunk: np.ndarray) -> str:
        """
        更新 VAD 状态。

        Returns:
            "speaking"  - 正在说话
            "started"   - 刚开始说话（触发录音）
            "stopped"   - 刚说完（可以转录了）
            "silence"   - 安静
        """
        if self.is_speech(audio_chunk):
            self._speech_count += 1
            self._silence_count = 0
            if not self._is_speaking and self._speech_count >= self.speech_blocks:
                self._is_speaking = True
                return "started"
            return "speaking"
        else:
            self._silence_count += 1
            self._speech_count = 0
            if self._is_speaking and self._silence_count >= self.silence_blocks:
                self._is_speaking = False
                return "stopped"
            return "silence"


class ASREngine:
    """
    语音识别引擎。

    两种模式：
    - Whisper模式（生产）：麦克风 → VAD → 自动录音 → Whisper转录
    - 键盘模式（调试）：直接打字输入，模拟语音识别
    """

    def __init__(self,
                 model_name: str = "tiny",
                 language: str = "zh",
                 use_whisper: bool = True,
                 debug_keyboard: bool = False,
                 mic_device: int = None):
        """
        Args:
            model_name: Whisper模型大小 "tiny"/"base"/"small"
            language: 识别语言
            use_whisper: True=加载Whisper, False=仅键盘模式
            debug_keyboard: True=用键盘输入代替麦克风
            mic_device: 麦克风设备号 (None=系统默认)
        """
        self.model_name = model_name
        self.language = language
        self.debug_keyboard = debug_keyboard
        self.mic_device = mic_device

        self._model = None
        self._vad = VADDetector()
        self._audio_buffer = []
        self._recording = False

        if use_whisper and WHISPER_AVAILABLE and not debug_keyboard:
            self._load_model()

        # 存储最近一次识别结果
        self._result_queue = queue.Queue()

    def _load_model(self):
        """加载 Whisper 模型"""
        try:
            log.info(f"加载 Whisper 模型: {self.model_name} ...")
            self._model = whisper.load_model(self.model_name)
            log.info("Whisper 加载完成")
        except Exception as e:
            log.error(f"Whisper 加载失败: {e}")
            self._model = None

    @property
    def available(self) -> bool:
        """检查 ASR 是否可用"""
        return self._model is not None or self.debug_keyboard

    def listen(self, timeout: float = 10.0) -> Optional[str]:
        """
        听用户说一句话，返回识别的文本。

        这是对外主接口。

        Args:
            timeout: 最大等待时间（秒）

        Returns:
            识别到的文本，如果超时或失败返回 None
        """
        if self.debug_keyboard:
            return self._listen_keyboard(timeout)
        elif self._model is not None and SD_AVAILABLE:
            return self._listen_microphone(timeout)
        else:
            # 回退到键盘
            log.warning("麦克风/Whisper不可用，使用键盘输入")
            return self._listen_keyboard(timeout)

    def _listen_keyboard(self, timeout: float) -> Optional[str]:
        """键盘输入模式"""
        try:
            print("\n🎤 请输入（模拟语音）: ", end="", flush=True)
            # 这里不能用 input()，因为它在主线程会阻塞 UI
            # 在命令行测试时可以用
            text = input()
            return text.strip() if text.strip() else None
        except (EOFError, KeyboardInterrupt):
            return None

    def _listen_microphone(self, timeout: float) -> Optional[str]:
        """
        麦克风模式：录音 + VAD + Whisper

        流程：
        1. 持续录音
        2. VAD 检测到用户开始说话 → 开始保存音频
        3. VAD 检测到用户说完 → 停止录音
        4. Whisper 转录 → 返回文本
        """
        self._audio_buffer = []
        self._recording = False
        self._vad.reset()
        result = [None]
        done = threading.Event()

        def audio_callback(indata, frames, time_info, status):
            if status:
                log.warning(f"录音状态: {status}")

            chunk = indata[:, 0].copy()   # 单声道
            vad_result = self._vad.update(chunk)

            if vad_result == "started":
                log.debug("VAD: 检测到语音开始")
                self._recording = True
                self._audio_buffer = list(self._audio_buffer[-10:])  # 保留前0.3s
            elif vad_result == "stopped" and self._recording:
                log.debug("VAD: 检测到语音结束")
                self._recording = False
                # 转录
                if len(self._audio_buffer) > 30:  # 至少 0.9s
                    audio = np.concatenate(self._audio_buffer)
                    text = self._transcribe(audio)
                    result[0] = text
                done.set()
                raise sd.CallbackStop()

            if self._recording:
                self._audio_buffer.append(chunk)

            # 超时
            if len(self._audio_buffer) > SAMPLE_RATE * timeout / BLOCK_DURATION:
                self._recording = False
                if len(self._audio_buffer) > 30:
                    audio = np.concatenate(self._audio_buffer)
                    text = self._transcribe(audio)
                    result[0] = text
                done.set()
                raise sd.CallbackStop()

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=int(SAMPLE_RATE * BLOCK_DURATION),
                callback=audio_callback,
                device=self.mic_device,
            ):
                done.wait(timeout=timeout)
        except sd.CallbackStop:
            pass
        except Exception as e:
            log.error(f"录音异常: {e}")
            return None

        return result[0]

    def _transcribe(self, audio: np.ndarray) -> Optional[str]:
        """Whisper 转录"""
        if self._model is None:
            return None

        try:
            # 转为 float32 归一化
            audio_float = audio.astype(np.float32) / 32768.0

            result = self._model.transcribe(
                audio_float,
                language=self.language,
                task="transcribe",
                fp16=False,              # 树莓派用 FP32
                no_speech_threshold=0.6,
            )
            text = result.get("text", "").strip()
            log.info(f"Whisper: {text}")
            return text
        except Exception as e:
            log.error(f"Whisper 转录失败: {e}")
            return None

    def record_to_file(self, filename: str, duration: float = 5.0):
        """录制一段音频到文件（用于测试/收集数据）"""
        if not SD_AVAILABLE:
            log.error("sounddevice 不可用")
            return

        log.info(f"录音 {duration}s → {filename}")
        audio = sd.rec(
            int(duration * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
        )
        sd.wait()

        # 保存为 WAV
        import wave
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # 16bit
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio.tobytes())

        log.info(f"已保存: {filename}")


# ============================================================
# 键盘输入监听器（用于 GUI 线程）
# ============================================================

class KeyboardListener:
    """
    非阻塞键盘输入监听器。

    用于 PyQt5 等 GUI 场景：在一个后台线程等待键盘输入，
    不阻塞 UI 事件循环。输入后通过回调通知。
    """

    def __init__(self, callback: Callable[[str], None]):
        self.callback = callback
        self._thread = None
        self._running = False

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _run(self):
        while self._running:
            try:
                text = input()
                if text.strip():
                    self.callback(text.strip())
            except (EOFError, KeyboardInterrupt):
                break


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s: %(message)s")

    print("=" * 50)
    print("ASR 语音识别自测")
    print("=" * 50)

    # 检查依赖
    print(f"\nsounddevice: {'OK' if SD_AVAILABLE else 'NO'}")
    print(f"Whisper: {'OK' if WHISPER_AVAILABLE else 'NO'}")

    if not WHISPER_AVAILABLE:
        print("\n⚠ Whisper 未安装，请先安装: pip install openai-whisper")
        print("  模型下载需要联网（约150MB，用 hf-mirror.com）")

    asr = ASREngine(debug_keyboard=True)
    print(f"\n键盘模拟模式（麦克风模式需要硬件支持）")
    print("输入一句话试试: ")
    text = asr.listen()
    print(f"识别结果: {text}")
