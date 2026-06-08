(function () {
  var zone   = document.getElementById('image-dropzone');
  var status = document.getElementById('upload-status');
  if (!zone) return;

  var uploadUrl = zone.dataset.uploadUrl;

  function getCookie(name) {
    var value = '; ' + document.cookie;
    var parts = value.split('; ' + name + '=');
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
  }

  function setActive(on) {
    zone.style.borderColor = on ? '#447e9b' : '#ccc';
    zone.style.background  = on ? '#f0f7fb' : '';
  }

  zone.addEventListener('dragover', function (e) {
    e.preventDefault();
    setActive(true);
  });

  zone.addEventListener('dragleave', function () {
    setActive(false);
  });

  zone.addEventListener('drop', function (e) {
    e.preventDefault();
    setActive(false);

    var files = Array.from(e.dataTransfer.files).filter(function (f) {
      return f.type.startsWith('image/');
    });

    if (!files.length) {
      status.textContent = 'No image files detected.';
      return;
    }

    status.textContent = 'Uploading ' + files.length + ' file(s)…';

    var form = new FormData();
    files.forEach(function (f) { form.append('images', f); });

    fetch(uploadUrl, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
      body: form,
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var n = data.created ? data.created.length : 0;
        status.textContent = n + ' option(s) added. Reloading…';
        setTimeout(function () { location.reload(); }, 800);
      })
      .catch(function () {
        status.textContent = 'Upload failed. Please try again.';
      });
  });
}());
