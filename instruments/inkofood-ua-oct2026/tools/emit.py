#!/usr/bin/env python3
"""Генерация артефактов опросника: instrument.json, instrument.md, instrument.csv, index.html."""
import json, csv, os, hashlib, html

SRC_PDF = os.environ.get("INKO_PDF", "/home/lenovo/Загрузки/Маркетинговое исследование Инко Фуд, онлайн панель 900 респондентов.pdf")
SLUG = "inkofood-ua-oct2026"
OUT = os.environ.get("INKO_OUT", "/home/lenovo/projects/consumer-research/instruments/" + SLUG)
P = json.load(open("lines_parsed.json")) if os.path.exists("lines_parsed.json") else json.load(open("parsed.json"))

sha = hashlib.sha256(open(SRC_PDF, "rb").read()).hexdigest()
nbytes = os.path.getsize(SRC_PDF)

TYPE_RU = {"single": "Одиночный выбор", "multi": "Множественный выбор",
           "open": "Открытый вопрос", "scale": "Шкала", "matrix": "Матрица"}

questions = P["questions"]
blocks = P["blocks"]

# ---------- routing из notes ----------
for q in questions:
    n = q.get("notes") or ""
    if n.startswith("(Для респондентов"):
        q["routing"] = n
        q["notes"] = None

# ---------- items с source ----------
# q5/q8: items уже с code и source
# ---------- totals ----------
tot_options = sum(len(q.get("options", [])) for q in questions)
tot_items = sum(len(q.get("items", [])) for q in questions)

instrument = {
    "schema_version": "1.0",
    "instrument": {
        "slug": SLUG,
        "title": P["title"],
        "method": P["method"].replace("Метод: ", "").strip() if P["method"] else None,
        "field_period": None,
        "field_period_note": "В PDF период поля не указан. Колода decks/inkofood-2026 относит исследование к октябрю 2026; здесь это не утверждается.",
        "language": "ru",
        "geography": P["geo"],
        "n_total": sum(g["n"] for g in P["geo"]),
        "source": {"file": os.path.basename(SRC_PDF), "bytes": nbytes, "sha256": sha, "pages": 14},
    },
    "blocks": blocks,
    "questions": questions,
    "totals": {
        "pages": 14,
        "blocks": len(blocks),
        "questions": len(questions),
        "options": tot_options,
        "options_from_bullets": tot_options - 78,
        "options_from_brand_lists": 78,
        "scale_items": tot_items,
        "bullets_in_pdf": 272,
    },
}

os.makedirs(OUT, exist_ok=True)
json.dump(instrument, open(f"{OUT}/instrument.json", "w"), ensure_ascii=False, indent=1)

# ---------------- markdown ----------------
L = []
L.append("# Маркетинговое исследование\n")
L.append("> Дословная расшифровка опросника из PDF (текстовый слой, без OCR).\n"
         f"> Источник: `{os.path.basename(SRC_PDF)}`, sha256 `{sha[:16]}…`, 14 страниц.\n")
L.append(f"{P['method']}\n")
L.append("Географическая выборка:\n")
for g in P["geo"]:
    L.append(f"- {g['city']} - {g['n']} респондентов")
L.append("")
for b in blocks:
    L.append(f"\n## Блок {b['number']}. {b['title']}\n")
    for q in [x for x in questions if x["block"] == b["id"]]:
        L.append(f"\n### {q['number']}. {q['text']}\n")
        if q.get("instruction"):
            instr = q["instruction"].replace("(", "_(", 1)
            L.append(f"_{q['instruction'].strip('()')}_\n" if q["instruction"].startswith("(") else f"_{q['instruction']}_\n")
        if q.get("scope"):
            L.append(f"*Только {q['scope']}.*\n")
        if q.get("max_choices"):
            L.append(f"*Не более {q['max_choices']} вариантов.*\n")
        if q.get("routing"):
            L.append(f"*{q['routing'].strip('()')}*\n")
        # q12: два набора брендов по странам; q13: дословная инструкция
        if q["number"] == 12:
            for scope in ("RF", "RB"):
                opts = [o for o in q["options"] if o.get("scope") == scope]
                if not opts:
                    continue
                L.append(f"{q['show_if'][scope]}:\n")
                for o in opts:
                    L.append(f"- {o['text']}")
                L.append("")
        elif q["number"] == 13:
            L.append(f"{q.get('raw_extra_text','')}\n")
        else:
            for o in q.get("options", []):
                mark = "- [ ] " if q["type"] == "multi" else "- "
                L.append(f"{mark}{o['text']}")
            for it in q.get("items", []):
                L.append(f"- {it['text']}")
            if q.get("options") or q.get("items"):
                L.append("")
        if q["type"] == "matrix":
            L.append("| " + " | ".join(["Новинка / характеристика"] + q["columns"]) + " |")
            L.append("|---|---|---|")
            for r in q["rows"]:
                L.append("| " + r + " | | |")
            L.append("")
        if q.get("notes"):
            L.append(f"*Примечание: {q['notes']}*\n")
open(f"{OUT}/instrument.md", "w").write("\n".join(L) + "\n")

# ---------------- csv ----------------
with open(f"{OUT}/instrument.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["question_id", "question_number", "block", "question", "type",
                "option_code", "option_text", "scope", "kind", "page"])
    for q in questions:
        block_title = next(b["title"] for b in blocks if b["id"] == q["block"])
        rows = []
        for o in q.get("options", []):
            rows.append((o["code"], o["text"], o.get("scope") or q.get("scope") or "",
                         o.get("kind", "option"), (o.get("source") or {}).get("page", "")))
        for it in q.get("items", []):
            rows.append((it["code"], it["text"], q.get("scope") or "", "scale_item",
                         (it.get("source") or {}).get("page", "")))
        for r in q.get("rows", []):
            rows.append(("", r, q.get("scope") or "", "matrix_row", q["source"]["page"]))
        if not rows:
            w.writerow([q["id"], q["number"], block_title, q["text"], q["type"], "", "", "", "no_options", q["source"]["page"]])
        for code, text, scope, kind, page in rows:
            w.writerow([q["id"], q["number"], block_title, q["text"], q["type"], code, text, scope, kind, page])

# ---------------- index.html ----------------
data = json.dumps({"blocks": blocks, "questions": questions,
                   "instrument": instrument["instrument"], "totals": instrument["totals"]},
                  ensure_ascii=False)
HTML = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Опросник — Инко Фуд, онлайн-панель 900 респондентов</title>
<style>
:root{--bg:#f7f6f3;--card:#fff;--ink:#1b1b1f;--muted:#6b6b75;--line:#e3e0d8;--accent:#1b2a6b;--accent2:#0f8a6a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
header.top{padding:30px 40px 16px;background:linear-gradient(135deg,#1b2a6b,#0f3b6a);color:#fff}
header.top h1{margin:0 0 6px;font-size:24px}
header.top p{margin:2px 0;color:#cdd6f0;font-size:13.5px}
.wrap{display:grid;grid-template-columns:300px 1fr;align-items:start}
nav{position:sticky;top:0;max-height:100vh;overflow:auto;padding:16px 12px 40px;border-right:1px solid var(--line);background:#fbfaf7}
nav h3{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:14px 8px 6px}
nav a{display:block;padding:4px 8px;border-radius:6px;color:#333;text-decoration:none;font-size:13.5px}
nav a:hover{background:#eee9dd}
nav .num{color:var(--muted);font-variant-numeric:tabular-nums;margin-right:6px}
#q{width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:8px;font-size:14px;margin:6px 0;background:#fff}
.filters{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 8px}
.filters button{font:12.5px/1 inherit;padding:6px 9px;border:1px solid var(--line);background:#fff;border-radius:999px;cursor:pointer;color:#333}
.filters button.on{background:var(--accent);color:#fff;border-color:var(--accent)}
main{padding:22px 32px 80px;max-width:1080px}
section.card{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:0 0 14px;padding:14px 18px}
.qid{font:600 12px/1 ui-monospace,monospace;color:#fff;background:var(--accent);padding:4px 7px;border-radius:5px;margin-right:8px}
h2.q{font-size:17px;margin:0 0 6px;display:flex;align-items:baseline;flex-wrap:wrap}
.tag{font-size:11.5px;color:#0f6b52;background:#e3f3ec;border:1px solid #bfe0d2;border-radius:5px;padding:1px 6px;margin-left:8px}
.tag.scope{color:#7a4b00;background:#fff3d6;border-color:#f0dca8}
.instr{color:var(--muted);font-style:italic;font-size:13.5px;margin:2px 0 8px}
ol.opts,ul.items{margin:6px 0 0;padding-left:22px}
ol.opts li,ul.items li{margin:2px 0}
code.c{font:11.5px ui-monospace,monospace;color:var(--muted);margin-right:6px}
table{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0 0}
th,td{border-bottom:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top}
th{background:#f4f2ec;font-size:13px}
.note{background:#f3f1ea;border-left:3px solid var(--accent2);padding:7px 11px;font-size:13.5px;border-radius:6px;margin:8px 0 0;color:#3a3a42}
.hidden{display:none}
@media (max-width:1000px){.wrap{grid-template-columns:1fr}nav{position:static;max-height:none}}
</style></head><body>
<header class="top">
<h1>Опросник — «Маркетинговое исследование», онлайн-панель 900 респондентов</h1>
<p id="sub"></p>
<p>Текст извлечён из текстового слоя PDF дословно (OCR не применялся). Источник в репозиторий не вложен — только sha256.</p>
</header>
<div class="wrap"><nav><input id="q" placeholder="Поиск по вопросам и вариантам…" oninput="apply()">
<div class="filters" id="fl"></div><div id="toc"></div></nav>
<main id="main"></main></div>
<script>
const D=__DATA__;
const TYPE={single:'Одиночный выбор',multi:'Множественный выбор',open:'Открытый вопрос',scale:'Шкала',matrix:'Матрица'};
let state={type:null};
document.getElementById('sub').textContent=`${D.totals.blocks} блоков, ${D.totals.questions} вопросов, ${D.totals.options} вариантов ответа, ${D.totals.scale_items} пунктов шкал. n=${D.instrument.n_total}.`;
const main=document.getElementById('main'), toc=document.getElementById('toc');
const types=[...new Set(D.questions.map(q=>q.type))];
const fl=document.getElementById('fl');
fl.innerHTML=types.map(t=>`<button data-t="${t}">${TYPE[t]||t} (${D.questions.filter(q=>q.type===t).length})</button>`).join('');
fl.querySelectorAll('button').forEach(b=>b.onclick=()=>{state.type=state.type===b.dataset.t?null:b.dataset.t;fl.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x.dataset.t===state.type));apply();});
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function opts(q){
  if(q.number===12){
    return Object.entries(q.show_if||{}).map(([sc,label])=>`<div class="instr">${esc(label)}</div><ol class="opts">`+
      q.options.filter(o=>o.scope===sc).map(o=>`<li><code class="c">${o.code}</code>${esc(o.text)}</li>`).join('')+`</ol>`).join('');
  }
  if(q.options&&q.options.length) return `<ol class="opts">`+q.options.map(o=>`<li><code class="c">${o.code}</code>${esc(o.text)}${o.scope?` <span class="tag scope">${o.scope}</span>`:''}</li>`).join('')+`</ol>`;
  if(q.items&&q.items.length) return `<ul class="items">`+q.items.map(i=>`<li><code class="c">${i.code}</code>${esc(i.text)}</li>`).join('')+`</ul>`;
  if(q.type==='matrix') return `<table><tr><th>Новинка / характеристика</th>${q.columns.map(c=>`<th>${esc(c)}</th>`).join('')}</tr>`+
    q.rows.map(r=>`<tr><td>${esc(r)}</td><td></td><td></td></tr>`).join('')+`</table>`;
  return '';
}
D.blocks.forEach(b=>{
  const qs=D.questions.filter(q=>q.block===b.id);
  main.insertAdjacentHTML('beforeend',`<h2 class="q" id="${b.id}" style="margin:22px 0 8px;font-size:19px">Блок ${b.number}. ${esc(b.title)} <span class="tag">${qs.length} вопр.</span></h2>`);
  qs.forEach(q=>{
    main.insertAdjacentHTML('beforeend',`<section class="card" data-type="${q.type}">
      <h2 class="q"><span class="qid">${q.number}</span>${esc(q.text)}
        <span class="tag">${TYPE[q.type]||q.type}</span>${q.scope?`<span class="tag scope">только ${q.scope}</span>`:''}</h2>
      ${q.instruction?`<div class="instr">${esc(q.instruction)}</div>`:''}
      ${q.routing?`<div class="instr">${esc(q.routing)}</div>`:''}
      ${q.number===13?`<div class="instr">${esc(q.raw_extra_text)}</div>`:''}
      ${opts(q)}
      ${q.notes?`<div class="note">${esc(q.notes)}</div>`:''}
      </section>`);
  });
});
toc.innerHTML='<h3>Блоки</h3>'+D.blocks.map(b=>`<a href="#${b.id}"><span class="num">${String(b.number).padStart(2,'0')}</span>${esc(b.title)}</a>`).join('');
function apply(){
  const s=document.getElementById('q').value.toLowerCase();
  document.querySelectorAll('section.card').forEach(c=>{
    const okType=!state.type||c.dataset.type===state.type;
    const okText=c.innerText.toLowerCase().indexOf(s)>=0;
    c.classList.toggle('hidden',!(okType&&okText));
  });
}
</script></body></html>"""
open(f"{OUT}/index.html", "w").write(HTML.replace("__DATA__", data))
print("written:", OUT)
print("totals:", instrument["totals"])
print("md lines:", len(L), "csv rows:", sum(1 for _ in open(f'{OUT}/instrument.csv')) - 1)
