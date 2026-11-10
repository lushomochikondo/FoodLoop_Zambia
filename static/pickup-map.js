(() => {
  const open=document.querySelector('[data-open-pickup-map]');
  if(!open)return;
  const lat=document.querySelector('#id_pickup_latitude'),lon=document.querySelector('#id_pickup_longitude');
  const panel=document.querySelector('[data-pickup-map-panel]'),status=document.querySelector('[data-pickup-status]');
  const latitude=document.querySelector('[data-pin-lat]'),longitude=document.querySelector('[data-pin-lon]');
  let map,marker;
  function update(point){
    if(marker)marker.setLatLng(point);else marker=L.circleMarker(point,{radius:10,color:'#163e2d',fillColor:'#e1a91b',fillOpacity:1,draggable:false}).addTo(map);
    lat.value=point[0].toFixed(6);lon.value=point[1].toFixed(6);latitude.value=lat.value;longitude.value=lon.value;
    status.textContent='Pickup pin selected. Check it marks the collection entrance, then save your listing.';
  }
  open.addEventListener('click',()=>{
    if(typeof L==='undefined'){status.textContent='Map could not load. Use current location instead.';return;}
    panel.hidden=false;open.hidden=true;
    map=L.map(document.querySelector('[data-pickup-map]'));
    if(lat.value&&lon.value)map.setView([+lat.value,+lon.value],15);
    else map.fitBounds([[-18.1,21.9],[-8.1,33.8]]);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);
    if(lat.value&&lon.value)update([+lat.value,+lon.value]);
    map.on('click',event=>update([event.latlng.lat,event.latlng.lng]));
  });
  document.querySelector('[data-zambia-overview]').addEventListener('click',()=>{map.fitBounds([[-18.1,21.9],[-8.1,33.8]]);document.querySelector('[data-pickup-town]').value='';});
  document.querySelector('[data-pickup-town]').addEventListener('change',event=>{if(event.target.value)map.setView(event.target.value.split(',').map(Number),13);else map.fitBounds([[-18.1,21.9],[-8.1,33.8]]);});
  document.querySelector('[data-apply-pin]').addEventListener('click',()=>{
    if(latitude.value===''||longitude.value===''||!Number.isFinite(+latitude.value)||!Number.isFinite(+longitude.value)||Math.abs(+latitude.value)>90||Math.abs(+longitude.value)>180){status.textContent='Enter valid latitude and longitude values.';return;}
    update([+latitude.value,+longitude.value]);map.setView([+lat.value,+lon.value],16);
  });
  document.querySelector('[data-clear-pickup]').addEventListener('click',()=>{if(marker){map.removeLayer(marker);marker=null;}latitude.value='';longitude.value='';});
})();
