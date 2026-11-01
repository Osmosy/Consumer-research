"""Предикат обязательства, версия 2: факт отражён в выводах — по основам слов.

Отличие от версии 1: подпись факта ищется не дословно, а по основам значимых слов в одном
предложении вывода, и число факта должно стоять в том же предложении. Пересказ
(«больше мяса» вместо «высокое содержание мяса») больше не даёт ложного провала, а
«похожие слова без числа» — ложной приёмки.

Протокол тот же: JSON {"ok": bool, "detail": str}, код выхода 0/1.
Версия предиката — 4 (в реестре инварианты версии 1–3 указывают на прежний чекер).

Порог и стоп-слова: docs/facts/config.json → match.min_share, match.stopwords.
"""
import argparse
import json
import re
import sys
from pathlib import Path

try:
    import snowballstemmer
except ModuleNotFoundError:
    print(json.dumps({"ok": False, "detail": "нет snowballstemmer — pip install snowballstemmer"},
                     ensure_ascii=False))
    raise SystemExit(1)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import dispositions  # noqa: E402

CHECKER_VERSION = "5"
REGISTRY = Path("docs/requirements-registry.jsonl")
CONFIG = Path("docs/facts/config.json")
CONCLUSIONS = (
    "reviews/2026-10-25-inkofood/AGENT-REVIEW.md",
    "reviews/2026-10-25-inkofood/README.md",
    "reviews/2026-10-25-inkofood/summary",
    "reviews/2026-10-25-inkofood/agents",
)
INFO = ("reviews/2026-10-25-inkofood/APPENDIX-INFO.md",)
CELL = re.compile(r"\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
WORD = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+")
SENTENCE = re.compile(r"(?<=[.!?])\s+|\n{2,}")
STEMMER = snowballstemmer.stemmer("russian")
DEFAULT_STOP = ("и", "в", "во", "на", "с", "со", "по", "для", "из", "от", "до", "к", "ко", "о",
                "об", "не", "ни", "что", "как", "это", "при", "или", "а", "но", "у", "же", "бы",
                "за", "более", "менее", "также", "только", "если", "то", "их", "его", "её",
                "все", "весь", "который", "которая", "которые", "быть", "есть", "был", "была",
                "были", "может")


def norm(text: str) -> str:
    return str(text).lower().replace("ё", "е")


def stems(text: str, stopwords) -> list[str]:
    stop = {norm(word) for word in stopwords}
    out: list[str] = []
    for word in WORD.findall(norm(text)):
        if word in stop or word.isdigit():
            continue
        stem = STEMMER.stemWord(word)
        if len(stem) >= 3 and stem not in out:
            out.append(stem)
    return out


def numbers(text: str) -> set[str]:
    return {value.replace(",", ".") for value in NUMBER.findall(norm(text))}


MARKER_WORDS = ("рб", "беларус", "🇧🇾")


def marker_required(root: Path, req_id: str) -> bool:
    """Нужен ли маркер панели: требование в списке исключений с пометкой в причине."""
    path = root / "docs/facts/config.json"
    if not path.is_file():
        return False
    try:
        config = json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError:
        return False
    for entry in config.get("owner_exceptions") or []:
        if isinstance(entry, dict) and str(entry.get("req_id")) == req_id:
            reason = str(entry.get("reason") or "").lower()
            return "пометк" in reason or "маркер" in reason
    return False


def has_marker(sentence: str, aliases: dict[str, list[str]]) -> bool:
    words = [str(word).lower() for word in (aliases.get("РБ") or [])] + list(MARKER_WORDS)
    text = sentence.lower()
    return any(word and word in text for word in words)


def load_panel_aliases(root: Path) -> dict[str, list[str]]:
    path = root / "docs/facts/config.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text("utf-8")).get("panel_aliases") or {}
    except json.JSONDecodeError:
        return {}


def load_settings(root: Path) -> tuple[float, tuple]:
    path = root / CONFIG
    if not path.is_file():
        return 0.6, DEFAULT_STOP
    body = json.loads(path.read_text("utf-8")).get("match", {})
    return float(body.get("min_share", 0.6)), tuple(body.get("stopwords", DEFAULT_STOP))


def strip_tables(text: str) -> str:
    """Таблицы не выводы: строка таблицы перечисляет факт, а не объясняет его.

    Без этого правила факт «находится» в сводной таблице фактов и у самого себя.
    """
    blocks = re.split(r"\n\s*\n", text)
    return "\n\n".join(block for block in blocks
                        if not any(line.lstrip().startswith("|") for line in block.splitlines()))


def units(text: str, allow_tables: bool) -> list[str]:
    """Единицы сравнения: предложения прозы, а в приложении — ещё и строки таблицы.

    Приложение «Справочно» само является таблицей, и её строка — законное место факта.
    В выводах строка сводной таблицы фактом не является: она его перечисляет, а не объясняет.
    """
    if allow_tables:
        return [line.strip() for line in text.splitlines() if line.strip()]
    return [part for part in SENTENCE.split(strip_tables(text)) if part.strip()]


def find_fact(text: str, label: str, fact_numbers: set[str], min_share: float,
              stopwords, allow_tables: bool = False, need_marker: bool = False,
              aliases: dict[str, list[str]] | None = None) -> tuple[bool, str]:
    """Ищем единицу текста, где доля основ подписи не ниже порога и есть число факта.

    Факт без числа проверяется дословно, как в версии 1: основы без числа слишком легко
    совпадают с методическим текстом («вердикты: подтв. — значение найдено»).
    """
    if not fact_numbers:
        ok = norm(label) in norm(text)
        return ok, ("подпись найдена дословно" if ok else "подписи нет дословно")

    wanted = stems(label, stopwords)
    if not wanted:
        return False, "в подписи не осталось значимых слов"
    best = (0.0, False, "", [])
    for raw in units(text, allow_tables):
        sentence = raw.strip()
        if not sentence:
            continue
        have = set(stems(sentence, stopwords))
        found = [stem for stem in wanted if stem in have]
        share = len(found) / len(wanted)
        number_ok = (not fact_numbers) or bool(fact_numbers & numbers(sentence))
        if need_marker and not has_marker(sentence, aliases or {}):
            if (share, number_ok) > (best[0], best[1]):
                best = (share, number_ok, sentence[:120], ["маркер панели"])
            continue
        if share >= min_share and number_ok:
            return True, f"основы {found} и число {sorted(fact_numbers & numbers(sentence))} в предложении: «{sentence[:120]}»"
        if (share, number_ok) > (best[0], best[1]):
            missing = [stem for stem in wanted if stem not in have]
            best = (share, number_ok, sentence[:120], missing)
    return False, (f"лучшее предложение дало долю основ {best[0]:.2f} (нужно {min_share}), "
                   f"число {'есть' if best[1] else 'не найдено'}, не хватило основ {best[3]}: "
                   f"«{best[2]}»")


def load_record(root: Path, req_id: str) -> dict | None:
    path = root / REGISTRY
    if not path.is_file():
        return None
    latest = None
    for line in path.read_text("utf-8").splitlines():
        if line.strip():
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
    req = args.transition.strip()

    record = load_record(root, req)
    if record is None:
        print(json.dumps({"ok": False, "detail": f"нет {req} в реестре"}, ensure_ascii=False))
        return 1

    cells = CELL.findall(record.get("raw_text", ""))
    if cells:
        label = cells[0][0].strip()
        fact_numbers = numbers(" ".join(cell[1] for cell in cells))
    else:
        label, fact_numbers = "", set()
        for line in record.get("raw_text", "").splitlines():
            stripped = line.strip()
            if len(stripped) > 12 and NUMBER.search(stripped) and not stripped.startswith(("#", ">", "<")):
                label = stripped[:120]
                fact_numbers = numbers(stripped)
                break
        if not label:
            label = record.get("raw_text", "").strip()[:120]
    if not label:
        print(json.dumps({"ok": False, "detail": "в строке не нашлось подписи"}, ensure_ascii=False))
        return 1

    target = dispositions.target_of(root, req)
    if target == "waive":
        entry = dispositions.load(root).get(req, {})
        print(json.dumps({"ok": True, "detail": f"обязательство снято: {entry.get('reason', 'без причины')}"},
                         ensure_ascii=False))
        return 0

    texts = conclusion_texts(root) if target == "conclusions" else conclusion_texts(root, INFO)
    if not texts:
        where = "текстов выводов нет" if target == "conclusions" else "приложения «Справочно» нет"
        print(json.dumps({"ok": False, "detail": where}, ensure_ascii=False))
        return 1

    min_share, stopwords = load_settings(root)
    need_marker = marker_required(root, req) and target == "conclusions"
    aliases = load_panel_aliases(root)
    notes = []
    for name, text in texts:
        ok, detail = find_fact(text, label, fact_numbers, min_share, stopwords,
                               allow_tables=(target != "conclusions"),
                               need_marker=need_marker, aliases=aliases)
        if ok:
            print(json.dumps({"ok": True, "checker_version": CHECKER_VERSION,
                              "detail": f"факт отражён в {name}: {detail}"}, ensure_ascii=False))
            return 0
        notes.append(f"{name}: {detail}")
    print(json.dumps({"ok": False, "checker_version": CHECKER_VERSION,
                      "detail": f"«{label}» с числом {sorted(fact_numbers)} не найдено по основам — "
                                + " | ".join(notes[:2])}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    sys.exit(main())
