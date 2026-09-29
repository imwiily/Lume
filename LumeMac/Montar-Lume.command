#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
  printf '%s\n' 'Execute no Mac Apple Silicon, com Terminal e Python nativos.'
  exit 1
fi
fonte_mode="${1:---app}"
case "$fonte_mode" in --app|--motor) ;; *) printf '%s\n' 'Uso: bash Montar-Lume.command [--app|--motor]'; exit 1 ;; esac
if [ "$fonte_mode" = --app ]; then
  if ! xcodebuild -version >/dev/null 2>&1; then
    printf '%s\n' 'Instale/abra o Xcode e selecione sua instalação em Settings > Locations > Command Line Tools.'
    exit 1
  fi
fi
if [ ! -x Analisador/.venv/bin/python ]; then
  /bin/bash Analisador/instalar.sh
fi
fonte_python="$PWD/Analisador/.venv/bin/python"
"$fonte_python" -c 'import platform; assert platform.machine() == "arm64", "Use um ambiente Python arm64 nativo"'
"$fonte_python" -m pip install --upgrade ./Analisador
# Coerência com IA (Claude): instalada em modo editável; o motor congelado usa os fontes de ../LumeCoerencia.
"$fonte_python" -m pip install -e ../LumeCoerencia
# Caches copiados com datas futuras podem fazer setuptools reutilizar código antigo.
"$fonte_python" - <<'PYVERIFY'
from pathlib import Path
import fonte
source = Path('Analisador/fonte')
installed = Path(fonte.__file__).parent
mismatched = [str(path.relative_to(source)) for path in source.rglob('*')
              if path.is_file() and path.suffix in {'.py', '.html'}
              and (not (installed / path.relative_to(source)).is_file()
                   or path.read_bytes() != (installed / path.relative_to(source)).read_bytes())]
if mismatched:
    raise SystemExit('Instalação divergente do código-fonte: ' + ', '.join(mismatched)
                     + '. Mova Analisador/build para uma pasta de backup e execute a montagem novamente.')
PYVERIFY
"$fonte_python" -m pip install 'pyinstaller==6.22.3'
if ! "$fonte_python" -c 'import pt_core_news_sm' >/dev/null 2>&1; then
  "$fonte_python" -m pip install 'https://github.com/explosion/spacy-models/releases/download/pt_core_news_sm-3.8.0/pt_core_news_sm-3.8.0-py3-none-any.whl'
fi
fonte_output="$PWD/Saida/$(date +%Y%m%d-%H%M%S)-$(uuidgen | cut -c1-8)"
mkdir -p "$fonte_output"
printf '%s\n' 'Executando regressões do analisador e dos pacotes antes da montagem.'
if ! "$fonte_python" -m unittest discover -s Analisador/tests >"$fonte_output/testes-analisador.log" 2>&1; then
  tail -n 50 "$fonte_output/testes-analisador.log"
  exit 1
fi
if ! "$fonte_python" -m unittest discover -s Tests -p 'test_*.py' >"$fonte_output/testes-pacotes.log" 2>&1; then
  tail -n 50 "$fonte_output/testes-pacotes.log"
  exit 1
fi
if [ ! -f Analisador/.languagetool/languagetool-server.jar ]; then
  printf '%s\n' 'Preparando o corretor gramatical embutido (LanguageTool e Java mínimo). Requer JDK 17+ e internet.'
  "$fonte_python" Scripts/preparar_languagetool.py
fi
"$fonte_python" Scripts/build_engine.py --output "$fonte_output"
fonte_engine="$(cat "$fonte_output/engine-path.txt")"
if [ "$fonte_mode" = --motor ]; then
  printf '\n%s\n' 'Atualização independente criada. Envie o .lumemotor.zip; extraia e importe a pasta .lumemotor no Lume.' "$fonte_output"
  open "$fonte_output"
  exit 0
fi
printf '%s\n' 'Compilando a interface. Acompanhe o registro xcodebuild.log na pasta de saída.'
if ! xcodebuild -project Lume.xcodeproj -scheme Lume -configuration Release -derivedDataPath "$fonte_output/DerivedData" ARCHS=arm64 build >"$fonte_output/xcodebuild.log" 2>&1; then
  tail -n 40 "$fonte_output/xcodebuild.log"
  exit 1
fi
swiftc Lume/Models.swift Lume/PythonRunner.swift Tests/ContractCheck.swift -o "$fonte_output/contrato-swift"
"$fonte_output/contrato-swift" Exemplo/Mestre/relatorio.json "$fonte_python"
"$fonte_python" Scripts/package_app.py \
  --app "$fonte_output/DerivedData/Build/Products/Release/Lume.app" \
  --engine "$fonte_engine" --output "$fonte_output/Pacote"
fonte_app="$fonte_output/Pacote/Lume.app"
printf '\n%s\n' 'Concluído. Abra Lume.app; ele já contém Python, modelo e analisador.' "$fonte_app"
open "$fonte_output"
