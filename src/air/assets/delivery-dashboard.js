'use strict';
(() => {
  for (const root of document.querySelectorAll('[data-delivery]')) {
    const form = root.querySelector('form');
    const rows = [...root.querySelectorAll('[data-delivery-task]')];
    const control = name => form.querySelector(`[data-filter="${name}"]`);
    const isoMonday = value => {
      if (!value) return null;
      const [year, week] = value.split('-W').map(Number);
      const jan4 = new Date(Date.UTC(year, 0, 4));
      jan4.setUTCDate(jan4.getUTCDate() - ((jan4.getUTCDay() + 6) % 7) + 7 * (week - 1));
      return jan4;
    };
    const apply = () => {
      let count = 0, done = 0, cancelled = 0, blocked = 0, overdue = 0;
      const monday = isoMonday(control('week').value);
      const sunday = monday && new Date(monday.getTime() + 6 * 86400000);
      const asOf = control('as-of').value;
      for (const row of rows) {
        const d = row.dataset;
        const late = !!(d.active === 'true' && d.due && d.due < asOf);
        const start = d.start || d.due;
        const inWeek = !monday || !!(start && d.due && new Date(start + 'T00:00:00Z') <= sunday && new Date(d.due + 'T00:00:00Z') >= monday);
        row.hidden = !!((control('team').value && d.team !== control('team').value) ||
          (control('member').value && !JSON.parse(d.members).includes(control('member').value)) ||
          (control('late').checked && !late) || (control('blocked').checked && d.blocked !== 'true') || !inWeek);
        const days = late ? Math.round((Date.parse(asOf + 'T00:00:00Z') - Date.parse(d.due + 'T00:00:00Z')) / 86400000) : 0;
        row.querySelector('[data-late]').textContent = late ? `Retard : ${days} jour(s)` : '';
        if (!row.hidden) {
          count++;
          if (d.status === 'DONE') done++;
          if (d.status === 'CANCELLED') cancelled++;
          if (d.blocked === 'true') blocked++;
          if (late) overdue++;
        }
      }
      root.querySelector('[data-delivery-count]').textContent = `${count} tâche(s) affichée(s).`;
      const denominator = count - cancelled;
      const percent = denominator ? Math.round(100 * done / denominator) : null;
      root.querySelector('[data-delivery-progress]').textContent = `${done} terminée(s), ${blocked} bloquée(s), ${overdue} en retard, ${cancelled} annulée(s). ` + (percent === null ? 'Avancement non calculable.' : `${percent} % des tâches non annulées.`);
      root.querySelector('[data-delivery-bar]').value = percent || 0;
    };
    form.addEventListener('submit', e => e.preventDefault());
    form.addEventListener('input', apply);
    form.addEventListener('reset', () => setTimeout(apply, 0));
    apply();
  }
})();
