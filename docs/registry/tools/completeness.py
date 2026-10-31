"""Сопоставление фактов корпуса с проверками: что использовано, что нет.

Факт считается использованным, если есть проверка, которая цитирует ту же колоду и ту же
страницу и несёт то же число. Числа сравниваются в нормализованном виде (точка → запятая),
подписи не сравниваются: у агента и у колоды они сформулированы по-разному.

Пишет docs/registry/completeness.json:
  per deck: used, unused, waived, used_elsewhere (число есть в проверке, но на другой странице)
Отказываемые факты берутся из waivers.json — «этот факт мы сознательно не проверяем».
"""
import csv
import json
import re
import sys
from pathlib import Path

REPO = Path.home() / "projects" / "consumer-research"
FACTS = REPO / "docs/registry/page_facts.json"
CHECKS = REPO / "reviews/2026-10-25-inkofood/checks/checks.csv"
WAIVERS = REPO / "docs/registry/waivers.json"
OUT = REPO / "docs/registry/completeness.json"
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def numbers(text: str) -> set[str]:
    return {n.replace(".", ",") for n in NUMBER.findall(text or "")}


def main() -> int:
    facts = json.loads(FACTS.read_text("utf-8"))["decks"]
    waivers = json.loads(WAIVERS.read_text("utf-8")) if WAIVERS.exists() else {}
    rows = list(csv.DictReader(CHECKS.open(encoding="utf-8")))

    by_page: dict[tuple[str, int], set[str]] = {}
    by_number: dict[tuple[str, str], set[int]] = {}
    for row in rows:
        slug = row["ref"].split(",")[0].strip()
        pages = [int(x) for x in re.findall(r"\d+", row["ref"].split("page=")[-1])] if "page=" in row["ref"] else []
        values = numbers(f"{row['value']} {row['fact']}")
        for page in pages:
            by_page.setdefault((slug, page), set()).update(values)
        for value in values:
            by_number.setdefault((slug, value), set()).update(pages)

    report = {"decks": {}, "totals": {}}
    totals = {"used": 0, "unused": 0, "waived": 0, "used_elsewhere": 0}
    for slug, deck in facts.items():
        used, unused, waived, elsewhere = [], [], [], []
        for page_key, page in deck["pages"].items():
            page_number = int(page_key)
            for fact in page.get("facts", []):
                if not fact.get("verified"):
                    continue
                value = (fact.get("value") or "").replace(".", ",")
                key = f"{slug}#{page_number}#{value}"
                if value in by_page.get((slug, page_number), set()):
                    used.append({"page": page_number, "label": fact["label"], "value": fact["value"]})
                elif waivers.get(f"{slug}|{page_number}|{value}"):
                    waived.append({"page": page_number, "label": fact["label"], "value": fact["value"],
                                   "reason": waivers[f"{slug}|{page_number}|{value}"]})
                elif by_number.get((slug, value)):
                    elsewhere.append({"page": page_number, "label": fact["label"], "value": fact["value"],
                                      "cited_pages": sorted(by_number[(slug, value)])})
                else:
                    unused.append({"page": page_number, "label": fact["label"], "value": fact["value"]})
                del key
        report["decks"][slug] = {
            "used": len(used), "unused": len(unused), "waived": len(waived),
            "used_elsewhere": len(elsewhere),
            "unused_examples": unused[:12],
            "elsewhere_examples": elsewhere[:6],
        }
        for name, bucket in (("used", used), ("unused", unused), ("waived", waived), ("used_elsewhere", elsewhere)):
            totals[name] += len(bucket)
        print(f"{slug}: использовано {len(used)}, не использовано {len(unused)}, "
              f"отказано {len(waived)}, число есть на другой странице {len(elsewhere)}")
    report["totals"] = totals
    report["totals"]["facts"] = sum(totals.values())
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"итого: {report['totals']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
