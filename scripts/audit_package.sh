#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-}"

patterns=(
  '__pycache__'
  '.pytest_cache'
  '.mypy_cache'
  '.ruff_cache'
  'htmlcov'
  'playwright-report'
  'test-results'
  'node_modules'
  'dist'
  'build'
)

find_artifacts() {
  cd "$ROOT_DIR"
  find . \( \
    -name '__pycache__' -o -name '.pytest_cache' -o -name '.mypy_cache' -o -name '.ruff_cache' -o \
    -name '.coverage' -o -name '.tsbuildinfo' -o -name 'htmlcov' -o -name 'playwright-report' -o -name 'test-results' -o \
    -name 'node_modules' -o -name 'dist' -o -name 'build' -o -name '.venv' -o -name '.DS_Store' -o \
    -name '*.pyc' -o -name '*.pyo' -o -name '*.log' -o -name '*.bak' -o -name '*.prepatch' -o -name '*.prep2' -o \
    -path './api-server/reports/*' \
  \) -print | sort
}

if [[ "$MODE" == "--check" ]]; then
  if artifacts="$(find_artifacts)" && [[ -n "$artifacts" ]]; then
    echo "Packaging audit FAILED — artefacts détectés:"
    echo "$artifacts"
    exit 1
  fi
  echo "Packaging audit OK — aucun artefact inutile détecté."
  exit 0
fi

cd "$ROOT_DIR"
find . -type d \( -name '__pycache__' -o -name '.pytest_cache' -o -name '.mypy_cache' -o -name '.ruff_cache' -o -name 'htmlcov' -o -name 'playwright-report' -o -name 'test-results' -o -name 'node_modules' -o -name 'dist' -o -name 'build' -o -name '.venv' \) -prune -exec rm -rf {} +
find . -type f \( -name '.coverage' -o -name '.tsbuildinfo' -o -name '.DS_Store' -o -name '*.pyc' -o -name '*.pyo' -o -name '*.log' -o -name '*.bak' -o -name '*.prepatch' -o -name '*.prep2' -o -path './api-server/reports/*' \) -delete

echo "Packaging audit cleanup completed."
find_artifacts
