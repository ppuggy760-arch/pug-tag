/* =====================================================================
   UNTIL THE ALARM — the ART HELPER
   Loaded only when the game is opened with ?dev at the end of the address
   (index.html?dev). Players never load this file.
   It checks your pictures, lets you drag the door boxes into place, place
   every monster on the cameras and in the doorways, aim the jumpscare,
   and reload your pictures without restarting. Every number it finds is
   written out for you, ready to paste into js/config.js.
   See HOW-TO-ADD-ART.md, part 2.
   ===================================================================== */
(function () {
  'use strict';
  const GM = window.__game;
  if (!GM) return;
  const { G, CFG, Art, Sound, Dev } = GM;
  const W = 1600, H = 900;
  const $ = (s) => document.querySelector(s);
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const esc = GM.escapeHtml;
  const f2 = (v) => (+v).toFixed(2), f3 = (v) => (+v).toFixed(3);
  const EDGE = 14; // how close (in stage pixels) to a door box's edge a press grabs that edge

  /* target: what +/-, the wheel and R change ({ kind: 'pose' or 'doorPose', key: the camera or the side }) */
  const D = { panel: null, open: true, target: null, drag: null, click: null, jView: false, errors: 0, lastError: '', report: [], busy: '' };
  const monDef = () => CFG.monsters[G.devMon % Math.max(1, CFG.monsters.length)];
  const monLive = () => G.monsters.find((m) => m.def === monDef());
  const playing = () => G.state === 'night' && !G.paused;

  /* ------------------------------------------------------------------ */
  /*  THE PANEL                                                         */
  /* ------------------------------------------------------------------ */
  /* buttons for the keys (so it works on a tablet too): [label, key, when] */
  const BUTTONS = [['next monster', 'Tab', 'night'], ['see-through (G)', 'g', 'night'], ['jumpscare aim (J)', 'j', 'night'], ['test scare (K)', 'k', 'night'],
    ['at left door (Z)', 'z', 'night'], ['at right door (X)', 'x', 'night'], ['time ×10 (T)', 't', 'night'], ['reload pictures (U)', 'u', 'any']];
  const SIZE_BUTTONS = [['smaller (−)', '-'], ['bigger (+)', '+'], ['flip (R)', 'r']];

  function buildPanel() {
    const p = document.createElement('div');
    p.id = 'devPanel';
    p.innerHTML = '<div class="dTop"><b>ART HELPER</b> <span class="dMon"></span><button class="dMin" title="hide or show (H)">H: hide</button></div>' +
      '<div class="dBody"><div class="dBtns"></div><div class="dHelp"></div><div class="dWarn"></div>' +
      '<details class="dCheck"><summary></summary><div class="dRows"></div></details>' +
      '<pre class="dState"></pre>' +
      '<div class="dOut hidden"><div class="dLabel"></div><textarea readonly spellcheck="false"></textarea>' +
      '<div class="dOutBtns"><button class="dCopy">copy</button><span class="dSize"></span></div></div></div>';
    $('#stage').appendChild(p);
    D.panel = p;
    p.querySelector('.dMin').addEventListener('click', () => toggleOpen());
    p.querySelector('.dCopy').addEventListener('click', copyOut);
    const btns = p.querySelector('.dBtns'), size = p.querySelector('.dSize');
    for (const [label, k, when] of BUTTONS) addBtn(btns, label, k, when);
    for (const [label, k] of SIZE_BUTTONS) addBtn(size, label, k, 'night');
    // a press on the panel never reaches the game (it would place the monster under it)
    p.addEventListener('pointerdown', (e) => e.stopPropagation());
  }
  function addBtn(parent, label, k, when) {
    const b = document.createElement('button');
    b.textContent = label; b.dataset.when = when;
    b.addEventListener('click', () => key(k));
    parent.appendChild(b);
  }
  function toggleOpen() { D.open = !D.open; D.panel.classList.toggle('min', !D.open); D.panel.querySelector('.dMin').textContent = D.open ? 'H: hide' : 'H: show'; }

  /* which side the panel sits on: away from the doorway you are looking at, or from the monster on this camera
     (so it never covers what you are placing) */
  function dockSide() {
    if (G.state !== 'night') return 'right';
    if (G.cams.up) {
      const here = G.monsters.find((m) => m.state === 'roam' && m.room === G.cams.cur), def = here ? here.def : monDef();
      const pose = def && def.poses && def.poses[G.cams.cur];
      return pose && pose.x > 0.5 ? 'left' : 'right';
    }
    const L = GM.doorBox('left'), R = GM.doorBox('right');
    if (L.x + L.w > 0 && L.x < W / 2) return 'right';
    if (R.x < W && R.x + R.w > W / 2) return 'left';
    return 'left';
  }

  let lastState = '', lastWarn = '', lastHelp = '';
  function updatePanel() {
    const p = D.panel;
    if (!p) return;
    const side = dockSide();
    p.classList.toggle('dockL', side === 'left'); p.classList.toggle('dockR', side === 'right');
    p.classList.toggle('cams', G.state === 'night' && G.cams.up);
    p.classList.toggle('idle', G.state !== 'night'); // (menus: down in the corner, off the title)
    const def = monDef();
    p.querySelector('.dMon').textContent = def ? '· monster: ' + def.name + ' [' + (def.behavior || 'walker') + ']' : '';
    for (const b of p.querySelectorAll('button[data-when]')) b.classList.toggle('hidden', b.dataset.when === 'night' && !playing());
    p.querySelector('.dSize').classList.toggle('hidden', !D.target);
    if (!D.open) return;
    const help = helpText();
    if (help !== lastHelp) { lastHelp = help; p.querySelector('.dHelp').textContent = help; }
    const warn = warnHtml();
    if (warn !== lastWarn) { lastWarn = warn; p.querySelector('.dWarn').innerHTML = warn; }
    const st = stateText();
    if (st !== lastState) { lastState = st; p.querySelector('.dState').textContent = st; }
  }

  function helpText() {
    if (D.busy) return D.busy;
    if (G.state !== 'night') return 'Start a night to place your monsters and doors. Everything you place is written out below, ready to paste into js/config.js.';
    if (D.jView) return 'JUMPSCARE AIM: click the part of the picture that should rush at the player (its face). J or Esc: back.';
    if (G.cams.up) return G.devGhost ? 'SEE-THROUGH MONSTER: click where its FEET go on this camera. Wheel or +/−: size. R: flip.'
      : 'G: a see-through monster to place on this camera.';
    return G.devGhost ? 'SEE-THROUGH MONSTER: turn a light ON (A or D), then click where its FEET go in that doorway. Wheel or +/−: size. R: flip.'
      : 'Light OFF: drag a green door box by its edges or corners (or its middle to move it). Click anywhere else in the room for that spot\'s x and y.';
  }
  function warnHtml() {
    const w = GM.configWarnings.map((x) => '• ' + esc(x));
    if (D.errors) w.unshift(`• the game hit a problem ${D.errors} time(s): ${esc(D.lastError)}`);
    return w.length ? '<b>CONFIG.JS WARNINGS</b>\n' + w.join('\n') : '';
  }
  function stateText() {
    if (G.state !== 'night') return '';
    const C = G.cams, mins = Math.floor(G.nightT / GM.hourSec() * 60), clock = (Math.floor(mins / 60) || 12) + ':' + String(mins % 60).padStart(2, '0');
    const head = `night ${G.night} · ${clock} AM · time ×${G.timeScale} · Lucidity ${G.luc.toFixed(1)} · using ${G.usage.toFixed(2)} · doors held ${G.doors.left.held.toFixed(0)}/${G.doors.right.held.toFixed(0)} s` +
      (C.up ? ` · camera ${C.cur}` : '') + (G.lies.length ? ' · lie: ' + G.lies.map((l) => l.kind + ' ' + (l.side || l.room)).join(', ') : '');
    const mons = G.monsters.map((m) => {
      const where = m.state === 'roam' ? '@' + m.room : m.state === 'door' ? '@door:' + m.door + ' wait ' + Math.max(0, m.linger).toFixed(1) : m.state;
      const brain = m.def.behavior || 'walker', extra = brain === 'shy' ? ` (+${m.extra}, ignored ${m.ignored.toFixed(0)} s)` : brain === 'sleeper' ? (m.awake > 0 ? ' (awake)' : ' (asleep)') : '';
      return `${m.def === monDef() ? '▸ ' : '  '}${m.def.name} [${brain}] ${where} · level ${m.lvl}${extra} · next try ${Math.max(0, m.timer).toFixed(1)} s`;
    });
    return head + '\n' + mons.join('\n');
  }

  /* the line to paste: label says where it goes */
  function output(label, text) {
    const o = D.panel.querySelector('.dOut');
    o.classList.remove('hidden');
    o.querySelector('.dLabel').textContent = label;
    o.querySelector('textarea').value = text;
    o.querySelector('.dCopy').textContent = 'copy';
  }
  function copyOut() {
    const ta = D.panel.querySelector('.dOut textarea'), btn = D.panel.querySelector('.dCopy');
    const done = (ok) => { btn.textContent = ok ? 'copied!' : 'select it and copy'; setTimeout(() => { btn.textContent = 'copy'; }, 1200); };
    const fallback = () => { ta.focus(); ta.select(); let ok = false; try { ok = document.execCommand('copy'); } catch (e) { /* not allowed */ } ta.blur(); done(ok); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(ta.value).then(() => done(true), fallback);
    else fallback();
  }

  /* ------------------------------------------------------------------ */
  /*  THE ART CHECKLIST: every picture and sound config.js asks for,    */
  /*  with plain-language warnings (Art.report)                         */
  /* ------------------------------------------------------------------ */
  let alphaBlocked = false; // (opened from a file, the browser won't let the helper look at the pixels)
  /* does the picture have see-through corners? null when the browser won't say */
  function hasAlpha(img) {
    try {
      const c = document.createElement('canvas'); c.width = 32; c.height = 32;
      const x = c.getContext('2d'); x.drawImage(img, 0, 0, 32, 32);
      const d = x.getImageData(0, 0, 32, 32).data, at = (px, py) => d[(py * 32 + px) * 4 + 3];
      return [at(0, 0), at(31, 0), at(0, 31), at(31, 31)].some((a) => a < 250);
    } catch (e) { alphaBlocked = true; return null; }
  }
  const fileName = (p) => String(p || '').split('/').pop();
  /* the size each kind of picture is best drawn at */
  const WANT = [[/^office\.image$/, '2400×900'], [/^camera|^youCam|^bedroom/, '1600×900'], [/^office\.doors/, 'the shape of its door box']];
  const wantFor = (slot) => (WANT.find(([re]) => re.test(slot)) || [0, ''])[1];
  const ratioOff = (w, h, want) => Math.abs(w / h / want - 1);

  function buildReport() {
    alphaBlocked = false;
    const rows = [];
    const byMonster = {};
    for (const f of Art.files) {
      const r = { slot: f.slot, path: f.path, found: f.w > 0, w: f.w, h: f.h, want: wantFor(f.slot), opt: f.opt, warn: [] };
      const name = fileName(f.path), size = `${f.w}×${f.h}`;
      if (!r.found) {
        if (/frame/.test(f.slot) && f.path) r.warn.push(`${name} is missing, so this frame is skipped.`);
        rows.push(r); continue;
      }
      if (f.slot === 'office.image' && f.w / f.h < 2.2) {
        r.warn.push(`${name} is ${size}. Make it wider (about 2400×900) so there is room to look around.` +
          (Art.officeBand && Art.officeBand.k < 1 ? ' For now the game zooms in, so its top and bottom are cut off.' : ''));
      }
      if (/^camera|^youCam|^bedroom/.test(f.slot) && ratioOff(f.w, f.h, 16 / 9) > 0.08) r.warn.push(`${name} is ${size}: its edges will be cropped (use 16:9, like 1600×900).`);
      const door = /^office\.doors\.(left|right)\./.exec(f.slot);
      if (door) { const d = GM.officeDoor(door[1]), want = d.w * GM.officeWidthFor(Art.office) / (d.h * H); if (ratioOff(f.w, f.h, want) > 0.15) r.warn.push(`${name} is ${size}: it gets stretched to fit its door box.`); }
      if ((/frame/.test(f.slot) || /evidence/.test(f.slot)) && f.img && hasAlpha(f.img) === false) r.warn.push(`${name} has no see-through background. Cut the background out (a transparent PNG).`);
      const mon = /^(.*) (frame|jumpscare frame|sleep frame) \d+$/.exec(f.slot);
      if (mon) (byMonster[mon[1] + '|' + mon[2]] = byMonster[mon[1] + '|' + mon[2]] || []).push(r);
      rows.push(r);
    }
    // the frames of one animation should all be the same size, or the monster jumps around while it moves
    for (const k in byMonster) {
      const list = byMonster[k].filter((r) => r.found), sizes = [...new Set(list.map((r) => r.w + '×' + r.h))];
      if (sizes.length > 1) list[0].warn.push(`${k.split('|')[0]}'s ${k.split('|')[1]}s are not all the same size (${sizes.join(', ')}): it will jump around. Use the same canvas size for every frame.`);
    }
    for (const def of CFG.monsters) { const s = bodyShift(def); if (s) rows.push({ slot: def.name + ' (moving)', path: '', found: true, info: s, warn: [] }); }
    for (const name of Object.keys(CFG.sounds || {})) {
      const miss = Sound.missing.has(name), opt = GM.OPTIONAL_SOUNDS.indexOf(name) >= 0;
      rows.push({ slot: 'sound ' + name, path: CFG.sounds[name], found: !miss, opt, sound: true,
        warn: miss && !opt ? [`${fileName(CFG.sounds[name])} is missing: the game plays nothing there.`] : [] });
    }
    D.report = Art.report = rows;
    drawReport();
  }
  /* how far a monster's body moves sideways between its frames (seen as the onion skin in Extras) */
  function bodyShift(def) {
    const A = Art.monsters[def.id];
    if (!A || A.missing || A.frames.length < 2) return '';
    const boxes = A.frames.map(opaqueBox).filter(Boolean);
    if (boxes.length < 2) return '';
    const mids = boxes.map((b) => (b.x + b.w / 2) * A.frames[0].width), shift = Math.round(Math.max(...mids) - Math.min(...mids));
    return shift > 40 ? `its body moves up to ${shift} px sideways between frames (see the onion skin in Extras). That's fine for a sway; for a still monster, line the frames up.` : '';
  }
  function drawReport() {
    const rows = D.report, look = rows.filter((r) => r.warn.length).length;
    const ok = rows.filter((r) => r.found && !r.warn.length && !r.info).length, stand = rows.filter((r) => !r.found && !r.warn.length).length;
    D.panel.querySelector('.dCheck summary').textContent = `Art checklist: ${ok} fine · ${stand} not added yet · ${look} to look at` + (alphaBlocked ? ' · (the see-through check needs a local server)' : '');
    const rank = (r) => (r.warn.length ? 0 : r.info ? 1 : r.found ? 3 : 2); // (what needs a look comes first)
    D.panel.querySelector('.dRows').innerHTML = rows.slice().sort((a, c) => rank(a) - rank(c)).map((r) => {
      const icon = r.warn.length ? '<i class="bad">!</i>' : r.info ? '<i class="info">i</i>' : r.found ? '<i class="ok">✓</i>' : '<i class="dim">–</i>';
      const what = r.sound ? '' : r.found ? (r.w ? ` ${r.w}×${r.h}` + (r.warn.length && r.want ? ` (best: ${r.want})` : '') : '')
        : r.path ? ' not drawn yet: the game uses a stand-in' + (r.want ? ` (draw it ${r.want})` : '') : ' (empty: the built-in look)';
      const so = r.sound && !r.found ? (r.opt ? ' optional, not added yet' : ' MISSING') : '';
      return `<div>${icon} <b>${esc(r.slot)}</b> <span class="dim">${esc(fileName(r.path))}</span>${esc(what + so)}` +
        r.warn.concat(r.info ? [r.info] : []).map((w) => `<div class="why">${esc(w)}</div>`).join('') + '</div>';
    }).join('');
    if (look) D.panel.querySelector('.dCheck').open = true;
  }

  /* ------------------------------------------------------------------ */
  /*  PLACING THINGS                                                    */
  /* ------------------------------------------------------------------ */
  /* the band of your desk room picture that is shown (see fitOffice in game.js): band fractions <-> picture fractions */
  const band = () => Art.officeBand || { y0: 0, k: 1 };
  const toPicY = (y) => band().y0 + y * band().k;

  /* a monster's pose on the camera you are looking at (made if it has none yet) */
  function camPose() {
    const def = monDef(); def.poses = def.poses || {};
    return (def.poses[G.cams.cur] = def.poses[G.cams.cur] || { x: 0.5, y: 1.02, h: 0.7 });
  }
  function doorPose(side) {
    const def = monDef(); def.doorPose = def.doorPose || {};
    return (def.doorPose[side] = def.doorPose[side] || Object.assign({}, GM.doorPoseOf({ def: {} }, side)));
  }
  const poseLine = (key, p) => `${(key + ':').padEnd(6)} { x: ${f2(p.x)}, y: ${f2(p.y)}, h: ${f2(p.h || 0.7)}${p.flip ? ', flip: true' : ''} },`;
  function writePose() {
    const t = D.target;
    if (!t) return;
    const id = monDef().id;
    if (t.kind === 'pose') output(`Paste into config.js (monster "${id}", under poses:)`, poseLine(t.key, camPose()));
    else output(`Paste into config.js (monster "${id}", under doorPose:)`, poseLine(t.key, doorPose(t.key)));
  }
  function resize(f) {
    const t = D.target;
    if (!t) return;
    const p = t.kind === 'pose' ? camPose() : doorPose(t.key);
    p.h = clamp((p.h || 0.7) * f, 0.05, 3); writePose();
  }
  function flip() {
    const t = D.target;
    if (!t) return;
    const p = t.kind === 'pose' ? camPose() : doorPose(t.key);
    p.flip = !p.flip; writePose();
  }

  /* a door box from config.js, ready to paste back (its pictures stay as they are) */
  function doorLine(side) {
    const d = CFG.office.doors[side], q = (k) => `${k}: "${d[k] || ''}"`;
    return `${side}:${side === 'left' ? '  ' : ' '}{ x: ${f3(d.x)}, y: ${f3(d.y)}, w: ${f3(d.w)}, h: ${f3(d.h)}, ${q('darkImage')}, ${q('litImage')}, ${q('closedImage')} },`;
  }
  /* which part of a door box is under the pointer: { side, l, r, t, b } (edges) or { side, move } (inside) */
  function doorHit(p) {
    for (const side of ['left', 'right']) {
      const b = GM.doorBox(side);
      if (p.x < b.x - EDGE || p.x > b.x + b.w + EDGE || p.y < b.y - EDGE || p.y > b.y + b.h + EDGE) continue;
      const e = { side, l: Math.abs(p.x - b.x) <= EDGE, r: Math.abs(p.x - b.x - b.w) <= EDGE, t: Math.abs(p.y - b.y) <= EDGE, b: Math.abs(p.y - b.y - b.h) <= EDGE };
      if (e.l || e.r || e.t || e.b) return e;
      if (p.x > b.x && p.x < b.x + b.w && p.y > b.y && p.y < b.y + b.h) return { side, move: true };
    }
    return null;
  }
  /* drag a door box: the change goes into config.js's numbers straight away (in your picture's own fractions) */
  function dragDoor(p) {
    const g = D.drag, dx = (p.x - g.x0) / G.officeW, dy = (p.y - g.y0) / H, s = g.start;
    let { x, y, w, h } = s;
    if (g.move) { x += dx; y += dy; }
    if (g.l) { x += dx; w -= dx; }
    if (g.r) w += dx;
    if (g.t) { y += dy; h -= dy; }
    if (g.b) h += dy;
    w = Math.max(0.03, w); h = Math.max(0.05, h);
    const d = CFG.office.doors[g.side], k = band().k;
    d.x = +f3(clamp(x, 0, 1 - w)); d.w = +f3(w); d.y = +f3(toPicY(y)); d.h = +f3(h * k);
    g.moved = true;
  }
  /* after a drag: the stand-in doorway, shutter (and stand-in room) are painted again at the new size */
  function repaintDoor(side) {
    const A = Art.doors[side];
    if (A.dark && !A.own.dark) A.dark = GM.paintDoorway(side, false);
    if (!A.own.lit) A.lit = GM.paintDoorway(side, true);
    if (!A.own.closed) A.closed = GM.paintShutter(side);
    if (Art.officeMissing) Art.office = GM.paintOffice();
  }
  function officeSpotLine(p) {
    const nx = (p.x - GM.officeOriginX()) / G.officeW, ny = toPicY(p.y / H);
    output('A spot in your desk room picture (for office.clock, window or lamp: x and y)', `x: ${f3(nx)}, y: ${f3(ny)}`);
  }

  /* the jumpscare aim: the first jumpscare frame, as big as fits, with a crosshair on jumpscareFocus */
  function jumpRect() {
    const A = Art.monsters[monDef().id], img = A.jump[0], s = Math.min(W * 0.9 / img.width, H * 0.86 / img.height);
    return { img, w: img.width * s, h: img.height * s, x: (W - img.width * s) / 2, y: (H - img.height * s) / 2 };
  }
  function setJView(on) {
    D.jView = on;
    if (on) G.grace = Math.max(G.grace, 1e9); else if (!G.devGhost) G.grace = 0; // (nothing moves while you aim)
  }

  /* ------------------------------------------------------------------ */
  /*  HOOKS (called by game.js)                                         */
  /* ------------------------------------------------------------------ */
  function key(k) {
    if (k === 'h' || k === 'H') { toggleOpen(); return true; }
    if (k === 'u' || k === 'U') { reload(); return true; }
    if (!playing()) return false;
    if (D.jView && (k === 'Escape' || k === 'j' || k === 'J')) { setJView(false); return true; }
    const m = monLive(), lk = k.length === 1 ? k.toLowerCase() : k;
    switch (lk) {
      case 'Tab': if (CFG.monsters.length) { G.devMon = (G.devMon + 1) % CFG.monsters.length; D.target = null; } return true;
      case 't': G.timeScale = G.timeScale === 1 ? 10 : G.timeScale === 10 ? 40 : 1; return true;
      case 'n': GM.endLesson(false); G.nightT = 6 * GM.hourSec() - 2; return true;
      case 'k': if (m) GM.jumpscare(m); return true;
      case 'm': for (const mm of G.monsters) GM.monsterMove(mm, true); return true;
      case 'l': G.luc = 5; return true;
      case 'v': if (G.monsters.length) { G.lies = []; GM.spawnLie(); } return true; // (it goes again at once if a monster is near a door)
      case 'y': GM.toggleCams(true); GM.endEvent(); GM.startEvent(GM.DREAM_EVENTS.find((e) => e.id === 'youCam')); return true; // CAM 7 now, any night
      case 'z': case 'x': if (m) { m.state = 'door'; m.door = lk === 'z' ? 'left' : 'right'; m.room = null; m.linger = 999; m.seen = false; } return true;
      case 'g': G.devGhost = !G.devGhost; G.grace = G.devGhost || D.jView ? 1e9 : 0; return true;
      case 'j': setJView(!D.jView); return true;
      case '+': case '=': if (!D.target) return false; resize(1.05); return true;
      case '-': case '_': if (!D.target) return false; resize(1 / 1.05); return true;
      case 'r': if (!D.target) return false; flip(); return true;
      default: return false;
    }
  }

  function down(p) {
    if (D.jView) { // aim the jumpscare
      const r = jumpRect(), def = monDef();
      def.jumpscareFocus = { x: +f2(clamp((p.x - r.x) / r.w, 0, 1)), y: +f2(clamp((p.y - r.y) / r.h, 0, 1)) };
      output(`Paste into config.js (monster "${def.id}": replace its jumpscareFocus line)`, `jumpscareFocus: { x: ${f2(def.jumpscareFocus.x)}, y: ${f2(def.jumpscareFocus.y)} },`);
      return true;
    }
    if (G.cams.up) { // place its feet on this camera
      if (!G.devGhost || G.cams.cur === GM.YOU_CAM.id) return false;
      const box = GM.camFeedBox(), pose = camPose();
      pose.x = +f2(clamp((p.x - box.x) / box.w, -0.5, 1.5)); pose.y = +f2(clamp((p.y - box.y) / box.h, -0.5, 2));
      D.target = { kind: 'pose', key: G.cams.cur }; writePose();
      return true;
    }
    const hit = doorHit(p);
    if (hit && G.devGhost && G.doors[hit.side].light) { // place its feet in this lit doorway
      const b = GM.doorBox(hit.side), pose = doorPose(hit.side);
      pose.x = +f2(clamp((p.x - b.x) / b.w, 0, 1)); pose.y = +f2(clamp((p.y - b.y) / b.h, 0, 1.5));
      D.target = { kind: 'doorPose', key: hit.side }; writePose();
      return true;
    }
    if (hit && !G.doors[hit.side].light) { // grab a door box
      D.drag = Object.assign({ x0: p.x, y0: p.y, start: Object.assign({}, GM.officeDoor(hit.side)), moved: false }, hit);
      G.devDrag = true;
      return true;
    }
    D.click = p; // a plain click in the room: its x and y (on release)
    return false;
  }
  function move(p) {
    if (D.drag) { dragDoor(p); return; }
    if (playing() && !G.cams.up && !D.jView) { // the cursor shows what a press would grab
      const h = doorHit(p), lit = h && G.doors[h.side].light;
      $('#stage').style.cursor = !h || lit ? '' : h.move ? 'move' : (h.l || h.r) && (h.t || h.b) ? ((h.l && h.t) || (h.r && h.b) ? 'nwse-resize' : 'nesw-resize') : h.l || h.r ? 'ew-resize' : 'ns-resize';
    } else $('#stage').style.cursor = '';
  }
  function up(p) {
    if (D.drag) {
      const g = D.drag;
      D.drag = null; G.devDrag = false;
      if (g.moved) { repaintDoor(g.side); output('Paste into config.js, under office: doors: (it replaces the whole "' + g.side + ':" line)', doorLine(g.side)); }
      else officeSpotLine(p);
      return;
    }
    if (D.click && playing() && !G.cams.up && Math.abs(p.x - D.click.x) < 6 && Math.abs(p.y - D.click.y) < 6) officeSpotLine(p);
    D.click = null;
  }
  function wheel(e) {
    if (!D.target || !playing()) return false;
    resize(e.deltaY < 0 ? 1.04 : 1 / 1.04);
    return true;
  }

  /* the see-through monster on a camera */
  function camGhost(c, cam, box) {
    if (!G.devGhost || cam.id === GM.YOU_CAM.id) return;
    const def = monDef(), A = def && Art.monsters[def.id];
    if (!A) return;
    GM.drawSprite(c, A.soft[Math.floor(G.t * (def.fps || 4)) % A.soft.length], box, (def.poses && def.poses[cam.id]) || { x: 0.5, y: 1.02, h: 0.7 }, 0.85);
  }
  /* … and in a lit doorway (only where no real monster stands) */
  function inDoorway(c, side, box) {
    if (!G.devGhost || !G.doors[side].light || G.monsters.some((m) => m.state === 'door' && m.door === side)) return;
    const def = monDef(), A = def && Art.monsters[def.id];
    if (A) GM.drawSprite(c, A.soft[Math.floor(G.t * (def.fps || 4)) % A.soft.length], box, GM.doorPoseOf({ def }, side), 0.7);
  }
  /* the green door box, its numbers and its corner handles */
  function doorFrame(c, side, box) {
    const d = CFG.office.doors[side], grabbed = D.drag && D.drag.side === side;
    c.save(); c.strokeStyle = grabbed ? '#bfffbf' : '#3f3'; c.lineWidth = grabbed ? 3 : 2; c.setLineDash([8, 6]);
    c.strokeRect(box.x, box.y, box.w, box.h); c.setLineDash([]);
    c.fillStyle = '#3f3';
    for (const [hx, hy] of [[box.x, box.y], [box.x + box.w, box.y], [box.x, box.y + box.h], [box.x + box.w, box.y + box.h]]) c.fillRect(hx - 5, hy - 5, 10, 10);
    c.font = '22px VT323, monospace';
    c.fillText(`${side} door  x:${f3(d.x)} y:${f3(d.y)} w:${f3(d.w)} h:${f3(d.h)}`, box.x + 4, box.y - 10);
    c.restore();
  }
  /* on top of everything: the stand-in hint, and the jumpscare aim */
  function overlay(ctx) {
    const st = G.state;
    if (st === 'night' && !D.jView) {
      if (G.cams.t >= 1) {
        const cam = GM.camById[G.cams.cur];
        if (cam === GM.YOU_CAM) { if (!Art.youCam) standInHint(ctx, (CFG.youCam || {}).image || 'assets/rooms/cam7_you.png'); }
        else if (cam && Art.camMissing[cam.id]) standInHint(ctx, cam.image);
      } else if (Art.officeMissing) standInHint(ctx, CFG.office.image);
    }
    if ((st === 'asleep' || st === 'morning' || st === 'win') && Art.bedroomMissing) standInHint(ctx, (CFG.bedroom || {}).image || 'assets/rooms/bedroom.png');
    if (st === 'night' && D.jView) {
      const r = jumpRect(), f = monDef().jumpscareFocus || { x: 0.5, y: 0.2 }, fx = r.x + f.x * r.w, fy = r.y + f.y * r.h;
      ctx.save(); ctx.fillStyle = 'rgba(0,0,0,.92)'; ctx.fillRect(0, 0, W, H);
      ctx.drawImage(r.img, r.x, r.y, r.w, r.h);
      ctx.strokeStyle = '#3f3'; ctx.lineWidth = 2; ctx.strokeRect(r.x, r.y, r.w, r.h);
      ctx.beginPath(); ctx.moveTo(fx - 40, fy); ctx.lineTo(fx + 40, fy); ctx.moveTo(fx, fy - 40); ctx.lineTo(fx, fy + 40); ctx.stroke();
      ctx.beginPath(); ctx.arc(fx, fy, 18, 0, 7); ctx.stroke();
      ctx.restore();
    }
  }
  /* which file would replace the stand-in picture on screen right now */
  function standInHint(c, path) {
    const text = 'stand-in art — your picture goes at ' + path;
    c.save();
    c.font = '24px VT323, monospace'; c.textAlign = 'center'; c.textBaseline = 'middle';
    const w = c.measureText(text).width + 28;
    c.fillStyle = 'rgba(0,0,0,.6)'; c.fillRect(W / 2 - w / 2, 44, w, 34);
    c.fillStyle = 'rgba(233,223,207,.85)'; c.fillText(text, W / 2, 62);
    c.restore();
  }

  /* the Extras gallery: every frame at once, faint, each with its outline (the onion skin) */
  const boxCache = new WeakMap();
  /* the box around a frame's visible pixels, as fractions of the frame (null when the browser won't say) */
  function opaqueBox(img) {
    if (boxCache.has(img)) return boxCache.get(img);
    let box = null;
    try {
      const s = Math.min(1, 160 / Math.max(img.width, img.height)), w = Math.max(1, Math.round(img.width * s)), h = Math.max(1, Math.round(img.height * s));
      const c = document.createElement('canvas'); c.width = w; c.height = h;
      const x = c.getContext('2d'); x.drawImage(img, 0, 0, w, h);
      const d = x.getImageData(0, 0, w, h).data;
      let x0 = w, y0 = h, x1 = -1, y1 = -1;
      for (let py = 0; py < h; py++) for (let px = 0; px < w; px++) if (d[(py * w + px) * 4 + 3] > 40) { x0 = Math.min(x0, px); x1 = Math.max(x1, px); y0 = Math.min(y0, py); y1 = Math.max(y1, py); }
      if (x1 >= 0) box = { x: x0 / w, y: y0 / h, w: (x1 - x0 + 1) / w, h: (y1 - y0 + 1) / h };
    } catch (e) { alphaBlocked = true; }
    boxCache.set(img, box);
    return box;
  }
  function gallery(x, A, cv) {
    A.frames.forEach((f, i) => {
      const s = Math.min(cv.width / f.width, cv.height / f.height), w = f.width * s, h = f.height * s, ox = (cv.width - w) / 2, oy = (cv.height - h) / 2;
      x.globalAlpha = 0.22; x.drawImage(f, ox, oy, w, h); x.globalAlpha = 1;
      const b = opaqueBox(f);
      if (b) { x.strokeStyle = `hsla(${i * 360 / A.frames.length}, 90%, 60%, .8)`; x.lineWidth = 1; x.strokeRect(ox + b.x * w + 0.5, oy + b.y * h + 0.5, b.w * w, b.h * h); }
    });
  }

  /* U: load every picture again (after you saved a new one), without restarting the night */
  async function reload() {
    if (/…/.test(D.busy)) return; // (already reloading)
    D.busy = 'reloading your pictures…'; updatePanel();
    try {
      await GM.loadArt(() => {}, Date.now());
      for (const m of G.monsters) m.art = Art.monsters[m.id];
      for (const L of G.lies) L.frame %= L.who.art.soft.length;
      G.officeW = GM.officeWidthFor(Art.office) * G.stretch;
      G.scroll = clamp(G.scroll, 0, Math.max(0, G.officeW - W));
      buildReport();
      D.busy = 'pictures reloaded ✓';
      setTimeout(() => { D.busy = ''; }, 1500); // (just the message: the helper's own panel, not the night)
    } catch (e) { D.busy = ''; error(e); }
    updatePanel();
  }

  function error(err) { D.errors++; D.lastError = String(err && err.message || err); }

  function booted() {
    if (D.panel) return;
    buildPanel();
    buildReport();
    updatePanel();
    setInterval(updatePanel, 120);
    console.log('[dev] art helper on. Missing sounds:', Array.from(Sound.missing));
  }

  Object.assign(Dev, { inDoorway, doorFrame, camGhost, overlay, gallery, booted, error, key, down, move, up, wheel });
  if (G.ready) booted();
  window.__dev = { D, buildReport, reload, doorLine, doorHit, bodyShift, opaqueBox, updatePanel, key };
})();
