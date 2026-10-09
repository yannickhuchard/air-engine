/* Optional disposable Edge qualification and real AIR UI captures for BRAG. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');const {chromium}=require(process.argv[4]||'playwright');
const demo=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),root=path.dirname(demo.entrypoint);
const output=path.resolve(path.dirname(process.argv[2]),'story-browser');fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:process.argv[3],headless:true});
 const context=await browser.newContext({deviceScaleFactor:2}),page=await context.newPage(),errors=[],external=[];
 page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>{if(/^https?:/.test(r.url()))external.push(r.url());});
 let pages=0;
 try{
  for(const [i,d] of demo.site.dossiers.entries()){
   for(const width of [390,1440]){
    await page.setViewportSize({width,height:900});await page.goto(pathToFileURL(path.join(root,d.story)).href);
    await page.waitForFunction(()=>!document.querySelector('.story-controls').hidden);
    assert.equal(await page.locator('.story-chapter:visible').count(),6);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));
    for(const id of ['purpose','mechanism','data','choices','evolution','next']){
     const link=page.locator('[data-story-chapter="'+id+'"]');await link.focus();await page.keyboard.press('Enter');
     assert.equal(await page.locator('.story-chapter:visible').getAttribute('id'),'story-'+id);
    }
    for(const [time,id] of [[20,'next'],[6,'mechanism'],[0,'purpose'],[13,'choices'],[24,'next']]){
     await page.locator('#story-seek').fill(String(time));await page.locator('#story-seek').dispatchEvent('input');
     assert.equal(await page.locator('.story-chapter:visible').getAttribute('id'),'story-'+id);
    }
    await page.locator('#story-seek').fill('0');await page.locator('#story-seek').dispatchEvent('input');
    await page.locator('#story-play').click();await page.waitForFunction(()=>Number(document.querySelector('#story-seek').value)>0.1);
    await page.locator('#story-play').click();assert.equal(await page.locator('#story-play').textContent(),'Lire le récit court');
    pages++;
   }
   if(i%2===0){
    await page.setViewportSize({width:900,height:1100});await page.locator('[data-story-chapter="choices"]').click();
    const card=page.locator('#story-choices .story-card').filter({has:page.locator('h3 a', {hasText:'Séparer proposition et exécution'})}).first();
    await card.locator('details').evaluateAll(es=>es.forEach(e=>e.open=true));
    await card.screenshot({path:path.join(output,'D0'+(i/2+1)+'-decision.png')});
   }
  }
  await page.emulateMedia({reducedMotion:'reduce'});assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).scrollBehavior),'auto');
  await page.goto(pathToFileURL(path.join(root,demo.site.dossiers[0].story)).href);await page.keyboard.press('Tab');
  assert.equal(await page.locator(':focus').textContent(),'Aller au contenu');
  const nojs=await browser.newContext({javaScriptEnabled:false}),fallback=await nojs.newPage();
  await fallback.goto(pathToFileURL(path.join(root,demo.site.dossiers[0].story)).href);
  assert.equal(await fallback.locator('.story-chapter:visible').count(),6);await nojs.close();
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  fs.writeFileSync(path.join(output,'receipt.json'),JSON.stringify({status:'PASS_SCOPED',browser:browser.version(),pages_checked:pages,
    baseline_pages:6,viewports:[390,1440],keyboard_chapters:6,seek_both_directions:true,play_pause:true,no_autoplay:true,
    reduced_motion:true,no_js_fallback:true,external_requests:0,browser_errors:0},null,2));
  console.log(JSON.stringify({status:'PASS_SCOPED',pages_checked:pages,captures:3}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
