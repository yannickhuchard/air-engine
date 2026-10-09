/* Optional UI qualification: Node + Playwright + an installed Chromium browser.
   Neither Node nor Playwright is required to install or use AIR. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {pathToFileURL} = require('node:url');
const root = path.resolve(__dirname, '..');
const scratch = fs.mkdtempSync(path.join(root, 'tmp', 'workbench-browser-'));
process.env.TEMP = process.env.TMP = scratch;
const {chromium} = require(process.argv[4] || 'playwright');
const report = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
(async () => {
  const context = await chromium.launchPersistentContext(path.join(scratch, 'profile'), {executablePath:process.argv[3],headless:true,args:["--disk-cache-dir=" + path.join(scratch,"cache"),"--crash-dumps-dir=" + path.join(scratch,"crashes")],acceptDownloads:true,downloadsPath:scratch,viewport:{width:1440,height:1050}});
  const results = [];
  const browserVersion = context.browser().version();
  try {
    for (const dossier of report.treatments) {
      const page = await context.newPage(), errors = [], requests = [];
      page.on('pageerror', e => errors.push(String(e)));
      page.on('request', r => { if (/^https?:/.test(r.url())) requests.push(r.url()); });
      await page.route(/^https?:/, route => route.abort());
      await page.goto(pathToFileURL(dossier.workbench.path).href);
      await page.waitForFunction(() => document.getElementById('js-status').textContent === 'Consultation hors ligne prête');
      const data = await page.locator('#air-data').textContent().then(JSON.parse);
      assert.equal(data.objects.length, dossier.workbench.objects);
      const targetKind = data.objects.some(o => o.meta.type === 'air.Conflict') ? 'air.Conflict' : (data.objects.some(o => o.meta.type === 'air.Goal') ? 'air.Goal' : 'air.Decision');
      await page.fill('#search','aucun-objet-ne-porte-ce-nom-unique');
      assert.equal(await page.locator('#object-list button').count(), 0);
      assert.equal(await page.locator('#empty-results').isVisible(), true);
      await page.fill('#search','');await page.selectOption('#type-filter',targetKind);
      assert.equal(await page.locator('#object-list button').count(), 1);
      await page.locator('#object-list button').click();
      const title = await page.locator('#object-title').textContent();
      assert.equal(title,data.objects.find(o => o.meta.type === targetKind).meta.name);
      if (targetKind === 'air.Conflict') assert.match(await page.locator('#properties').textContent(),/Une décision documentée ne prouve pas sa résolution/);
      await page.keyboard.press('Tab');
      assert.equal(await page.evaluate(() => document.activeElement.id),'prepare-contribution');
      const linked = await page.locator('#outgoing button.reference').first().textContent();
      await page.locator('#outgoing button.reference').first().click();
      assert.equal(await page.locator('#object-title').textContent(),linked);
      await page.locator('#object-list button').click();
      await page.click('#prepare-contribution');
      assert.equal(await page.evaluate(() => document.activeElement.id),'contribution-title');
      await page.fill('#contribution-title','Question de recette navigateur');
      const message = 'Comment vérifier ce traitement ? <script>window.airInjected=true</script>';
      await page.fill('#contribution-message',message);
      const [download] = await Promise.all([page.waitForEvent('download'),page.click('#contribution-form button[type=submit]')]);
      const output = path.join(scratch,dossier.case + '-contribution.json');try { await download.saveAs(output); } catch (e) { throw new Error(dossier.case + ' download: ' + await download.failure()); }
      const submission = JSON.parse(fs.readFileSync(output,'utf8'));
      assert.equal(submission.object.body.message,message);assert.equal(submission.object.body.author,data.identity);
      assert.equal(submission.object.meta.provenance.recorded_by,data.identity);
      assert.equal(submission.object.body.target[0].id,data.objects.find(o => o.meta.type === targetKind).meta.id);
      assert.equal(await page.evaluate(() => window.airInjected),undefined);
      const [again] = await Promise.all([page.waitForEvent('download'),page.click('#contribution-form button[type=submit]')]);
      const second = path.join(scratch,dossier.case + '-again.json');await again.saveAs(second);
      assert.deepEqual(JSON.parse(fs.readFileSync(second,'utf8')),submission);
      const desktop = path.join(path.dirname(dossier.workbench.path),dossier.case + '-desktop.png');await page.screenshot({path:desktop,fullPage:true});
      await page.setViewportSize({width:390,height:844});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),true);
      const mobile = path.join(path.dirname(dossier.workbench.path),dossier.case + '-mobile.png');await page.screenshot({path:mobile,fullPage:true});
      const csp = await page.evaluate(async () => {
        const directives = [];document.addEventListener('securitypolicyviolation', event => directives.push(event.effectiveDirective));
        try { await fetch('http://127.0.0.1:9/workbench-network-must-be-blocked'); } catch {}
        await new Promise(resolve => setTimeout(resolve,100));return directives;
      });
      assert.ok(csp.includes('connect-src'));assert.deepEqual(requests,[]);assert.deepEqual(errors,[]);
      results.push({case:dossier.case,prepared_target_type:targetKind,source_content_digest:dossier.workbench.content_digest,search:true,type_filter:true,reference_navigation:true,keyboard_focus:true,mobile_no_horizontal_overflow:true,
        prepared_submission:output,repeated_download_identical:true,script_text_inert:true,network_blocked_by_csp:true,http_requests:requests.length,desktop,mobile});
      await page.close();
    }
    const hostilePath = path.join(root,'tmp/demo-asteria/workbench/hostile.html');
    if (fs.existsSync(hostilePath)) {
      const page = await context.newPage(), requests = [];
      page.on('request', r => { if (/^https?:/.test(r.url())) requests.push(r.url()); });
      await page.route(/^https?:/, route => route.abort());
      await page.goto(pathToFileURL(hostilePath).href);
      await page.waitForFunction(() => document.getElementById('js-status').textContent === 'Consultation hors ligne prête');
      await page.selectOption('#type-filter','air.Source');
      await page.locator('#object-list button').filter({hasText:'window.airInjected'}).click();
      assert.ok((await page.locator('#object-title').textContent()).includes('<script>'));
      assert.equal(await page.evaluate(() => window.airInjected),undefined);
      assert.equal(await page.locator('img').count(),0);
      assert.equal(await page.locator('#prepare-contribution').isVisible(),false);
      assert.deepEqual(requests,[]);
      await page.close();
      const nojs = await context.browser().newContext({javaScriptEnabled:false});
      try { const fallback = await nojs.newPage();await fallback.goto(pathToFileURL(hostilePath).href);assert.ok((await fallback.locator('noscript').textContent()).includes('Contenu du contexte')); }
      finally { await nojs.close(); }
    }
  } finally { await context.close(); }
  const proof = {status:'PASS',version:report.version,browser:process.argv[3],browser_version:browserVersion,results,required_for_default_install:false,hostile_model_tested:fs.existsSync(path.join(root,'tmp/demo-asteria/workbench/hostile.html'))};
  const output = path.join(root,'tmp/demo-asteria',path.basename(process.argv[2],'.json') + '-browser.json');fs.writeFileSync(output,JSON.stringify(proof,null,2));
  console.log(JSON.stringify({status:proof.status,dossiers:results.length,report:output}));
})().catch(error => { console.error(error.stack);process.exitCode=1; });
