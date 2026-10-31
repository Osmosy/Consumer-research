"""Предикат смысловой половины вердикта: перезапуск записанного опровергателя.

Это не «модель судит смысл». В `falsifiers.json` лежит конкретное наблюдение,
зафиксированное при разборе: если на стр. 42 «без нитритной соли» стоит в
колонке «Маркетинговый ход», утверждение агента о преимуществе опровергается.
Предикат перезапускает именно это наблюдение по тексту колоды.

`ok = true` означает, что опровергатель подтверждается, то есть искажение
действительно есть, а не приписано агенту. Нет записанного опровергателя —
проверять нечем, и это честный `fail`, а не зелёный результат.

Протокол: JSON {"ok": bool, "detail": str} в stdout, код выхода 0/1.
"""
import argparse
import json
import re
import sys
from pathlib import Path

RULES = Path("docs/registry/falsifiers.json")
PAGE_HEADING = re.compile(r"(?m)^##\s+(?:Слайд|Slide)\s+(\d+)")


def page_text(root: Path, slug: str, page: int) -> str | None:
    path = root / "decks" / slug / f"{slug}.md"
    if not path.is_file():
        return None
    text = path.read_text("utf-8")
    marks = [(int(m.group(1)), m.start()) for m in PAGE_HEADING.finditer(text)]
    for index, (number, start) in enumerate(marks):
        if number == page:
            end = marks[index + 1][1] if index + 1 < len(marks) else len(text)
            body = text[start:end]
            body = body.split("\n", 1)[1] if "\n" in body else ""
            # якоря вида <a id="slide-17"></a> несут цифры, но данными не являются
            return "\n".join(
                line for line in body.splitlines() if not line.strip().startswith("<a id=")
            )
    return None


def normalize(text: str) -> str:
    text = text.lower().replace("ё", "е")
    text = re.sub(r"\s+", " ", text)
    return text.replace(".", ",")


def evaluate(root: Path, condition: dict) -> tuple[bool, str]:
    slug = condition["file"]
    page = int(condition["page"])
    body = page_text(root, slug, page)
    if body is None:
        return False, f"нет стр. {page} в {slug}"
    text = normalize(body)
    if "all" in condition:
        missing = [needle for needle in condition["all"] if needle.lower() not in text]
        if missing:
            return False, f"стр. {page} {slug}: нет {missing}"
        return True, f"стр. {page} {slug}: найдено {condition['all']}"
    if "absent_regex" in condition:
        match = re.search(condition["absent_regex"], text)
        if match:
            return False, f"стр. {page} {slug}: найдено «{match.group(0)}» — ожидалось отсутствие"
        return True, f"стр. {page} {slug}: чисел нет"
    return False, "условие без all/absent_regex"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--transition", required=True, help="id строки checks.csv")
    args = parser.parse_args()
    root = Path(args.root)

    path = root / RULES
    if not path.is_file():
        print(json.dumps({"ok": False, "detail": f"нет {RULES}"}, ensure_ascii=False))
        return 1
    rules = json.loads(path.read_text("utf-8"))
    rule = rules.get(args.transition.strip())
    if rule is None:
        print(
            json.dumps(
                {"ok": False, "detail": f"для проверки {args.transition} опровергатель не записан"},
                ensure_ascii=False,
            )
        )
        return 1

    details = []
    confirmed = True
    for condition in rule.get("conditions", []):
        ok, detail = evaluate(root, condition)
        details.append(detail)
        confirmed = confirmed and ok
    payload = {
        "ok": confirmed,
        "detail": ("искажение подтверждается: " if confirmed else "искажение не подтверждается: ")
        + "; ".join(details),
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if confirmed else 1


if __name__ == "__main__":
    sys.exit(main())
