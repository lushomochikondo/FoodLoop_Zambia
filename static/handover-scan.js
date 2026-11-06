(() => {
  if (!('BarcodeDetector' in window) || !navigator.mediaDevices?.getUserMedia) {
    document.querySelectorAll('[data-qr-scan]').forEach(button => button.addEventListener('click', () => {
      const panel = button.closest('form')?.querySelector('[data-qr-panel]');
      const message = panel?.querySelector('[data-qr-message]');
      if (panel) panel.hidden = false;
      if (message) message.textContent = 'QR scanning is not supported in this browser. Enter the six-digit code above.';
      button.disabled = true;
    }));
    return;
  }

  document.querySelectorAll('[data-qr-scan]').forEach(button => {
    const form = button.closest('form');
    const panel = form?.querySelector('[data-qr-panel]');
    const video = panel?.querySelector('video');
    const message = panel?.querySelector('[data-qr-message]');
    const input = form?.querySelector('[name="handover_code"]');
    const stopButton = panel?.querySelector('[data-qr-stop]');
    if (!form || !panel || !video || !input || !message || !stopButton) return;

    let stream = null;
    let running = false;
    let frame = 0;
    const detector = new BarcodeDetector({ formats: ['qr_code'] });

    const stop = () => {
      running = false;
      cancelAnimationFrame(frame);
      stream?.getTracks().forEach(track => track.stop());
      stream = null;
      video.srcObject = null;
      panel.hidden = true;
      button.disabled = false;
    };

    const scan = async () => {
      if (!running) return;
      if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
        try {
          const codes = await detector.detect(video);
          const code = codes.find(item => /^\d{6}$/.test(item.rawValue.trim()));
          if (code) {
            input.value = code.rawValue.trim();
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.focus();
            message.textContent = 'Code scanned. Confirm the quantity and weight, then record the handover.';
            stop();
            return;
          }
        } catch (_) {
          message.textContent = 'Could not read that QR code. Hold it steady inside the camera view.';
        }
      }
      frame = requestAnimationFrame(scan);
    };

    button.addEventListener('click', async () => {
      button.disabled = true;
      panel.hidden = false;
      message.textContent = 'Requesting camera access...';
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
        video.srcObject = stream;
        await video.play();
        running = true;
        message.textContent = 'Point the camera at the recipient\'s QR code.';
        scan();
      } catch (_) {
        message.textContent = 'Camera access was unavailable. Allow camera access or enter the six-digit code above.';
        stream?.getTracks().forEach(track => track.stop());
        stream = null;
        button.disabled = false;
      }
    });
    stopButton.addEventListener('click', stop);
    document.addEventListener('visibilitychange', () => { if (document.hidden && running) stop(); });
  });
})();
