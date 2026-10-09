'use strict';
(function () {
  const embedded=document.getElementById('air-temporal');if(!embedded)return;
  const payload=JSON.parse(embedded.textContent),data=payload.temporal;
  const el=id=>document.getElementById(id),comparison=el('temporal-comparison'),snapshot=el('temporal-snapshot');
  const boundary=el('temporal-boundary'),slider=el('temporal-slider'),search=el('temporal-search'),kind=el('temporal-kind');
  function html(tag,text,parent,attrs={}) {
    const node=document.createElement(tag);if(text!==null)node.textContent=String(text).replace(/\u2014/g,'-');
    for(const [k,v] of Object.entries(attrs))node.setAttribute(k,v);if(parent)parent.appendChild(node);return node;
  }
  function normalize(text){return text.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase();}
  function sourceLink(info,state,parent,text=info.name){
    const href=payload.links[state.digest].objects[info.reference.id+'\u0000'+info.reference.revision];
    return html('a',text,parent,{href});
  }
  function objectDetails(info,state,parent,label){
    html('h3',label,parent);sourceLink(info,state,parent);
    html('p',info.type.slice(4)+' · r'+info.reference.revision+' · '+info.lifecycle,parent);
    html('p',info.description,parent);html('p','Identité : '+info.reference.id,parent);
    html('p','Empreinte : '+info.reference.digest,parent);
    html('p','Validité déclarée : ['+info.validity.start+', '+(info.validity.end||'fin non déclarée')+')',parent);
    html('p','Date auteur : '+info.author_recorded_at+' (pas la réception dans le registre)',parent);
  }
  function showChange(group,c){
    const panel=el('temporal-detail');panel.replaceChildren();html('h2',data.change_labels[group.status],panel);
    html('p',group.id,panel);
    group.before.forEach(o=>objectDetails(o,c.before,panel,'État A'));
    group.after.forEach(o=>objectDetails(o,c.after,panel,'État B'));
    if(group.status==='MULTIPLE_REVISIONS')html('p','Plusieurs révisions figurent dans un même état. Elles restent séparées ; aucune paire de champs n’est choisie arbitrairement.',panel);
    if(group.fields.length){
      const details=html('details',null,panel);html('summary',group.fields.length+' champ(s) différent(s)',details);
      for(const field of group.fields){html('h4',field.path+' · '+field.change,details);
        if('before' in field)html('pre',JSON.stringify(field.before,null,2),details);
        if('after' in field)html('pre',JSON.stringify(field.after,null,2),details);}
    }
  }
  function drawComparison(){
    const target=el('temporal-diff'),status=el('temporal-comparison-status'),links=el('temporal-state-links');
    target.replaceChildren();links.replaceChildren();el('temporal-detail').replaceChildren();
    html('h3','Lire un changement',el('temporal-detail'));html('p','Choisissez une ligne pour lire ses champs et ses sources.',el('temporal-detail'));
    if(!data.comparisons.length){status.textContent='Aucune comparaison choisie. Déclarez une paire de baselines exactes lors de la génération.';el('temporal-diff-count').textContent='';return;}
    const c=data.comparisons[Number(comparison.value)],a=data.snapshots.find(s=>s.baseline.digest===c.before.digest),b=data.snapshots.find(s=>s.baseline.digest===c.after.digest);
    status.textContent=('État A : '+a.name+' ; état B : '+b.name+'. '+(!c.same_namespace?'Les périmètres diffèrent. ':'')+'La comparaison n’établit ni compatibilité ni réalisation.').replace(/\u2014/g,'-');
    for(const [label,state] of [['Ouvrir le graphe de l’état A',c.before],['Ouvrir le graphe de l’état B',c.after]])html('a',label,links,{href:payload.links[state.digest].graph});
    const words=normalize(search.value).split(/\s+/).filter(Boolean);
    const rows=c.objects.filter(g=>(kind.value==='ALL'||kind.value==='CHANGED'&&g.status!=='UNCHANGED'||g.status===kind.value)&&words.every(w=>normalize(g.id+' '+[...g.before,...g.after].map(o=>o.name+' '+o.type+' '+o.description).join(' ')).includes(w)));
    el('temporal-diff-count').textContent=rows.length+' objet(s) correspondant aux filtres, '+Math.min(150,rows.length)+' présenté(s).'+(rows.length>150?' Précisez la recherche ; le JSON conserve la liste complète.':'');
    const heading=html('div',null,target,{class:'temporal-pair temporal-pair-heading'});html('span','État A',heading);html('span','État B',heading);
    for(const group of rows.slice(0,150)){
      const row=html('div',null,target,{class:'temporal-pair change-'+group.status,'data-temporal-change':group.status});
      for(const [label,objects] of [['A',group.before],['B',group.after]]){
        const button=html('button',null,row,{type:'button','aria-label':data.change_labels[group.status]+' : '+(objects[0]?.name||'Objet absent')+', état '+label});
        html('strong',objects.map(o=>o.name).join(' / ')||'Absent de cet état',button);
        html('span',objects.map(o=>o.type.slice(4)+' r'+o.reference.revision).join(' / ')||'-',button);
        html('span',data.change_labels[group.status],button);button.addEventListener('click',()=>{showChange(group,c);el('temporal-detail').querySelector('a')?.focus();});
      }
    }
    if(!rows.length)html('p','Aucun résultat. Changez le filtre ou la recherche.',target);
  }
  function drawValidity(){
    const s=data.snapshots[Number(snapshot.value)],i=Number(boundary.value||0),t=s.validity_boundaries[i];
    slider.value=String(i);const target=el('temporal-validity');target.replaceChildren();
    if(!t){el('temporal-validity-status').textContent='Aucun objet ne porte une date de validité.';return;}
    // Canonical UTC keys retain microseconds. Date.parse is used only for drawing
    // coordinates below; it never decides inclusion at a half-open boundary.
    const active=s.objects.filter(o=>o.valid_start<=t&&(o.valid_end===null||t<o.valid_end));
    el('temporal-validity-status').textContent=t+' : '+active.length+' objet(s) valide(s) selon leur déclaration sur '+s.objects.length+'. '+Math.min(150,active.length)+' ligne(s) présentée(s).'+(active.length>150?' Le JSON conserve tous les objets.':'')+' Cette sélection ne forme pas une nouvelle baseline fermée.';
    const times=s.validity_boundaries.map(v=>Date.parse(v)),first=Math.min(...times),last=Math.max(...times),span=Math.max(86400000,last-first);
    const scale=v=>Math.max(0,Math.min(100,(Date.parse(v)-first)*100/span));
    html('p','Étendue des dates déclarées : '+s.validity_boundaries[0]+' → '+s.validity_boundaries.at(-1),target,{class:'temporal-time-axis'});
    for(const o of active.slice(0,150)){
      const row=html('div',null,target,{class:'temporal-time-row','data-valid-object':o.reference.id});
      sourceLink(o,s.baseline,row,o.name+' · r'+o.reference.revision);
      const track=html('div',null,row,{class:'temporal-time-track','aria-hidden':'true'});
      const left=scale(o.valid_start),right=o.valid_end?scale(o.valid_end):100;
      const bar=html('span',null,track,{class:'temporal-time-bar'+(o.valid_end===null?' open-end':'')});
      bar.style.left=left+'%';bar.style.width=Math.max(1,right-left)+'%';
      const cursor=html('span',null,track,{class:'temporal-time-cursor'});cursor.style.left=scale(t)+'%';
      html('small','['+o.validity.start+', '+(o.validity.end||'fin non déclarée')+')',row);
    }
    if(!active.length)html('p','Aucun objet n’est déclaré valide à cet instant. Choisissez une autre frontière ou un autre état.',target);
  }
  function selectSnapshot(){
    const s=data.snapshots[Number(snapshot.value)];boundary.replaceChildren();
    s.validity_boundaries.forEach((v,i)=>html('option',v,boundary,{value:i}));
    slider.max=String(Math.max(0,s.validity_boundaries.length-1));slider.value='0';
    slider.disabled=!s.validity_boundaries.length;boundary.disabled=slider.disabled;
    const plans=el('temporal-plans');plans.replaceChildren();
    const validPlans=s.plans.filter(p=>p.dates_valid),dates=validPlans.map(p=>p.start).sort();
    if(s.plans.length){
      const first=Date.parse(dates[0]),last=Math.max(...validPlans.map(p=>Date.parse(p.end||p.start))),span=Math.max(86400000,last-first);
      for(const p of s.plans.slice(0,150)){
        const row=html('div',null,plans,{class:'temporal-time-row'}),source=s.objects.find(o=>o.reference.id===p.source.id&&o.reference.revision===p.source.revision);
        sourceLink(source,s.baseline,row,p.name);
        const track=html('div',null,row,{class:'temporal-time-track','aria-hidden':'true'});
        const bar=html('span',null,track,{class:'temporal-time-bar planned'});
        if(p.dates_valid&&Number.isFinite(first)&&Number.isFinite(last)){
          bar.style.left=((Date.parse(p.start)-first)*100/span)+'%';bar.style.width=Math.max(1,(Date.parse(p.end||p.start)-Date.parse(p.start))*100/span)+'%';
        }
        html('small',p.start+(p.end?' → '+p.end:'')+' · prévu'+(p.dates_valid?'':' · date invalide à corriger'),row);
        if(p.criteria.length)html('p','Critères déclarés : '+p.criteria.join(' ; '),row);
      }
      html('p',s.plans.length+' jalon(s)/phase(s), '+Math.min(150,s.plans.length)+' présenté(s). Les dates ne sont pas des constats d’exécution.',plans);
    }else html('p','Aucun jalon ou phase de roadmap déclaré pour cet état.',plans);
    if(s.gaps.length)html('p',s.gaps.length+' anomalie(s) de date déclarée. Consultez le JSON et les sources avant de lire le calendrier.',plans);
    drawValidity();
  }
  data.comparisons.forEach((c,i)=>html('option',c.title,comparison,{value:i}));comparison.disabled=!data.comparisons.length;
  data.snapshots.forEach((s,i)=>html('option',s.name+' · r'+s.baseline.revision,snapshot,{value:i}));
  html('option','Tous les changements',kind,{value:'CHANGED'});html('option','Tous les objets',kind,{value:'ALL'});
  for(const [k,label] of Object.entries(data.change_labels))html('option',label,kind,{value:k});
  comparison.addEventListener('change',drawComparison);kind.addEventListener('change',drawComparison);search.addEventListener('input',drawComparison);
  snapshot.addEventListener('change',selectSnapshot);boundary.addEventListener('change',drawValidity);
  slider.addEventListener('input',()=>{boundary.value=slider.value;drawValidity();});
  el('temporal-interactive').hidden=false;drawComparison();selectSnapshot();el('temporal-interactive').dataset.ready='true';
})();
