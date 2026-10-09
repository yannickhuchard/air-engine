'use strict';
(function () {
  const embedded = document.getElementById('air-graph');
  if (!embedded) return;
  const payload = JSON.parse(embedded.textContent), graph = payload.graph;
  const byId = new Map(graph.nodes.map(n => [n.id,n]));
  const byRef = new Map(graph.nodes.filter(n=>!n.local_step).map(n=>[refKey(n.reference),n]));
  const canvas = document.getElementById('graph-canvas'), detail = document.getElementById('graph-detail');
  const status = document.getElementById('graph-status'), pathStatus = document.getElementById('graph-path-status');
  const objectSelect = document.getElementById('graph-object'), pathSelect = document.getElementById('graph-path');
  const search = document.getElementById('graph-search'), typeSelect = document.getElementById('graph-type');
  const neighbors = document.getElementById('graph-neighbors'), onlyPath = document.getElementById('graph-only-path');
  const motion = document.getElementById('graph-motion'), reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const presets = {
    business:{families:['business','behavior'],types:['air.Intent','air.Goal','air.Capability']},
    solution:{families:['behavior','interface','component'],types:['air.ArchitectureBlock','air.SemanticContract','air.Function']},
    data:{families:['data','component','interface'],types:['air.DataEntity','air.Concept','air.PhysicalTable']},
    delivery:{families:['governance','component','evidence'],types:['air.ConstructionUnit','air.Requirement','air.VerificationCase']}
  };
  const defaults = new Map([...document.querySelectorAll('[data-graph-family],[data-graph-kind]')].map(e=>[e,e.checked]));
  const SVG_NS = 'http://www.w3.org/2000/svg';
  let selected = '', selectedEdge = '', positions = new Map(), svg, box, fullBox, drag, overviewBox;
  let layoutSignature='', viewportSignature='';
  let cameraFrame=0,cameraTarget=null,readingEdge=null,readingStep=0;
  function firstObject(preset) {
    const sorted=graph.nodes.filter(n=>!n.local_step).slice().sort((a,b)=>a.name.localeCompare(b.name,'fr')||a.id.localeCompare(b.id));
    return preset.types.map(type=>sorted.find(n=>n.type===type)).find(Boolean)||sorted.find(n=>preset.families.includes(n.family));
  }
  function refKey(ref) { return ref.id+'\u0000'+ref.revision; }
  function normalize(text) { return text.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase(); }
  function html(tag,text,parent,attrs={}) {
    const el=document.createElement(tag);if(text!==null) el.textContent=String(text).replace(/\u2014/g,'-');
    for(const [key,value] of Object.entries(attrs)) el.setAttribute(key,value);
    if(parent)parent.appendChild(el);return el;
  }
  function shape(tag,attrs={},text=null,parent=svg) {
    const el=document.createElementNS(SVG_NS,tag);
    for(const [key,value] of Object.entries(attrs))el.setAttribute(key,value);
    if(text!==null)el.textContent=String(text).replace(/\u2014/g,'-');if(parent)parent.appendChild(el);return el;
  }
  function link(text,href,parent) { return html('a',text,parent,{href}); }
  function activeKinds() { return new Set([...document.querySelectorAll('[data-graph-kind]:checked')].map(e=>e.dataset.graphKind)); }
  function pathMembers() {
    if(!pathSelect.value)return new Set();
    const path=payload.paths[Number(pathSelect.value)], refs=new Set(path.objects.map(refKey)), workflows=new Set(path.workflows.map(refKey));
    return new Set(graph.nodes.filter(n=>n.local_step?workflows.has(refKey(n.reference)):refs.has(refKey(n.reference))).map(n=>n.id));
  }
  function markPreset(key) {
    document.querySelectorAll('[data-graph-preset]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.graphPreset===key)));
  }
  function choose(id,focusDetail=false) {
    selected=id;selectedEdge='';readingEdge=null;objectSelect.value=id;
    if(id){
      const node=byId.get(id);document.querySelector('[data-graph-family="'+node.family+'"]').checked=true;
      search.value='';typeSelect.value='';
    }
    render();showNode();if(focusDetail)detail.querySelector('a,button')?.focus();
  }
  function showNode() {
    detail.replaceChildren();
    if(!selected){html('h2','Lire les relations',detail);html('p','Choisissez un objet pour examiner ses voisins et leurs sources exactes.',detail);return;}
    const node=byId.get(selected);html('h2',node.name,detail);html('p',node.type.slice(4)+' · révision '+node.reference.revision+' · '+node.lifecycle,detail);
    html('p',node.description,detail);link(node.local_step?'Ouvrir le workflow source':'Ouvrir la définition exacte',payload.links[node.id],detail);
    if(node.local_step){const d=html('details',null,detail);html('summary','Déclaration de cette étape',d);html('pre',JSON.stringify(node.declared,null,2),d);}
    html('p','Identité : '+node.reference.id,detail);html('p','Empreinte : '+node.reference.digest,detail);
    html('h3','Voisins directs',detail);
    // The panel retains all relations, even when a drawing filter hides them.
    const incident=graph.edges.filter(e=>e.source===selected||e.target===selected);
    html('p',incident.length+' relation(s) déclarée(s), y compris celles cachées par les filtres.'+(incident.length>200?' Les 200 premières sont présentées ici ; consultez le JSON pour la liste complète.':''),detail);
    const list=html('ul',null,detail,{class:'graph-relations'});
    for(const edge of incident.slice(0,200)){
      const neighbor=byId.get(edge.source===selected?edge.target:edge.source), item=html('li',null,list);
      const button=html('button',neighbor.name,item,{type:'button','data-graph-neighbor':neighbor.id});button.addEventListener('click',()=>choose(neighbor.id,true));
      html('span',(edge.source===selected?' Sortant · ':' Entrant · ')+graph.relation_kinds[edge.kind],item);
      const relation=html('button','Lire la relation et sa source',item,{type:'button','data-graph-relation':edge.id});relation.addEventListener('click',()=>showEdge(edge));
    }
    if(!incident.length)html('p','Aucune relation déclarée pour cet objet dans cette baseline.',detail);
  }
  function showEdge(edge) {
    readingEdge=edge;readingStep=0;selectedEdge=edge.id;selected=edge.source;objectSelect.value=selected;
    search.value='';typeSelect.value='';onlyPath.checked=false;neighbors.checked=true;
    for(const id of [edge.source,edge.target])document.querySelector('[data-graph-family="'+byId.get(id).family+'"]').checked=true;
    document.querySelector('[data-graph-kind="'+edge.kind+'"]').checked=true;markPreset('');
    render();detail.replaceChildren();
    html('h2',graph.relation_kinds[edge.kind],detail);
    html('p',byId.get(edge.source).name+' → '+byId.get(edge.target).name,detail);
    const reader=html('div',null,detail,{class:'graph-reading'});
    html('p','Lire une déclaration en trois étapes, sans exécution de la solution.',reader);
    const steps=html('div',null,reader,{class:'graph-reading-steps',role:'group','aria-label':'Étapes de lecture de la relation'});
    ['Source','Relation','Destination'].forEach((label,index)=>{
      const button=html('button',(index+1)+'. '+label,steps,{type:'button','data-reading-step':index,'aria-pressed':String(index===0)});
      button.addEventListener('click',()=>readRelation(index,true));
    });
    html('div',null,reader,{id:'graph-reading-caption',role:'status'});
    readRelation(0,false);
    html('p',edge.label,detail);html('p','Sélecteur source : '+edge.selector,detail);
    const evidence=byRef.get(refKey(edge.evidence));if(evidence)link('Ouvrir la source exacte',payload.links[evidence.id],detail);
    html('p','Empreinte : '+edge.evidence.digest,detail);
    if(edge.kind==='CONTROL_FLOW')html('p','Branche potentielle. La condition et la garde ne sont pas évaluées ; les jointures parallèles ne sont pas reconstruites par ce dessin.',detail);
    if(edge.kind==='REFERENCE'||edge.kind==='CONTEXT'||edge.kind==='PROVENANCE')html('p','Cette flèche est une référence, pas une interaction métier.',detail);
    if(edge.declared){const d=html('details',null,detail);html('summary','Déclaration complète',d);html('pre',JSON.stringify(edge.declared,null,2),d);}
    const back=html('button','Revenir à l’objet',detail,{type:'button'});back.addEventListener('click',()=>choose(selected,true));
    steps.querySelector('button')?.focus();
  }
  function readRelation(step,animate) {
    if(!readingEdge)return;
    readingStep=step;
    const edge=readingEdge,node=byId.get(step===2?edge.target:edge.source);
    document.querySelectorAll('[data-reading-step]').forEach(button=>button.setAttribute('aria-pressed',String(Number(button.dataset.readingStep)===step)));
    for(const el of canvas.querySelectorAll('[data-node]')){
      el.classList.toggle('reading-focus',step!==1&&el.dataset.node===node.id);
    }
    for(const el of canvas.querySelectorAll('[data-edge]'))el.classList.toggle('reading-focus',step===1&&el.dataset.edge===edge.id);
    const caption=document.getElementById('graph-reading-caption');caption.replaceChildren();
    html('h3',step===1?graph.relation_kinds[edge.kind]:node.name,caption);
    html('p',step===1?edge.label:node.description,caption);
    if(step===1){
      const evidence=byRef.get(refKey(edge.evidence));
      if(evidence)link('Lire la déclaration source',payload.links[evidence.id],caption);
    }else link('Lire la définition exacte',payload.links[node.id],caption);
    if(animate){
      const a=positions.get(edge.source),b=positions.get(edge.target);
      if(step===1&&a&&b){
        const ratio=box.w/box.h,w=Math.max(360,Math.abs(a.x-b.x)+280,(Math.abs(a.y-b.y)+160)*ratio);
        moveBox({x:(a.x+b.x)/2-w/2,y:(a.y+b.y)/2-w/ratio/2,w,h:w/ratio});
      }else focusNode(node.id,true);
    }
  }
  function setBox(value) {
    box=value;svg.setAttribute('viewBox',[box.x,box.y,box.w,box.h].join(' '));
    if(overviewBox)for(const [key,v] of Object.entries({x:box.x,y:box.y,width:box.w,height:box.h}))overviewBox.setAttribute(key,v);
  }
  function stopCamera(settle=true) {
    if(cameraFrame)cancelAnimationFrame(cameraFrame);cameraFrame=0;
    if(settle&&cameraTarget&&svg)setBox(cameraTarget);
    cameraTarget=null;canvas.dataset.cameraMotion='idle';
  }
  function moveBox(value,animate=true) {
    stopCamera(false);
    if(!animate||!box||!motion.checked||reducedMotion.matches){setBox(value);return;}
    const from={...box},started=performance.now();cameraTarget={...value};canvas.dataset.cameraMotion='running';
    function frame(now){
      const t=Math.min(1,(now-started)/200),ease=1-Math.pow(1-t,3),next={};
      for(const key of ['x','y','w','h'])next[key]=from[key]+(value[key]-from[key])*ease;
      setBox(next);
      if(t<1)cameraFrame=requestAnimationFrame(frame);else{cameraFrame=0;cameraTarget=null;canvas.dataset.cameraMotion='idle';}
    }
    cameraFrame=requestAnimationFrame(frame);
  }
  function zoom(factor,cx=.5,cy=.5){
    if(!svg||!box)return;
    const w=Math.max(180,Math.min(fullBox.w*5,box.w*factor)),h=w*box.h/box.w;
    moveBox({x:box.x+(box.w-w)*cx,y:box.y+(box.h-h)*cy,w,h});
  }
  function fit() { if(svg&&fullBox)moveBox({...fullBox}); }
  function focusNode(id,animate=false) {
    const p=positions.get(id);if(!p){status.textContent+=' L’objet choisi est masqué : modifiez les filtres.';return;}
    const w=Math.min(fullBox.w,Math.max(canvas.clientWidth,360)),h=w*fullBox.h/fullBox.w;
    moveBox({x:p.x-w/2,y:p.y-h/2,w,h},animate);
  }
  function center() { focusNode(selected,true); }
  function render() {
    document.querySelector('.graph-map').hidden=false;
    stopCamera(true);
    const previousBox=box?{...box}:null;
    const families=new Set([...document.querySelectorAll('[data-graph-family]:checked')].map(e=>e.dataset.graphFamily));
    const kinds=activeKinds(), members=pathMembers(), words=normalize(search.value).split(/\s+/).filter(Boolean);
    let visible=graph.nodes.filter(n=>families.has(n.family)&&(!typeSelect.value||n.type===typeSelect.value)&&words.every(w=>normalize(n.name+' '+n.type+' '+n.description).includes(w)));
    if(onlyPath.checked&&pathSelect.value)visible=visible.filter(n=>members.has(n.id));
    if(neighbors.checked&&selected){
      const adjacent=new Set([selected]);for(const e of graph.edges)if(kinds.has(e.kind)&&(e.source===selected||e.target===selected)){adjacent.add(e.source);adjacent.add(e.target);}
      visible=visible.filter(n=>adjacent.has(n.id));
    }
    visible.sort((a,b)=>(b.id===selected)-(a.id===selected)||members.has(b.id)-members.has(a.id)||a.name.localeCompare(b.name,'fr')||a.id.localeCompare(b.id));
    const matched=visible.length;visible=visible.slice(0,180);const ids=new Set(visible.map(n=>n.id));
    let edges=graph.edges.filter(e=>kinds.has(e.kind)&&ids.has(e.source)&&ids.has(e.target));const relationCount=edges.length;edges=edges.slice(0,1000);
    status.textContent=(neighbors.checked&&selected?'Voisinage de « '+byId.get(selected).name+' ». ':'')+visible.length+' objet(s)/étape(s) dessiné(s) sur '+matched+' correspondant aux filtres ('+graph.nodes.length+' dans la baseline), '+edges.length+' relation(s).'+
      (matched>180?' Limite de 180 objets : précisez les filtres.':'')+(relationCount>1000?' '+(relationCount-1000)+' relations non dessinées : précisez les filtres.':'')+
      (!visible.length?' Aucun résultat. Modifiez la recherche, les couches, le type ou le contexte choisi.':'');
    pathStatus.replaceChildren();if(pathSelect.value){const path=payload.paths[Number(pathSelect.value)];html('span','Contexte déclaré de « '+path.name+' » : '+path.gaps+' point(s) de vigilance. La surbrillance ne prouve pas une chaîne d’appels. '+(path.context_truncated?'Contexte limité. ':''),pathStatus);link('Lire ce parcours',path.href,pathStatus);}
    canvas.replaceChildren();svg=shape('svg',{role:'group','aria-label':'Relations déclarées de cette baseline'},null,null);canvas.appendChild(svg);
    const defs=shape('defs');for(const kind of Object.keys(graph.relation_kinds)){
      const marker=shape('marker',{id:'arrow-'+kind,viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:7,markerHeight:7,orient:'auto-start-reverse'},null,defs);
      shape('path',{d:'M 0 0 L 10 5 L 0 10 z',class:'graph-arrow kind-'+kind},null,marker);
    }
    positions=new Map();const groups=graph.families.filter(f=>visible.some(n=>n.family===f.id));let maxRows=1;
    groups.forEach((f,col)=>{
      const items=visible.filter(n=>n.family===f.id).sort((a,b)=>a.name.localeCompare(b.name,'fr')||a.id.localeCompare(b.id));maxRows=Math.max(maxRows,items.length);
      shape('text',{x:col*236+16,y:20,class:'graph-lane'},f.label);
      items.forEach((n,row)=>positions.set(n.id,{x:col*236+118,y:row*88+80}));
    });
    const edgeLayer=shape('g',{class:'graph-edges'});
    for(const edge of edges){
      const a=positions.get(edge.source),b=positions.get(edge.target),right=b.x>=a.x;
      const sx=a.x+(right?100:-100),tx=b.x+(right?-100:100),bend=a.x===b.x?a.x+146:(sx+tx)/2;
      const d=edge.source===edge.target?'M '+sx+' '+a.y+' C '+(sx+65)+' '+(a.y-90)+' '+(sx+65)+' '+(a.y+90)+' '+sx+' '+(a.y+12):'M '+sx+' '+a.y+' C '+bend+' '+a.y+' '+bend+' '+b.y+' '+tx+' '+b.y;
      const inPath=members.has(edge.source)&&members.has(edge.target);
      const el=shape('path',{d,class:'graph-edge kind-'+edge.kind+(inPath?' path-member':'')+(edge.id===selectedEdge?' edge-selected':'')+(readingEdge&&readingStep===1&&edge.id===readingEdge.id?' reading-focus':''),
        'marker-end':'url(#arrow-'+edge.kind+')',tabindex:'0',role:'button','data-edge':edge.id,
        'aria-label':graph.relation_kinds[edge.kind]+' : '+byId.get(edge.source).name+' vers '+byId.get(edge.target).name},null,edgeLayer);
      shape('title',{},graph.relation_kinds[edge.kind]+' · '+edge.label,el);
      const hit=shape('path',{d,class:'graph-edge-hit','aria-hidden':'true'},null,edgeLayer);hit.addEventListener('click',()=>showEdge(edge));
      el.addEventListener('click',()=>showEdge(edge));el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();showEdge(edge);detail.querySelector('a,button')?.focus();}});
    }
    for(const node of visible){
      const p=positions.get(node.id),inPath=members.has(node.id),el=shape('g',{transform:'translate('+p.x+','+p.y+')',
        class:'graph-node family-'+node.family+(node.id===selected?' node-selected':'')+(inPath?' path-member':'')+(readingEdge&&node.id===readingEdge.source?' relation-source':'')+(readingEdge&&node.id===readingEdge.target?' relation-target':'')+(readingEdge&&readingStep!==1&&node.id===(readingStep===2?readingEdge.target:readingEdge.source)?' reading-focus':''),
        tabindex:'0',role:'button','data-node':node.id,'aria-label':node.name+' ('+node.type.slice(4)+', révision '+node.reference.revision+')'+(inPath?' : contexte du parcours':'')});
      shape('title',{},node.name+' · '+node.type+' · '+node.description,el);
      shape('rect',{x:-100,y:-34,width:200,height:68,rx:node.local_step?24:4},null,el);
      const short=node.name.length>50?node.name.slice(0,47)+'…':node.name;
      const words=short.split(/\s+/),lines=[''];for(const word of words){let last=lines.length-1;if((lines[last]+' '+word).trim().length>25&&lines[last]&&lines.length<2){lines.push(word);}else{lines[last]=(lines[last]+' '+word).trim();}}
      lines.slice(0,2).forEach((line,i)=>shape('text',{x:-88,y:-12+i*16,class:'graph-node-name'},line.length>28?line.slice(0,26)+'…':line,el));
      shape('text',{x:-88,y:25,class:'graph-node-type'},node.type.slice(4)+' · r'+node.reference.revision,el);
      el.addEventListener('click',()=>choose(node.id));el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose(node.id);detail.querySelector('a,button')?.focus();}});
    }
    const width=Math.max(300,groups.length*236+20),worldHeight=maxRows*88+36;
    // Match the viewport aspect ratio so the initial view is measurable and
    // buttons/keyboard zoom use the same world coordinates as pointer panning.
    const ratio=Math.max(canvas.clientWidth,300)/Math.max(canvas.clientHeight,300);
    const w=Math.max(width,worldHeight*ratio);fullBox={x:(width-w)/2,y:0,w,h:w/ratio};
    const signature=visible.map(n=>n.id).sort().join('|'),viewport=canvas.clientWidth+':'+canvas.clientHeight;
    const overview=document.getElementById('graph-overview');overview.replaceChildren();
    const mini=shape('svg',{viewBox:[fullBox.x,fullBox.y,fullBox.w,fullBox.h].join(' '),tabindex:'0',role:'group','aria-label':'Vue globale. Entrée cadre l’ensemble ; les flèches déplacent la vue.'},null,null);overview.appendChild(mini);
    for(const n of visible){const p=positions.get(n.id);shape('rect',{x:p.x-95,y:p.y-30,width:190,height:60,class:'graph-mini-node family-'+n.family},null,mini);}
    overviewBox=shape('rect',{class:'graph-overview-camera',fill:'none'},null,mini);
    mini.addEventListener('click',e=>{
      const p=mini.createSVGPoint();p.x=e.clientX;p.y=e.clientY;const point=p.matrixTransform(mini.getScreenCTM().inverse());
      moveBox({...box,x:point.x-box.w/2,y:point.y-box.h/2});
    });
    mini.addEventListener('keydown',cameraKeys);
    if(previousBox&&signature===layoutSignature&&viewport===viewportSignature)setBox(previousBox);
    else{
      const readable=Math.min(fullBox.w,Math.max(canvas.clientWidth,360));
      setBox({x:0,y:0,w:readable,h:readable/ratio});
      if(selected&&positions.has(selected))focusNode(selected);
      setBox({...box,y:Math.max(0,box.y)});
    }
    layoutSignature=signature;viewportSignature=viewport;
    document.querySelector('.graph-map').hidden=false;canvas.dataset.graphReady='true';canvas.dataset.visibleNodes=String(visible.length);canvas.dataset.visibleEdges=String(edges.length);
    svg.addEventListener('pointerdown',e=>{if(e.target.closest('[data-node],[data-edge],.graph-edge-hit')||e.button!==0)return;stopCamera(false);drag={x:e.clientX,y:e.clientY,box:{...box}};svg.setPointerCapture(e.pointerId);});
    svg.addEventListener('pointermove',e=>{if(!drag)return;const bounds=svg.getBoundingClientRect();setBox({...drag.box,x:drag.box.x-(e.clientX-drag.x)*drag.box.w/bounds.width,y:drag.box.y-(e.clientY-drag.y)*drag.box.h/bounds.height});});
    svg.addEventListener('pointerup',()=>{drag=null;});svg.addEventListener('pointercancel',()=>{drag=null;});
  }
  document.querySelector('.graph-toolbar').hidden=false;document.querySelector('.graph-camera').hidden=false;
  function applyPreset(key){
    const preset=presets[key],target=firstObject(preset);markPreset(key);
    document.querySelectorAll('[data-graph-family]').forEach(input=>input.checked=preset.families.includes(input.dataset.graphFamily));
    neighbors.checked=true;onlyPath.checked=false;pathSelect.value='';search.value='';typeSelect.value='';choose(target?.id||'');
  }
  document.querySelectorAll('[data-graph-preset]').forEach(button=>button.addEventListener('click',()=>applyPreset(button.dataset.graphPreset)));
  search.addEventListener('input',()=>{if(search.value.trim()){neighbors.checked=false;selected='';selectedEdge='';readingEdge=null;objectSelect.value='';showNode();}render();});
  document.querySelectorAll('[data-graph-family],[data-graph-kind]').forEach(e=>e.addEventListener('change',()=>{markPreset('');render();}));
  [typeSelect,neighbors,onlyPath].forEach(e=>e.addEventListener('change',render));
  pathSelect.addEventListener('change',()=>{
    if(pathSelect.value){
      const path=payload.paths[Number(pathSelect.value)];selected=byRef.get(refKey(path.reference))?.id||'';objectSelect.value=selected;
      selectedEdge='';readingEdge=null;neighbors.checked=false;onlyPath.checked=true;search.value='';typeSelect.value='';
      document.querySelectorAll('[data-graph-family]').forEach(input=>input.checked=true);markPreset('');
    }render();showNode();
  });
  objectSelect.addEventListener('change',()=>choose(objectSelect.value));
  document.querySelectorAll('[data-graph-zoom]').forEach(e=>e.addEventListener('click',()=>e.dataset.graphZoom==='fit'?fit():zoom(e.dataset.graphZoom==='in'?.8:1.25)));
  document.getElementById('graph-center').addEventListener('click',center);
  document.getElementById('graph-reset').addEventListener('click',()=>{for(const [el,value] of defaults)el.checked=value;layoutSignature='';applyPreset('solution');});
  function motionPreference(){motion.disabled=reducedMotion.matches;if(reducedMotion.matches){motion.checked=false;stopCamera(true);}}
  motion.addEventListener('change',()=>{if(!motion.checked)stopCamera(true);});reducedMotion.addEventListener('change',motionPreference);motionPreference();
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stopCamera(true);});window.addEventListener('blur',()=>stopCamera(true));
  function cameraKeys(e){
    if(!box)return;
    if(e.key==='Enter'){e.preventDefault();fit();}
    else if(e.key==='+'||e.key==='='){e.preventDefault();zoom(.8);}
    else if(e.key==='-'){e.preventDefault();zoom(1.25);}
    else if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){
      e.preventDefault();moveBox({...box,x:box.x+({'ArrowLeft':-.12,'ArrowRight':.12}[e.key]||0)*box.w,y:box.y+({'ArrowUp':-.12,'ArrowDown':.12}[e.key]||0)*box.h});
    }
  }
  canvas.addEventListener('keydown',e=>{
    if(e.key==='Escape'){e.preventDefault();choose('');canvas.focus();return;}
    if(e.target!==canvas)return;
    cameraKeys(e);
  });
  applyPreset('solution');
  let resizePending=false;
  new ResizeObserver(()=>{if(resizePending)return;resizePending=true;requestAnimationFrame(()=>{resizePending=false;if(canvas.clientWidth+':'+canvas.clientHeight!==viewportSignature)render();});}).observe(canvas);
})();
