#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate pie and bar charts for city consumption structure and age groups.

Input CSV columns (minimum):
year,city,age_group,category,per_capita_expenditure

Outputs:
- pie_city_structure.png
- bar_age_share.png
- bar_age_category.png
- chart_summary.md
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

S = 2  # supersample for crisp text and edges
W, H = 1200, 750

BG = (247, 241, 231)
INK = (14, 35, 32)
MUTED = (109, 124, 117)
CORAL = (232, 100, 60)
TEAL = (47, 111, 101)
GOLD = (200, 162, 74)
SAGE = (169, 192, 181)
PALE = (232, 220, 200)
WHITE = (255, 255, 255)
PIE_COLORS = [
    CORAL,
    TEAL,
    GOLD,
    SAGE,
    (122, 158, 159),
    (217, 142, 115),
    (140, 154, 147),
]

SHORT = {
    "食品烟酒": "食品",
    "衣着": "衣着",
    "居住": "居住",
    "生活用品及服务": "生活用品",
    "交通通信": "交通通信",
    "教育文化娱乐": "教育文娱",
    "医疗保健": "医疗",
    "其他用品及服务": "其他",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成消费结构饼图与年龄组柱形图")
    parser.add_argument("--input", required=True, help="输入 CSV")
    parser.add_argument("--outdir", default="charts", help="输出目录")
    parser.add_argument("--city", default=None, help="城市名；默认取第一个")
    parser.add_argument("--year", type=int, default=None, help="年份；默认取最新")
    parser.add_argument("--age-column", default="age_group", help="年龄列名")
    return parser.parse_args()


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path(r"C:\Windows\Fonts\msyhbd.ttc") if bold else Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf"),
    ]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size * S)
            except OSError:
                continue
    return ImageFont.load_default()


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (W * S, H * S), BG)
    return image, ImageDraw.Draw(image)


def text(draw: ImageDraw.ImageDraw, xy, content, size, color=INK, bold=False, anchor="la"):
    draw.text((xy[0] * S, xy[1] * S), content, font=font(size, bold), fill=color, anchor=anchor)


def rect(draw: ImageDraw.ImageDraw, box, fill, radius=0, outline=None, width=1):
    draw.rounded_rectangle(
        tuple(int(v * S) for v in box),
        radius=radius * S,
        fill=fill,
        outline=outline,
        width=width * S,
    )


def pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%"


def short(category: str) -> str:
    if category in SHORT:
        return SHORT[category]
    return category if len(category) <= 9 else category[:8] + "…"


def header(draw: ImageDraw.ImageDraw, kicker: str, title: str, subtitle: str, badge: str = "模拟数据") -> None:
    draw.rectangle((60 * S, 54 * S, 86 * S, 58 * S), fill=CORAL)
    text(draw, (96, 48), kicker, 13, CORAL, True)
    text(draw, (60, 82), title, 30, INK, True)
    text(draw, (60, 126), subtitle, 15, MUTED)
    draw.line((60 * S, 158 * S, 1140 * S, 158 * S), fill=PALE, width=1 * S)
    rect(draw, (1032, 48, 1140, 76), fill=INK, radius=4)
    text(draw, (1086, 62), badge, 11, BG, True, anchor="mm")


def footer(draw: ImageDraw.ImageDraw, source: str) -> None:
    draw.line((60 * S, 702 * S, 1140 * S, 702 * S), fill=PALE, width=1 * S)
    text(draw, (60, 716), source, 11, MUTED)


def save(image: Image.Image, path: Path) -> None:
    image.resize((W, H), Image.LANCZOS).save(path, quality=95)


def load_data(path: Path, city: str | None, year: int | None, age_col: str) -> tuple[pd.DataFrame, str, int]:
    df = pd.read_csv(path, encoding="utf-8-sig")
    required = {"year", "city", "category", "per_capita_expenditure", age_col}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"缺少列：{sorted(missing)}")
    df["year"] = pd.to_numeric(df["year"], errors="raise").astype(int)
    df["per_capita_expenditure"] = pd.to_numeric(df["per_capita_expenditure"], errors="raise")
    city = city or sorted(df["city"].dropna().unique())[0]
    data = df[df["city"] == city].copy()
    if data.empty:
        raise ValueError(f"没有城市：{city}")
    year = year or int(data["year"].max())
    data = data[data["year"] == year].copy()
    if data.empty:
        raise ValueError(f"{city} 没有 {year} 年数据")
    return data, city, year


def pie_chart(data: pd.DataFrame, city: str, year: int, age_col: str, out: Path, data_label: str = "模拟数据") -> pd.DataFrame:
    has_population = (
        "population" in data.columns
        and data["population"].notna().all()
        and (data["population"] > 0).all()
    )

    if has_population:
        weighted = data.assign(
            weighted_expenditure=data["per_capita_expenditure"] * data["population"]
        )
        values = weighted.groupby("category")["weighted_expenditure"].sum()
        total_consumption = float(values.sum())
        population_total = float(data.groupby(age_col)["population"].first().sum())
        per_capita = values / population_total
        shares = values / total_consumption
        total_label = f"人口加权人均消费  {total_consumption / population_total:,.0f} 元"
        subtitle = "按八大类人均消费支出计算 · 人口加权"
    else:
        per_capita = data.groupby("category")["per_capita_expenditure"].mean()
        total_consumption = float(per_capita.sum())
        shares = per_capita / total_consumption
        total_label = f"各年龄组简单平均  {total_consumption:,.0f} 元"
        subtitle = "按八大类人均消费支出计算 · 未按人口加权（简单平均）"

    ordered = shares.sort_values(ascending=False)
    items = [(category, float(shares[category])) for category in ordered.index]
    if len(items) > 7:
        items = items[:6] + [("其他", sum(value for _, value in items[6:]))]
    items = sorted(items, key=lambda item: item[1], reverse=True)

    image, draw = canvas()
    header(
        draw,
        "CHART / 01",
        f"{year} 年{city}居民消费结构",
        f"{subtitle} · 饼图用于 part-to-whole",
        data_label,
    )

    cx, cy, r = 350, 430, 205
    start = -90.0
    for index, (category, share) in enumerate(items):
        end = start + share * 360
        draw.pieslice(
            ((cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S),
            start=start,
            end=end,
            fill=PIE_COLORS[index % len(PIE_COLORS)],
            outline=BG,
            width=3 * S,
        )
        start = end

    # legend panel
    rect(draw, (610, 196, 1140, 636), fill=WHITE, radius=10, outline=PALE, width=1)
    text(draw, (636, 218), "品类", 12, MUTED, True)
    text(draw, (1092, 218), "占比", 12, MUTED, True, anchor="ra")
    for index, (category, share) in enumerate(items):
        y = 252 + index * 44
        color = PIE_COLORS[index % len(PIE_COLORS)]
        draw.rectangle((636 * S, (y - 9) * S, 654 * S, (y + 9) * S), fill=color)
        text(draw, (670, y), short(category), 16, INK, anchor="lm")
        text(draw, (1092, y), pct(share), 17, INK, True, anchor="rm")

    # total callout
    text(draw, (60, 650), total_label, 16, INK, True)
    footer(draw, f"数据：{data_label}，仅用于方法演示；占比按未四舍五入数据计算。")
    save(image, out)
    return pd.DataFrame(
        [
            {
                "category": category,
                "per_capita": per_capita[category],
                "share": shares[category],
            }
            for category in per_capita.index
        ]
    )


def bar_age_share(data: pd.DataFrame, city: str, year: int, age_col: str, out: Path, data_label: str = "模拟数据") -> pd.DataFrame:
    order = list(dict.fromkeys(data[age_col].astype(str)))
    per_capita = (
        data.groupby(age_col)["per_capita_expenditure"].sum().reindex(order)
    )
    has_population = (
        "population" in data.columns
        and data["population"].notna().all()
        and (data["population"] > 0).all()
    )
    if has_population:
        population = data.groupby(age_col)["population"].first().reindex(order)
        weighted_total = per_capita * population
        grand = float(weighted_total.sum())
        shares = weighted_total / grand
        subtitle = "按年龄组人口加权，各年龄组消费支出占全市总消费的比重"
    else:
        weighted_total = pd.Series([float("nan")] * len(per_capita), index=per_capita.index)
        grand = float(per_capita.sum())
        shares = per_capita / grand
        subtitle = "未按人口加权；各年龄组人均消费的简单占比（仅作演示）"

    max_share = max(float(shares.max()), 0.01)

    image, draw = canvas()
    header(
        draw,
        "CHART / 02",
        f"{year} 年{city}不同年龄人群的消费比重",
        f"{subtitle} · 柱形图用于组间比较",
        data_label,
    )

    bx0, bx1 = 300, 1090
    top, row_h = 210, 82
    grid_max = math.ceil(max_share * 100 / 10) * 10
    grid_max = max(grid_max, 20)
    for tick in range(0, grid_max + 1, 10):
        x = bx0 + (bx1 - bx0) * tick / grid_max
        draw.line((x * S, (top - 10) * S, x * S, (top + row_h * len(per_capita) + 6) * S), fill=PALE, width=1 * S)
        text(draw, (x, top + row_h * len(per_capita) + 22), f"{tick}%", 11, MUTED, anchor="ma")

    highlight = int(shares.values.argmax())
    for index, (age, value) in enumerate(per_capita.items()):
        y = top + index * row_h
        share = shares[age]
        width = (bx1 - bx0) * (share * 100) / grid_max
        color = CORAL if index == highlight else TEAL
        text(draw, (270, y + 17), str(age), 16, INK, True, anchor="ra")
        rect(draw, (bx0, y, bx0 + width, y + 34), fill=color, radius=3)
        text(draw, (bx0 + width + 10, y + 17), pct(share), 15, INK, True, anchor="lm")

    footer(draw, f"数据：{data_label}，仅用于方法演示；分母为全市总消费。")
    save(image, out)
    return pd.DataFrame(
        [
            {
                "age_group": age,
                "per_capita": per_capita[age],
                "weighted_total": weighted_total[age],
                "share": shares[age],
            }
            for age in per_capita.index
        ]
    )


def bar_age_category(data: pd.DataFrame, city: str, year: int, age_col: str, out: Path, data_label: str = "模拟数据") -> pd.DataFrame:
    order = list(dict.fromkeys(data[age_col].astype(str)))
    total_by_cat = data.groupby("category")["per_capita_expenditure"].sum().sort_values(ascending=False)
    categories = list(total_by_cat.index[:5])
    pivot = (
        data[data["category"].isin(categories)]
        .pivot_table(index=age_col, columns="category", values="per_capita_expenditure", aggfunc="sum")
        .reindex(order)[categories]
    )
    shares = pivot.div(pivot.sum(axis=1), axis=0)
    max_share = max(float(shares.max().max()), 0.01)

    image, draw = canvas()
    header(
        draw,
        "CHART / 03",
        f"{year} 年{city}不同年龄人群的品类结构",
        "前 5 大品类；百分比为各年龄组内的消费占比 · 分组柱形图",
        data_label,
    )

    # legend
    lx = 60
    for index, category in enumerate(categories):
        draw.rectangle((lx * S, 186 * S, (lx + 14) * S, 200 * S), fill=PIE_COLORS[index])
        text(draw, (lx + 20, 193), short(category), 12, INK, anchor="lm")
        lx += 150

    plot_l, plot_r, plot_t, plot_b = 100, 1140, 250, 610
    grid_max = math.ceil(max_share * 100 / 5) * 5
    grid_max = max(grid_max, 20)
    for tick in range(0, grid_max + 1, 5):
        y = plot_b - (plot_b - plot_t) * tick / grid_max
        draw.line((plot_l * S, y * S, plot_r * S, y * S), fill=PALE, width=1 * S)
        text(draw, (plot_l - 14, y), f"{tick}%", 10, MUTED, anchor="rm")

    group_w = (plot_r - plot_l) / len(order)
    bar_w = min(26, (group_w - 26) / len(categories))
    for gi, age in enumerate(order):
        center = plot_l + group_w * (gi + 0.5)
        text(draw, (center, plot_b + 18), str(age), 12, INK, True, anchor="ma")
        for ci, category in enumerate(categories):
            value = float(shares.loc[age, category])
            h = (plot_b - plot_t) * (value * 100) / grid_max
            x = center - (len(categories) * bar_w) / 2 + ci * bar_w
            draw.rectangle(
                (x * S, (plot_b - h) * S, (x + bar_w - 3) * S, plot_b * S),
                fill=PIE_COLORS[ci],
            )

    footer(draw, f"数据：{data_label}，仅用于方法演示；分母为该年龄组总消费。")
    save(image, out)
    return shares.reset_index()


def summary(
    city: str,
    year: int,
    pie: pd.DataFrame,
    age: pd.DataFrame,
    age_cat: pd.DataFrame,
    out: Path,
    data_label: str = "模拟数据",
) -> None:
    weighted = age["weighted_total"].notna().any()
    if data_label == "模拟数据":
        data_note = "> 数据为模拟数据，仅用于方法演示；不代表真实统计。"
    else:
        data_note = f"> 数据性质：{data_label}；请以原始数据与机构复核为准。"
    lines = [
        f"# {year} 年{city}消费结构与年龄组图表",
        "",
        data_note,
        "",
        "## 图表口径",
        "",
        f"- 城市：{city}",
        f"- 年份：{year}",
        (
            "- 饼图分母：人口加权后的城市总消费"
            if weighted
            else "- 饼图分母：各年龄组人均消费的简单平均"
        ),
        (
            "- 年龄柱形图分母：人口加权后的全市总消费"
            if weighted
            else "- 年龄柱形图分母：各年龄组人均消费合计（未按人口加权）"
        ),
        "- 分组柱形图分母：各年龄组总消费",
        "",
        "## 品类结构",
        "",
        "| 品类 | 人均支出 | 占比 |",
        "|---|---:|---:|",
    ]
    for item in pie.itertuples():
        lines.append(f"| {item.category} | {item.per_capita:,.0f} | {pct(item.share)} |")
    lines += [
        "",
        "## 年龄组消费比重",
        "",
        "| 年龄组 | 人均支出 | 占全市比重 |",
        "|---|---:|---:|",
    ]
    for item in age.itertuples():
        lines.append(f"| {item.age_group} | {item.per_capita:,.0f} | {pct(item.share)} |")
    lines += [
        "",
        "## 输出文件",
        "",
        "- `pie_city_structure.png`：城市消费结构饼图",
        "- `bar_age_share.png`：不同年龄人群的消费比重柱形图",
        "- `bar_age_category.png`：不同年龄人群的品类结构分组柱形图",
        "",
        "## 局限",
        "",
        "- 饼图类别超过 7 个时，尾部合并为“其他”。",
        "- 年龄组为模拟分组，真实分析需替换为调查口径。",
        "- 未提供人口时，年龄组比重按人均消费简单占比计算，不代表真实人口结构。",
        "- 消费结构不等于还款能力，不能用于个人授信。",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    data, city, year = load_data(Path(args.input), args.city, args.year, args.age_column)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    types = set(data["data_type"].astype(str)) if "data_type" in data.columns else set()
    if types == {"模拟"}:
        data_label = "模拟数据"
    elif "模拟" not in types and ("真实" in types or "实际" in types):
        data_label = "真实数据"
    else:
        data_label = "数据待确认"

    pie = pie_chart(data, city, year, args.age_column, outdir / "pie_city_structure.png", data_label)
    age = bar_age_share(data, city, year, args.age_column, outdir / "bar_age_share.png", data_label)
    age_cat = bar_age_category(data, city, year, args.age_column, outdir / "bar_age_category.png", data_label)
    summary(city, year, pie, age, age_cat, outdir / "chart_summary.md", data_label)

    print(f"完成：{outdir.resolve()}")
    for name in (
        "pie_city_structure.png",
        "bar_age_share.png",
        "bar_age_category.png",
        "chart_summary.md",
    ):
        print(f"- {name}")


if __name__ == "__main__":
    main()
