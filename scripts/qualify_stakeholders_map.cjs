// Local static-site verification, not a native AI client or user research receipt.
const fs=require('fs'),path=require('path'),http=require('http');
const {chromium}=require(process.argv[5]);
(async()=>{
  const root=path.resolve(process.argv[2]),out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
  const server=http.createServer((req,res)=>{
    const file=path.resolve(root,'.'+decodeURIComponent(req.url.split('?')[0]));
    if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}
    try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.json')?'application/json':file.endsWith('.svg')?'image/svg+xml':'text/html');res.end(fs.readFileSync(file));}
    catch{res.writeHead(404);res.end();}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin=`http://127.0.0.1:${server.address().port}`;
  const browser=await chromium.launch({executablePath:process.argv[4],headless:true}),checks=[],errors=[],remote=[];
  try{
    const manifest=JSON.parse(fs.readFileSync(path.join(root,'site-manifest.json'))),dossier=manifest.dossiers[0];
    for(const width of [320,390,768,1440]){
      const page=await browser.newPage({viewport:{width,height:1000},hasTouch:width<=390,reducedMotion:'reduce'});
      page.on('pageerror',e=>errors.push(e.message));page.on('console',e=>{if(e.type()==='error')errors.push(e.text());});
      page.on('request',r=>{if(!r.url().startsWith(origin))remote.push(r.url());});
      const response=await page.goto(origin+'/'+dossier.stakeholders_map);if(response.status()!==200)throw Error('Missing map');
      if(await page.locator('.stakeholder-node').count()!==4)throw Error('Expected four participation states');
      await page.locator('[data-stakeholder-filter="MISSING"]').click();
      await page.locator('.stakeholder-node[data-state="MISSING"]').click();
      if(await page.locator('[data-stakeholder-state]:visible').count()!==1)throw Error('State filter');
      const vacant=page.locator('[data-stakeholder-state="MISSING"]');
      if(!(await vacant.innerText()).includes('Recrutement à prévoir'))throw Error('Staffing action hidden');
      if(await page.locator('[data-stakeholder-back]').isVisible())await page.locator('[data-stakeholder-back]').click();
      if(await page.locator('.stakeholder-node:visible').count()!==1)throw Error('Map filter or return lost filter');
      await page.locator('[data-stakeholder-search]').fill('sécurité');
      if(!await page.locator('[data-stakeholder-empty]').isVisible())throw Error('Combined filters or empty state');
      await page.locator('[data-stakeholder-reset]').click();
      await page.locator('[data-stakeholder-search]').fill('securite');
      if(await page.locator('.stakeholder-node:visible').count()!==1)throw Error('Accent insensitive search');
      await page.locator('[data-stakeholder-search]').fill('');
      await page.locator('.stakeholder-node').first().focus();await page.keyboard.press('Enter');
      if(!(await page.locator('[data-stakeholder-state="INVOLVED"]').getAttribute('open')) && await page.locator('[data-stakeholder-state="INVOLVED"]').getAttribute('open')===null)throw Error('Keyboard did not open detail');
      if(await page.locator('.stakeholder-node[aria-current="true"]').count()!==1)throw Error('Selected role missing');
      if(await page.locator('[data-stakeholder-back]').isVisible())await page.locator('[data-stakeholder-back]').click();
      const missingNode=page.locator('.stakeholder-node[data-state="MISSING"]');
      if(width<=390)await missingNode.tap();else await missingNode.click();
      if(!await vacant.isVisible())throw Error('Touch selection');
      if(await page.locator('[data-stakeholder-back]').isVisible()){
        await page.locator('[data-stakeholder-back]').click();
        if(!await missingNode.evaluate(e=>e===document.activeElement))throw Error('Return focus');
      }
      for(const rect of await page.locator('.stakeholder-node:visible,[data-stakeholder-filter]:visible').evaluateAll(nodes=>nodes.map(e=>({h:e.getBoundingClientRect().height,w:e.getBoundingClientRect().width})))){
        if(rect.h<44||rect.w<44)throw Error('Touch target smaller than 44px');
      }
      if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Page overflow '+width);
      await page.locator('[data-stakeholders-map]').screenshot({path:path.join(out,`stakeholders-${width}.png`)});
      await page.reload();
      if(!await vacant.isVisible())throw Error('Deep link reload');
      await page.emulateMedia({media:'print'});
      await page.evaluate(()=>window.dispatchEvent(new Event('beforeprint')));
      if(await page.locator('[data-stakeholder-state]:visible').count()!==4)throw Error('Print omits contributions');
      await page.evaluate(()=>window.dispatchEvent(new Event('afterprint')));
      await page.emulateMedia({media:'screen'});
      let sources=0;for(const href of await page.locator('main a[href]').evaluateAll(a=>[...new Set(a.map(x=>x.getAttribute('href')))])){
        if(!href||href.startsWith('#'))continue;const r=await page.request.get(new URL(href,page.url()).toString());if(r.status()!==200)throw Error('Broken source '+href);sources++;
      }
      checks.push({width,states:4,filter:true,search_combined_and_accent_insensitive:true,empty_state:true,touch_or_mouse_selection:true,keyboard_to_detail:true,return_focus:true,deep_link_reload:true,print_all_entries:true,touch_targets_44px:true,page_overflow:false,source_links:sources});await page.close();
    }
    const plain=await browser.newPage({viewport:{width:390,height:1000},javaScriptEnabled:false});
    await plain.goto(origin+'/'+dossier.stakeholders_map);
    if(await plain.locator('[data-stakeholder-state]:visible').count()!==4)throw Error('No script reading incomplete');
    if(await plain.locator('[data-stakeholder-tools]').isVisible())throw Error('Inactive controls without script');
    if(await plain.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('No script overflow');
    await plain.close();checks.push({no_javascript:true,all_details_readable:true,controls_hidden:true});
    if(errors.length||remote.length)throw Error(JSON.stringify({errors,remote}));
    const result={result:'PASS_SCOPED',checks,script_errors:errors,external_requests:remote};fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
