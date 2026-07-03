"""
Coco 导购机器人 — CosyVoice 语音克隆 TTS

使用阿里 CosyVoice 实现零样本语音克隆：
只需 3~10 秒参考音频即可复制目标说话人的音色。

用法:
    # 首次使用会自动下载模型（约 2GB，需联网）
    engine = CosyVoiceTTS()
    engine.load()

    # 方式一：内置中文音色（快速体验）
    engine.speak("你好！我是Coco～", voice_id="中文女")

    # 方式二：零样本克隆（需要提供参考音频）
    engine.set_reference_voice("data/voices/coco_ref.wav", "你好，我是Coco！")
    engine.speak("可乐一瓶三块五～")

参考音频要求:
    - 3~10 秒，采样率不限（会自动重采样到 16kHz）
    - 无背景音乐/噪音（从熊出没片段中截取纯净说话部分）
    - 语速自然，语气活泼

硬件要求:
    - NVIDIA GPU 4GB+ VRAM（RTX 5060 8GB ✓）
    - 首次运行需下载约 2GB 模型
    - RTX 5060 (Blackwell sm_120) 需 PyTorch >= 2.12 nightly
"""

import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from typing import Optional, List, Dict

import numpy as np
import soundfile as sf
import torch

log = logging.getLogger("coco.cosy_tts")

# ---------------------------------------------------------------------------
# CosyVoice 源码路径（没有 setup.py，只能手动加 sys.path）
# ---------------------------------------------------------------------------
_COSYVOICE_SRC = os.environ.get("COSYVOICE_SRC", "D:/CosyVoice")
_COSYVOICE_MATCHA = os.path.join(_COSYVOICE_SRC, "third_party", "Matcha-TTS")

for _p in [_COSYVOICE_SRC, _COSYVOICE_MATCHA]:
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Monkey-patch CosyVoice load_wav: 用 soundfile 替代 torchaudio
# 原因：PyTorch nightly 的 torchaudio 强制使用 torchcodec，后者需要 FFmpeg DLL，
# 在 Windows 上极其难配。soundfile 直接基于 libsndfile，零配置。
# ---------------------------------------------------------------------------
_patch_applied = False


def _apply_load_wav_patch():
    global _patch_applied
    if _patch_applied:
        return
    try:
        import cosyvoice.utils.file_utils as fu
        import torchaudio

        def _patched_load_wav(wav, target_sr):
            """用 soundfile 加载音频，torchaudio 重采样"""
            if isinstance(wav, str):
                speech_np, sample_rate = sf.read(wav, dtype="float32")
                speech = torch.from_numpy(speech_np).unsqueeze(0)  # (1, T)
            else:
                speech = wav
                if hasattr(speech, "cpu"):
                    speech = speech.cpu().numpy()
                elif isinstance(speech, np.ndarray):
                    pass
                else:
                    speech = np.array(speech)
                if speech.ndim == 1:
                    speech = speech[np.newaxis, :]
                speech = torch.from_numpy(speech.astype(np.float32))
                sample_rate = 16000

            if speech.shape[0] > 1:
                speech = speech.mean(dim=0, keepdim=True)
            if sample_rate != target_sr:
                speech = torchaudio.functional.resample(speech, sample_rate, target_sr)
            return speech

        fu.load_wav = _patched_load_wav
        _patch_applied = True
    except ImportError:
        pass


COSY_AVAILABLE = False
try:
    _apply_load_wav_patch()
    from cosyvoice.cli.cosyvoice import CosyVoice  # noqa: E402
    COSY_AVAILABLE = True
except ImportError:
    log.warning("CosyVoice 未安装。请 git clone https://github.com/FunAudioLLM/CosyVoice.git D:/CosyVoice")

# 内置中文音色（无需参考音频）
BUILTIN_VOICES = {
    "中文男": "沉稳男声，新闻播报风格",
    "中文女": "温柔女声，标准普通话",
    "粤语女": "粤语女声",
    "日语男": "日语男声",
    "英文男": "英语男声",
    "英文女": "英语女声",
}


class CosyVoiceTTS:
    """CosyVoice 语音克隆引擎"""

    def __init__(
        self,
        model_cache_dir: str = "checkpoints/cosyvoice",
        model_type: str = "instruct",  # instruct / sft / base
        device: str = "auto",
    ):
        """
        Args:
            model_cache_dir: 模型缓存目录（首次运行自动下载到此处）
            model_type: instruct=指令控制, sft=微调, base=基础300M
            device: "cuda" / "cpu" / "auto"
        """
        self.model_cache_dir = model_cache_dir
        self.model_type = model_type

        if device == "auto":
            if torch.cuda.is_available():
                # 检查是否真的能跑 CUDA kernel（sm_120 需要 PyTorch >= 2.12 nightly）
                try:
                    t = torch.randn(1).cuda()
                    t = t + 1
                    self.device = "cuda"
                except RuntimeError:
                    log.warning("GPU 检测到但 CUDA kernel 不兼容，回退到 CPU。"
                                "RTX 5060 (sm_120) 需 PyTorch >= 2.12 nightly。")
                    os.environ["CUDA_VISIBLE_DEVICES"] = ""
                    self.device = "cpu"
            else:
                self.device = "cpu"

        self.cosy_model_dir = os.path.join(model_cache_dir, "CosyVoice-300M")
        self._model = None
        self._loaded = False

        # 自定义参考音频路径（零样本克隆）
        self._ref_wav_path: str = ""
        self._ref_text: str = ""

    def load(self) -> bool:
        """加载 CosyVoice 模型（首次运行自动下载）"""
        if not COSY_AVAILABLE:
            log.error("CosyVoice 未安装。pip install cosyvoice")
            return False

        if self._loaded:
            return True

        if not os.path.exists(self.cosy_model_dir):
            log.error(f"模型目录不存在: {self.cosy_model_dir}")
            log.error("请先下载模型: modelscope download --model iic/CosyVoice-300M "
                      f"--local_dir {self.cosy_model_dir}")
            return False

        try:
            log.info(f"加载 CosyVoice (type={self.model_type}, device={self.device})...")
            log.info("首次运行将自动加载模型 (~2GB)，请耐心等待...")

            self._model = CosyVoice(
                self.cosy_model_dir,
                load_jit=False,
                fp16=(self.device == "cuda"),
            )
            self._loaded = True
            log.info(f"CosyVoice 加载完成  (device={self.device})")
            return True
        except Exception as e:
            log.error(f"CosyVoice 加载失败: {e}")
            return False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ---- 参考音色设置 ----

    def set_reference_voice(self, wav_path: str, ref_text: str) -> bool:
        """
        设置自定义参考音色（零样本克隆）。

        Args:
            wav_path: 参考音频文件路径（Coco 原声，3~10秒）
            ref_text: 参考音频中说的话

        Returns:
            True=设置成功
        """
        if not os.path.exists(wav_path):
            log.error(f"参考音频不存在: {wav_path}")
            return False

        try:
            # 验证音频可读
            audio, sr = sf.read(wav_path, dtype="float32")
            duration = len(audio) / sr
            self._ref_wav_path = wav_path
            self._ref_text = ref_text
            log.info(f"参考音色已设置: {wav_path}")
            log.info(f"  参考文本: {ref_text}")
            log.info(f"  音频时长: {duration:.1f}s")
            return True
        except Exception as e:
            log.error(f"加载参考音频失败: {e}")
            return False

    def clear_reference_voice(self):
        """清除自定义参考音色，回到内置音色"""
        self._ref_wav_path = ""
        self._ref_text = ""
        log.info("自定义参考音色已清除")

    @property
    def has_reference(self) -> bool:
        return bool(self._ref_wav_path)

    # ---- 语音合成 ----

    def speak(self, text: str, voice_id: str = "中文女",
              block: bool = True) -> bool:
        """
        合成并播报。

        Args:
            text: 要说的文本
            voice_id: 内置音色 ID ("中文男"/"中文女"等)，仅当无参考音色时生效
            block: True=阻塞播完, False=后台播放

        Returns:
            True=成功
        """
        if not text or not text.strip():
            return False
        text = text.strip()

        if not self._loaded:
            if not self.load():
                return False

        if self._ref_wav_path:
            log.info(f"CosyVoice[克隆]: {text[:50]}...")
        else:
            log.info(f"CosyVoice[{voice_id}]: {text[:50]}...")

        if block:
            return self._synth_and_play(text, voice_id)
        else:
            threading.Thread(target=self._synth_and_play,
                             args=(text, voice_id), daemon=True).start()
            return True

    def _synth_and_play(self, text: str, voice_id: str) -> bool:
        """内部：合成 + 保存 + 播放"""
        try:
            audio = self.synthesize(text, voice_id)
            if audio is None or len(audio) == 0:
                return False

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name

            self._save_wav(audio, tmp_path)

            if sys.platform == "win32":
                os.system(f'start /min "" "{tmp_path}"')
            else:
                subprocess.run(["aplay", "-q", tmp_path], check=False)

            def _clean():
                time.sleep(max(len(audio) / 22050 + 2, 5))
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
            threading.Thread(target=_clean, daemon=True).start()

            return True
        except Exception as e:
            log.error(f"CosyVoice 合成失败: {e}")
            return False

    def synthesize(self, text: str, voice_id: str = "中文女") -> Optional[np.ndarray]:
        """
        合成语音，返回 numpy 音频数组（不播放）。

        Returns:
            numpy array (1D, float32, sample_rate=22050) 或 None
        """
        if not self._loaded:
            return None

        try:
            if self._ref_wav_path:
                # 零样本克隆 — 直接传文件路径
                output = self._model.inference_zero_shot(
                    text,
                    self._ref_text,
                    self._ref_wav_path,
                    stream=False,
                )
            else:
                # 内置音色
                output = self._model.inference_instruct(
                    text,
                    spk_id=voice_id,
                    prompt="",
                    stream=False,
                )

            chunks = []
            for item in output:
                speech = item["tts_speech"]
                if hasattr(speech, "cpu"):
                    speech = speech.cpu().numpy()
                chunks.append(speech.squeeze())

            if not chunks:
                return None
            return np.concatenate(chunks).astype(np.float32)
        except Exception as e:
            log.error(f"CosyVoice 推理失败: {e}")
            return None

    # ---- 批量缓存 ----

    def pregenerate(self, phrases: List[str],
                    output_dir: str = "data/audio_cache/") -> int:
        """
        预生成常用短语缓存（供树莓派端使用）。

        Args:
            phrases: 要预生成的文本列表
            output_dir: 输出 wav 文件目录

        Returns:
            成功生成的数量
        """
        if not self._loaded:
            self.load()

        os.makedirs(output_dir, exist_ok=True)
        count = 0

        for i, phrase in enumerate(phrases):
            path = os.path.join(output_dir, f"coco_{i:04d}.wav")
            if os.path.exists(path):
                count += 1
                continue

            try:
                audio = self.synthesize(phrase)
                if audio is not None and len(audio) > 0:
                    self._save_wav(audio, path)
                    count += 1
                    log.info(f"预生成 [{i+1}/{len(phrases)}]: {phrase[:30]}")
                time.sleep(0.3)
            except Exception as e:
                log.error(f"预生成失败 [{i}]: {e}")

        log.info(f"缓存完成: {count}/{len(phrases)} -> {output_dir}")
        return count

    # ---- 工具 ----

    def _save_wav(self, audio: np.ndarray, path: str, sample_rate: int = 22050):
        """保存为 WAV"""
        import wave
        audio = np.clip(audio, -1.0, 1.0)
        audio_int16 = (audio * 32767).astype(np.int16)
        with wave.open(path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_int16.tobytes())

    @staticmethod
    def list_builtin_voices() -> Dict[str, str]:
        """列出内置音色"""
        return dict(BUILTIN_VOICES)


# ============================================================
# 音频提取工具
# ============================================================

def extract_audio_clip(
    video_path: str,
    output_path: str,
    start_time: str = "0:00",
    duration: str = "5",
) -> bool:
    """
    用 ffmpeg 从视频截取音频片段。

    Args:
        video_path: 视频文件路径
        output_path: 输出 wav 路径
        start_time: 开始时间，如 "1:23"
        duration: 时长秒数，建议 3~10
    """
    try:
        subprocess.run([
            "ffmpeg", "-y",
            "-ss", start_time, "-t", duration,
            "-i", video_path,
            "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le",
            output_path,
        ], check=True, capture_output=True)
        log.info(f"音频已提取: {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        log.error(f"ffmpeg 失败: {e.stderr.decode()}")
        return False
    except FileNotFoundError:
        log.error("ffmpeg 未安装")
        return False


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                        datefmt="%H:%M:%S")

    print("=" * 60)
    print("CosyVoice 语音克隆自测")
    print("=" * 60)

    if not COSY_AVAILABLE:
        print("\nCosyVoice 未安装。")
        print("  pip install cosyvoice")
        sys.exit(0)

    # 内置音色
    print("\n内置音色:")
    for name, desc in BUILTIN_VOICES.items():
        print(f"  {name}: {desc}")

    engine = CosyVoiceTTS()
    print(f"\n加载模型 (device={engine.device})...")

    if not engine.load():
        print("模型加载失败！")
        sys.exit(1)

    # 测试内置音色
    print("\n--- 测试内置音色 ---")
    text = "你好！我是 Coco，你的智能导购小帮手～"
    print(f"合成: {text}")
    audio = engine.synthesize(text, voice_id="中文女")
    if audio is not None:
        print(f"  音频: {len(audio)} samples, {len(audio)/22050:.1f}s")
        engine.speak(text, voice_id="中文女")
        print("  播报完成")

    # 如果有参考音频，测试零样本克隆
    ref_wav = "data/voices/coco_reference.wav"
    if os.path.exists(ref_wav):
        print(f"\n--- 测试零样本克隆 ---")
        engine.set_reference_voice(ref_wav, "你好，我是Coco！")
        text2 = "可口可乐一瓶三块五，在A区一号货架"
        print(f"合成: {text2}")
        audio2 = engine.synthesize(text2)
        if audio2 is not None:
            print(f"  音频: {len(audio2)} samples, {len(audio2)/22050:.1f}s")
            engine.speak(text2)
            print("  播报完成")

    print("\n自测完成！")
