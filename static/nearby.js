(() => {
  const button = document.querySelector('[data-nearby-sort]');
  const status = document.querySelector('[data-nearby-status]');
  const container = document.querySelector('.exchange-listings .cards');
  if (!button || !status || !container) return;
  if (!navigator.geolocation) {
    button.disabled = true;
    status.textContent = 'Location access is not available in this browser. Listings remain ordered by area matching.';
    return;
  }

  button.addEventListener('click', () => {
    const cards = [...container.querySelectorAll('[data-listing-card]')];
    if (!cards.length) {
      status.textContent = 'There are no listings to sort.';
      return;
    }
    button.disabled = true;
    status.textContent = 'Getting your location. Allow access when your browser asks.';
    navigator.geolocation.getCurrentPosition(async position => {
      status.textContent = 'Sorting listings by distance...';
      const token = document.querySelector('[name="csrfmiddlewaretoken"]')?.value;
      try {
        const response = await fetch(button.dataset.endpoint, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token || '' },
          body: JSON.stringify({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            listing_ids: cards.map(card => card.dataset.listingId)
          })
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || 'Nearby sorting is unavailable right now.');
        const byId = new Map(cards.map(card => [card.dataset.listingId, card]));
        payload.listings.forEach(item => {
          const card = byId.get(String(item.id));
          if (!card) return;
          const distance = card.querySelector('[data-listing-distance]');
          if (distance) {
            distance.textContent = item.distance || 'Area match';
            distance.hidden = false;
          }
          container.append(card);
          byId.delete(String(item.id));
        });
        byId.forEach(card => container.append(card));
        status.textContent = 'Nearest pinned collection points are first. Listings without a pickup pin follow using area matching.';
      } catch (error) {
        status.textContent = error.message || 'Could not sort listings by distance. Your usual area-based order is unchanged.';
      } finally {
        button.disabled = false;
      }
    }, error => {
      status.textContent = error.code === error.PERMISSION_DENIED
        ? 'Location permission was declined. Your usual area-based order is unchanged.'
        : 'Your location is unavailable. Your usual area-based order is unchanged.';
      button.disabled = false;
    }, { enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 });
  });
})();
