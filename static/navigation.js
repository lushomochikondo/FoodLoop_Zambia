const toggle = document.querySelector('#menu-toggle');
const drawer = document.querySelector('#workspace-menu');
const backdrop = document.querySelector('#drawer-backdrop');
const closeButton = document.querySelector('#menu-close');
function setMenu(open) {
  if (!drawer) return;
  drawer.hidden = !open;
  backdrop.hidden = !open;
  toggle.setAttribute('aria-expanded', String(open));
  document.body.classList.toggle('menu-open', open);
  if (open) closeButton.focus();
  else toggle.focus();
}
if (toggle) {
  toggle.addEventListener('click', () => setMenu(drawer.hidden));
  closeButton.addEventListener('click', () => setMenu(false));
  backdrop.addEventListener('click', () => setMenu(false));
  drawer.querySelectorAll('a').forEach(link => link.addEventListener('click', () => setMenu(false)));
  document.addEventListener('keydown', event => {
    if (drawer.hidden) return;
    if (event.key === 'Escape') { setMenu(false); return; }
    if (event.key !== 'Tab') return;
    const items = [...drawer.querySelectorAll('button, a[href]')].filter(el => el.offsetParent !== null);
    const first = items[0], last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
}
