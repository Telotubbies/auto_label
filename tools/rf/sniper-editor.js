(() => {
  const pick = (el, props) => {
    if (!el) return null;
    const s = getComputedStyle(el);
    const o = {};
    props.forEach(p => o[p] = s[p]);
    const r = el.getBoundingClientRect();
    o._box = {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)};
    return o;
  };
  const P = ['color','backgroundColor','fontFamily','fontSize','fontWeight','lineHeight','letterSpacing','padding','margin','borderRadius','border','borderColor','borderWidth','boxShadow','display','gap','alignItems','opacity'];
  const q = s => document.querySelector(s);
  const txt = t => [...document.querySelectorAll('*')].find(e => (e.textContent||'').trim() === t);
  const out = {};
  out.filename = pick(txt('M_M_maxresdefault3.jpg'), P);
  out.testPill = pick(txt('TEST'), P);
  out.leftRailIcon = pick(txt('Labels'), P);
  out.panelTitle = pick(txt('Annotations'), P);
  out.classesTab = pick(txt('Classes'), P);
  out.layersTab = pick(txt('Layers'), P);
  out.classRow = pick(txt('mixer'), P);
  out.findAI = pick(txt('Find Objects with AI'), P);
  out.zoomPill = pick(txt('30%'), P);
  out.reset = pick(txt('RESET'), P);
  out.imagesPanel = pick(txt('Images'), P);
  out.tagsH = pick(txt('Tags'), P);
  const canvasWrap = [...document.querySelectorAll('div')].filter(d => { const r=d.getBoundingClientRect(); return r.width>600 && r.height>500 && getComputedStyle(d).backgroundColor !== 'rgba(0, 0, 0, 0)'; })[0];
  out.canvasBg = pick(canvasWrap, ['backgroundColor','backgroundImage']);
  out.bodyBg = getComputedStyle(document.body).backgroundColor;
  return JSON.stringify(out);
})()
