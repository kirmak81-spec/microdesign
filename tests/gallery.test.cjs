const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../static/shop/store.js'), 'utf8');

function setup(total = 3) {
  function element(values = {}) {
    return Object.assign({
      events: {}, attributes: {}, dataset: {},
      addEventListener(name, handler) { this.events[name] = handler; },
      setAttribute(name, value) { this.attributes[name] = value; },
      closest() { return null; },
    }, values);
  }
  const main = element();
  const stage = element({
    getBoundingClientRect: () => ({ top: 100, bottom: 500 }),
    setPointerCapture() {},
  });
  const strip = element({ clientWidth: 160, scrolls: [], scrollTo(options) { this.scrolls.push(options); } });
  const counter = element();
  const slides = Array.from({ length: total }, (_, i) => element({
    dataset: { gallery: `/photo-${i + 1}.webp`, galleryCaption: `Фото ${i + 1}` },
    offsetLeft: i * 84, offsetWidth: 74,
  }));
  const controls = [-1, 1].map(step => element({ dataset: { galleryStep: String(step) } }));
  const nodes = { '#gallery-main': main, '.gallery-main': stage, '.thumbnails': strip, '[data-gallery-counter]': counter };
  const gallery = {
    querySelector: selector => nodes[selector],
    querySelectorAll: selector => selector === '[data-gallery]' ? slides : controls,
  };
  const document = element({ querySelectorAll: () => [gallery] });
  vm.runInNewContext(source, { document, window: { innerHeight: 800, matchMedia: () => ({ matches: true }) } });
  function emit(target, name, values = {}) {
    const event = { target: element(), isPrimary: true, pointerType: 'touch', pointerId: 1, clientX: 0, clientY: 0, preventDefault() {}, ...values };
    target.events[name]?.(event);
  }
  return { main, stage, strip, counter, slides, controls, document, emit };
}

test('arrow buttons cycle and keep the matching thumbnail selected', () => {
  const g = setup();
  g.emit(g.controls[0], 'click');
  assert.equal(g.main.src, '/photo-3.webp');
  assert.equal(g.counter.textContent, '3 / 3');
  assert.equal(g.slides[2].attributes['aria-pressed'], 'true');
  g.emit(g.controls[1], 'click');
  assert.equal(g.main.src, '/photo-1.webp');
});

test('keyboard arrows navigate, but do not interfere with text inputs or shortcuts', () => {
  const g = setup();
  g.emit(g.document, 'keydown', { key: 'ArrowRight' });
  assert.equal(g.main.src, '/photo-2.webp');
  g.emit(g.document, 'keydown', { key: 'ArrowRight', target: { closest: () => ({}) } });
  g.emit(g.document, 'keydown', { key: 'ArrowLeft', altKey: true });
  assert.equal(g.main.src, '/photo-2.webp');
  g.emit(g.document, 'keydown', { key: 'ArrowLeft' });
  assert.equal(g.main.src, '/photo-1.webp');
});

test('horizontal swipes navigate in both directions', () => {
  const g = setup();
  g.emit(g.stage, 'pointerdown', { clientX: 200, clientY: 100 });
  g.emit(g.stage, 'pointerup', { clientX: 80, clientY: 105 });
  assert.equal(g.main.src, '/photo-2.webp');
  g.emit(g.stage, 'pointerdown', { clientX: 80, clientY: 100 });
  g.emit(g.stage, 'pointerup', { clientX: 200, clientY: 105 });
  assert.equal(g.main.src, '/photo-1.webp');
});

test('vertical scrolling, cancelled gestures and small movements do not change photos', () => {
  const g = setup();
  g.emit(g.stage, 'pointerdown', { clientX: 200, clientY: 100 });
  g.emit(g.stage, 'pointerup', { clientX: 150, clientY: 300 });
  g.emit(g.stage, 'pointerdown', { clientX: 200, clientY: 100 });
  g.emit(g.stage, 'pointercancel');
  g.emit(g.stage, 'pointerup', { clientX: 80, clientY: 100 });
  g.emit(g.stage, 'pointerdown', { clientX: 200, clientY: 100 });
  g.emit(g.stage, 'pointerup', { clientX: 180, clientY: 100 });
  assert.equal(g.main.src, '/photo-1.webp');
});

test('thumbnail selection updates the photo, caption and strip scroll only', () => {
  const g = setup();
  g.emit(g.slides[2], 'click');
  assert.equal(g.main.src, '/photo-3.webp');
  assert.equal(g.main.alt, 'Фото 3');
  assert.equal(g.strip.scrolls.length, 1);
});

test('single-photo galleries hide navigation and do not attach swipe handlers', () => {
  const g = setup(1);
  assert.ok(g.controls.every(button => button.hidden));
  assert.equal(g.counter.hidden, true);
  assert.equal(g.stage.events.pointerdown, undefined);
});
