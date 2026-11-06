(() => {
  const capture = document.querySelector('[data-capture-pickup]');
  const clear = document.querySelector('[data-clear-pickup]');
  const latitude = document.querySelector('#id_pickup_latitude');
  const longitude = document.querySelector('#id_pickup_longitude');
  const status = document.querySelector('[data-pickup-status]');
  if (!capture || !clear || !latitude || !longitude || !status) return;

  if (latitude.value && longitude.value) status.textContent = 'Pickup pin saved. You can update or clear it here.';
  capture.addEventListener('click', () => {
    if (!navigator.geolocation) {
      status.textContent = 'This browser cannot provide a location. The general area will still be used.';
      return;
    }
    capture.disabled = true;
    status.textContent = 'Getting the pickup point. Allow location access when your browser asks.';
    navigator.geolocation.getCurrentPosition(position => {
      latitude.value = position.coords.latitude.toFixed(6);
      longitude.value = position.coords.longitude.toFixed(6);
      status.textContent = `Pickup pin saved (approximately ${Math.round(position.coords.accuracy)} m accuracy).`;
      capture.disabled = false;
    }, error => {
      const message = error.code === error.PERMISSION_DENIED
        ? 'Location permission was declined. You can continue using the general area.'
        : error.code === error.TIMEOUT
          ? 'Location lookup timed out. Try again or continue using the general area.'
          : 'Location is unavailable. Try again or continue using the general area.';
      status.textContent = message;
      capture.disabled = false;
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 });
  });
  clear.addEventListener('click', () => {
    latitude.value = '';
    longitude.value = '';
    status.textContent = 'Pickup pin cleared. Listings will use the general area.';
  });
})();
