// Local product checks. This does not constitute user research or native client acceptance.
const fs = require('fs'), path = require('path'), http = require('http');
const { chromium } = require(process.argv[5]);
(async () => {
  const root = path.resolve(process.argv[2]), out = path.resolve(process.argv[3]);
  fs.mkdirSync(out, { recursive: true });
  const server = http.createServer((req, res) => {
    const file = path.resolve(root, '.' + decodeURIComponent(req.url.split('?')[0]));
    if (!file.startsWith(root + path.sep)) { res.writeHead(403); return res.end(); }
    try {
      res.setHeader('Content-Type', file.endsWith('.css') ? 'text/css' : file.endsWith('.js') ? 'text/javascript' : file.endsWith('.json') ? 'application/json' : 'text/html');
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
      const progress = JSON.parse(fs.readFileSync(path.join(root, path.posix.dirname(home), 'progress.json')));
      for (const width of [320, 390, 768, 1440]) {
        for (const javaScriptEnabled of [true, false]) {
          const context = await browser.newContext({ viewport: { width, height: 950 }, reducedMotion: 'reduce', javaScriptEnabled });
          const page = await context.newPage();
          page.on('pageerror', error => errors.push(error.message));
          page.on('request', request => { if (!request.url().startsWith(origin)) remote.push(request.url()); });
          await page.goto(origin + '/' + home);
          const ribbon = page.locator('.completion-ribbon');
          const summaries = ribbon.locator('.completion-part > summary');
          if (await summaries.count() !== 8) throw Error('Expected eight parts');
          for (let i = 0; i < 8; i++) {
            const part = progress.parts[i];
            const summary = summaries.nth(i);
            if (!(await summary.innerText()).includes(part.percent === null ? 'Non évalué' : part.percent + ' %')) throw Error('Percentage mismatch');
            await summary.press('Enter');
            const panel = ribbon.locator('.completion-part').nth(i).locator('.completion-detail');
            await panel.waitFor({ state: 'visible' });
            if (!(await panel.innerText()).includes(part.covered + '/' + part.total)) throw Error('Coverage mismatch');
            await panel.getByRole('heading', { name: 'Contrôles restants', exact: true }).waitFor();
            await panel.getByRole('heading', { name: 'Travail déclaré', exact: true }).waitFor();
            const panelBox = await panel.boundingBox(), ribbonBox = await ribbon.boundingBox();
            if (panelBox.width < ribbonBox.width * .9) throw Error('Detail is confined to a narrow segment');
            if (javaScriptEnabled && await ribbon.locator('.completion-part[open]').count() !== 1) throw Error('Disclosure isolation failed');
            if (javaScriptEnabled) {
              await summary.press('Escape');
              await panel.waitFor({ state: 'hidden' });
              if (!(await summary.evaluate(e => e === document.activeElement))) throw Error('Escape lost focus');
            } else {
              await summary.press('Enter');
              await panel.waitFor({ state: 'hidden' });
            }
          }
          if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)) throw Error('Page overflow');
          await summaries.nth(7).click();
          await ribbon.locator('.completion-part').nth(7).locator('.completion-detail').waitFor({ state: 'visible' });
          if (javaScriptEnabled) await ribbon.screenshot({ path: path.join(out, path.posix.basename(path.posix.dirname(home)) + '-' + width + '.png') });
          checks.push({ baseline: dossier.baseline, width, javaScriptEnabled, keyboard: true, eight_parts: true, exact_percentages: true });
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
