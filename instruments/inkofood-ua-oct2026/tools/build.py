#!/usr/bin/env python3
"""Сборка instrument.json из lines.json (pymupdf rawdict), с провенансом page+bbox."""
import json, re, sys, unicodedata

import os
PDF = os.environ.get("INKO_PDF", "/home/lenovo/Загрузки/Маркетинговое исследование Инко Фуд, онлайн панель 900 респондентов.pdf")
SLUG = "inkofood-ua-oct2026"
lines = json.load(open("lines.json"))
for l in lines:
    l["t"] = l["text"].replace("\u200b", "").replace("\u00a0", " ").strip()


def norm(s):
    return re.sub(r"\s+", " ", s.replace("\u200b", "").replace("\u00a0", " ")).strip()


BULLET = "\u25cf"  # ●
TYPE_MAP = [
    ("Одиночный выбор", "single"),
    ("Множественный выбор", "multi"),
    ("Открытый вопрос", "open"),
    ("Шкала", "scale"),
    ("Матрица", "matrix"),
]
RE_BLOCK = re.compile(r"^Блок\s+(\d+)\.\s*(.+)$")
RE_Q = re.compile(r"^(\d{1,2})\.\s+(.+)$")

blocks, questions = [], []
cur_block = None
cur_q = None
buf = []          # accumulating text (question text or option text)
buf_target = None # "qtext" | "opt" | "other"
cur_opt = None
expect_q = 1
preamble = []


def close_opt():
    global cur_opt
    if cur_opt is not None and cur_q is not None:
        txt = norm(" ".join(cur_opt["parts"]))
        if txt:
            cur_opt["text"] = txt
            cur_q["options"].append(cur_opt)
    cur_opt = None


def close_q():
    global cur_q, buf
    close_opt()
    if cur_q is not None:
        cur_q["text"] = norm(" ".join(buf))
        questions.append(cur_q)
    cur_q = None
    buf = []


for idx, l in enumerate(lines):
    t = l["t"]
    if not t:
        continue
    m = RE_BLOCK.match(t)
    if m:
        close_q()
        cur_block = {"id": f"b{int(m.group(1))}", "number": int(m.group(1)),
                     "title": norm(m.group(2)), "source": {"page": l["page"], "bbox": l["bbox"]}}
        blocks.append(cur_block)
        buf_target = "other"
        continue
    m = RE_Q.match(t)
    if m and int(m.group(1)) == expect_q and cur_block is not None:
        close_q()
        cur_q = {"id": f"q{expect_q}", "number": expect_q, "block": cur_block["id"],
                 "text": "", "type": None, "instruction": [], "options": [],
                 "source": {"page": l["page"], "bbox": l["bbox"]}, "_parts": [m.group(2)]}
        buf = cur_q["_parts"]
        buf_target = "qtext"
        expect_q += 1
        continue
    if t.startswith(BULLET):
        if cur_q is None:
            raise SystemExit(f"bullet outside question: p{l['page']} {t!r}")
        close_opt()
        rest = t.lstrip(BULLET).strip()
        cur_opt = {"parts": [rest] if rest else [], "page": l["page"], "bbox": l["bbox"],
                   "line_index": idx}
        buf_target = "opt"
        continue
    if t.startswith("(") and cur_q is not None:
        for kw, typ in TYPE_MAP:
            if kw in t:
                if cur_q["type"] and cur_q["type"] != typ:
                    raise SystemExit(f"type conflict q{cur_q['number']}: {cur_q['type']} vs {typ}")
                cur_q["type"] = typ
                cur_q["instruction"].append(norm(t))
                buf_target = "instr"
                break
        else:
            # скобочная строка, не тип: роутинг/примечание клиента
            if cur_q is not None:
                cur_q.setdefault("_extra", []).append(norm(t))
                buf_target = "instr"
        continue
    # прочий текст
    if cur_q is None:
        preamble.append({"text": t, "page": l["page"], "bbox": l["bbox"]})
        continue
    if buf_target == "opt" and cur_opt is not None:
        cur_opt["parts"].append(t)
    elif buf_target == "qtext" and not cur_q["type"]:
        buf.append(t)
    else:
        cur_q.setdefault("_extra", []).append(norm(t))

close_q()

# ---------- география и метод из преамбулы ----------
geo = []
for p in preamble:
    m = re.match(r"^(.+?)\s*-\s*(\d+)\s*респондент", p["text"])
    if m:
        geo.append({"city": m.group(1).strip(), "n": int(m.group(2))})
title = next(p["text"] for p in preamble if p["text"])
method = next((p["text"] for p in preamble if p["text"].startswith("Метод")), None)

# ---------- спец-обработка ----------
by_num = {q["number"]: q for q in questions}
RF_MARK = re.compile(r"Для РФ.*?:")
RB_MARK = re.compile(r"Для РБ.*?:")


def brand_blocks(num):
    """Извлекает два списка брендов (РФ/РБ) из хвостовых строк вопроса."""
    q = by_num[num]
    extra = q.pop("_extra", [])
    q["raw_extra_text"] = " ".join(extra)
    joined = norm(" ".join(extra))
    out = {}
    mi_rf, mi_rb = RF_MARK.search(joined), RB_MARK.search(joined)
    if mi_rf and mi_rb:
        rf = joined[mi_rf.end():mi_rb.start()]
        rb = joined[mi_rb.end():]
        out["RF"] = [normalize_brand(x) for x in split_brands(rf)]
        out["RB"] = [normalize_brand(x) for x in split_brands(rb)]
        out["instruction"] = [norm(joined[mi_rf.start():mi_rb.start()]).rstrip(), norm(joined[mi_rb.start():])[:120]]
    elif mi_rf:
        out["RF"] = [normalize_brand(x) for x in split_brands(joined[mi_rf.end():])]
    elif mi_rb:
        out["RB"] = [normalize_brand(x) for x in split_brands(joined[mi_rb.end():])]
    return out


def split_brands(s):
    s = norm(s)
    parts = [p.strip(" .;") for p in s.split(";")]
    return [p for p in parts if p]


def normalize_brand(s):
    s = s.strip(" .")
    s = s.replace("Другой бренд (укажите)", "Другой бренд (укажите)")
    return s


for q in questions:
    q["instruction"] = " ".join(q["instruction"]) or None
    q.pop("_parts", None)

# Q11: список от клиента, в PDF вариантами не приведён → берём объединение списков из Q12
q11 = by_num[11]
q11["notes"] = "Варианты в PDF не приведены: пометка «(список от клиента)». Список восстановлен из вопроса 12 (два набора: РФ и РБ) и помечен scope."
q11["options_from"] = "q12"

# Q12: варианты — бренды, разделённые «;», с привязкой к стране показа
q12 = by_num[12]
bb12 = brand_blocks(12)
q12["options"] = []
for scope in ("RF", "RB"):
    for i, b in enumerate(bb12.get(scope, []), start=1):
        q12["options"].append({"code": f"q12.{scope.lower()}{i}", "text": b, "kind": "brand",
                               "exclusive": b.lower().startswith("другой бренд"), "scope": scope})
q12["notes"] = ("Варианты приведены двумя наборами с условием показа по стране респондента: "
                "«Для РФ — показывать только респондентам РФ» (24 бренда), "
                "«Для РБ — показывать только респондентам РБ» (15 брендов); поле scope помечает набор.")
q12["show_if"] = {"RF": "Для РФ — показывать только респондентам РФ",
                  "RB": "Для РБ — показывать только респондентам РБ"}

# Q13: те же списки — это инструкция, а не варианты (открытый вопрос)
q13 = by_num[13]
bb13 = brand_blocks(13)
q13["options"] = []
q13["notes"] = ("Инструкция содержит те же списки брендов, что и вопрос 12 (отдельно для РФ и РБ); "
                "это указание, какой бренд подставлять, а не варианты ответа.")

# Q11 опции = объединение брендов из Q12 с scope
q11["options"] = [{"code": o["code"].replace("q12.", "q11."), "text": o["text"], "kind": "brand",
                   "exclusive": o["exclusive"], "scope": o["scope"], "source_kind": "referenced"}
                  for o in q12["options"]]

# scope для вопросов, показываемых одной стране
for num, scope in ((50, "RF"), (51, "RB")):
    by_num[num]["scope"] = scope

# Q48: максимум 3
q48 = by_num[48]
if q48["type"] == "multi":
    q48["max_choices"] = 3

# Q5, Q8: шкала 1–10 по каждому фактору → items вместо options
for num in (5, 8):
    q = by_num[num]
    q["type"] = "scale"
    q["items"] = [{"code": f"q{num}.i{i}", "text": o["text"], "source": {"page": o["page"], "bbox": o["bbox"]}}
                  for i, o in enumerate(q["options"], start=1)]
    q["options"] = []
    q["scale"] = {"min": 1, "max": 10,
                  "labels": {"min": "совершенно неважно" if num == 5 else "практически никогда не останавливает",
                             "max": "очень важно" if num == 5 else "очень часто останавливает"}}

# Q49: матрица (строки×столбцы)
q49 = by_num[49]
q49["table_cells"] = q49.pop("_extra", [])
q49["type"] = "matrix"
q49["options"] = []
q49["rows"] = ["Продукты без нитритной соли",
               "Упаковка Easy-Peel, которую легко открыть без ножниц",
               "Использование натуральных ингредиентов для придания продукту цвета "
               "(например, свекольного сока, черного чеснока и т. д.) вместо искусственных красителей",
               "Мясные чипсы (сушеное мясо) к пиву или вину"]
q49["columns"] = ["Скорее маркетинговый ход", "Скорее реальное преимущество"]
q49["instruction"] = "Матрица; один вариант ответа для каждой новинки"
q49["notes"] = "Таблица в PDF без рамок; строки и столбцы восстановлены из порядка ячеек и сверены с текстом страниц 12–13."

# остатки _extra → notes
for q in questions:
    ex = q.pop("_extra", None)
    if ex:
        note = " ".join(ex)
        q["notes"] = (q.get("notes") + " " + note).strip() if q.get("notes") else note

# нормализация полей вариантов: kind/exclusive + провенанс page+bbox
for q in questions:
    for o in q.get("options", []):
        o.setdefault("kind", "option")
        o.setdefault("exclusive", False)
        if "bbox" in o and "source" not in o:
            o["source"] = {"page": o["page"], "bbox": o["bbox"]}
        o.pop("page", None)
        o.pop("bbox", None)

# коды вариантов: q{n}.a{i} — стабильные, от порядка вывода не зависят
for q in questions:
    for i, o in enumerate(q.get("options", []), start=1):
        o.setdefault("code", f"q{q['number']}.a{i}")

json.dump({"blocks": blocks, "questions": questions, "geo": geo, "title": title,
           "method": method, "preamble": preamble},
          open("parsed.json", "w"), ensure_ascii=False, indent=1)

# ---------- отчёт ----------
print("blocks", len(blocks), "questions", len(questions))
print("geo", geo, "sum", sum(g["n"] for g in geo))
missing = [n for n in range(1, 54) if n not in by_num]
print("missing questions:", missing)
tot_opt = sum(len(q.get("options", [])) for q in questions)
tot_items = sum(len(q.get("items", [])) for q in questions)
print("options", tot_opt, "items", tot_items, "options+items", tot_opt + tot_items)
for q in questions:
    print(f"q{q['number']:>2} [{q['type'] or '???'}] opts={len(q.get('options', []))} "
          f"items={len(q.get('items', []))} p{q['source']['page']} :: {q['text'][:70]}")
