import argparse
from contextlib import ExitStack, nullcontext
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

from . import __version__
from .pipeline import run as run_pipeline
from .reader import read_manuscript


def load_model():
    import spacy
    try:
        return spacy.load("pt_core_news_sm", disable=["ner"])
    except OSError as exc:
        raise ValueError("Modelo português ausente. Execute: python -m spacy download pt_core_news_sm (com o ambiente do projeto ativado).") from exc


def coherence_options(command):
    command.add_argument("--coerencia-projeto", type=Path, help="Pasta de projeto da Coerência com IA deste manuscrito")
    command.add_argument("--coerencia-versao", type=int, choices=[1, 2], default=1,
                         help="1: leitura incremental por cena (padrão); 2: leitura global da obra em uma só requisição")
    command.add_argument("--coerencia-modelo", default="claude-sonnet-5-5",
                         help="Modelo (claude-sonnet-5-5, claude-opus-5-5, claude-haiku-4-5 ou gemini-3.8-flash)")


def audit_options(command):
    command.add_argument("--auditoria-projeto", type=Path, help="Pasta de projeto da Auditoria final com IA deste manuscrito")
    command.add_argument("--auditoria-modelo", default="claude-opus-5-5",
                         help="Modelo (claude-opus-5-5, claude-sonnet-5-5, claude-haiku-4-5 ou gemini-3.8-flash)")
    command.add_argument("--auditoria-esforco", default="medium", choices=["low", "medium", "high", "xhigh", "max"])


def parser():
    root = argparse.ArgumentParser(description="FONTE — triagem editorial local, sem corrigir o manuscrito.")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    review = commands.add_parser("revisar", help="Ler DOCX ou Pages e gerar o relatório JSON")
    review.add_argument("arquivo", type=Path)
    review.add_argument("--saida", type=Path, help="Pasta nova para os relatórios (nunca sobrescreve)")
    review.add_argument("--config", type=Path, help="Configuração JSON das verificações e estrutura do manuscrito")
    review.add_argument("--modo", choices=["linguistica", "editorial", "ambas"], default="linguistica")
    review.add_argument("--original", type=Path, help="DOCX ou Pages original opcional para procurar cicatrizes de edição")
    # Sem detecção automática: o tempo da narração é informado (passado ou presente).
    review.add_argument("--tempo", choices=["passado", "presente"], default="passado",
                        help="Tempo em que o livro é narrado (padrão: passado)")
    review.add_argument("--incluir-italico", action="store_true", help="Analisar também itálicos na narração")
    review.add_argument("--languagetool", action="store_true",
                        help="Usar o corretor gramatical local: o embutido, se existir; senão, um servidor já ativo. Nenhum serviço na nuvem")
    review.add_argument("--porta-lt", type=int,
                        help="Porta de um servidor LanguageTool já ativo (ignora o embutido; padrão 8081 quando não há embutido)")
    review.add_argument("--coerencia-ia", action="store_true",
                        help="Contradições narrativas com IA (envia os capítulos alterados à Anthropic ou ao Google, conforme o modelo)")
    coherence_options(review)
    review.add_argument("--coerencia-teto", type=float, default=1.0, help="Gasto máximo em US$ nesta análise")
    review.add_argument("--coerencia-esforco", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    review.add_argument("--auditoria-ia", action="store_true",
                        help="Auditoria final com IA: procura o que as etapas anteriores deixaram passar "
                             "(envia à Anthropic ou ao Google, conforme o modelo, os capítulos ainda não auditados)")
    audit_options(review)
    review.add_argument("--auditoria-teto", type=float, default=1.0, help="Gasto máximo em US$ da auditoria nesta análise")
    audit_estimate = commands.add_parser("auditoria-estimar",
                                         help="Estimar trechos e custo da Auditoria final com IA, sem chamar a API")
    audit_options(audit_estimate)
    audit_estimate.add_argument("arquivo", type=Path)
    audit_estimate.add_argument("--config", type=Path)
    audit_estimate.add_argument("--tempo", choices=["passado", "presente"], default="passado")
    estimate = commands.add_parser("coerencia-estimar",
                                   help="Estimar capítulos e custo da Coerência com IA, sem chamar a API")
    coherence_options(estimate)
    estimate.add_argument("arquivo", type=Path)
    estimate.add_argument("--config", type=Path)
    search = commands.add_parser("pesquisar-fundamento",
                                 help="Pesquisa Google (Gemini) de uma dúvida normativa abstrata; só sob pedido, sem manuscrito")
    search.add_argument("--pergunta", required=True, help="Pergunta linguística sem trechos do manuscrito")
    search.add_argument("--modelo", default="gemini-3.8-flash")
    search.add_argument("--teto", type=float, default=0.25, help="Gasto máximo em US$ desta pesquisa")
    search.add_argument("--estimar", action="store_true", help="Só calcula o pior caso; não chama a API")
    check = commands.add_parser("conferir-edicao",
                                help="Conferir que uma correção alterou só o parágrafo indicado; não grava nada")
    check.add_argument("antes", type=Path, help="Cópia do manuscrito antes da correção")
    check.add_argument("depois", type=Path, help="Manuscrito depois da correção")
    check.add_argument("--paragrafo", type=int, required=True)
    check.add_argument("--esperado", type=Path, required=True, help="Arquivo UTF-8 com o texto esperado do parágrafo")
    for nome, ajuda in (("validar-decisoes-estimar", "Estimar custo do Validador de decisões, sem chamar a API"),
                        ("validar-decisoes", "Reavaliar as decisões do autor com a API do Claude; não altera nada")):
        validar = commands.add_parser(nome, help=ajuda)
        validar.add_argument("arquivo", type=Path, help="Manuscrito atual (DOCX ou Pages)")
        validar.add_argument("--relatorio", type=Path, required=True, help="relatorio.json da análise")
        validar.add_argument("--decisoes", type=Path, required=True, help="JSON de decisões do app")
        validar.add_argument("--projeto", type=Path, required=True, help="Pasta de projeto do Validador deste manuscrito")
        validar.add_argument("--config", type=Path)
        validar.add_argument("--modo", choices=["hibrido", "sonnet_direto"], default="hibrido")
        validar.add_argument("--triagem-modelo", default="claude-haiku-5-5")
        validar.add_argument("--juiz-modelo", default="claude-sonnet-5-5")
        validar.add_argument("--amostra", type=float, default=0.1,
                             help="Fração das decisões mantidas pela triagem que o Sonnet confere (0 a 1)")
        validar.add_argument("--teto", type=float, default=1.0, help="Gasto máximo em US$ desta validação")
    for nome, ajuda in (("validar-decisoes-v5-estimar", "Estimar o envio e o custo da validação V5, sem rede"),
                        ("validar-decisoes-v5", "Segunda opinião (V5, OpenAI) sobre as decisões escolhidas; não altera nada"),
                        ("validar-decisoes-v5-resultados", "Resultados V5 já gravados, no estado atual; sem rede"),
                        ("validar-decisoes-v5-previa", "Texto exato que a V5 enviaria, sem rede")):
        v5 = commands.add_parser(nome, help=ajuda)
        v5.add_argument("arquivo", type=Path, help="Manuscrito atual (DOCX ou Pages)")
        v5.add_argument("--relatorio", type=Path, required=True)
        v5.add_argument("--decisoes", type=Path, required=True)
        v5.add_argument("--projeto", type=Path, required=True, help="Pasta de projeto do Validador deste manuscrito")
        v5.add_argument("--config", type=Path)
        v5.add_argument("--ids", nargs="*", default=[], help="IDs dos apontamentos (obrigatório para estimar e executar)")
        v5.add_argument("--ids-arquivo", type=Path, help="JSON com a lista de IDs")
        v5.add_argument("--max-itens", type=int, default=40, help="Limite de itens da execução (até 60)")
        v5.add_argument("--teto", type=float, default=1.0, help="Gasto máximo em US$ (padrão 1,00; máximo 5,00)")
        v5.add_argument("--permitir-contexto-parcial", action="store_true",
                        help="Aceita manuscrito de outra versão se o contexto registrado no relatório estiver presente")
        v5.add_argument("--autorizar-contexto-adicional", action="store_true",
                        help="Autoriza a segunda rodada de contexto pedida pelo modelo (desligada por padrão)")
        v5.add_argument("--reanalisar", nargs="*", default=[], help="IDs com resultado válido a reanalisar (histórico preservado)")
        v5.add_argument("--revalidar", nargs="*", default=[], help="IDs com resultado desatualizado a analisar de novo")
        v5.add_argument("--tentativas", type=int, choices=(1, 2, 3), help="Tentativas por requisição (padrão do cliente: 3)")
    commands.add_parser("diagnostico", help="Conferir Python e modelo instalado")
    return root


def estimate_coherence(args):
    """Uma linha JSON para o app: capítulos a enviar e custo estimado. Não chama a API."""
    from .settings import load as load_settings, validate as validate_settings
    from .coerencia_ia import estimar
    from .coerencia2_ia import estimar as estimar_global
    path = args.arquivo.expanduser().resolve()
    if not path.is_file():
        raise ValueError("Arquivo não encontrado.")
    if not args.coerencia_projeto:
        raise ValueError("Informe a pasta de projeto (--coerencia-projeto).")
    settings = load_settings(args.config) if args.config else validate_settings({})
    blocks, _ = read_manuscript(path, settings)
    project = args.coerencia_projeto.expanduser().resolve()
    result = (estimar_global if args.coerencia_versao == 2 else estimar)(blocks, project, args.coerencia_modelo)
    print("LUME_ESTIMATIVA " + json.dumps(result, ensure_ascii=False), flush=True)
    return 0


def estimate_audit(args):
    """Uma linha JSON para o app: trechos a enviar e custo estimado da auditoria. Não chama a API."""
    from .settings import load as load_settings, validate as validate_settings
    from .auditoria_ia import estimar
    path = args.arquivo.expanduser().resolve()
    if not path.is_file():
        raise ValueError("Arquivo não encontrado.")
    if not args.auditoria_projeto:
        raise ValueError("Informe a pasta de projeto (--auditoria-projeto).")
    settings = load_settings(args.config) if args.config else validate_settings({})
    blocks, _ = read_manuscript(path, settings)
    result = estimar(blocks, args.auditoria_projeto.expanduser().resolve(), tempo=args.tempo,
                     modelo=args.auditoria_modelo, esforco=args.auditoria_esforco)
    print("LUME_ESTIMATIVA_AUDITORIA " + json.dumps(result, ensure_ascii=False), flush=True)
    return 0


def search_ground(args):
    """Uma linha JSON para o app. Uma única chamada, só com `--pergunta`; `--estimar` não chama a API."""
    from . import pesquisa_gemini as pesquisa
    if args.estimar:
        print("LUME_PESQUISA_ESTIMATIVA " + json.dumps(pesquisa.estimar(args.pergunta, args.modelo), ensure_ascii=False), flush=True)
        return 0
    if not 0 < args.teto < float("inf"):
        raise ValueError("O teto da pesquisa precisa ser maior que zero.")
    print("LUME_PESQUISA " + json.dumps(pesquisa.pesquisar(args.pergunta, args.modelo, args.teto), ensure_ascii=False), flush=True)
    return 0


def validate_decisions(args, estimate_only):
    """Segunda leitura das decisões do autor. Só escreve na pasta de projeto; relatório, decisões e
    manuscrito ficam intactos. Uma linha JSON para o app, com o resumo."""
    from .settings import load as load_settings, validate as validate_settings
    from . import validador_decisoes as vd
    path = args.arquivo.expanduser().resolve()
    if not path.is_file():
        raise ValueError("Arquivo não encontrado.")
    try:
        findings = json.loads(args.relatorio.expanduser().read_text(encoding="utf-8"))["findings"]
        raw = json.loads(args.decisoes.expanduser().read_text(encoding="utf-8"))
        decisions = {str(k): str(v) for k, v in (raw.get("decisions", raw)).items()}
    except (OSError, ValueError, KeyError, AttributeError) as exc:
        raise ValueError("Relatório ou decisões ilegíveis.") from exc
    if not 0 <= args.amostra <= 1 or not 0 <= args.teto < float("inf"):
        raise ValueError("A amostra precisa estar entre 0 e 1 e o teto não pode ser negativo.")
    settings = load_settings(args.config) if args.config else validate_settings({})
    blocks, _ = read_manuscript(path, settings)
    project = args.projeto.expanduser().resolve()
    if estimate_only:
        result = vd.estimar(blocks, findings, decisions, project, args.modo, args.triagem_modelo, args.juiz_modelo,
                              teto=args.teto, configuracao=settings)
        print("LUME_ESTIMATIVA_VALIDADOR " + json.dumps(result, ensure_ascii=False), flush=True)
        return 0
    progress = lambda etapa, feitos, total: print("LUME_VALIDADOR_PROGRESSO " + json.dumps(
        {"etapa": etapa, "feitos": feitos, "total": total}), flush=True)
    meta = {"documento": path.name, "sha256_manuscrito": hashlib.sha256(path.read_bytes()).hexdigest()}
    _, warnings, summary = vd.validar(blocks, findings, decisions, pasta=project, modo=args.modo, teto=args.teto,
                                      amostra=args.amostra, triagem=args.triagem_modelo, juiz=args.juiz_modelo,
                                      avancar=progress, meta=meta, configuracao=settings)
    for warning in warnings:
        print(warning, flush=True)
    print("LUME_VALIDACAO " + json.dumps({"arquivo": str(project / vd.ESTADO), "resumo": summary},
                                         ensure_ascii=False), flush=True)
    return 0


def validate_decisions_v5(args, mode):
    """Integração supervisionada da V5. Só escreve na pasta de projeto; relatório, decisões e manuscrito ficam
    intactos. Cada resposta é uma linha JSON com prefixo próprio; falhas esperadas saem como LUME_VALIDADOR_V5_ERRO."""
    import signal
    from .settings import load as load_settings, validate as validate_settings
    from . import validador_v5_integracao as integracao
    def fail(codigo, mensagem):
        print("LUME_VALIDADOR_V5_ERRO " + json.dumps({"codigo": codigo, "mensagem": mensagem}, ensure_ascii=False), flush=True)
        return 2
    path = args.arquivo.expanduser().resolve()
    if not path.is_file():
        return fail("arquivo_ausente", "Arquivo não encontrado.")
    try:
        report = json.loads(args.relatorio.expanduser().read_text(encoding="utf-8"))
        findings = report["findings"]
        raw = json.loads(args.decisoes.expanduser().read_text(encoding="utf-8"))
        decisions = {str(k): str(v) for k, v in (raw.get("decisions", raw)).items()}
        ids = list(args.ids)
        if args.ids_arquivo:
            extra = json.loads(args.ids_arquivo.expanduser().read_text(encoding="utf-8"))
            ids += [str(i) for i in (extra.get("ids", extra) if isinstance(extra, dict) else extra)]
    except (OSError, ValueError, KeyError, AttributeError, TypeError):
        return fail("entrada_ilegivel", "Relatório, decisões ou lista de IDs ilegíveis.")
    settings = load_settings(args.config) if args.config else validate_settings({})
    blocks, _ = read_manuscript(path, settings)
    sha_file = hashlib.sha256(path.read_bytes()).hexdigest()
    sha_report = report.get("sha256")
    project = args.projeto.expanduser().resolve()
    common = dict(maximo=args.max_itens, permitir_parcial=args.permitir_contexto_parcial,
                  autorizar_contexto=args.autorizar_contexto_adicional, config=settings, revalidar=args.revalidar)
    try:
        if mode == "resultados":
            out = integracao.resultados(blocks, findings, decisions, project, ids=ids or None, config=settings)
            print("LUME_RESULTADOS_V5 " + json.dumps(out, ensure_ascii=False), flush=True)
            return 0
        if mode == "previa":
            out = integracao.previa(blocks, findings, decisions, ids, sha_file, sha_report, project, maximo=args.max_itens,
                                    permitir_parcial=args.permitir_contexto_parcial, config=settings,
                                    revalidar=args.revalidar)
            print("LUME_PREVIA_VALIDADOR_V5 " + json.dumps(out, ensure_ascii=False), flush=True)
            return 0
        if mode == "estimar":
            out = integracao.estimar(blocks, findings, decisions, ids, sha_file, sha_report, project, teto=args.teto, **common)
            print("LUME_ESTIMATIVA_VALIDADOR_V5 " + json.dumps(out, ensure_ascii=False), flush=True)
            return 0
        def terminate(signum, frame):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, terminate)         # cancelar devolve os itens em processamento
        progress = lambda etapa, feitos, total: print("LUME_VALIDADOR_V5_PROGRESSO " + json.dumps(
            {"etapa": etapa, "feitos": feitos, "total": total}), flush=True)
        simulado = os.environ.get("LUME_V5_TRANSPORTE_SIMULADO")     # só testes locais; o app nunca o define
        out = integracao.executar(blocks, findings, decisions, ids, sha_file, sha_report, project, teto=args.teto,
                                  reanalisar=args.reanalisar, tentativas=args.tentativas, avancar=progress,
                                  transporte=integracao.transporte_simulado(simulado) if simulado else None,
                                  meta={"documento": path.name, "sha256_manuscrito": sha_file}, **common)
        for warning in out.get("avisos", []):
            print(warning, flush=True)
        print("LUME_VALIDACAO_V5 " + json.dumps(out, ensure_ascii=False, default=str), flush=True)
        return 0
    except integracao.ErroIntegracao as exc:
        return fail(exc.codigo, str(exc))


def check_edit(args):
    """Uma linha JSON para o app com o hash do manuscrito corrigido. Só lê os dois arquivos."""
    from .reader import verify_edit
    before, after = (p.expanduser().resolve() for p in (args.antes, args.depois))
    if not before.is_file() or not after.is_file():
        raise ValueError("Arquivo não encontrado.")
    digest = hashlib.sha256(after.read_bytes()).hexdigest()
    verify_edit(before, after, args.paragrafo, args.esperado.read_text(encoding="utf-8"))
    print("LUME_EDICAO " + json.dumps({"sha256": digest}), flush=True)
    return 0


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "diagnostico":
            nlp = load_model()
            from .lexicon import data as lexical_data
            entries = len(lexical_data())
            print(f"FONTE {__version__} · Python {sys.version.split()[0]} · modelo {nlp.meta['name']} {nlp.meta['version']}")
            print(f"Confirmação lexical local: {entries} formas no PortiLexicon-UD.")
            from .languagetool import available
            print("Corretor gramatical local: " + ("embutido disponível." if available()
                  else "não embutido; use um servidor LanguageTool local separado."))
            print("Pronto para análise narrativa.")
            return 0
        if args.command == "coerencia-estimar":
            return estimate_coherence(args)
        if args.command == "auditoria-estimar":
            return estimate_audit(args)
        if args.command == "pesquisar-fundamento":
            return search_ground(args)
        if args.command == "conferir-edicao":
            return check_edit(args)
        if args.command in ("validar-decisoes-v5", "validar-decisoes-v5-estimar", "validar-decisoes-v5-resultados",
                            "validar-decisoes-v5-previa"):
            return validate_decisions_v5(args, {"validar-decisoes-v5": "executar", "validar-decisoes-v5-estimar": "estimar",
                                                "validar-decisoes-v5-resultados": "resultados",
                                                "validar-decisoes-v5-previa": "previa"}[args.command])
        if args.command in ("validar-decisoes", "validar-decisoes-estimar"):
            return validate_decisions(args, args.command.endswith("estimar"))
        path = args.arquivo.expanduser().resolve()
        if path.is_dir() and path.suffix.lower() == ".pages":
            raise ValueError("Este documento do Pages está salvo como pacote (pasta). No Pages: Arquivo → Avançado → Alterar Tipo de Arquivo → Arquivo Único.")
        if not path.is_file():
            raise ValueError("Arquivo não encontrado. Arraste um .docx ou .pages para o Terminal para inserir o caminho.")
        if path.stat().st_size > 50_000_000:
            raise ValueError("Limite desta versão: manuscrito de até 50 MB.")
        if args.saida and args.saida.expanduser().resolve().exists():
            raise ValueError("A pasta de saída já existe. Escolha uma pasta nova para preservar relatórios anteriores.")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        from .settings import load as load_settings, validate as validate_settings
        settings=load_settings(args.config) if args.config else validate_settings({})
        blocks, warnings = read_manuscript(path, settings)
        if args.original and args.modo == "linguistica":
            raise ValueError("A comparação com original exige o modo editorial ou ambas.")
        if args.coerencia_ia and (args.modo == "linguistica" or not args.coerencia_projeto):
            raise ValueError("A Coerência com IA exige o modo editorial ou ambas e uma pasta de projeto (--coerencia-projeto).")
        if args.auditoria_ia and not args.auditoria_projeto:
            raise ValueError("A Auditoria final com IA exige uma pasta de projeto (--auditoria-projeto).")
        if args.languagetool and args.modo == "editorial":
            raise ValueError("LanguageTool exige o modo linguistica ou ambas.")
        print(f"Lendo {len(blocks)} parágrafos não vazios. Modo: {args.modo}…", flush=True)
        original_blocks = None
        original_metadata = {}
        if args.original:
            original_path = args.original.expanduser().resolve()
            if not original_path.is_file() or original_path.stat().st_size > 50_000_000:
                raise ValueError("Original ausente ou maior que 50 MB.")
            original_blocks, original_warnings = read_manuscript(original_path, settings)
            warnings.extend("Original: " + w for w in original_warnings)
            original_metadata = {"original": original_path.name,
                                 "original_sha256": hashlib.sha256(original_path.read_bytes()).hexdigest()}
        if args.incluir_italico and not args.config:
            settings["italic_thoughts"] = False
        def progress(event):
            print("LUME_PROGRESS " + json.dumps(event, ensure_ascii=False), flush=True)
        from . import languagetool as grammar_checker
        origin = None
        if args.languagetool and args.porta_lt is None and grammar_checker.available():
            print("Iniciando o corretor gramatical local…", flush=True)
            server, origin = grammar_checker.embedded(), "embutido"
        else:
            server = nullcontext(args.porta_lt or 8081)
            origin = "externo" if args.languagetool else None
        with ExitStack() as stack:
            port, falha = None, None
            try:
                port = stack.enter_context(server)
            except grammar_checker.LanguageToolIndisponivel as exc:
                # O FONTE segue sem o corretor; o relatório registra a análise parcial.
                falha = str(exc)
            findings, extra_warnings, metadata = run_pipeline(
                blocks, load_model, settings=settings, tense=args.tempo, mode=args.modo,
                original=original_blocks, languagetool=args.languagetool, port=port, languagetool_falha=falha,
                progress=progress, coerencia=dict(
                    pasta=args.coerencia_projeto.expanduser().resolve(), documento=path.name,
                    modelo=args.coerencia_modelo, teto=args.coerencia_teto, esforco=args.coerencia_esforco,
                    versao=args.coerencia_versao)
                if args.coerencia_ia else None,
                auditoria=dict(pasta=args.auditoria_projeto.expanduser().resolve(), modelo=args.auditoria_modelo,
                               teto=args.auditoria_teto, esforco=args.auditoria_esforco)
                if args.auditoria_ia else None)
        metadata.update(original_metadata)
        warnings.extend(extra_warnings)
        if args.config and not any(settings['rules'].values()) and not args.languagetool:
            warnings.append("Todas as verificações estão desativadas nesta configuração. A ausência de alertas não representa uma análise do conteúdo.")
        metadata['search_settings']=settings if args.config else None
        metadata['chapters']=[{'paragraph':b.number,'title':b.chapter} for b in blocks if b.heading and b.narrative_role != 'front_matter']
        metadata['document_structure']=[{'paragraph':b.number,'role':b.narrative_role} for b in blocks if b.narrative_role != 'body']
        if args.config:
            warnings.append("Filtros aplicados antes da busca. Falas/pensamentos são separados pelas marcações configuradas; pensamentos implícitos e diálogos ambíguos podem ser classificados incorretamente. Estrutura e acentuação contextual são verificadas na narração; pontuação duplicada, espaçamento e quê final também em falas/pensamentos. LanguageTool mantém sua proteção própria de falas/itálicos.")
        metadata.update({"languagetool": args.languagetool, "languagetool_origem": origin,
                         "versao_fonte": __version__})
        parcial = metadata.get("languagetool_status") == "indisponivel"
        if parcial:
            # Pedido, mas não executado: o relatório não pode dizer que o corretor rodou.
            metadata.update(languagetool=False, languagetool_pedido=True, languagetool_origem=None)
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
        with (output / "relatorio.json").open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(data, ensure_ascii=False, indent=2))
        destinos = metadata.get("destinos", {})
        print(f"{destinos.get('pendencia', len(findings))} pendências ({metadata.get('impeditivos', 0)} impeditivas) e "
              f"{destinos.get('informacao', 0)} observações para avaliação humana. Isso não mede a qualidade nem "
              "certifica a publicação.")
        print(f"Relatório: {output / 'relatorio.json'}")
        print("Manuscrito preservado. Corretor gramatical geral: " + (
            "INDISPONÍVEL — análise parcial, sem ortografia geral nem boa parte da gramática" if parcial
            else f"LanguageTool local ({origin})" if args.languagetool else "não executado (opcional)"))
        return 0
    except KeyboardInterrupt:
        print("\nAnálise interrompida. Manuscrito preservado.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
