/* Optional isolated browser receipt, never a native ChatGPT or user research receipt. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url'),{createHash}=require('node:crypto');
const [rootArg,outArg,exe,pw]=process.argv.slice(2),root=path.resolve(rootArg),out=path.resolve(outArg);
const {chromium}=require(pw);
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const manifest=JSON.parse(fs.readFileSync(path.join(root,'site-manifest.json'),'utf8'));
 const pages=manifest.dossiers.flatMap(d=>{
  const catalog=JSON.parse(fs.readFileSync(path.join(root,d.journeys_data),'utf8'));
  return catalog.journeys.map(j=>({j,file:path.posix.join(path.posix.dirname(d.path),'journey-map-n'+createHash('sha256').update(j.reference.id+':'+j.reference.revision).digest('hex').slice(0,12)+'.html')}));
 });
 const browser=await chromium.launch({executablePath:exe,headless:true});
 const context=await browser.newContext({reducedMotion:'reduce'}),page=await context.newPage(),errors=[],remote=[],checks=[];
 page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>{if(/^https?:/.test(r.url()))remote.push(r.url());});
 let tourChecked=false,actorChecked=false;
 try{
  for(const width of [320,390,768,1440]){
   await page.setViewportSize({width,height:1100});
   for(const {j,file} of pages){
    await page.goto(pathToFileURL(path.join(root,file)).href);
    const map=page.locator('[data-journey-visual]');await page.waitForFunction(()=>document.querySelector('[data-journey-visual]')?.dataset.journeyReady==='true');
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),file+' document overflow');
    const ids=await page.locator('[id]').evaluateAll(es=>es.map(e=>e.id));assert.equal(ids.length,new Set(ids).size);
    const nodes=map.locator('.jv-svg [data-jv-step]');assert.equal(await nodes.count(),j.steps.length);
    const last=j.steps.length-1;
    await nodes.nth(last).click();assert.equal(await map.getAttribute('data-selected-step'),String(last));
    assert.equal(await map.locator('.jv-step-detail[open]').count(),1);
    assert.ok((await map.locator('.jv-step-detail[open]').textContent()).includes(j.steps[last].selector));
    await nodes.nth(last).focus();await page.keyboard.press('Home');assert.equal(await map.getAttribute('data-selected-step'),'0');
    await page.keyboard.press('ArrowRight');assert.equal(await map.getAttribute('data-selected-step'),String(Math.min(1,last)));
    const options=await map.locator('[data-jv-actor] option').evaluateAll(es=>es.map(e=>({value:e.value,text:e.textContent})));
    const subset=options.find(o=>o.value && o.value.split(',').length<j.steps.length);
    if(subset){
     await map.locator('[data-jv-actor]').selectOption(subset.value);
     assert.ok(subset.value.split(',').includes(await map.getAttribute('data-selected-step')));
     assert.equal(await map.locator('.jv-svg a.is-muted').count(),j.steps.length-subset.value.split(',').length);
     await map.locator('[data-jv-actor]').selectOption('');actorChecked=true;
    }
    await map.locator('[data-jv-layer]').selectOption('systems');assert.equal(await map.getAttribute('data-layer'),'systems');
    assert.equal(await map.locator('.jv-actors-part').first().evaluate(e=>getComputedStyle(e).opacity),'0.16');
    await map.locator('[data-jv-layer]').selectOption('all');
    await map.locator('[data-jv-action="fit"]').click();
    const fit=await map.locator('svg').evaluate(e=>e.getBoundingClientRect().width);
    await map.locator('[data-jv-action="zoom"]').click();assert.ok(await map.locator('svg').evaluate(e=>e.getBoundingClientRect().width)>fit);
    await map.locator('[data-jv-action="reduce"]').click();
    if(!tourChecked && j.steps.length>1){
     await page.clock.install();await map.locator('[data-jv-action="tour"]').click();await page.clock.fastForward(4100);
     assert.equal(await map.getAttribute('data-selected-step'),'1');
     await map.locator('[data-jv-action="tour"]').click();await page.clock.fastForward(4100);
     assert.equal(await map.getAttribute('data-selected-step'),'1');tourChecked=true;
    }
    await nodes.first().click();await map.locator('[data-jv-action="read"]').click();
    assert.equal(await map.locator('.jv-svg a').first().evaluate(e=>getComputedStyle(e).transitionDuration),'0s');
    if([390,1440].includes(width)){
     await map.locator('.jv-viewport').screenshot({path:path.join(out,path.basename(file,'.html')+'-'+width+'.png')});
    }
    checks.push({file,width,steps:j.steps.length,selection:true,keyboard:true,zoom:true,layers:true});
   }
  }
  const plain=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:1100}}),nojs=await plain.newPage();
  for(const {file,j} of pages){
   await nojs.goto(pathToFileURL(path.join(root,file)).href);
   assert.equal(await nojs.locator('[data-jv-toolbar]').isVisible(),false);
   assert.ok(await nojs.locator('.jv-svg').isVisible());
   if(j.steps.length>1)await nojs.locator('.jv-step-detail > summary').last().click();
   assert.equal(await nojs.locator('.jv-step-detail').last().getAttribute('open'),'');
   assert.equal(await nojs.locator('.jv-step-detail').count(),j.steps.length);
  }
  await plain.close();
  const normal=await browser.newContext({reducedMotion:'no-preference',viewport:{width:390,height:1100}}),moving=await normal.newPage();
  moving.on('pageerror',e=>errors.push(String(e)));moving.on('request',r=>{if(/^https?:/.test(r.url()))remote.push(r.url());});
  await moving.goto(pathToFileURL(path.join(root,pages[0].file)).href);
  await moving.waitForFunction(()=>document.querySelector('[data-journey-visual]')?.dataset.journeyReady==='true');
  await moving.locator('.jv-svg [data-jv-step]').last().click();
  assert.equal(await moving.locator('[data-journey-visual]').getAttribute('data-selected-step'),String(pages[0].j.steps.length-1));
  await moving.waitForFunction(()=>{
   const root=document.querySelector('[data-journey-visual]'),view=root.querySelector('.jv-viewport').getBoundingClientRect(),
    card=root.querySelector('.jv-svg a.is-selected .jv-card').getBoundingClientRect();
   return card.left>=view.left-3 && card.right<=view.right+3;
  });
  await normal.close();assert.deepEqual(errors,[]);assert.deepEqual(remote,[]);assert.ok(tourChecked);
  const report={status:'PASS_SCOPED',scope:'LOCAL_BROWSER_NOT_NATIVE_CLIENT_OR_USER_RESEARCH',checks,no_js:true,
   guided_tour_start_advance_stop:true,actor_filter_subset_exercised:actorChecked,reduced_motion:true,normal_motion_selection:true,remote_requests:0};
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2)+'\n');
  process.stdout.write(JSON.stringify({status:report.status,views:checks.length,actor_filter:actorChecked})+'\n');
 }finally{await browser.close();}
})().catch(e=>{process.stderr.write(String(e.stack)+'\n');process.exitCode=1;});
