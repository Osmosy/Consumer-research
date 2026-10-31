"""Отбор неиспользованных фактов, близких к вопросу исследования.

Фильтр по словам темы (мясо, колбаса, деликатесы, покупка, цена, упаковка, вкус, состав,
рацион, потребитель). Это не список пропусков: один и тот же факт часто стоит на двух
страницах, и часть «неиспользованных» — дубли уже проверенных строк на соседних слайдах.
"""
import json
import re
import sys
from pathlib import Path

REPO = Path.home() / "projects" / "consumer-research"
FACTS = REPO / "docs/registry/page_facts.json"
OUT = REPO / "docs/registry/unused_relevant.json"
KEY = re.compile(
    r"мяс|колбас|деликатес|гастроном|сосиск|паштет|ветчин|полуфабрикат|покуп|цен[аыу]|"
    r"упаковк|вкус|белок|состав|рацион|потребител",
    re.I,
)


def main() -> int:
    decks = json.loads(FACTS.read_text("utf-8"))["decks"]
    out = {"note": "кандидаты, а не доказанные пропуски; сверять с checks.csv по подписи", "decks": {}}
    total = 0
    for slug, deck in decks.items():
        items = []
        for page in deck["pages"].values():
            for fact in page.get("facts", []):
                if fact.get("verified") and KEY.search(fact["label"]):
                    items.append(
                        {"page": page["page"], "cited": page.get("cited", False),
                         "label": fact["label"], "value": fact["value"]}
                    )
        items.sort(key=lambda item: item["page"])
        out["decks"][slug] = items
        total += len(items)
        print(f"{slug}: {len(items)}")
    out["total"] = total
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"итого по теме: {total} → {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
