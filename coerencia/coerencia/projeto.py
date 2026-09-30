"""Projeto incremental: só capítulos alterados vão ao modelo.

Cada livro tem uma pasta de projeto com o estado de cada capítulo (hash do texto
e fatos extraídos), um cache de julgamentos e as pendências com a decisão do
autor. Numa nova rodada:

- capítulo com o mesmo texto não é reenviado; seus fatos continuam na memória
  para comparação com o que mudou (contradições cruzam capítulos);
- capítulo alterado ou novo é relido cena por cena;
- só pares que envolvem fatos novos vão ao juiz, e um par já julgado com o
  mesmo contexto sai do cache;
- pendência cujo trecho sumiu com a edição é encerrada; a marcada como
  intencional não volta.

Fatos guardam a posição relativa ao capítulo, para que editar um capítulo não
desalinhe os outros.
"""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

from .analise import (SISTEMA_JUIZ, ESQUEMA_JUIZ, confirmada, ler_cena, mesma_contradicao, normalizar, pares_candidatos,
                      pedido_juiz, registro, relevantes, verificar)
from .leitura import cenas
from .modelo import ErroModelo

ESTADOS = ("aberta", "corrigida", "intencional", "resolvida_por_edicao")
# Custo = parte proporcional ao texto + parte fixa por cena (instruções e raciocínio
# de cada chamada). Calibrado com Sonnet 5.5 em duas medições reais: Hikari
# (79.984 caracteres, 29 cenas, US$ 0,77) e um texto de 2 cenas (US$ 0,013).
CUSTO_POR_CARACTERE = 7.45e-6
CUSTO_POR_CENA = 0.006
FATOR_MODELO = {"claude-sonnet-5-5": 1.0, "claude-opus-5-5": 2.0, "claude-haiku-4-5": 0.5}


class Capitulo:
    def __init__(self, id, titulo, ordem, paragrafos):
        self.id, self.titulo, self.ordem, self.paragrafos = id, titulo, ordem, paragrafos
        self.hash = hashlib.sha256("\n".join(p.texto for p in paragrafos).encode("utf-8")).hexdigest()

    @property
    def inicio(self):
        return self.paragrafos[0].numero

    def localizar(self, trecho):
        """Posição relativa do parágrafo que contém o trecho, ou None."""
        alvo = normalizar(trecho)
        return next((i for i, p in enumerate(self.paragrafos) if alvo in normalizar(p.texto)), None)


def slug(texto):
    texto = normalizar(texto)
    return re.sub(r"[^\w]+", "-", texto).strip("-")[:60] or "sem-titulo"


def capitulos(paragrafos):
    """Agrupa os parágrafos de texto por título; o id usa título e ocorrência."""
    grupos, vistos, atual = [], {}, None
    for p in paragrafos:
        if p.titulo:
            atual = None
            continue
        if atual is None or atual[0] != p.capitulo:
            atual = (p.capitulo, [])
            grupos.append(atual)
        atual[1].append(p)
    resultado = []
    for ordem, (titulo, itens) in enumerate(grupos, 1):
        base = slug(titulo)
        vistos[base] = vistos.get(base, 0) + 1
        ident = base if vistos[base] == 1 else f"{base}-{vistos[base]}"
        resultado.append(Capitulo(ident, titulo, ordem, itens))
    return resultado


class Projeto:
    def __init__(self, pasta):
        self.pasta = Path(pasta)
        self.pasta.mkdir(parents=True, exist_ok=True)
        (self.pasta / "cenas").mkdir(exist_ok=True)
        self.estado = self._ler("projeto.json", {"versao": 1, "capitulos": {}})
        self.cache = self._ler("julgamentos.json", {})
        self.pendencias = self._ler("pendencias.json", [])
        self.rodadas = self._ler("rodadas.json", [])

    def _ler(self, nome, padrao):
        arquivo = self.pasta / nome
        return json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else padrao

    def _gravar(self, nome, valor):
        temporario = self.pasta / (nome + ".tmp")
        temporario.write_text(json.dumps(valor, ensure_ascii=False, indent=2), encoding="utf-8")
        temporario.replace(self.pasta / nome)

    def salvar(self):
        for nome, valor in (("projeto.json", self.estado), ("julgamentos.json", self.cache),
                            ("pendencias.json", self.pendencias), ("rodadas.json", self.rodadas)):
            self._gravar(nome, valor)

    # ---- rodada ------------------------------------------------------------------------------
    def atualizar(self, documento, paragrafos, modelo, maximo=3500, registrar=print, reler=False, avancar=None):
        """Uma rodada. Se o teto de gasto for atingido, o que já foi lido fica salvo:
        capítulos não lidos seguem na próxima rodada, e fatos cujos pares ainda não
        foram julgados ficam marcados para reavaliação (sem nova leitura)."""
        caps = capitulos(paragrafos)
        guardados = self.estado["capitulos"]
        alterados = [c for c in caps if reler or guardados.get(c.id, {}).get("hash") != c.hash
                     or guardados.get(c.id, {}).get("modelo") != modelo.modelo]
        ids_alterados = {c.id for c in alterados}
        tokens_antes = _tokens(modelo.chamadas)
        chamadas_antes = len(modelo.chamadas)
        por_id = {c.id: c for c in caps}
        por_paragrafo = {p.numero: c for c in caps for p in c.paragrafos}

        # Memória: fatos dos capítulos inalterados, com a posição de hoje. Os
        # marcados para reavaliação voltam a formar pares como fatos novos.
        memoria, sugestoes = [], []
        for cap in caps:
            if cap.id in ids_alterados:
                continue
            reavaliar = guardados[cap.id].get("reavaliar", False)
            for fato in guardados[cap.id]["fatos"]:
                memoria.append({**fato, "paragrafo": cap.inicio + fato["rel"], "capitulo": cap.id, "novo": reavaliar})
            if reavaliar:
                sugestoes += self._sugestoes_de(guardados[cap.id].get("sugestoes", []), por_id)
        poupados = sum(guardados[c.id].get("tokens", 0) for c in caps if c.id not in ids_alterados)

        registrar(f"{len(caps)} capítulos: {len(alterados)} a enviar, {len(caps) - len(alterados)} sem alteração (não enviados).")
        parada = None
        enviados = 0
        # Andamento para a interface: cenas lidas de todos os capítulos a enviar.
        total_cenas, lidas = sum(len(cenas(c.paragrafos, maximo)) for c in alterados), 0
        for cap in alterados:
            antes = _tokens(modelo.chamadas)
            fatos_cap, sugestoes_cap = [], []
            try:
                for cena in cenas(cap.paragrafos, maximo):
                    cena.capitulo = cap.titulo
                    bruto = ler_cena(modelo, cena, relevantes(memoria + fatos_cap, cena))
                    fatos, sug, descartes = verificar(paragrafos, cena, bruto)
                    for fato in fatos:
                        fato.update(id=f"{cap.ordem}.{len(fatos_cap) + 1}", capitulo=cap.id,
                                    rel=fato["paragrafo"] - cap.inicio, novo=True)
                        fatos_cap.append(fato)
                    sugestoes_cap += sug
                    lidas += 1
                    if avancar:
                        avancar(lidas, total_cenas)
                    (self.pasta / "cenas" / f"{cap.id}-{cena.numero:02d}.json").write_text(json.dumps(
                        {"capitulo": cap.titulo, "cena": cena.numero, "resposta": bruto, "descartes": descartes},
                        ensure_ascii=False, indent=2), encoding="utf-8")
            except ErroModelo as erro:
                if "Teto" not in str(erro):
                    raise
                parada = str(erro)
                registrar(f"  {cap.titulo}: interrompido pelo teto; será lido na próxima rodada.")
                break
            memoria += fatos_cap
            sugestoes += sugestoes_cap
            enviados += 1
            gasto = _tokens(modelo.chamadas) - antes
            guardados[cap.id] = {"titulo": cap.titulo, "ordem": cap.ordem, "hash": cap.hash, "modelo": modelo.modelo,
                                 "tokens": gasto, "lido_em": _agora(), "reavaliar": True,
                                 "sugestoes": self._guardar_sugestoes(sugestoes_cap, por_paragrafo),
                                 "fatos": [{k: v for k, v in f.items() if k not in ("paragrafo", "novo", "capitulo")}
                                           for f in fatos_cap]}
            self.salvar()  # capítulo pago não se perde se algo falhar depois
            registrar(f"  {cap.titulo}: {len(fatos_cap)} fatos, {gasto} tokens")
        for antigo in set(guardados) - {c.id for c in caps}:
            del guardados[antigo]
        self.estado["documento"] = documento

        self._reconciliar(caps, {c.id for c in alterados[:enviados]})

        # Juiz: só pares com algum fato novo; o que já foi julgado sai do cache.
        pares = pares_candidatos(memoria, sugestoes, novo=lambda f: f["novo"])
        de_cache = julgados = 0
        for n, par in enumerate(pares, 1):
            pedido = pedido_juiz(paragrafos, par)
            chave_cache = hashlib.sha256((modelo.modelo + "\n" + pedido).encode("utf-8")).hexdigest()
            if chave_cache in self.cache:
                veredito, de_cache = self.cache[chave_cache]["veredito"], de_cache + 1
                poupados += self.cache[chave_cache].get("tokens", 0)
            elif parada:
                continue
            else:
                antes = _tokens(modelo.chamadas)
                try:
                    veredito = modelo.json(SISTEMA_JUIZ, pedido, ESQUEMA_JUIZ, f"juiz {n}")
                except ErroModelo as erro:
                    if "Teto" not in str(erro):
                        raise
                    parada = str(erro)
                    continue
                self.cache[chave_cache] = {"veredito": veredito, "tokens": _tokens(modelo.chamadas) - antes}
            julgados += 1
            julgamento = registro(par, veredito)
            if confirmada(julgamento):
                self._registrar_pendencia(julgamento, por_paragrafo)
        registrar(f"  {julgados}/{len(pares)} pares avaliados ({de_cache} do cache).")
        if not parada:
            for cap in caps:
                guardados.get(cap.id, {}).pop("reavaliar", None)

        self._atualizar_estados(caps)
        gasto = _tokens(modelo.chamadas) - tokens_antes
        custo = round(sum(c.get("custo_usd", 0) for c in modelo.chamadas[chamadas_antes:]), 6)
        rodada = {"data": _agora(), "modelo": modelo.modelo, "capitulos": len(caps), "enviados": enviados,
                  "a_enviar": len(alterados), "tokens_gastos": gasto, "custo_usd": custo,
                  "tokens_poupados_estimados": poupados, "pares": len(pares), "pares_julgados": julgados,
                  "pares_do_cache": de_cache, "pendencias_abertas": sum(p["status"] == "aberta" for p in self.pendencias),
                  "interrompida": parada}
        self.rodadas.append(rodada)
        self.salvar()
        return rodada

    @staticmethod
    def _guardar_sugestoes(sugestoes, por_paragrafo):
        """Conflitos sugeridos com posição relativa ao capítulo, para retomar o julgamento."""
        guardadas = []
        for s in sugestoes:
            ca, cb = por_paragrafo.get(s["paragrafo_anterior"]), por_paragrafo.get(s["paragrafo"])
            if ca and cb:
                guardadas.append({"a": [ca.id, s["paragrafo_anterior"] - ca.inicio, s["trecho_anterior"]],
                                  "b": [cb.id, s["paragrafo"] - cb.inicio, s["trecho"]], "explicacao": s["explicacao"]})
        return guardadas

    @staticmethod
    def _sugestoes_de(guardadas, por_id):
        resultado = []
        for s in guardadas:
            ca, cb = por_id.get(s["a"][0]), por_id.get(s["b"][0])
            if ca and cb and 0 <= s["a"][1] < len(ca.paragrafos) and 0 <= s["b"][1] < len(cb.paragrafos):
                resultado.append({"origem": "extracao", "paragrafo_anterior": ca.inicio + s["a"][1], "trecho_anterior": s["a"][2],
                                  "paragrafo": cb.inicio + s["b"][1], "trecho": s["b"][2], "explicacao": s["explicacao"]})
        return resultado

    def _reconciliar(self, caps, alterados):
        """Pendências que tocam capítulos alterados ou removidos: se o trecho sumiu, encerra."""
        por_id = {c.id: c for c in caps}
        for pendencia in self.pendencias:
            if pendencia["status"] != "aberta":
                continue
            for lado in ("a", "b"):
                cap = por_id.get(pendencia[lado]["capitulo"])
                if cap is None:
                    pendencia.update(status="resolvida_por_edicao", atualizada=_agora())
                    break
                if cap.id in alterados:
                    rel = cap.localizar(pendencia[lado]["trecho"])
                    if rel is None:
                        pendencia.update(status="resolvida_por_edicao", atualizada=_agora())
                        break
                    pendencia[lado]["rel"] = rel

    def _registrar_pendencia(self, julgamento, por_paragrafo):
        lados = {}
        for lado in ("a", "b"):
            cap = por_paragrafo[julgamento[lado]["paragrafo"]]
            lados[lado] = {"capitulo": cap.id, "titulo": cap.titulo,
                           "rel": julgamento[lado]["paragrafo"] - cap.inicio, "trecho": julgamento[lado]["trecho"]}
        chave_par = [lados["a"]["capitulo"], normalizar(lados["a"]["trecho"]),
                     lados["b"]["capitulo"], normalizar(lados["b"]["trecho"])]
        existente = next((p for p in self.pendencias if p["chave"] == chave_par), None)
        if existente:
            if existente["status"] in ("corrigida", "resolvida_por_edicao"):
                existente.update(status="aberta", atualizada=_agora(), nota="reapareceu depois de marcada como corrigida")
            return
        # Mesmo ponto do texto de uma pendência já registrada: vira relacionada, sem número novo.
        novo = {lado: {"paragrafo": (lados[lado]["capitulo"], lados[lado]["rel"]), "trecho": lados[lado]["trecho"]}
                for lado in ("a", "b")}
        for pendencia in self.pendencias:
            if pendencia["status"] == "resolvida_por_edicao":
                continue
            atual = {lado: {"paragrafo": (pendencia[lado]["capitulo"], pendencia[lado]["rel"]),
                            "trecho": pendencia[lado]["trecho"]} for lado in ("a", "b")}
            if mesma_contradicao(novo, atual):
                relacionadas = pendencia.setdefault("relacionadas", [])
                if all(r["chave"] != chave_par for r in relacionadas):
                    relacionadas.append({"chave": chave_par, **lados, "explicacao": julgamento["explicacao"]})
                return
        self.pendencias.append({"id": f"C{len(self.pendencias) + 1:03d}", "chave": chave_par, **lados,
                                "explicacao": julgamento["explicacao"], "confianca": julgamento["confianca"],
                                "status": "aberta", "criada": _agora()})

    def _atualizar_estados(self, caps):
        abertas = {lado["capitulo"] for p in self.pendencias if p["status"] == "aberta" for lado in (p["a"], p["b"])}
        for cap in caps:
            if cap.id in self.estado["capitulos"]:  # capítulo ainda não lido (teto) fica sem situação
                self.estado["capitulos"][cap.id]["situacao"] = "com_pendencias" if cap.id in abertas else "sem_pendencias"

    def estimar(self, paragrafos, modelo, reler=False):
        """Quanto a próxima rodada enviaria, sem chamar a API. A calibração vem de
        medições reais e o custo varia com o texto; por isso devolve também uma faixa."""
        caps = capitulos(paragrafos)
        guardados = self.estado["capitulos"]
        enviar = [c for c in caps if reler or guardados.get(c.id, {}).get("hash") != c.hash
                  or guardados.get(c.id, {}).get("modelo") != modelo]
        caracteres = sum(len(p.texto) for c in enviar for p in c.paragrafos)
        quantas_cenas = sum(len(cenas(c.paragrafos)) for c in enviar)
        estimado = (caracteres * CUSTO_POR_CARACTERE + quantas_cenas * CUSTO_POR_CENA) * FATOR_MODELO.get(modelo, 1.0)
        return {"modelo": modelo, "capitulos": len(caps), "a_enviar": len(enviar),
                "titulos_a_enviar": [c.titulo for c in enviar], "caracteres": caracteres, "cenas": quantas_cenas,
                "custo_estimado_usd": round(estimado, 4), "custo_minimo_usd": round(estimado * .5, 4),
                "custo_maximo_usd": round(estimado * 1.6, 4),
                "reavaliacao_pendente": any(g.get("reavaliar") for g in guardados.values())}

    # ---- consulta e decisões -------------------------------------------------------------------
    def decidir(self, ident, status):
        if status not in ESTADOS:
            raise ValueError("Situação inválida. Use: " + ", ".join(ESTADOS))
        pendencia = next((p for p in self.pendencias if p["id"].casefold() == ident.casefold()), None)
        if pendencia is None:
            raise ValueError(f"Pendência {ident} não encontrada.")
        pendencia.update(status=status, atualizada=_agora())
        abertas = {lado["capitulo"] for p in self.pendencias if p["status"] == "aberta" for lado in (p["a"], p["b"])}
        for ident_cap, cap in self.estado["capitulos"].items():
            cap["situacao"] = "com_pendencias" if ident_cap in abertas else "sem_pendencias"
        self.salvar()
        return pendencia


def _tokens(chamadas):
    return sum((c.get("tokens_entrada") or 0) + (c.get("tokens_saida") or 0) for c in chamadas)


def _agora():
    return datetime.now().isoformat(timespec="seconds")
