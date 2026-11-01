"""Перевыпуск инвариантов под новый предикат: новый чекер, новая версия, новые доказательства.

Зачем скриптом: правка зарегистрированного чекера обнуляет все доказательства, поэтому
новый предикат живёт отдельным файлом, инварианты перевыпускаются с его sha256, а
доказательства пишутся заново прогоном чекера по каждому переходу.

Старый чекер не трогается: его записи остаются историей, replay видит только последние
инварианты и доказательства.

Осторожно: это пишет в реестр (append-only). Запуск:
  CORPUS_ROOT=$PWD python3 docs/registry/tools/reissue_predicate.py --dry-run
  CORPUS_ROOT=$PWD python3 docs/registry/tools/reissue_predicate.py --apply
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CORPUS_ROOT") or Path.cwd()).resolve()
REGISTRY = ROOT / "docs/registry"
GRACE = Path(os.environ.get("GRACE_REGISTRY", Path.home() / "projects/vector-grace/registry")) / "grace.py"
OLD = "docs/registry/checkers/check_fact_in_conclusions.py"
NEW = "docs/registry/checkers/check_fact_in_conclusions_v4.py"
VERSION = "4"
BY = "agent:hermes/registry-0.1"


def load(name: str) -> list[dict]:
    path = REGISTRY / name
    if not path.is_file():
        raise SystemExit(f"нет {path}")
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def grace(*args: str) -> str:
    done = subprocess.run([sys.executable, str(GRACE), "--root", str(ROOT), *args],
                          capture_output=True, text=True)
    if done.returncode not in (0, 1):
        raise SystemExit(f"grace {' '.join(args)} → {done.returncode}\n{done.stdout}\n{done.stderr}")
    return done.stdout.strip()


def check(transition: str) -> tuple[str, str]:
    done = subprocess.run([sys.executable, str(ROOT / NEW), "--root", str(ROOT),
                           "--transition", transition], capture_output=True, text=True)
    body = json.loads(done.stdout.strip().splitlines()[-1])
    return ("pass" if body.get("ok") else "fail"), str(body.get("detail") or "")


def span_ids() -> dict[tuple[str, int], str]:
    index: dict[tuple[str, int], str] = {}
    path = REGISTRY / "spans.jsonl"
    if path.is_file():
        for line in path.read_text("utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            span = row.get("span") or [None, None]
            if row.get("file") and span[0] is not None:
                index[(row["file"], int(span[0]))] = row["span_id"]
    return index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", action="append", help="только это требование")
    args = parser.parse_args()
    if not (args.apply or args.dry_run):
        raise SystemExit("нужен --dry-run или --apply")

    invariants = load("invariants.jsonl")
    evidence = load("evidence.jsonl")
    old_invariants = [item for item in invariants if item["predicate"]["path"] == OLD]
    by_req: dict[str, dict] = {}
    for item in old_invariants:
        current = by_req.setdefault(item["req_id"], {"transitions": [], "kind": item.get("kind", "analytic")})
        for transition in item.get("transitions", []):
            if transition not in current["transitions"]:
                current["transitions"].append(transition)
    live: dict[str, str] = {}
    for row in (json.loads(line) for line in
                (ROOT / "docs/requirements-registry.jsonl").read_text("utf-8").splitlines()
                if line.strip()):
        live[row["req_id"]] = row.get("status", "")
    dead = {"rejected", "superseded"}
    skipped = sorted(req for req in by_req if live.get(req) in dead)
    for req in skipped:
        by_req.pop(req, None)
    if skipped:
        print(f"пропущены мёртвые требования: {', '.join(skipped)}")
    if args.only:
        by_req = {req: body for req, body in by_req.items() if req in args.only}

    previous: dict[tuple[str, str], str] = {}
    for row in evidence:
        if row.get("req_id") and row.get("transition"):
            previous[(row["req_id"], row["transition"])] = row.get("result")

    flipped, rows = [], []
    for req in sorted(by_req):
        body = by_req[req]
        results = {transition: check(transition) for transition in body["transitions"]}
        rows.append((req, body, results))
        for transition, (result, detail) in results.items():
            before = previous.get((req, transition))
            if before != result:
                flipped.append((req, transition, before, result, detail))

    print(f"требований под предикатом: {len(rows)}, переходов: "
          f"{sum(len(body['transitions']) for _req, body, _res in rows)}")
    for req, transition, before, result, detail in flipped:
        print(f"  {req} [{transition}]: {before} → {result} | {detail[:110]}")
    if args.dry_run:
        print("пробный прогон: реестр не изменён")
        return 0

    spans = span_ids()
    requirements = {row["req_id"]: row for row in
                    (json.loads(line) for line in
                     (ROOT / "docs/requirements-registry.jsonl").read_text("utf-8").splitlines()
                     if line.strip())}
    existing: dict[str, str] = {}
    for item in invariants:
        if item["predicate"]["path"] == NEW:
            existing[item["req_id"]] = item["inv_id"]
    latest_evidence: dict[tuple[str, str], dict] = {}
    for row in evidence:
        if row.get("req_id") and row.get("transition"):
            latest_evidence[(row["req_id"], row["transition"])] = row

    written = 0
    for req, body, results in rows:
        if req in existing:
            inv_id = existing[req]
            print(f"  {inv_id} → {req}: инвариант уже перевыпущен")
        else:
            out = grace("invariant-add", "--req", req, "--predicate", NEW,
                        "--transitions", ",".join(body["transitions"]),
                        "--checker-version", VERSION, "--kind", body["kind"], "--by", BY)
            inv_id = out.split(":", 1)[0].strip()
        source = requirements.get(req, {}).get("source", {})
        span = spans.get((source.get("file"), int((source.get("span") or [0])[0]))) if source else None
        for transition, (result, detail) in results.items():
            done = latest_evidence.get((req, transition))
            if done and done.get("result") == result and done.get("inv_id") == inv_id:
                continue
            defeat = (f"факт не упомянут ни по основам, ни дословно: {detail[:200]}" if result == "fail"
                      else f"факт упомянут: {detail[:200]}")
            extra = ["--source-span", span] if span else []
            grace("evidence", "--req", req, "--inv", inv_id, "--transition", transition,
                  "--result", result, "--defeater", defeat, "--detail", detail[:400],
                  *extra, "--by", BY)
            written += 1
        print(f"  {inv_id} → {req}: переходов {len(results)}")
    print(f"записано доказательств: {written}, инвариантов: {len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
