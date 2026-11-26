#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""6 checks for the chart workflow (pie + age-group bars)."""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

from PIL import Image

import make_charts

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets" / "sample_age_groups.csv"
OUT = ROOT / "outputs_charts" / "test_results_charts.json"


def close(a: float, b: float, tol: float = 1e-6) -> bool:
    return math.isclose(float(a), float(b), rel_tol=tol, abs_tol=tol)


def main() -> None:
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))

    data, city, year = make_charts.load_data(DATA, "成都", 2025, "age_group")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        pie = make_charts.pie_chart(data, city, year, "age_group", out / "pie_city_structure.png")
        age = make_charts.bar_age_share(data, city, year, "age_group", out / "bar_age_share.png")
        make_charts.bar_age_category(data, city, year, "age_group", out / "bar_age_category.png")
        make_charts.summary(city, year, pie, age, None, out / "chart_summary.md")

        files = [
            out / "pie_city_structure.png",
            out / "bar_age_share.png",
            out / "bar_age_category.png",
            out / "chart_summary.md",
        ]
        check("4 个输出文件都存在", all(path.exists() for path in files))
        sizes = []
        for name in ("pie_city_structure.png", "bar_age_share.png", "bar_age_category.png"):
            with Image.open(out / name) as image:
                sizes.append(image.size)
        check("三张图都是 1200×750", all(size == (1200, 750) for size in sizes), str(sizes))
        check("饼图占比合计 = 100%", close(pie["share"].sum(), 1.0, 1e-6), f"{pie['share'].sum():.8f}")
        check("年龄组占比合计 = 100%", close(age["share"].sum(), 1.0, 1e-6), f"{age['share'].sum():.8f}")
        check("年龄组保持自然顺序", age["age_group"].iloc[0] == "18-24岁", str(list(age["age_group"])))
        summary = (out / "chart_summary.md").read_text(encoding="utf-8")
        check("图表说明写清人口加权与分母", "人口加权" in summary and "分母" in summary)

    passed = sum(1 for _, ok, _ in checks if ok)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "total": len(checks),
                "passed": passed,
                "checks": [
                    {"name": name, "passed": ok, "detail": detail}
                    for name, ok, detail in checks
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    for index, (name, ok, detail) in enumerate(checks, start=1):
        print(f"{index:02d} [{'PASS' if ok else 'FAIL'}] {name} ({detail})")
    print(f"\n{passed}/{len(checks)} passed -> {OUT}")
    if passed != len(checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
