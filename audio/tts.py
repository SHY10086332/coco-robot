"""
Coco -- TTS

edge-tts / cosyvoice / system
"""

import asyncio
import logging
import os
import subprocess
import sys
import tempfile
import threading
from typing import Optional, Dict, List

log = logging.getLogger("coco.tts")

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    log.warning("edge-tts not installed, fallback to system TTS")

from config import (
    TTS_ENGINE, TTS_VOICE, TTS_SPEED, TTS_PITCH, TTS_PRESET,
    COSY_MODEL_CACHE, COSY_MODEL_TYPE, COSY_REF_WAV, COSY_REF_TEXT,
)

VOICE_PRESETS: Dict[str, Dict] = {
    "coco_child": {
        "voice": "zh-CN-XiaoxiaoNeural",
        "speed": "+15%",
        "pitch": "+35Hz",
        "desc": "Coco child voice",
    },
    "xiaoxiao": {
        "voice": "zh-CN-XiaoxiaoNeural",
        "speed": "+10%",
        "pitch": "+15Hz",
        "desc": "Lively female",
    },
    "xiaoyi": {
        "voice": "zh-CN-YunyiNeural",
        "speed": "+5%",
        "pitch": "+0Hz",
        "desc": "Gentle female",
    },
    "yunxi": {
        "voice": "zh-CN-YunxiNeural",
        "speed": "+0%",
        "pitch": "+0Hz",
        "desc": "Steady male",
    },
    "xiaoyou": {
        "voice": "zh-CN-XiaoyouNeural",
        "speed": "+10%",
        "pitch": "+10Hz",
        "desc": "Microsoft child voice",
    },
    "fast_coco": {
        "voice": "zh-CN-XiaoxiaoNeural",
        "speed": "+25%",
        "pitch": "+45Hz",
        "desc": "Fast Coco",
    },
    "slow_gentle": {
        "voice": "zh-CN-YunyiNeural",
        "speed": "-10%",
        "pitch": "-5Hz",
        "desc": "Slow gentle",
    },
}


class TTSEngine:
    """TTS engine -- edge-tts / cosyvoice / system"""

    def __init__(self, preset: str = None, engine: str = None):
        self._engine = engine or TTS_ENGINE
        self._current_preset = preset or TTS_PRESET
        self._cosy = None

        # edge-tts params
        if self._current_preset in VOICE_PRESETS:
            p = VOICE_PRESETS[self._current_preset]
            self.voice = p["voice"]
            self.speed = p["speed"]
            self.pitch = p["pitch"]
        else:
            self.voice = TTS_VOICE
            self.speed = TTS_SPEED
            self.pitch = TTS_PITCH

        log.info(f"TTS engine: {self._engine}")

    # ---- lazy cosyvoice init ----

    def _get_cosy(self):
        if self._cosy is not None:
            return self._cosy
        try:
            from .cosy_tts import CosyVoiceTTS, COSY_AVAILABLE as _CA
            if not _CA:
                log.error("CosyVoice not available")
                return None
            self._cosy = CosyVoiceTTS(
                model_cache_dir=COSY_MODEL_CACHE,
                model_type=COSY_MODEL_TYPE,
            )
            if not self._cosy.load():
                log.error("CosyVoice load failed")
                self._cosy = None
                return None
            # set reference voice
            ref_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), COSY_REF_WAV)
            if os.path.exists(ref_path):
                self._cosy.set_reference_voice(ref_path, COSY_REF_TEXT)
            return self._cosy
        except Exception as e:
            log.error(f"CosyVoice init failed: {e}")
            return None

    # ---- voice presets (edge-tts only) ----

    def set_preset(self, name: str) -> bool:
        if name not in VOICE_PRESETS:
            log.warning(f"Unknown preset '{name}'. Available: {list(VOICE_PRESETS.keys())}")
            return False
        p = VOICE_PRESETS[name]
        self.voice = p["voice"]
        self.speed = p["speed"]
        self.pitch = p["pitch"]
        self._current_preset = name
        log.info(f"TTS preset: {name}")
        return True

    def get_preset(self) -> str:
        return self._current_preset

    def set_pitch(self, pitch: str):
        self.pitch = pitch

    def set_speed(self, speed: str):
        self.speed = speed

    @staticmethod
    def list_presets() -> List[Dict]:
        result = []
        for name, p in VOICE_PRESETS.items():
            result.append({
                "name": name,
                "voice": p["voice"],
                "speed": p["speed"],
                "pitch": p["pitch"],
                "desc": p["desc"],
            })
        return result

    # ---- speak ----

    def speak(self, text: str, block: bool = True) -> bool:
        if not text or not text.strip():
            return False
        text = text.strip()
        log.info(f"TTS [{self._engine}]: {text[:60]}...")

        if self._engine == "cosyvoice":
            return self._speak_cosy(text, block)
        elif EDGE_TTS_AVAILABLE:
            return self._speak_edge(text, block)
        else:
            return self._speak_system(text, block)

    def _speak_cosy(self, text: str, block: bool) -> bool:
        cosy = self._get_cosy()
        if cosy is None:
            log.warning("CosyVoice unavailable, fallback to edge-tts")
            if EDGE_TTS_AVAILABLE:
                return self._speak_edge(text, block)
            return self._speak_system(text, block)

        return cosy.speak(text, block=block)

    def _speak_edge(self, text: str, block: bool) -> bool:
        if block:
            try:
                return asyncio.run(self._edge_synth(text))
            except Exception as e:
                log.error(f"TTS error: {e}")
                return False
        else:
            threading.Thread(target=lambda: asyncio.run(self._edge_synth(text)), daemon=True).start()
            return True

    async def _edge_synth(self, text: str, retry: int = 1) -> bool:
        import asyncio as aio
        last_error = None
        for attempt in range(retry + 1):
            try:
                if attempt > 0:
                    await aio.sleep(0.5)
                communicate = edge_tts.Communicate(
                    text=text, voice=self.voice,
                    rate=self.speed, pitch=self.pitch,
                )
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    tmp_path = f.name
                await communicate.save(tmp_path)
                break
            except Exception as e:
                last_error = e
                if attempt < retry:
                    log.warning(f"TTS retry {attempt+1}...")
        else:
            log.error(f"TTS failed after {retry} retries: {last_error}")
            return False

        if sys.platform == "win32":
            os.system(f'start /min "" "{tmp_path}"')
        else:
            subprocess.run(["mpg123", "-q", tmp_path], check=False)

        def _clean():
            import time
            time.sleep(8)
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        threading.Thread(target=_clean, daemon=True).start()
        return True

    def _speak_system(self, text: str, block: bool) -> bool:
        if sys.platform == "win32":
            try:
                subprocess.run([
                    "powershell", "-Command",
                    f'Add-Type -AssemblyName System.Speech; '
                    f'(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{text}")'
                ], check=False, capture_output=True)
                return True
            except Exception:
                pass
        print(f"[Coco]: {text}")
        return True

    def speak_sync(self, text: str):
        self.speak(text, block=True)

    def speak_async(self, text: str):
        self.speak(text, block=False)


# ============================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("=" * 50)
    print(f"TTS self-test (engine={TTS_ENGINE})")
    print("=" * 50)

    tts = TTSEngine()

    if TTS_ENGINE == "edge-tts":
        print("\nVoice presets:")
        for p in tts.list_presets():
            print(f"  {p['name']:15s} {p['desc']}")

        for preset in ["coco_child", "xiaoxiao", "yunxi"]:
            print(f"\nSwitching to: {preset}")
            tts.set_preset(preset)
            tts.speak("nihao, wo shi Coco!")

    elif TTS_ENGINE == "cosyvoice":
        tts.speak("nihao, wo shi Coco, huanying lai dao women de shangdian!")

    print("\nDone!")
