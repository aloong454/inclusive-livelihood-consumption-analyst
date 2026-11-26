#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 8 条关键口径/合规规则是否已写入 SKILL 文档。

这是“规则覆盖检查”，不是模型行为测试：
- 它证明规则被写进了可执行说明；
- 它不证明模型在每一次生成中都遵守规则。

运行：
    python scripts/test_rule_coverage.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "rule_coverage.json"

DOCS = [
    ROOT / "SKILL.md",
    ROOT / "references" / "indicator-system.md",
    ROOT / "references" / "compliance-guardrails.md",
    ROOT / "references" / "analysis-playbook.md",
    ROOT / "references" / "report-template.md",
    ROOT / "assets" / "demo_questions.md",
    ROOT / "assets" / "eval_rubric.md",
]

RULES = [
    ("同比/环比", ["同比", "环比"]),
    ("名义/实际", ["名义", "实际"]),
    ("占比/百分点", ["占比", "百分点"]),
    ("总计/分项", ["总计", "分项"]),
    ("个人授信", ["个人授信", "授信决策"]),
    ("敏感属性", ["敏感属性"]),
    ("过度借贷", ["过度借贷", "诱导"]),
    ("人工复核", ["人工复核"]),
]


def main() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOCS if path.exists())

    checks = []
    for name, keywords in RULES:
        hits = [keyword for keyword in keywords if keyword in text]
        checks.append(
            {
                "rule": name,
                "keywords": keywords,
                "hits": hits,
                "passed": len(hits) == len(keywords),
            }
        )

    passed = sum(1 for item in checks if item["passed"])
    payload = {
        "check_type": "documentation_coverage",
        "note": "只证明规则写入文档，不证明模型行为；行为测试需另做红队评估。",
        "total": len(checks),
        "passed": passed,
        "checks": checks,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    for index, item in enumerate(checks, start=1):
        mark = "PASS" if item["passed"] else "FAIL"
        print(f"{index:02d} [{mark}] {item['rule']} -> {', '.join(item['hits']) or '缺失'}")
    print(f"\n{passed}/{len(checks)} covered -> {OUT}")
    if passed != len(checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
