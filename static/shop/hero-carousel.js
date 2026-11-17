document.querySelectorAll('[data-hero-carousel]').forEach(carousel => {
  const slides = [...carousel.querySelectorAll('[data-hero-slide]')];
  const controls = carousel.querySelectorAll('[data-hero-step]');
  const counter = carousel.querySelector('[data-hero-count]');
  const dotsContainer = carousel.querySelector('[data-hero-dots]');
  const dots = carousel.querySelectorAll('[data-hero-dot]');
  if (slides.length < 2) return;
  let current = 0;
  let touch = null;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  function show(index, animate = true) {
    const previous = current;
    const direction = index > current ? 1 : -1;
    current = (index + slides.length) % slides.length;
    slides.forEach(slide => {
      slide.getAnimations().forEach(animation => animation.cancel());
      slide.hidden = true;
    });
    const selected = slides[current];
    selected.hidden = false;
    if (animate && !reducedMotion.matches && current !== previous) {
      const outgoing = slides[previous];
      outgoing.hidden = false;
      const options = { duration: 480, easing: 'cubic-bezier(.22, 1, .36, 1)' };
      outgoing.animate([{ transform: 'translateX(0)' }, { transform: `translateX(${-direction * 100}%)` }], options).onfinish = () => { outgoing.hidden = true; };
      selected.animate([{ transform: `translateX(${direction * 100}%)` }, { transform: 'translateX(0)' }], options);
    }
    counter.textContent = `${current + 1} / ${slides.length}`;
    dots.forEach((dot, i) => dot.setAttribute('aria-current', String(i === current)));
  }
  controls.forEach(button => {
    button.hidden = false;
    button.addEventListener('click', () => show(current + Number(button.dataset.heroStep)));
  });
  counter.hidden = false;
  dotsContainer.hidden = false;
  dots.forEach(dot => dot.addEventListener('click', () => show(Number(dot.dataset.heroDot))));
  show(0, false);

  document.addEventListener('keydown', event => {
    if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    if (event.target.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="textbox"]')) return;
    const bounds = carousel.getBoundingClientRect();
    if (bounds.bottom <= 0 || bounds.top >= window.innerHeight || bounds.right <= 0 || bounds.left >= window.innerWidth) return;
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    show(current + (event.key === 'ArrowRight' ? 1 : -1));
  });
  carousel.addEventListener('touchstart', event => {
    if (event.touches.length !== 1 || event.target.closest('button')) return;
    touch = { x: event.touches[0].clientX, y: event.touches[0].clientY };
  }, { passive: true });
  carousel.addEventListener('touchend', event => {
    if (!touch || event.changedTouches.length !== 1) { touch = null; return; }
    const dx = event.changedTouches[0].clientX - touch.x;
    const dy = event.changedTouches[0].clientY - touch.y;
    touch = null;
    if (Math.abs(dx) >= 40 && Math.abs(dx) > Math.abs(dy) * 1.25) show(current + (dx < 0 ? 1 : -1));
  }, { passive: true });
  carousel.addEventListener('touchcancel', () => { touch = null; });
});
