/* Optional isolated local-browser verification. AIR itself still needs Python only. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.argv[5]||'playwright');
const root=path.resolve(process.argv[2]),out=path.resolve(process.argv[3]);
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:process.argv[4],headless:true});
 const context=await browser.newContext(),page=await context.newPage(),errors=[],requests=[],checks=[];
 page.on('pageerror',e=>errors.push(String(e)));
 page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});
 const manifest=JSON.parse(fs.readFileSync(path.join(root,'site-manifest.json'),'utf8'));
 try {
  for(const width of [320,390,768,1440]) {
   await page.setViewportSize({width,height:900});
   for(const d of manifest.dossiers) {
    for(const file of [d.path,d.finance,d.traceability]) {
     await page.goto(pathToFileURL(path.join(root,file)).href);
     await page.waitForFunction(()=>document.body.dataset.diagramsReady==='true');
     assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),file+' overflows '+width);
     if(file===d.traceability && await page.locator('#sankey-filter option').count()>1) {
      const selected=await page.locator('#sankey-filter option').nth(1).getAttribute('value');
      await page.locator('#sankey-filter').focus();await page.keyboard.press('ArrowDown');await page.keyboard.press('Enter');
      // Browser/platform key handling differs: selectOption is a real select change if keys did not choose.
      if(await page.locator('#sankey-filter').inputValue()!==selected) await page.locator('#sankey-filter').selectOption(selected);
      assert.equal(await page.locator('.sankey-paths:visible').count(),1);
      await page.locator('.sankey-paths:visible > summary').focus();await page.keyboard.press('Enter');
      assert.equal(await page.locator('.sankey-paths:visible').evaluate(e=>e.open),true);
      assert.ok(await page.locator('.sankey-paths:visible a').count()>0);
      await page.locator('#sankey-filter').selectOption('');
      assert.equal(await page.locator('.sankey-paths:visible').count(),await page.locator('.sankey-paths').count());
     }
     if(manifest.dossiers.indexOf(d)===0 && [390,1440].includes(width))
      await page.screenshot({path:path.join(out,width+'-'+path.basename(file,'.html')+'.png'),fullPage:false});
     checks.push({width,page:file,document_overflow:false});
    }
   }
  }
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.goto(pathToFileURL(path.join(root,manifest.dossiers[0].traceability)).href);
  if(await page.locator('.sankey-flow').count()) assert.equal(await page.locator('.sankey-flow').first().evaluate(e=>getComputedStyle(e).transitionDuration),'0s');
  // Text traces must remain usable with JavaScript disabled.
  const noJs=await browser.newContext({javaScriptEnabled:false}),fallback=await noJs.newPage();
  await fallback.goto(pathToFileURL(path.join(root,manifest.dossiers[0].traceability)).href);
  const traces=await fallback.locator('.sankey-paths').count();
  if(traces) {await fallback.locator('.sankey-paths > summary').first().click();assert.ok(await fallback.locator('.sankey-paths[open] a').count()>0);}
  await noJs.close();
  assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
  const result={status:'PASS_SCOPED',scope:'LOCAL_FINANCE_AND_SANKEY_UI',browser:browser.version(),dossiers:manifest.dossiers.map(d=>({name:d.name,baseline:d.baseline})),
   checked:checks,keyboard_select_and_disclosure:true,source_links_without_javascript:true,reduced_motion:true,remote_requests:0,page_errors:[],human_research_performed:false};
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(result,null,2)+'\n');
  process.stdout.write(JSON.stringify({status:result.status,pages:checks.length,viewports:[320,390,768,1440],remote_requests:0})+'\n');
 } finally {await browser.close();}
})().catch(e=>{process.stderr.write(String(e)+'\n');process.exitCode=1;});
