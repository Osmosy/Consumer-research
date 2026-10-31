"""Предикат для вычисляемых значений: сумма по панелям страницы.

Проверка 14 заявляет 30 % (calc) для оценок 9–10. На странице 53 две панели (РФ и РБ),
и «30,3 %» — это сумма 9,5 + 20,8 по панели РФ; по РБ та же сумма даёт 22,6 %. Предикат
считает сумму по каждой панели и подтверждает утверждение, если хотя бы одна панель
сходится с заявленным числом; в detail пишет, какая панель и что в остальных.

Протокол: JSON {"ok": bool, "detail": str}, код выхода 0/1.
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

CHECKS = Path("reviews/2026-10-25-inkofood/checks/checks.csv")
PAGE_HEADING = re.compile(r"(?m)^##\s+(?:Слайд|Slide)\s+(\d+)")
PANEL = re.compile(r"(?m)^###\s+(.+)$")
ROW = re.compile(r"(?m)^\|\s*(\d+)\s*\|\s*([\d]+(?:[.,]\d+)?)\s*%?\s*\|")
TARGET = ("9", "10")


def page_body(root: Path, slug: str, page: int) -> str | None:
    path = root / "decks" / slug / f"{slug}.md"
    if not path.is_file():
        return None
    text = path.read_text("utf-8")
    marks = [(int(m.group(1)), m.start()) for m in PAGE_HEADING.finditer(text)]
    for index, (number, start) in enumerate(marks):
        if number == page:
            return text[start : marks[index + 1][1] if index + 1 < len(marks) else len(text)]
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--transition", required=True)
    args = parser.parse_args()
    root = Path(args.root)

    rows = {row["id"].strip(): row for row in csv.DictReader((root / CHECKS).open(encoding="utf-8"))}
    row = rows.get(args.transition.strip())
    if row is None:
        print(json.dumps({"ok": False, "detail": "проверки нет в checks.csv"}, ensure_ascii=False))
        return 1
    claim_numbers = [float(n.replace(",", ".")) for n in re.findall(r"\d+(?:[.,]\d+)?", row["fact"])]
    if not claim_numbers:
        print(json.dumps({"ok": False, "detail": "в строке нет числа для сверки"}, ensure_ascii=False))
        return 1
    target = claim_numbers[0]

    slug = row["ref"].split(",")[0].strip()
    pages = [int(x) for x in re.findall(r"\d+", row["ref"].split("page=")[-1])] if "page=" in row["ref"] else []
    for page in pages:
        body = page_body(root, slug, page)
        if body is None:
            continue
        chunks = PANEL.split(body)
        panels = []
        for index in range(1, len(chunks) - 1, 2):
            name = chunks[index].strip()
            values = {num: float(value.replace(",", ".")) for num, value in ROW.findall(chunks[index + 1])}
            if all(key in values for key in TARGET):
                panels.append((name, values[TARGET[0]] + values[TARGET[1]]))
        if not panels:
            continue
        hits = [(name, total) for name, total in panels if abs(total - target) <= 0.25]
        detail = "; ".join(f"{name}: {total:.1f} %" for name, total in panels)
        if hits:
            print(json.dumps({"ok": True, "detail": f"стр. {page}: сходится {hits[0][0]} — {hits[0][1]:.1f} % "
                                                    f"(заявлено {target}); остальные панели {detail}"},
                             ensure_ascii=False))
            return 0
        print(json.dumps({"ok": False, "detail": f"стр. {page}: ни одна панель не даёт {target} ({detail})"},
                         ensure_ascii=False))
        return 1
    print(json.dumps({"ok": False, "detail": "страница с панелями не найдена"}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    sys.exit(main())
