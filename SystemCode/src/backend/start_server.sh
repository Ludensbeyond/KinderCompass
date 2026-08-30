#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." && pwd)"
PYTHON="${REPOSITORY_ROOT}/.venv/bin/python"

if [[ ! -x "${PYTHON}" ]]; then
  echo "Python virtual environment not found at ${PYTHON}" >&2
  exit 1
fi

cd "${REPOSITORY_ROOT}"
exec "${PYTHON}" -m uvicorn SystemCode.src.backend.main:app --reload "$@"
