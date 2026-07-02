"""
Coco 导购机器人 — Web 商品管理后台

基于 Gradio，店长用手机/电脑浏览器即可管理商品。
在树莓派上运行后，局域网内任何设备访问 http://<树莓派IP>:7860

用法:
    python -m nlp.web_admin                  # 启动Web后台
    python main.py --web                     # 也可以从main.py启动
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional

import gradio as gr

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRODUCTS_FILE = PROJECT_ROOT / "data" / "products.json"


# ============================================================
# 数据操作层
# ============================================================

def _load() -> List[dict]:
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(products: List[dict]):
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


def _next_id(products: List[dict]) -> str:
    max_num = max((int(p["id"][1:]) for p in products), default=0)
    return f"P{max_num + 1:03d}"


# ============================================================
# 业务逻辑（供 Gradio 回调）
# ============================================================

def refresh_product_list(search: str = "", category: str = "全部"):
    """刷新商品列表表格"""
    products = _load()
    rows = []
    for p in products:
        if search:
            kw = search.lower()
            if not (kw in p["name"].lower() or
                    kw in p.get("brand", "").lower() or
                    any(kw in a.lower() for a in p.get("aliases", []))):
                continue
        if category != "全部" and p.get("category", "") != category:
            continue

        aliases = ", ".join(p.get("aliases", []))
        rows.append([
            p["id"],
            p["name"],
            aliases,
            p.get("category", ""),
            f"¥{p['price']:.2f}",
            f"{p['stock']}{p.get('unit', '')}",
            p.get("shelf", ""),
            p.get("description", "")[:50],
        ])
    return rows if rows else [["", "", "", "", "", "", "", ""]]


def get_categories():
    """获取所有分类"""
    products = _load()
    cats = sorted(set(p.get("category", "未分类") for p in products))
    return ["全部"] + cats


def get_product_ids():
    """获取所有商品ID列表"""
    products = _load()
    return [f"{p['id']} - {p['name']}" for p in products]


def load_product_for_edit(selection: str):
    """选中商品 → 填充编辑表单"""
    if not selection:
        return "", "", "", "", "", "", "", "", ""
    pid = selection.split(" - ")[0]
    products = _load()
    for p in products:
        if p["id"] == pid:
            return (
                p["id"],
                p["name"],
                ", ".join(p.get("aliases", [])),
                p.get("category", ""),
                str(p["price"]),
                p.get("unit", ""),
                p.get("spec", ""),
                p.get("brand", ""),
                p.get("shelf", ""),
                str(p["stock"]),
                p.get("description", ""),
            )
    return "", "", "", "", "", "", "", "", "", "", ""


def add_product(name, aliases_str, category, price_str, unit, spec,
                brand, shelf, stock_str, description):
    """添加商品"""
    if not name.strip():
        return "❌ 商品名称不能为空", *refresh_product_list()

    try:
        price = float(price_str) if price_str else 0
        stock = int(stock_str) if stock_str else 0
    except ValueError:
        return "❌ 价格或库存格式错误", *refresh_product_list()

    products = _load()
    new_p = {
        "id": _next_id(products),
        "name": name.strip(),
        "aliases": [a.strip() for a in aliases_str.split(",") if a.strip()],
        "category": category.strip() or "未分类",
        "price": price,
        "unit": unit.strip(),
        "spec": spec.strip(),
        "brand": brand.strip(),
        "shelf": shelf.strip(),
        "stock": stock,
        "description": description.strip(),
    }
    products.append(new_p)
    _save(products)

    msg = f"✅ 已添加 [{new_p['id']}] {new_p['name']} ¥{price:.2f}"
    return msg, *refresh_product_list()


def update_product(pid, name, aliases_str, category, price_str, unit,
                   spec, brand, shelf, stock_str, description):
    """更新商品"""
    if not pid.strip():
        return "❌ 请先选择要修改的商品", *refresh_product_list()

    products = _load()
    target = None
    for p in products:
        if p["id"] == pid:
            target = p
            break

    if target is None:
        return "❌ 商品不存在", *refresh_product_list()

    if name.strip():
        target["name"] = name.strip()
    if aliases_str.strip():
        target["aliases"] = [a.strip() for a in aliases_str.split(",") if a.strip()]
    if category.strip():
        target["category"] = category.strip()
    if price_str.strip():
        try:
            target["price"] = float(price_str)
        except ValueError:
            return "❌ 价格格式错误", *refresh_product_list()
    if unit.strip():
        target["unit"] = unit.strip()
    if spec.strip():
        target["spec"] = spec.strip()
    if brand.strip():
        target["brand"] = brand.strip()
    if shelf.strip():
        target["shelf"] = shelf.strip()
    if stock_str.strip():
        try:
            target["stock"] = int(stock_str)
        except ValueError:
            return "❌ 库存格式错误", *refresh_product_list()
    if description.strip():
        target["description"] = description.strip()

    _save(products)
    msg = f"✅ 已更新 [{pid}] {target['name']}"
    return msg, *refresh_product_list()


def delete_product(selection: str):
    """删除商品"""
    if not selection:
        return "❌ 请先选择要删除的商品", *refresh_product_list()

    pid = selection.split(" - ")[0]
    products = _load()

    target = None
    for i, p in enumerate(products):
        if p["id"] == pid:
            target = (i, p)
            break

    if target is None:
        return "❌ 商品不存在", *refresh_product_list()

    idx, prod = target
    products.pop(idx)
    _save(products)

    msg = f"🗑 已删除 [{pid}] {prod['name']}"
    return msg, *refresh_product_list()


def batch_update_price(category_filter: str, change_percent: str, change_type: str):
    """批量调价"""
    if not change_percent.strip():
        return "❌ 请输入调价百分比", *refresh_product_list()

    try:
        pct = float(change_percent)
    except ValueError:
        return "❌ 百分比格式错误（如 10 或 -5）", *refresh_product_list()

    products = _load()
    count = 0
    for p in products:
        if category_filter == "全部" or p.get("category", "") == category_filter:
            if change_type == "涨价":
                p["price"] = round(p["price"] * (1 + pct / 100), 2)
            else:
                p["price"] = round(p["price"] * (1 - pct / 100), 2)
            p["price"] = max(0.01, p["price"])  # 价格不能为负
            count += 1

    _save(products)
    verb = "涨" if change_type == "涨价" else "降"
    msg = f"✅ 已对 {count} 件商品{verb}价 {pct}%"
    return msg, *refresh_product_list()


# ============================================================
# Gradio UI
# ============================================================

def create_ui():
    # 内置 CSS
    css = """
    .main-header {
        text-align: center;
        background: linear-gradient(135deg, #00FFD0, #00BFFF);
        color: white;
        padding: 12px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    .price-up { color: #e74c3c; font-weight: bold; }
    .price-down { color: #27ae60; font-weight: bold; }
    footer { visibility: hidden; }
    """

    with gr.Blocks(title="Coco 商品管理") as app:
        gr.HTML("""
        <div class="main-header">
            <h1>🤖 Coco 商品管理后台</h1>
            <p style="margin:0;opacity:0.9">实体店智能导购机器人 · 店长专用</p>
        </div>
        """)

        with gr.Tabs():
            # ================ Tab 1: 商品列表 ================
            with gr.TabItem("📋 商品列表"):
                with gr.Row():
                    with gr.Column(scale=1):
                        search_box = gr.Textbox(
                            placeholder="搜索商品名/品牌...", label="搜索",
                            show_label=False)
                    with gr.Column(scale=1):
                        cat_filter = gr.Dropdown(
                            choices=get_categories(), value="全部",
                            label="分类筛选", show_label=False)

                product_table = gr.Dataframe(
                    headers=["ID", "名称", "别名", "分类", "价格", "库存", "货架", "简介"],
                    datatype=["str", "str", "str", "str", "str", "str", "str", "str"],
                    row_count=(10, "dynamic"),
                    interactive=False,
                    wrap=True,
                )

                search_box.change(refresh_product_list,
                                  inputs=[search_box, cat_filter],
                                  outputs=product_table)
                cat_filter.change(refresh_product_list,
                                  inputs=[search_box, cat_filter],
                                  outputs=product_table)

                # 初始加载
                app.load(refresh_product_list, inputs=[search_box, cat_filter],
                         outputs=product_table)

            # ================ Tab 2: 添加商品 ================
            with gr.TabItem("➕ 添加商品"):
                with gr.Row():
                    with gr.Column():
                        add_name = gr.Textbox(label="商品名称 *", placeholder="如：可口可乐")
                        add_aliases = gr.Textbox(label="别名（逗号分隔）", placeholder="可乐, Coke, 碳酸饮料")
                        add_category = gr.Textbox(label="分类", placeholder="饮料")
                        add_price = gr.Textbox(label="价格（元）*", placeholder="3.50")
                        add_unit = gr.Textbox(label="单位", placeholder="瓶")
                    with gr.Column():
                        add_spec = gr.Textbox(label="规格", placeholder="500ml")
                        add_brand = gr.Textbox(label="品牌", placeholder="可口可乐公司")
                        add_shelf = gr.Textbox(label="货架号", placeholder="A-01-03")
                        add_stock = gr.Textbox(label="库存 *", placeholder="120")
                        add_desc = gr.Textbox(label="描述", placeholder="经典碳酸饮料...", lines=3)

                add_btn = gr.Button("✅ 添加商品", variant="primary")
                add_msg = gr.Markdown("")

                add_btn.click(
                    add_product,
                    inputs=[add_name, add_aliases, add_category, add_price,
                            add_unit, add_spec, add_brand, add_shelf,
                            add_stock, add_desc],
                    outputs=[add_msg, product_table],
                )

            # ================ Tab 3: 修改商品 ================
            with gr.TabItem("✏️ 修改商品"):
                gr.Markdown("选择商品 → 修改字段 → 保存")

                edit_selector = gr.Dropdown(
                    choices=get_product_ids(), label="选择要修改的商品",
                    interactive=True)

                with gr.Row():
                    with gr.Column():
                        edit_id = gr.Textbox(label="ID", interactive=False)
                        edit_name = gr.Textbox(label="商品名称")
                        edit_aliases = gr.Textbox(label="别名")
                        edit_category = gr.Textbox(label="分类")
                        edit_price = gr.Textbox(label="价格")
                        edit_unit = gr.Textbox(label="单位")
                    with gr.Column():
                        edit_spec = gr.Textbox(label="规格")
                        edit_brand = gr.Textbox(label="品牌")
                        edit_shelf = gr.Textbox(label="货架号")
                        edit_stock = gr.Textbox(label="库存")
                        edit_desc = gr.Textbox(label="描述", lines=3)

                with gr.Row():
                    edit_btn = gr.Button("💾 保存修改", variant="primary")
                    delete_btn = gr.Button("🗑 删除此商品", variant="stop")

                edit_msg = gr.Markdown("")

                edit_selector.change(
                    load_product_for_edit,
                    inputs=[edit_selector],
                    outputs=[edit_id, edit_name, edit_aliases, edit_category,
                             edit_price, edit_unit, edit_spec, edit_brand,
                             edit_shelf, edit_stock, edit_desc],
                )

                edit_btn.click(
                    update_product,
                    inputs=[edit_id, edit_name, edit_aliases, edit_category,
                            edit_price, edit_unit, edit_spec, edit_brand,
                            edit_shelf, edit_stock, edit_desc],
                    outputs=[edit_msg, product_table],
                ).then(
                    lambda: gr.Dropdown(choices=get_product_ids()),
                    outputs=[edit_selector],
                )

                delete_btn.click(
                    delete_product,
                    inputs=[edit_selector],
                    outputs=[edit_msg, product_table],
                ).then(
                    lambda: gr.Dropdown(choices=get_product_ids()),
                    outputs=[edit_selector],
                )

            # ================ Tab 4: 批量调价 ================
            with gr.TabItem("📊 批量调价"):
                gr.Markdown("""
                对某个分类的所有商品统一调价。
                例如：春节期间饮料全部涨价 5%，输入 `5`。
                """)

                with gr.Row():
                    batch_cat = gr.Dropdown(
                        choices=get_categories(), value="全部",
                        label="目标分类")
                    batch_pct = gr.Textbox(
                        label="调价百分比（正数涨、负数降）",
                        placeholder="例如 10 表示涨 10%，-5 表示降 5%")
                    batch_type = gr.Radio(
                        choices=["涨价", "降价"], value="涨价",
                        label="类型")

                batch_btn = gr.Button("📊 执行批量调价", variant="primary")
                batch_msg = gr.Markdown("")

                batch_btn.click(
                    batch_update_price,
                    inputs=[batch_cat, batch_pct, batch_type],
                    outputs=[batch_msg, product_table],
                )

    return app


# ============================================================
# 启动
# ============================================================

def main(port: int = 7860, share: bool = False):
    """
    启动 Web 管理后台。

    Args:
        port: 本地端口，默认 7860
        share: True=生成公网链接（临时，用于外网访问）
    """
    app = create_ui()

    print("""
   ╔══════════════════════════════════════════╗
   ║   Coco 商品管理后台 (Web版)             ║
   ╚══════════════════════════════════════════╝
    """)
    print(f"  本地访问: http://localhost:{port}")
    print(f"  局域网访问: http://<树莓派IP>:{port}")
    print(f"  按 Ctrl+C 停止\n")

    app.launch(
        server_port=port,
        share=share,
        show_error=True,
        css=css,
        theme=gr.themes.Soft(),
    )


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 7860
    share = "--share" in sys.argv
    main(port=port, share=share)
