const {JSDOM, VirtualConsole} = require('jsdom');
const fs = require('fs');
const path = require('path');
const errors=[];
const vc=new VirtualConsole();
vc.on('jsdomError', e=>errors.push(e.message));
const reportPath=path.join(__dirname,'../examples/Memoria/Relatorio/relatorio.html');
const dom=new JSDOM(fs.readFileSync(reportPath,'utf8'),{runScripts:'dangerously',virtualConsole:vc});
const w=dom.window,d=w.document;
function check(test,message){if(!test)throw Error(message)}
function choose(id,value){const e=d.getElementById(id);e.value=value;e.dispatchEvent(new w.Event('input'))}
check(!d.getElementById('memory-panel').hidden,'Memória visível');
check(d.getElementById('memory').textContent.includes('2 cenas · 7 fatos'),'Contagens da memória');
check(d.querySelectorAll('#memory blockquote').length===7,'Evidência dos sete fatos');
check(d.querySelectorAll('.card').length===5,'Cinco ocorrências');
choose('module','global_coherence');
check(d.querySelectorAll('.card').length===3,'Três conflitos globais');
choose('severity','possible_inconsistency');
check(d.querySelectorAll('.card').length===3,'Classificação preservada');
check(d.querySelector('.card').textContent.includes('Íris só usa fogo.'),'Evidência anterior visível');
check(!d.querySelector('.suggestion'),'Sem substituição automática');
choose('module','audit');check(d.querySelectorAll('.card').length===0,'Sem auditoria fictícia');
check(errors.length===0,errors.join('; '));
w.close();
console.log('Memória narrativa: cenas, fatos, evidências, classificações e filtros aprovados.');
