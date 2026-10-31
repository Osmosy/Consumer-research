"""Предикат перехода «утверждение агента → страница колоды».

Проверяет только числовую часть вердикта `подтв.` — «значение найдено»:
заявленное число должно буквально присутствовать на цитируемой странице.
Смысл утверждения этот предикат не проверяет и не может: `искаж.` тоже
проходит числовую проверку, поэтому смысловая часть требует отдельного
инварианта с defeater, а не этой проверки.

Протокол: JSON {"ok": bool, "detail": str} в stdout, код выхода 0/1.
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

CHECKS = Path("reviews/2026-10-25-inkofood/checks/checks.csv")
PAGE_HEADING = re.compile(r"(?m)^##\s+(?:Слайд|Slide)\s+(\d+)")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def page_text(root: Path, slug: str, page: int) -> str | None:
    path = root / "decks" / slug / f"{slug}.md"
    if not path.is_file():
        return None
    text = path.read_text("utf-8")
    marks = [(int(m.group(1)), m.start()) for m in PAGE_HEADING.finditer(text)]
    for index, (number, start) in enumerate(marks):
        if number == page:
            end = marks[index + 1][1] if index + 1 < len(marks) else len(text)
            return text[start:end]
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--transition", required=True, help="id строки checks.csv")
    args = parser.parse_args()
    root = Path(args.root)

    path = root / CHECKS
    if not path.is_file():
        print(json.dumps({"ok": False, "detail": f"нет {CHECKS}"}, ensure_ascii=False))
        return 1
    rows = {row["id"].strip(): row for row in csv.DictReader(path.open(encoding="utf-8"))}
    row = rows.get(args.transition.strip())
    if row is None:
        print(json.dumps({"ok": False, "detail": f"проверки {args.transition} нет в checks.csv"}, ensure_ascii=False))
        return 1

    ref = row["ref"]
    slug = ref.split(",")[0].strip()
    cited = [int(x) for x in re.findall(r"\d+", ref.split("page=")[-1])] if "page=" in ref else []
    pages = [page_text(root, slug, page) for page in cited]
    if not cited or any(text is None for text in pages):
        print(json.dumps({"ok": False, "detail": f"страницы {cited} нет в {slug}"}, ensure_ascii=False))
        return 1

    numbers = {n.replace(".", ",") for n in NUMBER.findall(f"{row['value']} {row['fact']}")}
    if not numbers:
        print(json.dumps({"ok": False, "detail": "в проверке нет чисел — числовой предикат неприменим"}, ensure_ascii=False))
        return 1

    blob = " ".join(text for text in pages if text).replace(".", ",")
    found = sorted(number for number in numbers if number in blob)
    if found:
        detail = f"на стр. {cited} колоды {slug}: {', '.join(found[:5])}"
        print(json.dumps({"ok": True, "detail": detail}, ensure_ascii=False))
        return 0
    detail = f"ни одно из {sorted(numbers)[:5]} не найдено на стр. {cited} колоды {slug}"
    print(json.dumps({"ok": False, "detail": detail}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    sys.exit(main())
