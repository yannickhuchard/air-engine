/* Progressive enhancement: source data stays in the SVG and semantic HTML. */
(() => {
  'use strict';
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  document.querySelectorAll('[data-journey-visual]').forEach(root => {
    const svg=root.querySelector('.jv-svg'), viewport=root.querySelector('.jv-viewport');
    if (!svg || !viewport) return;
    const steps=[...svg.querySelectorAll('[data-jv-step]')], panels=[...root.querySelectorAll('.jv-step-detail')];
    const toolbar=root.querySelector('[data-jv-toolbar]'), status=root.querySelector('.jv-status');
    const tour=root.querySelector('[data-jv-action="tour"]'), actor=root.querySelector('[data-jv-actor]');
    let selected=0, timer=null, scale=1, active=steps.map((_,i)=>i);
    const button=name=>root.querySelector('[data-jv-action="'+name+'"]');
    function stop() {
      if (timer) clearInterval(timer); timer=null;
      tour.setAttribute('aria-pressed','false'); tour.textContent='Visite guidée';
    }
    function position(i) {
      const card=steps[i].querySelector('.jv-card').getBoundingClientRect(), box=viewport.getBoundingClientRect();
      viewport.scrollTo({left:Math.max(0,viewport.scrollLeft+card.left-box.left-(box.width-card.width)/2),
        behavior:reduced.matches?'instant':'smooth'});
    }
    function select(i, move=true, focus=false) {
      if (!active.includes(i)) return;
      selected=i;
      steps.forEach((step,k)=>{
        step.classList.toggle('is-selected',k===i); step.setAttribute('aria-current',k===i?'step':'false');
      });
      panels.forEach((panel,k)=>panel.open=k===i);
      status.textContent=steps[i].getAttribute('aria-label')+' ('+(i+1)+' sur '+steps.length+').';
      const ordinal=active.indexOf(i);
      button('previous').disabled=ordinal===0; button('next').disabled=ordinal===active.length-1;
      if(move)position(i); if(focus)steps[i].focus({preventScroll:true});
      root.dataset.selectedStep=String(i);
    }
    steps.forEach((step,i)=>{
      step.addEventListener('click',e=>{
        // Compact views link to the dedicated page with its complete detail panel.
        if (!panels.length || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
        e.preventDefault(); stop(); select(i);
      });
      step.addEventListener('keydown',e=>{
        if(!['ArrowRight','ArrowLeft','Home','End'].includes(e.key))return;
        e.preventDefault();stop();
        const p=active.indexOf(selected), next=e.key==='Home'?0:e.key==='End'?active.length-1:
          Math.max(0,Math.min(active.length-1,p+(e.key==='ArrowRight'?1:-1)));
        select(active[next],true,true);
      });
    });
    panels.forEach((panel,i)=>panel.querySelector('summary').addEventListener('click',e=>{
      e.preventDefault();stop();select(i);
    }));
    button('previous').addEventListener('click',()=>{stop();select(active[Math.max(0,active.indexOf(selected)-1)]);});
    button('next').addEventListener('click',()=>{stop();select(active[Math.min(active.length-1,active.indexOf(selected)+1)]);});
    tour.addEventListener('click',()=>{
      if(timer){stop();return;}
      select(active[0]);tour.setAttribute('aria-pressed','true');tour.textContent='Arrêter la visite';
      timer=setInterval(()=>{
        const p=active.indexOf(selected)+1;
        if(p>=active.length){stop();return;} select(active[p]);
      },4000);
    });
    button('fit').addEventListener('click',()=>{
      stop();root.dataset.overview='true';svg.style.width='100%';svg.style.minWidth='0';svg.style.height='auto';
      scale=svg.getBoundingClientRect().width/svg.viewBox.baseVal.width;
      viewport.scrollLeft=0;status.textContent='Vue d’ensemble. Choisir une étape pour ses détails.';
    });
    function zoom(next) {
      stop();root.dataset.overview='false';scale=Math.max(.25,Math.min(2,next));
      svg.style.width=(svg.viewBox.baseVal.width*scale)+'px';svg.style.minWidth='0';svg.style.height='auto';position(selected);
      status.textContent='Carte à '+Math.round(scale*100)+' %. '+steps[selected].getAttribute('aria-label');
    }
    button('zoom').addEventListener('click',()=>zoom(scale+.25));
    button('reduce').addEventListener('click',()=>zoom(scale-.25));
    button('read').addEventListener('click',()=>zoom(1));
    root.querySelector('[data-jv-layer]').addEventListener('change',e=>{
      stop();root.dataset.layer=e.target.value;
      status.textContent='Lecture : '+e.target.selectedOptions[0].textContent+'. Les autres dimensions restent disponibles.';
    });
    actor.addEventListener('change',()=>{
      stop();active=actor.value?actor.value.split(',').map(Number):steps.map((_,i)=>i);
      steps.forEach((step,i)=>{
        const muted=!active.includes(i);step.classList.toggle('is-muted',muted);step.setAttribute('tabindex',muted?'-1':'0');
      });
      panels.forEach((panel,i)=>panel.hidden=!active.includes(i));select(active.includes(selected)?selected:active[0]);
      status.textContent+=' '+active.length+' étape(s) pour '+actor.selectedOptions[0].textContent+'.';
    });
    const hash=location.hash.slice(1), requested=panels.findIndex(p=>p.id===hash);
    select(requested>=0?requested:0,false); toolbar.hidden=false;root.dataset.journeyReady='true';
    if(viewport.clientWidth>=900 && steps.length<=4){
      root.dataset.overview='true';
      svg.style.width='100%';svg.style.minWidth='0';svg.style.height='auto';
      scale=svg.getBoundingClientRect().width/svg.viewBox.baseVal.width;
    }
    if(innerWidth<700 || requested>=0)position(selected);
    document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
    window.addEventListener('pagehide',stop);
    viewport.addEventListener('keydown',e=>{if(e.key==='Escape')stop();});
  });
})();
