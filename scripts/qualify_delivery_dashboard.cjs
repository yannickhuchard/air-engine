// Browser qualification of generated static files, not a native ChatGPT receipt.
const fs = require('fs'), path = require('path'), http = require('http');
const { chromium } = require(process.argv[5]);
(async () => {
  const root = path.resolve(process.argv[2]), out = path.resolve(process.argv[3]);
  fs.mkdirSync(out, {recursive:true});
  const server = http.createServer((req,res) => {
    const file = path.resolve(root, '.' + decodeURIComponent(req.url.split('?')[0]));
    if (!file.startsWith(root + path.sep)) {res.writeHead(403); return res.end();}
    try {
      res.setHeader('Content-Type', file.endsWith('.css')?'text/css':file.endsWith('.js')?'text/javascript':file.endsWith('.json')?'application/json':file.endsWith('.svg')?'image/svg+xml':'text/html');
      res.end(fs.readFileSync(file));
    } catch {res.writeHead(404);res.end();}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const browser=await chromium.launch({executablePath:process.argv[4],headless:true});
  const errors=[], remote=[], checks=[];
  try {
    const manifest=JSON.parse(fs.readFileSync(path.join(root,'site-manifest.json')));
    const dossier=manifest.dossiers[0];
    for (const width of [390,768,1440]) {
      const page=await browser.newPage({viewport:{width,height:1000}});
      page.on('pageerror',e=>errors.push(e.message));
      page.on('console',e=>{if(e.type()==='error')errors.push(e.text());});
      page.on('request',req=>{if(!req.url().startsWith(origin))remote.push(req.url());});
      const response=await page.goto(origin+'/'+dossier.delivery_dashboard); if(response.status()!==200)throw Error('Missing dashboard');
      await page.locator('[data-filter="as-of"]').fill('2026-10-19');
      await page.locator('[data-filter="late"]').check();
      if(await page.locator('[data-delivery-task]:visible').count()!==1)throw Error('Late filter');
      await page.locator('[data-filter="week"]').fill('2026-W43');
      if(await page.locator('[data-delivery-task]:visible').count()!==0)throw Error('Week filter');
      await page.locator('[data-filter="week"]').fill('2026-W42');
      await page.locator('[data-filter="blocked"]').check();
      await page.locator('[data-filter="team"]').selectOption('urn:team:platform');
      await page.locator('[data-filter="member"]').selectOption('urn:identity:delivery-demo:architect');
      if(await page.locator('[data-delivery-task]:visible').count()!==1)throw Error('Combined filters');
      await page.getByRole('button',{name:'Réinitialiser'}).click();
      await page.waitForTimeout(50);
      if(await page.locator('[data-filter="team"]').inputValue()!=='')throw Error('Reset');
      if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Page overflow '+width);
      await page.screenshot({path:path.join(out,`delivery-${width}.png`),fullPage:true});
      const links=await page.locator('main a[href]').evaluateAll(elements=>elements.map(e=>e.getAttribute('href')));
      let verified=0;
      for(const href of [...new Set(links)]) {
        if(!href || href.startsWith('#'))continue;
        const r=await page.request.get(new URL(href,page.url()).toString());
        if(r.status()!==200)throw Error('Broken link '+href);verified++;
      }
      checks.push({width,combined_filters:true,iso_week:true,late:true,reset:true,page_overflow:false,links:verified});
      await page.close();
    }
    if(errors.length||remote.length)throw Error(JSON.stringify({errors,remote}));
    const result={result:'PASS_SCOPED',checks,script_errors:errors,external_requests:remote};
    fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(result,null,2)); console.log(JSON.stringify(result));
  } finally {await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
