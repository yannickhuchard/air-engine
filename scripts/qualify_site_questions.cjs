/* Optional browser qualification of AIR's generated fictional reading routes.
   node scripts/qualify_site_questions.cjs site-demo.json output edge.exe playwright-directory
   The installed AIR product needs Python alone. No user browser is controlled. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.argv[5]||'playwright');
const demo=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const output=path.resolve(process.argv[3]),root=path.dirname(demo.entrypoint);
const origin=process.argv[6];
if(origin&&!/^http:\/\/127\.0\.0\.1:\d+$/.test(origin))throw new Error('The optional offline check requires the owned loopback preview');
fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:process.argv[4],headless:true});
 const page=await browser.newPage(),checks=[],errors=[],external=[],offline=[];
 page.on('pageerror',e=>errors.push(String(e)));
 page.on('request',r=>{if(/^https?:/.test(r.url())&&(!origin||!r.url().startsWith(origin+'/')))external.push(r.url());});
 try{
  for(const width of [320,390,768,1440]){
   await page.setViewportSize({width,height:1000});
   for(const dossier of demo.site.dossiers){
    const folder=path.dirname(dossier.path);
    const model=JSON.parse(fs.readFileSync(path.join(root,dossier.questions_data),'utf8'));
    assert.deepEqual(model.baseline,dossier.baseline);
    assert.equal(model.questions.length,37);assert.equal(model.roles.length,6);
    for(const role of model.roles){
     const file=path.join(folder,'role-'+role.id+'.html');
     await page.goto(pathToFileURL(path.join(root,file)).href);
     await page.waitForFunction(()=>document.body.dataset.diagramsReady==='true');
     assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),file+' overflows');
     assert.equal(await page.locator('.question-card').count(),role.questions.length);
     await page.locator('.reading-context summary').click();
     const context=await page.locator('.reading-context').innerText();
     assert.ok(context.includes(dossier.baseline.id)&&context.includes(dossier.baseline.digest));
     await page.locator('.reading-context summary').click();
     await page.locator('#question-search').fill('zzzz-no-result');
     assert.equal(await page.locator('.question-card:visible').count(),0);
     assert.match(await page.locator('#question-search-status').innerText(),/Aucun résultat/);
     await page.locator('#question-search').fill('');
     assert.equal(await page.locator('.question-card:visible').count(),role.questions.length);
     await page.locator('.question-card h2 a').first().focus();
     const target=await page.locator('.question-card h2 a').first().evaluate(a=>a.href);
     await Promise.all([page.waitForURL(target),page.keyboard.press('Enter')]);
     assert.ok(path.basename(new URL(page.url()).pathname).match(/^\d\d-.*\.html$/));
     checks.push({width,dossier:dossier.namespace,role:role.id,questions:role.questions.length,
                  horizontal_overflow:false,search:true,keyboard_topic_navigation:true,exact_context:true});
    }
    await page.goto(pathToFileURL(path.join(root,dossier.questions)).href);
    await page.waitForFunction(()=>document.body.dataset.diagramsReady==='true');
    await page.locator('#question-search').fill('coûts');
    assert.ok(await page.locator('.question-card:visible').count()>=1);
    const budget=await page.locator('#q17').innerText();
    assert.match(budget,/Postes de coûts CAPEX et OPEX/);
    assert.match(budget,/Information manquante|Dimensions non documentées/);
    assert.match(await page.locator('#q28').innerText(),/Contrôle calculé/i);
   }
   await page.goto(pathToFileURL(path.join(root,demo.site.dossiers[0].path)).href);
   await page.waitForFunction(()=>document.body.dataset.diagramsReady==='true');
   assert.equal(await page.locator('.reading-route').count(),6);
   await page.screenshot({path:path.join(output,'dossier-'+width+'.png'),fullPage:false});
   await page.goto(pathToFileURL(path.join(root,path.dirname(demo.site.dossiers[0].path),'role-comex.html')).href);
   await page.waitForFunction(()=>document.body.dataset.diagramsReady==='true');
   await page.screenshot({path:path.join(output,'comex-'+width+'.png'),fullPage:false});
  }
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  await page.emulateMedia({reducedMotion:'reduce'});
  assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).scrollBehavior),'auto');
  if(origin){
   await page.goto(origin+'/index.html');
   await page.locator('.app-menu summary').click();
   await page.locator('#pwa-enable').click();
   await page.waitForFunction(()=>Boolean(navigator.serviceWorker.controller),{},{timeout:60000});
   await page.context().setOffline(true);
   for(const dossier of demo.site.dossiers){
    await page.goto(origin+'/'+path.dirname(dossier.path).replaceAll('\\','/')+'/role-comex.html');
    await page.waitForFunction(()=>document.body.dataset.diagramsReady==='true');
    assert.equal(await page.locator('h1').innerText(),'COMEX');
    assert.ok((await page.locator('.reading-context').textContent()).includes(dossier.baseline.digest));
    offline.push({dossier:dossier.namespace,role:'comex',exact_context:true,offline:true});
   }
   await page.context().setOffline(false);
  }
  fs.writeFileSync(path.join(output,'checks.json'),JSON.stringify({status:'PASS_SCOPED',
   method:'Isolated Edge; generated fictional files, no participant sessions',checks,
   widths:[320,390,768,1440],dossiers:3,roles_per_dossier:6,page_errors:errors,
   external_requests:external,offline_routes:offline,participants:0,client_plugin_qualification:false,
   accessibility_certification:false},null,2)+'\n');
  console.log(JSON.stringify({status:'PASS_SCOPED',role_checks:checks.length,dossiers:3,widths:4}));
 }finally{await Promise.race([browser.close(),new Promise(resolve=>setTimeout(resolve,10000))]);}
})().then(()=>process.exit(0)).catch(e=>{console.error(e);process.exit(1);});
