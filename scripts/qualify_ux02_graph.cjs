/* Inspect only generated fictional AIR files in an isolated Edge instance.
   node scripts/qualify_ux02_graph.cjs site-demo.json output edge.exe playwright-directory */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url'),{chromium}=require(process.argv[5]||'playwright');
const demo=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),root=path.dirname(demo.entrypoint),output=path.resolve(process.argv[3]);
fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:process.argv[4],headless:true});
 const context=await browser.newContext(),page=await context.newPage(),checks=[],errors=[],requests=[];
 page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});
 const settled=async()=>page.waitForFunction(()=>document.getElementById('graph-canvas').dataset.cameraMotion==='idle');
 try{
  for(const width of [320,390,768,1440]){
   await page.setViewportSize({width,height:1000});
   for(const dossier of demo.site.dossiers){
    await page.goto(pathToFileURL(path.join(root,dossier.graph)).href);
    await page.waitForFunction(()=>document.getElementById('graph-canvas').dataset.graphReady==='true');
    const folder=path.dirname(dossier.path),graph=JSON.parse(fs.readFileSync(path.join(root,folder,'graph.json'),'utf8'));
    assert.deepEqual(await page.locator('#air-graph').evaluate(e=>JSON.parse(e.textContent).graph),graph);
    const initial={selected:await page.locator('#graph-object').inputValue(),
      nodes:Number(await page.locator('#graph-canvas').getAttribute('data-visible-nodes')),
      canvas_y:(await page.locator('#graph-canvas').boundingBox()).y,
      title_y:(await page.locator('h1').boundingBox()).y};
    await page.screenshot({path:path.join(output,width+'-'+dossier.namespace+'-initial.png')});
    assert.ok(initial.canvas_y<740,'The map must be visible before the first fold: '+JSON.stringify(initial));
    assert.ok(initial.title_y<400);
    assert.equal(await page.locator('#graph-filters').evaluate(e=>e.open),false);
    assert.ok(initial.nodes>0&&initial.nodes<graph.nodes.length,'The initial reading is a real subset');
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));
    for(const preset of ['business','solution','data','delivery']){
     await page.locator('[data-graph-preset='+preset+']').focus();await page.keyboard.press('Enter');
     assert.equal(await page.locator('[data-graph-preset][aria-pressed=true]').getAttribute('data-graph-preset'),preset);
     assert.ok(Number(await page.locator('#graph-canvas').getAttribute('data-visible-nodes'))>0);
    }
    await page.locator('[data-graph-preset=solution]').click();
    const edgeLocator=page.locator('.graph-edge[data-edge]').first();
    assert.ok(await edgeLocator.count(),'The fixture must expose a real declared relation');
    const edgeId=await edgeLocator.getAttribute('data-edge'),edge=graph.edges.find(e=>e.id===edgeId);
    await edgeLocator.focus();await page.keyboard.press('Enter');
    assert.equal(await page.locator(':focus').getAttribute('data-reading-step'),'0');
    for(const step of [0,1,2,1,0]){
     await page.locator('[data-reading-step="'+step+'"]').focus();await page.keyboard.press('Enter');
     await settled();assert.equal(await page.locator(':focus').getAttribute('data-reading-step'),String(step));
     assert.equal(await page.locator('[data-reading-step][aria-pressed=true]').getAttribute('data-reading-step'),String(step));
     const caption=await page.locator('#graph-reading-caption').innerText();
     assert.ok(caption.includes(step===1?graph.relation_kinds[edge.kind]:graph.nodes.find(n=>n.id===(step===0?edge.source:edge.target)).name));
     assert.ok((await page.locator('#graph-detail').innerText()).includes(edge.evidence.digest));
    }
    if(width===390||width===1440)await page.screenshot({path:path.join(output,width+'-'+dossier.namespace+'-relation.png'),fullPage:true});
    await page.locator('#graph-filters summary').first().focus();await page.keyboard.press('Enter');
    assert.equal(await page.evaluate(()=>{document.querySelector('[data-graph-zoom=in]').click();return document.getElementById('graph-canvas').dataset.cameraMotion;}),'running');
    await settled();
    await page.locator('#graph-motion').uncheck();
    await page.locator('[data-graph-zoom=in]').click();
    assert.equal(await page.locator('#graph-canvas').getAttribute('data-camera-motion'),'idle');
    await page.locator('#graph-neighbors').uncheck();
    assert.ok(Number(await page.locator('#graph-canvas').getAttribute('data-visible-nodes'))>=initial.nodes);
    await page.locator('#graph-search').fill('zzzz-no-result');
    assert.equal(await page.locator('#graph-canvas').getAttribute('data-visible-nodes'),'0');
    assert.match(await page.locator('#graph-status').innerText(),/Aucun résultat/);
    await page.locator('#graph-reset').click();
    assert.equal(await page.locator('#graph-object').inputValue(),initial.selected);
    const pathOption=await page.locator('#graph-path option').count();
    if(pathOption>1){
     await page.locator('#graph-path').selectOption('0');
     assert.ok(await page.locator('#graph-only-path').isChecked());
     assert.ok(Number(await page.locator('#graph-canvas').getAttribute('data-visible-nodes'))>0);
     assert.match(await page.locator('#graph-path-status').innerText(),/ne prouve pas une chaîne/);
    }
    await page.locator('#graph-reset').click();
    await page.locator('#graph-canvas').focus();await page.keyboard.press('+');await settled();
    const before=await page.locator('#graph-canvas>svg').getAttribute('viewBox');
    await page.keyboard.press('ArrowRight');await settled();
    assert.notEqual(await page.locator('#graph-canvas>svg').getAttribute('viewBox'),before);
    await page.emulateMedia({reducedMotion:'reduce'});
    await page.waitForFunction(()=>document.getElementById('graph-motion').disabled);
    assert.ok(await page.locator('#graph-motion').isDisabled());
    await page.locator('[data-graph-zoom=out]').click();
    assert.equal(await page.locator('#graph-canvas').getAttribute('data-camera-motion'),'idle');
    assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).scrollBehavior),'auto');
    await page.emulateMedia({reducedMotion:'no-preference'});
    await page.waitForFunction(()=>!document.getElementById('graph-motion').disabled);
    assert.equal(await page.locator('#graph-motion').isDisabled(),false);
    checks.push({width,dossier:dossier.namespace,...initial,presets:4,relation_step_reads:5,
      exact_graph_unchanged:true,exact_edge_source:true,keyboard:true,filters:true,reset:true,
      declared_path:pathOption>1,reduced_motion:true,horizontal_overflow:false});
   }
   await page.goto(pathToFileURL(demo.entrypoint).href);
   await page.waitForFunction(()=>document.body.dataset.diagramsReady==='true');
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));
   assert.equal(await page.locator('.dossier').count(),3);
   assert.equal(await page.locator('body').evaluate(e=>getComputedStyle(e).fontSize),'17px');
   await page.screenshot({path:path.join(output,'project-'+width+'.png'),fullPage:true});
  }
  // Direct file reading without JavaScript must retain the complete source list.
  const noJs=await browser.newContext({javaScriptEnabled:false});
  const fallback=await noJs.newPage();await fallback.goto(pathToFileURL(path.join(root,demo.site.dossiers[0].graph)).href);
  assert.ok(await fallback.locator('a[href="graph.json"]').isVisible());
  assert.equal(await fallback.locator('.graph-toolbar').isVisible(),false);
  assert.equal(await fallback.locator('.graph-map').isVisible(),false);
  await noJs.close();
  assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
  const report={status:'PASS_SCOPED',method:'Isolated Edge, generated fictional files',
   checks,widths:[320,390,768,1440],dossiers:3,relation_step_reads:checks.length*5,
   page_errors:errors,external_requests:requests,participants:0,accessibility_certification:false,
   business_execution_performed:false,client_plugin_qualification:false,without_javascript:true};
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify({status:report.status,graph_walkthroughs:checks.length,relation_step_reads:report.relation_step_reads}));
 }finally{await Promise.race([browser.close(),new Promise(resolve=>setTimeout(resolve,10000))]);}
})().then(()=>process.exit(0)).catch(e=>{console.error(e);process.exit(1);});
