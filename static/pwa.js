(() => {
  const button=document.querySelector('#install-app');
  const status=document.querySelector('#install-status');
  let installPrompt=null;
  const installed=()=>window.matchMedia('(display-mode: standalone)').matches || navigator.standalone===true;
  const say=text=>{if(status){status.hidden=false;status.textContent=text;}};
  function update(){if(button){button.hidden=false;button.disabled=installed();button.textContent=installed()?'App installed':'Install app';}}
  function guidance(){
    const ios=/iPad|iPhone|iPod/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
    if(ios)return 'On iPhone or iPad, open FoodLoop in Safari, tap Share, then Add to Home Screen.';
    if(/Android/.test(navigator.userAgent))return 'Open FoodLoop in Chrome, then use the browser menu and choose Install app or Add to Home screen. If it is already installed, open FoodLoop from your apps.';
    return 'In Chrome or Edge, use the install icon in the address bar or open the browser menu and look for Install FoodLoop or Apps > Install this site as an app. If already installed, open FoodLoop from your apps.';
  }
  window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();installPrompt=event;update();});
  window.addEventListener('appinstalled',()=>{installPrompt=null;if(button){button.disabled=true;button.textContent='App installed';}say('FoodLoop is installed. Open it from your device apps.');});
  button?.addEventListener('click',async()=>{
    if(installed()){update();say('FoodLoop is already running as an installed app.');return;}
    if(!installPrompt){say(guidance());return;}
    const prompt=installPrompt;installPrompt=null;button.disabled=true;
    try {
      await prompt.prompt();
      const choice=await prompt.userChoice;
      say(choice?.outcome==='accepted'?'Installation requested. Follow your browser instructions to finish.':guidance());
    } catch(_){say(guidance());}
    finally{if(button.textContent!=='App installed')button.disabled=false;}
  });
  update();
  if('serviceWorker' in navigator && window.isSecureContext){
    const register=()=>navigator.serviceWorker.register('/service-worker.js').catch(()=>{say('App setup could not finish. Reload the page and try again, or use your browser install menu.');});
    if(document.readyState==='complete')register();else window.addEventListener('load',register,{once:true});
  }
})();
