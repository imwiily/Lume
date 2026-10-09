import re
from difflib import SequenceMatcher
from ..analysis import explicar
from .common import WORDS, alert, evidence, normalized
from ..settings import validate
from ..segments import classify, spans
from ..lexicon import FINITE, flags

STOP = set("a o as os um uma uns umas de da do das dos em no na nos nas por para pra com sem e ou mas que se eu tu ele ela eles elas nós vós você vocês me te lhe lhes meu minha seus suas seu sua isso isto esse essa este esta ao aos à às não sim já só mais muito como quando porque então era foi tinha havia estava ser estar ter faz fez fazer disse dizer é está são eram foram pelo pela pelos pelas comigo contigo consigo assim aqui ali tudo nada pouco cada qual onde este esta aquele aquela isto aquilo estou estamos obrigado obrigada".split())
SENTENCE = re.compile(r"[^.!?…\n]+[.!?…]*")


# Pronomes átonos que, depois do hífen (ênclise), têm a mesma forma do artigo ou da preposição seguinte.
ENCLITICOS_HOMOGRAFOS = {"a", "o", "as", "os"}
# O que pode vir entre o pronome “se” e o verbo dele (“se se lhes não conta”).
ANTES_DO_VERBO = {"me", "te", "lhe", "lhes", "nos", "vos", "o", "a", "os", "as", "não", "nunca", "já"}


def dobra_legitima(text, first, second, following):
    """A mesma forma duas vezes, mas com funções diferentes, sem erro de digitação:
    - pronome enclítico seguido de artigo ou preposição homógrafos (“Alcancei-a a poucos passos”);
    - conjunção “se” seguida do pronome “se”, que pede um verbo logo depois (“se se sabe”, “se se lhes
      não conta”); sem verbo (“se se ele vier”), é dobra;
    - letra isolada abreviada (“P. e E.”)."""
    key = first[0].casefold()
    if key in ENCLITICOS_HOMOGRAFOS and first.start() > 0 and text[first.start() - 1] == "-":
        return True
    if key == "se":
        for word in following[:4]:
            if flags(word[0]) & FINITE:
                return True
            if word[0].casefold() not in ANTES_DO_VERBO:
                return False
        return False
    return len(key) == 1 and (text[second.end():second.end() + 1] == "." or text[first.end():first.end() + 1] == ".")


def analyze(blocks, settings=None):
    options=validate(settings or {})
    classified=classify(blocks, options)
    out, recent = [], []
    for block,labels in zip(blocks,classified):
        if block.heading:
            recent=[]
            continue
        if not options['duplicate_across_paragraphs']:
            recent=[]
        for lower,upper,scope in spans(labels, options['repetition_scopes']):
            # Cada fala/inciso é independente: palavras não atravessam esse limite.
            for sentence in SENTENCE.finditer(block.text,lower,upper):
                key=normalized(sentence[0]);words=key.split()
                if len(words)>=6 and options['rules']['frase_duplicada']:
                    previous=None
                    for item in reversed(recent):
                        old_key,old,start,end,old_scope=item
                        if old_scope != scope:
                            continue
                        ratio=1.0 if old_key==key else (SequenceMatcher(None,old_key.split(),words,autojunk=False).ratio() if options['duplicate_similarity']<1 else 0)
                        if ratio>=options['duplicate_similarity']:
                            previous=(old,start,end,ratio);break
                    if previous:
                        old,start,end,ratio=previous
                        rule='frase_duplicada'
                        reason=('Esta frase é igual a uma frase próxima.' if ratio==1 else 'Esta frase é muito parecida com uma frase próxima.')
                        out.append(alert(block,rule,'Possível repetição de frase',sentence.start(),sentence.end(),
                            explicar(reason+' Confira se é de propósito (refrão, retomada) ou se ficou duplicada numa edição.',
                                     'frase repetida'),
                            'alta' if ratio==1 else 'baixa',[evidence(old,start,end)]))
                    recent.append((key,block,sentence.start(),sentence.end(),scope));recent=recent[-8:]
            if not options['rules']['palavra_consecutiva']:
                continue
            units=[(lower,upper)] if options['repetition_boundary']=='trecho' else [(s.start(),s.end()) for s in SENTENCE.finditer(block.text,lower,upper)]
            for start,end in units:
                tokens=list(WORDS.finditer(block.text,start,end));seen={}
                for i,token in enumerate(tokens):
                    key=token[0].casefold();previous=seen.get(key)
                    if previous is not None:
                        first=tokens[previous]
                        # A repetição próxima (estilo) foi retirada na Fase 7b; só a dobra conta.
                        if (i-previous==1 and block.text[first.end():token.start()].isspace() and flags(key)
                                and not dobra_legitima(block.text, first, token, tokens[i + 1:])):
                            out.append(alert(block,'palavra_consecutiva','Palavra repetida',first.start(),token.end(),
                                explicar('A mesma palavra aparece duas vezes seguidas. Confira se é de propósito ou digitação.',
                                         'palavra repetida'),'média'))
                    seen[key]=i
    return out
