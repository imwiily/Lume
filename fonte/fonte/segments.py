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
        # Hífen seguido de espaço abre fala como o travessão (“- Vamos.”); no meio da linha, só o
        # hífen isolado por espaços separa, nunca o de palavra composta (“bem-vindo”). Cada linha
        # do parágrafo (quebra de linha manual) vale como início possível de fala; a fala que fica
        # aberta continua na linha seguinte só se ela a fechar (“… — disse ela.”).
        base,spoken,hyphen=0,False,False
        def separator(line,j):
            return line[j] in '—–' or (hyphen and line[j]=='-' and (j==0 or line[j-1].isspace())
                                        and (j+1==len(line) or line[j+1].isspace()))
        for line in text.split('\n') if settings['dialogue_dashes'] else ():
            if line.strip():
                if line.lstrip().startswith(('—','–','- ')):
                    spoken,hyphen=False,line.lstrip().startswith('- ')
                elif not any(separator(line,j) for j in range(len(line))):
                    spoken=False
                for j,char in enumerate(line):
                    if separator(line,j) and (spoken or line.lstrip().startswith(('—','–','- '))):
                        spoken=not spoken
                        roles[base+j]='separador'
                    elif spoken:
                        roles[base+j]='dialogo'
            base+=len(line)+1
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
