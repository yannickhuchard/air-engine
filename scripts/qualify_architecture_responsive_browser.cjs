/* Optional local UI qualification, using a disposable headless browser. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');const {chromium}=require(process.argv[4]||'playwright');
const demo=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),root=path.dirname(demo.entrypoint);
const output=path.resolve(path.dirname(process.argv[2]),'responsive-browser');fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:process.argv[3],headless:true});
 const context=await browser.newContext(),page=await context.newPage(),errors=[],requests=[];
 page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});
 const checked=[];
 try {
  const dossier=path.dirname(demo.site.dossiers[0].path);
  for(const width of [320,390,768,1440]){
   await page.setViewportSize({width,height:900});
   for(const file of ['index.html',dossier+'/19-modele-donnees-logique.html',dossier+'/graph.html','timeline.html']){
    // Find the actual topic name from the generator, not a translation guess.
    const chosen=file.includes('19-')?path.join(dossier,fs.readdirSync(path.join(root,dossier)).find(x=>x.startsWith('19-')&&x.endsWith('.html'))):file;
    await page.goto(pathToFileURL(path.join(root,chosen)).href);
    await page.waitForFunction(()=>document.body.dataset.diagramsReady==='true');
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),chosen+' '+width);
    const nav=page.locator('.workspace-nav');assert.equal(await nav.evaluate(e=>e.open),width>900);
    if(width<=900){
      assert.ok((await page.locator('h1').boundingBox()).y<400,'Reading must start before the fold');
      await nav.locator(':scope>summary').focus();await page.keyboard.press('Enter');assert.equal(await nav.evaluate(e=>e.open),true);
      assert.ok(await nav.locator('nav').isVisible());
      await page.keyboard.press('Enter');assert.equal(await nav.evaluate(e=>e.open),false);
    }
    assert.equal(await page.locator('#pwa-enable').isVisible(),false,'file mode must not enable browser caching');
    assert.ok((await page.locator('#pwa-status').textContent()).includes('Lecture directe'));
    await page.screenshot({path:path.join(output,width+'-'+path.basename(chosen,'.html')+'.png'),fullPage:true});
    checked.push({width,page:chosen});
   }
  }
  await page.emulateMedia({reducedMotion:'reduce'});
  assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).scrollBehavior),'auto');
  await page.goto(pathToFileURL(demo.entrypoint).href);await page.keyboard.press('Tab');
  assert.equal(await page.locator(':focus').textContent(),'Aller au contenu');
  assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
  const result={status:'PASS_SCOPED',browser:browser.version(),viewports:[320,390,768,1440],pages_checked:checked.length,
   no_document_overflow:true,content_before_mobile_fold:true,mobile_menu_keyboard:true,reduced_motion:true,skip_link:true,
   file_mode_no_worker:true,remote_requests:0,page_errors:[],checked};
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(result,null,2)+'\n');process.stdout.write(JSON.stringify({...result,checked:undefined})+'\n');
 } finally{await Promise.race([browser.close(),new Promise(r=>setTimeout(r,10000))]);}
 process.exit(0);
})().catch(e=>{process.stderr.write(e.stack+'\n');process.exit(1);});
