'use strict';
(() => {
  for (const root of document.querySelectorAll('[data-stakeholders-map]')) {
    const tools = root.querySelector('[data-stakeholder-tools]');
    if (!tools) continue;
    const filters = [...root.querySelectorAll('[data-stakeholder-filter]')];
    const search = root.querySelector('[data-stakeholder-search]');
    const nodes = [...root.querySelectorAll('[data-stakeholder-target]')];
    const entries = [...root.querySelectorAll('[data-stakeholder-state]')];
    const inspector = root.querySelector('.stakeholder-inspector');
    const back = root.querySelector('[data-stakeholder-back]');
    let state = '', selected = '';
    const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase();
    const select = (id, navigate = false) => {
      const target = entries.find(entry => entry.id === id);
      const node = nodes.find(item => item.dataset.stakeholderTarget === id);
      if (!target || !node || node.hidden) return;
      selected = id;
      nodes.forEach(item => {
        if (item === node) item.setAttribute('aria-current', 'true');
        else item.removeAttribute('aria-current');
      });
      entries.forEach(entry => { entry.hidden = entry !== target; });
      target.open = true; inspector.hidden = false;
      if (navigate) {
        root.classList.add('is-detail-open');
        if (!matchMedia('(prefers-reduced-motion: reduce)').matches) {
          target.animate?.([{opacity: .55, transform: 'translateY(4px)'}, {opacity: 1, transform: 'translateY(0)'}], {duration: 160, easing: 'ease-out'});
        }
        try { history.replaceState(null, '', '#' + id); } catch { /* Sandboxed previews may restrict history. */ }
        target.querySelector('summary').focus({preventScroll: true});
        if (getComputedStyle(root.querySelector('.stakeholder-workspace')).gridTemplateColumns.split(' ').length === 1) {
          inspector.scrollIntoView({block: 'start', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
        }
      }
    };
    const apply = () => {
      const terms = normalize(search.value).trim().split(/\s+/).filter(Boolean);
      const visible = nodes.filter(node => {
        node.hidden = !!(state && node.dataset.state !== state) || !terms.every(term => normalize(node.dataset.search).includes(term));
        return !node.hidden;
      });
      root.querySelectorAll('[data-stakeholder-group]').forEach(group => {
        const count = [...group.querySelectorAll('[data-stakeholder-target]')].filter(node => !node.hidden).length;
        group.hidden = !count; group.querySelector('.stakeholder-group-count').textContent = count;
      });
      filters.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.stakeholderFilter === state)));
      root.querySelector('[data-stakeholder-count]').textContent = `${visible.length} contribution(s) sur ${nodes.length}. Une personne peut tenir plusieurs rôles.`;
      root.querySelector('[data-stakeholder-empty]').hidden = !!visible.length;
      root.querySelector('.stakeholder-project').hidden = !visible.length;
      root.querySelector('.stakeholder-branches').hidden = !visible.length;
      if (visible.length) select(visible.some(node => node.dataset.stakeholderTarget === selected) ? selected : visible[0].dataset.stakeholderTarget);
      else { entries.forEach(entry => { entry.hidden = true; }); inspector.hidden = true; }
    };
    const reveal = () => {
      const target = entries.find(entry => '#' + entry.id === location.hash);
      if (!target) return;
      state = ''; search.value = ''; apply(); select(target.id, true);
    };
    filters.forEach(button => button.addEventListener('click', () => { state = button.dataset.stakeholderFilter; apply(); }));
    search.addEventListener('input', apply);
    nodes.forEach(node => node.addEventListener('click', event => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault(); select(node.dataset.stakeholderTarget, true);
    }));
    root.querySelector('[data-stakeholder-reset]').addEventListener('click', () => { state = ''; search.value = ''; apply(); search.focus(); });
    const returnToMap = () => {
      root.classList.remove('is-detail-open');
      const node = nodes.find(item => item.dataset.stakeholderTarget === selected);
      if (node && !node.hidden) { node.focus({preventScroll: true}); node.scrollIntoView({block: 'center'}); }
    };
    back.addEventListener('click', returnToMap);
    inspector.addEventListener('keydown', event => { if (event.key === 'Escape') returnToMap(); });
    window.addEventListener('hashchange', reveal);
    window.addEventListener('beforeprint', () => {
      root.classList.remove('is-interactive');
      entries.forEach(entry => { entry.hidden = false; entry.open = true; });
      inspector.hidden = false;
    });
    window.addEventListener('afterprint', () => { root.classList.add('is-interactive'); apply(); });
    root.classList.add('is-interactive'); tools.hidden = false; back.hidden = false;
    apply(); reveal();
  }
})();
