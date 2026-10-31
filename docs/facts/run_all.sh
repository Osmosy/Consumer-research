#!/usr/bin/env bash
# Полный прогон конвейера: все колоды, обе модели, затем сравнение по каждой.
set -u
cd "$(dirname "$0")/../.." || exit 1
DECKS="ekopsi-debaty-pro-pokoleniya nielsen-fmcg-do-avgusta-2026 nielsen-itogi-2025-vektory-2026 romir-trendy-2026 sbermarket-globalnye-trendy-2026 sbermarket-serebryanyy-vozrast-2026"
for deck in $DECKS; do
  for backend in zcode ollama; do
    echo "=== $deck / $backend ==="
    python3 docs/facts/run_analysis.py --backend "$backend" --deck "$deck" || echo "  сбой $deck/$backend"
  done
  python3 docs/facts/compare_analyses.py "$deck"
done
echo "=== готово ==="
