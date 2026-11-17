(function () {
  'use strict';
  document.addEventListener('DOMContentLoaded', function () {
    const $ = django.jQuery;
    const product = document.getElementById('id_product');
    const news = document.getElementById('id_news');
    const productImage = document.getElementById('id_product_image_id');
    const newsImage = document.getElementById('id_news_image_id');
    const file = document.getElementById('id_image');
    if (!product || !news || !productImage || !newsImage || !file) return;
    const row = file.closest('.form-row');
    const picker = document.createElement('div');
    picker.className = 'banner-image-picker';
    row.querySelector('.flex-container, div').appendChild(picker);
    const sourceUrl = productImage.dataset.bannerSourceUrl;
    let lastProduct = product.value;
    let lastNews = news.value;
    let requestNumber = 0;

    function setValue(id, value) {
      const field = document.getElementById(id);
      if (field) field.value = value || '';
    }
    function clearUpload() {
      file.value = '';
      const clear = document.getElementById('image-clear_id');
      if (clear) clear.checked = false;
    }
    function message(text) {
      picker.replaceChildren();
      const note = document.createElement('p');
      note.className = 'banner-image-help';
      note.textContent = text;
      picker.appendChild(note);
    }
    async function getSource(type, id) {
      const url = new URL(sourceUrl, location.origin);
      url.searchParams.set('type', type);
      url.searchParams.set('id', id);
      const response = await fetch(url, { credentials: 'same-origin' });
      if (!response.ok) throw new Error('Не удалось загрузить данные.');
      return response.json();
    }
    function renderPhotos(images) {
      picker.replaceChildren();
      if (!images.length) { message('У товара пока нет фотографий. Можно загрузить файл.'); return; }
      const caption = document.createElement('p');
      caption.className = 'banner-image-help';
      caption.textContent = 'Или выберите фотографию товара:';
      picker.appendChild(caption);
      const list = document.createElement('div');
      list.className = 'banner-image-options';
      images.forEach((photo, index) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'banner-image-choice';
        button.setAttribute('aria-label', `Выбрать фотографию ${index + 1}: ${photo.caption}`);
        button.setAttribute('aria-pressed', String(productImage.value === String(photo.id)));
        const image = document.createElement('img');
        image.src = photo.url;
        image.alt = '';
        image.loading = 'lazy';
        button.appendChild(image);
        button.addEventListener('click', () => {
          productImage.value = String(photo.id);
          newsImage.value = '';
          clearUpload();
          list.querySelectorAll('button').forEach(choice => choice.setAttribute('aria-pressed', String(choice === button)));
        });
        list.appendChild(button);
      });
      picker.appendChild(list);
    }
    function clearOther(select) {
      if (select.value) $(select).val(null).trigger('change');
      setValue('id_link_url', '');
    }
    async function chooseProduct(id, ask) {
      const number = ++requestNumber;
      if (!id) { picker.replaceChildren(); productImage.value = ''; return; }
      try {
        const data = await getSource('product', id);
        if (number !== requestNumber || product.value !== id) return;
        renderPhotos(data.images);
        if (ask && window.confirm('Заменить тексты баннера данными выбранного товара?')) {
          setValue('id_title', data.title.slice(0, 250));
          setValue('id_subtitle', data.subtitle.slice(0, 250));
          setValue('id_label', 'МИКРОДИЗАЙН / ИЗ КАТАЛОГА');
          setValue('id_overlay_text', '');
          setValue('id_image_alt', data.title.slice(0, 250));
        }
      } catch (_) { if (number === requestNumber) message('Не удалось загрузить фотографии товара.'); }
    }
    async function chooseNews(id) {
      const number = ++requestNumber;
      if (!id) return;
      try {
        const data = await getSource('news', id);
        if (number !== requestNumber || news.value !== id) return;
        const prompt = data.image ? 'Заменить тексты и изображение баннера данными выбранной новости?' : 'У новости нет изображения. Заменить тексты баннера данными новости?';
        if (!window.confirm(prompt)) return;
        setValue('id_title', data.title.slice(0, 250));
        setValue('id_subtitle', data.summary.slice(0, 250));
        setValue('id_label', 'МИКРОДИЗАЙН / НОВОСТИ');
        setValue('id_overlay_text', data.title.slice(0, 200));
        setValue('id_image_alt', data.title.slice(0, 250));
        if (data.image) {
          productImage.value = '';
          newsImage.value = id;
          clearUpload();
          message('При сохранении будет использовано изображение выбранной новости.');
        }
      } catch (_) { message('Не удалось загрузить данные новости.'); }
    }
    $(product).on('change', function () {
      const id = this.value;
      if (id === lastProduct) return;
      lastProduct = id;
      productImage.value = '';
      if (id) { clearOther(news); newsImage.value = ''; }
      chooseProduct(id, Boolean(id));
    });
    $(news).on('change', function () {
      const id = this.value;
      if (id === lastNews) return;
      lastNews = id;
      newsImage.value = '';
      if (id) { clearOther(product); productImage.value = ''; picker.replaceChildren(); chooseNews(id); }
      else if (!product.value) { requestNumber++; picker.replaceChildren(); }
    });
    file.addEventListener('change', () => {
      if (file.files.length) {
        productImage.value = '';
        newsImage.value = '';
        picker.querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed', 'false'));
      }
    });
    if (product.value) chooseProduct(product.value, false);
  });
})();
