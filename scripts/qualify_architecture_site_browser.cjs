/* Optional development qualification; not a runtime or installation dependency. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {pathToFileURL} = require('node:url');
const {chromium} = require(process.argv[4] || 'playwright');
const report = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const entrypoint = report.entrypoint;
const root = path.dirname(entrypoint);
const output = path.resolve(path.dirname(process.argv[2]),'browser');
fs.mkdirSync(output,{recursive:true});
function htmlFiles(directory) {
  return fs.readdirSync(directory,{withFileTypes:true}).flatMap(e => e.isDirectory() ? htmlFiles(path.join(directory,e.name)) : e.name.endsWith('.html') ? [path.join(directory,e.name)] : []);
}
(async () => {
  const browser = await chromium.launch({executablePath:process.argv[3],headless:true});
  const context = await browser.newContext({viewport:{width:1440,height:1000}});
  const page = await context.newPage(), requests = [], errors = [];
  page.on('request',r => { if (/^https?:/.test(r.url())) requests.push(r.url()); });
  page.on('pageerror',e => errors.push(String(e)));
  await page.route(/^https?:/,route => route.abort());
  const results = [];
  try {
    await page.goto(pathToFileURL(entrypoint).href);
    assert.equal(await page.locator('.dossier').count(),report.site.dossiers.length);
    await page.screenshot({path:path.join(output,'project.png'),fullPage:true});
    await page.fill('#dossier-search','nom totalement absent');
    assert.equal(await page.locator('.dossier:visible').count(),0);
    await page.fill('#dossier-search','maintenance');
    assert.equal(await page.locator('.dossier:visible').count(),report.site.dossiers.filter(d=>d.name.toLocaleLowerCase().includes('maintenance')).length);
    await page.fill('#dossier-search','');
    for (const file of htmlFiles(root)) {
      await page.goto(pathToFileURL(file).href);
      await page.waitForFunction(() => document.body.dataset.diagramsReady === 'true');
      const diagrams = await page.locator('.diagram').count();
      const failed = await page.locator('.diagram[data-rendered=false]').count();
      assert.equal(failed,0,'Failed diagram in '+file);
      assert.equal(await page.locator('.diagram-canvas svg').count(),diagrams);
      const links = await page.locator('a[href]').evaluateAll(nodes => nodes.map(a => a.getAttribute('href')));
      for (const href of links) {
        const [target,fragment] = href.split('#');
        const actual = target ? path.resolve(path.dirname(file),target) : file;
        assert.ok(fs.existsSync(actual),'Broken link '+href+' in '+file);
        if (fragment) assert.ok(fs.readFileSync(actual,'utf8').includes('id="'+fragment+'"'),'Broken anchor '+href);
      }
      if (diagrams) {
        const svg = page.locator('.diagram-canvas svg').first();
        const before = await svg.evaluate(e => e.style.width);
        await page.locator('[data-zoom=in]').first().click();
        assert.notEqual(await svg.evaluate(e => e.style.width),before);
        await page.locator('[data-zoom=reset]').first().click();
      }
      results.push({page:path.relative(root,file).replaceAll('\\','/'),diagrams,rendered:diagrams});
    }
    for (const dossier of report.site.dossiers) {
      const directory = path.dirname(path.join(root,dossier.path));
      await page.goto(pathToFileURL(path.join(directory,'19-modele-logique.html')).href);
      await page.waitForFunction(() => document.body.dataset.diagramsReady === 'true');
      assert.ok(await page.locator('svg .air-linked').count()>0,'Entity definitions must be reachable from the diagram');
      await page.screenshot({path:path.join(output,dossier.namespace+'-logical.png'),fullPage:true});
      const linked = page.locator('svg .air-linked').first();
      await linked.focus();await page.keyboard.press('Enter');
      await page.waitForURL(/objects\.html#/);
      assert.equal(await page.locator('.object:target').evaluate(e=>e.open),true);
      await page.goto(pathToFileURL(path.join(directory,'objects.html')).href);
      await page.fill('#object-search','nom inexistant');assert.equal(await page.locator('.object:visible').count(),0);
      await page.fill('#object-search','');
      const id = await page.locator('.object').first().getAttribute('id');
      await page.goto(pathToFileURL(path.join(directory,'objects.html')).href+'#'+id);
      assert.equal(await page.locator('#'+id).evaluate(e=>e.open),true);
      await page.goto(pathToFileURL(path.join(directory,'25-adr.html')).href);
      await page.screenshot({path:path.join(output,dossier.namespace+'-decisions.png'),fullPage:true});
      await page.goto(pathToFileURL(path.join(directory,'business-paths.html')).href);
      await page.fill('#path-search','nom inexistant');assert.equal(await page.locator('.business-path:visible').count(),0);
      await page.fill('#path-search','');
      const paths = page.locator('.business-path');
      if (await paths.count()) {
        await paths.first().locator('a').click();
        assert.ok((await page.locator('main').textContent()).includes('ne prouvent pas une chaîne'));
        await page.screenshot({path:path.join(output,dossier.namespace+'-path.png'),fullPage:true});
      }
      await page.goto(pathToFileURL(path.join(directory,'graph.html')).href);
      await page.waitForFunction(()=>document.getElementById('graph-canvas').dataset.graphReady==='true');
      assert.ok(await page.locator('#graph-canvas [data-node]').count()>0);
      const initialScale=await page.locator('#graph-canvas svg').evaluate(el=>el.getBoundingClientRect().width/el.viewBox.baseVal.width);
      assert.ok(initialScale>=0.9,'Initial camera must retain readable labels');
      const miniature=page.locator('#graph-overview svg'),miniBefore=await page.locator('#graph-canvas svg').getAttribute('viewBox');
      await miniature.click({position:{x:15,y:15}});
      assert.notEqual(await page.locator('#graph-canvas svg').getAttribute('viewBox'),miniBefore,'Overview must navigate the camera');
      await page.click('#graph-reset');
      await page.screenshot({path:path.join(output,dossier.namespace+'-graph-overview.png'),fullPage:true});
      const graph=await page.evaluate(()=>JSON.parse(document.getElementById('air-graph').textContent).graph);
      await page.fill('#graph-search','nom totalement absent');assert.equal(await page.locator('#graph-canvas [data-node]').count(),0);
      await page.fill('#graph-search','');
      await page.selectOption('#graph-type','air.RuntimeComponent');
      const shownTypes=await page.locator('#graph-canvas [data-node]').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('aria-label')));
      assert.ok(shownTypes.length>0&&shownTypes.every(text=>text.includes('(RuntimeComponent,')));
      await page.selectOption('#graph-type','');
      const workflow=graph.nodes.find(n=>n.type==='air.Workflow'&&!n.local_step);
      await page.selectOption('#graph-object',workflow.id);
      assert.equal(await page.locator('#graph-detail h2').textContent(),workflow.name);
      const all=await page.locator('#graph-canvas [data-node]').count();
      await page.check('#graph-neighbors');
      assert.ok(await page.locator('#graph-canvas [data-node]').count()<=all);
      await page.uncheck('#graph-neighbors');
      await page.selectOption('#graph-path','0');await page.check('#graph-only-path');
      assert.ok(await page.locator('#graph-canvas .graph-node.path-member').count()>0);
      assert.ok((await page.locator('#graph-path-status').textContent()).includes('ne prouve pas'));
      assert.equal(await page.locator('#graph-canvas .graph-node:not(.path-member)').count(),0);
      await page.uncheck('#graph-only-path');
      const svg=page.locator('#graph-canvas svg'),before=await svg.getAttribute('viewBox');
      await page.click('[data-graph-zoom=in]');assert.notEqual(await svg.getAttribute('viewBox'),before);
      await page.locator('#graph-canvas').focus();await page.keyboard.press('ArrowRight');
      const panned=await svg.getAttribute('viewBox');assert.notEqual(panned,before);
      await page.click('[data-graph-zoom=fit]');
      const bounds=await page.locator('#graph-canvas').boundingBox();
      const panBefore=await svg.getAttribute('viewBox');
      await page.mouse.move(bounds.x+12,bounds.y+bounds.height-12);await page.mouse.down();
      await page.mouse.move(bounds.x+65,bounds.y+bounds.height-25);await page.mouse.up();
      assert.notEqual(await svg.getAttribute('viewBox'),panBefore,'Pointer pan must change the camera');
      await page.click('#graph-reset');
      const edge=page.locator('#graph-canvas .graph-edge').first();await edge.focus();await page.keyboard.press('Enter');
      assert.ok((await page.locator('#graph-detail').textContent()).includes('Empreinte'));
      assert.ok((await page.locator('#graph-detail a').getAttribute('href')).startsWith('objects.html#'));
      await page.click('#graph-reset');await page.selectOption('#graph-object',workflow.id);
      await page.click('#graph-center');
      const centeredBox=await page.locator('#graph-canvas svg').getAttribute('viewBox');
      await page.locator('#graph-canvas .node-selected').focus();await page.keyboard.press('Enter');
      assert.equal(await page.locator('#graph-canvas svg').getAttribute('viewBox'),centeredBox,'Selecting the same object must preserve the camera');
      assert.ok((await page.locator(':focus').getAttribute('href')).startsWith('objects.html#'));
      await page.screenshot({path:path.join(output,dossier.namespace+'-graph.png'),fullPage:true});
      await page.setViewportSize({width:390,height:844});
      await page.waitForFunction(()=>document.getElementById('graph-canvas').clientWidth/ document.querySelector('#graph-canvas svg').viewBox.baseVal.width>=0.85);
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2));
      await page.screenshot({path:path.join(output,dossier.namespace+'-graph-mobile.png'),fullPage:true});
      await page.setViewportSize({width:1440,height:1000});
    }
    await page.goto(pathToFileURL(path.join(root,'timeline.html')).href);
    await page.waitForFunction(()=>document.getElementById('temporal-interactive').dataset.ready==='true');
    const temporal=await page.evaluate(()=>JSON.parse(document.getElementById('air-temporal').textContent).temporal);
    assert.equal(await page.locator('#temporal-snapshot option').count(),report.site.dossiers.length);
    assert.equal(temporal.registry_knowledge_history_available,false);
    for(let i=0;i<temporal.comparisons.length;i++){
      await page.selectOption('#temporal-comparison',String(i));
      const c=temporal.comparisons[i];
      await page.selectOption('#temporal-kind','ALL');assert.equal(await page.locator('[data-temporal-change]').count(),Math.min(150,c.objects.length));
      await page.selectOption('#temporal-kind','CONTENT');assert.equal(await page.locator('[data-temporal-change]').count(),Math.min(150,c.summary.CONTENT));
      await page.fill('#temporal-search','nom totalement absent');assert.equal(await page.locator('[data-temporal-change]').count(),0);
      await page.fill('#temporal-search','');
      const change=page.locator('[data-temporal-change=CONTENT] button').first();
      if(await change.count()){
        await change.focus();await page.keyboard.press('Enter');
        assert.ok((await page.locator('#temporal-detail').textContent()).includes('Empreinte'));
        assert.ok((await page.locator('#temporal-detail').textContent()).includes('champ(s) différent(s)'));
        assert.ok((await page.locator(':focus').getAttribute('href')).includes('objects.html#'));
      }
    }
    for(let i=0;i<temporal.snapshots.length;i++){
      await page.selectOption('#temporal-snapshot',String(i));const s=temporal.snapshots[i];
      for(let j=0;j<s.validity_boundaries.length;j++){
        await page.selectOption('#temporal-boundary',String(j));const t=s.validity_boundaries[j];
        const expected=s.objects.filter(o=>o.valid_start<=t&&(o.valid_end===null||t<o.valid_end)).slice(0,150).map(o=>o.reference.id);
        assert.deepEqual(await page.locator('[data-valid-object]').evaluateAll(nodes=>nodes.map(n=>n.dataset.validObject)),expected,'Half-open validity boundary '+t);
        assert.equal(await page.locator('#temporal-slider').inputValue(),String(j));
      }
      await page.locator('#temporal-slider').focus();await page.keyboard.press('Home');
      assert.equal(await page.locator('#temporal-boundary').inputValue(),'0');
      if(s.validity_boundaries.length>1){await page.keyboard.press('ArrowRight');assert.equal(await page.locator('#temporal-boundary').inputValue(),'1');}
    }
    if(temporal.comparisons.length){await page.selectOption('#temporal-comparison','0');await page.selectOption('#temporal-kind','CHANGED');}
    await page.screenshot({path:path.join(output,'temporal.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2));
    await page.screenshot({path:path.join(output,'temporal-mobile.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await page.goto(pathToFileURL(entrypoint).href);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2));
    await page.screenshot({path:path.join(output,'mobile.png'),fullPage:true});
    await page.keyboard.press('Tab');assert.equal(await page.locator(':focus').textContent(),'Aller au contenu');
    assert.equal(requests.length,0,'The site must make no network request');
    assert.deepEqual(errors,[]);
    const receipt = {status:'PASS_SCOPED',browser:browser.version(),pages:results.length,diagram_instances:results.reduce((n,r)=>n+r.diagrams,0),
      network_requests:0,page_errors:[],search:true,path_search:true,graph_filters:true,graph_path_highlight:true,
      graph_neighbors:true,graph_source_panel:true,graph_keyboard:true,graph_pointer_pan:true,graph_mobile:true,
      graph_overview_navigation:true,graph_readable_initial_camera:true,graph_camera_preserved_on_selection:true,
      temporal_comparisons:temporal.comparisons.length,temporal_filters:true,temporal_sources:true,
      temporal_half_open_boundaries:true,temporal_slider_keyboard:true,temporal_mobile:true,
      zoom:true,mobile:true,keyboard:true,links:true,results};
    fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(receipt,null,2)+'\n');
    process.stdout.write(JSON.stringify({...receipt,results:undefined})+'\n');
  } finally {
    // Edge can retain its pipe after closing on Windows. The receipt above is
    // written only after every assertion; bound helper teardown separately.
    await Promise.race([browser.close(),new Promise(resolve=>setTimeout(resolve,10000))]);
  }
  process.exit(0);
})();
