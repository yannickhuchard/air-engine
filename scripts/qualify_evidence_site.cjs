/* Optional browser reception for the static proof/change view, no human UX claim. */
const fs = require('fs'), path = require('path'), http = require('http'), assert = require('assert/strict');
const { chromium } = require(process.argv[5]);
(async () => {
  const root = path.resolve(process.argv[2]), out = path.resolve(process.argv[3]);
  fs.mkdirSync(out, { recursive: true });
  const server = http.createServer((req, res) => {
    const file = path.resolve(root, '.' + decodeURIComponent(req.url.split('?')[0]));
    if (!file.startsWith(root + path.sep)) { res.writeHead(403); return res.end(); }
    try {
      res.setHeader('Content-Type', file.endsWith('.svg') ? 'image/svg+xml' : file.endsWith('.png') ? 'image/png' : file.endsWith('.css') ? 'text/css' : file.endsWith('.js') ? 'text/javascript' : file.endsWith('.json') ? 'application/json' : 'text/html');
      res.end(fs.readFileSync(file));
    } catch { res.writeHead(404); res.end(); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  let browser;
  const checks = [], errors = [], remote = [];
  try {
    browser = await chromium.launch({ executablePath: process.argv[4], headless: true });
    const manifest = JSON.parse(fs.readFileSync(path.join(root, 'site-manifest.json')));
    for (const dossier of manifest.dossiers) {
      const route = path.posix.dirname(dossier.path) + '/verification.html';
      for (const width of [320, 390, 768, 1440]) for (const javaScriptEnabled of [true, false]) {
        const context = await browser.newContext({ viewport: { width, height: 950 }, reducedMotion: 'reduce', javaScriptEnabled });
        const page = await context.newPage();
        page.on('pageerror', error => errors.push(error.message));
        page.on('request', request => { if (!request.url().startsWith(origin)) remote.push(request.url()); });
        await page.goto(origin + '/' + route);
        await page.getByRole('heading', { name: 'Vérifications et changements', exact: true }).waitFor();
        assert.equal(await page.locator('img').evaluateAll(images => images.some(img => !img.complete || img.naturalWidth === 0)), false, 'Image failed to load');
        const panels = page.locator('main details');
        for (let i = 0; i < await panels.count(); i++) {
          await panels.nth(i).locator('summary').focus(); await page.keyboard.press('Enter');
          assert.equal(await panels.nth(i).getAttribute('open'), '');
        }
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, 'Responsive overflow');
        for (const href of await page.locator('main a').evaluateAll(elements => elements.map(e => e.getAttribute('href')))) {
          const response = await context.request.get(new URL(href, page.url()).href.split('#')[0]);
          assert.equal(response.status(), 200, href);
        }
        await page.screenshot({ path: path.join(out, `${checks.length}-${width}-${javaScriptEnabled}.png`) });
        checks.push({ baseline: dossier.baseline, width, javaScriptEnabled, keyboard_details: true, readable_links: true, overflow: false });
        await context.close();
      }
    }
    assert.deepEqual(errors, []); assert.deepEqual(remote, []);
    fs.writeFileSync(path.join(out, 'report.json'), JSON.stringify({ status: 'PASS_SCOPED', checks, errors, remote, user_research: false }, null, 2));
    console.log(JSON.stringify({ status: 'PASS_SCOPED', views: checks.length }));
  } finally { if (browser) await browser.close(); server.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
