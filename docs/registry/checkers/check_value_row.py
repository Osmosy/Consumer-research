"""Предикат: заявленное значение стоит в строке с тем же показателем.

Числовая проверка отвечает «число есть на странице», но не отвечает «оно про то,
о чём говорит агент». Здесь проверяется строка: на цитируемой странице должно
найтись место, где рядом с числом стоит показатель из `row_labels.json`.

Показатель — дословная подстрока подписи строки/панели. Если подпись подобрана
неверно, строка не найдётся и проверка провалится: подделка подписи не проходит.

Протокол: JSON {"ok": bool, "detail": str} в stdout, код выхода 0/1.
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

CHECKS = Path("reviews/2026-10-25-inkofood/checks/checks.csv")
LABELS = Path("docs/registry/row_labels.json")
PAGE_HEADING = re.compile(r"(?m)^##\s+(?:Слайд|Slide)\s+(\d+)")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def page_lines(root: Path, slug: str, page: int) -> list[str] | None:
    path = root / "decks" / slug / f"{slug}.md"
    if not path.is_file():
        return None
    text = path.read_text("utf-8")
    marks = [(int(m.group(1)), m.start()) for m in PAGE_HEADING.finditer(text)]
    for index, (number, start) in enumerate(marks):
        if number == page:
            end = marks[index + 1][1] if index + 1 < len(marks) else len(text)
            body = text[start:end]
            lines = body.splitlines()
            if lines and lines[0].startswith("##"):
                lines[0] = re.sub(r"^##\s+(?:Слайд|Slide)\s+\d+\s*[—–-]?\s*", "", lines[0])
            return [line for line in lines if not line.strip().startswith("<a id=")]
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--transition", required=True)
    args = parser.parse_args()
    root = Path(args.root)

    labels_path = root / LABELS
    if not labels_path.is_file():
        print(json.dumps({"ok": False, "detail": f"нет {LABELS}"}, ensure_ascii=False))
        return 1
    labels = json.loads(labels_path.read_text("utf-8"))
    entry = labels.get(args.transition.strip())
    if not isinstance(entry, dict) or not entry.get("label"):
        print(json.dumps({"ok": False, "detail": "показатель для проверки не размечен"}, ensure_ascii=False))
        return 1

    checks_path = root / CHECKS
    rows = {row["id"].strip(): row for row in csv.DictReader(checks_path.open(encoding="utf-8"))}
    row = rows.get(args.transition.strip())
    if row is None:
        print(json.dumps({"ok": False, "detail": "проверки нет в checks.csv"}, ensure_ascii=False))
        return 1

    ref = row["ref"]
    slug = ref.split(",")[0].strip()
    cited = [int(x) for x in re.findall(r"\d+", ref.split("page=")[-1])] if "page=" in ref else []
    label = entry["label"].strip().lower()
    numbers = {n.replace(".", ",") for n in NUMBER.findall(f"{row['value']} {row['fact']}")}
    if not numbers:
        print(json.dumps({"ok": False, "detail": "в проверке нет чисел"}, ensure_ascii=False))
        return 1

    for page in cited:
        lines = page_lines(root, slug, page)
        if lines is None:
            continue
        hits = [line for line in lines if label in line.lower()]
        for line in hits:
            normalized = line.replace(".", ",")
            found = sorted(n for n in numbers if n in normalized)
            if found:
                print(
                    json.dumps(
                        {
                            "ok": True,
                            "detail": f"стр. {page} {slug}: «{line.strip()[:120]}» содержит {found[:3]}",
                        },
                        ensure_ascii=False,
                    )
                )
                return 0
        if hits:
            print(
                json.dumps(
                    {"ok": False, "detail": f"стр. {page}: строка «{hits[0].strip()[:120]}» без заявленных чисел"},
                    ensure_ascii=False,
                )
            )
            return 1
    print(
        json.dumps({"ok": False, "detail": f"показатель «{label}» не найден на стр. {cited} {slug}"}, ensure_ascii=False)
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
