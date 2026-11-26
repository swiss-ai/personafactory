(function(){
/* ---------- misc ---------- */
$('#copyBib').addEventListener('click', e => {
  const b = e.currentTarget; const txt = $('#bib').textContent;
  const done = ok => { b.textContent = ok ? 'Copied' : 'Select and copy'; setTimeout(() => b.textContent = 'Copy BibTeX', 1600); };
  try { navigator.clipboard.writeText(txt).then(() => done(true), () => { selectBib(); done(false); }); } catch(err){ selectBib(); done(false); }
});
function selectBib(){ const r = document.createRange(); r.selectNodeContents($('#bib')); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }
// active nav link
const secs = $$('main section[id]'); const navA = $$('.nav a');
// the nav is a map of the line: stations before the current one are marked as passed
const io = new IntersectionObserver(es => es.forEach(en => {
  if (!en.isIntersecting) return;
  const idx = navA.findIndex(a => a.getAttribute('href') === '#' + en.target.id);
  navA.forEach((a, i) => { a.setAttribute('aria-current', i === idx ? 'true' : 'false'); a.classList.toggle('passed', idx >= 0 && i < idx); });
}), { rootMargin: '-40% 0px -55% 0px' });
secs.forEach(s => io.observe(s));
// belt under the header fills with scroll progress
const beltBar = $('.belt-progress i');
const onBelt = () => { const max = document.documentElement.scrollHeight - innerHeight; beltBar.style.width = (max > 0 ? Math.min(100, scrollY / max * 100) : 0) + '%'; };
addEventListener('scroll', onBelt, { passive: true }); addEventListener('resize', onBelt); onBelt();
$$('.toc-list a').forEach(a => a.addEventListener('click', () => $('.toc').removeAttribute('open')));
if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => renders.forEach(f => f()));
})();
