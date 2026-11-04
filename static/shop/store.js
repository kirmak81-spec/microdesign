document.querySelectorAll('[data-product-gallery]').forEach(gallery => {
  const main = gallery.querySelector('#gallery-main');
  const stage = gallery.querySelector('.gallery-main');
  const strip = gallery.querySelector('.thumbnails');
  const slides = [...gallery.querySelectorAll('[data-gallery]')];
  const counter = gallery.querySelector('[data-gallery-counter]');
  const controls = gallery.querySelectorAll('[data-gallery-step]');
  if (!main || slides.length === 0) return;

  let current = 0;
  let gesture = null;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  function show(index, scroll = true) {
    current = (index + slides.length) % slides.length;
    const selected = slides[current];
    main.src = selected.dataset.gallery;
    main.alt = selected.dataset.galleryCaption;
    slides.forEach((slide, i) => {
      slide.setAttribute('aria-pressed', String(i === current));
    });
    counter.textContent = `${current + 1} / ${slides.length}`;
    if (scroll) {
      // Scroll the strip itself, never the page, when the selected photo changes.
      strip.scrollTo({
        left: selected.offsetLeft - (strip.clientWidth - selected.offsetWidth) / 2,
        behavior: reducedMotion.matches ? 'auto' : 'smooth',
      });
    }
  }

  slides.forEach((slide, index) => slide.addEventListener('click', () => show(index)));
  controls.forEach(control => {
    control.hidden = slides.length < 2;
    control.addEventListener('click', () => show(current + Number(control.dataset.galleryStep)));
  });
  counter.hidden = slides.length < 2;
  show(0, false);
  if (slides.length < 2) return;

  document.addEventListener('keydown', event => {
    if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    if (event.target.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="textbox"]')) return;
    const bounds = stage.getBoundingClientRect();
    if (bounds.bottom <= 0 || bounds.top >= window.innerHeight) return;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault();
      show(current + (event.key === 'ArrowRight' ? 1 : -1));
    }
  });

  stage.addEventListener('pointerdown', event => {
    if (!event.isPrimary || event.pointerType === 'mouse' || event.target.closest('button')) return;
    gesture = { id: event.pointerId, x: event.clientX, y: event.clientY };
    stage.setPointerCapture(event.pointerId);
  });
  stage.addEventListener('pointerup', event => {
    if (!gesture || gesture.id !== event.pointerId) return;
    const dx = event.clientX - gesture.x;
    const dy = event.clientY - gesture.y;
    gesture = null;
    if (Math.abs(dx) >= 40 && Math.abs(dx) > Math.abs(dy) * 1.25) {
      show(current + (dx < 0 ? 1 : -1));
    }
  });
  stage.addEventListener('pointercancel', () => { gesture = null; });
  stage.addEventListener('lostpointercapture', () => { gesture = null; });
});
