(() => {
  let theme;
  try { theme=localStorage.getItem('foodloop-theme'); } catch (_) {}
  if(theme!=='light' && theme!=='dark') theme=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';
  document.documentElement.dataset.theme=theme;
})();
