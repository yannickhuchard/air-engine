/* Optional isolated browser QA; the AIR runtime still needs Python only. */
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {pathToFileURL}=require('url');
const [rootArg,outArg,exe,pw]=process.argv.slice(2),root=path.resolve(rootArg),out=path.resolve(outArg);
const {chromium}=require(pw);
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({executablePath:exe,headless:true});
 const page=await browser.newPage(),errors=[],remote=[],checks=[];
 page.on('pageerror',e=>errors.push(String(e)));
 page.on('request',r=>{if(/^https?:/.test(r.url()))remote.push(r.url());});
 const manifest=JSON.parse(fs.readFileSync(path.join(root,'site-manifest.json'),'utf8'));
 try {
  for(const width of [320,390,768,1440]) {
   await page.setViewportSize({width,height:900});
   for(const d of manifest.dossiers) {
    const model=JSON.parse(fs.readFileSync(path.join(root,d.journeys_data),'utf8'));
    const dir=path.dirname(d.journeys),focus=model.journeys.map(j=>path.join(dir,'journey-'+require('crypto').createHash('sha256').update(j.reference.id+':'+j.reference.revision).digest('hex').slice(0,12).replace(/^/,'n')+'.html'));
    for(const file of [d.path,d.journeys,...focus]) {
     await page.goto(pathToFileURL(path.join(root,file)).href);
     await page.waitForFunction(()=>document.body.dataset.diagramsReady==='true');
     assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),file+' overflows '+width);
     if(file===d.journeys && model.personas.length) {
      const select=page.locator('#journey-persona'),key=await select.locator('option').nth(1).getAttribute('value');
      await select.focus();await page.keyboard.press('ArrowDown');await page.keyboard.press('Enter');
      if(await select.inputValue()!==key)await select.selectOption(key);
      assert.equal(await page.locator('.persona-journeys:visible').count(),1);
      assert.ok(await page.locator('#journey-filter-status').innerText());
      await select.selectOption('');assert.equal(await page.locator('.persona-journeys:visible').count(),model.personas.length);
     }
     if(file.includes('journey-n')) {
      const details=page.locator('.journey-steps details').first();
      await details.locator('summary').focus();await page.keyboard.press('Enter');
      assert.equal(await details.evaluate(e=>e.open),true);
     }
     await page.keyboard.press('Escape');
     await page.evaluate(()=>{document.activeElement?.blur();window.scrollTo({top:0,behavior:'instant'});});
     if(manifest.dossiers.indexOf(d)===0 && [390,1440].includes(width) && [d.journeys,focus[0]].includes(file))
      await page.screenshot({path:path.join(out,width+'-'+(file===d.journeys?'catalog':'focus')+'.png'),fullPage:false});
     checks.push({width,page:file,document_overflow:false});
    }
   }
  }
  const fallbackContext=await browser.newContext({javaScriptEnabled:false}),fallback=await fallbackContext.newPage();
  const d=manifest.dossiers[0],model=JSON.parse(fs.readFileSync(path.join(root,d.journeys_data),'utf8'));
  await fallback.goto(pathToFileURL(path.join(root,d.journeys)).href);
  assert.equal(await fallback.locator('.persona-journeys:visible').count(),model.personas.length);
  assert.ok(await fallback.locator('a[href^="journey-"]').count()>=model.journeys.length);
  await fallbackContext.close();assert.deepEqual(errors,[]);assert.deepEqual(remote,[]);
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({status:'PASS_SCOPED',scope:'LOCAL_JOURNEY_UI',checked:checks,
   browser:browser.version(),keyboard_filter_and_disclosures:true,no_javascript_full_inventory:true,
   remote_requests:0,page_errors:[],human_research_performed:false},null,2)+'\n');
  process.stdout.write(JSON.stringify({status:'PASS_SCOPED',page_checks:checks.length,remote_requests:0})+'\n');
 }finally{await browser.close();}
})().catch(e=>{process.stderr.write(String(e)+'\n');process.exitCode=1;});
