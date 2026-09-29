const {JSDOM, VirtualConsole} = require('jsdom');
const fs = require('fs');
const path = require('path');
const errors = [];
const vc = new VirtualConsole();
vc.on('jsdomError', e => errors.push(e.message));
const dom = new JSDOM(fs.readFileSync(path.join(__dirname, '../Exemplo/Temporal/relatorio.html'), 'utf8'), {
  runScripts: 'dangerously', virtualConsole: vc
});
const w = dom.window, d = w.document;
function requireOK(condition, message) { if (!condition) throw Error(message); }
function choose(id, value) { const el = d.getElementById(id); el.value = value; el.dispatchEvent(new w.Event('input')); }
const count = () => d.querySelectorAll('.card').length;
requireOK(count() === 9, 'Total da demonstração temporal');
choose('severity', 'confirmed_error'); requireOK(count() === 0, 'Nenhuma dúvida tratada como erro confirmado');
choose('severity', 'editorial_attention'); requireOK(count() === 2, 'Duas dúvidas temporais');
requireOK(d.querySelector('mark').textContent === 'atravessamos', 'Homógrafo destacado');
requireOK(!d.querySelector('.card').querySelector('.suggestion'), 'Sem substituição obrigatória para homógrafo');
choose('severity', ''); choose('module', 'morphosyntactic'); requireOK(count() === 7, 'Relações e acentuação contextual');
requireOK(d.querySelector('mark').textContent === 'receberá', 'Trecho temporal exato');
requireOK(d.querySelector('.suggestion').textContent.includes('receberia'), 'Sugestão condicional');
requireOK(d.querySelector('h3').textContent === 'Trechos relacionados', 'Evidência da relação visível');
choose('module', 'linguistic'); requireOK(count() === 2, 'Mecânica do diálogo');
requireOK(d.querySelector('.suggestion').textContent.includes('quê'), 'Acentuação da pergunta');
choose('module', 'audit'); requireOK(count() === 0, 'Auditoria sem ocorrências inventadas');
requireOK(errors.length === 0, errors.join('; '));
w.close();
process.stdout.write('Relatório temporal validado: dúvidas, sugestões, evidências, filtros e acentos.\n');
