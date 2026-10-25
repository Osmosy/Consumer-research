#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка машиночитаемого факт-листа из перечня проверок verify_claims.py.

Вход: verify_claims.py рядом с этим файлом (список C — единственный источник истины).
Выход при --write: facts.csv (подтверждённые факты), facts-rejected.csv (что утверждать нельзя),
facts-summary.json (счёт по колодам и блокам).

Колонки facts.csv:
  id        номер проверки в verify_claims.py
  block     блок (Демография, Драйверы, Бренды, Макро, Продукт, Поколения)
  claim     что утверждал агент
  fact      что стоит в колоде
  value_ru  первое число пары «РФ / РБ», если оно есть в факте
  value_by  второе число пары
  unit      единица измерения (%, п.п.) или пусто
  deck      папка колоды
  page      страница или страницы как в источнике
  verdict   подтв. | подтв.* (число верное, подпись или категория — нет)
  agent     кто из агентов это утверждал (A1 Клод, A2 Грок, A3 Гемини)
  note      оговорка, если вердикт подтв.*

Строки с вердиктом «искаж.» в facts.csv не попадают: они лежат в facts-rejected.csv как запрет.
Порядок строк — как в verify_claims.py, чтобы номера совпадали с checks.csv и приложением A.
"""
import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from verify_claims import C, BLOCK_ORDER  # noqa: E402

PAIR = re.compile(r"(\d+(?:[,.]\d+)?)\s*(?:%|п\.п\.)?\s*/\s*(\d+(?:[,.]\d+)?)")
NUM = re.compile(r"\d+(?:[,.]\d+)?")
REF = re.compile(r"^(?P<deck>[a-z0-9\-]+),\s*page=(?P<page>.+)$")

COLUMNS = ["id", "block", "claim", "fact", "value_ru", "value_by", "unit",
           "pairs", "numbers", "shape", "deck", "page", "page_num", "verdict", "agent", "note"]


def split_ref(ref):
    m = REF.match(ref.strip())
    if not m:
        return ref.strip(), ""
    return m.group("deck"), m.group("page").strip()


def source_text(fact, value):
    """Числа берём из факта; если факт описан словами («совпадает»), то из значения агента —
    при вердикте «подтверждено» они совпадают по определению."""
    has_num = bool(NUM.search(fact)) and not fact.strip().startswith("1 млн")
    return fact if has_num else value


def pairs_of(text):
    return ["%s/%s" % (a, b) for a, b in PAIR.findall(text)]


def numbers_of(text):
    seen, out = set(), []
    for n in NUM.findall(text):
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def rows():
    out = []
    for cid, block, claim, agent, value, fact, ref, verdict in C:
        deck, page = split_ref(ref)
        src = source_text(fact, value)
        pz = pairs_of(src)
        ru, by = (pz[0].split("/") if pz else ("", ""))
        nums = numbers_of(src)
        unit = "%" if "%" in src else ""
        first_page = re.match(r"\d+", page)
        note = ""
        if verdict == "подтв.*":
            note = "число верное, но подпись, страница или категория у агента не те"
        out.append({"id": cid, "block": block, "claim": claim, "fact": fact,
                    "value_ru": ru, "value_by": by, "unit": unit,
                    "pairs": "; ".join(pz), "numbers": ", ".join(nums),
                    "shape": "пара" if pz else ("числа" if nums else "текст"),
                    "deck": deck, "page": page,
                    "page_num": first_page.group(0) if first_page else "",
                    "verdict": verdict,
                    "agent": agent, "note": note})
    return out


def summary(all_rows):
    ok = [r for r in all_rows if r["verdict"] in ("подтв.", "подтв.*")]
    bad = [r for r in all_rows if r["verdict"] == "искаж."]
    by_deck, by_block, by_agent = {}, {}, {}
    for r in ok:
        by_deck[r["deck"]] = by_deck.get(r["deck"], 0) + 1
        by_block[r["block"]] = by_block.get(r["block"], 0) + 1
        by_agent[r["agent"]] = by_agent.get(r["agent"], 0) + 1
    return {
        "проверок всего": len(all_rows),
        "фактов в facts.csv": len(ok),
        "из них дословных": sum(1 for r in ok if r["verdict"] == "подтв."),
        "из них с оговоркой": sum(1 for r in ok if r["verdict"] == "подтв.*"),
        "запретов в facts-rejected.csv": len(bad),
        "строк с парой РФ/РБ": sum(1 for r in ok if r["value_ru"]),
        "по колодам": dict(sorted(by_deck.items(), key=lambda x: -x[1])),
        "по блокам": {b: by_block.get(b, 0) for b in BLOCK_ORDER},
        "по агентам": dict(sorted(by_agent.items())),
        "строк без пары": sum(1 for r in ok if not r["value_ru"]),
        "по форме": {k: sum(1 for r in ok if r["shape"] == k) for k in ("пара", "числа", "текст")},
    }


def write(outdir):
    outdir = Path(outdir)
    all_rows = rows()
    ok = [r for r in all_rows if r["verdict"] in ("подтв.", "подтв.*")]
    bad = [r for r in all_rows if r["verdict"] == "искаж."]
    with open(outdir / "facts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(ok)
    with open(outdir / "facts-rejected.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["id", "block", "claim", "agent", "что говорит колода", "deck", "page"])
        for r in bad:
            w.writerow([r["id"], r["block"], r["claim"], r["agent"], r["fact"], r["deck"], r["page"]])
    (outdir / "facts-summary.json").write_text(
        json.dumps(summary(all_rows), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    s = summary(rows())
    for k, v in s.items():
        if isinstance(v, dict):
            print(f"{k}: " + ", ".join(f"{dk} {dv}" for dk, dv in v.items()))
        else:
            print(f"{k}: {v}")
    if "--write" in sys.argv:
        target = Path(sys.argv[sys.argv.index("--write") + 1]) if len(sys.argv) > sys.argv.index("--write") + 1 else HERE
        write(target)
        print("записаны facts.csv, facts-rejected.csv, facts-summary.json →", target)
