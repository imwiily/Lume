"""Classificação por marcações escolhidas; não infere voz ou pensamento implícito."""
from .settings import validate


def classify(blocks, settings):
    settings=validate(settings)
    result=[]
    closer=None
    for block in blocks:
        text=block.text
        roles=['narracao']*len(text)
        if block.heading:
            closer=None
            result.append(['titulo']*len(text))
            continue
        if settings['dialogue_dashes'] and text.lstrip().startswith(('—','–')):
            spoken=False
            for i,char in enumerate(text):
                if char in '—–':
                    spoken=not spoken
                    roles[i]='separador'
                elif spoken:
                    roles[i]='dialogo'
        if settings['quotes_role'] != 'narracao':
            stripped=text.lstrip()
            opener={'”':'“','»':'«','"':'"','’':'‘'}.get(closer)
            if closer and opener and stripped.startswith(opener) and closer in stripped[1:]:
                closer=None
            for i,char in enumerate(text):
                if closer:
                    roles[i]=settings['quotes_role']
                    if char==closer:
                        roles[i]='separador';closer=None
                elif char in {'“','«','"','‘'}:
                    closer={'“':'”','«':'»','"':'"','‘':'’'}[char]
                    roles[i]='separador'
        if settings['italic_thoughts']:
            for start,end in block.italic:
                roles[start:end]=['pensamento']*(end-start)
        result.append(roles)
    return result


def masks(blocks, roles, allowed):
    # Pontuação de encerramento nos limites impede unir frases de áreas separadas.
    return [''.join(c if role in allowed else ('\n' if c=='\n' else ' ')
                    for c,role in zip(block.text,labels))
            for block,labels in zip(blocks,roles)]


def spans(labels, allowed):
    start=0
    for i in range(1,len(labels)+1):
        if i==len(labels) or labels[i]!=labels[start]:
            if labels[start] in allowed:
                yield start,i,labels[start]
            start=i
