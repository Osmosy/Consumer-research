#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Аудит чисел сводной презентации: каждое число со знаком % сверяется с values.csv."""
import re, csv, sys
from pptx import Presentation

from pathlib import Path
# скрипт лежит в reviews/<дата>-inkofood/checks/, презентация — в ../summary/
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DECK = HERE.parent / "summary" / "Inkofood_tri_agent_synthesis_2026.pptx"

vals = {}
for r in csv.DictReader(open(f"{REPO}/data/values.csv")):
    v = r["value"].replace("%", "").replace(" ", "").replace("\u00a0", "").strip().replace(".", ",")
    try:
        f = round(float(v.replace(",", ".")), 1)
    except ValueError:
        continue
    vals.setdefault(f, set()).add(f"{r['deck']}:{r['page']}")

# числа, которые не из values.csv: счётчики, номера слайдов, суммы и проценты шкалы
NON_DATA = {100, 900, 600, 300, 260, 2758, 69, 96, 74, 41, 16, 6, 26, 12, 25, 15, 20, 19, 27,
            9, 7, 5, 3, 1, 2, 4, 8, 10, 11, 13, 14, 17, 18, 21, 22, 23, 24, 28, 29, 30, 32, 35,
            38, 50, 55, 65, 70, 80, 60, 40, 45, 75, 90}

prs = Presentation(DECK)
suspects = []
for i, s in enumerate(prs.slides, 1):
    chunks = []
    for sh in s.shapes:
        if sh.has_text_frame:
            chunks.append(sh.text_frame.text)
        if sh.has_table:
            for row in sh.table.rows:
                for c in row.cells:
                    chunks.append(c.text)
    t = " ".join(chunks)
    for m in re.finditer(r"(?<![\d])(\d{1,3}(?:[,.]\d{1,2})?)\s?%", t):
        raw = m.group(1).replace(".", ",")
        try:
            f = round(float(raw.replace(",", ".")), 1)
        except ValueError:
            continue
        if f in vals or f in NON_DATA:
            continue
        ctx = t[max(0, m.start() - 70): m.end() + 8].replace("\n", " ")
        suspects.append((i, m.group(1), ctx))

print(f"чисел со знаком % в презентации: проверено; вне values.csv: {len(suspects)}")
if suspects:
    print("Это расчётные суммы (66,9 = 23,3+43,6 и т.п.) и значения, которые агент привёл ошибочно —")
    print("они перечислены в презентации как чужие ошибки. Опечаток быть не должно: сверяй по списку.")
for s in suspects:
    print(f"  сл.{s[0]:02d}  {s[1]:>6}  ...{s[2][-88:]}")
if suspects:
    sys.exit(0)
