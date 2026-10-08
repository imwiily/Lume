"""Verbos de fala, pensamento e percepção (núcleo compartilhado; estabilização, Fase 5).

Uma só fonte de dados: `CATEGORIAS` diz o que cada verbo é; os perfis dizem quais verbos cada
uso reconhece. Os perfis não são equivalentes e não se unem: cada um reproduz a lista que a regra
sempre usou, com as diferenças que tinha (registradas no plano).

Categorias (do verbo, não do uso):
- `elocucao`: dizer algo a alguém (“disse”, “perguntou”, “prometeu”);
- `pensamento`: pensar, crer, saber, lembrar, querer (“pensou”, “achava”);
- `percepcao`: perceber pelos sentidos ou pela atenção (“sentiu”, “ouviu”, “notou”);
- `contexto`: só é fala pelo contexto do inciso ou da frase (“continuou ela”, “vou mostrar”).
Admitir oração com “que” não é categoria: é o perfil `PEDEM_QUE`.

Perfis:
- `INCISO`: verbo que, depois da fala ou das aspas, abre o inciso do narrador (“— Vamos — disse
  ela”). Usado na pontuação de diálogo, no diálogo contextual, no pronome reto (“perguntou ela”
  tem sujeito, não objeto), na vírgula sujeito-verbo e na crase do LanguageTool;
- `PEDEM_QUE`: além dos do inciso, verbos que continuam com “que” depois de reticências;
- `RELATO`: verbos que introduzem conteúdo relatado ou sabido (tempo verbal: verdade geral e
  discurso indireto);
- `COMENTARIO_DO_NARRADOR`: primeira pessoa do presente com “que” (“acho que”);
- `NARRADOR_ANUNCIA`: “vou contar”, “vou explicar”;
- `ATESTA`: “posso garantir”, “pode confirmar”.

O reconhecimento pela forma (radical + terminação) cobre o lema que o modelo pequeno erra
(“perguntei” → “perguntei”). Usa as mesmas terminações da recuperação de lema do tempo verbal.
"""
import re

ELOCUCAO, PENSAMENTO, PERCEPCAO, CONTEXTO = "elocucao", "pensamento", "percepcao", "contexto"

CATEGORIAS = {
    **dict.fromkeys(
        "dizer informar perguntar responder murmurar gritar sussurrar comentar retrucar afirmar falar exclamar replicar "
        "declarar indagar confessar explicar acrescentar argumentar insistir ordenar pedir protestar avisar admitir "
        "concluir balbuciar resmungar cochichar implorar vociferar anunciar sugerir repetir garantir negar confirmar "
        "questionar reclamar ironizar saudar recitar citar ditar declamar prometer jurar contar narrar relatar descrever "
        "resumir atestar ensinar reconhecer".split(), ELOCUCAO),
    **dict.fromkeys(
        "pensar refletir ponderar lembrar esquecer achar saber acreditar crer imaginar supor esperar temer decidir "
        "querer entender aprender descobrir".split(), PENSAMENTO),
    **dict.fromkeys("sentir perceber ouvir notar observar".split(), PERCEPCAO),
    **dict.fromkeys(
        "continuar completar interromper terminar brincar chamar ler cantar começar mostrar apresentar".split(), CONTEXTO),
}

INCISO = frozenset(
    "dizer informar perguntar responder murmurar gritar sussurrar comentar retrucar afirmar falar exclamar replicar "
    "declarar indagar confessar explicar acrescentar argumentar insistir ordenar pedir protestar avisar pensar refletir "
    "ponderar admitir lembrar concluir continuar completar interromper balbuciar resmungar cochichar implorar vociferar "
    "anunciar observar sugerir repetir garantir negar confirmar questionar reclamar ironizar brincar saudar chamar ler "
    "recitar citar ditar cantar declamar terminar".split())
# Formas que o radical não alcança.
INCISO_IRREGULARES = {"dizer": ("disse", "disseram", "diz", "dizem", "dizia", "diziam", "dirá"),
                      "pedir": ("pediu", "pediram", "pede", "pedia")}
# Além dos do inciso (“prometi… que voltaria”).
PEDEM_QUE = ("prometer", "jurar", "avisar", "contar", "achar", "saber", "acreditar", "garantir", "sentir",
             "perceber", "imaginar", "esperar", "temer", "lembrar", "esquecer", "decidir", "admitir")
RELATO = frozenset({"dizer", "explicar", "contar", "afirmar", "saber", "aprender", "ensinar", "descobrir", "lembrar",
                    "perceber", "entender", "ler", "ouvir", "achar", "pensar", "acreditar", "notar", "garantir"})
# Lema → primeira pessoa do singular do presente, a forma que a regra procura antes de “que”.
COMENTARIO_DO_NARRADOR = {"achar": "acho", "sentir": "sinto", "saber": "sei", "crer": "creio", "acreditar": "acredito",
                          "confessar": "confesso", "admitir": "admito", "imaginar": "imagino", "esperar": "espero",
                          "lembrar": "lembro", "garantir": "garanto", "jurar": "juro", "supor": "suponho",
                          "querer": "quero", "pensar": "penso", "reconhecer": "reconheço"}
NARRADOR_ANUNCIA = ("contar", "narrar", "relatar", "explicar", "falar", "dizer", "começar", "descrever", "mostrar",
                    "resumir", "apresentar")
ATESTA = frozenset({"confirmar", "afirmar", "garantir", "dizer", "atestar"})

# Terminações verbais comuns; com o radical de um verbo, reconhecem a forma mesmo quando o
# modelo pequeno erra o lema (“perguntei” → “perguntei”, “respondemos” → “respond”).
TERMINACOES = re.compile(r"(?:o|a|as|amos|ais|am|ei|aste|ou|astes|aram|ava|avas|ávamos|avam|e|es|emos|em|i|este|eu|"
                         r"estes|eram|ia|ias|íamos|iam|iu|imos|iram|ará|arão|erá|erão|irá|irão|ando|endo|indo)(?:-\w+)?")

_IRREGULARES = frozenset(f for formas in INCISO_IRREGULARES.values() for f in formas)


def pelo_radical(forma, verbos):
    """A forma é de algum dos verbos, pelo radical (três letras ou mais) + terminação verbal."""
    forma = forma.casefold()
    for verbo in verbos:
        radical = verbo[:-2]
        if len(radical) >= 3 and forma.startswith(radical) and TERMINACOES.fullmatch(forma[len(radical):]):
            return True
    return False


def forma_de_fala(forma):
    """Verbo do inciso só pela forma escrita (sem análise sintática)."""
    return forma.casefold() in _IRREGULARES or pelo_radical(forma, INCISO)


def verbo_de_fala(token):
    """Verbo do inciso, pelo lema do modelo ou pela forma escrita."""
    return token.lemma_.casefold() in INCISO or forma_de_fala(token.lower_)


def pede_completiva(forma):
    """Verbo que continua com “que” (os do inciso e os de `PEDEM_QUE`), pela forma escrita."""
    return forma_de_fala(forma) or pelo_radical(forma, PEDEM_QUE)
