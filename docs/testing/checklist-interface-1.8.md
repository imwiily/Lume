# Checklist manual da interface — Lume 1.8 (candidato local)

Objetivo: o proprietário exercitar pessoalmente, na interface, os fluxos essenciais antes do
lançamento. **Nada aqui foi executado pela automação**: um item só vale como aprovado depois de
você marcá-lo e anotar a evidência.

## Antes de começar — proteja seus dados

1. **Use uma conta macOS separada** (Ajustes do Sistema → Usuários e Grupos → Adicionar conta,
   tipo Padrão). O Lume grava em `~/Library/Application Support/FONTE/` da conta que o abre e ainda
   não tem modo de teste isolado; numa conta nova esse caminho começa vazio e não toca a sua.
2. Copie o app e os documentos de teste para um lugar legível por todas as contas, a partir da
   sua conta principal:
   ```
   ditto "<raiz>/build/candidato-1.8-<commit>/Lume.app" /Users/Shared/Lume-1.8-teste/Lume.app
   ditto "<raiz>/build/candidato-1.8-<commit>/Documentos-de-teste" /Users/Shared/Lume-1.8-teste/Documentos
   ```
   Na conta de teste, copie os documentos para a Mesa/Documentos da própria conta antes de usar
   (assim o backup e as correções ficam dentro dela).
3. **Não use manuscritos reais, nem chave da Anthropic.** Deixe “Coerência com IA” e “Auditoria
   final com IA” **desligadas**. Nada neste checklist envia texto à rede.
4. Se, mesmo assim, for testar na conta principal: use só os documentos sintéticos abaixo, não
   reanalise livros reais, e registre o que foi criado em `Application Support/FONTE`
   (`Decisoes/`, `Edicoes/`, `Copias/`, `Recuperacao/`, `Livros/`, `Relatorios/`, `Registros/`).
   Apague **somente** os arquivos cujos nomes você anotou; não apague mais nada da pasta.
5. O app compilado ainda se identifica como **Lume 1.7** (os números de versão só mudam na release).
   O candidato é identificado pelo commit em `CANDIDATO.txt`, ao lado do app.

## Documentos sintéticos (em `Documentos-de-teste/`)

| Arquivo | Uso |
|---|---|
| `Sintetico-A.docx` | Itens 2, 4–8 (somente leitura: DOCX não recebe correções) |
| `Sintetico-A.pages` | Itens 3, 4–10, 13 (documento Pages **fechado**) |
| `Sintetico-B.pages` | Item 11 (será aberto no Pages de propósito) |
| `Longo.docx` | Item 12 (cancelamento: 3 000 parágrafos) |

Textos inventados, com erros plantados (concordância/tempo, crase, repetição). Não contêm dados
pessoais.

## Como registrar

Para cada item: marque **OK** ou **Falhou**, anote a **evidência** (o que viu, o caminho do
arquivo, uma captura se quiser) e, se falhou, descreva o **defeito** (passos, mensagem exata).
Item não exercitado fica em branco: **não conta como aprovado**.

## Roteiro

| # | Fluxo | Passos | Esperado | Resultado | Evidência | Defeito |
|---|---|---|---|---|---|---|
| 1 | Abrir o aplicativo | Abra `Lume.app` (botão direito → Abrir, na primeira vez). Veja “Motor de análise”. | Abre sem erro; motor “FONTE 1.5.0 · embutido” | ☐ OK ☐ Falhou | | |
| 2 | Importar DOCX | Arraste/escolha `Sintetico-A.docx`. | Nome do arquivo aparece; análise liberada | ☐ OK ☐ Falhou | | |
| 3 | Importar Pages | Antes, no Terminal: `shasum -a 256 Sintetico-A.pages` e **anote o hash**. Escolha o arquivo no Lume (fechado no Pages). | Idem; sem aviso de erro | ☐ OK ☐ Falhou | | |
| 4 | Análise local | Com IA desligada, analise o DOCX e depois o Pages. | Termina sem erro; abre a Revisão com 4 alertas em cada: tempo verbal (“observa”), crase (“a professora”), frase duplicada e “e e” | ☐ OK ☐ Falhou | | |
| 5 | Alertas e relatório | Percorra os alertas; abra o inspetor; confira o trecho destacado do emoji (🌿) e dos acentos. | Destaque cobre exatamente o trecho; texto não truncado | ☐ OK ☐ Falhou | | |
| 6 | Salvar decisões | Marque 2–3 decisões diferentes; feche o relatório e reabra-o (Arquivo → relatórios recentes). | “Decisão salva neste Mac”; as marcações voltam | ☐ OK ☐ Falhou | | |
| 7 | Reanalisar | Use “Reanalisar” (sem mudar o arquivo). | Conclui; mensagem de decisões mantidas | ☐ OK ☐ Falhou | | |
| 8 | Preservação de decisões | Compare as decisões antes/depois da reanálise. | As dos alertas que continuam voltam iguais; nenhum alerta novo herda decisão | ☐ OK ☐ Falhou | | |
| 9 | Corrigir (Pages fechado) | No `Sintetico-A.pages`, escolha um alerta com correção e use “Corrigir”. Confirme a cópia. (Na primeira vez, permita a Automação do Pages.) | Pede confirmação; grava a correção; alerta fica “Corrigido”; abra o arquivo no Pages e veja só o trecho trocado | ☐ OK ☐ Falhou | | |
| 10 | Backup | Use “Mostrar cópia”. No Terminal: `shasum -a 256` na cópia e compare com o hash anotado no item 3. | A cópia existe em `Copias/<sha>/`; o hash é o do original anterior à correção | ☐ OK ☐ Falhou | | |
| 11 | Recusa com documento aberto | Abra `Sintetico-B.pages` no Pages e deixe-o aberto. No Lume, analise esse arquivo e tente corrigir um alerta. | Recusa: “Este documento está aberto no Pages…”; nada muda; janela do Pages intacta; análise funciona | ☐ OK ☐ Falhou | | |
| 12 | Cancelar | Inicie a análise de `Longo.docx` e cancele logo. | Volta ao estado anterior; sem relatório parcial; arquivo intacto; relatório anterior (se havia) preservado | ☐ OK ☐ Falhou | | |
| 13 | Fechar e reabrir | Feche o Lume (⌘Q) e abra de novo; abra o relatório de `Sintetico-A.pages`. | Decisões e histórico de correções presentes; “Corrigido” mantido | ☐ OK ☐ Falhou | | |
| 14 | Restaurar o embutido | Motor de análise → “Restaurar embutido”. | Mensagem de sucesso; decisões e relatórios continuam lá; análise volta a funcionar | ☐ OK ☐ Falhou | | |

## Depois do teste

- Envie ao desenvolvedor: este arquivo preenchido (e capturas dos itens que falharem).
- Conta de teste: pode ser removida sem efeito sobre a conta principal.
- Se testou na conta principal: confira que só os arquivos anotados no passo 4 foram criados.

Falhas de disco, de histórico e de restauração, a recusa do documento aberto e o Unicode no Pages
real já têm testes automáticos (`tests/EditCheck.swift`, `tests/pages_real_check.py`); este
roteiro cobre o que só a interface mostra.
