#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a simulated age-group sample for the chart workflow."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "sample_age_groups.csv"

CATEGORIES = [
    "食品烟酒",
    "衣着",
    "居住",
    "生活用品及服务",
    "交通通信",
    "教育文化娱乐",
    "医疗保健",
    "其他用品及服务",
]

# total per capita expenditure, shares, population by age group (Chengdu, 2025, simulated)
GROUPS = {
    "18-24岁": (22000, [28, 6, 27, 5, 15, 10, 5, 4], 1_800_000),
    "25-34岁": (30000, [27, 5, 28, 6, 14, 10, 6, 4], 2_600_000),
    "35-44岁": (36000, [26, 4, 27, 5, 13, 14, 7, 4], 2_200_000),
    "45-54岁": (33000, [28, 4, 26, 6, 12, 10, 10, 4], 1_900_000),
    "55岁以上": (27000, [30, 4, 25, 5, 10, 6, 16, 4], 2_000_000),
}


def split_total(total: int, shares: list[int]) -> list[int]:
    values = [round(total * share / 100) for share in shares]
    diff = total - sum(values)
    values[-1] += diff
    return values


def main() -> None:
    rows = []
    for age_group, (total, shares, population) in GROUPS.items():
        values = split_total(total, shares)
        for category, value in zip(CATEGORIES, values):
            rows.append(
                {
                    "year": 2025,
                    "city": "成都",
                    "age_group": age_group,
                    "category": category,
                    "per_capita_expenditure": value,
                    "population": population,
                    "currency": "CNY",
                    "data_type": "模拟",
                    "source": "模拟数据（用于图表演示）",
                    "note": "仅用于方法演示，不代表真实统计",
                }
            )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
