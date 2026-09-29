const {JSDOM,VirtualConsole}=require('jsdom');
const fs=require('fs');
const path=require('path');
(async()=>{
 const errors=[]; const console=new VirtualConsole(); console.on('jsdomError',e=>errors.push(e.message));
 let exported;
 const dom=new JSDOM(fs.readFileSync(path.join(__dirname,'../Exemplo/Editorial/relatorio.html'),'utf8'),{
   runScripts:'dangerously',virtualConsole:console,beforeParse(w){
    w.Blob=Blob; w.URL.createObjectURL=b=>{exported=b;return 'blob:test'}; w.URL.revokeObjectURL=()=>{};
    w.HTMLAnchorElement.prototype.click=function(){};
   }});
 const w=dom.window,d=w.document;
 const count=()=>d.querySelectorAll('.card').length;
 function choose(id,value){d.getElementById(id).value=value;d.getElementById(id).dispatchEvent(new w.Event('input'))}
 function requireOK(condition,label){if(!condition)throw Error(label)}
 requireOK(count()===7,'Total de alertas');
 requireOK(d.getElementById('criteria').textContent.includes('2 títulos/capítulos detectados.'),'Capítulos no HTML');
 requireOK(d.getElementById('criteria').textContent.includes('Repetições: narração'),'Critérios no HTML');
 requireOK(d.querySelector('mark').textContent==='melhor eu me preparar melhor','Offsets Unicode');
 choose('layer','editorial'); requireOK(count()===5,'Filtro por camada');
 const sel=d.querySelector('.decision select');sel.value='Intencional';sel.dispatchEvent(new w.Event('change'));
 choose('decision','Intencional');requireOK(count()===1,'Decisão e filtro');
 d.getElementById('export').click();const saved=JSON.parse(await exported.text());
 requireOK(Object.values(saved.decisions).includes('Intencional'),'Exportação');
 saved.decisions.alerta_de_outro_modo='Aceito editorialmente';
 const target=d.getElementById('import');Object.defineProperty(target,'files',{value:[{size:100,text:async()=>JSON.stringify(saved)}]});
 await target.onchange({target});
 d.getElementById('export').click();const savedAgain=JSON.parse(await exported.text());
 requireOK(savedAgain.decisions.alerta_de_outro_modo==='Aceito editorialmente','Preservação de decisões de outros modos');
 choose('decision','');choose('category','Possível inconsistência temporal');requireOK(count()===2,'Filtro por categoria');
 requireOK(d.querySelector('h3').textContent==='Trechos relacionados','Evidência');
 requireOK(d.querySelector('.card details summary').textContent==='Ver contexto próximo','Contexto');
 requireOK(errors.length===0,errors.join(';'));
 process.stdout.write('DOM do HTML validado: alertas, Unicode, filtros, contexto, evidências, decisões, importação/exportação e preservação entre modos.\n');
 w.close();
})().catch(e=>{process.stderr.write(e.stack);process.exit(1)});
