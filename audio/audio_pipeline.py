"""
Coco 导购机器人 — 音频管线

串联完整语音交互链路：
  麦克风录音 → VAD静音检测 → Whisper语音识别 → 对话管理 → TTS播报

两种运行模式：
- DEBUG模式: 键盘输入代替麦克风，屏幕输出代替喇叭（方便PC开发）
- 生产模式: 真实麦克风 + Whisper + Edge-TTS（树莓派5硬件）

用法:
    pipeline = AudioPipeline()
    pipeline.initialize()
    pipeline.run()          # 持续对话循环
    pipeline.listen_once()  # 听一句话并回复
"""

import logging
import sys
import threading
import time
from typing import Optional, Callable

from .asr import ASREngine
from .tts import TTSEngine

log = logging.getLogger("coco.audio")


class AudioPipeline:
    """
    音频管线 — 语音交互的完整闭环。

    事件回调（可选，用于 UI 联动）：
    - on_listening:  开始聆听
    - on_speech:     识别到语音文本
    - on_thinking:   正在处理对话
    - on_reply:      准备播报回复
    - on_done:       一轮对话完成
    """

    def __init__(self,
                 whisper_model: str = "tiny",
                 tts_voice: str = "zh-CN-XiaoyouNeural",
                 debug_keyboard: bool = True):
        """
        Args:
            whisper_model: Whisper 模型大小
            tts_voice: TTS 音色
            debug_keyboard: True=键盘模拟, False=真实麦克风
        """
        self.asr = ASREngine(
            model_name=whisper_model,
            debug_keyboard=debug_keyboard,
        )
        self.tts = TTSEngine(voice=tts_voice)
        self.debug_keyboard = debug_keyboard

        # 对话管理器（延迟加载）
        self._dialogue = None

        # 回调
        self.on_listening: Optional[Callable[[], None]] = None
        self.on_speech: Optional[Callable[[str], None]] = None
        self.on_thinking: Optional[Callable[[], None]] = None
        self.on_reply: Optional[Callable[[str], None]] = None
        self.on_done: Optional[Callable[[], None]] = None

        self._running = False

    def initialize(self):
        """初始化对话管理器"""
        from nlp.dialogue import DialogueManager
        self._dialogue = DialogueManager()
        self._dialogue.initialize()
        log.info("音频管线就绪")

    def listen_once(self) -> bool:
        """
        听一句话 → 理解 → 回复。

        Returns:
            True=成功完成一轮对话, False=超时/失败
        """
        if self._dialogue is None:
            self.initialize()

        # 1. 聆听
        if self.on_listening:
            self.on_listening()

        if self.debug_keyboard:
            print("\n" + "=" * 40)
        text = self.asr.listen(timeout=15.0)

        if not text:
            return False

        if self.on_speech:
            self.on_speech(text)

        # 2. 思考
        if self.on_thinking:
            self.on_thinking()

        reply = self._dialogue.chat(text)

        if self.on_reply:
            self.on_reply(reply.text)

        # 3. 播报
        print(f"\n🤖 Coco: {reply.text}")
        self.tts.speak(reply.text)

        if self.on_done:
            self.on_done()

        return True

    def run(self):
        """
        持续对话循环。按 Ctrl+C 退出。
        """
        if self._dialogue is None:
            self.initialize()

        self._running = True

        print("""
   ╔══════════════════════════════════════╗
   ║   Coco 语音导购模式                 ║
   ║   说"你好Coco"开始对话              ║
   ║   按 Ctrl+C 退出                    ║
   ╚══════════════════════════════════════╝
        """)

        try:
            while self._running:
                ok = self.listen_once()
                if not ok and self.debug_keyboard:
                    # 键盘模式下，空输入不算超时
                    time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\nCoco 下班啦，再见！👋")
        finally:
            self._running = False

    def stop(self):
        """停止对话循环"""
        self._running = False


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                        datefmt="%H:%M:%S")

    print("=" * 50)
    print("音频管线自测（键盘模拟模式）")
    print("=" * 50)
    print("\n按 Enter 开始一轮对话，说几句话试试")
    print("输入 'q' 退出\n")

    pipeline = AudioPipeline(debug_keyboard=True)
    pipeline.initialize()

    while True:
        try:
            text = input("🎤 > ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if text.lower() == "q":
            break
        if not text:
            continue

        # 模拟 ASR 输入 → 对话 → TTS
        from nlp.dialogue import DialogueReply
        reply = pipeline._dialogue.chat(text)
        print(f"🎯 [{reply.intent}]")
        print(f"🤖 {reply.text}")

        # TTS 播报
        pipeline.tts.speak(reply.text)

    print("\n自测完成！")
