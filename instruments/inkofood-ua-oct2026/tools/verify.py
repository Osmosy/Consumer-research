#!/usr/bin/env python3
"""Проверки «100% распознавания»: a) мультимножество символов, b) счётчики, c) страницы,
e) варианты не склеены/не разрезаны, f) согласованность md/json/csv."""
import json, re, csv, hashlib, os, sys
from collections import Counter

PDF = os.environ.get("INKO_PDF", "/home/lenovo/Загрузки/Маркетинговое исследование Инко Фуд, онлайн панель 900 респондентов.pdf")
D = os.environ.get("INKO_OUT", "/home/lenovo/projects/consumer-research/instruments/inkofood-ua-oct2026")
res = {}


def norm(s):
    return re.sub(r"\s+", " ", s.replace("\u200b", "").replace("\u00a0", " ")).strip()


import pymupdf
doc = pymupdf.open(PDF)
page_text = {i + 1: doc[i].get_text("text") for i in range(doc.page_count)}
all_text = "\n".join(page_text.values())
J = json.load(open(f"{D}/instrument.json"))
qs = J["questions"]
MD = open(f"{D}/instrument.md").read()
CSV = open(f"{D}/instrument.csv").read()
HTML = open(f"{D}/index.html").read()

# ---------- b) независимый подсчёт по сырому тексту ----------
lines = [norm(x) for x in all_text.splitlines() if norm(x)]
ind = {}
ind["pages"] = doc.page_count
ind["blocks"] = len([l for l in lines if re.match(r"^Блок\s+\d+\.", l)])
qnums = []
for l in lines:
    m = re.match(r"^(\d{1,2})\.\s+\S", l)
    if m:
        n = int(m.group(1))
        if n == (qnums[-1] + 1 if qnums else 1):
            qnums.append(n)
ind["questions"] = len(qnums)
ind["bullets"] = all_text.count("\u25cf")
ind["single_labels"] = len(re.findall(r"\(Одиночный выбор\)", all_text))
ind["multi_labels"] = len(re.findall(r"\(Множественный выбор", all_text))
ind["open_labels"] = len(re.findall(r"\(Открытый вопрос\)", all_text))
ind["scale_labels"] = len(re.findall(r"\(Шкала", all_text))
ind["matrix_labels"] = len(re.findall(r"\(Матрица", all_text))
res["b_independent"] = ind

declared = J["totals"]
res["b_match"] = {
    "pages": (ind["pages"], declared["pages"], ind["pages"] == declared["pages"]),
    "blocks": (ind["blocks"], declared["blocks"], ind["blocks"] == declared["blocks"]),
    "questions": (ind["questions"], declared["questions"], ind["questions"] == declared["questions"]),
    "bullets": (ind["bullets"], declared["bullets_in_pdf"], ind["bullets"] == declared["bullets_in_pdf"]),
    "bullets_equals_options_plus_items": (ind["bullets"], declared["options_from_bullets"] + declared["scale_items"],
                                          ind["bullets"] == declared["options_from_bullets"] + declared["scale_items"]),
    "options_json": (sum(len(q.get("options", [])) for q in qs), declared["options"], sum(len(q.get("options", [])) for q in qs) == declared["options"]),
    "scale_items_json": (sum(len(q.get("items", [])) for q in qs), declared["scale_items"], sum(len(q.get("items", [])) for q in qs) == declared["scale_items"]),
}
by_type = Counter(q["type"] for q in qs)
res["b_type_counts"] = {"json": dict(by_type), "pdf_labels": {k: ind[k + "_labels"] for k in ("single", "multi", "open", "scale", "matrix")}}

# ---------- a) мультимножество символов ----------
def chars(s, drop_bullet=True):
    s = s.replace("\u200b", "").replace("\u00a0", " ")
    s = re.sub(r"\s+", "", s)
    if drop_bullet:
        s = s.replace("\u25cf", "")
    return Counter(s)

pdf_c = chars(all_text)
art_c = chars(MD + CSV + json.dumps(J, ensure_ascii=False))
missing = pdf_c - art_c
res["a_multiset"] = {"pdf_chars": sum(pdf_c.values()), "artifact_chars": sum(art_c.values()),
                     "missing_total": sum(missing.values()),
                     "missing_sample": dict(list(missing.items())[:20])}

# ---------- c) покрытие страниц ----------
pages_used = Counter()
for b in J["blocks"]:
    pages_used[b["source"]["page"]] += 1
for q in qs:
    pages_used[q["source"]["page"]] += 1
    for o in q.get("options", []):
        if o.get("source"):
            pages_used[o["source"]["page"]] += 1
    for it in q.get("items", []):
        if it.get("source"):
            pages_used[it["source"]["page"]] += 1
lost = [p for p in range(1, doc.page_count + 1) if pages_used[p] == 0]
res["c_pages"] = {"per_page": dict(sorted(pages_used.items())), "lost_pages": lost,
                  "text_chars_per_page": {p: len(page_text[p]) for p in page_text}}

# ---------- e) варианты не склеены и не разрезаны ----------
bad = []
for q in qs:
    pg = q["source"]["page"]
    ctx = norm(page_text[pg] + " " + page_text.get(pg - 1, "") + " " + page_text.get(pg + 1, ""))
    for o in q.get("options", []):
        opg = (o.get("source") or {}).get("page") or pg
        po = norm(page_text[opg] + " " + page_text.get(opg - 1, "") + " " + page_text.get(opg + 1, ""))
        if norm(o["text"]) not in po:
            bad.append(("option", q["number"], o["code"], o["text"][:60], opg))
    for it in q.get("items", []):
        ipg = (it.get("source") or {}).get("page") or pg
        pi = norm(page_text[ipg] + " " + page_text.get(ipg - 1, "") + " " + page_text.get(ipg + 1, ""))
        if norm(it["text"]) not in pi:
            bad.append(("item", q["number"], it["code"], it["text"][:60], ipg))
    for r in q.get("rows", []):
        if norm(r) not in norm(page_text[12] + " " + page_text[13]):
            bad.append(("row", q["number"], "", r[:60], 12))
    if norm(q["text"]) not in ctx:
        bad.append(("qtext", q["number"], "", q["text"][:60], pg))
res["e_contiguity"] = {"violations": bad, "checked_questions": len(qs),
                       "checked_options": sum(len(q.get("options", [])) for q in qs),
                       "checked_items": sum(len(q.get("items", [])) for q in qs)}
# склейка: два вопроса в одной строке варианта
glued = [o["text"] for q in qs for o in q.get("options", []) if re.search(r"\d{1,2}\.\s", o["text"]) or "\n" in o["text"]]
res["e_glued"] = glued

# ---------- f) согласованность трёх представлений ----------
md_heads = re.findall(r"^### (\d{1,2})\. ", MD, re.M)
csv_rows = list(csv.DictReader(CSV.splitlines()))
md_missing_opts = [o["text"] for q in qs for o in q.get("options", []) if o["text"] not in MD]
md_missing_items = [i["text"] for q in qs for i in q.get("items", []) if i["text"] not in MD]
csv_codes = {r["option_code"] for r in csv_rows if r["option_code"]}
json_codes = {o["code"] for q in qs for o in q.get("options", [])} | {i["code"] for q in qs for i in q.get("items", [])}
res["f_consistency"] = {
    "md_question_headings": len(md_heads), "distinct_md_numbers": len(set(md_heads)),
    "csv_data_rows": len(csv_rows),
    "csv_expected": sum(len(q.get("options", [])) + len(q.get("items", [])) + len(q.get("rows", [])) for q in qs)
                    + sum(1 for q in qs if not (q.get("options") or q.get("items") or q.get("rows"))),
    "csv_kinds": dict(Counter(r["kind"] for r in csv_rows)),
    "codes_missing_in_md": md_missing_opts + md_missing_items,
    "codes_csv_vs_json_diff": sorted(json_codes - csv_codes) + sorted(csv_codes - json_codes),
}
m0 = re.search(r"const D=(\{.*?\});\n", HTML, re.S)
D0 = json.loads(m0.group(1)) if m0 else {}
res["f_counts_in_texts"] = {
    "html_questions": len(D0.get("questions", [])),
    "html_blocks": len(D0.get("blocks", [])),
    "html_last_block": (D0.get("blocks") or [{}])[-1].get("title"),
    "html_has_codes": "q12.rf1" in HTML,
}

# ---------- JSON валиден, index.html данные парсятся ----------
m = re.search(r"const D=(\{.*?\});\n", HTML, re.S)
res["html_embedded_json_ok"] = bool(m and json.loads(m.group(1))["totals"]["questions"] == 53)

ok = (res["a_multiset"]["missing_total"] == 0
      and all(v[2] for v in res["b_match"].values())
      and not res["c_pages"]["lost_pages"]
      and not res["e_contiguity"]["violations"]
      and not res["e_glued"]
      and not res["f_consistency"]["codes_missing_in_md"]
      and not res["f_consistency"]["codes_csv_vs_json_diff"]
      and res["f_consistency"]["md_question_headings"] == 53
      and res["f_consistency"]["csv_data_rows"] == res["f_consistency"]["csv_expected"]
      and res["html_embedded_json_ok"]
      and res["f_counts_in_texts"]["html_questions"] == 53
      and res["f_counts_in_texts"]["html_blocks"] == 12)
res["ALL_PASS"] = ok
json.dump(res, open("verify.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1)[:6000])
print("\nALL_PASS:", ok)
