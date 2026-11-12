(() => {
  const input = document.querySelector('#id_photo');
  const editor = document.querySelector('[data-photo-editor]');
  if (!input || !editor) return;
  const preview = document.querySelector('#photo-preview');
  const placeholder = document.querySelector('#upload-placeholder');
  const status = document.querySelector('#photo-filename');
  const grid = document.querySelector('#new-photo-previews');
  const saved = [...editor.querySelectorAll('[data-saved-photo]')];
  let urls = [];
  function chooseCover() {
    const radios = [...editor.querySelectorAll('[name=cover_photo]')].filter(radio => !radio.disabled);
    if (!radios.some(radio => radio.checked) && radios.length) radios[0].checked = true;
  }
  function render() {
    const previousCover = editor.querySelector('[name=cover_photo]:checked')?.value;
    urls.forEach(url => URL.revokeObjectURL(url)); urls = [];
    grid.replaceChildren(); input.setCustomValidity(''); status.textContent = '';
    preview.hidden = true; placeholder.hidden = false;
    saved.forEach(item => {
      const removed = item.querySelector('[data-remove-photo]').checked;
      item.querySelector('[name=cover_photo]').disabled = removed;
      item.classList.toggle('is-removed', removed);
    });
    const files = [...input.files];
    const count = saved.filter(item => !item.querySelector('[data-remove-photo]').checked).length + files.length;
    let error = count > 5 ? 'A listing can have up to five photos. Remove a saved photo before adding more.' : '';
    if (files.some(file => file.size > Number(input.dataset.maxBytes || 4194304))) error = 'Each photo must be smaller than 4 MB.';
    if (files.some(file => file.type && !['image/jpeg','image/png','image/webp'].includes(file.type))) error = 'Choose JPG, PNG or WebP photos.';
    if (error) { input.setCustomValidity(error); status.textContent = error; chooseCover(); return; }
    files.forEach((file, index) => {
      const url = URL.createObjectURL(file); urls.push(url);
      if (index === 0) { preview.src = url; preview.hidden = false; placeholder.hidden = true; }
      const item = document.createElement('div'); item.className = 'new-photo-item';
      const image = document.createElement('img'); image.src = url; image.alt = `Selected photo ${index + 1}`;
      const label = document.createElement('label');
      const radio = document.createElement('input'); radio.type = 'radio'; radio.name = 'cover_photo'; radio.value = `new-${index}`;
      radio.checked = previousCover === radio.value;
      label.append(radio, ' Cover');
      const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'quiet'; remove.textContent = 'Remove';
      remove.setAttribute('aria-label', `Remove selected photo ${index + 1}`);
      remove.addEventListener('click', () => {
        const chosen = editor.querySelector('[name=cover_photo]:checked');
        const selectedIndex = chosen?.value.match(/^new-(\d+)$/);
        if (selectedIndex) {
          const oldIndex = Number(selectedIndex[1]);
          if (oldIndex === index) chosen.checked = false;
          else if (oldIndex > index) chosen.value = `new-${oldIndex - 1}`;
        }
        const transfer = new DataTransfer();
        [...input.files].filter((_, position) => position !== index).forEach(photo => transfer.items.add(photo));
        input.files = transfer.files; render();
      });
      item.append(image, label, remove); grid.append(item);
    });
    if (files.length) status.textContent = `${files.length} new photo${files.length === 1 ? '' : 's'} selected · ${count} of 5 photos after saving.`;
    chooseCover();
  }
  input.addEventListener('change', render);
  saved.forEach(item => item.querySelector('[data-remove-photo]').addEventListener('change', render));
  window.addEventListener('pagehide', () => urls.forEach(url => URL.revokeObjectURL(url)));
})();
