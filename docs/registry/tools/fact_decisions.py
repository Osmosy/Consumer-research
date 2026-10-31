"""Лист решений по обязательствам: куда идёт каждый факт.

Колонки: REQ, страница, факт, значение, есть ли уже в выводах, рекомендация агента,
решение (заполняет человек: выводы / справочно / снять).

Рекомендация — эвристика, а не заключение: потребительские предпочтения идут в выводы,
фоновые числа (уровни жизни, бренды, «не ассоциируется») — справочно.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path.home() / "projects" / "consumer-research"
CHECKER = REPO / "docs/registry/checkers/check_fact_in_conclusions.py"
OUT = REPO / "docs/registry/fact_decisions.md"
REGISTRY = REPO / "docs/requirements-registry.jsonl"
SPANS = REPO / "docs/registry/spans.jsonl"
BACKGROUND = re.compile(
    r"денег хватает|дорогие покупки|мясокомбинат|не подходит|не ассоциируется|"
    r"подарками|вещей длительного",
    re.I,
)


def in_conclusions(req_id: str) -> bool:
    proc = subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(REPO), "--transition", req_id],
        capture_output=True, text=True, timeout=120,
    )
    return proc.returncode == 0


def main() -> int:
    span_pages = {}
    for line in SPANS.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        span = json.loads(line)
        span_pages[(span["file"], tuple(span["span"]))] = span.get("page")

    latest = {}
    for line in REGISTRY.read_text("utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            latest[record["req_id"]] = record

    rows = []
    for req_id in sorted((rid for rid in latest if rid >= "REQ-0004"), key=lambda r: int(r.split("-")[1])):
        record = latest[req_id]
        cells = [c.strip() for c in record["raw_text"].strip().strip("|").split("|")]
        label = cells[0] if cells else record["raw_text"].strip()
        value = cells[1] if len(cells) > 1 else ""
        page = span_pages.get((record["source"]["file"], tuple(record["source"]["span"])), "—")
        found = in_conclusions(req_id)
        if found:
            recommendation = "оставить"
        elif BACKGROUND.search(label):
            recommendation = "справочно"
        else:
            recommendation = "в выводы"
        rows.append((req_id, page, label, value, "да" if found else "нет", recommendation))

    lines = [
        "# Решения по обязательствам выводов",
        "",
        "Каждая строка — факт, признанный обязательным (решение заказчика 31.10.2026).",
        "Решение: `выводы` — факт обязан быть в выводах; `справочно` — факт обозначен в",
        "приложении «Справочно» и в выводы не идёт; `снять` — малозначим, обязательство",
        "снимается с причиной.",
        "",
        "| REQ | стр. | факт | значение | в выводах | рекомендация | решение |",
        "|---|---|---|---|---|---|---|",
    ]
    for req_id, page, label, value, found, recommendation in rows:
        clean = label.replace("|", "\\|")[:80]
        lines.append(f"| {req_id} | {page} | {clean} | {value} | {found} | {recommendation} |  |")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    counts: dict[str, int] = {}
    for row in rows:
        counts[row[5]] = counts.get(row[5], 0) + 1
    print(f"строк: {len(rows)} → {OUT.relative_to(REPO)}")
    print("рекомендации:", counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
