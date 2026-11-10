(() => {
  const button=document.querySelector('#theme-toggle');
  if(!button)return;
  const system=window.matchMedia('(prefers-color-scheme: dark)');
  function stored(){try{return localStorage.getItem('foodloop-theme');}catch(_){return null;}}
  function apply(theme){
    document.documentElement.dataset.theme=theme;
    const dark=theme==='dark';
    button.setAttribute('aria-pressed',String(dark));
    button.setAttribute('aria-label',dark?'Switch to light mode':'Switch to dark mode');
    button.title=button.getAttribute('aria-label');
  }
  apply(document.documentElement.dataset.theme || (system.matches?'dark':'light'));
  button.addEventListener('click',()=>{
    const theme=document.documentElement.dataset.theme==='dark'?'light':'dark';
    try{localStorage.setItem('foodloop-theme',theme);}catch(_){}
    apply(theme);
  });
  system.addEventListener('change',()=>{if(!['light','dark'].includes(stored()))apply(system.matches?'dark':'light');});
  window.addEventListener('storage',event=>{if(event.key==='foodloop-theme')apply(['light','dark'].includes(event.newValue)?event.newValue:system.matches?'dark':'light');});
})();
