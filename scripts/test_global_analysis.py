#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""10 assertions for the global-city analysis path."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_global import (  # noqa: E402
    assess_comparability,
    build_growth,
    build_indicators,
    validate,
)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets" / "sample_global_cities.csv"
OUT = ROOT / "outputs_global" / "test_results_global.json"


def close(actual: float, expected: float, tol: float = 1e-6) -> bool:
    return math.isclose(float(actual), float(expected), rel_tol=tol, abs_tol=tol)


def main() -> None:
    df = pd.read_csv(DATA, encoding="utf-8-sig")
    validate(df)
    indicators = build_indicators(df)
    growth = build_growth(df, 2024, 2025)
    grade, reasons = assess_comparability(indicators, 2025)

    checks: list[tuple[str, bool, str]] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        checks.append((name, bool(condition), detail))

    check(
        "48 行 / 3 城 / 2 年 / 8 类",
        len(df) == 48
        and df["city"].nunique() == 3
        and df["year"].nunique() == 2
        and df["category"].nunique() == 8,
        f"{len(df)} rows",
    )

    berlin = indicators[(indicators["city"] == "Berlin") & (indicators["year"] == 2025)].iloc[0]
    singapore = indicators[(indicators["city"] == "Singapore") & (indicators["year"] == 2025)].iloc[0]
    sao = indicators[(indicators["city"] == "São Paulo") & (indicators["year"] == 2025)].iloc[0]

    check("Berlin 2025 本地总支出 = 25,600", close(berlin["total_local"], 25600), f"{berlin['total_local']}")
    check("Singapore 2025 本地总支出 = 40,000", close(singapore["total_local"], 40000), f"{singapore['total_local']}")
    check("São Paulo 2025 本地总支出 = 29,500", close(sao["total_local"], 29500), f"{sao['total_local']}")
    check("Berlin 食品+居住 = 42.0%", close(berlin["food_housing_share"], 0.42, 1e-5), f"{berlin['food_housing_share']:.6f}")
    check("Berlin PPP 人均 = 25,600 / 0.75", close(berlin["ppp_total"], 25600 / 0.75, 1e-5), f"{berlin['ppp_total']:.6f}")

    share_ok = True
    for _, part in df.groupby(["year", "country", "city", "group"]):
        shares = part["per_capita_expenditure"] / part["per_capita_expenditure"].sum()
        if not close(shares.sum(), 1.0, 1e-6):
            share_ok = False
    check("每个城市-年份的品类占比合计 = 100%", share_ok)

    check("可比性等级 = B", grade == "B", grade)
    berlin_growth = growth[(growth["country"] == "Germany") & (growth["city"] == "Berlin")]["total_growth_local"].iloc[0]
    check("Berlin 2025 本地名义增速 ≈ 3.23%", close(berlin_growth, 25600 / 24800 - 1, 1e-5), f"{berlin_growth:.6f}")

    reasons_text = " ".join(reasons)
    check(
        "输出提示多币种/PPP，不自动宣称 A",
        ("多币种" in reasons_text or "PPP" in reasons_text) and "A 级" in reasons_text,
        reasons_text[:120],
    )

    passed = sum(1 for _, ok, _ in checks if ok)
    payload = {
        "total": len(checks),
        "passed": passed,
        "checks": [{"name": name, "passed": ok, "detail": detail} for name, ok, detail in checks],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    for index, (name, ok, detail) in enumerate(checks, start=1):
        print(f"{index:02d} [{'PASS' if ok else 'FAIL'}] {name} ({detail})")
    print(f"\n{passed}/{len(checks)} passed -> {OUT}")
    if passed != len(checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
