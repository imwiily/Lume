import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import webbrowser

from . import __version__
from .pipeline import run as run_pipeline
from .reader import read_docx
from .report import render


def load_model():
    import spacy
    try:
        return spacy.load("pt_core_news_sm", disable=["ner"])
    except OSError as exc:
        raise ValueError("Modelo português ausente. Execute: python -m spacy download pt_core_news_sm (com o ambiente do projeto ativado).") from exc


def parser():
    root = argparse.ArgumentParser(description="FONTE — triagem editorial local, sem corrigir o manuscrito.")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    review = commands.add_parser("revisar", help="Ler DOCX e gerar HTML + JSON")
    review.add_argument("arquivo", type=Path)
    review.add_argument("--saida", type=Path, help="Pasta nova para os relatórios (nunca sobrescreve)")
    review.add_argument("--config", type=Path, help="Configuração JSON das verificações e estrutura do manuscrito")
    review.add_argument("--modo", choices=["linguistica", "editorial", "ambas"], default="linguistica")
    review.add_argument("--original", type=Path, help="DOCX original opcional para procurar cicatrizes de edição")
    review.add_argument("--tempo", choices=["auto", "passado", "presente"], default="auto")
    review.add_argument("--incluir-italico", action="store_true", help="Analisar também itálicos na narração")
    review.add_argument("--languagetool", action="store_true", help="Usar servidor local opcional; nenhum serviço na nuvem")
    review.add_argument("--porta-lt", type=int, default=8081)
    review.add_argument("--abrir", action="store_true", help="Abrir relatório no navegador")
    commands.add_parser("diagnostico", help="Conferir Python e modelo instalado")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "diagnostico":
            nlp = load_model()
            from .lexicon import data as lexical_data
            entries = len(lexical_data())
            print(f"FONTE {__version__} · Python {sys.version.split()[0]} · modelo {nlp.meta['name']} {nlp.meta['version']}")
            print(f"Confirmação lexical local: {entries} formas no PortiLexicon-UD.")
            print("Pronto para análise narrativa. LanguageTool é opcional e precisa de um servidor local separado.")
            return 0
        path = args.arquivo.expanduser().resolve()
        if not path.is_file():
            raise ValueError("Arquivo não encontrado. Arraste um .docx para o Terminal para inserir o caminho.")
        if path.stat().st_size > 50_000_000:
            raise ValueError("Limite desta versão: DOCX de até 50 MB.")
        if args.saida and args.saida.expanduser().resolve().exists():
            raise ValueError("A pasta de saída já existe. Escolha uma pasta nova para preservar relatórios anteriores.")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        from .settings import load as load_settings, validate as validate_settings
        settings=load_settings(args.config) if args.config else validate_settings({})
        blocks, warnings = read_docx(path, settings)
        if args.original and args.modo == "linguistica":
            raise ValueError("A comparação com original exige o modo editorial ou ambas.")
        if args.languagetool and args.modo == "editorial":
            raise ValueError("LanguageTool exige o modo linguistica ou ambas.")
        print(f"Lendo {len(blocks)} parágrafos não vazios. Modo: {args.modo}…", flush=True)
        original_blocks = None
        original_metadata = {}
        if args.original:
            original_path = args.original.expanduser().resolve()
            if not original_path.is_file() or original_path.stat().st_size > 50_000_000:
                raise ValueError("Original ausente ou maior que 50 MB.")
            original_blocks, original_warnings = read_docx(original_path, settings)
            warnings.extend("Original: " + w for w in original_warnings)
            original_metadata = {"original": original_path.name,
                                 "original_sha256": hashlib.sha256(original_path.read_bytes()).hexdigest()}
        if args.incluir_italico and not args.config:
            settings["italic_thoughts"] = False
        def progress(event):
            print("LUME_PROGRESS " + json.dumps(event, ensure_ascii=False), flush=True)
        findings, extra_warnings, metadata = run_pipeline(
            blocks, load_model, settings=settings, tense=args.tempo, mode=args.modo,
            original=original_blocks, languagetool=args.languagetool, port=args.porta_lt,
            progress=progress)
        metadata.update(original_metadata)
        warnings.extend(extra_warnings)
        if args.config and not any(settings['rules'].values()) and not args.languagetool:
            warnings.append("Todas as verificações estão desativadas nesta configuração. A ausência de alertas não representa uma análise do conteúdo.")
        metadata['search_settings']=settings if args.config else None
        metadata['chapters']=[{'paragraph':b.number,'title':b.chapter} for b in blocks if b.heading]
        if args.config:
            warnings.append("Filtros aplicados antes da busca. Falas/pensamentos são separados pelas marcações configuradas; pensamentos implícitos e diálogos ambíguos podem ser classificados incorretamente. Estrutura e acentuação contextual são verificadas na narração; pontuação duplicada, espaçamento e quê final também em falas/pensamentos. LanguageTool mantém sua proteção própria de falas/itálicos.")
        metadata.update({"languagetool": args.languagetool, "versao_fonte": __version__})
        data = {"schema_version": 1, "document": path.name, "sha256": digest,
                "created": datetime.now(timezone.utc).isoformat(), "metadata": metadata,
                "warnings": warnings, "findings": findings}
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("O manuscrito mudou durante a análise. Execute novamente sobre a versão atual.")
        # Não escreve nada até concluir os analisadores. A pasta sempre é nova.
        if args.saida:
            output = args.saida.expanduser().resolve()
            output.mkdir(parents=True, exist_ok=False)
        else:
            output = Path(tempfile.mkdtemp(prefix=path.stem + "-revisao-", dir=path.parent))
        for name, content in [("relatorio.html", render(data)),
                              ("relatorio.json", json.dumps(data, ensure_ascii=False, indent=2))]:
            with (output / name).open("x", encoding="utf-8") as handle:
                handle.write(content)
        print(f"{len(findings)} suspeitas para avaliação humana. Isso não mede a qualidade nem certifica a publicação.")
        print(f"Relatório: {output / 'relatorio.html'}")
        print("Manuscrito preservado. Corretor gramatical geral: " + ("LanguageTool local" if args.languagetool else "não executada (opcional)"))
        if args.abrir:
            webbrowser.open((output / "relatorio.html").as_uri())
        return 0
    except KeyboardInterrupt:
        print("\nAnálise interrompida. Manuscrito preservado.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
