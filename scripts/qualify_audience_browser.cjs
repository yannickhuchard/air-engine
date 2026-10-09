/* Optional offline browser qualification; Node is never required by AIR itself. */
const fs = require('node:fs/promises');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
(async () => {
  const [reportPath, executablePath, modulePath] = process.argv.slice(2);
  assert(reportPath && executablePath && modulePath, 'Pass audience report, browser executable and Playwright module');
  const input = JSON.parse(await fs.readFile(reportPath, 'utf8'));
  const {chromium} = require(modulePath);
  const workspace = await fs.mkdtemp(path.join(root, 'tmp', 'audience-browser-'));
  process.env.TEMP = process.env.TMP = workspace;
  const browser = await chromium.launchPersistentContext(path.join(workspace, 'profile'), {
    executablePath, headless: true, acceptDownloads: false, viewport: {width: 1280, height: 1000},
    args: ['--disk-cache-dir=' + path.join(workspace, 'cache'), '--crash-dumps-dir=' + path.join(workspace, 'crashes')]
  });
  const outputs = [];
  try {
    const page = await browser.newPage();
    for (const dossier of input.treatments) for (const view of dossier.views) {
      const resolved = path.resolve(view.path);
      assert(resolved.startsWith(path.join(root, 'tmp') + path.sep));
      const bytes = await fs.readFile(resolved);
      assert.equal('sha256:' + crypto.createHash('sha256').update(bytes).digest('hex'), view.report.content_digest);
      await page.setViewportSize({width: 1280, height: 1000});
      await page.goto(pathToFileURL(resolved).href);
      assert.equal(await page.locator('article').count(), view.report.objects_selected);
      assert.equal(await page.locator('script').count(), 0);
      assert((await page.locator('h1').innerText()).includes(dossier.title));
      for (const mapping of view.report.source_mapping) {
        const article = page.locator(mapping.selector);
        assert.equal(await article.count(), 1);
        assert((await article.locator('details pre').textContent()).includes(mapping.object.id));
      }
      for (const mapping of view.report.context_mapping) assert.equal(await page.locator(mapping.selector).count(), 1);
      assert.equal(await page.evaluate(() => getComputedStyle(document.documentElement).backgroundColor), 'rgb(242, 246, 250)');
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      const violation = await page.evaluate(() => new Promise(resolve => {
        document.addEventListener('securitypolicyviolation', event => resolve({directive: event.effectiveDirective, blocked: event.blockedURI}), {once: true});
        fetch('https://example.invalid/air-browser-probe').then(() => resolve({connected: true}), () => {});
        setTimeout(() => resolve({timeout: true}), 500);
      }));
      assert.equal(violation.directive, 'connect-src');
      assert(violation.blocked.startsWith('https://example.invalid'));
      const desktop = resolved.replace(/\.html$/, '-desktop.png');
      await page.screenshot({path: desktop});
      await page.locator('details summary').first().focus();
      await page.keyboard.press('Enter');
      assert(await page.locator('details').first().evaluate(node => node.open));
      await page.setViewportSize({width: 390, height: 844});
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      const mobile = resolved.replace(/\.html$/, '-mobile.png');
      await page.goto(pathToFileURL(resolved).href);
      await page.screenshot({path: mobile});
      outputs.push({case: dossier.case, audience: view.audience, content_digest: view.report.content_digest,
        mappings_verified: view.report.source_mapping.length, desktop, mobile, keyboard: 'PASS', csp: 'PASS', horizontal_overflow: false});
    }
  } finally { await browser.close(); }
  const result = {status: 'PASS', version: input.version, executable: executablePath, reports: outputs, live_instance_modified: false};
  const destination = path.join(root, 'tmp', 'demo-asteria', 'audience-browser.json');
  await fs.writeFile(destination, JSON.stringify(result, null, 2) + '\n');
  process.stdout.write(JSON.stringify({status: 'PASS', views: outputs.length, report: destination}) + '\n');
})().catch(error => { process.stderr.write(error.stack + '\n'); process.exitCode = 1; });
