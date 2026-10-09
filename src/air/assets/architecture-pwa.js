'use strict';
(async function () {
  const root = new URL('../', document.currentScript.src);
  const status = document.getElementById('pwa-status');
  const enable = document.getElementById('pwa-enable'), clear = document.getElementById('pwa-clear');
  const update = document.getElementById('pwa-update'), install = document.getElementById('pwa-install');
  const local = ['localhost','127.0.0.1','[::1]'].includes(location.hostname);
  if (!(location.protocol === 'https:' || (location.protocol === 'http:' && local)) || !('serviceWorker' in navigator)) {
    status.textContent = 'Lecture directe disponible. Pour installer et conserver ce site dans le navigateur, ouvrez-le via le serveur local AIR (ou HTTPS).';
    return;
  }
  const manifest = document.createElement('link');manifest.rel = 'manifest';
  manifest.href = new URL('manifest.webmanifest', root).href;document.head.append(manifest);
  enable.hidden = false;
  status.textContent = 'Vous pouvez conserver tous les sujets et diagrammes de ce site hors ligne. Les exports liés en dehors du site restent sur disque.';
  let registration = await navigator.serviceWorker.getRegistration(root.href), deferred;
  let removing = false, applying = false;
  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault();deferred = event;install.hidden = false;
  });
  install.addEventListener('click', async () => {
    if (!deferred) return;
    await deferred.prompt();await deferred.userChoice;deferred = null;install.hidden = true;
  });
  function watch(reg) {
    clear.hidden = false;
    if (reg.active) {enable.hidden = true;status.textContent = 'Site conservé hors ligne dans ce navigateur. Les données sont une copie de cette génération.';}
    if (reg.waiting) {update.hidden = false;status.textContent = 'Une nouvelle version complète est prête. Appliquez-la pour actualiser toutes les pages.';}
    reg.addEventListener('updatefound', () => {
      const worker = reg.installing;
      if (!worker) return;
      worker.addEventListener('statechange', () => {
        if (worker.state === 'installed' && reg.active) watch(reg);
        if (worker.state === 'activated') watch(reg);
        if (worker.state === 'redundant') {enable.hidden = false;enable.disabled = false;status.textContent = 'La copie a échoué (fichier modifié, stockage insuffisant ou serveur indisponible). La version précédente reste conservée. Relancez le serveur après régénération puis réessayez.';}
      });
    });
  }
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (removing) return;
    if (applying) {location.reload();return;}
    // First activation is complete; other open pages may still show the old
    // generation. Reload explicitly instead of silently changing their reading.
    status.textContent = 'Copie hors ligne prête. Rechargez cette page si vous aviez déjà une version ouverte.';
    enable.hidden = true;enable.disabled = false;
  });
  if (registration && registration.scope === root.href) {
    watch(registration);registration.update().catch(() => {});
  } else registration = null;
  enable.addEventListener('click', async () => {
    enable.disabled = true;status.textContent = 'Vérification et conservation de tous les fichiers… Gardez cette page ouverte.';
    try {
      registration = await navigator.serviceWorker.register(new URL('sw.js', root), {scope:root.href, updateViaCache:'none'});
      watch(registration);
      // register() may return after updatefound; watch the current installer too.
      const worker = registration.installing;
      if (worker) worker.addEventListener('statechange', () => {
        if (worker.state === 'activated' || worker.state === 'installed') watch(registration);
        if (worker.state === 'redundant') {enable.disabled = false;status.textContent = 'Copie incomplète. Vérifiez le serveur et l’espace disponible, puis réessayez.';}
      });
      else enable.disabled = false;
    } catch (_) {enable.disabled = false;status.textContent = 'Impossible de conserver le site. Vérifiez le serveur local et les autorisations de stockage du navigateur.';}
  });
  update.addEventListener('click', () => {
    if (registration && registration.waiting) {applying = true;registration.waiting.postMessage('AIR_APPLY_VERSION');}
  });
  clear.addEventListener('click', async () => {
    clear.disabled = true;removing = true;
    try {
      if (registration) await registration.unregister();
      const prefix = 'air-site:' + encodeURIComponent(root.pathname) + ':';
      for (const name of await caches.keys()) if (name.startsWith(prefix)) await caches.delete(name);
      clear.hidden = true;update.hidden = true;enable.hidden = false;enable.disabled = false;
      status.textContent = 'Copie hors ligne effacée. Fermez ces pages pour terminer la déconnexion de l’ancienne version ; les fichiers sur disque sont conservés.';
    } catch (_) {status.textContent = 'Effacement incomplet. Fermez les pages puis effacez les données de ce site dans le navigateur.';}
    finally {clear.disabled = false;}
  });
})().catch(() => {
  document.getElementById('pwa-status').textContent = 'Le stockage hors ligne est indisponible dans ce navigateur. La lecture du site reste disponible.';
});
