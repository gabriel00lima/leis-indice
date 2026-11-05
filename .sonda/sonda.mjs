import { chromium } from 'playwright';
const REG = '202203143240';
const base = 'https://consulta-processo.web.stj.jus.br/';
const b = await chromium.launch();
const p = await b.newPage();
p.on('request', r => { const u = r.url(); if (!/\.(png|svg|woff2?|css|ico)(\?|$)/.test(u)) console.log('REQ', r.method(), u, r.postData() || ''); });
p.on('framenavigated', f => { if (f === p.mainFrame()) console.log('NAV', f.url()); });
await p.goto(base, { waitUntil: 'networkidle', timeout: 60000 });
console.log('HTML-HEAD', (await p.content()).slice(0, 3000));
const scripts = await p.$$eval('script[src]', s => s.map(x => x.src));
console.log('SCRIPTS', scripts);
for (const s of scripts) {
  const t = await (await fetch(s)).text();
  for (const m of t.matchAll(/(path:\s*["'`][^"'`]*["'`]|["'`]\/[a-zA-Z\-]+\/[^"'`\s]{0,80}["'`]|[a-zA-Z]+Registro[a-zA-Z]*|tipoPesquisa[^"'`]{0,60})/g)) console.log('BUNDLE', m[0]);
}
console.log('INPUTS', await p.$$eval('input,button,a', es => es.map(e => `${e.tagName} ${e.type||''} ${e.name||''} ${e.id||''} ${e.placeholder||''} ${(e.innerText||'').slice(0,40)} ${e.href||''}`).slice(0,80)));
const inp = await p.$('input[type=text], input:not([type])');
if (inp) { await inp.fill(REG); await inp.press('Enter'); await p.waitForTimeout(8000); console.log('URL-APOS-BUSCA', p.url()); console.log('TEXTO', (await p.innerText('body')).slice(0, 3000)); }
for (const c of ['processo/'+REG, '?termo='+REG, '?registro='+REG, 'processo?numeroRegistro='+REG, '#/processo/'+REG]) {
  await p.goto(base + c, { waitUntil: 'networkidle', timeout: 60000 }).catch(e => console.log('ERR', e.message));
  await p.waitForTimeout(4000);
  console.log('CAND', c, '=>', p.url(), JSON.stringify((await p.innerText('body')).slice(0, 600)));
}
await b.close();
