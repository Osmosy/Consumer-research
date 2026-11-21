# Опросник Инко Фуд — потребительское исследование, онлайн-панель 900 респондентов

Полевой инструмент колоды [`decks/inkofood-2026`](../../decks/inkofood-2026/): анкета, по которой собраны
числа презентации. Здесь она лежит в машинно-читаемом виде — дословно, без пересказа.

- Блоков: **12**, вопросов: **53**, вариантов ответа: **321**, пунктов шкал: **29**.
- Источник: `Маркетинговое исследование Инко Фуд, онлайн панель 900 респондентов.pdf`,
  14 страниц, 932 564 Б, sha256 `dcaf31cb38a8bc4d3e4a8c2a3364685b3cf49e000354656a247e9a249c1dc4f9`.
  PDF приложен к репозиторию: [`sources/pdf/`](../../sources/pdf/) — 932 КБ, рядом с манифестом.
- Текст извлечён из текстового слоя PDF; OCR не применялся. Сверка — в [VERIFICATION.md](VERIFICATION.md).

## Файлы

| Файл | Что внутри |
|---|---|
| [`instrument.json`](instrument.json) | источник истины для машин: блоки, вопросы, варианты, коды, `source.page` + `bbox` |
| [`instrument.md`](instrument.md) | дословный текст опросника, блок за блоком (для чтения и diff) |
| [`instrument.csv`](instrument.csv) | плоско: `question_id,question_number,block,question,type,option_code,option_text,scope,kind,page` |
| [`index.html`](index.html) | самодостаточная страница: оглавление блоков, поиск, фильтр по типу |
| [`instrument.raw.json`](instrument.raw.json) | сырое извлечение: каждая строка PDF с bbox — доказательство происхождения |
| [`question-to-slide.json`](question-to-slide.json) | карта «вопрос → слайды колоды» с указанием силы связи |
| [`tools/`](tools/) | скрипты сборки, проверки и связки с колодой |
| [`VERIFICATION.md`](VERIFICATION.md) | таблица шести проверок с числами |

## Схема `instrument.json`

```
schema_version
instrument { slug, title, method, field_period, field_period_note, language, geography[{city,n}], n_total,
             source{file,bytes,sha256,pages} }
blocks     [{ id, number, title, source{page,bbox} }]
questions  [{ id, number, block, text, type, instruction, options[{code,text,kind,exclusive,scope,source}],
              items[{code,text,source}], scale{min,max,labels}, rows[], columns[], routing, notes,
              scope, max_choices, show_if, source{page,bbox} }]
totals     { pages, blocks, questions, options, options_from_bullets, options_from_brand_lists,
             scale_items, bullets_in_pdf }
```

`type`: `single` | `multi` | `open` | `scale` | `matrix`. Коды вариантов стабильные: `q12.a3`, пункты шкал — `q5.i7`.

## Особенности исходника, которые видно в схеме

- **Шкалы не развёрнуты в варианты.** Вопросы 5 и 8 — оценка 1–10 по каждому фактору: диапазон и подписи полюсов
  в `scale`, сами факторы в `items` (17 и 12). Одиночные оценки названий (18, 21, 24) — `scale` без `items`.
- **Вопросы 11 и 12 — списки брендов от клиента.** В PDF у них нет маркеров «●»: бренды идут строкой через `;`,
  двумя наборами — «Для РФ» (24 бренда) и «Для РБ» (15). В выгрузке они помечены `scope: RF|RB`,
  условие показа — в `show_if`. Это 78 из 321 варианта; остальные 243 — из маркеров «●».
- **Вопрос 13** содержит те же списки, но как инструкцию (какой бренд подставлять) — вариантами не считается.
- **Роутинг** вопросов 14 и 15 («для тех, кто не выбрал X в вопросе 12») — в поле `routing`.
- **Вопросы 33 и 34** ждут от клиента варианты нарезки: в PDF только «Вариант 1 / Вариант 2 / Затрудняюсь ответить».
- **Вопрос 48** — множественный выбор с ограничением: `max_choices: 3`.
- **Вопрос 49** — матрица 4×2: новинки × (маркетинговый ход / реальное преимущество).
- **Вопросы 16 и 17** сопровождаются визуалами упаковок (стр. 5 и 6). Внутри изображений вариантов ответа нет.
- **Вопросы 50 и 51** показываются только одной стране (`scope: RF` для ГОСТ, `RB` для СТБ/ТУ).
- **Период поля в PDF не указан** (`field_period: null`). Колода называет октябрь 2026 — здесь это не утверждается.

## Как читать

```python
import json
ins = json.load(open("instruments/inkofood-ua-oct2026/instrument.json"))
q = next(x for x in ins["questions"] if x["number"] == 4)
[(o["code"], o["text"]) for o in q["options"]]          # категории мясной гастрономии
q = next(x for x in ins["questions"] if x["number"] == 5)
q["scale"], [i["text"] for i in q["items"]]              # шкала 1–10 и 17 факторов
```

```python
import csv
rows = list(csv.DictReader(open("instruments/inkofood-ua-oct2026/instrument.csv", encoding="utf-8-sig")))
brands_rf = [r["option_text"] for r in rows if r["question_number"] == "12" and r["scope"] == "RF"]
```

```python
import json
m = json.load(open("instruments/inkofood-ua-oct2026/question-to-slide.json"))
next(x for x in m["maps"] if x["question"] == 39)        # какие слайды связаны с «Сервелатом»
```

## Связь с колодой

Колода `decks/inkofood-2026` — числа, полученные по этой анкете. `question-to-slide.json` связывает вопрос
со слайдами по совпадению текста: 30 вопросов — по точному совпадению подписей таблиц, 2 — по частичному,
16 — по словам заголовков слайдов, 5 — по разделу колоды (назначен блоку вручную), без связи — 0.
Сила связи указана у каждой пары: ссылка не значит, что слайд отвечает именно на этот вопрос.

## Ограничения

- Разметка блоков и типов повторяет пометки PDF. Там, где пометки нет (открытые вопросы без «●»), тип выведен
  из пометки в скобках; вопросов без пометки типа в исходнике нет.
- География (900 респондентов) взята с первой страницы «как есть»; разбивка РФ/РБ в PDF не приводится.
- Опечатки исходника сохранены: «продvуктах» в вопросе 13 (латинская «v» внутри слова), «Рублевски МК»,
  «Рублеский МПЗ», «Великолукций МК» в списках брендов, «Francôté» латиницей в списке РБ — см. [`docs/caveats.md`](../../docs/caveats.md).
