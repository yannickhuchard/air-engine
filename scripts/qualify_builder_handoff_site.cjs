// Optional local Chromium qualification; no human UX study is claimed.
const fs = require('fs'), path = require('path'), http = require('http'), assert = require('assert/strict');
const { chromium } = require(process.argv[5]);
(async () => {
  const root = path.resolve(process.argv[2]), out = path.resolve(process.argv[3]);
  fs.mkdirSync(out, { recursive: true });
  const server = http.createServer((req, res) => {
    const file = path.resolve(root, '.' + decodeURIComponent(req.url.split('?')[0]));
    if (!file.startsWith(root + path.sep)) { res.writeHead(403); return res.end(); }
    try {
      res.setHeader('Content-Type', file.endsWith('.svg') ? 'image/svg+xml' : file.endsWith('.css') ? 'text/css' : file.endsWith('.js') ? 'text/javascript' : file.endsWith('.json') ? 'application/json' : 'text/html');
      res.end(fs.readFileSync(file));
    } catch { res.writeHead(404); res.end(); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({ executablePath: process.argv[4], headless: true });
  const checks = [], errors = [], remote = [];
  try {
    const manifest = JSON.parse(fs.readFileSync(path.join(root, 'site-manifest.json')));
    for (const dossier of manifest.dossiers) {
      const route = path.posix.dirname(dossier.path) + '/handoff.html';
      const model = JSON.parse(fs.readFileSync(path.join(root, path.posix.dirname(route), 'builder-receipts.json')));
      for (const width of [320, 390, 768, 1440]) for (const javaScriptEnabled of [true, false]) {
        const context = await browser.newContext({ viewport: { width, height: 950 }, reducedMotion: 'reduce', javaScriptEnabled });
        const page = await context.newPage();
        page.on('pageerror', error => errors.push(error.message));
        page.on('request', request => { if (!request.url().startsWith(origin)) remote.push(request.url()); });
        await page.goto(origin + '/' + route);
        await page.getByRole('heading', { name: 'Réception des paquets', exact: true }).waitFor();
        const panels = page.locator('#builder-receipts details');
        assert.equal(await panels.count(), model.packages.length);
        for (let i = 0; i < model.packages.length; i++) {
          const panel = panels.nth(i), summary = panel.locator('summary');
          await summary.focus(); await page.keyboard.press('Enter');
          assert.equal(await panel.getAttribute('open'), '');
          assert.ok((await panel.innerText()).includes(model.packages[i].package.digest));
        }
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, 'Responsive overflow');
        for (const link of await page.locator('#builder-receipts a').evaluateAll(elements => elements.map(e => e.getAttribute('href')))) {
          const response = await context.request.get(new URL(link, page.url()).href.split('#')[0]);
          assert.equal(response.status(), 200, link);
        }
        await page.locator('#builder-receipts').scrollIntoViewIfNeeded();
        await page.screenshot({ path: path.join(out, `${checks.length}-${width}-${javaScriptEnabled}.png`) });
        checks.push({ baseline: dossier.baseline, width, javaScriptEnabled, packages: model.packages.length,
          state: model.state, keyboard_details: true, readable_links: true, overflow: false });
        await context.close();
      }
    }
    assert.deepEqual(errors, []); assert.deepEqual(remote, []);
    fs.writeFileSync(path.join(out, 'report.json'), JSON.stringify({ status: 'PASS_SCOPED', checks, errors, remote, user_research: false }, null, 2));
    console.log(JSON.stringify({ status: 'PASS_SCOPED', views: checks.length }));
  } finally { await browser.close(); server.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
