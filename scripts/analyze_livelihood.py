#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""民生消费分析：计算结构、增速、贡献度，并生成 Markdown 摘要。

只做描述性统计，不生成授信结论。输入为长表 CSV：
year,city,group,category,per_capita_expenditure,sample_size,data_type,source,note
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

REQUIRED_COLUMNS = {
    "year",
    "city",
    "group",
    "category",
    "per_capita_expenditure",
    "sample_size",
    "data_type",
    "source",
    "note",
}

CATEGORY_ORDER = [
    "食品烟酒",
    "衣着",
    "居住",
    "生活用品及服务",
    "交通通信",
    "教育文化娱乐",
    "医疗保健",
    "其他用品及服务",
]
RIGID_CATEGORIES = ["食品烟酒", "居住"]
DEVELOPMENT_CATEGORIES = ["交通通信", "教育文化娱乐", "医疗保健"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="民生消费结构分析")
    parser.add_argument("--input", required=True, help="输入 CSV 路径")
    parser.add_argument("--outdir", default="outputs", help="输出目录")
    parser.add_argument("--base-year", type=int, required=True, help="基期年份")
    parser.add_argument("--compare-year", type=int, required=True, help="报告期年份")
    parser.add_argument(
        "--benchmark",
        default="城镇常住居民",
        help="对比基准群体名称；不存在时自动跳过",
    )
    parser.add_argument(
        "--focus-group",
        default=None,
        help="重点分析的群体名称；默认取样本量最大的新市民群体",
    )
    return parser.parse_args()


def validate(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"缺少必需列：{sorted(missing)}")

    df["year"] = pd.to_numeric(df["year"], errors="raise").astype(int)
    df["per_capita_expenditure"] = pd.to_numeric(
        df["per_capita_expenditure"], errors="raise"
    )
    df["sample_size"] = pd.to_numeric(df["sample_size"], errors="coerce").fillna(0)

    if (df["per_capita_expenditure"] < 0).any():
        raise ValueError("per_capita_expenditure 存在负值，请检查数据。")

    unknown = sorted(set(df["category"]) - set(CATEGORY_ORDER))
    if unknown:
        raise ValueError(f"存在未定义的消费类别：{unknown}")

    counts = (
        df.groupby(["year", "city", "group"], dropna=False)["category"]
        .nunique()
        .reset_index(name="n_categories")
    )
    incomplete = counts[counts["n_categories"] != len(CATEGORY_ORDER)]
    if not incomplete.empty:
        print("[警告] 以下分组不是完整的八大类，结构占比可能不可比：")
        print(incomplete.to_string(index=False))


def build_totals(df: pd.DataFrame) -> pd.DataFrame:
    totals = (
        df.groupby(["year", "city", "group"], dropna=False)
        .agg(
            total=("per_capita_expenditure", "sum"),
            sample_size=("sample_size", "max"),
            data_type=("data_type", "first"),
        )
        .reset_index()
    )
    return totals


def build_indicators(df: pd.DataFrame, totals: pd.DataFrame) -> pd.DataFrame:
    merged = df.merge(totals, on=["year", "city", "group"], how="left")
    merged["share"] = merged["per_capita_expenditure"] / merged["total"]

    share_pivot = merged.pivot_table(
        index=["year", "city", "group"],
        columns="category",
        values="share",
        aggfunc="sum",
    ).reset_index()
    share_pivot.columns.name = None

    for category in CATEGORY_ORDER:
        if category not in share_pivot.columns:
            share_pivot[category] = 0.0

    indicators = totals.merge(
        share_pivot[
            ["year", "city", "group", *CATEGORY_ORDER]
        ],
        on=["year", "city", "group"],
        how="left",
    )

    indicators["刚性支出占比"] = indicators[RIGID_CATEGORIES].sum(axis=1)
    indicators["发展型支出占比"] = indicators[DEVELOPMENT_CATEGORIES].sum(axis=1)
    indicators = indicators.rename(
        columns={
            "total": "人均消费支出",
            "sample_size": "样本量",
            "data_type": "数据性质",
        }
    )

    ordered = [
        "year",
        "city",
        "group",
        "人均消费支出",
        "样本量",
        "数据性质",
        "刚性支出占比",
        "发展型支出占比",
        *CATEGORY_ORDER,
    ]
    return indicators[ordered].sort_values(["group", "year"]).reset_index(drop=True)


def build_growth(df: pd.DataFrame, base_year: int, compare_year: int) -> pd.DataFrame:
    base = df[df["year"] == base_year].copy()
    compare = df[df["year"] == compare_year].copy()
    if base.empty or compare.empty:
        raise ValueError(f"基期 {base_year} 或报告期 {compare_year} 没有数据。")

    keys = ["city", "group", "category"]
    merged = base.merge(
        compare,
        on=keys,
        suffixes=(f"_{base_year}", f"_{compare_year}"),
        how="outer",
        indicator=True,
    )
    missing = merged[merged["_merge"] != "both"]
    if not missing.empty:
        print("[警告] 以下品类在基期/报告期不匹配，增速将为空：")
        print(missing[keys + ["_merge"]].to_string(index=False))

    merged["基期支出"] = merged[f"per_capita_expenditure_{base_year}"]
    merged["报告期支出"] = merged[f"per_capita_expenditure_{compare_year}"]
    merged["增速"] = merged["报告期支出"] / merged["基期支出"] - 1

    totals = (
        merged.groupby(["city", "group"], dropna=False)
        .agg(基期总支出=("基期支出", "sum"), 报告期总支出=("报告期支出", "sum"))
        .reset_index()
    )
    totals["总增速"] = totals["报告期总支出"] / totals["基期总支出"] - 1
    merged = merged.merge(totals[["city", "group", "总增速"]], on=["city", "group"], how="left")

    merged["基期占比"] = merged["基期支出"] / merged.groupby(["city", "group"])[
        "基期支出"
    ].transform("sum")
    merged["贡献度"] = merged["基期占比"] * merged["增速"] / merged["总增速"]
    merged.loc[merged["总增速"].abs() < 1e-9, "贡献度"] = 0.0
    merged["结构变化_pct"] = (
        merged["报告期支出"] / merged.groupby(["city", "group"])["报告期支出"].transform("sum")
        - merged["基期占比"]
    ) * 100

    out = merged[
        [
            "city",
            "group",
            "category",
            "基期支出",
            "报告期支出",
            "增速",
            "基期占比",
            "贡献度",
            "结构变化_pct",
            "总增速",
        ]
    ].copy()
    out = out.rename(
        columns={
            "基期支出": f"{base_year}年人均支出",
            "报告期支出": f"{compare_year}年人均支出",
            "增速": "同比增速",
            "基期占比": "基期占比",
            "贡献度": "对总增长贡献",
            "结构变化_pct": "占比变化_pct",
            "总增速": "总支出增速",
        }
    )
    return out.sort_values(["group", "同比增速"], ascending=[True, False]).reset_index(
        drop=True
    )


def pct(value: float, digits: int = 1) -> str:
    if pd.isna(value):
        return "—"
    return f"{value * 100:.{digits}f}%"


def pct_point(value: float, digits: int = 1) -> str:
    if pd.isna(value):
        return "—"
    if abs(value) < 0.05:
        value = 0.0
    return f"{value:+.{digits}f}pct"


def yuan(value: float) -> str:
    if pd.isna(value):
        return "—"
    return f"{value:,.0f}"


def top_categories(row: pd.Series, n: int = 2) -> list[tuple[str, float]]:
    items = [(category, float(row[category])) for category in CATEGORY_ORDER]
    return sorted(items, key=lambda item: item[1], reverse=True)[:n]


def make_findings(
    indicators: pd.DataFrame,
    growth: pd.DataFrame,
    base_year: int,
    compare_year: int,
    focus_group: str,
    benchmark: str,
) -> list[str]:
    findings: list[str] = []
    focus_ind = indicators[
        (indicators["group"] == focus_group) & (indicators["year"] == compare_year)
    ]
    if focus_ind.empty:
        return findings
    row = focus_ind.iloc[0]
    findings.append(
        f"**结构**：{focus_group}人均消费支出 {yuan(row['人均消费支出'])} 元，"
        f"食品烟酒 {pct(row['食品烟酒'])}、居住 {pct(row['居住'])}，"
        f"两项合计 {pct(row['刚性支出占比'])}，是消费结构中最重的部分。"
    )

    focus_growth = growth[
        (growth["group"] == focus_group)
        & (growth["city"] == row["city"])
    ].copy()
    if not focus_growth.empty:
        fastest = focus_growth.sort_values("同比增速", ascending=False).head(2)
        fastest_text = "、".join(
            f"{category}（{pct(growth_value, 1)}）"
            for category, growth_value in fastest[
                ["category", "同比增速"]
            ].itertuples(index=False, name=None)
        )
        findings.append(
            f"**变化**：{compare_year} 年总支出同比 {pct(focus_growth['总支出增速'].iloc[0], 1)}，"
            f"增速最快的是{fastest_text}。需要结合基数看：高增速不等于高贡献。"
        )

    benchmark_ind = indicators[
        (indicators["group"] == benchmark) & (indicators["year"] == compare_year)
    ]
    if not benchmark_ind.empty and benchmark != focus_group:
        b = benchmark_ind.iloc[0]
        diff = (row["刚性支出占比"] - b["刚性支出占比"]) * 100
        findings.append(
            f"**分化**：与{benchmark}相比，{focus_group}的刚性支出占比"
            f"{'高' if diff >= 0 else '低'} {abs(diff):.1f} 个百分点；"
            f"教育文化娱乐占比 {pct(row['教育文化娱乐'])}，"
            f"对比基准 {pct(b['教育文化娱乐'])}。差异不能直接归因于消费观念。"
        )
    return findings


def make_report(
    indicators: pd.DataFrame,
    growth: pd.DataFrame,
    base_year: int,
    compare_year: int,
    focus_group: str,
    benchmark: str,
    input_path: Path,
) -> str:
    lines: list[str] = []
    lines.append(f"# {base_year}—{compare_year} 年民生消费结构分析摘要")
    lines.append("")
    data_types = ", ".join(sorted(set(indicators["数据性质"].dropna().astype(str))))
    lines.append(f"- 数据性质：{data_types or '未标注'}")
    lines.append(f"- 输入文件：`{input_path.name}`")
    lines.append(f"- 重点群体：{focus_group}")
    lines.append(f"- 对比基准：{benchmark}")
    lines.append("")
    lines.append("> 本摘要为描述性统计，不构成个人授信建议。若为模拟数据，仅用于方法演示。")
    lines.append("")

    lines.append("## 一、总览")
    lines.append("")
    lines.append(
        "| 年份 | 群体 | 人均消费支出（元） | 刚性支出占比 | 发展型支出占比 | 样本量 |"
    )
    lines.append("|---|---|---:|---:|---:|---:|")
    overview = indicators.sort_values(["group", "year"])
    for item in overview.itertuples():
        lines.append(
            f"| {item.year} | {item.group} | {yuan(item.人均消费支出)} | "
            f"{pct(item.刚性支出占比)} | {pct(item.发展型支出占比)} | {int(item.样本量)} |"
        )
    lines.append("")

    lines.append("## 二、三条可放进 PPT 的发现")
    lines.append("")
    findings = make_findings(
        indicators, growth, base_year, compare_year, focus_group, benchmark
    )
    if findings:
        for index, finding in enumerate(findings, start=1):
            lines.append(f"{index}. {finding}")
    else:
        lines.append("数据不足以生成发现，请检查重点群体名称。")
    lines.append("")

    lines.append("## 三、重点群体：品类增速与贡献")
    lines.append("")
    focus_growth = growth[growth["group"] == focus_group].copy()
    if focus_growth.empty:
        lines.append("未找到重点群体数据。")
    else:
        lines.append("| 品类 | 基期占比 | 同比增速 | 对总增长贡献 | 占比变化 |")
        lines.append("|---|---:|---:|---:|---:|")
        for item in focus_growth.sort_values("同比增速", ascending=False).itertuples():
            lines.append(
                f"| {item.category} | {pct(item.基期占比)} | {pct(item.同比增速)} | "
                f"{pct(item.对总增长贡献)} | {pct_point(item.占比变化_pct)} |"
            )
    lines.append("")

    lines.append("## 四、所有群体对比")
    lines.append("")
    compare_ind = indicators[indicators["year"] == compare_year].sort_values(
        "刚性支出占比", ascending=False
    )
    lines.append("| 群体 | 人均消费支出（元） | 食品+居住 | 教育文化娱乐 | 交通通信 |")
    lines.append("|---|---:|---:|---:|---:|")
    for item in compare_ind.itertuples():
        lines.append(
            f"| {item.group} | {yuan(item.人均消费支出)} | {pct(item.刚性支出占比)} | "
            f"{pct(item.教育文化娱乐)} | {pct(item.交通通信)} |"
        )
    lines.append("")

    lines.append("## 五、口径、局限与下一步")
    lines.append("")
    lines.append("- 口径：人均消费支出；占比为八大类占合计；增速为同比名义增速。")
    lines.append("- 结构：总计由八大类加总；四舍五入可能导致合计与 100% 有细微差异。")
    lines.append("- 因果：本分析只描述相关与结构，不证明因果。")
    lines.append("- 样本：分组样本量低于 30 时，结论只作描述性提示。")
    lines.append("- 合规：不输出个人授信结论；个人层面决策需人工结合征信、收入、负债与适当性评估。")
    lines.append("- 下一步：补充收入、负债、房租/通勤等数据，验证场景假设。")
    lines.append("")
    lines.append("---")
    lines.append("由 `scripts/analyze_livelihood.py` 自动生成；最终解释需人工复核。")
    lines.append("")
    return "\n".join(lines)


def choose_focus_group(df: pd.DataFrame, compare_year: int, requested: str | None) -> str:
    groups = sorted(df["group"].dropna().unique().tolist())
    if requested:
        if requested not in groups:
            raise ValueError(f"focus-group 不存在：{requested}；可选：{groups}")
        return requested
    new_citizen = [g for g in groups if "新市民" in g]
    if new_citizen:
        sample = (
            df[(df["year"] == compare_year) & (df["group"].isin(new_citizen))]
            .groupby("group")["sample_size"]
            .max()
            .sort_values(ascending=False)
        )
        if not sample.empty:
            return str(sample.index[0])
    return groups[0]


def write_json(
    path: Path,
    indicators: pd.DataFrame,
    growth: pd.DataFrame,
    base_year: int,
    compare_year: int,
    focus_group: str,
) -> None:
    payload = {
        "base_year": base_year,
        "compare_year": compare_year,
        "focus_group": focus_group,
        "indicators": indicators.to_dict(orient="records"),
        "focus_growth": growth[growth["group"] == focus_group].to_dict(orient="records"),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path)
    validate(df)
    totals = build_totals(df)
    indicators = build_indicators(df, totals)
    growth = build_growth(df, args.base_year, args.compare_year)
    focus_group = choose_focus_group(df, args.compare_year, args.focus_group)

    indicators.to_csv(outdir / "indicators.csv", index=False, encoding="utf-8-sig")
    growth.to_csv(outdir / "category_growth.csv", index=False, encoding="utf-8-sig")
    write_json(
        outdir / "analysis_data.json",
        indicators,
        growth,
        args.base_year,
        args.compare_year,
        focus_group,
    )

    report = make_report(
        indicators,
        growth,
        args.base_year,
        args.compare_year,
        focus_group,
        args.benchmark,
        input_path,
    )
    (outdir / "analysis_summary.md").write_text(report, encoding="utf-8")

    print(f"完成：{outdir.resolve()}")
    print(f"- indicators.csv")
    print(f"- category_growth.csv")
    print(f"- analysis_summary.md")
    print(f"- analysis_data.json")
    print(f"重点群体：{focus_group}")


if __name__ == "__main__":
    main()
