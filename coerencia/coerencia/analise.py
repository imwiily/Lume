"""Extração por cena, memória em arquivos, verificação dos trechos e juiz.

Fluxo: para cada cena, o modelo recebe o texto numerado e os fatos já conhecidos
que parecem relevantes; devolve fatos novos e possíveis conflitos. Todo trecho
citado precisa existir no parágrafo indicado, senão é descartado. Depois, pares
de fatos incompatíveis e conflitos sugeridos passam por um juiz que vê os dois
trechos e o contexto. A memória nunca depende do modelo lembrar do livro.
"""
import json
from pathlib import Path
import re
import unicodedata

ESQUEMA_CENA = {
    "type": "object",
    "properties": {
        "fatos": {"type": "array", "items": {"type": "object", "properties": {
            "entidade": {"type": "string"},
            "tipo": {"type": "string", "enum": ["personagem", "objeto", "lugar", "grupo", "ambiente"]},
            "aspecto": {"type": "string"},
            "valor": {"type": "string"},
            "paragrafo": {"type": "integer"},
            "trecho": {"type": "string"},
            "fonte": {"type": "string", "enum": ["narrador", "fala"]},
        }, "required": ["entidade", "tipo", "aspecto", "valor", "paragrafo", "trecho", "fonte"]}},
        "conflitos": {"type": "array", "items": {"type": "object", "properties": {
            "paragrafo": {"type": "integer"},
            "trecho": {"type": "string"},
            "paragrafo_anterior": {"type": "integer"},
            "trecho_anterior": {"type": "string"},
            "explicacao": {"type": "string"},
        }, "required": ["paragrafo", "trecho", "paragrafo_anterior", "trecho_anterior", "explicacao"]}},
    },
    "required": ["fatos", "conflitos"],
}

ESQUEMA_JUIZ = {
    "type": "object",
    "properties": {
        "contradicao": {"type": "boolean"},
        "confianca": {"type": "string", "enum": ["alta", "media", "baixa"]},
        "explicacao": {"type": "string"},
    },
    "required": ["contradicao", "confianca", "explicacao"],
}

SISTEMA_CENA = """Você é um revisor de continuidade de romances em português.
Leia a CENA e registre FATOS explícitos que um leitor atento guardaria para conferir depois:
características físicas (cor dos olhos, cabelo, altura), idade, nome, parentesco, profissão,
se alguém está vivo ou morto, objetos e seus atributos (cor, material, quantidade),
quem possui o quê, onde algo está, clima e horário do momento, há quanto tempo algo acontece.

Regras:
- Só registre o que o texto afirma. Não deduza, não invente.
- "trecho" deve ser cópia literal e curta (3 a 12 palavras) do parágrafo indicado em "paragrafo".
- "aspecto" é um rótulo curto e estável em minúsculas (ex.: "cor dos olhos", "idade", "vivo ou morto",
  "cor da capa", "quantidade de termômetros", "clima", "tempo de trabalho no lugar").
- Use para a mesma pessoa ou objeto o mesmo nome de "entidade" já usado nos FATOS CONHECIDOS.
- "fonte" é "fala" quando o fato está na fala de um personagem, e "narrador" nos demais casos.

Em "conflitos", registre apenas quando algo desta cena não pode ser verdade junto com um fato conhecido
ou com outra frase da própria cena (por exemplo: cor diferente sem explicação, pessoa morta agindo no
presente da história, idade incompatível, alguém sem um objeto que acabou de usar).
Não é conflito: mudança explicada pelo texto (trocou de roupa, o tempo passou, pintou), lembrança,
sonho, mentira evidente de personagem, ou estranheza que o próprio narrador aponta como mistério.
Para cada conflito, copie o trecho desta cena e o trecho anterior, com os números de parágrafo.
Em "explicacao", diga em uma ou duas frases curtas, com palavras do dia a dia, o que não combina
entre os dois trechos; sem termos técnicos e sem sugerir outra redação.
Se não houver nada, devolva listas vazias."""

SISTEMA_JUIZ = """Você é um revisor de continuidade de romances em português.
Receberá dois trechos de uma mesma história (A, anterior; B, posterior) e o contexto.
Diga se B contradiz A: os dois não podem ser verdade ao mesmo tempo na história, e o texto não
explica a mudança. Mudanças explicadas (tempo passou, troca, conserto, pintura), lembranças, sonhos,
hipóteses, mentira de personagem e mistérios apontados pelo próprio narrador NÃO são contradição.
Duas descrições compatíveis (ex.: "cinzentos" e "cinza") também não.
Em "explicacao", diga em uma ou duas frases curtas, com palavras do dia a dia, o que não combina
entre A e B (ou por que combina); sem termos técnicos e sem sugerir outra redação.
Responda em JSON. Na dúvida, contradicao=false ou confianca="baixa"."""


def normalizar(texto):
    texto = unicodedata.normalize("NFC", texto).replace(" ", " ")
    texto = re.sub(r"[“”«»\"]", '"', texto)
    texto = re.sub(r"[‘’]", "'", texto)
    texto = texto.replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", texto).strip().casefold()


def chave(texto):
    texto = normalizar(texto)
    texto = re.sub(r"^(o|a|os|as|um|uma|dona|seu|sr\.?|sra\.?)\s+", "", texto)
    return texto.strip(" .,:;!?")


def trecho_valido(paragrafos, numero, trecho):
    """O trecho existe literalmente (sem diferenças de espaço/aspas/caixa) no parágrafo?"""
    if not trecho or not isinstance(numero, int) or not 1 <= numero <= len(paragrafos):
        return False
    return normalizar(trecho) in normalizar(paragrafos[numero - 1].texto)


def relevantes(memoria, cena, limite=80):
    """Fatos cujas entidades aparecem na cena, mais o ambiente mais recente."""
    texto = normalizar(" ".join(p.texto for p in cena.paragrafos))
    escolhidos = []
    for fato in memoria:
        palavras = [w for w in chave(fato["entidade"]).split() if len(w) > 2]
        if fato["tipo"] == "ambiente" or any(re.search(r"\b" + re.escape(w) + r"\b", texto) for w in palavras):
            escolhidos.append(fato)
    return escolhidos[-limite:]


def formatar_fatos(fatos):
    if not fatos:
        return "(nenhum)"
    return "\n".join(f"{f['id']} | {f['entidade']} ({f['tipo']}) | {f['aspecto']}: {f['valor']} | §{f['paragrafo']} "
                     f"\"{f['trecho']}\" | {f['fonte']}" for f in fatos)


def contexto(paragrafos, a, b, limite=2500):
    """Os dois parágrafos e, se couber, os que estão entre eles."""
    a, b = sorted((a, b))
    meio = paragrafos[a:b - 1]
    partes = [paragrafos[a - 1]]
    if sum(len(p.texto) for p in meio) <= limite:
        partes += meio
    if b != a:
        partes.append(paragrafos[b - 1])
    return "\n".join(f"[§{p.numero}] {p.texto}" for p in partes)


CAMPOS_FATO = ("entidade", "tipo", "aspecto", "valor", "paragrafo", "trecho", "fonte")


def ler_cena(modelo, cena, conhecidos):
    """Uma chamada ao modelo: fatos e conflitos da cena, dados os fatos conhecidos."""
    pedido = (f"FATOS CONHECIDOS (cenas anteriores):\n{formatar_fatos(conhecidos)}\n\n"
              f"CENA {cena.numero} — {cena.capitulo}, parágrafos {cena.inicio} a {cena.fim}:\n"
              f"{cena.texto_numerado()}")
    return modelo.json(SISTEMA_CENA, pedido, ESQUEMA_CENA, f"cena {cena.numero}")


def verificar(paragrafos, cena, bruto):
    """Separa o que o modelo citou corretamente do que inventou. Devolve fatos
    (sem id), conflitos sugeridos e descartes."""
    dentro = {p.numero for p in cena.paragrafos}
    fatos, sugestoes, descartes = [], [], []
    for fato in bruto.get("fatos", []):
        if fato.get("paragrafo") in dentro and trecho_valido(paragrafos, fato.get("paragrafo"), fato.get("trecho")):
            fatos.append({k: fato[k] for k in CAMPOS_FATO})
        else:
            descartes.append({"cena": cena.numero, "motivo": "trecho inexistente", **fato})
    for conflito in bruto.get("conflitos", []):
        if (conflito.get("paragrafo") in dentro
                and trecho_valido(paragrafos, conflito.get("paragrafo"), conflito.get("trecho"))
                and trecho_valido(paragrafos, conflito.get("paragrafo_anterior"), conflito.get("trecho_anterior"))
                and conflito["paragrafo_anterior"] <= conflito["paragrafo"]):
            sugestoes.append({"origem": "extracao", "cena": cena.numero, **conflito})
        else:
            descartes.append({"cena": cena.numero, "motivo": "conflito com trecho inexistente", **conflito})
    return fatos, sugestoes, descartes


def pares_candidatos(memoria, sugestoes, novo=lambda fato: True):
    """Conflitos sugeridos e pares da memória com mesma entidade e aspecto e
    valores diferentes. `novo` restringe aos pares que envolvem algum fato novo."""
    pares, vistos = [], set()
    for sugestao in sugestoes:
        par = (sugestao["paragrafo_anterior"], sugestao["trecho_anterior"], sugestao["paragrafo"], sugestao["trecho"])
        if par not in vistos:
            vistos.add(par)
            pares.append({"origem": "extracao", "a": (par[0], par[1]), "b": (par[2], par[3]),
                          "entidade": "", "aspecto": "", "sugestao": sugestao["explicacao"]})
    grupos = {}
    for fato in memoria:
        grupos.setdefault((chave(fato["entidade"]), chave(fato["aspecto"])), []).append(fato)
    for fatos in grupos.values():
        fatos = sorted(fatos, key=lambda f: f["paragrafo"])
        for i, anterior in enumerate(fatos):
            for posterior in fatos[i + 1:]:
                if (chave(anterior["valor"]) == chave(posterior["valor"]) or anterior["paragrafo"] == posterior["paragrafo"]
                        or not (novo(anterior) or novo(posterior))):
                    continue
                par = (anterior["paragrafo"], anterior["trecho"], posterior["paragrafo"], posterior["trecho"])
                if par in vistos:
                    continue
                vistos.add(par)
                pares.append({"origem": "memoria", "a": par[:2], "b": par[2:],
                              "entidade": anterior["entidade"], "aspecto": anterior["aspecto"],
                              "sugestao": f"{anterior['aspecto']}: “{anterior['valor']}” e depois “{posterior['valor']}”"})
    return pares


def pedido_juiz(paragrafos, par):
    (pa, ta), (pb, tb) = par["a"], par["b"]
    return (f"A (§{pa}): \"{ta}\"\nB (§{pb}): \"{tb}\"\n"
            f"Observação da leitura: {par['sugestao']}\n\nCONTEXTO:\n{contexto(paragrafos, pa, pb)}")


def registro(par, veredito):
    (pa, ta), (pb, tb) = par["a"], par["b"]
    return {**par, "a": {"paragrafo": pa, "trecho": ta}, "b": {"paragrafo": pb, "trecho": tb}, **veredito}


def confirmada(julgamento):
    return julgamento["contradicao"] and julgamento["confianca"] != "baixa"


class Analise:
    """Análise completa de um texto, com retomada por cena (usada na avaliação)."""

    def __init__(self, paragrafos, cenas, modelo, pasta, registrar=print):
        self.paragrafos, self.cenas, self.modelo = paragrafos, cenas, modelo
        self.pasta = Path(pasta)
        (self.pasta / "cenas").mkdir(parents=True, exist_ok=True)
        self.registrar = registrar
        self.memoria, self.sugestoes, self.descartes = [], [], []

    def extrair(self):
        for cena in self.cenas:
            arquivo = self.pasta / "cenas" / f"{cena.numero:03d}.json"
            salvo = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else None
            if salvo and salvo.get("assinatura") == cena.assinatura() and salvo.get("modelo") == self.modelo.modelo:
                bruto = salvo["resposta"]
                self.registrar(f"  cena {cena.numero} (§{cena.inicio}–{cena.fim}): reaproveitada")
            else:
                bruto = ler_cena(self.modelo, cena, relevantes(self.memoria, cena))
                self.registrar(f"  cena {cena.numero} (§{cena.inicio}–{cena.fim}): {len(bruto.get('fatos', []))} fatos, "
                               f"{len(bruto.get('conflitos', []))} conflitos sugeridos")
            fatos, sugestoes, descartes = verificar(self.paragrafos, cena, bruto)
            for fato in fatos:
                fato.update(id=f"F{len(self.memoria) + 1:04d}", cena=cena.numero)
                self.memoria.append(fato)
            self.sugestoes += sugestoes
            self.descartes += descartes
            arquivo.write_text(json.dumps({"cena": cena.numero, "capitulo": cena.capitulo, "paragrafos": [cena.inicio, cena.fim],
                                           "assinatura": cena.assinatura(), "modelo": self.modelo.modelo,
                                           "resposta": bruto, "fatos_aceitos": [f["id"] for f in fatos]},
                                          ensure_ascii=False, indent=2), encoding="utf-8")
            (self.pasta / "memoria.json").write_text(json.dumps(self.memoria, ensure_ascii=False, indent=2), encoding="utf-8")

    def candidatos(self):
        return pares_candidatos(self.memoria, self.sugestoes)

    def julgar(self):
        pares = self.candidatos()
        self.registrar(f"  {len(pares)} pares para o juiz")
        resultado = [registro(par, self.modelo.json(SISTEMA_JUIZ, pedido_juiz(self.paragrafos, par), ESQUEMA_JUIZ, f"juiz {n}"))
                     for n, par in enumerate(pares, 1)]
        (self.pasta / "julgamentos.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
        contradicoes = agrupar([r for r in resultado if confirmada(r)])
        (self.pasta / "contradicoes.json").write_text(json.dumps(contradicoes, ensure_ascii=False, indent=2), encoding="utf-8")
        (self.pasta / "descartes.json").write_text(json.dumps(self.descartes, ensure_ascii=False, indent=2), encoding="utf-8")
        return contradicoes


def _sobrepoe(x, y):
    """Trechos do mesmo parágrafo que se sobrepõem (um contém o outro ou dividem a maior parte das palavras)."""
    if x["paragrafo"] != y["paragrafo"]:
        return False
    a, b = normalizar(x["trecho"]), normalizar(y["trecho"])
    if a in b or b in a:
        return True
    pa, pb = set(re.findall(r"\w+", a)), set(re.findall(r"\w+", b))
    return bool(pa and pb) and len(pa & pb) / min(len(pa), len(pb)) >= .6


def mesma_contradicao(x, y):
    """Mesmo ponto do texto: trechos sobrepostos, ou o mesmo par de parágrafos distintos."""
    par_x = {x["a"]["paragrafo"], x["b"]["paragrafo"]}
    if len(par_x) == 2 and par_x == {y["a"]["paragrafo"], y["b"]["paragrafo"]}:
        return True
    return any(_sobrepoe(x[i], y[j]) for i in ("a", "b") for j in ("a", "b"))


def agrupar(contradicoes):
    """Une alertas sobre o mesmo ponto do texto. Fica o de maior confiança (e,
    no empate, o primeiro); os demais seguem em `relacionadas`."""
    ordem = {"alta": 0, "media": 1, "baixa": 2}
    grupos = []
    for c in contradicoes:
        grupo = next((g for g in grupos if any(mesma_contradicao(c, m) for m in g)), None)
        if grupo is None:
            grupos.append([c])
        else:
            grupo.append(c)
    resultado = []
    for grupo in grupos:
        principal = min(grupo, key=lambda c: ordem.get(c.get("confianca"), 3))
        outras = [{"a": c["a"], "b": c["b"], "explicacao": c["explicacao"]} for c in grupo if c is not principal]
        resultado.append({**principal, "relacionadas": outras} if outras else principal)
    return resultado
