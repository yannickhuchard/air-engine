'use strict';
(async () => {
  if (!window.BpmnJS) return;
  for (const figure of document.querySelectorAll('.process-diagram')) {
    const container = figure.querySelector('.process-viewer');
    const status = figure.querySelector('.process-status');
    let viewer;
    try {
      const data = JSON.parse(figure.querySelector('.bpmn-data').textContent);
      container.hidden = false;
      container.style.height = Math.min(660, Math.max(380, data.height)) + 'px';
      viewer = new BpmnJS({container, textRenderer:{defaultStyle:{fontFamily:'Segoe UI, sans-serif',fontSize:14},externalStyle:{fontSize:12}}});
      const result = await viewer.importXML(data.xml);
      if (result.warnings.length) throw new Error('BPMN import warnings');
      const canvas = viewer.get('canvas');
      function readingView() { canvas.viewbox({x:container.clientWidth<600?240:40,y:50,width:container.clientWidth,height:container.clientHeight}); }
      readingView();
      // The official watermark remains fully visible, as required by its license.
      figure.querySelector('.process-fallback').hidden = true;
      figure.querySelector('.process-tools').hidden = false;
      figure.querySelectorAll('[data-bpmn-zoom]').forEach(button => button.addEventListener('click', () => {
        const action = button.dataset.bpmnZoom;
        if(action === 'read') readingView();
        else canvas.zoom(action === 'fit' ? 'fit-viewport' : Math.min(3, Math.max(.2, canvas.zoom() * (action === 'in' ? 1.25 : .8))));
        status.textContent = 'BPMN descriptif, échelle ' + Math.round(canvas.zoom() * 100) + ' %. Les activités et conditions complètes figurent sur la page de focus.';
      }));
      figure.dataset.bpmnReady = 'true';
      status.textContent = 'BPMN descriptif. Glisser pour explorer ; taille de lecture 100 %. Export et détail complet sur la page du processus.';
    } catch (_) {
      if (viewer) viewer.destroy();
      container.hidden = true;
      figure.dataset.bpmnReady = 'false';
      status.textContent = 'Lecteur interactif indisponible. Le dessin statique et le détail complet restent accessibles.';
    }
  }
})();
