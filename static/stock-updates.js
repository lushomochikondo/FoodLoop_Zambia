(() => {
  const feed = document.querySelector('[data-stock-feed]');
  const detail = document.querySelector('[data-stock-detail]');
  if (!feed && !detail) return;
  const entries = [...document.querySelectorAll('[data-listing-card]')].slice(0,300).map(node => ({node, parent:node.parentElement, id:Number(node.dataset.listingId)}));
  const ids = [...new Set(entries.map(entry => entry.id).concat(detail ? [Number(detail.dataset.listingId)] : []))].slice(0,300);
  if (!ids.length) return;
  const endpoint = (feed || detail).dataset.stockEndpoint;
  const message = document.querySelector('[data-stock-message]');
  let busy = false;
  function updateNode(node, stock) {
    for (const field of ['remaining','reserved','collected']) {
      node.querySelectorAll(`[data-stock-${field}]`).forEach(el => { el.textContent = Number(stock[field]).toLocaleString(undefined,{maximumFractionDigits:2}); });
    }
    node.querySelectorAll('[data-stock-status]').forEach(el => { el.textContent=stock.status;el.className=`status listing-status-${stock.status_key}`; });
  }
  async function refresh() {
    if (busy || document.hidden) return;
    busy=true;
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
    try {
      const response=await fetch(`${endpoint}?ids=${ids.join(',')}`,{credentials:'same-origin',cache:'no-store',signal:controller.signal});
      if (!response.ok || response.redirected) return;
      const data=await response.json();
      const stocks=new Map(data.listings.map(stock=>[stock.id,stock]));
      let changed=false;
      for (const entry of entries) {
        const stock=stocks.get(entry.id);
        if(stock)updateNode(entry.node,stock);
        if(feed.dataset.stockDonor!=='1') {
          if(!stock || !stock.available) {
            if(entry.node.isConnected){entry.node.remove();changed=true;}
          } else if(!entry.node.isConnected) {entry.parent.append(entry.node);changed=true;}
        }
      }
      if(feed){const count=feed.querySelector('.heading-count');if(count)count.textContent=feed.querySelectorAll('[data-listing-card]').length;}
      if(changed && message){message.hidden=false;message.textContent='Availability updated. Listings with no available stock have left the feed; released reservations can reappear.';}
      if(detail) {
        const stock=stocks.get(Number(detail.dataset.listingId));
        if(stock) {
          updateNode(document,stock);
          const form=document.querySelector('.request-panel form');
          if(form){form.querySelector('button').disabled=!stock.available;form.querySelector('#id_quantity').max=stock.remaining;}
          if(message && !stock.available){message.hidden=false;message.textContent=stock.status_key==='exhausted'?'This listing is exhausted. All quantities have been collected.':`This listing is ${stock.status.toLowerCase()}. No collection quantity is currently available.`;}
          else if(message && !form && detail.dataset.stockRecipient==='1' && detail.dataset.stockInitiallyAvailable==='0'){message.hidden=false;message.textContent='Stock is available. Refresh this page to see current request options.';}
          else if(message){message.hidden=true;}
        } else if(message) {message.hidden=false;message.textContent='This listing is no longer available. Return to food listings for current availability.';document.querySelector('.request-panel form button')?.setAttribute('disabled','');}
      }
    } catch (_) { /* Keep the last known state; the server validates every request. */ }
    finally{clearTimeout(timer);busy=false;}
  }
  window.setInterval(refresh,30000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
  window.addEventListener('pageshow',refresh);
})();
