/* Optional isolated Edge qualification, never a user browser or native assistant. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const {pathToFileURL}=require('node:url'),{chromium}=require(process.argv[5]||'playwright');
const http=require('node:http');
const demo=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),root=path.dirname(demo.entrypoint),output=path.resolve(process.argv[3]);
fs.mkdirSync(output,{recursive:true});
const canonical=v=>JSON.stringify(v,(_,x)=>x&&!Array.isArray(x)&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,x[k]])):x);
const sha=s=>'sha256:'+crypto.createHash('sha256').update(s).digest('hex');
(async()=>{
 const browser=await chromium.launch({executablePath:process.argv[4],headless:true}),page=await browser.newPage({acceptDownloads:true}),checks=[],errors=[],remote=[];
 page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>{if(/^https?:/.test(r.url()))remote.push(r.url());});
 try {
  for(const width of [320,390,768,1440]) {
   await page.setViewportSize({width,height:1000});
   for(const dossier of demo.site.dossiers) {
    const folder=path.dirname(dossier.path),url=pathToFileURL(path.join(root,dossier.cooperation)).href;
    await page.goto(url+'?topic=09&audience=realisation');
    await page.waitForFunction(()=>document.body.dataset.diagramsReady==='true');
    await page.waitForSelector('#capsule-download:not([disabled])');
    assert.equal(await page.locator('#capsule-topic').inputValue(),'09');
    assert.equal(await page.locator('#capsule-audience').inputValue(),'realisation');
    await page.locator('#capsule-question').fill('Comment préparer la réalisation de ce mécanisme ?');
    await page.waitForFunction(()=>document.getElementById('capsule-prompt').value.includes('Comment préparer la réalisation'));
    await page.locator('.capsule-source-picker summary').click();
    const first=page.locator('#capsule-sources input').first();
    if(await first.count()) { await first.uncheck();await first.check(); }
    await page.waitForSelector('#capsule-download:not([disabled])');
    const sourceLinks=await page.locator('#capsule-sources a').evaluateAll(a=>a.map(a=>a.getAttribute('href')));
    for(const link of sourceLinks) {
     const [file,fragment]=link.split('#');assert.ok(fragment);
     assert.ok(fs.readFileSync(path.join(root,folder,file),'utf8').includes('id="'+fragment+'"'));
    }
    await page.locator('.capsule-source-picker summary').click();
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));
    const download=page.waitForEvent('download');await page.locator('#capsule-download').click();
    const downloaded=await download,filename=path.join(output,width+'-'+dossier.namespace+'.json');await downloaded.saveAs(filename);
    const request=JSON.parse(fs.readFileSync(filename,'utf8')),c=request.capsule,{capsule_digest,...content}=c;
    assert.deepEqual(c.baseline,dossier.baseline);assert.equal(c.namespace,dossier.namespace);
    assert.equal(c.question.topic,'09');assert.equal(c.audience,'realisation');assert.ok(c.sources.length<=64);
    assert.equal(capsule_digest,sha(canonical(content)));assert.ok(!JSON.stringify(c).includes('access_token'));
    await page.locator('#capsule-question').fill('');await page.waitForSelector('#capsule-download[disabled]');
    assert.ok((await page.locator('#capsule-status').innerText()).includes('Écrivez'));
    await page.locator('#capsule-topic').selectOption('23');await page.waitForSelector('#capsule-download:not([disabled])');
    await page.locator('#capsule-download').focus();assert.equal(await page.evaluate(()=>document.activeElement.id),'capsule-download');
    if(width===390||width===1440) await page.screenshot({path:path.join(output,width+'-'+dossier.namespace+'.png')});
    checks.push({namespace:dossier.namespace,width,download:path.basename(filename),capsule_digest,source_links:sourceLinks.length});
   }
  }
  const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:1000}}),plain=await nojs.newPage();
  for(const dossier of demo.site.dossiers) {
   await plain.goto(pathToFileURL(path.join(root,dossier.cooperation)).href);
   assert.equal(await plain.locator('#capsule-editor').isVisible(),false);
   assert.equal(await plain.locator('a[download]').count(),37);
   assert.ok(await plain.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));
  }
  await nojs.close();
  // A secure loopback origin and a disposable browser context allow actual
  // clipboard verification. No user browser, profile or clipboard is used.
  const server=http.createServer((req,res)=>{
   try {
    const file=path.resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));
    assert.ok(file.startsWith(path.resolve(root)+path.sep));
    const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8',
      '.css':'text/css; charset=utf-8','.json':'application/json','.svg':'image/svg+xml'};
    res.setHeader('Content-Type',types[path.extname(file)]||'application/octet-stream');
    res.end(fs.readFileSync(file));
   } catch (_) { res.statusCode=404;res.end('Not found'); }
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const origin='http://127.0.0.1:'+server.address().port,clipboard=[];
  try {
   const context=await browser.newContext({permissions:['clipboard-read','clipboard-write']}),clip=await context.newPage();
   clip.on('pageerror',e=>errors.push(String(e)));
   await clip.route('**/*',route=>{
    if(new URL(route.request().url()).origin===origin) return route.continue();
    remote.push(route.request().url());return route.abort();
   });
   for(const dossier of demo.site.dossiers) {
    await clip.goto(origin+'/'+dossier.cooperation);
    await clip.waitForSelector('#capsule-copy:not([disabled])');
    await clip.locator('#capsule-copy').click();
    await clip.waitForFunction(()=>/Demande copiée|Copie automatique indisponible/.test(document.getElementById('capsule-status').textContent));
    assert.ok((await clip.locator('#capsule-status').innerText()).includes('Demande copiée'));
    const copied=await clip.evaluate(()=>navigator.clipboard.readText()),preview=await clip.locator('#capsule-prompt').inputValue();
    // Windows clipboard text uses CRLF; only surrounding text line endings
    // differ. The parsed JSON and its canonical content digest must be exact.
    const normalized=copied.replace(/\r\n/g,'\n');assert.equal(normalized,preview);
    const c=JSON.parse(normalized.slice(normalized.indexOf('\n\n')+2)).capsule,{capsule_digest,...content}=c;
    assert.deepEqual(c.baseline,dossier.baseline);assert.equal(c.namespace,dossier.namespace);
    assert.equal(capsule_digest,sha(canonical(content)));
    // An explicit simulated denial verifies the manual-copy fallback, rather
    // than claiming a real permission refusal occurred in this context.
    await clip.evaluate(()=>{window.__fixtureClipboardWrite=navigator.clipboard.writeText;
      navigator.clipboard.writeText=async()=>{throw new Error('Fixture clipboard denial');};});
    await clip.locator('#capsule-copy').click();
    await clip.waitForFunction(()=>document.getElementById('capsule-status').textContent.includes('Copie automatique indisponible'));
    assert.ok((await clip.locator('#capsule-status').innerText()).includes('Copie automatique indisponible'));
    assert.equal(await clip.locator('#capsule-prompt').isVisible(),true);
    assert.equal(await clip.evaluate(()=>document.activeElement.id),'capsule-prompt');
    assert.equal(await clip.locator('#capsule-prompt').inputValue(),preview);
    await clip.evaluate(()=>{navigator.clipboard.writeText=window.__fixtureClipboardWrite;delete window.__fixtureClipboardWrite;});
    clipboard.push({namespace:dossier.namespace,baseline:dossier.baseline,capsule_digest,
      actual_clipboard_matches_preview_after_line_endings:true,
      parsed_json_digest_verified:true,simulated_denial_manual_fallback:true});
   }
   await context.close();
  } finally { await new Promise(resolve=>server.close(resolve)); }
  assert.deepEqual(errors,[]);assert.deepEqual(remote,[]);
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify({status:'PASS_SCOPED',engine:'air.question-capsule/1',
   checks,clipboard_checks:clipboard,no_js_dossiers:3,remote_requests:0,page_errors:errors,native_assistant_exercised:false},null,2)+'\n');
  console.log(JSON.stringify({status:'PASS_SCOPED',checks:checks.length,clipboard_checks:clipboard.length,no_js_dossiers:3}));
 } finally { await Promise.race([browser.close(),new Promise(r=>setTimeout(r,10000))]); }
})().then(()=>process.exit(0)).catch(e=>{console.error(e);process.exit(1);});
