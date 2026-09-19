/* ============================================================
   拾光 Capture · 站点共享脚本
   ============================================================ */

/* ---------- 主题（默认深色，localStorage 持久化） ---------- */
(function initTheme(){
  const saved = localStorage.getItem('sg-theme');
  if(saved === 'light') document.documentElement.setAttribute('data-theme','light');
})();
function toggleTheme(){
  const el = document.documentElement;
  const light = el.getAttribute('data-theme') === 'light';
  if(light){ el.removeAttribute('data-theme'); localStorage.setItem('sg-theme','dark'); }
  else { el.setAttribute('data-theme','light'); localStorage.setItem('sg-theme','light'); }
  document.querySelectorAll('.theme-toggle').forEach(b=>{
    b.textContent = light ? '🌙' : '☀️';
    b.title = light ? '切换到深色' : '切换到浅色';
  });
}
document.addEventListener('DOMContentLoaded', ()=>{
  document.querySelectorAll('.theme-toggle').forEach(b=>{
    const light = document.documentElement.getAttribute('data-theme') === 'light';
    b.textContent = light ? '☀️' : '🌙';
    b.title = light ? '切换到浅色' : '切换到深色';
  });
});

/* ---------- 顶栏滚动阴影 ---------- */
document.addEventListener('DOMContentLoaded', ()=>{
  const header = document.getElementById('header');
  if(!header) return;
  addEventListener('scroll', ()=> header.classList.toggle('scrolled', scrollY > 10));
});

/* ---------- Toast ---------- */
let toastTimer;
function toast(msg){
  let t = document.getElementById('toast');
  if(!t){
    t = document.createElement('div');
    t.id = 'toast'; t.className = 'toast';
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(()=> t.classList.remove('show'), 2400);
}

/* ---------- 滚动入场 ---------- */
document.addEventListener('DOMContentLoaded', ()=>{
  const io = new IntersectionObserver(es => es.forEach(e=>{
    if(e.isIntersecting){ e.target.classList.add('in'); io.unobserve(e.target); }
  }), {threshold:.15});
  document.querySelectorAll('.reveal').forEach(el => io.observe(el));
});

/* ---------- 数字滚动 ---------- */
document.addEventListener('DOMContentLoaded', ()=>{
  const statIO = new IntersectionObserver(es => es.forEach(e=>{
    if(!e.isIntersecting) return;
    const el = e.target, target = +el.dataset.count,
          pre = el.dataset.prefix || '', suf = el.dataset.suffix || '';
    let cur = 0; const step = Math.max(target / 40, .5);
    (function tick(){
      cur += step;
      if(cur >= target){ el.textContent = pre + target + suf; return; }
      el.textContent = pre + Math.round(cur) + suf;
      requestAnimationFrame(tick);
    })();
    statIO.unobserve(el);
  }), {threshold:.6});
  document.querySelectorAll('.stat .num, [data-count]').forEach(el => statIO.observe(el));
});
