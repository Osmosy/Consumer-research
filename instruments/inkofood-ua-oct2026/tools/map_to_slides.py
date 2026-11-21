#!/usr/bin/env python3
"""Карта «вопрос опросника → слайды колоды»: только по совпадению текста, без догадок."""
import json, re, os
from collections import defaultdict

D = os.environ.get("REPO", "/home/lenovo/projects/consumer-research")
INS = json.load(open(f"{D}/instruments/inkofood-ua-oct2026/instrument.json"))
DECK = json.load(open(f"{D}/decks/inkofood-2026/deck.json"))


def norm(s):
    s = (s or "").lower().replace("ё", "е")
    s = re.sub(r"[«»\"“”„“’']", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .,:;—-")


STOP = set("""какой какие какая какое какие что чем как где когда для вас ваш ваши вы это или
при или каждая каждый перечисленных ниже также более менее наиболее может могут
если будете будет очень скорее совсем ответить затрудняюсь укажите опишите оцените
представьте посмотрите выберите назовите дайте развёрнутый ответ продукт продукта
продукты продуктов продуктах продукту изделие изделия колбаса колбасы колбасных мясной
мясных мясные мясного себя себя мне меня мой моя мои вашему мнению вашего вашу
того чтобы тогда только кроме например т.д т.п""".split())


END = tuple("ого ому ыми ими ами ями ов ев ие ия ию ей ой ая ое ые ых им ым ах ях ам ям ую юю ый ий ы и а я е о у ю ь".split())


def stem(w):
    for e in END:
        if len(w) - len(e) >= 4 and w.endswith(e):
            return w[: -len(e)]
    return w


def toks(s, use_stem=False):
    ws = {w for w in re.findall(r"[а-яa-z0-9%]+", norm(s)) if len(w) > 2 and w not in STOP}
    return {stem(w) for w in ws} if use_stem else ws


slides = DECK["slides"]
DF = {}
for s_ in slides:
    for w in toks(s_.get("title", "") + " " + s_.get("section", ""), use_stem=True):
        DF[w] = DF.get(w, 0) + 1
slide_labels = {}
slide_corpus = {}
for s in slides:
    labels = [norm(r.get("label", "")) for r in (s.get("table") or []) if r.get("label")]
    slide_labels[s["page"]] = [l for l in labels if l]
    parts = [s.get("title", ""), s.get("section", ""), norm(s.get("note", ""))]
    for b in (s.get("blocks") or []):
        parts.append(b if isinstance(b, str) else json.dumps(b, ensure_ascii=False))
    slide_corpus[s["page"]] = norm(" ".join(parts))

BRAND = {"natura", "белорусск", "традиц", "беловежск", "гостинец", "сервелат"}

# раздел колоды для каждого блока — назначено вручную по смыслу блока (не автоматика)
BLOCK_SECTION = {
    "b1": "Общий U&A", "b2": "Общий U&A", "b3": "Общий U&A",
    "b4": "Знание брендов", "b5": "Оценка брендов", "b6": "Оценка брендов",
    "b7": "Нарезка", "b8": "Упаковка", "b9": "Сервелат", "b10": "Высокий белок",
    "b11": "Форматы и новинки", "b12": "Форматы и новинки",
}
section_pages = {}
for s_ in slides:
    section_pages.setdefault(s_["section"], []).append(s_["page"])

out = []
for q in INS["questions"]:
    qn = q["number"]
    unit_texts = ([o["text"] for o in q.get("options", [])] + [i["text"] for i in q.get("items", [])]
                  + list(q.get("rows", [])))
    unit_norm = {norm(t) for t in unit_texts if norm(t)}
    qtok = toks(q["text"], use_stem=True)
    hits = []
    for s in slides:
        page = s["page"]
        lab = slide_labels.get(page, [])
        exact = sorted({l for l in lab if l in unit_norm})
        partial = []
        if not exact:
            for u in sorted(unit_norm):
                if len(u) < 8:
                    continue
                for l in lab:
                    if len(l) >= 8 and (u in l or l in u):
                        partial.append(l)
                        break
                if len(partial) >= 3:
                    break
        ttok = toks(s.get("title", "") + " " + s.get("section", ""), use_stem=True) & qtok
        ttok = {w for w in ttok if DF.get(w, 99) <= 12}
        partial = sorted(set(partial))
        if exact:
            hits.append({"page": page, "title": s["title"],
                         "evidence": [f"подпись таблицы: {x}" for x in exact[:6]],
                         "strength": "label"})
        elif len(partial) >= 2:
            hits.append({"page": page, "title": s["title"],
                         "evidence": [f"подпись таблицы: {x}" for x in partial[:6]],
                         "strength": "label-partial"})
        elif len(ttok) >= 2 or (len(ttok) == 1 and any(w in BRAND for w in ttok)):
            hits.append({"page": page, "title": s["title"],
                         "evidence": [f"слова заголовка/раздела: {', '.join(sorted(ttok))}"],
                         "strength": "topic", "_n": len(ttok)})
    if not hits:
        sec = BLOCK_SECTION.get(q["block"])
        for page in section_pages.get(sec, [])[:4]:
            ttl = next(x["title"] for x in slides if x["page"] == page)
            hits.append({"page": page, "title": ttl,
                         "evidence": [f"раздел колоды «{sec}» (по блоку {q['block']})"],
                         "strength": "section"})
    order = {"label": 0, "label-partial": 1, "topic": 2, "section": 3}
    hits.sort(key=lambda h: (order[h["strength"]], -h.get("_n", 0), h["page"]))
    for h in hits:
        h.pop("_n", None)
    out.append({"question": qn, "type": q["type"],
                "text": q["text"],
                "slides": hits[:6],
                "best": hits[0]["strength"] if hits else "none"})

stat = defaultdict(int)
for r in out:
    stat[r["best"]] += 1
mapped = [r["question"] for r in out if r["best"] != "none"]
unmapped = [r["question"] for r in out if r["best"] == "none"]

doc = {
    "instrument": "inkofood-ua-oct2026",
    "deck": "inkofood-2026",
    "method": "Совпадение текста: вариант/пункт опросника ищется среди подписей таблиц слайда "
              "(точное или частичное совпадение, ≥8 символов), иначе — по словам заголовка слайда. "
              "Никаких чисел и выводов: только ссылки.",
    "strength_legend": {
        "label": "вариант/пункт опросника совпал с подписью таблицы слайда (сильная связь)",
        "label-partial": "подписи совпали частично (≥8 символов), проверять глазами",
        "topic": "совпали слова заголовка/раздела слайда (слабая связь)",
        "section": "слайд из раздела колоды, назначенного блоку вручную (связь по разделу, не по тексту)",
        "none": "связи не найдено",
    },
    "coverage": {"questions": len(out), "mapped": len(mapped), "unmapped": len(unmapped),
                 "by_strength": dict(stat)},
    "maps": out,
}
OUT = os.environ.get("INKO_OUT", f"{D}/instruments/inkofood-ua-oct2026")
json.dump(doc, open(f"{OUT}/question-to-slide.json", "w"),
          ensure_ascii=False, indent=1)
print(json.dumps(doc["coverage"], ensure_ascii=False, indent=1))
print("unmapped:", unmapped)
for r in out:
    if r["best"] == "none":
        print(f"  q{r['question']}: {r['text'][:70]}")
print("\nsample mapped:")
for r in out[:8]:
    print(f"  q{r['question']} [{r['best']}] -> " + ", ".join(f"s{h['page']}" for h in r["slides"][:4]))
