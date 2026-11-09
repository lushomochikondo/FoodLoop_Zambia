(() => {
  const bar = document.querySelector('.page-loading');
  if (!bar) return;
  let timeout;
  const stop = () => {
    clearTimeout(timeout);
    bar.classList.remove('is-active');
    bar.setAttribute('aria-hidden', 'true');
  };
  const start = () => {
    bar.classList.add('is-active');
    bar.setAttribute('aria-hidden', 'false');
    clearTimeout(timeout);
    // Recover if navigation is cancelled or a response becomes a download.
    timeout = setTimeout(stop, 30000);
  };
  document.addEventListener('click', event => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest('a[href]');
    if (!link || link.hasAttribute('download') || (link.target && link.target !== '_self')) return;
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin || !['http:', 'https:'].includes(url.protocol)) return;
    if (url.pathname === location.pathname && url.search === location.search) return;
    start();
  });
  document.addEventListener('submit', event => {
    const form = event.target;
    const target = event.submitter?.formTarget || form.target;
    if (!event.defaultPrevented && form.method !== 'dialog' && (!target || target === '_self')) start();
  });
  window.addEventListener('pageshow', stop);
  window.addEventListener('pagehide', stop);
})();
