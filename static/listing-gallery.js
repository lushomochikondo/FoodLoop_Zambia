(() => {
  const gallery = document.querySelector('[data-gallery]');
  if (!gallery) return;
  const image = gallery.querySelector('[data-gallery-main]');
  const buttons = [...gallery.querySelectorAll('[data-gallery-src]')];
  const position = gallery.querySelector('[data-gallery-position]');
  if (!image || !buttons.length) return;
  function show(index, focus = false) {
    image.src = buttons[index].dataset.gallerySrc;
    buttons.forEach((button, i) => button.setAttribute('aria-pressed', String(i === index)));
    position.textContent = `Photo ${index + 1} of ${buttons.length}`;
    if (focus) buttons[index].focus();
  }
  buttons.forEach((button, index) => {
    button.addEventListener('click', () => show(index));
    button.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const target = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1
        : (index + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length;
      show(target, true);
    });
  });
})();
