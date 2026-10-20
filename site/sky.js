/* Weather background for all pages: a canvas behind the page that shows the weather the page is about.
   Sky.set(mood, level, night)
     mood  'storm' = heavy rain with occasional lightning, 'rain' = steady rain, 'clear' = sun (or stars at night)
     level 0..1, how strong (more and faster drops, more frequent lightning)
     night true = clear night sky instead of sun (only matters for 'clear')
   Calm by design: low contrast, cards and maps stay solid on top, lightning is a soft glow at most every few
   seconds (never rapid flashing). Stops when the tab is hidden. With "reduce motion" on, it draws a still picture. */
(function () {
  const RM = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const cv = document.createElement('canvas');
  cv.setAttribute('aria-hidden', 'true');
  cv.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;z-index:-1;pointer-events:none;display:block';
  const ready = () => document.body.insertBefore(cv, document.body.firstChild);
  if (document.body) ready(); else document.addEventListener('DOMContentLoaded', ready);
  const cx = cv.getContext('2d');
  let W = 0, H = 0, DPR = 1;
  function size() {
    DPR = Math.min(1.5, window.devicePixelRatio || 1); W = innerWidth; H = innerHeight;
    cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR); cx.setTransform(DPR, 0, 0, DPR, 0, 0);
    seed();
  }
  const rnd = (a, b) => a + Math.random() * (b - a);
  // ---- scene state
  let cur = { mood: 'clear', level: 0, night: false }, prev = null, mix = 1, drops = [], stars = [], clouds = [];
  let flash = 0, flashT = 0, nextBolt = 0, bolt = null, t0 = performance.now(), last = 0;
  function seed() {
    drops = []; const n = Math.round((W * H) / 2600);              // pool; how many are drawn depends on level
    for (let i = 0; i < n; i++) drops.push({ x: rnd(-50, W + 50), y: rnd(-H, H), l: rnd(12, 26), v: rnd(.75, 1.15), a: rnd(.16, .34), z: Math.random() });
    stars = []; for (let i = 0; i < Math.round(W * H / 9000); i++) stars.push({ x: rnd(0, W), y: rnd(0, H * .55), r: rnd(.4, 1.3), p: rnd(0, 6.28), s: rnd(.3, 1) });
    clouds = []; for (let i = 0; i < 6; i++) clouds.push({ x: rnd(-.2, 1.1), y: rnd(-.04, .2), w: rnd(.45, .9), h: rnd(.08, .16), s: rnd(.004, .012) });
  }
  // ---- painters
  function sky(m, a, t) {
    const g = cx.createLinearGradient(0, 0, 0, H);
    if (m.mood === 'storm') { g.addColorStop(0, '#1d2a3a'); g.addColorStop(.45, '#101c2b'); g.addColorStop(1, '#0a121c') }
    else if (m.mood === 'rain') { g.addColorStop(0, '#1a2d44'); g.addColorStop(.5, '#0f1d2f'); g.addColorStop(1, '#0a131e') }
    else if (m.night) { g.addColorStop(0, '#0d1b33'); g.addColorStop(.55, '#0b1522'); g.addColorStop(1, '#08101a') }
    else { g.addColorStop(0, '#1f4064'); g.addColorStop(.35, '#152c46'); g.addColorStop(.75, '#0b1522'); g.addColorStop(1, '#09121d') }
    cx.globalAlpha = a; cx.fillStyle = g; cx.fillRect(0, 0, W, H);
    if (m.mood === 'storm' || m.mood === 'rain') {                     // slow, heavy cloud banks across the top
      clouds.forEach(c => {
        const x = ((c.x + t * c.s / 60) % 1.4 - .2) * W, y = c.y * H, rw = c.w * W, rh = c.h * H;
        const r = cx.createRadialGradient(x, y, 0, x, y, rw);
        const k = m.mood === 'storm' ? .28 : .2;
        r.addColorStop(0, `rgba(120,140,165,${k})`); r.addColorStop(1, 'rgba(120,140,165,0)');
        cx.save(); cx.translate(x, y); cx.scale(1, rh / rw); cx.translate(-x, -y); cx.fillStyle = r; cx.fillRect(x - rw, y - rw, 2 * rw, 2 * rw); cx.restore();
      });
    } else if (m.night) {                                                // stars and a moon
      stars.forEach(s => { cx.globalAlpha = a * (.35 + .35 * Math.sin(t * s.s + s.p)); cx.fillStyle = '#dfe9ff'; cx.beginPath(); cx.arc(s.x, s.y, s.r, 0, 7); cx.fill() });
      cx.globalAlpha = a; const mx = W * .84, my = Math.min(H * .1, 90), mr = 16;
      const gl = cx.createRadialGradient(mx, my, 0, mx, my, mr * 6); gl.addColorStop(0, 'rgba(220,232,255,.22)'); gl.addColorStop(1, 'rgba(220,232,255,0)');
      cx.fillStyle = gl; cx.fillRect(mx - mr * 6, my - mr * 6, mr * 12, mr * 12);
      cx.fillStyle = '#e9eef8'; cx.beginPath(); cx.arc(mx, my, mr, 0, 7); cx.fill();
      cx.fillStyle = '#0d1b33'; cx.beginPath(); cx.arc(mx + 7, my - 4, mr * .92, 0, 7); cx.fill();   // crescent
    } else {                                                             // sun with a soft halo and slowly turning rays
      const sx = W * .86, sy = Math.min(H * .09, 80), sr = 24;
      const halo = cx.createRadialGradient(sx, sy, 0, sx, sy, Math.max(W, H) * .7);
      halo.addColorStop(0, 'rgba(255,210,120,.40)'); halo.addColorStop(.18, 'rgba(255,190,100,.16)'); halo.addColorStop(1, 'rgba(255,190,100,0)');
      cx.fillStyle = halo; cx.fillRect(0, 0, W, H);
      cx.save(); cx.translate(sx, sy); cx.rotate(t * .02);
      for (let i = 0; i < 12; i++) { cx.rotate(Math.PI / 6); cx.fillStyle = 'rgba(255,214,140,.05)'; cx.beginPath(); cx.moveTo(0, 0); cx.lineTo(Math.max(W, H), -40); cx.lineTo(Math.max(W, H), 40); cx.closePath(); cx.fill() }
      cx.restore();
      const d = cx.createRadialGradient(sx, sy, 0, sx, sy, sr); d.addColorStop(0, '#fff3cf'); d.addColorStop(1, '#ffc75a');
      cx.fillStyle = d; cx.beginPath(); cx.arc(sx, sy, sr, 0, 7); cx.fill();
    }
    cx.globalAlpha = 1;
  }
  function rain(m, a, dt) {
    if (m.mood !== 'storm' && m.mood !== 'rain') return;
    const lv = Math.max(0, Math.min(1, m.level)), n = Math.round(drops.length * (m.mood === 'storm' ? .55 + .45 * lv : .22 + .3 * lv));
    const sp = (m.mood === 'storm' ? 900 : 650) * (.85 + .3 * lv), lean = m.mood === 'storm' ? .22 : .12;
    cx.lineCap = 'round';
    for (let i = 0; i < n; i++) {
      const d = drops[i]; d.y += sp * d.v * dt; d.x -= sp * d.v * lean * dt;
      if (d.y > H + 30) { d.y = rnd(-80, -10); d.x = rnd(0, W + 120) }
      if (d.x < -40) d.x += W + 80;
      const k = .6 + .4 * d.z;
      cx.strokeStyle = `rgba(175,215,250,${(d.a * a * k).toFixed(3)})`; cx.lineWidth = .7 + .6 * d.z;
      cx.beginPath(); cx.moveTo(d.x, d.y); cx.lineTo(d.x + d.l * lean * k, d.y - d.l * k); cx.stroke();
    }
  }
  function makeBolt() {
    const pts = []; let x = rnd(W * .1, W * .9), y = 0; const end = rnd(H * .22, H * .42);
    while (y < end) { pts.push([x, y]); y += rnd(14, 34); x += rnd(-22, 22) }
    return pts;
  }
  function lightning(m, a, now) {
    if (m.mood !== 'storm' || RM) return;
    if (!nextBolt) nextBolt = now + rnd(3000, 7000);
    if (now > nextBolt) { flashT = now; bolt = Math.random() < .55 ? makeBolt() : null; nextBolt = now + rnd(9000, 16000) * (1.25 - .5 * m.level) }
    const e = now - flashT;                                              // soft double glow, ~0.6 s in all
    flash = e < 70 ? e / 70 * .16 : e < 150 ? .16 - (e - 70) / 80 * .12 : e < 220 ? .04 + (e - 150) / 70 * .08 : e < 650 ? .12 * (1 - (e - 220) / 430) : 0;
    if (flash > 0) {
      cx.globalAlpha = a; cx.fillStyle = `rgba(190,210,240,${flash.toFixed(3)})`; cx.fillRect(0, 0, W, H * .75);
      if (bolt && e < 260) {
        cx.strokeStyle = `rgba(225,235,255,${(.55 * (1 - e / 260)).toFixed(3)})`; cx.lineWidth = 1.4; cx.shadowColor = 'rgba(180,205,255,.8)'; cx.shadowBlur = 8;
        cx.beginPath(); bolt.forEach((p, i) => i ? cx.lineTo(p[0], p[1]) : cx.moveTo(p[0], p[1])); cx.stroke(); cx.shadowBlur = 0;
      }
      cx.globalAlpha = 1;
    }
  }
  function frame(now) {
    const dt = Math.min(.05, (now - (last || now)) / 1000); last = now; const t = (now - t0) / 1000;
    cx.clearRect(0, 0, W, H);
    if (prev && mix < 1) { sky(prev, 1, t); rain(prev, 1 - mix, dt) }
    sky(cur, prev && mix < 1 ? mix : 1, t); rain(cur, mix, dt); lightning(cur, mix, now);
    if (mix < 1) { mix = Math.min(1, mix + dt / .9); if (mix >= 1) prev = null }
  }
  let raf = 0, lastDraw = 0;
  function loop(now) {
    raf = requestAnimationFrame(loop);
    if (now - lastDraw < 32) return;                                     // ~30 frames a second is plenty
    lastDraw = now; frame(now);
  }
  function start() { if (RM) { frame(performance.now()); return } if (!raf) { last = 0; raf = requestAnimationFrame(loop) } }
  function stop() { if (raf) cancelAnimationFrame(raf); raf = 0 }
  document.addEventListener('visibilitychange', () => document.hidden ? stop() : start());
  addEventListener('resize', () => { size(); if (RM) frame(performance.now()) });
  size();
  window.Sky = {
    set(mood, level, night) {
      const m = { mood: mood || 'clear', level: +level || 0, night: !!night };
      if (m.mood === cur.mood && m.night === cur.night && Math.abs(m.level - cur.level) < .05) return;
      if (m.mood !== cur.mood || m.night !== cur.night) { prev = cur; mix = RM ? 1 : 0 }
      cur = m; nextBolt = 0; start(); if (RM) frame(performance.now());
      document.documentElement.dataset.sky = m.mood + (m.night ? '-night' : '');
    },
    get() { return Object.assign({}, cur) },
    flash() { nextBolt = performance.now() }   // for testing the lightning look
  };
  start();
})();
