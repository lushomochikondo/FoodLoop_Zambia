const input = document.querySelector('#id_photo');
const preview = document.querySelector('#photo-preview');
const placeholder = document.querySelector('#upload-placeholder');
const filename = document.querySelector('#photo-filename');
let currentUrl;
if (input) {
  input.addEventListener('change', () => {
    if (currentUrl) URL.revokeObjectURL(currentUrl);
    const file = input.files[0];
    preview.hidden = true;
    placeholder.hidden = false;
    filename.textContent = '';
    if (!file) return;
    if (file.size > 8 * 1024 * 1024) {
      filename.textContent = 'This photo is too large. Choose a file smaller than 8 MB.';
      input.value = '';
      return;
    }
    currentUrl = URL.createObjectURL(file);
    preview.src = currentUrl;
    preview.hidden = false;
    placeholder.hidden = true;
    filename.textContent = file.name + ' — click Choose file to replace';
  });
}
