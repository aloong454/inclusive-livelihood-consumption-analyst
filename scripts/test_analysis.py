#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对分析脚本做 20 项计算断言，输出可直接引用的测试结果。

运行：
    python scripts/test_analysis.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_livelihood import build_growth, build_indicators, build_totals  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets" / "sample_consumption.csv"
OUT = ROOT / "outputs" / "test_results.json"

TOL = 1e-6


def close(actual: float, expected: float, tol: float = 1e-6) -> bool:
    return math.isclose(float(actual), float(expected), rel_tol=tol, abs_tol=tol)


def main() -> None:
    df = pd.read_csv(DATA)
    df["year"] = df["year"].astype(int)
    df["per_capita_expenditure"] = df["per_capita_expenditure"].astype(float)
    df["sample_size"] = df["sample_size"].astype(float)

    totals = build_totals(df)
    indicators = build_indicators(df, totals)
    growth = build_growth(df, 2024, 2025)

    checks: list[tuple[str, bool, str]] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        checks.append((name, bool(condition), detail))

    # 1. 每个群体-年份有 8 个品类
    counts = df.groupby(["year", "group"])["category"].nunique()
    check("每个群体-年份包含八大类", bool((counts == 8).all()), f"min={counts.min()}, max={counts.max()}")

    # 2. 青年蓝领 2025 总支出
    y = indicators[(indicators["group"] == "新市民·青年蓝领") & (indicators["year"] == 2025)].iloc[0]
    check("青年蓝领 2025 总支出 = 26,100", close(y["人均消费支出"], 26100), f"{y['人均消费支出']}")
    # 3. 小微经营者 2025 总支出
    s = indicators[(indicators["group"] == "新市民·小微经营者") & (indicators["year"] == 2025)].iloc[0]
    check("小微经营者 2025 总支出 = 32,300", close(s["人均消费支出"], 32300), f"{s['人均消费支出']}")
    # 4. 城镇 2025 总支出
    u = indicators[(indicators["group"] == "城镇常住居民") & (indicators["year"] == 2025)].iloc[0]
    check("城镇 2025 总支出 = 37,800", close(u["人均消费支出"], 37800), f"{u['人均消费支出']}")

    # 5. 占比合计 = 100%
    share_sum = sum(y[c] for c in ["食品烟酒", "衣着", "居住", "生活用品及服务", "交通通信", "教育文化娱乐", "医疗保健", "其他用品及服务"])
    check("青年蓝领 2025 八大类占比合计 = 100%", close(share_sum, 1.0, 1e-5), f"{share_sum:.8f}")

    # 6. 食品占比
    check("青年蓝领 2025 食品占比 ≈ 30.8%", close(y["食品烟酒"], 8039 / 26100, 1e-5), f"{y['食品烟酒']:.6f}")
    # 7. 居住占比
    check("青年蓝领 2025 居住占比 ≈ 26.4%", close(y["居住"], 6890 / 26100, 1e-5), f"{y['居住']:.6f}")
    # 8. 刚性支出
    check("青年蓝领 2025 刚性支出 ≈ 57.2%", close(y["刚性支出占比"], (8039 + 6890) / 26100, 1e-5), f"{y['刚性支出占比']:.6f}")
    # 9. 发展型支出
    check("青年蓝领 2025 发展型支出 ≈ 31.9%", close(y["发展型支出占比"], (4046 + 2532 + 1749) / 26100, 1e-5), f"{y['发展型支出占比']:.6f}")

    # 10. 总增速
    yg = growth[growth["group"] == "新市民·青年蓝领"]
    total_growth = yg["总支出增速"].iloc[0]
    check("青年蓝领 2025 总增速 ≈ 5.24%", close(total_growth, 26100 / 24800 - 1, 1e-5), f"{total_growth:.6f}")

    def cat_growth(category: str) -> float:
        return float(yg[yg["category"] == category]["同比增速"].iloc[0])

    # 11. 教育增速
    check("教育文化娱乐增速 ≈ 13.44%", close(cat_growth("教育文化娱乐"), 2532 / 2232 - 1, 1e-5), f"{cat_growth('教育文化娱乐'):.6f}")
    # 12. 交通增速
    check("交通通信增速 ≈ 8.76%", close(cat_growth("交通通信"), 4046 / 3720 - 1, 1e-5), f"{cat_growth('交通通信'):.6f}")
    # 13. 食品增速
    check("食品烟酒增速 ≈ 4.57%", close(cat_growth("食品烟酒"), 8039 / 7688 - 1, 1e-5), f"{cat_growth('食品烟酒'):.6f}")
    # 14. 居住增速
    check("居住增速 ≈ 2.90%", close(cat_growth("居住"), 6890 / 6696 - 1, 1e-5), f"{cat_growth('居住'):.6f}")

    # 15. 小微经营者刚性支出
    check("小微经营者 2025 刚性支出 ≈ 52.3%", close(s["刚性支出占比"], (8947 + 7946) / 32300, 1e-5), f"{s['刚性支出占比']:.6f}")
    # 16. 城镇刚性支出
    check("城镇 2025 刚性支出 ≈ 50.7%", close(u["刚性支出占比"], (10660 + 8505) / 37800, 1e-5), f"{u['刚性支出占比']:.6f}")
    # 17. 群体差距
    gap = (y["刚性支出占比"] - u["刚性支出占比"]) * 100
    check("青年蓝领与城镇刚性支出差 ≈ 6.5pct", close(gap, 6.5, 1e-2), f"{gap:.6f}")

    # 18. 贡献度合计 ≈ 100%
    contrib_sum = float(yg["对总增长贡献"].sum())
    check("青年蓝领各品类贡献度合计 ≈ 100%", close(contrib_sum, 1.0, 1e-4), f"{contrib_sum:.8f}")

    def contribution(category: str) -> float:
        return float(yg[yg["category"] == category]["对总增长贡献"].iloc[0])

    # 19. 教育贡献
    check("教育文化娱乐贡献 ≈ 23.1%", close(contribution("教育文化娱乐"), 0.231, 2e-3), f"{contribution('教育文化娱乐'):.6f}")
    # 20. 交通贡献
    check("交通通信贡献 ≈ 25.1%", close(contribution("交通通信"), 0.251, 2e-3), f"{contribution('交通通信'):.6f}")

    passed = sum(1 for _, ok, _ in checks if ok)
    results = {
        "total": len(checks),
        "passed": passed,
        "failed": len(checks) - passed,
        "checks": [
            {"name": name, "passed": ok, "detail": detail}
            for name, ok, detail in checks
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    for index, (name, ok, detail) in enumerate(checks, start=1):
        mark = "PASS" if ok else "FAIL"
        print(f"{index:02d} [{mark}] {name} ({detail})")
    print(f"\n{passed}/{len(checks)} passed -> {OUT}")

    if passed != len(checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
