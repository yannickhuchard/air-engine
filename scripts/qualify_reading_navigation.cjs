// Technical navigation exercise on fictional exports, not field user research.
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
  const manifest=JSON.parse(fs.readFileSync(path.join(root,'site-manifest.json')));
  const openMenu=async page=>{if(!await page.locator('.workspace-nav').evaluate(e=>e.open))await page.locator('.workspace-nav>summary').click();};
  const current=async(page,href)=>{const selected=page.locator('.workspace-nav a[aria-current="page"]');if(await selected.count()!==1||await selected.getAttribute('href')!==href)throw Error('Incorrect current link '+href);};
  const fit=async page=>{if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Page overflow');};
  for(const dossier of manifest.dossiers)for(const width of [320,390,768,1440]){
   const page=await browser.newPage({viewport:{width,height:1000},hasTouch:width<=390,reducedMotion:'reduce'});
   page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(!r.url().startsWith(origin))remote.push(r.url());});
   const base=origin+'/'+dossier.path.replace('index.html','');
   await page.goto(base+'lecture-cadrage.html');await current(page,'lecture-cadrage.html');
   const stages=await page.locator('[data-nav-stage]').evaluateAll(nodes=>nodes.map(e=>e.dataset.navStage));
   if(stages.join(',')!=='cadrage,usages,solution,donnees,qualite,construction,validation')throw Error('Reading order');
   const topics=await page.locator('.workspace-nav a[href]').evaluateAll(nodes=>nodes.map(e=>e.getAttribute('href')).filter(h=>/^\d\d-/.test(h)));
   if(topics.length!==38||new Set(topics).size!==38)throw Error('Topic missing or duplicate');
   if(await page.locator('.reading-position [rel="prev"]').count())throw Error('Previous before first chapter');
   await page.locator('.reading-position [rel="next"]').click();await page.waitForURL(base+'lecture-usages.html');await current(page,'lecture-usages.html');
   await openMenu(page);
   const data=page.locator('[data-nav-stage="donnees"]');await data.locator('summary').focus();await page.keyboard.press('Enter');
   if(!await data.evaluate(e=>e.open))throw Error('Keyboard disclosure');
   const logical=data.locator('a[href^="19-"]');const logicalHref=await logical.getAttribute('href');
   await logical.click();await page.waitForURL(base+logicalHref);await current(page,logicalHref);
   if(!await page.locator('[data-nav-stage="donnees"]').evaluate(e=>e.open))throw Error('Current chapter closed');
   if(!(await page.locator('.reading-position').innerText()).includes('Modèles de données'))throw Error('Dimension context missing');
   await fit(page);
   for(const role of ['metier','realisation']){
    await openMenu(page);await page.locator('.workspace-nav a[href="role-'+role+'.html"]').click();await page.waitForURL(base+'role-'+role+'.html');await current(page,'role-'+role+'.html');
   }
   await page.goto(base+'lecture-construction.html');await openMenu(page);await fit(page);
   for(const rect of await page.locator('.workspace-nav a:visible,.workspace-nav summary:visible').evaluateAll(nodes=>nodes.map(e=>({w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height,element:e.outerHTML.slice(0,180)}))))if(rect.h<44||rect.w<44)throw Error('Small touch target '+JSON.stringify({width,...rect}));
   await page.screenshot({path:path.join(out,`${dossier.namespace}-${width}.png`),fullPage:true});
   for(const href of await page.locator('main a[href]').evaluateAll(nodes=>nodes.map(e=>e.getAttribute('href'))))if((await page.request.get(new URL(href,page.url()).toString())).status()!==200)throw Error('Chapter link missing '+href);
   checks.push({dossier:dossier.namespace,width,ordered_chapters:7,unique_topics:38,current_link:true,dimension_context:true,next_chapter:true,keyboard_disclosure:true,business_and_builder_routes:true,no_overflow:true,touch_targets_44px:true});
   await page.close();
  }
  for(const width of [390,1440]){
   const page=await browser.newPage({viewport:{width,height:1000},javaScriptEnabled:false});
   const base=origin+'/'+manifest.dossiers[0].path.replace('index.html','');
   await page.goto(base+'19-modele-logique.html');await current(page,'19-modele-logique.html');
   if(!await page.locator('[data-nav-stage="donnees"]').evaluate(e=>e.open))throw Error('No script current chapter closed');
   await fit(page);checks.push({width,no_javascript:true,current_chapter_open:true,all_chapters_available:await page.locator('[data-nav-stage]').count()===7});await page.close();
  }
  if(errors.length||remote.length)throw Error(JSON.stringify({errors,remote}));
  const result={result:'PASS_SCOPED',checks,script_errors:errors,external_requests:remote,field_user_research:false};fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
