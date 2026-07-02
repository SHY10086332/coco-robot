"""
Coco 导购机器人 — 意图解析器

支持两种模式：
1. 关键词规则（默认）：毫秒级，离线，适合树莓派
2. LLM 分类（可选）：更准确但需要 Ollama 在线

意图类型：
- check_price: 查价（"可乐多少钱"）
- find_location: 找位置（"洗发水在哪"）
- recommend: 推荐（"有什么好吃的"）
- pay: 付款（"我要买单"）
- greet: 问候（"你好"）
- thanks: 道谢（"谢谢"）
- goodbye: 告别（"拜拜"）
- dialog: 闲聊/其他
"""

import re
import logging
from typing import Dict, Any
from enum import Enum

log = logging.getLogger("coco.intent")


class IntentType(Enum):
    CHECK_PRICE = "check_price"
    FIND_LOCATION = "find_location"
    RECOMMEND = "recommend"
    PAY = "pay"
    GREET = "greet"
    THANKS = "thanks"
    GOODBYE = "goodbye"
    DIALOG = "dialog"


# ============================================================
# 关键词规则引擎（默认）
# ============================================================

# 每个意图的关键词/正则
INTENT_RULES = [
    # (意图类型, 权重, 关键词列表)
    # 优先级：先匹配到的优先，pay > check_price > find_location > recommend > greet > thanks > goodbye > dialog

    (IntentType.PAY, [
        r"(我要|我想|帮我|扫码|微信|支付宝).*(买单|结账|付款|支付|扫码)",
        r"(买单|结账|付款|支付)",
        r"多少钱.*(总共|一共)",
        r"就(要|买)这个",
    ]),

    (IntentType.CHECK_PRICE, [
        r"(多少钱|怎么卖|什么价|价格|价钱|贵不贵|便宜)",
        r"(这个|那个|它).*(多少钱|价格|怎么卖)",
        r"(多少|几)钱",
        r"^(有没有|有没|还有).{0,10}(的|卖|买)?$",      # "有没有可乐" "有没有去屑的洗发水"
    ]),

    (IntentType.FIND_LOCATION, [
        r"(在哪|在哪儿|哪里|什么地方|位置|货架|几号)",
        r"怎么(走|去)",
        r"(有没有|有没|还有).{0,5}(卖|货)",
    ]),

    (IntentType.RECOMMEND, [
        r"(推荐|介绍|有什么|哪些|哪款|哪个|哪种).*(好|不错|值得|便宜|划算)",
        r"(推荐|介绍|有什么|哪些|哪款|哪个|哪种)",
        r"(好|不好).*(吃|喝|用)",
        r"(想|要).*(买|吃|喝)",
    ]),

    (IntentType.GREET, [
        r"^(你好|hi|hello|嗨|嘿|在吗|在不在)[!！。.]*$",
        r"^(早上好|下午好|晚上好|早啊|早呀)[!！。.]*$",
    ]),

    (IntentType.THANKS, [
        r"^(谢谢|多谢|感谢|谢了|3q|thx|thanks|thank|thank you)[!！。.]*$",
    ]),

    (IntentType.GOODBYE, [
        r"^(拜拜|再见|bye|88|回头见|下次见|走了)[!！。.]*$",
        r"(我要|我).*(走|离开|回去)了",
    ]),
]


class RuleIntentClassifier:
    """基于正则规则的意图分类器"""

    def classify(self, text: str) -> IntentType:
        """
        分类用户输入。

        按优先级从高到低匹配，匹配到即返回。
        """
        text = text.strip()

        for intent_type, patterns in INTENT_RULES:
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    log.debug(f"规则匹配: '{text}' → {intent_type.value} (pattern: {pattern})")
                    return intent_type

        # 兜底：如果有问号，可能是查价/询问
        if "?" in text or "？" in text:
            return IntentType.CHECK_PRICE

        return IntentType.DIALOG


# ============================================================
# LLM 意图分类器（可选，更准确）
# ============================================================

class LLMIntentClassifier:
    """用 LLM 做意图分类，更准确但依赖 Ollama"""

    def __init__(self, ollama_host: str = "http://localhost:11434",
                 model: str = "qwen2.5:0.5b"):
        self.host = ollama_host
        self.model = model

    def classify(self, text: str) -> IntentType:
        """用 LLM 做意图分类"""
        from .prompt import INTENT_CLASSIFY_PROMPT

        prompt = INTENT_CLASSIFY_PROMPT.replace("{query}", text)

        try:
            import requests
            resp = requests.post(
                f"{self.host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 10, "temperature": 0.0},
                },
                timeout=5.0,
            )
            if resp.status_code == 200:
                result = resp.json().get("response", "").strip().lower()
                # 解析 LLM 输出
                for it in IntentType:
                    if it.value in result:
                        return it
        except Exception as e:
            log.warning(f"LLM 意图分类失败: {e}，回退到规则引擎")

        # 回退
        return RuleIntentClassifier().classify(text)


# ============================================================
# 统一接口
# ============================================================

class IntentParser:
    """
    意图解析器。

    默认使用规则引擎（毫秒级、离线）。
    启用了 Ollama 且在线时自动升级为 LLM 分类。
    """

    def __init__(self, use_llm: bool = False,
                 ollama_host: str = "http://localhost:11434",
                 ollama_model: str = "qwen2.5:0.5b"):
        self.rule_classifier = RuleIntentClassifier()
        self.llm_classifier = None
        self.use_llm = use_llm

        if use_llm:
            self.llm_classifier = LLMIntentClassifier(ollama_host, ollama_model)

    def parse(self, text: str) -> Dict[str, Any]:
        """
        解析用户输入，返回结构化意图。

        Returns:
            {
                "intent": "check_price",
                "query": "可乐多少钱",
                "confidence": "rule" | "llm",
            }
        """
        if self.llm_classifier:
            intent = self.llm_classifier.classify(text)
            confidence = "llm"
        else:
            intent = self.rule_classifier.classify(text)
            confidence = "rule"

        return {
            "intent": intent.value,
            "query": text,
            "confidence": confidence,
        }

    def parse_intent(self, text: str) -> IntentType:
        """快捷方法：直接返回 IntentType"""
        if self.llm_classifier:
            return self.llm_classifier.classify(text)
        return self.rule_classifier.classify(text)


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format="%(levelname)s: %(message)s")

    parser = IntentParser()

    test_cases = [
        ("可乐多少钱", IntentType.CHECK_PRICE),
        ("这个怎么卖", IntentType.CHECK_PRICE),
        ("海飞丝什么价格", IntentType.CHECK_PRICE),
        ("便宜一点的牛奶", IntentType.CHECK_PRICE),
        ("洗发水在哪个货架", IntentType.FIND_LOCATION),
        ("啤酒在哪里", IntentType.FIND_LOCATION),
        ("洗手间怎么走", IntentType.FIND_LOCATION),
        ("推荐点零食", IntentType.RECOMMEND),
        ("有什么好吃的泡面", IntentType.RECOMMEND),
        ("哪个牌子的牛奶好", IntentType.RECOMMEND),
        ("我想买点水果", IntentType.RECOMMEND),
        ("我要买单", IntentType.PAY),
        ("扫码付款", IntentType.PAY),
        ("你好", IntentType.GREET),
        ("早上好", IntentType.GREET),
        ("谢谢", IntentType.THANKS),
        ("拜拜", IntentType.GOODBYE),
        ("今天天气不错", IntentType.DIALOG),
        ("你多大了", IntentType.DIALOG),
    ]

    print("=" * 60)
    print("意图解析器自测（规则引擎）")
    print("=" * 60)

    correct = 0
    for text, expected in test_cases:
        result = parser.parse(text)
        ok = result["intent"] == expected.value
        if ok:
            correct += 1
        flag = "✅" if ok else "❌"
        print(f"{flag} \"{text}\" → {result['intent']} (预期: {expected.value})")

    print(f"\n准确率: {correct}/{len(test_cases)} = {correct/len(test_cases):.0%}")
