#!/bin/bash
set -euo pipefail
# Executa a partir da raiz do repositório.
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
  printf '%s\n' 'Execute no Mac Apple Silicon, com Terminal e Python nativos.'
  exit 1
fi
fonte_mode="${1:---app}"
case "$fonte_mode" in --app|--motor) ;; *) printf '%s\n' 'Uso: bash scripts/montar-lume.command [--app|--motor]'; exit 1 ;; esac
if [ "$fonte_mode" = --app ]; then
  if ! xcodebuild -version >/dev/null 2>&1; then
    printf '%s\n' 'Instale/abra o Xcode e selecione sua instalação em Settings > Locations > Command Line Tools.'
    exit 1
  fi
fi
if [ ! -x fonte/.venv/bin/python ]; then
  /bin/bash fonte/instalar.sh
fi
fonte_python="$PWD/fonte/.venv/bin/python"
"$fonte_python" -c 'import platform; assert platform.machine() == "arm64", "Use um ambiente Python arm64 nativo"'
# Reinstala do zero, em modo editável: o Python importa sempre os fontes de fonte/, nunca uma cópia
# antiga. O modo compat põe fonte/ no sys.path, para a pasta de mesmo nome na raiz não ser lida
# como pacote de namespace. O cache fonte/build pode reintroduzir cópias antigas.
rm -rf fonte/build
"$fonte_python" -m pip install --upgrade --force-reinstall --no-deps -e ./fonte --config-settings editable_mode=compat
# Coerência com IA (Claude): instalada em modo editável; o motor congelado usa os fontes de coerencia.
"$fonte_python" -m pip install -e coerencia
# Caches copiados com datas futuras podem fazer setuptools reutilizar código antigo.
"$fonte_python" - <<'PYVERIFY'
from pathlib import Path
import fonte
source = Path('fonte/fonte')
installed = Path(fonte.__file__).parent
mismatched = [str(path.relative_to(source)) for path in source.rglob('*')
              if path.is_file() and path.suffix == '.py'
              and (not (installed / path.relative_to(source)).is_file()
                   or path.read_bytes() != (installed / path.relative_to(source)).read_bytes())]
mismatched += [str(path.relative_to(installed)) + ' (sobra)' for path in installed.rglob('*.py')
               if '__pycache__' not in path.parts and not (source / path.relative_to(installed)).is_file()]
if mismatched:
    raise SystemExit('Instalação divergente do código-fonte: ' + ', '.join(mismatched)
                     + '. Mova fonte/build para uma pasta de backup e execute a montagem novamente.')
PYVERIFY
"$fonte_python" -m pip install 'pyinstaller==6.22.3'
if ! "$fonte_python" -c 'import pt_core_news_sm' >/dev/null 2>&1; then
  "$fonte_python" -m pip install 'https://github.com/explosion/spacy-models/releases/download/pt_core_news_sm-3.8.0/pt_core_news_sm-3.8.0-py3-none-any.whl'
fi
fonte_output="$PWD/build/$(date +%Y%m%d-%H%M%S)-$(uuidgen | cut -c1-8)"
mkdir -p "$fonte_output"
printf '%s\n' 'Executando regressões do analisador e dos pacotes antes da montagem.'
if ! "$fonte_python" -m unittest discover -s fonte/tests >"$fonte_output/testes-analisador.log" 2>&1; then
  tail -n 50 "$fonte_output/testes-analisador.log"
  exit 1
fi
if ! "$fonte_python" -m unittest discover -s tests -p 'test_*.py' >"$fonte_output/testes-pacotes.log" 2>&1; then
  tail -n 50 "$fonte_output/testes-pacotes.log"
  exit 1
fi
if [ ! -f fonte/.languagetool/languagetool-server.jar ]; then
  printf '%s\n' 'Preparando o corretor gramatical embutido (LanguageTool e Java mínimo). Requer JDK 17+ e internet.'
  "$fonte_python" scripts/preparar_languagetool.py
fi
"$fonte_python" scripts/build_engine.py --output "$fonte_output"
fonte_engine="$(cat "$fonte_output/engine-path.txt")"
if [ "$fonte_mode" = --motor ]; then
  printf '\n%s\n' 'Atualização independente criada. Envie o .lumemotor.zip; extraia e importe a pasta .lumemotor no Lume.' "$fonte_output"
  open "$fonte_output"
  exit 0
fi
printf '%s\n' 'Compilando a interface. Acompanhe o registro xcodebuild.log na pasta de saída.'
if ! xcodebuild -project app/Lume.xcodeproj -scheme Lume -configuration Release -derivedDataPath "$fonte_output/DerivedData" ARCHS=arm64 build >"$fonte_output/xcodebuild.log" 2>&1; then
  tail -n 40 "$fonte_output/xcodebuild.log"
  exit 1
fi
swiftc app/Lume/Models.swift app/Lume/PythonRunner.swift tests/ContractCheck.swift -o "$fonte_output/contrato-swift"
"$fonte_output/contrato-swift" examples/Mestre/relatorio.json "$fonte_python"
swiftc app/Lume/Models.swift app/Lume/ManuscriptEditor.swift tests/EditCheck.swift -o "$fonte_output/edicao-swift"
swiftc app/Lume/Models.swift tests/FalsePositiveCheck.swift -o "$fonte_output/falsos-positivos-swift"
swiftc app/Lume/Models.swift tests/BookMemoryCheck.swift -o "$fonte_output/livro-swift"
swiftc app/Lume/Models.swift tests/DeskToolsCheck.swift -o "$fonte_output/mesa-swift"
swiftc app/Lume/Models.swift tests/ClosureCheck.swift -o "$fonte_output/encerramento-swift"
swiftc app/Lume/Models.swift tests/DeduplicationCheck.swift -o "$fonte_output/deduplicacao-swift"
swiftc app/Lume/Models.swift tests/PartialAnalysisCheck.swift -o "$fonte_output/analise-parcial-swift"
"$fonte_output/livro-swift"
"$fonte_output/deduplicacao-swift"
"$fonte_output/analise-parcial-swift"
"$fonte_output/mesa-swift"
"$fonte_output/encerramento-swift"
"$fonte_output/falsos-positivos-swift"
"$fonte_output/edicao-swift"
"$fonte_python" scripts/package_app.py \
  --app "$fonte_output/DerivedData/Build/Products/Release/Lume.app" \
  --engine "$fonte_engine" --output "$fonte_output/Pacote"
fonte_app="$fonte_output/Pacote/Lume.app"
printf '\n%s\n' 'Concluído. Abra Lume.app; ele já contém Python, modelo e analisador.' "$fonte_app"
open "$fonte_output"
