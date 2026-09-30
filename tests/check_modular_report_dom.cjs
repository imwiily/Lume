const {JSDOM, VirtualConsole} = require('jsdom');
const fs = require('fs');
const path = require('path');
const errors = [];
const vc = new VirtualConsole();
vc.on('jsdomError', e => errors.push(e.message));
const dom = new JSDOM(fs.readFileSync(path.join(__dirname, '../examples/Mestre/relatorio.html'), 'utf8'), {
  runScripts: 'dangerously', virtualConsole: vc
});
const w = dom.window, d = w.document;
function requireOK(condition, message) { if (!condition) throw Error(message); }
function choose(id, value) { const el = d.getElementById(id); el.value = value; el.dispatchEvent(new w.Event('input')); }
const count = () => d.querySelectorAll('.card').length;
requireOK(count() === 11, 'Total do corpus modular');
requireOK(d.getElementById('stages').textContent.includes('Auditoria final: Ainda não disponível'), 'Não anunciar auditoria concluída');
choose('module', 'linguistic'); requireOK(count() === 3, 'Linguístico');
choose('severity', 'confirmed_error'); requireOK(count() === 1, 'Erro confirmado');
requireOK(d.querySelector('mark').textContent === 'Além de disso', 'Offsets com emoji');
requireOK(d.querySelector('.suggestion').textContent.includes('Além disso'), 'Sugestão separada');
choose('severity', 'probable_error'); requireOK(count() === 2, 'Prováveis erros');
choose('severity', ''); choose('module', 'morphosyntactic'); requireOK(count() === 3, 'Morfossintático');
choose('module', 'global_coherence'); requireOK(count() === 2, 'Coerência');
choose('severity', 'possible_inconsistency'); requireOK(count() === 1, 'Inconsistência');
requireOK(d.querySelector('h3').textContent === 'Trechos relacionados', 'Evidência preservada');
choose('severity', ''); choose('module', 'audit'); requireOK(count() === 0, 'Nenhum alerta fictício de auditoria');
requireOK(errors.length === 0, errors.join('; '));
w.close();
process.stdout.write('Relatório modular validado: etapas, classificações, filtros, sugestões e Unicode.\n');
