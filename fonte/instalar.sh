#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
fonte_python="${FONTE_PYTHON:-}"
if [ -z "$fonte_python" ]; then
  for candidate in python3.12 python3.13 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; assert (3,10) <= sys.version_info[:2] < (3,14)' >/dev/null 2>&1; then
      fonte_python="$candidate"
      break
    fi
  done
fi
if [ -z "$fonte_python" ]; then
  printf '%s\n' 'Instale Python 3.12 e execute novamente. Se já usa Homebrew: brew install python@3.12' 'Também é possível instalar pelo site https://www.python.org/downloads/macos/'
  exit 1
fi
"$fonte_python" -c 'import sys; assert (3,10) <= sys.version_info[:2] < (3,14), "Use Python 3.10 a 3.13"'
printf '%s\n' 'Criando ambiente isolado e instalando dependências. É necessária internet nesta etapa.'
"$fonte_python" -m venv .venv
.venv/bin/python -m pip install -e . --config-settings editable_mode=compat
.venv/bin/python -m spacy download pt_core_news_sm
.venv/bin/python -m fonte diagnostico
printf '%s\n' 'Instalação concluída. Use: bash revisar.sh "/caminho/Livro.docx"'
