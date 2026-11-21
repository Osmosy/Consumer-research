# Как собраны артефакты опросника

Пять скриптов, один порядок. Промежуточные файлы пишутся в текущий каталог, готовые — в каталог опросника.
Требуется PyMuPDF (`import pymupdf`), больше ничего.

```bash
export INKO_PDF="/путь/Маркетинговое исследование Инко Фуд, онлайн панель 900 респондентов.pdf"
export INKO_OUT="$PWD/../"           # instruments/inkofood-ua-oct2026
export REPO="$(git rev-parse --show-toplevel)"
mkdir -p /tmp/inko && cd /tmp/inko

python extract_lines.py        # → lines.json: каждая строка PDF с bbox и шрифтами
python build.py                # → parsed.json: блоки, вопросы, типы, варианты, коды
python emit.py                 # → instrument.json / .md / .csv / index.html
python map_to_slides.py        # → question-to-slide.json (сверка со decks/inkofood-2026)
python verify.py               # → verify.json: пункты a–g, ALL_PASS
python render_verification.py  # → instrument.raw.json + VERIFICATION.md из verify.json
```

| Скрипт | Что делает | Что важно знать |
|---|---|---|
| `extract_lines.py` | сырое извлечение через `page.get_text("dict")` | порядок строк — как отдаёт MuPDF; одна строка PDF = один элемент разметки |
| `build.py` | разбор на блоки/вопросы/варианты | вопрос распознаётся только при совпадении номера с ожидаемым, иначе «2–3 раза в месяц» стало бы вопросом; списки брендов вопросов 11–12 разбираются по `;` с пометкой `scope` |
| `emit.py` | сборка четырёх представлений и `totals` | `totals` считается из данных, а не вписывается руками |
| `map_to_slides.py` | карта «вопрос → слайд» | четыре уровня связи; `section` назначен блоку вручную — это указано в `strength` |
| `verify.py` | проверки a–g | счётчики считаются заново по сырому тексту, независимо от `build.py`; выход — `verify.json`, ненулевой `ALL_PASS` означает расхождение |
| `render_verification.py` | `instrument.raw.json` и `VERIFICATION.md` | все числа в таблице проверок берутся из `verify.json`, руками не переносятся |

Скрипты не лезут в сеть и ничего не пишут за пределы `INKO_OUT` и текущего каталога.
