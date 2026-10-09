/* Presentation time is never execution time. No fetch, registry mutation or eval. */
(() => {
  'use strict';
  const node = document.getElementById('air-story');
  if (!node) return;
  const model = JSON.parse(node.textContent), controls = document.querySelector('.story-controls');
  const seek = document.getElementById('story-seek'), clock = document.getElementById('story-clock');
  const play = document.getElementById('story-play'), status = document.getElementById('story-status');
  const chapters = [...document.querySelectorAll('.story-chapter')];
  const links = [...document.querySelectorAll('[data-story-chapter]')];
  let playing = false, start = 0, offset = 0, frame = 0;
  function select(id) {
    chapters.forEach(c => { c.hidden = c.id !== 'story-' + id; });
    links.forEach(l => {
      if (l.dataset.storyChapter === id) l.setAttribute('aria-current', 'step');
      else l.removeAttribute('aria-current');
    });
  }
  function pose(time) {
    const t = Math.max(0, Math.min(model.duration_seconds, time));
    const i = model.timings.slice(1, -1).filter(v => t >= v).length;
    select(model.phase_ids[i]); seek.value = String(t);
    clock.textContent = t.toFixed(1) + ' / 24 s';
    status.textContent = model.structure[i] + ' · Animation narrative ; gardes non évaluées.';
  }
  function pause() { playing = false; cancelAnimationFrame(frame); play.textContent = 'Lire le récit court'; }
  function tick(now) {
    const t = offset + (now - start) / 1000; pose(t);
    if (t >= model.duration_seconds) { pause(); return; }
    frame = requestAnimationFrame(tick);
  }
  play.addEventListener('click', () => {
    if (playing) { pause(); return; }
    offset = Number(seek.value) >= model.duration_seconds ? 0 : Number(seek.value);
    start = performance.now(); playing = true; play.textContent = 'Mettre en pause'; pose(offset);
    frame = requestAnimationFrame(tick);
  });
  seek.addEventListener('input', () => { pause(); pose(Number(seek.value)); });
  links.forEach(l => l.addEventListener('click', () => { pause(); select(l.dataset.storyChapter); status.textContent = 'Lecture du chapitre · aucune exécution métier.'; }));
  document.addEventListener('visibilitychange', () => { if (document.hidden) pause(); });
  controls.hidden = false;
  const initial = location.hash.replace('#story-', '');
  if (chapters.some(c => c.id === 'story-' + initial)) select(initial);
  // No autoplay, no motion transforms. Full text remains available without JS.
})();
