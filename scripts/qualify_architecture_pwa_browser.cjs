/* Optional development qualification. Runtime server and export need Python only. */
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const {spawn} = require('node:child_process'), net = require('node:net'), crypto = require('node:crypto');
const {chromium} = require(process.argv[4] || 'playwright');
const demo = JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const output = path.resolve(path.dirname(process.argv[2]),'pwa-browser');
const root = path.join(output,'site');fs.mkdirSync(output,{recursive:true});
fs.cpSync(path.dirname(demo.entrypoint),root,{recursive:true});
const python = path.resolve('.venv/Scripts/python.exe');
const sha = bytes => 'sha256:' + crypto.createHash('sha256').update(bytes).digest('hex');
const delay = ms => new Promise(resolve => setTimeout(resolve,ms));
async function freePort() {
  const probe = net.createServer();await new Promise(resolve=>probe.listen(0,'127.0.0.1',resolve));
  const port=probe.address().port;await new Promise(resolve=>probe.close(resolve));return port;
}
async function start(port) {
  const process = spawn(python,['-m','air.site_server',root,'--port',String(port)],{windowsHide:true,stdio:['ignore','pipe','pipe']});
  await new Promise((resolve,reject)=>{
    const timeout=setTimeout(()=>reject(new Error('Static server startup timed out')),15000);
    process.once('error',reject);process.once('exit',code=>reject(new Error('Static server exited '+code)));
    process.stdout.once('data',()=>{clearTimeout(timeout);resolve();});
  });return process;
}
async function stop(child) {
  if (!child || child.exitCode !== null) return;
  // The Windows venv launcher owns a Python child which can retain the pipes.
  // Stop only this test-created process tree, never an independently found PID.
  if (process.platform === 'win32') {
    await new Promise(resolve=>{const task=spawn('taskkill.exe',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});task.once('exit',resolve);task.once('error',resolve);});
  } else { await new Promise(resolve=>{child.once('exit',resolve);child.kill();}); }
}
function newGeneration(comment) {
  const entry=path.join(root,'index.html');
  fs.writeFileSync(entry,fs.readFileSync(entry,'utf8').replace('</main>','<!-- '+comment+' --></main>'));
  const manifestPath=path.join(root,'site-manifest.json');
  const manifest=JSON.parse(fs.readFileSync(manifestPath,'utf8'));
  for (const item of manifest.pwa.resources) item.digest=sha(fs.readFileSync(path.join(root,item.path)));
  // RFC 8785 ordering here contains only ASCII keys/paths and digest strings.
  const template=fs.readFileSync('src/air/assets/architecture-worker.js','utf8');
  manifest.pwa.worker_template_digest=sha(template);
  manifest.pwa.version=sha(JSON.stringify({engine:manifest.pwa.engine,
    resources:manifest.pwa.resources.map(x=>({digest:x.digest,media_type:x.media_type,path:x.path})),
    worker_template_digest:manifest.pwa.worker_template_digest}));
  const worker=template.replace('__AIR_RESOURCE_LIST__',JSON.stringify(manifest.pwa.resources)).replace('__AIR_VERSION__',JSON.stringify(manifest.pwa.version));
  fs.writeFileSync(path.join(root,'sw.js'),worker);manifest.pwa.worker_digest=sha(worker);
  fs.writeFileSync(manifestPath,JSON.stringify(manifest));return manifest.pwa.version;
}
(async()=>{
  const port=await freePort(), origin='http://127.0.0.1:'+port;
  let server=await start(port);
  // An isolated persistent test profile avoids incognito's installation ban.
  const context=await chromium.launchPersistentContext(path.join(output,'profile-'+Date.now()),
    {executablePath:process.argv[3],headless:true,viewport:{width:1440,height:1000}});
  const browser=context.browser(), page=await context.newPage();
  const errors=[],remote=[];page.on('pageerror',e=>errors.push(String(e)));
  context.on('request',r=>{if (/^https?:/.test(r.url()) && !r.url().startsWith(origin+'/')) remote.push(r.url());});
  const openMenu=async()=>{await page.locator('.app-menu').evaluate(e=>e.open=true);};
  try {
    await page.goto(origin+'/index.html');await page.waitForSelector('link[rel=manifest]',{state:'attached'});
    assert.equal(await page.evaluate(async()=> (await navigator.serviceWorker.getRegistrations()).length),0);
    assert.equal(await page.evaluate(async()=> (await caches.keys()).length),0);
    const cdp=await context.newCDPSession(page), app=await cdp.send('Page.getAppManifest');
    assert.deepEqual(app.errors,[]);assert.ok(app.data.includes('standalone'));
    await openMenu();await page.click('#pwa-enable');
    await page.waitForFunction(()=>Boolean(navigator.serviceWorker.controller),null,{timeout:90000});
    await page.waitForFunction(()=>document.getElementById('pwa-enable').hidden);
    const original=await page.evaluate(async()=> (await caches.keys()).find(x=>x.startsWith('air-site:')));
    assert.ok(original);
    process.stderr.write('PWA_STAGE_INSTALLED\n');
    const installability=await cdp.send('Page.getInstallabilityErrors');
    assert.deepEqual(installability.installabilityErrors,[],JSON.stringify(installability));
    const cached=await page.evaluate(async name=>(await (await caches.open(name)).keys()).length,original);
    assert.equal(cached,demo.site.pwa.resource_count);
    await context.setOffline(true);
    for (const d of demo.site.dossiers) {
      await page.goto(origin+'/'+d.path);await page.waitForFunction(()=>document.body.dataset.diagramsReady==='true');
      await page.goto(origin+'/'+d.graph);await page.waitForSelector('.graph-node');
      await page.fill('#graph-search','nom totalement absent');
      assert.equal(await page.locator('.graph-node').count(),0);
      if (d.story) {
        await page.goto(origin+'/'+d.story);await page.waitForSelector('.story-controls:not([hidden])');
        await page.locator('[data-story-chapter="mechanism"]').click();
        assert.equal(await page.locator('.story-chapter:visible').getAttribute('id'),'story-mechanism');
      }
      if (d.handoff) {
        await page.goto(origin+'/'+d.handoff);await page.waitForFunction(()=>document.body.dataset.diagramsReady==='true');
        const focus=page.locator('.handoff-list a').first();await focus.click();
        await page.waitForFunction(()=>document.body.dataset.diagramsReady==='true');
        assert.equal(await page.locator('.handoff-section').count(),9);
        assert.equal(await page.locator('.diagram[data-rendered=false]').count(),0);
        assert.ok(await page.locator('#handoff-gaps').isVisible());
      }
      if (d.cooperation) {
        await page.goto(origin+'/'+d.cooperation+'?topic=23&audience=comex');
        await page.waitForSelector('#capsule-download:not([disabled])');
        assert.equal(await page.locator('#capsule-audience').inputValue(),'comex');
        await page.locator('#capsule-question').fill('Quels arbitrages restent à prendre ?');
        await page.waitForFunction(()=>document.getElementById('capsule-prompt').value.includes('Quels arbitrages restent'));
        const request=await page.evaluate(()=>JSON.parse(document.getElementById('capsule-prompt').value.split('\n\n').at(-1)));
        assert.deepEqual(request.capsule.baseline,d.baseline);
        const fallback=await page.evaluate(()=>fetch('question-23.json').then(r=>r.json()));
        assert.deepEqual(fallback.capsule.baseline,d.baseline);
      }
    }
    await page.goto(origin+'/timeline.html');await page.waitForSelector('#temporal-interactive:not([hidden])');
    await page.goto(origin+'/architecture-model.json');
    assert.ok((await page.locator('body').textContent()).includes('snapshots'));
    await page.goto(origin+'/');assert.ok(await page.locator('.dossier').count());
    await context.setOffline(false);
    process.stderr.write('PWA_STAGE_OFFLINE_READ\n');
    await stop(server);const changed=newGeneration('QUALIFIED_NEW_GENERATION');server=await start(port);
    await page.goto(origin+'/index.html');await openMenu();
    await page.waitForSelector('#pwa-update:not([hidden])',{timeout:90000});
    assert.ok(!(await page.content()).includes('QUALIFIED_NEW_GENERATION'));
    await page.click('#pwa-update');await page.waitForFunction(()=>document.documentElement.outerHTML.includes('QUALIFIED_NEW_GENERATION'));
    const upgraded=await page.evaluate(async()=>await caches.keys());
    assert.ok(upgraded.includes('air-site:%2F:'+changed));assert.ok(!upgraded.includes(original));
    process.stderr.write('PWA_STAGE_UPGRADED\n');
    // A corrupt next-generation file must not supersede the complete snapshot.
    await stop(server);newGeneration('INCOMPLETE_GENERATION');server=await start(port);
    fs.appendFileSync(path.join(root,'assets/site.css'),'\n/* modified after pinning */');
    await page.goto(origin+'/index.html');await openMenu();
    process.stderr.write('PWA_STAGE_CORRUPT_UPDATE_REQUESTED\n');
    await page.waitForFunction(()=>/échoué|incomplète/.test(document.getElementById('pwa-status').textContent),null,{timeout:90000});
    assert.equal(await page.evaluate(async()=> (await caches.keys()).filter(x=>x.startsWith('air-site:%2F:')).length),1);
    assert.equal(await page.locator('#pwa-update').isVisible(),false);
    await context.setOffline(true);await page.goto(origin+'/index.html');
    assert.ok((await page.content()).includes('QUALIFIED_NEW_GENERATION'));
    assert.ok(!(await page.content()).includes('INCOMPLETE_GENERATION'));
    await page.evaluate(async()=> {const other=await caches.open('air-site:%2Fother%2F:test');await other.put('/other/marker',new Response('other'));});
    await openMenu();await page.click('#pwa-clear');
    await page.waitForFunction(()=>document.getElementById('pwa-status').textContent.includes('effacée'));
    assert.deepEqual(await page.evaluate(async()=>await caches.keys()),['air-site:%2Fother%2F:test']);
    assert.equal(await page.evaluate(async()=> (await navigator.serviceWorker.getRegistrations()).length),0);
    process.stderr.write('PWA_STAGE_CLEARED\n');
    assert.deepEqual(errors,[]);assert.deepEqual(remote,[]);
    const receipt={status:'PASS_SCOPED',browser:browser.version(),resources:cached,
      opt_in_only:true,manifest_installability_errors:[],svg_icons_accepted:true,
      offline_dossiers:demo.site.dossiers.length,offline_graphs:true,offline_timeline:true,offline_model:true,
      offline_stories:demo.site.dossiers.filter(d=>d.story).length,
      offline_handoff_dossiers:demo.site.dossiers.filter(d=>d.handoff).length,
      offline_cooperation_dossiers:demo.site.dossiers.filter(d=>d.cooperation).length,
      explicit_upgrade:true,failed_upgrade_preserves_snapshot:true,scope_cache_clear:true,
      other_scope_cache_preserved:true,remote_requests:0,page_errors:[],os_installation_exercised:false};
    fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(receipt,null,2)+'\n');
    process.stdout.write(JSON.stringify(receipt)+'\n');
  } finally {await stop(server);await Promise.race([browser.close(),delay(10000)]);}
  process.exit(0);
})().catch(error=>{process.stderr.write(String(error.stack)+'\n');process.exit(1);});
