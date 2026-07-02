"""
Coco 导购机器人 — LLM 推理接口（Ollama）

封装 Ollama API 调用，支持：
- 非流式生成（用于后台）
- 流式生成（用于打字机效果）
- 连接检测
- 超时/错误处理
- 模拟模式（Ollama 不在线时用规则回复，方便开发调试）

树莓派5 推荐模型: qwen2.5:0.5b (~400MB) 或 qwen2.5:1.5b (~1GB)
"""

import logging
import time
from typing import Optional, Generator, Dict, Any

log = logging.getLogger("coco.llm")


class LLMEngine:
    """Ollama LLM 调用封装"""

    def __init__(self,
                 host: str = "http://localhost:11434",
                 model: str = "qwen2.5:0.5b",
                 timeout: float = 30.0,
                 max_tokens: int = 256):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self._available = None          # None=未检测, True=在线, False=离线
        self._last_check = 0.0

    @property
    def available(self) -> bool:
        """检查 Ollama 是否在线（带缓存，10秒内不重复检测）"""
        now = time.time()
        if self._available is not None and (now - self._last_check) < 10:
            return self._available
        self._last_check = now
        try:
            import requests
            resp = requests.get(f"{self.host}/api/tags", timeout=2.0)
            self._available = resp.status_code == 200
            if self._available:
                log.info(f"Ollama 在线，模型: {self.model}")
            else:
                log.warning("Ollama 未响应")
        except Exception:
            self._available = False
            log.warning("Ollama 不在线，使用模拟回复")
        return self._available

    def generate(self, prompt: str, system: str = "",
                 temperature: float = 0.7) -> str:
        """
        非流式生成。

        Returns:
            Ollama 生成的文本，如果不可用则返回模拟回复
        """
        if not self.available:
            return self._fallback(prompt, system)

        try:
            import requests

            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {
                    "num_predict": self.max_tokens,
                    "temperature": temperature,
                    "top_p": 0.9,
                },
            }

            resp = requests.post(
                f"{self.host}/api/generate",
                json=payload,
                timeout=self.timeout,
            )

            if resp.status_code == 200:
                result = resp.json()
                return result.get("response", "").strip()
            else:
                log.error(f"Ollama 返回 {resp.status_code}: {resp.text[:200]}")
                return self._fallback(prompt, system)

        except Exception as e:
            log.error(f"LLM 调用异常: {e}")
            return self._fallback(prompt, system)

    def generate_stream(self, prompt: str, system: str = "",
                        temperature: float = 0.7) -> Generator[str, None, None]:
        """
        流式生成（打字机效果）。

        Yields:
            每次 yield 一段生成的文本
        """
        if not self.available:
            full = self._fallback(prompt, system)
            # 模拟流式：逐字输出
            for char in full:
                yield char
                time.sleep(0.05)
            return

        try:
            import requests

            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system,
                "stream": True,
                "options": {
                    "num_predict": self.max_tokens,
                    "temperature": temperature,
                    "top_p": 0.9,
                },
            }

            with requests.post(
                f"{self.host}/api/generate",
                json=payload,
                stream=True,
                timeout=self.timeout,
            ) as resp:
                for line in resp.iter_lines():
                    if line:
                        try:
                            import json
                            chunk = json.loads(line)
                            text = chunk.get("response", "")
                            if text:
                                yield text
                        except Exception:
                            continue

        except Exception as e:
            log.error(f"流式生成异常: {e}")
            yield self._fallback(prompt, system)

    def generate_chat(self, messages: list, temperature: float = 0.7) -> str:
        """
        使用 /api/chat 格式（推荐，更好地支持 system prompt）。

        messages 格式:
            [
                {"role": "system", "content": "你是一个导购机器人"},
                {"role": "user", "content": "可乐多少钱"},
            ]
        """
        if not self.available:
            # 取最后一条 user 消息做 fallback
            user_msg = next((m["content"] for m in reversed(messages)
                            if m["role"] == "user"), "")
            system_msg = next((m["content"] for m in messages
                              if m["role"] == "system"), "")
            return self._fallback(user_msg, system_msg)

        try:
            import requests

            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "num_predict": self.max_tokens,
                    "temperature": temperature,
                    "top_p": 0.9,
                },
            }

            resp = requests.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=self.timeout,
            )

            if resp.status_code == 200:
                result = resp.json()
                return result.get("message", {}).get("content", "").strip()
            else:
                log.error(f"Ollama chat 返回 {resp.status_code}")
                return self._fallback("", "")

        except Exception as e:
            log.error(f"Chat 调用异常: {e}")
            return self._fallback("", "")

    def _fallback(self, prompt: str, system: str) -> str:
        """
        模拟回复 — 当 Ollama 不在线时的兜底方案。
        用简单的规则生成可用的回复，方便在没有 LLM 时开发调试。
        """
        # 从 prompt 中提取关键信息做简单回复
        prompt_lower = prompt.lower()

        if "查价" in prompt or "价格" in prompt:
            # 这是查价场景，fallback 返回一个模板
            return "好的，我帮你查一下。这个商品目前有货，具体价格请看一下屏幕哦～"

        if "推荐" in prompt or "recommend" in prompt:
            return "这几款都不错哦，你可以看看哪个更适合你～"

        if "谢谢" in prompt_lower or "thank" in prompt_lower:
            return "不客气！还有什么可以帮你的吗？"

        if "再见" in prompt or "拜拜" in prompt or "bye" in prompt_lower:
            return "再见！欢迎下次光临～"

        if "你好" in prompt or "hello" in prompt_lower or "hi" in prompt_lower:
            return "你好呀！我是 Coco，有什么可以帮你的吗？"

        # 默认
        return "嗯嗯，我听到了～你可以问我商品的价格、位置，或者让我推荐哦！"


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s: %(message)s")

    print("=" * 60)
    print("LLM 引擎自测")
    print("=" * 60)

    llm = LLMEngine()

    # 检测状态
    print(f"\nOllama 状态: {'在线' if llm.available else '离线（使用模拟回复）'}")

    # 测试 generate
    print("\n[非流式生成测试]")
    test_prompts = [
        ("你好", "你是一个友好的导购机器人"),
        ("可乐多少钱", "你是一个导购机器人，帮顾客查价格"),
        ("推荐点零食", "你是一个导购机器人，帮顾客推荐商品"),
    ]

    for prompt, system in test_prompts:
        print(f"\n  System: {system}")
        print(f"  User: {prompt}")
        reply = llm.generate(prompt=prompt, system=system)
        print(f"  Coco: {reply[:100]}")

    # 测试流式
    print("\n[流式生成测试]")
    print("  ", end="", flush=True)
    for chunk in llm.generate_stream(prompt="你好", system="你是一个友好的导购机器人"):
        print(chunk, end="", flush=True)
    print()

    # 测试 chat API
    print("\n[Chat API 测试]")
    reply = llm.generate_chat([
        {"role": "system", "content": "你是Coco导购机器人，说话简洁友好"},
        {"role": "user", "content": "你好，请问可乐多少钱？"},
    ])
    print(f"  Coco: {reply[:150]}")

    print(f"\n{'=' * 60}")
    print("自测完成！")
    print("=" * 60)
