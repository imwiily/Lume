import re
from difflib import SequenceMatcher
from .common import WORDS, alert, evidence, normalized
from ..settings import validate
from ..segments import classify, spans

STOP = set("a o as os um uma uns umas de da do das dos em no na nos nas por para pra com sem e ou mas que se eu tu ele ela eles elas nós vós você vocês me te lhe lhes meu minha seus suas seu sua isso isto esse essa este esta ao aos à às não sim já só mais muito como quando porque então era foi tinha havia estava ser estar ter faz fez fazer disse dizer é está são eram foram pelo pela pelos pelas comigo contigo consigo assim aqui ali tudo nada pouco cada qual onde este esta aquele aquela isto aquilo estou estamos obrigado obrigada".split())
SENTENCE = re.compile(r"[^.!?…\n]+[.!?…]*")


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
                        reason=('Esta frase repete uma frase próxima.' if ratio==1 else 'Esta frase tem palavras em sequência semelhantes às de uma frase próxima.')
                        out.append(alert(block,rule,'Possível repetição de frase',sentence.start(),sentence.end(),
                            reason+' Confira se é refrão, retomada deliberada ou duplicação de edição.',
                            'alta' if ratio==1 else 'baixa',[evidence(old,start,end)]))
                    recent.append((key,block,sentence.start(),sentence.end(),scope));recent=recent[-8:]
            if not options['rules']['palavra_proxima'] and not options['rules']['palavra_consecutiva']:
                continue
            units=[(lower,upper)] if options['repetition_boundary']=='trecho' else [(s.start(),s.end()) for s in SENTENCE.finditer(block.text,lower,upper)]
            for start,end in units:
                tokens=list(WORDS.finditer(block.text,start,end));seen={};emitted=set()
                for i,token in enumerate(tokens):
                    key=token[0].casefold();previous=seen.get(key)
                    if previous is not None:
                        first=tokens[previous];distance=i-previous
                        if (distance==1 and options['rules']['palavra_consecutiva']
                                and block.text[first.end():token.start()].isspace()):
                            out.append(alert(block,'palavra_consecutiva','Palavra repetida',first.start(),token.end(),
                                'Palavra repetida consecutivamente na área selecionada. Confira se é expressão deliberada ou digitação.','média'))
                        elif (options['rules']['palavra_proxima'] and key not in STOP and len(key)>=4
                              and not token[0][0].isupper() and 1<distance<=options['word_distance'] and key not in emitted):
                            between=block.text[first.end():token.start()].strip().casefold()
                            if between not in {'a','por'}:
                                out.append(alert(block,'palavra_proxima','Possível repetição próxima',first.start(),token.end(),
                                    f'“{token[0]}” aparece duas vezes em uma janela curta. A repetição pode ser necessária ou expressiva; confira se há redundância.','baixa'))
                                emitted.add(key)
                    seen[key]=i
    return out
