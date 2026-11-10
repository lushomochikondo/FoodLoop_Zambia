(() => {
  const button = document.querySelector('#push-enable');
  if (!button) return;
  const status = document.querySelector('#push-status');
  const test = document.querySelector('#push-test');
  const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
  const supported = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  const decode = value => {
    const padded = value.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - value.length % 4) % 4);
    return Uint8Array.from(atob(padded), c => c.charCodeAt(0));
  };
  const send = async (url, body) => {
    const response = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':csrf}, body:JSON.stringify(body), credentials:'same-origin'});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not update notification settings.');
    return data;
  };
  const ready = () => Promise.race([
    navigator.serviceWorker.register('/service-worker.js').then(() => navigator.serviceWorker.ready),
    new Promise((_, reject) => setTimeout(() => reject(new Error('Notification setup timed out. Refresh and try again.')), 15000))
  ]);
  const enabled = value => {
    button.textContent = value ? 'Turn off phone notifications' : 'Enable phone notifications';
    if (test) test.disabled = !value;
  };
  if (!supported) {
    button.disabled = true;
    status.textContent = 'Phone alerts need a supported browser. On iPhone, add FoodLoop to your Home Screen and open it there.';
    return;
  }
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') throw new Error('Allow notifications in browser and phone settings to receive alerts.');
      const registration = await ready();
      let subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        await send(button.dataset.unsubscribeUrl, subscription.toJSON());
        await subscription.unsubscribe();
        enabled(false);
        status.textContent = 'Phone notifications are turned off.';
      } else {
        subscription = await registration.pushManager.subscribe({userVisibleOnly:true, applicationServerKey:decode(button.dataset.publicKey)});
        await send(button.dataset.subscribeUrl, subscription.toJSON());
        enabled(true);
        status.textContent = 'Phone notifications are enabled. Send a test alert to check your phone notification tray.';
      }
    } catch (error) { status.textContent = error.message || 'Could not update notification settings.'; }
    finally { button.disabled = false; }
  });
  ready().then(reg => reg.pushManager.getSubscription()).then(async sub => {
    if (sub) {
      await send(button.dataset.subscribeUrl, sub.toJSON());
      enabled(true);
      status.textContent = 'Phone notifications are enabled on this device.';
    }
  }).catch(error => { status.textContent = error.message; });
  test?.addEventListener('click', async () => {
    test.disabled = true;
    try {
      await send(test.dataset.url, {});
      status.textContent = 'Test alert requested. Check your phone notification tray and notification permissions.';
    } catch (error) { status.textContent = error.message; }
    finally { test.disabled = false; }
  });
})();
