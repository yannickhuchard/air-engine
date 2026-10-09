'use strict';
(() => {
  const filter = document.getElementById('sankey-filter');
  if (!filter) return;
  filter.addEventListener('change', () => {
    const selected = filter.value;
    document.querySelectorAll('[data-requirements]').forEach(element => {
      element.classList.toggle('trace-dimmed', Boolean(selected) && !element.dataset.requirements.split(' ').includes(selected));
    });
    let count = 0;
    document.querySelectorAll('.sankey-paths').forEach(element => {
      element.hidden = Boolean(selected) && element.dataset.requirement !== selected;
      if (!element.hidden) count++;
    });
    document.getElementById('sankey-status').textContent = selected ? 'Exigence mise en évidence. Ses chemins et sources sont affichés sous le graphique.' : count + ' exigences : tous les chemins sont affichés.';
  });
})();
(async function () {
  const nav = document.querySelector('.workspace-nav');
  const compact = window.matchMedia('(max-width: 900px)');
  function navigationLayout() { if (nav) nav.open = !compact.matches; }
  navigationLayout();compact.addEventListener('change', navigationLayout);
  document.querySelectorAll('.workspace-nav nav details').forEach(group => {
    group.open = Boolean(group.querySelector('[aria-current="page"]'));
  });
  const nodeInfo = JSON.parse(document.getElementById('air-nodes').textContent);
  function kind(type) {
    if (['Concept','DataEntity','PhysicalTable','Message','Event','DataSchema'].includes(type)) return 'data';
    if (['ArchitectureBlock','RuntimeComponent','Device','NetworkZone'].includes(type)) return 'component';
    if (['Decision','Risk','BusinessRule','Control'].includes(type)) return 'decision';
    return 'process';
  }
  function reveal() {
    const id = location.hash.slice(1), target = document.getElementById(id);
    if (!target) return;
    for (let element = target; element; element = element.parentElement) {
      if (element.tagName === 'DETAILS') element.open = true;
      if (element.hidden) element.hidden = false;
    }
    target.scrollIntoView({block:'start'});
  }
  window.addEventListener('hashchange', reveal); reveal();
  function filter(inputId, selector, statusId) {
    const input = document.getElementById(inputId), status = document.getElementById(statusId);
    if (!input) return;
    const entries = [...document.querySelectorAll(selector)];
    input.addEventListener('input', () => {
      const words = input.value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase().split(/\s+/).filter(Boolean);
      let shown = 0;
      for (const item of entries) {
        const text = item.textContent.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase();
        item.hidden = !words.every(w => text.includes(w)); if (!item.hidden) shown++;
      }
      status.textContent = shown ? shown + ' résultat(s)' : 'Aucun résultat. Essayez un autre nom ou une autre définition.';
    });
  }
  filter('object-search','.object','object-search-status');
  filter('dossier-search','.dossier','dossier-search-status');
  filter('path-search','.business-path','path-search-status');
  filter('question-search','.question-card','question-search-status');
  if (!window.mermaid) return;
  mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'neutral',fontFamily:'Segoe UI, sans-serif',
    suppressErrorRendering:true,maxTextSize:200000,maxEdges:4000,flowchart:{htmlLabels:false},er:{useMaxWidth:false},
    secure:['securityLevel','startOnLoad','maxTextSize','maxEdges','suppressErrorRendering']});
  let n = 0;
  for (const element of document.querySelectorAll('.mermaid')) {
    const figure = element.closest('figure'), status = figure.querySelector('.diagram-status');
    const source = element.textContent;
    try {
      const rendered = await mermaid.render('air-diagram-' + (++n), source);
      // Only sanitized SVG from the pinned strict renderer is accepted here.
      element.innerHTML = rendered.svg;
      const svg = element.querySelector('svg');
      const viewBox = svg.viewBox.baseVal, width = Math.max(viewBox.width, 300);
      svg.style.width = Math.min(width, Math.max(figure.clientWidth - 40,300)) + 'px';
      let scale = parseFloat(svg.style.width) / width;
      figure.querySelectorAll('[data-zoom]').forEach(button => button.addEventListener('click', () => {
        scale = button.dataset.zoom === 'reset' ? Math.min(1,Math.max(figure.clientWidth - 40,300)/width) : Math.max(.15,Math.min(4,scale*(button.dataset.zoom === 'in' ? 1.25 : .8)));
        svg.style.width = width * scale + 'px';
      }));
      for (const node of nodeInfo) {
        // Mermaid emits nodes under different prefixes depending on diagram type.
        const matches = [...svg.querySelectorAll('g[id]')].filter(g => g.id === node.node || g.id.startsWith('flowchart-' + node.node + '-') || g.id.includes('-flowchart-' + node.node + '-') || g.id.includes('-entity-' + node.node + '-') || g.id.startsWith('entity-' + node.node + '-'));
        for (const match of matches) {
          match.classList.add('air-' + kind(node.type),'air-linked');
          match.setAttribute('tabindex','0');match.setAttribute('role','link');
          match.setAttribute('aria-label',node.name + ' (' + node.type + ') : ouvrir la définition');
          match.addEventListener('click', () => { location.href = node.href; });
          match.addEventListener('keydown', e => { if (e.key === 'Enter') location.href = node.href; });
        }
      }
      status.textContent = 'Diagramme du modèle déclaré. Utilisez les boutons pour changer d’échelle.';
      figure.dataset.rendered = 'true';
    } catch (_) {
      status.textContent = 'Le dessin n’a pas pu être affiché. Sa source complète reste disponible ci-dessous.';
      figure.querySelector('.diagram-source').open = true;figure.dataset.rendered = 'false';
      element.textContent = source;
    }
  }
  document.body.dataset.diagramsReady = 'true';
})();

(() => {
  const choice = document.getElementById('journey-persona');
  if (!choice) return;
  const cards = [...document.querySelectorAll('.persona-journeys')];
  choice.addEventListener('change', () => {
    cards.forEach(card => { card.hidden = !!choice.value && card.dataset.persona !== choice.value; });
    document.getElementById('journey-filter-status').textContent = cards.filter(card => !card.hidden).length + ' persona(s) affiché(s).';
  });
})();
