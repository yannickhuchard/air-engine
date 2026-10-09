/* Optional development checks for locally generated fictional dossiers only. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');const {chromium}=require(process.argv[4]||'playwright');
const report=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const root=path.dirname(report.entrypoint),output=path.join(path.dirname(process.argv[2]),'branding-browser');fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:process.argv[3],headless:true}),page=await browser.newPage(),errors=[],remote=[];
 page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>{if(/^https?:/.test(r.url()))remote.push(r.url());});
 const checked=[];
 try{
  for(const [i,dossier] of report.site.dossiers.entries()){
   const folder=path.dirname(dossier.path),brand=JSON.parse(fs.readFileSync(path.join(root,dossier.branding.path),'utf8')).profile;
   for(const width of [320,390,768,1440]){
    await page.setViewportSize({width,height:1000});
    for(const topic of ['index.html','story.html','graph.html',fs.readdirSync(path.join(root,folder)).find(f=>f.startsWith('25-')&&f.endsWith('.html'))]){
     await page.goto(pathToFileURL(path.join(root,folder,topic)).href);await page.locator('.brand img').waitFor();
     const state=await page.evaluate(()=>({brand:document.querySelector('.brand span').textContent,font:getComputedStyle(document.body).fontFamily,
       header:getComputedStyle(document.documentElement).getPropertyValue('--header').trim(),semanticGreen:getComputedStyle(document.documentElement).getPropertyValue('--green').trim(),
       logo:document.querySelector('.brand img').complete&&document.querySelector('.brand img').naturalWidth>0,
       overflow:document.documentElement.scrollWidth>innerWidth+1}));
     assert(state.brand.includes(brand.name));assert(state.font.includes(brand.fonts.body));assert.equal(state.header,brand.colors.header);
     assert.equal(state.semanticGreen,'#267053');assert(state.logo);
     if(topic==='graph.html'){
      await page.waitForFunction(()=>document.getElementById('graph-canvas').dataset.graphReady==='true');
      assert.equal(await page.locator('[data-graph-preset=solution]').evaluate(e=>getComputedStyle(e).color),await page.locator('header').evaluate(e=>getComputedStyle(e).color));
      assert.equal(await page.locator('.graph-node-name').first().evaluate(e=>getComputedStyle(e).fill),'rgb(23, 51, 60)');
     }assert(!state.overflow,JSON.stringify({dossier:i,width,topic,state}));
     checked.push({dossier:i+1,width,topic,profile_digest:dossier.branding.profile_digest});
     if(width===1440&&topic.startsWith('25-'))await page.screenshot({path:path.join(output,`D0${i+1}-decision.png`)});
     if(width===390&&topic==='index.html')await page.screenshot({path:path.join(output,`D0${i+1}-mobile.png`)});
    }
   }
  }
  assert.equal(errors.length,0);assert.equal(remote.length,0);
  const result={status:'PASS_SCOPED',profiles:3,pages_checked:checked.length,viewports:[320,390,768,1440],names_colors_fonts_logos:true,ontology_colors_preserved:true,remote_requests:remote.length,page_errors:errors,checked};
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({...result,checked:undefined}));
 }finally{await Promise.race([browser.close(),new Promise(resolve=>setTimeout(resolve,10000))]);}
 process.exit(0);
})().catch(e=>{console.error(e);process.exitCode=1;});
