"""Перевыпуск предиката «факт в выводах» на версию 7 для всех живых обязательств.

Зачем отдельный скрипт: `reissue_predicate.py` умеет только переход v1 → v4 и ищет строго
`check_fact_in_conclusions.py`. Здесь другая задача — сменить область поиска (из выводов
убраны рабочие черновики агентов) для всех обещаний сразу, при этом не трогая старые
инварианты: реестр append-only, история версий 1–6 остаётся.

Что делает:
  1. Для каждого живого обязательства (kind requirement/constraint, статус не dead) добавляет
     инвариант с предикатом v7 и переходом `[req_id]`, если такого ещё нет.
  2. Прогоняет v7 по каждому переходу и пишет доказательство с фактическим результатом
     (pass/fail), а не с ожидаемым.

Запуск:
  CORPUS_ROOT=$PWD python3 docs/registry/tools/reissue_v7.py --dry-run
  CORPUS_ROOT=$PWD python3 docs/registry/tools/reissue_v7.py --apply
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("CORPUS_ROOT") or Path.cwd()).resolve()
REGISTRY = ROOT / "docs/registry"
PREDICATE = "docs/registry/checkers/check_fact_in_conclusions_v7.py"
VERSION = "7"
BY = "agent:hermes/fact-corpus-pipeline"
DEAD = {"rejected", "superseded"}
OBLIGATIONS = {"requirement", "constraint"}


def load(name: str) -> list[dict]:
    # реестр требований лежит прямо в docs/, остальные журналы — в docs/registry/
    path = (ROOT / "docs" / name) if name.startswith("requirements") else (REGISTRY / name)
    if not path.is_file():
        raise SystemExit(f"нет {path}")
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def grace(*args: str) -> str:
    grace_py = Path(os.environ.get("GRACE_REGISTRY",
                                   Path.home() / "projects/vector-grace/registry")) / "grace.py"
    done = subprocess.run([sys.executable, str(grace_py), "--root", str(ROOT), *args],
                          capture_output=True, text=True)
    if done.returncode not in (0, 1):
        raise SystemExit(f"grace {' '.join(args)} → {done.returncode}\n{done.stdout}\n{done.stderr}")
    return done.stdout.strip()


def check(transition: str) -> tuple[str, str]:
    done = subprocess.run([sys.executable, str(ROOT / PREDICATE), "--root", str(ROOT),
                           "--transition", transition], capture_output=True, text=True)
    body = json.loads(done.stdout.strip().splitlines()[-1])
    return ("pass" if body.get("ok") else "fail"), str(body.get("detail") or "")


def latest(rows: list[dict], key: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows:
        rid = str(row.get(key) or "")
        if not rid:
            continue
        cur = out.get(rid)
        if cur is None or int(row.get("rev") or 1) > int(cur.get("rev") or 1):
            out[rid] = row
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not (args.apply or args.dry_run):
        raise SystemExit("нужен --dry-run или --apply")

    reqs = latest(load("requirements-registry.jsonl"), "req_id")
    invariants = load("invariants.jsonl")
    live = sorted(rid for rid, row in reqs.items()
                  if row.get("status") not in DEAD and row.get("kind") in OBLIGATIONS)
    v7 = [row for row in invariants if row.get("predicate", {}).get("path") == PREDICATE]
    done = {row["req_id"] for row in v7}
    proved = {(row.get("inv_id"), row.get("transition"))
              for row in load("evidence.jsonl") if row.get("req_id")}
    plan = [rid for rid in live if rid not in done]
    # инвариант мог добавиться, а доказательство — не записаться: доводим до конца,
    # причём по каждому v7-инварианту, а не только по последнему
    tail = [(row["req_id"], row["inv_id"]) for row in v7
            if row["req_id"] in live and (row["inv_id"], row["req_id"]) not in proved]
    print(f"живых обязательств: {len(live)}, уже с v7: {len(done & set(live))}, "
          f"перевыпустить: {len(plan)}, добрать доказательства: {len(tail)}")

    results = {rid: check(rid) for rid in plan}
    failed = [rid for rid, (result, _d) in results.items() if result != "pass"]
    for rid, (result, detail) in sorted(results.items()):
        if result != "pass":
            print(f"  {rid}: {result} | {detail[:110]}")
    print(f"проходят: {len(plan) - len(failed)}, падают: {len(failed)}")

    if args.dry_run:
        print("пробный прогон: реестр не изменён")
        return 0

    digest = sha256(ROOT / PREDICATE)
    for rid, inv_id in tail:
        result, detail = check(rid)
        grace("evidence", "--req", rid, "--inv", inv_id, "--transition", rid,
              "--result", result,
              "--defeater", "если число выпадет из выводов, приложения или сменит адрес",
              "--detail", detail[:400], "--by", BY)
        print(f"  {rid}: {inv_id} → {result} (добрано)")
    for rid in plan:
        transition = rid
        output = grace("invariant-add", "--req", rid, "--predicate", PREDICATE,
                       "--checker-version", VERSION, "--transition", transition,
                       "--kind", "analytic", "--by", BY)
        match = re.search(r"INV-\d+", output)
        if not match:
            raise SystemExit(f"не разобрал номер инварианта из {output!r}")
        inv_id = match.group(0)
        result, detail = results[rid]
        grace("evidence", "--req", rid, "--inv", inv_id, "--transition", transition,
              "--result", result,
              "--defeater", "если число выпадет из выводов, приложения или сменит адрес",
              "--detail", detail[:400], "--by", BY)
        print(f"  {rid}: {inv_id} → {result}")
    print(f"предикат v7, sha256 {digest[:12]}, инвариантов добавлено: {len(plan)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
