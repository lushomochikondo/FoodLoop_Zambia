(() => {
  const counters = [...document.querySelectorAll('[data-count-up]')];
  if (!counters.length) return;

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const runCounter = element => {
    const target = Number.parseInt(element.dataset.countUp, 10);
    if (!Number.isFinite(target) || target <= 0 || reduceMotion) return;

    const duration = 1200;
    const started = performance.now();
    const step = now => {
      const progress = Math.min((now - started) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      element.textContent = String(Math.round(target * eased));
      if (progress < 1) window.requestAnimationFrame(step);
      else element.textContent = String(target);
    };

    element.textContent = '0';
    window.requestAnimationFrame(step);
  };

  if (reduceMotion || !('IntersectionObserver' in window)) {
    counters.forEach(element => { element.textContent = element.dataset.countUp; });
    return;
  }

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      runCounter(entry.target);
      observer.unobserve(entry.target);
    });
  }, { threshold: 0.55 });

  counters.forEach(element => observer.observe(element));
})();
