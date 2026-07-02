"""
Coco 导购机器人 — 商品管理工具

店长可以用这个工具增删改查商品，修改立刻生效到 products.json，
下次 RAG 引擎初始化时自动重建索引。

用法：
    python -m nlp.product_manager                  # 交互模式
    python -m nlp.product_manager add              # 添加商品
    python -m nlp.product_manager update P001      # 修改商品
    python -m nlp.product_manager list             # 列出所有
    python -m nlp.product_manager delete P020      # 删除商品
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRODUCTS_FILE = PROJECT_ROOT / "data" / "products.json"


def _load() -> List[dict]:
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(products: List[dict]):
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


def _next_id(products: List[dict]) -> str:
    if not products:
        return "P001"
    max_num = max(int(p["id"][1:]) for p in products)
    return f"P{max_num + 1:03d}"


def list_products(products: List[dict] = None):
    """列出所有商品"""
    if products is None:
        products = _load()
    print(f"\n共 {len(products)} 件商品:\n")
    print(f"{'ID':6s} {'名称':20s} {'分类':8s} {'价格':>8s} {'库存':>6s} {'货架':10s}")
    print("-" * 70)
    for p in products:
        price_str = f"¥{p['price']:.2f}"
        print(f"{p['id']:6s} {p['name']:20s} {p['category']:8s} "
              f"{price_str:>8s} {p['stock']:>5}{p['unit']:2s} {p['shelf']:10s}")


def add_product():
    """交互式添加商品"""
    products = _load()

    print("\n=== 添加商品 ===\n")
    name = input("商品名称: ").strip()
    if not name:
        print("已取消")
        return

    # 别名
    aliases_raw = input('别名（逗号分隔，如 可乐,coke）: ').strip()
    aliases = [a.strip() for a in aliases_raw.split(",") if a.strip()] if aliases_raw else []

    category = input("分类（如 饮料/零食/日用品）: ").strip()
    price_str = input("价格（元）: ").strip()
    unit = input("单位（瓶/袋/盒/罐）: ").strip()
    spec = input("规格（如 500ml/105g）: ").strip()
    brand = input("品牌: ").strip()
    shelf = input("货架号（如 A-01-03）: ").strip()
    stock_str = input("库存数量: ").strip()
    description = input("描述: ").strip()

    try:
        price = float(price_str)
        stock = int(stock_str)
    except ValueError:
        print("价格或库存格式错误，已取消")
        return

    new_product = {
        "id": _next_id(products),
        "name": name,
        "aliases": aliases,
        "category": category,
        "price": price,
        "unit": unit,
        "spec": spec,
        "brand": brand,
        "shelf": shelf,
        "stock": stock,
        "description": description,
    }

    products.append(new_product)
    _save(products)
    print(f"\n✅ 已添加: [{new_product['id']}] {name} ¥{price:.2f}/{unit}")
    print(f"   下次运行 --search 时将自动包含此商品。")


def update_product(product_id: str = None):
    """修改商品信息"""
    products = _load()

    if product_id is None:
        list_products(products)
        product_id = input("\n输入要修改的商品ID: ").strip().upper()

    target = None
    for p in products:
        if p["id"] == product_id:
            target = p
            break

    if target is None:
        print(f"未找到商品: {product_id}")
        return

    print(f"\n=== 修改商品: [{target['id']}] {target['name']} ===\n")
    print("（直接回车保持不变）\n")

    field_labels = {
        "name": "商品名称",
        "category": "分类",
        "price": "价格",
        "unit": "单位",
        "spec": "规格",
        "brand": "品牌",
        "shelf": "货架号",
        "stock": "库存",
        "description": "描述",
    }

    for field, label in field_labels.items():
        old_value = target.get(field, "")
        if field == "aliases":
            old_str = ", ".join(target.get("aliases", []))
            new_val = input(f"{label} [{old_str}]: ").strip()
            if new_val:
                target["aliases"] = [a.strip() for a in new_val.split(",") if a.strip()]
        elif field in ("price",):
            new_val = input(f"{label} [¥{old_value:.2f}]: ").strip()
            if new_val:
                try:
                    target[field] = float(new_val)
                except ValueError:
                    print(f"  ⚠ 价格格式错误，保持原值")
        elif field in ("stock",):
            new_val = input(f"{label} [{old_value}]: ").strip()
            if new_val:
                try:
                    target[field] = int(new_val)
                except ValueError:
                    print(f"  ⚠ 库存格式错误，保持原值")
        else:
            new_val = input(f"{label} [{old_value}]: ").strip()
            if new_val:
                target[field] = new_val

    _save(products)
    print(f"\n✅ 已更新: [{target['id']}] {target['name']}")


def delete_product(product_id: str = None):
    """删除商品"""
    products = _load()

    if product_id is None:
        list_products(products)
        product_id = input("\n输入要删除的商品ID: ").strip().upper()

    target = None
    for i, p in enumerate(products):
        if p["id"] == product_id:
            target = (i, p)
            break

    if target is None:
        print(f"未找到商品: {product_id}")
        return

    idx, prod = target
    confirm = input(f"\n确认删除 [{prod['id']}] {prod['name']} ¥{prod['price']:.2f}? "
                    f"(输入 yes 确认): ").strip()
    if confirm.lower() != "yes":
        print("已取消")
        return

    products.pop(idx)
    _save(products)
    print(f"✅ 已删除: [{prod['id']}] {prod['name']}")


def search_product():
    """按名称/分类搜索商品"""
    keyword = input("\n搜索关键词: ").strip()
    if not keyword:
        return

    products = _load()
    kw = keyword.lower()
    results = []
    for p in products:
        if (kw in p["name"].lower() or
            kw in p["category"].lower() or
            kw in p["brand"].lower() or
            any(kw in a.lower() for a in p.get("aliases", []))):
            results.append(p)

    if not results:
        print(f"未找到匹配 '{keyword}' 的商品")
    else:
        list_products(results)


def interactive_mode():
    """交互式管理菜单"""
    while True:
        print("\n" + "=" * 50)
        print("  Coco 商品管理")
        print("=" * 50)
        print("  1. 列出所有商品")
        print("  2. 搜索商品")
        print("  3. 添加商品")
        print("  4. 修改商品")
        print("  5. 删除商品")
        print("  0. 退出")
        print("=" * 50)

        choice = input("\n选择: ").strip()

        if choice == "1":
            list_products()
        elif choice == "2":
            search_product()
        elif choice == "3":
            add_product()
        elif choice == "4":
            update_product()
        elif choice == "5":
            delete_product()
        elif choice == "0":
            print("再见！")
            break
        else:
            print("无效选择，请重试")


# ============================================================
# CLI 入口
# ============================================================

def main():
    args = sys.argv[1:]

    if not args:
        interactive_mode()
    elif args[0] == "list":
        list_products()
    elif args[0] == "add":
        add_product()
    elif args[0] == "update":
        update_product(args[1] if len(args) > 1 else None)
    elif args[0] == "delete":
        delete_product(args[1] if len(args) > 1 else None)
    elif args[0] == "search":
        search_product()
    else:
        print("用法: python -m nlp.product_manager [list|add|update|delete|search]")
        print("      python -m nlp.product_manager           # 交互模式")


if __name__ == "__main__":
    main()
