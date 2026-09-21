// User-initiated animation only. No analytics, cookies or third-party scripts.
const demo = document.querySelector('#orb-demo');
const button = document.querySelector('.demo-button');
if (demo && button) {
  const stop = () => {
    demo.src = demo.dataset.still;
    button.setAttribute('aria-pressed', 'false');
    button.textContent = button.dataset.play;
  };
  button.addEventListener('click', () => {
    if (button.getAttribute('aria-pressed') === 'true') return stop();
    demo.src = demo.dataset.animation;
    button.setAttribute('aria-pressed', 'true');
    button.textContent = button.dataset.stop;
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
  new IntersectionObserver(entries => { if (!entries[0].isIntersecting) stop(); }).observe(demo);
  matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', stop);
}
