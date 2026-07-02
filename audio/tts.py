"""
Coco 导购机器人 — 语音合成 (TTS)

使用 Microsoft Edge TTS（免费、中文效果好、无需模型下载）。
依赖: pip install edge-tts

音色选择：
- zh-CN-XiaoyouNeural   童声（可爱） ← 默认，熊出没Coco风格
- zh-CN-XiaoxiaoNeural  女声（活泼）
- zh-CN-XiaoyiNeural    女声（温柔）
- zh-CN-YunxiNeural     男声（稳重）
"""

import asyncio
import io
import logging
import os
import tempfile
import subprocess
import sys
from typing import Optional

log = logging.getLogger("coco.tts")

# 检查 edge-tts 是否可用
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    log.warning("edge-tts 未安装，使用系统 TTS 作为兜底")


class TTSEngine:
    """语音合成引擎"""

    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural",
                 speed: str = "+10%",
                 pitch: str = "+15Hz"):
        """
        Args:
            voice: 音色名称 (zh-CN-XiaoxiaoNeural=活泼女声)
            speed: 语速调节，如 "+10%" 或 "-5%"
            pitch: 音调调节，如 "+15Hz" 偏高模拟童声
        """
        self.voice = voice
        self.speed = speed
        self.pitch = pitch

    def speak(self, text: str, block: bool = True) -> bool:
        """
        播报文本。

        Args:
            text: 要播报的文本
            block: True=阻塞等待播完, False=后台播放

        Returns:
            是否成功开始播放
        """
        if not text or not text.strip():
            return False

        text = text.strip()
        log.info(f"TTS: {text[:60]}...")

        if EDGE_TTS_AVAILABLE:
            return self._speak_edge(text, block)
        else:
            return self._speak_fallback(text, block)

    def _speak_edge(self, text: str, block: bool) -> bool:
        """用 edge-tts 播放"""
        if block:
            # 同步：直接用 asyncio.run()
            try:
                return asyncio.run(self._edge_speak(text))
            except Exception as e:
                log.error(f"TTS 异常: {e}")
                return False
        else:
            # 异步：后台线程
            import threading

            def _bg():
                try:
                    asyncio.run(self._edge_speak(text))
                except Exception:
                    pass

            t = threading.Thread(target=_bg, daemon=True)
            t.start()
            return True

    async def _edge_speak(self, text: str, retry: int = 1) -> bool:
        """edge-tts 异步播报（失败自动重试）"""
        import asyncio as aio

        last_error = None
        for attempt in range(retry + 1):
            try:
                if attempt > 0:
                    await aio.sleep(0.5)  # 重试前等一会

                communicate = edge_tts.Communicate(
                    text=text,
                    voice=self.voice,
                    rate=self.speed,
                )

                # 保存到临时文件
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    tmp_path = f.name

                await communicate.save(tmp_path)
                break  # 成功，跳出重试循环

            except Exception as e:
                last_error = e
                if attempt < retry:
                    log.warning(f"TTS 第{attempt+1}次失败，重试中...")
                continue
        else:
            # 所有重试都失败
            log.error(f"TTS 播报失败(重试{retry}次): {last_error}")
            return False

        # 播放音频
        try:
            if sys.platform == "win32":
                os.system(f'start /min "" "{tmp_path}"')
            else:
                subprocess.run(["mpg123", "-q", tmp_path], check=False)
        except Exception as e:
            log.error(f"播放失败: {e}")

        # 延迟删除临时文件
        import threading
        def _clean():
            import time
            time.sleep(5)
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        threading.Thread(target=_clean, daemon=True).start()

        return True

    def _speak_fallback(self, text: str, block: bool) -> bool:
        """系统 TTS 兜底"""
        if sys.platform == "win32":
            try:
                import winsound
                # Windows 自带语音
                import subprocess
                subprocess.run([
                    "powershell", "-Command",
                    f'Add-Type -AssemblyName System.Speech; '
                    f'(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{text}")'
                ], check=False, capture_output=True)
                return True
            except Exception:
                pass

        # 实在不行就打印
        print(f"[Coco说]: {text}")
        return True

    def speak_sync(self, text: str):
        """同步播报（阻塞直到说完）"""
        self.speak(text, block=True)

    def speak_async(self, text: str):
        """异步播报（立即返回，后台播放）"""
        self.speak(text, block=False)


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s: %(message)s")

    print("=" * 50)
    print("TTS 语音合成自测")
    print("=" * 50)

    tts = TTSEngine()

    test_texts = [
        "你好！我是 Coco，你的智能导购小帮手～",
        "可口可乐一瓶三块五，在A区一号货架，需要我带你去吗？",
    ]

    for text in test_texts:
        print(f"\n播报: {text}")
        tts.speak(text)
        print("  播报完成")

    print("\n自测完成！")
