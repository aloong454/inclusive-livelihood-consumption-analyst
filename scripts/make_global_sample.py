#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the simulated global-city sample used by analyze_global.py.

The data is synthetic and calibrated to broad OECD/World Bank structure only.
It must not be presented as real statistics.
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "sample_global_cities.csv"

CATEGORIES = [
    "Food and non-alcoholic beverages",
    "Housing, water, electricity, gas",
    "Transport",
    "Communication",
    "Education",
    "Health",
    "Recreation and culture",
    "Clothing and footwear",
]

# total local currency per capita, shares, currency, ppp factor
CITIES = {
    "Berlin": {
        "country": "Germany",
        "currency": "EUR",
        "ppp_factor": 0.75,
        "sample": 1200,
        "years": {
            2024: (24800, [12, 30, 13, 4, 6, 12, 13, 10]),
            2025: (25600, [12, 30, 13, 4, 6, 12, 14, 9]),
        },
    },
    "Singapore": {
        "country": "Singapore",
        "currency": "SGD",
        "ppp_factor": 1.35,
        "sample": 1500,
        "years": {
            2024: (38500, [14, 27, 12, 5, 10, 10, 12, 10]),
            2025: (40000, [14, 27, 12, 5, 10, 11, 12, 9]),
        },
    },
    "São Paulo": {
        "country": "Brazil",
        "currency": "BRL",
        "ppp_factor": 2.60,
        "sample": 1000,
        "years": {
            2024: (28000, [20, 26, 14, 5, 8, 12, 8, 7]),
            2025: (29500, [20, 26, 14, 5, 9, 12, 8, 6]),
        },
    },
}


def split_total(total: int, shares: list[int]) -> list[int]:
    values = [round(total * share / 100) for share in shares]
    diff = total - sum(values)
    values[-1] += diff
    return values


def main() -> None:
    rows = []
    for city, meta in CITIES.items():
        for year, (total, shares) in meta["years"].items():
            values = split_total(total, shares)
            for category, value in zip(CATEGORIES, values):
                rows.append(
                    {
                        "year": year,
                        "country": meta["country"],
                        "city": city,
                        "group": "城市居民",
                        "category": category,
                        "per_capita_expenditure": value,
                        "currency": meta["currency"],
                        "price_basis": "nominal_local",
                        "classification": "COICOP-8-proxy",
                        "data_level": "city",
                        "sample_size": meta["sample"],
                        "data_type": "模拟",
                        "source": "模拟数据（基于 OECD/World Bank 结构校准）",
                        "note": "仅用于方法演示，不代表真实统计；PPP 因子为模拟值",
                        "ppp_factor": meta["ppp_factor"],
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
