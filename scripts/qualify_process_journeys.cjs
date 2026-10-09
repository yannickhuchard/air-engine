/* Optional isolated browser QA. No Node/browser is required to install AIR. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const [rootArg,outArg,exe,pw]=process.argv.slice(2),root=path.resolve(rootArg),out=path.resolve(outArg);
const {chromium}=require(pw);
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({executablePath:exe,headless:true});
 const page=await browser.newPage(),errors=[],remote=[],checks=[];
 page.on('pageerror',e=>errors.push(String(e)));
 page.on('request',r=>{if(/^https?:/.test(r.url()))remote.push(r.url());});
 const manifest=JSON.parse(fs.readFileSync(path.join(root,'site-manifest.json'),'utf8'));
 const journeys=manifest.dossiers.flatMap(d=>{
   const view=JSON.parse(fs.readFileSync(path.join(root,d.journeys_data),'utf8'));
   return view.journeys.slice(0,2).map(j=>path.posix.join(path.posix.dirname(d.journeys),'journey-'+require('node:crypto').createHash('sha256').update(j.reference.id+':'+j.reference.revision).digest('hex').slice(0,12).replace(/^/,'n')+'.html'));
 });
 const processes=manifest.dossiers.flatMap(d=>fs.readdirSync(path.join(root,path.dirname(d.path))).filter(n=>/^process-n.*\.html$/.test(n)).map(n=>path.posix.join(path.posix.dirname(d.path),n)));
 try{
  for(const width of [320,390,768,1440]){
   await page.setViewportSize({width,height:1050});
   for(const file of [...journeys,...processes]){
    await page.goto(pathToFileURL(path.join(root,file)).href);
    await page.waitForFunction(()=>document.body.dataset.diagramsReady==='true');
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),file+' document overflow '+width);
    const ids=await page.locator('[id]').evaluateAll(es=>es.map(e=>e.id));assert.equal(new Set(ids).size,ids.length,file+' duplicate IDs');
    if(file.includes('/process-')){
     await page.waitForFunction(()=>[...document.querySelectorAll('.process-diagram')].every(e=>e.dataset.bpmnReady));
     assert.equal(await page.locator('.process-diagram').getAttribute('data-bpmn-ready'),'true',file+' BPMN import failed');
     assert.equal(await page.locator('.bjs-powered-by').isVisible(),true,'watermark must stay visible');
     await page.locator('[data-bpmn-zoom="fit"]').click();
     await page.locator('[data-bpmn-zoom="read"]').click();
     await page.locator('[data-bpmn-zoom="in"]').click();
     await page.locator('[data-bpmn-zoom="out"]').focus();await page.keyboard.press('Enter');
     await page.locator('[data-bpmn-zoom="read"]').click();
     assert.ok(await page.locator('.process-viewer').evaluate(e=>{
       const area=e.getBoundingClientRect();return [...e.querySelectorAll('.djs-shape')].some(n=>{
        if(!/^n[0-9a-f]{12}_n[0-9a-f]{12}$/.test(n.getAttribute('data-element-id')||''))return false;
        const b=n.getBoundingClientRect();return b.width>20&&b.height>20&&b.left<area.right&&b.right>area.left&&b.top<area.bottom&&b.bottom>area.top;
       });
     }),file+' has no activity in the initial reading viewport');
    }else{
     const table=page.locator('.journey-matrix');await table.focus();await page.keyboard.press('ArrowRight');
     assert.ok(await page.locator('.journey-matrix th[scope="row"]').count()>=14);
     assert.ok(await page.locator('.journey-matrix th[scope="col"]').count()>=2);
     if(width<700) assert.equal(await page.locator('.journey-mobile').isVisible(),true);
    }
    checks.push({file,width,overflow:false});
    if([390,1440].includes(width)){
     const subject=page.locator(file.includes('/process-')?'.process-diagram':'.journey-map');
     await subject.evaluate(e=>e.scrollIntoView({block:'start',behavior:'instant'}));
     await page.screenshot({path:path.join(out,path.basename(file,'.html')+'-'+width+'.png'),fullPage:false});
    }
   }
  }
  const nojs=await browser.newContext({javaScriptEnabled:false});const plain=await nojs.newPage();
  for(const file of [...journeys,...processes]){
    await plain.goto(pathToFileURL(path.join(root,file)).href);
    assert.ok(await plain.locator(file.includes('/process-')?'.process-fallback svg':'.journey-matrix table').isVisible());
  }
  await nojs.close();assert.deepEqual(errors,[]);assert.deepEqual(remote,[]);
  const report={status:'PASS_SCOPED',scope:'LOCAL_BROWSER_NOT_USER_RESEARCH',checks,no_js:true,bpmn_imports_without_warnings:true,watermark_visible:true,remote_requests:0};
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2)+'\n');process.stdout.write(JSON.stringify({status:report.status,views:checks.length})+'\n');
 }finally{await browser.close();}
})().catch(e=>{process.stderr.write(String(e.stack)+'\n');process.exitCode=1;});
