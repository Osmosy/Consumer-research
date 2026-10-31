"""Предикат обязательства: факт колоды отражён в выводах работы.

Требование здесь — не «число есть в колоде» (это доказала бы любая страница), а «факт
учтён в выводах»: иначе заказчик получает стратегию без него. Поэтому предикат ищет
подпись факта и его число в текстах выводов (AGENT-REVIEW.md и материалы агентов), и
падает, если их там нет.

Протокол: JSON {"ok": bool, "detail": str}, код выхода 0/1.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import dispositions  # noqa: E402

REGISTRY = Path("docs/requirements-registry.jsonl")
CONCLUSIONS = (
    "reviews/2026-10-25-inkofood/AGENT-REVIEW.md",
    "reviews/2026-10-25-inkofood/README.md",
    "reviews/2026-10-25-inkofood/summary",
    "reviews/2026-10-25-inkofood/agents",
)
INFO = ("reviews/2026-10-25-inkofood/APPENDIX-INFO.md",)
CELL = re.compile(r"\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def norm(text: str) -> str:
    return text.lower().replace("ё", "е").replace(".", ",")


def load_record(root: Path, req_id: str) -> dict | None:
    path = root / REGISTRY
    if not path.is_file():
        return None
    latest = None
    for line in path.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("req_id") == req_id:
            latest = record
    return latest


def conclusion_texts(root: Path, sources=CONCLUSIONS) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for relative in sources:
        path = root / relative
        if path.is_file():
            out.append((relative, path.read_text("utf-8")))
        elif path.is_dir():
            for item in sorted(path.rglob("*.md")):
                out.append((str(item.relative_to(root)), item.read_text("utf-8")))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--transition", required=True)
    args = parser.parse_args()
    root = Path(args.root)

    record = load_record(root, args.transition.strip())
    if record is None:
        print(json.dumps({"ok": False, "detail": f"нет {args.transition} в реестре"}, ensure_ascii=False))
        return 1

    cells = CELL.findall(record.get("raw_text", ""))
    if cells:
        label = cells[0][0].strip()
        numbers = {n.replace(".", ",") for n in NUMBER.findall(" ".join(c[1] for c in cells))}
    else:
        # спан не строка таблицы: берём первую фразу с числом, иначе текст не станет подписью
        label = ""
        numbers = set()
        for line in record.get("raw_text", "").splitlines():
            stripped = line.strip()
            if len(stripped) > 12 and NUMBER.search(stripped) and not stripped.startswith(("#", ">", "<")):
                label = stripped[:120]
                numbers = {n.replace(".", ",") for n in NUMBER.findall(stripped)}
                break
        if not label:
            label = record.get("raw_text", "").strip()[:120]
    if not label:
        print(json.dumps({"ok": False, "detail": "в строке не нашлось подписи"}, ensure_ascii=False))
        return 1

    target = dispositions.target_of(root, args.transition.strip())
    if target == "waive":
        entry = dispositions.load(root).get(args.transition.strip(), {})
        print(json.dumps({"ok": True,
                          "detail": f"обязательство снято: {entry.get('reason', 'без причины')}"},
                         ensure_ascii=False))
        return 0

    texts = conclusion_texts(root) if target == "conclusions" else conclusion_texts(root, INFO)
    if not texts:
        where = "текстов выводов нет" if target == "conclusions" else "приложения «Справочно» нет"
        print(json.dumps({"ok": False, "detail": where}, ensure_ascii=False))
        return 1

    for name, text in texts:
        body = norm(text)
        if norm(label) in body and any(number in body for number in numbers):
            print(json.dumps({"ok": True, "detail": f"факт отражён в {name}: «{label}»"}, ensure_ascii=False))
            return 0
    print(
        json.dumps(
            {"ok": False, "detail": f"в выводах нет «{label}» с числом из {sorted(numbers)} — не учтено"},
            ensure_ascii=False,
        )
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
