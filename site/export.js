/* Download a map as PNG, JPEG or PDF.
   Redraws the page's SVG map (grid squares, outline, cities) on a canvas with a title, legend and source line.
   Hill shading (SVG filters) is left out so the image stays sharp and quick to make. */
(function () {
  const W = 1080, PAD = 48, MAPW = W - 2 * PAD;
  const FONT = '"Anek Latin", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
  let jspdf = null;

  function loadPdfLib() {
    if (jspdf) return Promise.resolve(jspdf);
    return new Promise((ok, fail) => {
      const s = document.createElement('script');
      s.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js';
      s.onload = () => { jspdf = window.jspdf; ok(jspdf); };
      s.onerror = () => fail(new Error('Could not load the PDF maker. Check the connection and try again.'));
      document.head.appendChild(s);
    });
  }

  function wrap(ctx, text, maxW) {
    const words = String(text).split(/\s+/), lines = []; let cur = '';
    words.forEach(w => { const t = cur ? cur + ' ' + w : w; if (ctx.measureText(t).width > maxW && cur) { lines.push(cur); cur = w; } else cur = t; });
    if (cur) lines.push(cur);
    return lines;
  }

  // draw an SVG subtree onto the canvas (rect, path, circle, text, g with clip-path)
  function drawNode(ctx, el, svg) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return;
    if (el.getAttribute('filter') || el.style.mixBlendMode) return;          // hill shading: skipped
    const tag = el.tagName.toLowerCase();
    if (tag === 'defs' || tag === 'clippath' || tag === 'filter') return;
    const op = parseFloat(cs.opacity); ctx.save();
    if (op < 1) ctx.globalAlpha *= op;
    const cp = el.getAttribute('clip-path');
    if (cp) {
      const id = (cp.match(/#([^)'"]+)/) || [])[1], c = id && svg.querySelector('#' + CSS.escape(id));
      const p = c && c.querySelector('path');
      if (p && p.getAttribute('d')) ctx.clip(new Path2D(p.getAttribute('d')));
    }
    const paint = (path) => {
      const f = cs.fill, s = cs.stroke, fo = parseFloat(cs.fillOpacity), sw = parseFloat(el.getAttribute('stroke-width') || cs.strokeWidth) || 0;
      if (f && f !== 'none') { ctx.globalAlpha *= isNaN(fo) ? 1 : fo; ctx.fillStyle = f; ctx.fill(path); if (!isNaN(fo)) ctx.globalAlpha /= (fo || 1); }
      if (s && s !== 'none' && sw > 0) { ctx.strokeStyle = s; ctx.lineWidth = sw; ctx.lineJoin = 'round'; ctx.stroke(path); }
    };
    if (tag === 'g' || tag === 'svg') {
      [...el.children].forEach(ch => drawNode(ctx, ch, svg));
    } else if (tag === 'rect') {
      const p = new Path2D(); p.rect(+el.getAttribute('x'), +el.getAttribute('y'), +el.getAttribute('width'), +el.getAttribute('height')); paint(p);
    } else if (tag === 'path' && el.getAttribute('d')) {
      paint(new Path2D(el.getAttribute('d')));
    } else if (tag === 'circle') {
      const p = new Path2D(); p.arc(+el.getAttribute('cx'), +el.getAttribute('cy'), +el.getAttribute('r'), 0, Math.PI * 2); paint(p);
    } else if (tag === 'text' && !el.getAttribute('transform')) {
      const fs = parseFloat(el.getAttribute('font-size')) || 8, fw = el.getAttribute('font-weight') || cs.fontWeight || 400;
      ctx.font = `${el.getAttribute('font-style') || ''} ${fw} ${fs}px ${FONT}`;
      const anc = el.getAttribute('text-anchor'); ctx.textAlign = anc === 'end' ? 'right' : anc === 'middle' ? 'center' : 'left';
      const x = +el.getAttribute('x'), y = +el.getAttribute('y'), sw = parseFloat(cs.strokeWidth) || 0;
      if (sw && cs.stroke !== 'none') { ctx.strokeStyle = '#ffffff'; ctx.lineWidth = sw; ctx.lineJoin = 'round'; ctx.strokeText(el.textContent, x, y); }
      ctx.fillStyle = cs.fill && cs.fill !== 'none' ? cs.fill : '#0f2a33'; ctx.fillText(el.textContent, x, y);
    }
    ctx.restore();
  }

  async function render(o) {
    try { await document.fonts.ready; } catch (e) {}
    const svg = o.svg, vb = [0, 0, 440, 575], k = MAPW / vb[2], mapH = vb[3] * k;
    const c = document.createElement('canvas'), ctx = c.getContext('2d');
    ctx.font = `700 40px ${FONT}`; const tl = wrap(ctx, o.title, W - 2 * PAD);
    ctx.font = `400 24px ${FONT}`; const sl = o.sub ? wrap(ctx, o.sub, W - 2 * PAD) : [];
    const legRows = Math.ceil(o.legend.length / 3);
    ctx.font = `400 20px ${FONT}`; const nl = o.note ? wrap(ctx, o.note, W - 2 * PAD) : [];
    const H = PAD + tl.length * 48 + sl.length * 32 + 20 + mapH + 30 + 32 + legRows * 36 + 16 + nl.length * 28 + 70;
    c.width = W; c.height = Math.ceil(H);
    ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, W, H);
    let y = PAD;
    ctx.fillStyle = '#0f2a33'; ctx.textBaseline = 'alphabetic';
    ctx.font = `700 40px ${FONT}`; tl.forEach(l => { y += 40; ctx.fillText(l, PAD, y); y += 8; });
    ctx.font = `400 24px ${FONT}`; ctx.fillStyle = '#5b6e73'; sl.forEach(l => { y += 26; ctx.fillText(l, PAD, y); y += 6; });
    y += 20;
    ctx.save(); ctx.translate(PAD, y); ctx.scale(k, k);
    // the page's own zoom changes text and dot sizes, so draw from a reset copy
    const clone = svg.cloneNode(true); clone.setAttribute('viewBox', '0 0 440 575');
    clone.style.cssText = 'position:absolute;left:-9999px;top:0;width:440px'; document.body.appendChild(clone);
    (o.fixClone || (() => {}))(clone);
    drawNode(ctx, clone, clone);
    clone.remove(); ctx.restore();
    y += mapH + 30;
    ctx.fillStyle = '#0f2a33'; ctx.font = `600 22px ${FONT}`; ctx.fillText(o.legendTitle || '', PAD, y); y += 16;
    const colW = (W - 2 * PAD) / 3;
    ctx.font = `400 20px ${FONT}`;
    o.legend.forEach((g, i) => {
      const cx = PAD + (i % 3) * colW, cy = y + Math.floor(i / 3) * 36;
      ctx.fillStyle = g[0]; ctx.fillRect(cx, cy + 6, 26, 22); ctx.strokeStyle = 'rgba(0,0,0,.2)'; ctx.lineWidth = 1; ctx.strokeRect(cx + .5, cy + 6.5, 25, 21);
      ctx.fillStyle = '#0f2a33'; ctx.fillText(g[1], cx + 36, cy + 24);
    });
    y += legRows * 36 + 16;
    ctx.fillStyle = '#5b6e73'; ctx.font = `400 20px ${FONT}`; nl.forEach(l => { y += 22; ctx.fillText(l, PAD, y); y += 6; });
    y += 34; ctx.fillStyle = '#0f6e7a'; ctx.font = `600 20px ${FONT}`; ctx.fillText(location.host ? location.host + location.pathname.replace(/[^/]*$/, '') : 'Tamil Nadu rainfall', PAD, y);
    return c;
  }

  function save(blob, name) {
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
  }

  async function download(o, fmt, msg) {
    msg.textContent = 'Making the ' + fmt.toUpperCase() + '…';
    try {
      const c = await render(o), name = o.file + (fmt === 'jpeg' ? '.jpg' : '.' + fmt);
      if (fmt === 'png') c.toBlob(b => save(b, name), 'image/png');
      else if (fmt === 'jpeg') c.toBlob(b => save(b, name), 'image/jpeg', 0.92);
      else {
        const { jsPDF } = await loadPdfLib();
        const pw = 210, ph = 297, m = 10, r = Math.min((pw - 2 * m) / c.width, (ph - 2 * m) / c.height);
        const doc = new jsPDF({ unit: 'mm', format: 'a4' });
        doc.addImage(c.toDataURL('image/jpeg', 0.92), 'JPEG', (pw - c.width * r) / 2, m, c.width * r, c.height * r);
        doc.save(name);
      }
      msg.textContent = 'Saved ' + name;
    } catch (e) { msg.textContent = e.message || 'Could not make the file.'; }
  }

  // a "Download this map" row: getOpts() returns {svg, title, sub, legend, legendTitle, note, file}
  window.mapDownload = function (container, getOpts) {
    const row = document.createElement('div');
    row.className = 'dl';
    row.innerHTML = '<span>Download this map</span><button data-f="png">PNG</button><button data-f="jpeg">JPEG</button><button data-f="pdf">PDF</button><small></small>';
    container.appendChild(row);
    row.onclick = e => { const b = e.target.closest('[data-f]'); if (b) download(getOpts(), b.dataset.f, row.querySelector('small')); };
  };
})();
