if ('serviceWorker' in navigator && window.isSecureContext) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/service-worker.js').catch(() => {}));
}
let installPrompt;
const installButton = document.querySelector('#install-app');
window.addEventListener('beforeinstallprompt', event => {
  event.preventDefault();
  installPrompt = event;
  if (installButton) installButton.hidden = false;
});
if (installButton) installButton.addEventListener('click', async () => {
  if (!installPrompt) return;
  await installPrompt.prompt();
  installPrompt = null;
  installButton.hidden = true;
});
window.addEventListener('appinstalled', () => { if (installButton) installButton.hidden = true; });
