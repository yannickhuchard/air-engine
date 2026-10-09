/* Optional isolated browser QA. The AIR installation still needs Python only. */
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
 try{
  const files=['index.html','transformation.html',...manifest.dossiers.flatMap(d=>[d.management_summary,d.transformation])];
  for(const width of [320,390,768,1440]){
   await page.setViewportSize({width,height:900});
   for(const file of files){
    await page.goto(pathToFileURL(path.join(root,file)).href);
    await page.waitForFunction(()=>document.body.dataset.diagramsReady==='true');
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),file+' overflows '+width);
    const ids=await page.locator('[id]').evaluateAll(es=>es.map(e=>e.id));
    assert.equal(new Set(ids).size,ids.length,file+' duplicate IDs');
    if(file.includes('transformation.html')){
     const details=page.locator('.transformation-view details').first();
     if(await details.count()){
      await details.locator('summary').focus();await page.keyboard.press('Enter');
      assert.equal(await details.evaluate(e=>e.open),true,file+' summary keyboard at '+width);
      await page.keyboard.press('Enter');
      const a=page.locator('.transformation-map a').first();
      await a.focus();await page.keyboard.press('Enter');
      await page.waitForFunction(()=>document.getElementById(location.hash.slice(1))?.open===true);
      assert.equal(await details.evaluate(e=>e.open),true,file+' graph keyboard at '+width+' '+await page.evaluate(()=>location.hash));
     }
    }
    checks.push({page:file,width,document_overflow:false});
    if([390,1440].includes(width)&&file==='transformation.html'){
     await page.evaluate(()=>window.scrollTo({top:0,behavior:'instant'}));
     await page.screenshot({path:path.join(out,'transformation-'+width+'.png'),fullPage:false});
    }
   }
  }
  const nojs=await browser.newContext({javaScriptEnabled:false});const plain=await nojs.newPage();
  for(const d of manifest.dossiers){
   await plain.goto(pathToFileURL(path.join(root,d.management_summary)).href);
   assert.ok(await plain.locator('.management-summary').innerText());
   await plain.goto(pathToFileURL(path.join(root,d.transformation)).href);
   assert.ok(await plain.locator('.transformation-view').innerText());
  }
  await nojs.close();assert.deepEqual(errors,[]);assert.deepEqual(remote,[]);
  const report={status:'PASS_SCOPED',scope:'ISOLATED_LOCAL_BROWSER_NOT_NATIVE_CHATGPT_OR_USER_RESEARCH',checks,keyboard:true,no_javascript_reading:true,remote_requests:0};
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2)+'\n');
  process.stdout.write(JSON.stringify({status:report.status,page_checks:checks.length,remote_requests:0})+'\n');
 }finally{await browser.close();}
})().catch(e=>{process.stderr.write(String(e.stack)+'\n');process.exitCode=1;});
