/* Optional inspection of a generated fictional AIR site, with an isolated browser.
   Usage: node scripts/audit_architecture_ux.cjs site-demo.json output edge.exe playwright-directory
   This records observations; it does not certify usability or accessibility. */
const fs=require('node:fs'),path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.argv[5]||'playwright');
const demo=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const output=path.resolve(process.argv[3]),root=path.dirname(demo.entrypoint);
fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:process.argv[4],headless:true});
 const context=await browser.newContext(),page=await context.newPage(),errors=[],external=[],observations=[];
 page.on('pageerror',e=>errors.push(String(e)));
 page.on('request',r=>{if(/^https?:/.test(r.url()))external.push(r.url());});
 const paths=['index.html','timeline.html'];
 for(const d of demo.site.dossiers){
  const dir=path.dirname(d.path),entries=fs.readdirSync(path.join(root,dir));
  paths.push(d.path,d.story,d.graph,path.join(dir,'business-paths.html'));
  for(const prefix of ['07-','17-','19-','22-','25-','27-','28-','35-']){
   const file=entries.find(p=>p.startsWith(prefix)&&p.endsWith('.html'));if(file)paths.push(path.join(dir,file));
  }
 }
 try{
  for(const width of [390,1440]){
   await page.setViewportSize({width,height:1000});
   for(const [index,file] of paths.entries()){
    const started=Date.now();await page.goto(pathToFileURL(path.join(root,file)).href);
    await page.waitForFunction(()=>document.body.dataset.diagramsReady==='true');
    const ready=Date.now()-started;
    const data=await page.evaluate(()=>{
     const main=document.querySelector('main'),visible=main.innerText;
     const names=s=>[...document.querySelectorAll(s)].map(e=>(e.innerText||e.textContent).trim());
     const font=getComputedStyle(document.body),nav=document.querySelector('.workspace-nav');
     return {title:document.title,h1:names('main h1'),headings:names('main h2'),
      words:visible.split(/\s+/).filter(Boolean).length,main_excerpt:visible.slice(0,3400),
      nav_links:nav.querySelectorAll('a').length,nav_initially_open:nav.open,
      document_overflow:document.documentElement.scrollWidth>innerWidth+2,
      inputs:[...main.querySelectorAll('input')].map(e=>({id:e.id,type:e.type,label:e.labels?.[0]?.innerText})),
      buttons:names('main button'),diagrams:main.querySelectorAll('.diagram').length,
      details:main.querySelectorAll('details').length,tables:main.querySelectorAll('table').length,
      body_font:font.fontFamily,body_font_size:font.fontSize,
      graph_canvas_y:main.querySelector('.graph-canvas')?.getBoundingClientRect().top??null,
      first_diagram_y:main.querySelector('.diagram')?.getBoundingClientRect().top??null,
      h1_y:main.querySelector('h1')?.getBoundingClientRect().top??null,
      links:[...main.querySelectorAll('a')].slice(0,20).map(e=>({text:e.innerText,href:e.getAttribute('href')}))};
    });
    const capture=index<5||index===8||index===10||index===11;
    let screenshot=null;
    if(capture){screenshot=width+'-'+file.replace(/[\\/]/g,'_')+'.png';await page.screenshot({path:path.join(output,screenshot)});}
    observations.push({width,page:file,local_file_ready_ms:ready,screenshot,...data});
   }
  }
  // An expert walkthrough of discoverability, navigation, search and reading controls.
  await page.goto(pathToFileURL(path.join(root,demo.site.dossiers[0].story)).href);
  const storyBefore=await page.locator('.story-chapter:not([hidden])').count();
  await page.locator('[data-story-chapter]').nth(1).click();
  const storyAfter=await page.locator('.story-chapter:not([hidden])').count();
  const storyUrl=page.url();
  await page.reload();
  const storyRestored=await page.locator('[data-story-chapter][aria-current]').getAttribute('data-story-chapter');
  const storage=await page.evaluate(()=>({label:document.querySelector('.app-menu summary').innerText,status:document.getElementById('pwa-status').innerText}));
  await page.emulateMedia({reducedMotion:'reduce'});
  const reducedMotion=await page.evaluate(()=>getComputedStyle(document.documentElement).scrollBehavior);
  const report={status:'OBSERVED_EXPERT_AUDIT',site:demo.site,method:'isolated Edge, local generated fictional site; no participant sessions',
   browser:browser.version(),pages_checked:observations.length,widths:[390,1440],
   page_errors:errors,external_requests:external,observations,
   story_walkthrough:{chapters_before_click:storyBefore,chapters_after_click:storyAfter,url_after_click:storyUrl,active_after_reload:storyRestored},
   file_mode_pwa:storage,reduced_motion_scroll_behavior:reducedMotion,
   participants:0,wcag_certification:false,production_performance_benchmark:false};
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
  process.stdout.write(JSON.stringify({status:report.status,pages:report.pages_checked,page_errors:errors.length,external_requests:external.length,story_walkthrough:report.story_walkthrough})+'\n');
 }finally{await Promise.race([browser.close(),new Promise(r=>setTimeout(r,10000))]);}
 process.exit(0);
})().catch(e=>{process.stderr.write(e.stack+'\n');process.exit(1);});
