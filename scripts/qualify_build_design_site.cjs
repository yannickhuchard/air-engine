// Local browser qualification, not a user study or a native agent receipt.
const fs = require('fs'), path = require('path'), http = require('http');
const { chromium } = require(process.argv[5]);
(async () => {
  const root = path.resolve(process.argv[2]), out = path.resolve(process.argv[3]);
  fs.mkdirSync(out, { recursive: true });
  const server = http.createServer((req, res) => {
    const file = path.resolve(root, '.' + decodeURIComponent(req.url.split('?')[0]));
    if (!file.startsWith(root + path.sep)) { res.writeHead(403); return res.end(); }
    try {
      res.setHeader('Content-Type', file.endsWith('.svg') ? 'image/svg+xml' : file.endsWith('.css') ? 'text/css' : file.endsWith('.js') ? 'text/javascript' : file.endsWith('.json') ? 'application/json' : file.endsWith('.py') ? 'text/plain' : 'text/html');
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
      const home = path.posix.dirname(dossier.news) + '/index.html';
      const dir = path.posix.dirname(home);
      const model = JSON.parse(fs.readFileSync(path.join(root, dir, 'completeness.json')));
      for (const width of [320, 390, 768, 1440]) {
        for (const javaScriptEnabled of [true, false]) {
          const context = await browser.newContext({ viewport: { width, height: 950 }, reducedMotion: 'reduce', javaScriptEnabled });
          const page = await context.newPage();
          page.on('pageerror', error => errors.push(error.message));
          page.on('request', request => { if (!request.url().startsWith(origin)) remote.push(request.url()); });
          await page.goto(origin + '/' + home);
          await page.locator('.contextual-completeness a').click();
          await page.getByRole('heading', { name: 'Complétude selon le contexte', exact: true }).waitFor();
          if (await page.locator('img').evaluateAll(images => images.some(image => !image.complete || image.naturalWidth === 0))) throw Error('Unreadable branding image');
          const rows = page.locator('tbody tr');
          if (await rows.count() !== model.checks.length) throw Error('Missing contextual question');
          for (let i = 0; i < model.checks.length; i++) {
            if (!(await rows.nth(i).innerText()).includes(model.checks[i].question)) throw Error('Question mismatch');
          }
          if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)) throw Error('Page overflow');
          const links = await page.locator('main a').evaluateAll(els => els.map(e => e.getAttribute('href')).filter(Boolean));
          for (const link of links) {
            const response = await context.request.get(new URL(link, page.url()).href.split('#')[0]);
            if (response.status() !== 200) throw Error('Missing local subject or contract file: ' + link);
          }
          if (javaScriptEnabled && [390, 1440].includes(width)) await page.screenshot({ path: path.join(out, path.posix.basename(dir) + '-' + width + '.png'), fullPage: true });
          checks.push({ baseline: dossier.baseline, width, javaScriptEnabled, questions: model.checks.length, context: model.context_state, links: links.length, no_overflow: true });
          await context.close();
        }
      }
    }
    if (errors.length || remote.length) throw Error('Browser errors or external resources');
    const report = { status: 'PASS_SCOPED', scope: 'LOCAL_CHROMIUM_NOT_USER_RESEARCH_OR_NATIVE_CLIENT', checks, page_errors: errors, remote_requests: remote };
    fs.writeFileSync(path.join(out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
    console.log(JSON.stringify({ status: report.status, views: checks.length }));
  } finally { await browser.close(); server.close(); }
})().catch(error => { console.error(error); process.exit(1); });
