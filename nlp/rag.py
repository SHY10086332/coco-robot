"""
Coco 导购机器人 — RAG 商品检索引擎

检索流程：
  用户问"可乐多少钱"
    → TF-IDF 向量化 → 余弦相似度匹配 → Top-K 商品
    → 回退关键词子串匹配
    → LLM 组织成自然语言回复

技术栈：
  - 主引擎: sklearn TfidfVectorizer（纯本地，无需网络，树莓派友好）
  - 可选升级: ChromaDB + sentence-transformers（更强的语义理解）

店铺场景约 1000-5000 个 SKU，TF-IDF 对商品名/品牌/分类的关键词匹配非常精准，
比纯 embedding 方案更适合导购物景（用户说的就是商品名/品类）。
"""

import json
import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

log = logging.getLogger("coco.rag")

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# 数据类型
# ============================================================

@dataclass
class Product:
    """商品数据结构"""
    id: str
    name: str
    aliases: List[str] = field(default_factory=list)
    category: str = ""
    price: float = 0.0
    unit: str = ""
    spec: str = ""
    brand: str = ""
    shelf: str = ""
    stock: int = 0
    description: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Product":
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in valid_fields})

    def to_search_text(self) -> str:
        """
        生成检索文本。
        TF-IDF 对重复关键词敏感，所以把名称和别名多写几遍来加权。
        """
        parts = []
        # 名称权重最高：重复3遍
        parts.extend([self.name] * 3)
        # 别名也重要：重复2遍
        for alias in self.aliases:
            parts.extend([alias] * 2)
        # 分类、品牌、描述各1遍
        parts.append(self.category)
        parts.append(self.brand)
        # 描述分词
        parts.append(self.description)
        return " ".join(parts)

    def to_display(self) -> str:
        return (f"{self.name} | {self.brand} | "
                f"¥{self.price:.2f}/{self.unit} | {self.spec} | "
                f"货架：{self.shelf} | 库存：{self.stock}")

    def to_context(self) -> str:
        """生成给 LLM 的上下文文本"""
        return (f"【{self.name}】价格：¥{self.price:.2f}/{self.unit}，"
                f"规格：{self.spec}，品牌：{self.brand}，"
                f"货架位置：{self.shelf}，库存：{self.stock}件，"
                f"简介：{self.description}")


@dataclass
class SearchResult:
    """检索结果"""
    product: Product
    score: float                      # 相似度 (0~1, 1=完全匹配)

    def __repr__(self):
        return f"SearchResult({self.product.name}, score={self.score:.3f})"


# ============================================================
# 商品数据库（JSON 读写）
# ============================================================

class ProductDB:
    """商品主数据库 — JSON + 内存多级索引"""

    def __init__(self, json_path: str = None):
        if json_path is None:
            json_path = PROJECT_ROOT / "data" / "products.json"
        self.json_path = Path(json_path)
        self._products: Dict[str, Product] = {}
        self._by_name: Dict[str, Product] = {}
        self._by_alias: Dict[str, Product] = {}
        self._by_category: Dict[str, List[Product]] = {}

    def load(self):
        """从 JSON 加载商品库"""
        if not self.json_path.exists():
            log.warning(f"商品库不存在: {self.json_path}")
            return

        with open(self.json_path, "r", encoding="utf-8") as f:
            raw_list = json.load(f)

        self._products.clear()
        self._by_name.clear()
        self._by_alias.clear()
        self._by_category.clear()

        for item in raw_list:
            prod = Product.from_dict(item)
            self._products[prod.id] = prod
            self._by_name[prod.name.lower()] = prod
            for alias in prod.aliases:
                self._by_alias[alias.lower()] = prod
            cat = prod.category
            if cat not in self._by_category:
                self._by_category[cat] = []
            self._by_category[cat].append(prod)

        log.info(f"加载了 {len(self._products)} 件商品，"
                 f"{len(self._by_category)} 个分类")

    def get_by_id(self, product_id: str) -> Optional[Product]:
        return self._products.get(product_id)

    def get_by_name(self, name: str) -> Optional[Product]:
        return self._by_name.get(name.lower())

    def get_by_alias(self, alias: str) -> Optional[Product]:
        return self._by_alias.get(alias.lower())

    def search_keyword(self, keyword: str) -> List[Product]:
        """
        关键词子串匹配 — 兜底方案。
        当 TF-IDF 检索结果不理想时用这个补充。
        """
        kw = keyword.lower()
        results = []
        for prod in self._products.values():
            searchable = (
                prod.name.lower() + " " +
                " ".join(a.lower() for a in prod.aliases) + " " +
                prod.brand.lower() + " " +
                prod.category.lower() + " " +
                prod.description.lower()
            )
            if kw in searchable:
                results.append(prod)
        return results

    def get_by_category(self, category: str) -> List[Product]:
        """按分类获取"""
        return self._by_category.get(category.strip(), [])

    def get_all(self) -> List[Product]:
        return list(self._products.values())

    def get_categories(self) -> List[str]:
        return sorted(self._by_category.keys())

    @property
    def count(self) -> int:
        return len(self._products)


# ============================================================
# TF-IDF 向量检索引擎（纯本地，零网络依赖）
# ============================================================

class TFIDFStore:
    """
    基于 sklearn TfidfVectorizer 的商品检索引擎。

    为什么选择 TF-IDF 而不是 embedding：
    1. 导购场景的用户查询高度关键词化（"可乐"、"洗发水"、"牛奶"）
    2. TF-IDF 对商品名/品牌的精确匹配比通用 embedding 更准
    3. 零网络依赖，加载速度毫秒级
    4. 树莓派上轻松跑，5000个SKU内存不到10MB
    5. 中文分词：用 char 级别 n-gram (1~2字符)，避免依赖 jieba
    """

    def __init__(self):
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._doc_matrix: Optional[np.ndarray] = None   # N×V 文档-词项矩阵
        self._products: List[Product] = []               # 与矩阵行对应的商品
        self._id_to_idx: Dict[str, int] = {}             # product_id → 矩阵行号

    def build(self, products: List[Product]):
        """构建 TF-IDF 矩阵"""
        if not products:
            log.warning("商品列表为空")
            return

        self._products = list(products)
        self._id_to_idx = {p.id: i for i, p in enumerate(self._products)}

        docs = [p.to_search_text() for p in self._products]

        # char 级别 n-gram (1~2字符) + 英文word级别
        # 这样"可乐"会被切成: "可", "乐", "可乐"
        # 不需要分词器，中文英文都能处理
        self._vectorizer = TfidfVectorizer(
            analyzer="char_wb",          # char within word boundaries
            ngram_range=(1, 2),          # 单字+双字n-gram
            max_features=5000,           # 最多5000个特征（对5000SKU足够）
            sublinear_tf=True,           # tf = 1 + log(tf)，抑制高频词
            norm="l2",                   # L2归一化
        )

        log.info(f"构建 TF-IDF 矩阵: {len(docs)} 文档...")
        self._doc_matrix = self._vectorizer.fit_transform(docs)
        log.info(f"特征维度: {self._doc_matrix.shape[1]}")

    def search(self, query: str, top_k: int = 5,
               threshold: float = 0.05) -> List[Tuple[str, float]]:
        """
        TF-IDF 余弦相似度检索。

        Args:
            query: 用户自然语言查询
            top_k: 返回数
            threshold: 余弦相似度阈值（TF-IDF 的 cosine 值通常比 embedding 小）

        Returns:
            [(product_id, similarity_score), ...] 降序
        """
        if self._vectorizer is None or self._doc_matrix is None:
            raise RuntimeError("TF-IDF 未构建，请先调用 build()")

        # 查询向量化
        q_vec = self._vectorizer.transform([query])

        # 余弦相似度（稀疏矩阵乘法）
        sims = cosine_similarity(q_vec, self._doc_matrix)[0]  # shape: (N,)

        # 取 Top-K
        # 用 argpartition 比 argsort 快（不需要全排序）
        if top_k >= len(sims):
            top_indices = np.argsort(sims)[::-1]
        else:
            top_indices = np.argpartition(sims, -top_k)[-top_k:]
            top_indices = top_indices[np.argsort(sims[top_indices])[::-1]]

        hits = []
        for idx in top_indices:
            score = float(sims[idx])
            if score >= threshold:
                prod = self._products[idx]
                hits.append((prod.id, score))

        return hits


# ============================================================
# RAG 引擎 — 对外统一接口
# ============================================================

class RAGEngine:
    """
    商品 RAG 检索引擎。

    两阶段检索：
    1. TF-IDF 语义检索（主引擎）
    2. 子串关键词匹配（兜底）

    用法:
        engine = RAGEngine()
        engine.initialize()
        results = engine.query("可乐多少钱")
        for r in results:
            print(r.product.name, r.product.price)
    """

    def __init__(self, products_json: str = None):
        self.product_db = ProductDB(products_json)
        self.tfidf_store = TFIDFStore()
        self._initialized = False

    def initialize(self, force_rebuild: bool = False):
        """加载商品库并构建 TF-IDF 矩阵"""
        self.product_db.load()
        if self.product_db.count == 0:
            log.warning("商品库为空！请检查 data/products.json")
            return
        self.tfidf_store.build(self.product_db.get_all())
        self._initialized = True
        log.info(f"RAG 引擎就绪: {self.product_db.count} 件商品, "
                 f"{len(self.product_db.get_categories())} 个分类")

    def query(self, text: str, top_k: int = 5,
              threshold: float = 0.03) -> List[SearchResult]:
        """
        查询商品。

        Args:
            text: 用户查询，如"可乐多少钱"、"有没有去屑洗发水"
            top_k: 返回 Top-K 个结果
            threshold: 相似度阈值 (0~1)

        Returns:
            SearchResult 列表，按相似度降序
        """
        if not self._initialized:
            raise RuntimeError("RAGEngine 未初始化，请先调用 initialize()")

        results = []

        # 先去掉口语化干扰词，提取关键词部分
        cleaned = self._clean_query(text)

        # 阶段1: TF-IDF 检索
        hits = self.tfidf_store.search(cleaned, top_k=top_k, threshold=threshold)
        for pid, score in hits:
            prod = self.product_db.get_by_id(pid)
            if prod:
                results.append(SearchResult(product=prod, score=score))

        # 阶段2: 如果 TF-IDF 结果不够，用关键词子串匹配补充
        if len(results) < min(3, top_k):
            keyword_results = self.product_db.search_keyword(cleaned)
            existing_ids = {r.product.id for r in results}
            for prod in keyword_results:
                if prod.id not in existing_ids:
                    results.append(SearchResult(product=prod, score=0.3))
                    if len(results) >= top_k:
                        break

        return results

    def _clean_query(self, text: str) -> str:
        """
        清洗用户查询：去掉口语化噪音词，保留关键词。

        比如 "可乐多少钱" → "可乐"
             "有没有去屑的洗发水" → "去屑 洗发水"
             "我想买一瓶牛奶" → "牛奶"
        """
        # 疑问/口语噪声词
        noise_words = [
            "多少钱", "有没有", "我想买", "我要", "帮我", "请问",
            "一下", "一个", "一瓶", "一袋", "一盒", "一罐",
            "在哪里", "在哪儿", "哪儿有", "哪个好", "推荐",
            "来点", "给我", "来一", "拿一", "买点",
        ]
        result = text
        for w in noise_words:
            result = result.replace(w, " ")
        # 多余空格
        result = re.sub(r"\s+", " ", result).strip()
        return result if result else text

    def search_by_category(self, category: str) -> List[Product]:
        """按分类筛选"""
        return self.product_db.get_by_category(category)

    def search_by_price_range(self, min_price: float, max_price: float
                              ) -> List[Product]:
        """按价格区间筛选"""
        return [p for p in self.product_db.get_all()
                if min_price <= p.price <= max_price]

    def get_categories(self) -> List[str]:
        """列出所有商品分类"""
        return self.product_db.get_categories()

    @property
    def total_products(self) -> int:
        return self.product_db.count


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    import time
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                        datefmt="%H:%M:%S")

    print("=" * 60)
    print("RAG 商品检索引擎 — 自测 (TF-IDF)")
    print("=" * 60)

    engine = RAGEngine()
    t0 = time.time()
    engine.initialize()
    print(f"初始化耗时: {time.time() - t0:.3f}s\n")

    test_queries = [
        ("可乐多少钱", "可口可乐"),
        ("有没有去屑的洗发水", "海飞丝去屑洗发露"),
        ("给我推荐点零食", "零食类"),
        ("吃火锅要蘸料", "老干妈风味豆豉"),
        ("我想买牛奶", "牛奶类"),
        ("牙膏", "牙膏类"),
        ("泡面在哪里", "康师傅红烧牛肉面"),
        ("啤酒多少钱", "青岛啤酒经典"),
        ("小孩子喜欢喝的", "旺仔牛奶"),
        ("买点坚果", "三只松鼠每日坚果"),
        ("夏天用什么驱蚊", "六神花露水"),
    ]

    correct = 0
    total = len(test_queries)

    for query, expected in test_queries:
        print(f"\n{'─' * 50}")
        print(f"查询: \"{query}\"  (预期相关: {expected})")
        results = engine.query(query, top_k=3)

        if not results:
            print("  ❌ 未找到匹配商品")
        else:
            top_hit = results[0].product.name
            for i, r in enumerate(results):
                flag = "⭐" if r.score > 0.3 else "  "
                print(f"  {flag} #{i+1} [相似度 {r.score:.3f}] {r.product.to_display()}")
            # 简单判断：预期商品是否在 Top-3 中
            found = any(expected in r.product.name or expected in r.product.category
                       for r in results)
            if found:
                correct += 1
                print(f"  ✅ 命中")
            else:
                print(f"  ⚠️ 预期 '{expected}' 未在 Top-3 中")

    print(f"\n{'=' * 60}")
    print(f"检索准确率: {correct}/{total} = {correct/total:.0%}")

    # 分类筛选
    print(f"\n分类列表: {', '.join(engine.get_categories())}")
    for cat in ["饮料", "零食", "日用品", "冷冻食品"]:
        items = engine.search_by_category(cat)
        names = [p.name for p in items]
        print(f"  {cat} ({len(items)}件): {', '.join(names)}")

    # 价格筛选
    print(f"\n价格区间 ¥5-¥15:")
    for p in engine.search_by_price_range(5.0, 15.0):
        print(f"  {p.name} ¥{p.price:.2f}")

    print(f"\n总商品数: {engine.total_products}")
    print("自测完成！")
