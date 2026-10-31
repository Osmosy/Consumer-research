"""Применяет решения по фактам: справочно / в выводы.

Пишет три вещи:
  docs/facts/fact_decisions.json      — решение по каждому факту с причиной;
  reviews/.../APPENDIX-INFO.md        — приложение «Справочно» (туда смотрит предикат для info);
  docs/registry/dispositions.json     — решения по требованиям (для apply_dispositions.py).

Решение по факту и решение по требованию — разные слои: факт может быть справочным, не
становясь требованием вовсе.
"""
import json
import re
import sys
from pathlib import Path

REPO = Path.home() / "projects" / "consumer-research"
FACTS = REPO / "docs/facts/facts.jsonl"
DECISIONS = REPO / "docs/facts/fact_decisions.json"
APPENDIX = REPO / "reviews/2026-10-25-inkofood/APPENDIX-INFO.md"
DISPOSITIONS = REPO / "docs/registry/dispositions.json"
REQUIREMENTS = REPO / "docs/requirements-registry.jsonl"
BY = "заказчик 31.10.2026"

# fact_id -> (решение, причина)
PLAN = {
    # пять расхождений: модели разошлись, решено «справочно»
    "F-2f12ca1c781b": ("info", "белорусский дубль показателя «перекус» (РФ 54,8 % уже обязательство)"),
    "F-bd8a8f55ce4f": ("info", "шестая строка проблем упаковки; тему закрывают 34 % и 28 %"),
    "F-a0b85637b0de": ("info", "мелкий конкурент в РБ после Брестского 33,5 %"),
    "F-0d723aa1d297": ("info", "нишевая претензия к названию в тесте ассоциаций"),
    "F-31adf778c2a0": ("info", "нишевая ассоциация названия, деталь теста"),
    # одно расхождение: оставляем в выводах
    "F-7ef3e8371c46": ("conclusions", "доминирующий бренд в РБ: знают 89 %, покупают 66,5 %"),
    # стратификация доходов = профиль выборки, а не поведение в категории
    "F-20e7ce2a328f": ("info", "профиль выборки: доля 2,3 %"),
    "F-6e3a3079b57f": ("info", "профиль выборки: вещи длительного пользования 27,3 %"),
    "F-a4c695c14522": ("info", "профиль выборки: дорогие покупки 4,8 %"),
}


def load_facts() -> dict[str, dict]:
    rows = {}
    for line in FACTS.read_text("utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["fact_id"]] = row
    return rows


def requirements_by_text() -> dict[str, str]:
    """raw_text требования → req_id (последняя ревизия)."""
    latest = {}
    for line in REQUIREMENTS.read_text("utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            latest[record["req_id"]] = record
    return {record["raw_text"].strip(): rid for rid, record in latest.items()}


def row_text(deck: str, label: str, value: str) -> str:
    """Дословная строка таблицы колоды, в которой стоит факт."""
    path = REPO / f"decks/{deck}/{deck}.md"
    text = path.read_text("utf-8")
    wanted_label = label.strip()
    wanted_value = value.strip()
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        if wanted_label[:40] in line and wanted_value.rstrip(" %") in line:
            return line.strip()
    return ""


def main() -> int:
    facts = load_facts()
    reqs = requirements_by_text()
    decisions: dict[str, dict] = {}
    dispositions: dict[str, dict] = {}
    missing = []

    for fid, (target, reason) in PLAN.items():
        fact = facts.get(fid)
        if not fact:
            missing.append(f"{fid}: нет в каноне")
            continue
        text = row_text(fact["deck"], fact["label"], fact["value"])
        req_id = reqs.get(text) if text else None
        decisions[fid] = {
            "target": target,
            "reason": reason,
            "deck": fact["deck"],
            "page": fact["page"],
            "label": fact["label"],
            "value": fact["value"],
            "req_id": req_id,
        }
        if req_id:
            dispositions[req_id] = {"target": target, "reason": reason, "by": BY}
        else:
            missing.append(f"{fid}: требования нет (факт остаётся только фактом)")

    DECISIONS.write_text(json.dumps(decisions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DISPOSITIONS.write_text(json.dumps(dispositions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    info_rows = [(fid, d) for fid, d in decisions.items() if d["target"] == "info"]
    print(f"решений по фактам: {len(decisions)} (справочно {len(info_rows)}, "
          f"в выводы {len(decisions) - len(info_rows)}); требований затронуто: {len(dispositions)}")
    for note in missing:
        print("  ", note)
    print(f"→ {DECISIONS.relative_to(REPO)}, {DISPOSITIONS.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
