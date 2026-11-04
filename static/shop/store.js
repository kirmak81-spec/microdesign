document.querySelectorAll('[data-gallery]').forEach(button => {
  button.addEventListener('click', () => {
    const main = document.getElementById('gallery-main');
    if (main) main.src = button.dataset.gallery;
    document.querySelectorAll('[data-gallery]').forEach(b => b.removeAttribute('aria-pressed'));
    button.setAttribute('aria-pressed', 'true');
  });
});
