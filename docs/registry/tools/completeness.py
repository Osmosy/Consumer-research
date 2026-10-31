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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import matching  # noqa: E402

REPO = Path.home() / "projects" / "consumer-research"
FACTS = REPO / "docs/registry/page_facts.json"
CHECKS = REPO / "reviews/2026-10-25-inkofood/checks/checks.csv"
WAIVERS = REPO / "docs/registry/waivers.json"
OUT = REPO / "docs/registry/completeness.json"


def numbers(text: str) -> set[str]:
    return matching.numbers(text)


def main() -> int:
    facts = json.loads(FACTS.read_text("utf-8"))["decks"]
    waivers = json.loads(WAIVERS.read_text("utf-8")) if WAIVERS.exists() else {}
    rows = list(csv.DictReader(CHECKS.open(encoding="utf-8")))

    checks_by_deck: dict[str, list[str]] = {}
    for row in rows:
        slug = row["ref"].split(",")[0].strip()
        checks_by_deck.setdefault(slug, []).append(f"{row['claim']} {row['value']} {row['fact']}")

    report = {"decks": {}, "totals": {}}
    totals = {"used": 0, "unused": 0, "waived": 0, "used_elsewhere": 0}
    for slug, deck in facts.items():
        texts = checks_by_deck.get(slug, [])
        used, unused, waived, elsewhere = [], [], [], []
        for page_key, page in deck["pages"].items():
            page_number = int(page_key)
            for fact in page.get("facts", []):
                if not fact.get("verified"):
                    continue
                value = (fact.get("value") or "").replace(".", ",")
                item = {"page": page_number, "label": fact["label"], "value": fact["value"]}
                waiver_key = f"{slug}|{page_number}|{value}"
                if waivers.get(waiver_key):
                    item["reason"] = waivers[waiver_key]
                    waived.append(item)
                elif any(matching.score(fact["label"], text) >= 0.34 for text in texts):
                    used.append(item)
                elif any(matching.numbers(value) & matching.numbers(text) for text in texts):
                    elsewhere.append(item)
                else:
                    unused.append(item)
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
