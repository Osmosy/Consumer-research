#!/usr/bin/env python3
"""Регрессия правила маркера: признак берётся из поля, а не из текста причины.

Зачем: если чекер решает «требовать ли маркер панели» по формулировке причины исключения,
достаточно переписать причину — и проверка отключится молча, а число белорусской панели
начнёт читаться как число по РФ. Скрипт доказывает две вещи на копии проекта:

1. `require_marker` в записи исключения включает проверку независимо от текста причины;
2. если маркер убрать из предложения, предикат даёт fail — то есть проверка живая.

Запуск: python3 docs/registry/tools/check_marker_rule.py
Код выхода: 0 — правило работает, 1 — правило не работает, 2 — нет данных.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CHECKER = "docs/registry/checkers/check_fact_in_conclusions_v6.py"
CONCLUSIONS = "reviews/2026-10-25-inkofood/AGENT-REVIEW.md"
APPENDIX = "reviews/2026-10-25-inkofood/APPENDIX-INFO.md"


def prepare(tmp: Path) -> None:
    shutil.copytree(ROOT / "docs", tmp / "docs")
    target = tmp / "reviews/2026-10-25-inkofood"
    target.mkdir(parents=True)
    for name in (CONCLUSIONS, APPENDIX):
        shutil.copy(ROOT / name, tmp / name)


def run(tmp: Path, req: str) -> dict:
    done = subprocess.run(
        [sys.executable, str(tmp / CHECKER), "--root", str(tmp), "--transition", req],
        capture_output=True, text=True)
    for line in done.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    return {"ok": None, "detail": done.stdout.strip() or done.stderr.strip()}


def edit_config(tmp: Path, reason: str) -> None:
    path = tmp / "docs/facts/config.json"
    config = json.loads(path.read_text("utf-8"))
    for entry in config.get("owner_exceptions") or []:
        entry["reason"] = reason
    path.write_text(json.dumps(config, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def strip_marker(tmp: Path) -> bool:
    path = tmp / CONCLUSIONS
    text = path.read_text("utf-8")
    stripped = (text.replace("только в Беларуси: ", "")
                    .replace("на панели РБ ", "")
                    .replace(" в Беларуси", ""))
    path.write_text(stripped, encoding="utf-8")
    return stripped != text


def main() -> int:
    if not (ROOT / CHECKER).is_file():
        print(f"нет предиката: {CHECKER}")
        return 2
    config = json.loads((ROOT / "docs/facts/config.json").read_text("utf-8"))
    exceptions = [entry for entry in config.get("owner_exceptions") or []
                  if isinstance(entry, dict) and entry.get("require_marker")]
    if not exceptions:
        print("в owner_exceptions нет поля require_marker — проверять нечего")
        return 2
    req = str(exceptions[0]["req_id"])
    ok = True

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        prepare(tmp)
        before = run(tmp, req)
        edit_config(tmp, "конкурент на рынке РФ, пометка не нужна")
        after_reason = run(tmp, req)
        stripped = strip_marker(tmp)
        after_strip = run(tmp, req)

    print(f"предикат: {CHECKER}, требование: {req}")
    print(f"  как есть:                        {before.get('ok')}")
    print(f"  причина переписана:              {after_reason.get('ok')}")
    print(f"  причина переписана + нет маркера: {after_strip.get('ok')}")

    if before.get("ok") is not True:
        print("ОШИБКА: исходное состояние не проходит — правило нечего проверять")
        ok = False
    if after_reason.get("ok") is not True:
        print("ОШИБКА: правка текста причины отключила проверку — признак всё ещё берётся из причины")
        ok = False
    if not stripped:
        print("ОШИБКА: маркер панели в выводах не найден, негативный тест не построен")
        ok = False
    elif after_strip.get("ok") is not False:
        print("ОШИБКА: без маркера панели предикат всё равно даёт pass — проверка не работает")
        ok = False

    print("итог: правило на структурном поле работает" if ok else "итог: правило не работает")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
