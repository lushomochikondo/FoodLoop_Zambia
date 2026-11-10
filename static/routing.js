(() => {
  const root = document.querySelector('[data-route-planner]');
  const config = document.querySelector('#route-destination');
  if (!root || !config) return;
  const destination = JSON.parse(config.textContent);
  const get = name => root.querySelector(`[data-${name}]`);
  const lat = get('origin-lat'), lon = get('origin-lon'), mode = get('route-mode'), preference = get('route-preference');
  const status = get('route-status'), results = get('route-results');
  let map, originMarker, routeLayer, watch = null, lastRefresh = 0, busy = false, routes = [], deadline;
  const origin = () => lat.value !== '' && lon.value !== '' && Number.isFinite(+lat.value) && Number.isFinite(+lon.value) && Math.abs(+lat.value)<=90 && Math.abs(+lon.value)<=180 ? [+lat.value,+lon.value] : null;
  function links() {
    const start = origin();
    const google = new URL('https://www.google.com/maps/dir/');
    google.searchParams.set('api','1'); google.searchParams.set('destination',`${destination.latitude},${destination.longitude}`);
    google.searchParams.set('travelmode',mode.value === 'cycling' ? 'bicycling' : mode.value);
    if (start) google.searchParams.set('origin',start.join(','));
    get('google-route').href=google.href;
    const osm = new URL('https://www.openstreetmap.org/directions');
    osm.searchParams.set('engine',`fossgis_osrm_${{driving:'car',walking:'foot',cycling:'bike'}[mode.value]}`);
    osm.searchParams.set('route',`${start ? start.join(',') : ''};${destination.latitude},${destination.longitude}`);
    get('osm-route').href=osm.href;
  }
  function setOrigin(point, fit=false) {
    lat.value=point[0].toFixed(6);lon.value=point[1].toFixed(6);
    if (originMarker) originMarker.setLatLng(point);
    else originMarker=L.circleMarker(point,{radius:8,color:'#163e2d',fillOpacity:1,fillColor:'#e1a91b'}).addTo(map).bindPopup('Your starting point');
    if (fit) map.fitBounds([point,[destination.latitude,destination.longitude]],{padding:[30,30],maxZoom:15});
    links();
  }
  function stopLive() {
    if(watch!==null) navigator.geolocation.clearWatch(watch);
    watch=null;get('live-route').textContent='Start live location';get('live-route').setAttribute('aria-pressed','false');
  }
  function choose(index) {
    const route=routes[index]; if(routeLayer)map.removeLayer(routeLayer);
    routeLayer=L.geoJSON(route.geometry,{style:{color:'#1f5e3b',weight:6,opacity:.85}}).addTo(map);
    map.fitBounds(routeLayer.getBounds(),{padding:[28,28]});
    root.querySelectorAll('.route-choice').forEach((button,i)=>button.setAttribute('aria-pressed',String(i===index)));
    const list=get('route-steps').querySelector('ol');list.replaceChildren();
    route.steps.forEach(step=>{const li=document.createElement('li');li.textContent=`${step.type.replaceAll('_',' ')} ${step.modifier} ${step.name ? 'on '+step.name : ''} · ${Math.round(step.distance)} m`;list.append(li);});
    get('route-steps').hidden=false;
    const arrival=new Date(Date.now()+route.duration*1000);
    const remaining=(new Date(deadline)-Date.now())/1000;
    const timing=document.createElement('p');timing.className='route-arrival';timing.dataset.arrival='';
    timing.textContent=`Estimated arrival: ${arrival.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})} (your device time). `+(remaining<0?'The collection deadline has passed.':route.duration>remaining?'Estimated travel exceeds the collection time remaining.':'Allow extra time for loading and delays before the collection deadline.');
    results.querySelector('[data-arrival]')?.remove();results.append(timing);
  }
  async function calculate() {
    const point=origin();if(!point){status.textContent='Choose a valid starting point on the map or enter its coordinates.';return;}
    if(busy)return;busy=true;get('calculate-route').disabled=true;status.textContent='Comparing mapped routes…';
    const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),18000);
    try {
      const csrf=document.querySelector('input[name=csrfmiddlewaretoken]')?.value;
      const response=await fetch(root.dataset.endpoint,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify({latitude:point[0],longitude:point[1],mode:mode.value,preference:preference.value}),signal:controller.signal});
      const data=await response.json();if(!response.ok)throw Error(data.error||'Routes are unavailable.');
      routes=data.routes;deadline=data.deadline;results.replaceChildren();
      routes.forEach((route,index)=>{const button=document.createElement('button');button.type='button';button.className='route-choice';button.setAttribute('aria-pressed','false');button.textContent=`${index===0?(preference.value==='distance'?'Shortest available':'Fastest estimated'):'Alternative '+index} · ${(route.distance/1000).toFixed(1)} km · about ${Math.max(1,Math.round(route.duration/60))} min`;button.addEventListener('click',()=>choose(index));results.append(button);});
      choose(0);lastRefresh=Date.now();status.textContent=destination.exact?'Route ready. Check road conditions before travel.':'Approximate preview only: final pickup directions become available after acceptance.';
    } catch(error){status.textContent=error.name==='AbortError'?'Routing timed out. Try again or open an external navigation app.':error.message;}
    finally{clearTimeout(timer);busy=false;get('calculate-route').disabled=false;}
  }
  get('open-route').addEventListener('click',()=>{
    if(typeof L==='undefined'){get('open-route').textContent='Map unavailable. Refresh the page to retry.';return;}
    get('route-controls').hidden=false;get('open-route').hidden=true;
    map=L.map(get('route-map')).setView([destination.latitude,destination.longitude],13);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · Routes: <a href="https://routing.openstreetmap.de/about.html">FOSSGIS / OSRM</a>'}).addTo(map);
    L.circleMarker([destination.latitude,destination.longitude],{radius:10,color:'#163e2d',fillColor:'#1f5e3b',fillOpacity:1}).addTo(map).bindPopup(destination.exact?'Pickup point':'Approximate collection area');
    if(!destination.exact)L.circle([destination.latitude,destination.longitude],{radius:1000,color:'#1f5e3b',fillOpacity:.08}).addTo(map);
    map.on('click',event=>{stopLive();setOrigin([event.latlng.lat,event.latlng.lng]);status.textContent='Starting point selected. Press Compare routes.';});
    links();
  });
  get('route-zambia').addEventListener('click',()=>{map.fitBounds([[-18.1,21.9],[-8.1,33.8]]);status.textContent='Showing all Zambia. Zoom in and tap the map to choose your starting point.';});
  get('origin-map').addEventListener('click',()=>{stopLive();get('route-map').scrollIntoView({behavior:'smooth',block:'center'});status.textContent='Tap the map to choose your starting point.';});
  get('origin-gps').addEventListener('click',()=>{
    if(!navigator.geolocation){status.textContent='Location is unavailable. Choose a start on the map.';return;}
    status.textContent='Allow location access to use your position.';
    navigator.geolocation.getCurrentPosition(p=>{stopLive();setOrigin([p.coords.latitude,p.coords.longitude],true);status.textContent=`Location set (about ${Math.round(p.coords.accuracy)} m accuracy). Press Compare routes.`;},()=>{status.textContent='Could not get location. Enable permission or choose a starting point on the map.';},{enableHighAccuracy:true,timeout:15000,maximumAge:15000});
  });
  get('live-route').addEventListener('click',()=>{
    if(watch!==null){stopLive();status.textContent='Live location stopped.';return;}
    if(!navigator.geolocation){status.textContent='Live location is unavailable in this browser.';return;}
    get('live-route').textContent='Stop live location';get('live-route').setAttribute('aria-pressed','true');
    watch=navigator.geolocation.watchPosition(p=>{setOrigin([p.coords.latitude,p.coords.longitude]);if(Date.now()-lastRefresh>60000)calculate();},()=>{stopLive();status.textContent='Live location unavailable. Check permission or choose a start on the map.';},{enableHighAccuracy:true,timeout:15000,maximumAge:10000});
  });
  [lat,lon].forEach(input=>input.addEventListener('change',()=>{stopLive();const point=origin();if(point)setOrigin(point);else links();}));
  [mode,preference].forEach(input=>input.addEventListener('change',()=>{links();results.replaceChildren();get('route-steps').hidden=true;status.textContent='Options changed. Press Compare routes for updated estimates.';}));
  get('calculate-route').addEventListener('click',calculate);
  window.addEventListener('pagehide',stopLive);document.addEventListener('visibilitychange',()=>{if(document.hidden)stopLive();});
})();
