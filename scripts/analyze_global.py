#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全球城市民生消费分析：结构、增速、PPP 与可比性提示。

只做描述性统计，不生成授信结论。输入为长表 CSV，至少包含：
year,country,city,group,category,per_capita_expenditure,currency,
price_basis,classification,data_level,sample_size,data_type,source,note
可选：ppp_factor（本币/国际元）。
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

REQUIRED = {
    "year",
    "country",
    "city",
    "group",
    "category",
    "per_capita_expenditure",
    "currency",
    "price_basis",
    "classification",
    "data_level",
    "sample_size",
    "data_type",
    "source",
    "note",
}
PRICE_BASIS = {"nominal_local", "real_local", "ppp_intl"}
DATA_LEVELS = {"city", "metro", "national", "regional"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="全球城市民生消费分析")
    parser.add_argument("--input", required=True, help="输入 CSV 路径")
    parser.add_argument("--outdir", default="outputs_global", help="输出目录")
    parser.add_argument("--base-year", type=int, required=True)
    parser.add_argument("--compare-year", type=int, required=True)
    return parser.parse_args()


def pct(value: float, digits: int = 1) -> str:
    if pd.isna(value):
        return "—"
    return f"{value * 100:.{digits}f}%"


def money(value: float, digits: int = 0) -> str:
    if pd.isna(value):
        return "—"
    return f"{value:,.{digits}f}"


def is_food(category: str) -> bool:
    text = category.lower()
    return "food" in text or "食品" in category


def is_housing(category: str) -> bool:
    text = category.lower()
    return "housing" in text or "居住" in category


def is_development(category: str) -> bool:
    text = category.lower()
    return any(
        key in text
        for key in ("education", "health", "transport", "communication")
    ) or any(key in category for key in ("教育", "医疗", "交通", "通信"))


def validate(df: pd.DataFrame) -> None:
    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"缺少必需列：{sorted(missing)}")

    df["year"] = pd.to_numeric(df["year"], errors="raise").astype(int)
    df["per_capita_expenditure"] = pd.to_numeric(
        df["per_capita_expenditure"], errors="raise"
    )
    df["sample_size"] = pd.to_numeric(df["sample_size"], errors="coerce").fillna(0)
    if "ppp_factor" in df.columns:
        df["ppp_factor"] = pd.to_numeric(df["ppp_factor"], errors="coerce")
    else:
        df["ppp_factor"] = pd.NA

    if (df["per_capita_expenditure"] < 0).any():
        raise ValueError("per_capita_expenditure 存在负值。")

    for column in ("country", "city", "group", "category", "currency", "classification"):
        if df[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"{column} 存在空值。")

    bad_basis = sorted(set(df["price_basis"]) - PRICE_BASIS)
    if bad_basis:
        raise ValueError(f"非法 price_basis：{bad_basis}")
    bad_level = sorted(set(df["data_level"]) - DATA_LEVELS)
    if bad_level:
        raise ValueError(f"非法 data_level：{bad_level}")

    counts = (
        df.groupby(["year", "country", "city", "group"])["category"]
        .nunique()
        .reset_index(name="n")
    )
    if (counts["n"] < 2).any():
        print("[警告] 以下分组少于 2 个品类，无法做结构分析：")
        print(counts[counts["n"] < 2].to_string(index=False))

    for (year, country, city, group), part in df.groupby(
        ["year", "country", "city", "group"]
    ):
        currencies = set(part["currency"].astype(str))
        if len(currencies) > 1:
            raise ValueError(
                f"{year}/{country}/{city}/{group} 混用币种：{sorted(currencies)}"
            )
        factors = part["ppp_factor"].dropna().unique()
        if len(factors) > 1:
            print(
                f"[警告] {year}/{country}/{city}/{group} 的 ppp_factor 不唯一：{factors}"
            )


def build_indicators(df: pd.DataFrame) -> pd.DataFrame:
    keys = ["year", "country", "city", "group"]
    totals = (
        df.groupby(keys, dropna=False)
        .agg(
            total_local=("per_capita_expenditure", "sum"),
            currency=("currency", "first"),
            price_basis=("price_basis", "first"),
            classification=("classification", "first"),
            data_level=("data_level", "first"),
            ppp_factor=("ppp_factor", "first"),
            sample_size=("sample_size", "max"),
            data_type=("data_type", "first"),
        )
        .reset_index()
    )

    merged = df.merge(totals[keys + ["total_local"]], on=keys, how="left")
    merged["share"] = merged["per_capita_expenditure"] / merged["total_local"]

    rows = []
    for item in totals.itertuples(index=False):
        part = merged[
            (merged["year"] == item.year)
            & (merged["country"] == item.country)
            & (merged["city"] == item.city)
            & (merged["group"] == item.group)
        ]
        food = part[part["category"].map(is_food)]["per_capita_expenditure"].sum()
        housing = part[part["category"].map(is_housing)]["per_capita_expenditure"].sum()
        development = part[part["category"].map(is_development)][
            "per_capita_expenditure"
        ].sum()
        top = part.sort_values("share", ascending=False).iloc[0]
        ppp_factor = item.ppp_factor
        if item.price_basis == "ppp_intl" and pd.isna(ppp_factor):
            ppp_factor = 1.0
        ppp_total = (
            item.total_local / ppp_factor if pd.notna(ppp_factor) and ppp_factor else pd.NA
        )
        rows.append(
            {
                "year": item.year,
                "country": item.country,
                "city": item.city,
                "group": item.group,
                "currency": item.currency,
                "price_basis": item.price_basis,
                "classification": item.classification,
                "data_level": item.data_level,
                "ppp_factor": ppp_factor,
                "total_local": item.total_local,
                "ppp_total": ppp_total,
                "food_housing_share": (food + housing) / item.total_local,
                "development_share": development / item.total_local,
                "top_category": top["category"],
                "top_share": top["share"],
                "sample_size": item.sample_size,
                "data_type": item.data_type,
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["year", "country", "city", "group"]
    ).reset_index(drop=True)


def build_growth(df: pd.DataFrame, base_year: int, compare_year: int) -> pd.DataFrame:
    base = df[df["year"] == base_year].copy()
    compare = df[df["year"] == compare_year].copy()
    if base.empty or compare.empty:
        raise ValueError(f"基期 {base_year} 或报告期 {compare_year} 没有数据。")

    keys = ["country", "city", "group", "category"]
    merged = base.merge(
        compare,
        on=keys,
        suffixes=(f"_{base_year}", f"_{compare_year}"),
        how="outer",
        indicator=True,
    )
    missing = merged[merged["_merge"] != "both"]
    if not missing.empty:
        print("[警告] 以下品类在基期/报告期不匹配，增速为空：")
        print(missing[keys + ["_merge"]].to_string(index=False))

    merged["base_value"] = merged[f"per_capita_expenditure_{base_year}"]
    merged["compare_value"] = merged[f"per_capita_expenditure_{compare_year}"]
    merged["growth"] = merged["compare_value"] / merged["base_value"] - 1

    total_keys = ["country", "city", "group"]
    totals = (
        merged.groupby(total_keys, dropna=False)
        .agg(base_total=("base_value", "sum"), compare_total=("compare_value", "sum"))
        .reset_index()
    )
    totals["total_growth"] = totals["compare_total"] / totals["base_total"] - 1
    merged = merged.merge(totals[total_keys + ["total_growth"]], on=total_keys, how="left")
    merged["base_share"] = merged["base_value"] / merged.groupby(total_keys)[
        "base_value"
    ].transform("sum")
    merged["contribution"] = (
        merged["base_share"] * merged["growth"] / merged["total_growth"]
    )
    merged.loc[merged["total_growth"].abs() < 1e-9, "contribution"] = 0.0

    out = merged.rename(
        columns={
            "base_value": f"{base_year}_local",
            "compare_value": f"{compare_year}_local",
            "growth": "growth_local",
            "base_share": "base_share",
            "contribution": "contribution",
            "total_growth": "total_growth_local",
        }
    )[
        [
            "country",
            "city",
            "group",
            "category",
            f"{base_year}_local",
            f"{compare_year}_local",
            "growth_local",
            "base_share",
            "contribution",
            "total_growth_local",
        ]
    ]
    return out.sort_values(["country", "city", "group", "growth_local"], ascending=[True, True, True, False]).reset_index(drop=True)


def assess_comparability(indicators: pd.DataFrame, compare_year: int) -> tuple[str, list[str]]:
    data = indicators[indicators["year"] == compare_year]
    reasons: list[str] = []
    grade = "B"

    if data["classification"].nunique() > 1:
        grade = "C"
        reasons.append("分类版本不一致，需先映射。")
    if any(level not in {"city", "metro"} for level in data["data_level"]):
        grade = "C"
        reasons.append("包含国家级/区域级数据，不能当作城市数据。")
    if data["currency"].nunique() > 1:
        if data["ppp_factor"].isna().any():
            grade = "C"
            reasons.append("多币种且缺少 PPP 因子，不能比较水平。")
        else:
            reasons.append("多币种已提供 PPP 因子；水平比较按 PPP，名义本币不可比。")
    if grade == "B":
        reasons.append("分类已对齐、城市级数据、PPP 可用；但调查框架/年份仍可能不同。")
    reasons.append("A 级需要同一调查框架与分类的可验证证据；本工具不自动宣称 A。")
    return grade, reasons


def make_summary(
    indicators: pd.DataFrame,
    growth: pd.DataFrame,
    base_year: int,
    compare_year: int,
    grade: str,
    reasons: list[str],
) -> str:
    lines: list[str] = []
    lines.append(f"# {base_year}—{compare_year} 全球城市民生消费分析摘要")
    lines.append("")
    lines.append("> 本摘要为描述性统计，不构成个人授信建议。跨国/跨币种比较必须先看价格基准与可比性等级。")
    lines.append("")
    lines.append(f"**可比性等级：{grade}**")
    lines.append("")
    for reason in reasons:
        lines.append(f"- {reason}")
    lines.append("")

    lines.append("## 一、城市总览")
    lines.append("")
    lines.append("| 国家 | 城市 | 币种 | 本地人均消费 | PPP 人均消费 | 食品+居住 | 发展型支出 | 数据层级 |")
    lines.append("|---|---|---|---:|---:|---:|---:|---|")
    data = indicators[indicators["year"] == compare_year].sort_values(
        ["country", "city"]
    )
    for item in data.itertuples():
        lines.append(
            f"| {item.country} | {item.city} | {item.currency} | "
            f"{money(item.total_local)} | {money(item.ppp_total)} | "
            f"{pct(item.food_housing_share)} | {pct(item.development_share)} | "
            f"{item.data_level} |"
        )
    lines.append("")
    lines.append("> 本地人均消费是不同币种，不能直接排名；PPP 人均消费才用于跨国水平比较。")
    lines.append("")

    lines.append("## 二、结构发现")
    lines.append("")
    ranked = data.sort_values("food_housing_share", ascending=False)
    top = ranked.iloc[0]
    bottom = ranked.iloc[-1]
    lines.append(
        f"1. 食品+居住占比最高的是 **{top.city}（{pct(top.food_housing_share)}）**，"
        f"最低的是 **{bottom.city}（{pct(bottom.food_housing_share)}）**。"
    )
    ppp_ranked = data.dropna(subset=["ppp_total"]).sort_values("ppp_total", ascending=False)
    if len(ppp_ranked) >= 2:
        lines.append(
            f"2. 按 PPP 人均消费，最高的是 **{ppp_ranked.iloc[0].city}（{money(ppp_ranked.iloc[0].ppp_total)} 国际元）**，"
            f"最低的是 **{ppp_ranked.iloc[-1].city}（{money(ppp_ranked.iloc[-1].ppp_total)} 国际元）**；"
            "这是消费量比较，不是收入或财富比较。"
        )
    lines.append(
        "3. 结构差异要回到生活场景：住房、通勤、教育、医疗的制度和价格差异，不能归因于“消费观念”。"
    )
    lines.append("")

    lines.append("## 三、变化追踪（本地名义）")
    lines.append("")
    lines.append("| 国家 | 城市 | 总增速 | 增速最快品类 | 增速 |")
    lines.append("|---|---|---:|---|---:|")
    for (country, city), part in growth.groupby(["country", "city"]):
        total_growth = part["total_growth_local"].iloc[0]
        fastest = part.sort_values("growth_local", ascending=False).iloc[0]
        lines.append(
            f"| {country} | {city} | {pct(total_growth)} | {fastest['category']} | {pct(fastest['growth_local'])} |"
        )
    lines.append("")
    lines.append("> 以上为本地名义增速；跨国比较应使用实际本币或 PPP，并确认 CPI/PPP 年份一致。")
    lines.append("")

    lines.append("## 四、口径、局限与下一步")
    lines.append("")
    lines.append("- 分类：COICOP-8 proxy 是本项目代理，不是 COICOP 官方八分类。")
    lines.append("- 价格：PPP 因子为模拟值；真实分析需替换为 World Bank/OECD/Eurostat 的对应年份。")
    lines.append("- 数据层级：城市级/国家级必须区分；国家级数据不能写成城市数据。")
    lines.append("- 因果：本分析只描述结构与相关，不证明因果。")
    lines.append("- 合规：不输出个人授信结论；跨境使用需当地合规/法务复核。")
    lines.append("")
    lines.append("---")
    lines.append("由 `scripts/analyze_global.py` 自动生成；最终解释需人工复核。")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path, encoding="utf-8-sig")
    validate(df)
    indicators = build_indicators(df)
    growth = build_growth(df, args.base_year, args.compare_year)
    grade, reasons = assess_comparability(indicators, args.compare_year)

    indicators.to_csv(outdir / "global_indicators.csv", index=False, encoding="utf-8-sig")
    growth.to_csv(outdir / "global_category_growth.csv", index=False, encoding="utf-8-sig")
    payload = {
        "base_year": args.base_year,
        "compare_year": args.compare_year,
        "comparability_grade": grade,
        "comparability_reasons": reasons,
        "indicators": indicators.to_dict(orient="records"),
        "growth": growth.to_dict(orient="records"),
    }
    (outdir / "global_analysis_data.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (outdir / "global_analysis_summary.md").write_text(
        make_summary(indicators, growth, args.base_year, args.compare_year, grade, reasons),
        encoding="utf-8",
    )

    print(f"完成：{outdir.resolve()}")
    print("- global_indicators.csv")
    print("- global_category_growth.csv")
    print("- global_analysis_summary.md")
    print("- global_analysis_data.json")
    print(f"可比性等级：{grade}")


if __name__ == "__main__":
    main()
