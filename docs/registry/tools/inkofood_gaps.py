"""Шаг 1: какие из «неиспользованных» фактов inkofood действительно пропущены.

Сопоставление по подписям (tools/matching.py), а не по номеру страницы: одна и та же
строка стоит на двух слайдах, и совпадение числа ничего не доказывает.
Пишет docs/registry/inkofood_gaps.json: covered / gaps.
"""
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import matching  # noqa: E402

REPO = Path.home() / "projects" / "consumer-research"
FACTS = REPO / "docs/registry/page_facts.json"
LABELS = REPO / "docs/registry/row_labels.json"
CHECKS = REPO / "reviews/2026-10-25-inkofood/checks/checks.csv"
OUT = REPO / "docs/registry/inkofood_gaps.json"
TOPIC = re.compile(
    r"мяс|колбас|деликатес|гастроном|сосиск|паштет|ветчин|полуфабрикат|"
    r"покуп|цен[аыу]|упаковк|вкус|белок|состав|рацион|потребител",
    re.I,
)


def main() -> int:
    facts = json.loads(FACTS.read_text("utf-8"))["decks"]["inkofood-2026"]["pages"]
    labels = json.loads(LABELS.read_text("utf-8"))
    rows = {row["id"].strip(): row for row in csv.DictReader(CHECKS.open(encoding="utf-8"))}

    reference = []
    for rid, entry in labels.items():
        row = rows.get(rid)
        if row:
            reference.append({"id": rid, "label": entry["label"], "page": entry.get("page"),
                              "text": f"{row['claim']} {row['value']} {row['fact']}"})

    covered, gaps = [], []
    for page in facts.values():
        for fact in page.get("facts", []):
            if not fact.get("verified") or not TOPIC.search(fact["label"]):
                continue
            best, best_score = None, 0.0
            for ref in reference:
                hit, value = matching.same_fact(fact["label"], fact["value"], ref["label"], ref["text"])
                if value > best_score:
                    best, best_score = ref, value
                    best_hit = hit
            item = {"page": page["page"], "cited": page.get("cited", False),
                    "label": fact["label"], "value": fact["value"],
                    "best_id": best["id"] if best else None,
                    "best_label": best["label"] if best else None,
                    "best_page": best["page"] if best else None,
                    "score": best_score}
            (covered if best and best_hit else gaps).append(item)

    covered.sort(key=lambda item: item["page"])
    gaps.sort(key=lambda item: item["page"])
    OUT.write_text(json.dumps({"covered": covered, "gaps": gaps}, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    print(f"по теме: покрыто {len(covered)}, пропущено {len(gaps)}")
    for item in gaps:
        print(f"  стр.{item['page']}: {item['label'][:60]} = {item['value']}  "
              f"(ближайшее {item['score']} → проверка {item['best_id']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
