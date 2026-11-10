(() => {
  const header = document.querySelector('#landing-header, .app .masthead');
  if (!header) return;

  let previousY = window.scrollY;
  const threshold = 6;

  const updateHeader = () => {
    const currentY = Math.max(0, window.scrollY);
    if (document.body.classList.contains('menu-open') || header.querySelector(':focus-visible')) {
      header.classList.add('is-revealed');
      header.classList.remove('is-hidden');
    } else if (currentY <= 24) {
      header.classList.remove('is-revealed', 'is-hidden');
    } else if (currentY < previousY - threshold) {
      header.classList.add('is-revealed');
      header.classList.remove('is-hidden');
    } else if (currentY > previousY + threshold) {
      header.classList.add('is-hidden');
      header.classList.remove('is-revealed');
    }
    previousY = currentY;
  };

  if (previousY > 24) header.classList.add('is-revealed');
  let scheduled = false;
  window.addEventListener('scroll', () => {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(() => {
      updateHeader();
      scheduled = false;
    });
  }, { passive: true });

  const menus = [...header.querySelectorAll('[data-landing-dropdown]')];
  const closeMenu = menu => {
    menu.open = false;
    menu.querySelector(':scope > summary')?.setAttribute('aria-expanded', 'false');
  };
  menus.forEach(menu => {
    const summary = menu.querySelector(':scope > summary');
    summary?.setAttribute('aria-expanded', String(menu.open));
    menu.addEventListener('toggle', () => {
      summary?.setAttribute('aria-expanded', String(menu.open));
      if (menu.open) menus.filter(other => other !== menu && !other.contains(menu) && !menu.contains(other)).forEach(closeMenu);
    });
    menu.addEventListener('pointerleave', event => {
      if (event.pointerType === 'touch' || window.matchMedia('(max-width: 900px)').matches) return;
      closeMenu(menu);
    });
  });

  document.addEventListener('pointerdown', event => {
    if (!header.contains(event.target)) menus.forEach(closeMenu);
  });
  header.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const open = menus.find(menu => menu.open);
    if (open) {
      closeMenu(open);
      open.querySelector(':scope > summary')?.focus();
    }
  });
  header.querySelectorAll('.landing-nav a, .landing-mobile-menu a').forEach(link => {
    link.addEventListener('click', () => menus.forEach(closeMenu));
  });
})();
