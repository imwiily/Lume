#!/bin/bash
set -euo pipefail
fonte_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -x "$fonte_dir/.venv/bin/python" ]; then
  printf '%s\n' 'Primeiro execute: bash instalar.sh'
  exit 1
fi
if [ "$#" -eq 0 ]; then
  printf '%s\n' 'Uso: bash revisar.sh "/caminho/Livro.docx" [--tempo passado] [--languagetool]'
  exit 1
fi
exec "$fonte_dir/.venv/bin/python" -m fonte revisar "$@"
