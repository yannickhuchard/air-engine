/* Optional local browser qualification of fictional generated handoff files.
   node scripts/qualify_site_handoff.cjs site-demo.json output edge.exe playwright-directory */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const {pathToFileURL}=require('node:url'),{chromium}=require(process.argv[5]||'playwright');
const demo=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),root=path.dirname(demo.entrypoint),output=path.resolve(process.argv[3]);
fs.mkdirSync(output,{recursive:true});
const anchor=ref=>'n'+crypto.createHash('sha256').update(ref.id+':'+ref.revision).digest('hex').slice(0,12);
(async()=>{
 const browser=await chromium.launch({executablePath:process.argv[4],headless:true}),page=await browser.newPage(),checks=[],errors=[],remote=[];
 page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>{if(/^https?:/.test(r.url()))remote.push(r.url());});
 const ready=async()=>page.waitForFunction(()=>document.body.dataset.diagramsReady==='true');
 const fits=async()=>assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));
 try{
  for(const width of [320,390,768,1440]){
   await page.setViewportSize({width,height:1000});
   for(const dossier of demo.site.dossiers){
    const folder=path.dirname(dossier.path),model=JSON.parse(fs.readFileSync(path.join(root,dossier.handoff_data),'utf8'));
    assert.deepEqual(model.baseline,dossier.baseline);assert.ok(model.packets.length);
    await page.goto(pathToFileURL(path.join(root,dossier.handoff)).href);await ready();await fits();
    if(!model.teams.length)assert.match(await page.locator('main').innerText(),/Aucune équipe.*déclarée/);
    if(width===390||width===1440)await page.screenshot({path:path.join(output,width+'-'+dossier.namespace+'-index.png')});
    for(const [i,packet] of model.packets.entries()){
     const file='handoff-'+anchor(packet.target)+'.html';
     await page.goto(pathToFileURL(path.join(root,folder,file)).href);await ready();await fits();
     assert.equal(await page.locator('h1').innerText(),packet.name.replace(/\u2014/g,'-'));
     assert.equal(await page.locator('.handoff-section').count(),9);
     for(const gap of packet.gaps)assert.ok((await page.locator('#handoff-gaps').innerText()).includes(gap.label));
     assert.ok((await page.content()).includes(model.baseline.digest));
     assert.equal(await page.locator('.diagram[data-rendered=false]').count(),0,'The source-linked focus diagram must render');
     assert.ok(await page.locator('.diagram svg').count());
     // The nine section links are native anchors, including on mobile/keyboard.
     const toc=page.locator('.handoff-toc a[href="#handoff-verification"]');await toc.focus();await page.keyboard.press('Enter');
     assert.ok(page.url().endsWith('#handoff-verification'));
     const details=page.locator('.handoff-source details').first();await details.locator('summary').focus();await page.keyboard.press('Enter');
     assert.ok(await details.evaluate(e=>e.open));
     const source=packet.sections.design[0];assert.ok((await page.content()).includes(source.digest));
     if(i===0&&(width===390||width===1440)){
      await page.locator('#handoff-map').scrollIntoViewIfNeeded();
      await page.screenshot({path:path.join(output,width+'-'+dossier.namespace+'-focus.png')});
     }
     await page.goto(pathToFileURL(path.join(root,folder,'diagram-'+file)).href);await ready();await fits();
     assert.equal(await page.locator('.diagram[data-rendered=false]').count(),0);
     assert.ok(await page.locator('.diagram svg .air-linked').count(),'Diagram nodes retain exact source navigation');
     checks.push({width,dossier:dossier.namespace,target:packet.target,sections:9,missing_explicit:true,focus_diagram:true,keyboard:true,overflow:false});
    }
    for(const team of model.teams){
     await page.goto(pathToFileURL(path.join(root,folder,'handoff-team-'+anchor(team.target)+'.html')).href);await ready();await fits();
     assert.equal(await page.locator('h1').innerText(),team.name.replace(/\u2014/g,'-'));
    }
   }
  }
  const context=await browser.newContext({javaScriptEnabled:false}),fallback=await context.newPage();
  const d=demo.site.dossiers[0],model=JSON.parse(fs.readFileSync(path.join(root,d.handoff_data),'utf8'));
  await fallback.goto(pathToFileURL(path.join(root,path.dirname(d.path),'handoff-'+anchor(model.packets[0].target)+'.html')).href);
  assert.ok(await fallback.locator('#handoff-gaps').isVisible());assert.equal(await fallback.locator('.handoff-section').count(),9);
  await fallback.locator('.diagram-source summary').click();assert.ok(await fallback.locator('.diagram-source pre').isVisible());
  await context.close();assert.deepEqual(errors,[]);assert.deepEqual(remote,[]);
  const report={status:'PASS_SCOPED',checks,dossiers:demo.site.dossiers.length,widths:[320,390,768,1440],without_javascript:true,
   page_errors:errors,external_requests:remote,participants:0,native_client_qualification:false,business_execution_performed:false};
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
  process.stdout.write(JSON.stringify({status:report.status,focus_checks:checks.length,dossiers:report.dossiers})+'\n');
 }finally{await Promise.race([browser.close(),new Promise(resolve=>setTimeout(resolve,10000))]);}
 process.exit(0);
})().catch(e=>{process.stderr.write(String(e.stack)+'\n');process.exit(1);});
