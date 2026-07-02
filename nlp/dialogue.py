"""
Coco 导购机器人 — 对话管理器

串联完整对话链路：
  用户语音 → 意图解析 → RAG检索 → LLM生成 → TTS播报 + 屏幕显示

这是 Coco 最核心的业务逻辑模块。

用法:
    dm = DialogueManager()
    dm.initialize()                         # 加载商品库+初始化各组件
    reply = dm.chat("可乐多少钱")            # 一次对话
    # reply 包含: text(播报文本), intent(意图), products(检索结果)
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from .rag import RAGEngine, SearchResult
from .intent import IntentParser, IntentType
from .prompt import PRICING_PROMPT, RECOMMEND_PROMPT, CHITCHAT_PROMPT, PAYMENT_PROMPT
from .llm import LLMEngine

log = logging.getLogger("coco.dialogue")


# ============================================================
# 数据类型
# ============================================================

@dataclass
class DialogueReply:
    """一次对话的完整响应"""
    text: str = ""                        # 播报文本
    intent: str = ""                      # 解析出的意图
    products: List[SearchResult] = field(default_factory=list)  # 检索结果
    display_text: str = ""                # 屏幕显示文本（可以比播报更长）
    is_fallback: bool = False             # 是否是兜底回复


# ============================================================
# 对话管理器
# ============================================================

class DialogueManager:
    """
    对话管理器 — 导购机器人的"大脑"。

    处理流程:
    1. IntentParser 解析意图
    2. 根据意图决定下一步：
       - check_price / find_location / recommend → RAG 检索 + LLM 生成
       - greet / thanks / goodbye → 直接模板回复（不需要 LLM）
       - pay → 切换支付状态
       - dialog → LLM 闲聊（不需要 RAG）
    """

    def __init__(self,
                 products_json: str = None,
                 ollama_host: str = "http://localhost:11434",
                 ollama_model: str = "qwen2.5:0.5b"):
        self.rag = RAGEngine(products_json)
        self.intent_parser = IntentParser()
        self.llm = LLMEngine(host=ollama_host, model=ollama_model)
        self._initialized = False

    def initialize(self):
        """初始化：加载商品库 + 构建 TF-IDF"""
        self.rag.initialize()
        self._initialized = True
        log.info(f"对话管理器就绪: {self.rag.total_products} 件商品, "
                 f"Ollama={'在线' if self.llm.available else '离线'}")

    # ---- 主入口 ----

    def chat(self, user_text: str) -> DialogueReply:
        """
        处理一次用户对话。

        Args:
            user_text: 用户语音识别后的文本

        Returns:
            DialogueReply: 完整的响应（播报文本 + 检索结果 + 显示文本）
        """
        if not self._initialized:
            self.initialize()

        user_text = user_text.strip()
        log.info(f"用户: {user_text}")

        # Step 1: 意图解析
        intent_result = self.intent_parser.parse(user_text)
        intent = intent_result["intent"]
        log.info(f"意图: {intent}")

        # Step 2: 根据意图分发
        if intent == IntentType.CHECK_PRICE.value:
            return self._handle_check_price(user_text)
        elif intent == IntentType.FIND_LOCATION.value:
            return self._handle_find_location(user_text)
        elif intent == IntentType.RECOMMEND.value:
            return self._handle_recommend(user_text)
        elif intent == IntentType.PAY.value:
            return self._handle_pay(user_text)
        elif intent == IntentType.GREET.value:
            return self._handle_greet()
        elif intent == IntentType.THANKS.value:
            return self._handle_thanks()
        elif intent == IntentType.GOODBYE.value:
            return self._handle_goodbye()
        else:
            return self._handle_dialog(user_text)

    # ---- 意图处理函数 ----

    def _handle_check_price(self, user_text: str) -> DialogueReply:
        """查价：RAG检索 → LLM生成"""
        results = self.rag.query(user_text, top_k=3)

        if not results:
            return DialogueReply(
                text="抱歉，我没有找到这个商品。你可以换个名字试试，或者问问我在哪个区域哦～",
                intent=IntentType.CHECK_PRICE.value,
                display_text="未找到匹配商品",
            )

        # 拼接商品信息给 LLM
        context_parts = []
        for i, r in enumerate(results[:2]):  # 最多给2个，避免prompt太长
            p = r.product
            context_parts.append(
                f"{i+1}. {p.name} | 品牌:{p.brand} | "
                f"价格:¥{p.price:.2f}/{p.unit} | 规格:{p.spec} | "
                f"货架:{p.shelf} | 库存:{p.stock}{p.unit} | "
                f"简介:{p.description}"
            )
        context = "\n".join(context_parts)

        # LLM 生成自然语言
        system = PRICING_PROMPT.replace("{context}", context)
        llm_reply = self.llm.generate(prompt=user_text, system=system)

        return DialogueReply(
            text=llm_reply,
            intent=IntentType.CHECK_PRICE.value,
            products=results,
            display_text=self._format_display(results),
        )

    def _handle_find_location(self, user_text: str) -> DialogueReply:
        """找位置：RAG检索 → 告知货架"""
        results = self.rag.query(user_text, top_k=3)

        if not results:
            return DialogueReply(
                text="抱歉，我不太确定这个商品在哪，你可以去服务台问一下哦～",
                intent=IntentType.FIND_LOCATION.value,
            )

        # 找到位置直接回复，不需要 LLM（更快）
        top = results[0]
        p = top.product

        # 制造导航指引
        section = p.shelf.split("-")[0] if "-" in p.shelf else p.shelf
        text = f"{p.name}在{section}区，货架号{p.shelf}，现在还有{p.stock}{p.unit}库存。需要我带你去吗？"

        return DialogueReply(
            text=text,
            intent=IntentType.FIND_LOCATION.value,
            products=results,
            display_text=self._format_display(results),
        )

    def _handle_recommend(self, user_text: str) -> DialogueReply:
        """推荐：RAG检索 → LLM推荐"""
        results = self.rag.query(user_text, top_k=5, threshold=0.03)

        if len(results) < 2:
            # 匹配太少，放宽阈值
            results = self.rag.query(user_text, top_k=5, threshold=0.01)

        if not results:
            return DialogueReply(
                text="嗯...让我想想。你可以告诉我你喜欢什么口味或者类型，我帮你推荐！",
                intent=IntentType.RECOMMEND.value,
            )

        # 拼接
        context_parts = []
        for i, r in enumerate(results[:4]):
            p = r.product
            context_parts.append(
                f"{i+1}. {p.name} ¥{p.price:.2f}/{p.unit} | "
                f"{p.spec} | {p.brand} | {p.description}"
            )
        context = "\n".join(context_parts)

        system = RECOMMEND_PROMPT.replace("{context}", context)
        llm_reply = self.llm.generate(prompt=user_text, system=system)

        return DialogueReply(
            text=llm_reply,
            intent=IntentType.RECOMMEND.value,
            products=results,
            display_text=self._format_display(results),
        )

    def _handle_pay(self, user_text: str) -> DialogueReply:
        """付款：确认订单 → 显示收款码"""
        # 简单场景：没有确切订单信息，引导用户
        return DialogueReply(
            text="好的，请看屏幕上的收款码。扫码支付后我会语音提示～",
            intent=IntentType.PAY.value,
            display_text="💰 请扫码支付\n\n收款码显示区域",
        )

    def _handle_greet(self) -> DialogueReply:
        """问候"""
        return DialogueReply(
            text="你好呀！我是 Coco，今天有什么可以帮你的吗？你可以问我商品价格、位置，或者让我推荐哦～",
            intent=IntentType.GREET.value,
        )

    def _handle_thanks(self) -> DialogueReply:
        """道谢"""
        return DialogueReply(
            text="不客气！还有什么需要随时叫我～",
            intent=IntentType.THANKS.value,
        )

    def _handle_goodbye(self) -> DialogueReply:
        """告别"""
        return DialogueReply(
            text="再见！欢迎下次光临，记得找我 Coco 哦～",
            intent=IntentType.GOODBYE.value,
        )

    def _handle_dialog(self, user_text: str) -> DialogueReply:
        """闲聊"""
        llm_reply = self.llm.generate(
            prompt=user_text,
            system=CHITCHAT_PROMPT,
        )
        return DialogueReply(
            text=llm_reply,
            intent=IntentType.DIALOG.value,
        )

    # ---- 辅助 ----

    def _format_display(self, results: List[SearchResult]) -> str:
        """格式化屏幕显示文本"""
        if not results:
            return ""
        lines = []
        for i, r in enumerate(results[:3]):
            p = r.product
            lines.append(f"{i+1}. {p.name}")
            lines.append(f"   💰 ¥{p.price:.2f}/{p.unit}  📍 {p.shelf}  📦 {p.stock}{p.unit}")
            lines.append("")
        return "\n".join(lines)


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                        datefmt="%H:%M:%S")

    dm = DialogueManager()
    dm.initialize()

    test_queries = [
        "你好",
        "可乐多少钱",
        "有没有去屑的洗发水",
        "推荐点零食",
        "啤酒在哪",
        "今天天气真好",
        "我要买单",
        "谢谢",
        "拜拜",
    ]

    print("=" * 60)
    print("对话管理器 — 完整链路自测")
    print(f"Ollama: {'在线' if dm.llm.available else '离线(fallback)'}")
    print("=" * 60)

    for q in test_queries:
        print(f"\n{'─' * 50}")
        print(f"👤 用户: {q}")
        reply = dm.chat(q)
        print(f"🎯 意图: {reply.intent}")
        print(f"🤖 Coco: {reply.text}")
        if reply.products:
            top = reply.products[0]
            print(f"📦 命中商品: {top.product.name} (分数:{top.score:.3f})")
        if reply.display_text:
            print(f"🖥 屏幕:\n{reply.display_text}")

    print(f"\n{'=' * 60}")
    print("自测完成！")
