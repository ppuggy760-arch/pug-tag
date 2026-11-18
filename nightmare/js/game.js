/* =====================================================================
   UNTIL THE ALARM — game engine
   You normally don't need to touch this file: pictures, monsters,
   rooms, sounds and text all live in js/config.js.
   ===================================================================== */
(function () {
  'use strict';

  const CFG = window.GAME_CONFIG;
  const W = 1600, H = 900;
  const NIGHTS = 5;
  const DEV = /[?&]dev(=|&|$)/.test(location.search);
  const $ = (s) => document.querySelector(s);
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const rand = (a, b) => a + Math.random() * (b - a);
  const randi = (a, b) => Math.floor(rand(a, b + 1));
  const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
  const ease = (t) => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
  function mulberry32(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      let t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  function makeCanvas(w, h) { const c = document.createElement('canvas'); c.width = Math.max(1, Math.round(w)); c.height = Math.max(1, Math.round(h)); return c; }
  const show = (el) => el.classList.remove('hidden');
  const hide = (el) => el.classList.add('hidden');
  const fmtHour = (h) => (h === 0 ? 12 : h) + ' AM';
  const isDoor = (r) => typeof r === 'string' && r.indexOf('door:') === 0;
  const sidePan = (side, other) => side === 'left' ? -0.85 : side === 'right' ? 0.85 : (other || 0);
  /* smooth "noise" for camera shake: two sines that never line up */
  const nz = (a) => (Math.sin(a) + Math.sin(a * 1.73 + 1.1)) / 2;
  const TOUCH = !!(window.matchMedia && matchMedia('(pointer: coarse)').matches);
  const TAP = TOUCH ? 'tap' : 'click';

  function escapeHtml(s) { return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
  /* IM Fell draws old-style digits ("NIGHT ı"), so numbers get the VT323 font */
  function numify(s) { return escapeHtml(s).replace(/\d+/g, '<span class="num">$&</span>'); }

  /* how many letters you must change to turn a into b (for "did you mean …?") */
  function editDistance(a, b) {
    const d = [];
    for (let i = 0; i <= a.length; i++) { d[i] = [i]; for (let j = 1; j <= b.length; j++) d[i][j] = i ? 0 : j; }
    for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++) {
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    return d[a.length][b.length];
  }
  /* the closest choice within 2 letters, or null when there is none (or two are equally close) */
  function didYouMean(word, choices) {
    let best = null, bestD = 3, tie = false;
    for (const c of choices) {
      const dd = editDistance(String(word).toLowerCase(), String(c).toLowerCase());
      if (dd < bestD) { bestD = dd; best = c; tie = false; } else if (dd === bestD && c !== best) tie = true;
    }
    return tie ? null : best;
  }

  /* ------------------------------------------------------------------ */
  /*  SAVE                                                              */
  /* ------------------------------------------------------------------ */
  const SAVE_KEY = 'until-the-alarm.save.v1';
  const save = { night: 1, beaten: 0, vol: 85, music: 70, fx: 'full', custom: {} };
  function loadSave() {
    let stored = null;
    try {
      stored = JSON.parse(localStorage.getItem(SAVE_KEY) || 'null');
      if (stored && typeof stored === 'object') Object.assign(save, stored);
    } catch (e) { /* private mode etc. */ }
    // first visit + the device asks for less motion: start on "Low" effects
    if (!stored && window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) save.fx = 'low';
    save.night = clamp(parseInt(save.night, 10) || 1, 1, NIGHTS);
    save.beaten = clamp(parseInt(save.beaten, 10) || 0, 0, NIGHTS);
    if (!['full', 'low', 'off'].includes(save.fx)) save.fx = 'full';
    if (!save.custom || typeof save.custom !== 'object') save.custom = {};
    applyFxSetting();
  }
  function writeSave() { try { localStorage.setItem(SAVE_KEY, JSON.stringify(save)); } catch (e) { /* ignore */ } }

  /* "Dream effects" setting as a number: Full 1, Low .4, Off 0. Multiply anything flashy or moving by it. */
  const fxMul = () => ({ full: 1, low: 0.4, off: 0 })[save.fx];
  function applyFxSetting() { document.documentElement.dataset.fx = save.fx; }

  /* ------------------------------------------------------------------ */
  /*  SOUND  (Web Audio when served from a website, plain <audio> when  */
  /*  opened straight from a file, because browsers block the former)   */
  /* ------------------------------------------------------------------ */
  const Sound = {
    defs: CFG.sounds || {},
    web: false, ctx: null, master: null, musicBus: null, sfxBus: null,
    buffers: {}, pools: {}, loops: {}, missing: new Set(), loaded: 0, total: 0,

    init() {
      const AC = window.AudioContext || window.webkitAudioContext;
      this.web = !!AC && location.protocol !== 'file:';
      if (this.web) {
        try {
          this.ctx = new AC();
          this.master = this.ctx.createGain(); this.master.connect(this.ctx.destination);
          this.musicBus = this.ctx.createGain(); this.musicBus.connect(this.master);
          this.sfxBus = this.ctx.createGain(); this.sfxBus.connect(this.master);
        } catch (e) { this.web = false; }
      }
      this.applyVolumes();
    },

    load(onEach) {
      const names = Object.keys(this.defs);
      this.total = names.length;
      return Promise.all(names.map((name) => {
        const url = this.defs[name];
        const done = (ok) => { if (!ok) this.missing.add(name); this.loaded++; if (onEach) onEach(); };
        if (!url) { done(false); return Promise.resolve(); }
        if (this.web) {
          return fetch(url)
            .then((r) => { if (!r.ok) throw new Error(r.status); return r.arrayBuffer(); })
            .then((ab) => new Promise((res, rej) => this.ctx.decodeAudioData(ab, res, rej)))
            .then((b) => { this.buffers[name] = b; done(true); })
            .catch(() => done(false));
        }
        return new Promise((res) => {
          const a = this._el(name);
          let fin = false;
          const end = (ok) => { if (fin) return; fin = true; done(ok); res(); };
          a.addEventListener('canplaythrough', () => end(true), { once: true });
          a.addEventListener('error', () => end(false), { once: true });
          setTimeout(() => end(!a.error), 2500); // some browsers wait for a click before loading
          this.pools[name] = [a];
          a.load();
        });
      }));
    },

    _el(name) {
      const a = new Audio(this.defs[name]);
      a.preload = 'auto';
      a.preservesPitch = false; a.mozPreservesPitch = false; a.webkitPreservesPitch = false;
      a.addEventListener('error', () => this.missing.add(name));
      return a;
    },

    /* first click: let the browser play sound at all */
    unlock() {
      this.resume();
      if (!this.web) { // poke every element once so mobile browsers allow later playback
        for (const k in this.pools) for (const a of this.pools[k]) { a.muted = true; const p = a.play(); if (p && p.then) p.then(() => { a.pause(); a.muted = false; a.currentTime = 0; }).catch(() => { a.muted = false; }); else a.muted = false; }
      }
    },
    /* make sure a paused (suspended) audio context is running again */
    resume() { if (this.web && this.ctx && this.ctx.state !== 'running') this.ctx.resume().catch(() => {}); },

    applyVolumes() {
      const mv = save.vol / 100, mu = save.music / 100;
      if (this.web) {
        this.master.gain.value = mv * mv;
        this.musicBus.gain.value = mu * mu;
      }
    },
    _htmlVol(v, music) { const mv = save.vol / 100, mu = save.music / 100; return clamp(v * mv * mv * (music ? mu * mu : 1), 0, 1); },

    /* can this sound play? (false for missing files and optional slots that were never filled) */
    has(name) { return !!name && !this.missing.has(name) && (this.web ? !!this.buffers[name] : !!this.defs[name]); },
    /* play the first sound in the list that exists, e.g. playAny(['reality_snap', 'ui_click']) */
    playAny(names, opts) { for (const n of names) if (this.has(n)) return this.play(n, opts); return null; },

    /* a backwards copy of a sound (Web Audio only; null when opened from a file) */
    reversed(name) {
      if (!this.web || !this.has(name)) return null;
      const key = name + '~';
      if (!this.buffers[key]) {
        const src = this.buffers[name];
        const out = this.ctx.createBuffer(src.numberOfChannels, src.length, src.sampleRate);
        for (let ch = 0; ch < src.numberOfChannels; ch++) {
          const a = src.getChannelData(ch), b = out.getChannelData(ch);
          for (let i = 0, n = a.length; i < n; i++) b[i] = a[n - 1 - i];
        }
        this.buffers[key] = out;
      }
      return key;
    },

    /* one-shot sound. opts: vol, rate, pan (-1..1), lowpass (Hz), music.
       Returns a handle { stop(fade), gain, filter, src } (Web Audio) or { stop, el } (file mode), or null. */
    play(name, opts) {
      if (!this.has(name)) return null;
      const o = Object.assign({ vol: 1, rate: 1, pan: 0, lowpass: 0, music: false }, opts || {});
      if (this.web) {
        const c = this.ctx;
        const src = c.createBufferSource(); src.buffer = this.buffers[name]; src.playbackRate.value = o.rate;
        const g = c.createGain(); g.gain.value = o.vol;
        let node = src, f = null;
        if (o.lowpass) { f = c.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = o.lowpass; node.connect(f); node = f; }
        if (o.pan && c.createStereoPanner) { const p = c.createStereoPanner(); p.pan.value = clamp(o.pan, -1, 1); node.connect(p); node = p; }
        node.connect(g); g.connect(o.music ? this.musicBus : this.sfxBus);
        src.start();
        return {
          src, gain: g, filter: f,
          stop(fade) { try { g.gain.setTargetAtTime(0, c.currentTime, (fade || 0.05) / 3); src.stop(c.currentTime + (fade || 0.05) + 0.05); } catch (e) { /* already stopped */ } },
        };
      }
      const pool = this.pools[name] || (this.pools[name] = []);
      let a = pool.find((x) => x.paused || x.ended);
      if (!a) {
        if (pool.length < 4) { a = this._el(name); pool.push(a); } else { a = pool.shift(); pool.push(a); }
      }
      try { a.currentTime = 0; } catch (e) { /* not ready */ }
      a.loop = false; a.playbackRate = o.rate; a.volume = this._htmlVol(o.vol, o.music);
      const pr = a.play(); if (pr && pr.catch) pr.catch(() => {});
      return { el: a, stop() { a.pause(); } };
    },

    /* looping sound that fades toward a target volume.
       key: a name for this loop (several loops can share one file).
       opts: fade (seconds), rate, pan, music, sound (which file; default = key),
             lowpass (Hz, or null for none; Web Audio only). */
    loop(key, target, opts) {
      const o = Object.assign({ fade: 1, rate: 1, music: true, pan: 0, sound: key, lowpass: null }, opts || {});
      let L = this.loops[key];
      if (!L) L = this.loops[key] = { key, sound: o.sound, vol: 0, target: 0, fade: o.fade, music: o.music, rate: o.rate, pan: o.pan, lp: o.lowpass, filt: false, h: null };
      if (!L.h && L.sound !== o.sound) L.sound = o.sound;
      L.target = target; L.fade = o.fade; L.music = o.music; // update() starts it once the file exists (never for empty slots)
      if (o.lowpass != null && !L.filt) { L.filt = true; if (L.h && this.web && !L.h.f) this._stopH(L); } // restarts with a filter
      if (L.rate !== o.rate || L.pan !== o.pan || L.lp !== o.lowpass) { L.rate = o.rate; L.pan = o.pan; L.lp = o.lowpass; this._tune(L); }
    },
    stopLoop(key, fade) { const L = this.loops[key]; if (L) { L.target = 0; L.fade = fade == null ? 0.5 : fade; } },
    /* stop every loop whose key starts with prefix (e.g. 'presence:') */
    stopLoops(prefix, fade) { for (const k in this.loops) if (k.indexOf(prefix) === 0) this.stopLoop(k, fade); },
    killLoops() { for (const k in this.loops) { const L = this.loops[k]; L.target = 0; L.vol = 0; this._stopH(L); } },
    stopAll() {
      this.killLoops();
      if (!this.web) for (const k in this.pools) for (const a of this.pools[k]) { try { a.pause(); } catch (e) { /* ignore */ } }
      else if (this.ctx) { // swap the sfx bus so every playing one-shot is cut
        try { this.sfxBus.disconnect(); } catch (e) { /* ignore */ }
        this.sfxBus = this.ctx.createGain(); this.sfxBus.connect(this.master);
      }
    },
    _tune(L) {
      if (!L.h) return;
      if (this.web) {
        const now = this.ctx.currentTime;
        L.h.src.playbackRate.value = L.rate;
        if (L.h.pan) L.h.pan.pan.value = clamp(L.pan, -1, 1);
        if (L.h.f) L.h.f.frequency.setTargetAtTime(L.lp || 20000, now, 0.1);
      } else L.h.el.playbackRate = L.rate;
    },
    _startH(L) {
      if (!this.has(L.sound)) return;
      if (this.web) {
        const buf = this.buffers[L.sound];
        const c = this.ctx;
        const src = c.createBufferSource(); src.buffer = buf; src.loop = true; src.playbackRate.value = L.rate;
        const g = c.createGain(); g.gain.value = 0;
        let node = src, pan = null, f = null;
        if (L.filt) { f = c.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = L.lp || 20000; node.connect(f); node = f; }
        if (c.createStereoPanner) { pan = c.createStereoPanner(); pan.pan.value = clamp(L.pan, -1, 1); node.connect(pan); node = pan; }
        node.connect(g); g.connect(L.music ? this.musicBus : this.sfxBus);
        src.start(0, Math.random() * Math.max(0, buf.duration - 0.1) * (L.sound === 'ambience' || L.sound === 'static' ? 1 : 0));
        L.h = { src, g, pan, f };
      } else {
        const el = this._el(L.sound); el.loop = true; el.volume = 0; el.playbackRate = L.rate;
        const pr = el.play(); if (pr && pr.catch) pr.catch(() => {});
        L.h = { el };
      }
    },
    _stopH(L) {
      if (!L.h) return;
      try { if (this.web) L.h.src.stop(); else L.h.el.pause(); } catch (e) { /* ignore */ }
      L.h = null;
    },
    update(dt) {
      for (const k in this.loops) {
        const L = this.loops[k];
        const step = dt / Math.max(0.02, L.fade);
        L.vol += clamp(L.target - L.vol, -step, step);
        if (L.vol > 0.001 && !L.h) this._startH(L);
        if (L.h) {
          if (this.web) L.h.g.gain.value = L.vol;
          else L.h.el.volume = this._htmlVol(L.vol, L.music);
        }
        if (L.vol <= 0.001 && L.target <= 0 && L.h) this._stopH(L);
      }
    },
    pauseAll(p) {
      if (this.web && this.ctx) { if (p) this.ctx.suspend().catch(() => {}); else this.ctx.resume().catch(() => {}); return; }
      for (const k in this.loops) { const L = this.loops[k]; if (L.h) { if (p) L.h.el.pause(); else { const pr = L.h.el.play(); if (pr && pr.catch) pr.catch(() => {}); } } }
      if (p) for (const k in this.pools) for (const a of this.pools[k]) a.pause();
    },
  };

  /* ------------------------------------------------------------------ */
  /*  CONFIG CHECK: fix capital letters quietly, warn about real typos   */
  /*  (warnings go to the console and to the ?dev art-helper panel)      */
  /* ------------------------------------------------------------------ */
  const configWarnings = [];
  function warnCfg(msg) { configWarnings.push(msg); console.warn('[config.js] ' + msg); }
  const TOP_KEYS = ['title', 'subtitle', 'hourSeconds', 'lucidityDrain', 'endlessDrain', 'nights', 'endlessRules', 'pinch',
    'office', 'cameras', 'monsters', 'sounds', 'dreamVoice', 'credits'];
  const MONSTER_KEYS = ['id', 'name', 'description', 'frames', 'fps', 'jumpscareFrames', 'jumpscareFps', 'jumpscareFocus',
    'jumpscareSound', 'levels', 'hourBoost', 'moveEvery', 'waitAtDoor', 'start', 'path', 'retreat', 'poses', 'doorPose'];
  /* an unknown key is only reported when it looks like a misspelt known one */
  function checkKeys(obj, known, where) {
    for (const k in obj) {
      if (known.indexOf(k) >= 0) continue;
      const g = didYouMean(k, known);
      if (g) warnCfg(`${where}"${k}" isn't a setting the game knows. Did you mean "${g}"?`);
    }
  }

  /* "a, , b" or a stray value in a list: keep only the real { … } blocks */
  function onlyBlocks(list, what) {
    if (!Array.isArray(list)) return list;
    const out = list.filter((x) => x && typeof x === 'object');
    if (out.length !== list.length) warnCfg(`${what}: there is an extra comma or an empty spot in the list. The game skipped it.`);
    return out;
  }

  function checkConfig() {
    checkKeys(CFG, TOP_KEYS, '');
    CFG.cameras = onlyBlocks(CFG.cameras, 'cameras');
    CFG.monsters = onlyBlocks(CFG.monsters, 'monsters');
    if (!Array.isArray(CFG.cameras) || !CFG.cameras.length) {
      warnCfg('cameras: the list is empty, so the game made one stand-in room.');
      CFG.cameras = [{ id: 'room', label: 'CAM 1', name: 'A Room', image: '', map: { x: 0.5, y: 0.5 } }];
    }
    const seen = {};
    CFG.cameras.forEach((c, i) => {
      if (!c.id) { c.id = 'cam' + (i + 1); warnCfg(`cameras: camera number ${i + 1} has no id, so it is called "${c.id}".`); }
      c.id = String(c.id);
      if (seen[c.id.toLowerCase()]) warnCfg(`cameras: two cameras are both called "${c.id}".`);
      seen[c.id.toLowerCase()] = true;
      if (!c.name) c.name = c.id;
      if (!c.map || typeof c.map.x !== 'number' || typeof c.map.y !== 'number') {
        warnCfg(`cameras: "${c.id}" needs map: { x: …, y: … } (where its button sits on the camera map).`);
        c.map = { x: 0.5, y: 0.5 };
      }
    });
    const ids = CFG.cameras.map((c) => c.id), byLower = {};
    ids.forEach((id) => { byLower[id.toLowerCase()] = id; });
    /* a room name: capital letters are fixed quietly; a small typo uses the closest room (and says so) */
    const fixRoom = (name, where, allowDoor) => {
      const s = String(name);
      if (allowDoor && /^door:(left|right)$/i.test(s)) return s.toLowerCase();
      if (byLower[s.toLowerCase()]) return byLower[s.toLowerCase()];
      const g = didYouMean(s, allowDoor ? ids.concat(['door:left', 'door:right']) : ids);
      warnCfg(`${where}: room "${s}" doesn't exist` + (g ? `. Did you mean "${g}"? (Using "${g}" for now.)` : `. The rooms are: ${ids.join(', ')}.`));
      return g;
    };

    if (!Array.isArray(CFG.monsters)) { warnCfg('monsters: this should be a list [ … ].'); CFG.monsters = []; }
    const monIds = {};
    CFG.monsters.forEach((m, i) => {
      if (!m.id) { m.id = 'monster' + (i + 1); warnCfg(`monsters: monster number ${i + 1} has no id, so it is called "${m.id}".`); }
      if (monIds[m.id]) warnCfg(`monsters: two monsters are both called "${m.id}". Give each one its own id.`);
      monIds[m.id] = true;
      if (!m.name) m.name = m.id;
      const who = m.name;
      checkKeys(m, MONSTER_KEYS, who + ': ');
      if (!Array.isArray(m.frames)) m.frames = [];
      m.start = fixRoom(m.start != null ? m.start : ids[0], who + ' start', false) || ids[0];
      const path = {};
      for (const from in (m.path || {})) {
        const f = fixRoom(from, who + ' path', false);
        if (!f) continue;
        const to = [].concat(m.path[from]).map((t) => fixRoom(t, `${who} path (from ${f})`, true)).filter(Boolean);
        if (to.length) path[f] = to;
      }
      m.path = path;
      m.retreat = [].concat(m.retreat || []).map((r) => fixRoom(r, who + ' retreat', false)).filter(Boolean);
      const poses = {};
      for (const k in (m.poses || {})) { const r = fixRoom(k, who + ' poses', false); if (r) poses[r] = m.poses[k]; }
      m.poses = poses;
      for (const k in (m.doorPose || {})) if (k !== 'left' && k !== 'right') warnCfg(`${who} doorPose: "${k}" should be "left" or "right".`);
      if (!Array.isArray(m.waitAtDoor) || m.waitAtDoor.length !== 2) {
        if (m.waitAtDoor != null) warnCfg(`${who} waitAtDoor: write it as two numbers, like [3.5, 7].`);
        m.waitAtDoor = [4, 7];
      }
      if (m.levels != null && !Array.isArray(m.levels)) { warnCfg(`${who} levels: write one number per night, like [3, 6, 9, 12, 16].`); m.levels = null; }
      if (m.jumpscareSound && CFG.sounds && !CFG.sounds[m.jumpscareSound]) warnCfg(`${who} jumpscareSound: there is no sound called "${m.jumpscareSound}" in sounds.`);
    });

    CFG.office = CFG.office || {};
    const doors = CFG.office.doors = CFG.office.doors || {};
    for (const side of ['left', 'right']) {
      const d = doors[side];
      if (!d || ['x', 'y', 'w', 'h'].some((k) => typeof d[k] !== 'number')) {
        warnCfg(`office.doors.${side} needs x, y, w and h numbers. Using the built-in spot for now.`);
        doors[side] = Object.assign({}, d || {}, { x: side === 'left' ? 0.03 : 0.82, y: 0.178, w: 0.15, h: 0.7 });
      }
    }
    if (CFG.nights != null && !Array.isArray(CFG.nights)) { warnCfg('nights: this should be a list of 5 { … } blocks.'); CFG.nights = null; }
    for (const k in (CFG.sounds || {})) if (typeof CFG.sounds[k] !== 'string') warnCfg(`sounds.${k}: write the file path in quotes, like "assets/audio/${k}.mp3".`);
  }
  checkConfig();

  const camById = {};
  CFG.cameras.forEach((c, i) => { c.index = i; camById[c.id] = c; });

  /* ------------------------------------------------------------------ */
  /*  NIGHT RULES: what changes from night to night (config "nights")   */
  /* ------------------------------------------------------------------ */
  const NIGHT_RULES = [ // used when config.js has no "nights" (same numbers as the shipped config)
    { drain: 0.09, stepChance: 1, lies: false, pinchRadius: 1, youCam: false, stare: 0, gasp: 0, doorFree: 14 },
    { drain: 0.10, stepChance: 1, lies: true, pinchRadius: 1, youCam: false, stare: 0, gasp: 0, doorFree: 12 },
    { drain: 0.11, stepChance: 0.8, lies: true, pinchRadius: 2, youCam: true, stare: 0, gasp: 0, doorFree: 11 },
    { drain: 0.12, stepChance: 0.65, lies: true, pinchRadius: 2, youCam: true, stare: 5, gasp: 32, doorFree: 10 },
    { drain: 0.13, stepChance: 0.5, lies: true, pinchRadius: 2, youCam: true, stare: 4, gasp: 28, doorFree: 10, falseDawn: 5.33 },
  ];
  const ENDLESS_RULES = { drain: 0.13, stepChance: 0.6, lies: true, pinchRadius: 2, youCam: true, stare: 4.5, gasp: 28, doorFree: 10 };
  /* rule('stare', 0): tonight's value from config.js, then the older keys, then the built-in table */
  function rule(key, dflt) {
    const own = G.endless ? CFG.endlessRules : (CFG.nights || [])[G.night - 1];
    if (own && own[key] != null) return own[key];
    if (key === 'drain') { // older config.js files (lucidityDrain / endlessDrain) keep working
      const old = G.endless ? CFG.endlessDrain : (CFG.lucidityDrain || [])[G.night - 1];
      if (typeof old === 'number') return old;
    }
    const built = G.endless ? ENDLESS_RULES : NIGHT_RULES[clamp(G.night, 1, NIGHTS) - 1];
    return built[key] != null ? built[key] : dflt;
  }

  /* ------------------------------------------------------------------ */
  /*  ART: load pictures, or paint dreamy stand-ins when they're missing */
  /* ------------------------------------------------------------------ */
  const Art = { office: null, officeMissing: true, doors: { left: {}, right: {} }, cams: {}, camMissing: {}, monsters: {}, noise: [], vignette: null, scan: null, dot: null };

  function loadImage(url) {
    return new Promise((res) => {
      if (!url) return res(null);
      const im = new Image();
      im.onload = () => res(im.naturalWidth ? im : null);
      im.onerror = () => res(null);
      im.src = url;
    });
  }

  async function loadArt(tick) {
    const jobs = [];
    const job = (p) => { jobs.push(p.then((v) => { tick(); return v; })); return p; };

    const officeP = job(loadImage(CFG.office.image));
    const doorP = {};
    for (const side of ['left', 'right']) {
      const d = CFG.office.doors[side];
      doorP[side] = { dark: job(loadImage(d.darkImage)), lit: job(loadImage(d.litImage)), closed: job(loadImage(d.closedImage)) };
    }
    const camP = {};
    for (const c of CFG.cameras) camP[c.id] = job(loadImage(c.image));
    const monP = {};
    for (const m of CFG.monsters) {
      monP[m.id] = {
        frames: Promise.all((m.frames || []).map((u) => job(loadImage(u)))),
        jump: Promise.all((m.jumpscareFrames || []).map((u) => job(loadImage(u)))),
      };
    }
    Art.total = jobs.length;
    await Promise.all(jobs);

    // monsters first (the office stand-in pins a drawing of the first monster on the wall)
    for (const m of CFG.monsters) {
      let frames = (await monP[m.id].frames).filter(Boolean);
      const missing = frames.length === 0;
      if (missing) frames = placeholderMonster(m);
      let jump = (await monP[m.id].jump).filter(Boolean);
      if (!jump.length) jump = frames;
      const soft = frames.map((f) => softFrame(f, 820));
      Art.monsters[m.id] = { frames, jump, soft, sil: soft.map((f) => silhouette(f, '#05030a')), missing };
    }

    const office = await officeP;
    Art.officeMissing = !office;
    Art.office = office || paintOffice();
    for (const side of ['left', 'right']) {
      const d = CFG.office.doors[side];
      const rw = d.w * officeWidthFor(Art.office), rh = d.h * H;
      Art.doors[side] = {
        dark: (await doorP[side].dark) || paintDoorway(rw, rh, false, side),
        lit: (await doorP[side].lit) || paintDoorway(rw, rh, true, side),
        closed: (await doorP[side].closed) || paintShutter(rw, rh, side),
      };
    }
    for (const c of CFG.cameras) {
      const im = await camP[c.id];
      Art.camMissing[c.id] = !im;
      Art.cams[c.id] = im || paintRoom(c);
    }
    paintFx();
  }

  function officeWidthFor(img) { return img.width * (H / img.height); }

  /* ----- baked picture effects (made once, so nothing needs ctx.filter per frame) ----- */
  function silhouette(img, color) {
    const c = makeCanvas(img.width, img.height), x = c.getContext('2d');
    x.drawImage(img, 0, 0);
    x.globalCompositeOperation = 'source-in'; x.fillStyle = color; x.fillRect(0, 0, c.width, c.height);
    return c;
  }
  const tintCache = new WeakMap();
  /* the picture with a colour laid over it (keeps its shape); cached per colour */
  function tinted(img, color) {
    let byColor = tintCache.get(img);
    if (!byColor) tintCache.set(img, byColor = {});
    if (!byColor[color]) {
      const c = makeCanvas(img.width, img.height), x = c.getContext('2d');
      x.drawImage(img, 0, 0);
      x.globalCompositeOperation = 'source-atop'; x.fillStyle = color; x.fillRect(0, 0, c.width, c.height);
      byColor[color] = c;
    }
    return byColor[color];
  }
  const ghostCache = new WeakMap();
  /* the "dream lie" look: colour drained out, then a violet wash */
  function ghostOf(img) {
    let c = ghostCache.get(img);
    if (c) return c;
    c = makeCanvas(img.width, img.height);
    const x = c.getContext('2d');
    x.drawImage(img, 0, 0);
    x.globalCompositeOperation = 'saturation';
    if (x.globalCompositeOperation === 'saturation') { // older browsers ignore it; they get the wash only
      x.fillStyle = '#888'; x.fillRect(0, 0, c.width, c.height);
      x.globalCompositeOperation = 'destination-in'; x.drawImage(img, 0, 0);
    }
    x.globalCompositeOperation = 'source-atop'; x.fillStyle = 'rgba(157,132,255,.35)'; x.fillRect(0, 0, c.width, c.height);
    ghostCache.set(img, c);
    return c;
  }

  /* soft version of a frame: smaller and fading into fog at the feet */
  function softFrame(img, maxH) {
    const s = Math.min(1, maxH / img.height);
    const c = makeCanvas(img.width * s, img.height * s), x = c.getContext('2d');
    x.drawImage(img, 0, 0, c.width, c.height);
    x.globalCompositeOperation = 'destination-in';
    const g = x.createLinearGradient(0, 0, 0, c.height);
    g.addColorStop(0, 'rgba(0,0,0,1)'); g.addColorStop(0.72, 'rgba(0,0,0,1)'); g.addColorStop(1, 'rgba(0,0,0,0)');
    x.fillStyle = g; x.fillRect(0, 0, c.width, c.height);
    return c;
  }

  function placeholderMonster(m) {
    const out = [];
    for (let i = 0; i < 4; i++) {
      const c = makeCanvas(600, 900), x = c.getContext('2d');
      const sway = Math.sin(i / 4 * Math.PI * 2) * 18;
      x.fillStyle = '#120a10';
      x.beginPath();
      x.ellipse(300 + sway, 190, 95, 120, sway / 200, 0, Math.PI * 2);
      x.moveTo(180 + sway, 300); x.quadraticCurveTo(300, 260, 420 + sway, 300);
      x.lineTo(470, 900); x.lineTo(130, 900); x.closePath(); x.fill();
      x.fillStyle = '#ffe9e0'; x.shadowColor = '#ff2040'; x.shadowBlur = 25;
      x.beginPath(); x.arc(262 + sway, 180, 11, 0, 7); x.arc(338 + sway, 180, 11, 0, 7); x.fill();
      if (DEV) { // tell the artist (never the player) why this monster looks like a shadow
        x.shadowBlur = 0; x.fillStyle = '#e9dfcf'; x.font = '28px VT323, monospace'; x.textAlign = 'center';
        x.fillText('(no frames for ' + m.name + ')', 300, 620);
      }
      out.push(c);
    }
    return out;
  }

  /* ----- painting helpers for stand-in art ----- */
  function noiseFill(x, w, h, alpha, seed, scale) {
    const r = mulberry32(seed);
    for (let i = 0; i < (w * h) / (scale * scale * 6); i++) {
      x.fillStyle = r() < 0.5 ? `rgba(255,255,255,${alpha * r()})` : `rgba(0,0,0,${alpha * 2 * r()})`;
      x.fillRect(r() * w, r() * h, scale * (0.5 + r()), scale * (0.5 + r()));
    }
  }
  function moon(x, cx, cy, r, color, alpha) {
    x.save(); x.globalAlpha = alpha; x.fillStyle = color;
    x.beginPath(); x.arc(cx, cy, r, 0, Math.PI * 2); x.fill();
    x.globalCompositeOperation = 'destination-out';
    x.beginPath(); x.arc(cx + r * 0.45, cy - r * 0.2, r * 0.9, 0, Math.PI * 2); x.fill();
    x.restore();
  }
  function glow(x, cx, cy, r, color, a) {
    const g = x.createRadialGradient(cx, cy, 0, cx, cy, r);
    g.addColorStop(0, color.replace('A', a)); g.addColorStop(1, color.replace('A', 0));
    x.fillStyle = g; x.fillRect(cx - r, cy - r, r * 2, r * 2);
  }
  function paintOffice() {
    const OW = 2400, c = makeCanvas(OW, H), x = c.getContext('2d');
    const r = mulberry32(7);
    // back wall
    let g = x.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, '#120c1c'); g.addColorStop(0.7, '#1d1429'); g.addColorStop(1, '#0c0812');
    x.fillStyle = g; x.fillRect(0, 0, OW, H);
    // wallpaper: rows of tiny moons and eyes
    for (let row = 0; row < 9; row++) {
      for (let col = 0; col < 40; col++) {
        const px = col * 62 + (row % 2) * 31 + 20, py = 90 + row * 66;
        if (py > 690) continue;
        if ((row + col) % 3 === 0) {
          x.save(); x.globalAlpha = 0.07; x.strokeStyle = '#d8c8ff'; x.lineWidth = 2;
          x.beginPath(); x.ellipse(px, py, 10, 5, 0, 0, Math.PI * 2); x.stroke();
          x.fillStyle = '#d8c8ff'; x.beginPath(); x.arc(px, py, 2.2, 0, 7); x.fill(); x.restore();
        } else moon(x, px, py, 6, '#d8c8ff', 0.06);
      }
    }
    // ceiling + skirting
    x.fillStyle = '#07050b'; x.fillRect(0, 0, OW, 58);
    x.fillStyle = 'rgba(255,255,255,.04)'; x.fillRect(0, 58, OW, 3);
    x.fillStyle = '#0b0710'; x.fillRect(0, 690, OW, 22);
    // floor: planks converging to the middle
    g = x.createLinearGradient(0, 712, 0, H);
    g.addColorStop(0, '#1a1018'); g.addColorStop(1, '#0a0609');
    x.fillStyle = g; x.fillRect(0, 712, OW, H - 712);
    x.strokeStyle = 'rgba(0,0,0,.45)'; x.lineWidth = 2;
    for (let i = -30; i <= 30; i++) { x.beginPath(); x.moveTo(OW / 2 + i * 40, 712); x.lineTo(OW / 2 + i * 150, H); x.stroke(); }
    for (let y = 730; y < H; y += (y - 690) * 0.35) { x.strokeStyle = 'rgba(0,0,0,.3)'; x.beginPath(); x.moveTo(0, y); x.lineTo(OW, y); x.stroke(); }
    noiseFill(x, OW, H, 0.05, 3, 3);

    // window with a too-big moon
    const wx = 560, wy = 160, ww = 250, wh = 270;
    g = x.createLinearGradient(0, wy, 0, wy + wh);
    g.addColorStop(0, '#0b1636'); g.addColorStop(1, '#1d1240');
    x.fillStyle = g; x.fillRect(wx, wy, ww, wh);
    for (let i = 0; i < 40; i++) { x.fillStyle = `rgba(255,255,255,${0.3 + r() * 0.6})`; x.fillRect(wx + r() * ww, wy + r() * wh, 2, 2); }
    glow(x, wx + 150, wy + 120, 170, 'rgba(230,220,255,A)', 0.35);
    x.fillStyle = '#efe6ff'; x.beginPath(); x.arc(wx + 150, wy + 120, 62, 0, 7); x.fill();
    x.fillStyle = 'rgba(160,140,200,.35)'; x.beginPath(); x.arc(wx + 130, wy + 105, 12, 0, 7); x.arc(wx + 170, wy + 140, 8, 0, 7); x.fill();
    x.strokeStyle = '#0a0610'; x.lineWidth = 14; x.strokeRect(wx, wy, ww, wh);
    x.lineWidth = 8; x.beginPath(); x.moveTo(wx + ww / 2, wy); x.lineTo(wx + ww / 2, wy + wh); x.moveTo(wx, wy + wh / 2); x.lineTo(wx + ww, wy + wh / 2); x.stroke();
    // curtains
    x.fillStyle = '#3a0c16';
    for (const s of [-1, 1]) {
      x.beginPath();
      const cx0 = s < 0 ? wx - 30 : wx + ww + 30;
      x.moveTo(cx0, wy - 30); x.lineTo(cx0 - s * 70, wy - 30);
      x.quadraticCurveTo(cx0 - s * 40, wy + wh * 0.6, cx0 - s * 10, wy + wh + 60); x.lineTo(cx0 + s * 30, wy + wh + 60); x.closePath(); x.fill();
    }
    // moonlight on the floor
    x.save(); x.globalAlpha = 0.06; x.fillStyle = '#d9d0ff';
    x.beginPath(); x.moveTo(wx, wy + wh); x.lineTo(wx + ww, wy + wh); x.lineTo(wx + ww + 260, H); x.lineTo(wx + 80, H); x.closePath(); x.fill(); x.restore();

    // "WAKE UP" scratched into the wall
    x.save(); x.font = '54px Eater, serif'; x.fillStyle = 'rgba(160, 14, 34, .55)'; x.translate(1610, 600); x.rotate(-0.05);
    x.fillText('WAKE UP', 0, 0); x.restore();

    // drawing of the monster pinned to the wall
    const first = CFG.monsters[0] && Art.monsters[CFG.monsters[0].id];
    const px = 1700, py = 190, pw = 190, ph = 230;
    x.save(); x.translate(px + pw / 2, py + ph / 2); x.rotate(0.05);
    x.fillStyle = '#d9cfb8'; x.fillRect(-pw / 2, -ph / 2, pw, ph);
    if (first && first.frames[0]) {
      x.globalAlpha = 0.85; x.filter = 'sepia(0.6) contrast(1.2)';
      const f = first.frames[0], s = Math.min((pw - 20) / f.width, (ph - 40) / f.height);
      x.drawImage(f, -f.width * s / 2, -ph / 2 + 10, f.width * s, f.height * s);
      x.filter = 'none'; x.globalAlpha = 1;
    }
    x.fillStyle = '#2a1a10'; x.font = '20px "Special Elite", monospace'; x.textAlign = 'center';
    x.fillText('he walks at night', 0, ph / 2 - 12);
    x.fillStyle = '#b01828'; x.beginPath(); x.arc(0, -ph / 2 + 4, 6, 0, 7); x.fill();
    x.restore();

    // desk
    const dx = 860, dw = 700, dy = 620;
    x.fillStyle = '#140c0a'; x.fillRect(dx + 30, dy + 40, 30, H - dy); x.fillRect(dx + dw - 60, dy + 40, 30, H - dy);
    x.fillStyle = '#1f130f';
    x.beginPath(); x.moveTo(dx - 40, dy + 50); x.lineTo(dx + 30, dy); x.lineTo(dx + dw - 30, dy); x.lineTo(dx + dw + 40, dy + 50); x.closePath(); x.fill();
    x.fillStyle = '#170e0b'; x.fillRect(dx - 40, dy + 50, dw + 80, 34);
    x.fillStyle = '#100907'; x.fillRect(dx + 40, dy + 84, dw - 80, 140);
    x.strokeStyle = 'rgba(255,200,150,.06)'; x.strokeRect(dx + 60, dy + 100, dw / 2 - 80, 50); x.strokeRect(dx + dw / 2 + 20, dy + 100, dw / 2 - 80, 50);
    // lamp glow + lamp
    glow(x, dx + 90, dy - 40, 360, 'rgba(255,190,110,A)', 0.22);
    x.fillStyle = '#2a1b10'; x.fillRect(dx + 84, dy - 120, 10, 120);
    x.fillStyle = '#4a2c14'; x.beginPath(); x.moveTo(dx + 40, dy - 120); x.lineTo(dx + 140, dy - 120); x.lineTo(dx + 115, dy - 175); x.lineTo(dx + 65, dy - 175); x.closePath(); x.fill();
    glow(x, dx + 90, dy - 110, 60, 'rgba(255,220,160,A)', 0.6);
    // monitor
    const mx = 1060, my = 438, mw = 280, mh = 190;
    x.fillStyle = '#0f0c12'; x.fillRect(mx - 14, my - 14, mw + 28, mh + 28);
    x.fillStyle = '#18141c'; x.fillRect(mx + mw / 2 - 40, my + mh + 14, 80, 20);
    g = x.createRadialGradient(mx + mw / 2, my + mh / 2, 10, mx + mw / 2, my + mh / 2, mw * 0.7);
    g.addColorStop(0, '#2c4a46'); g.addColorStop(1, '#0a1614');
    x.fillStyle = g; x.fillRect(mx, my, mw, mh);
    x.fillStyle = 'rgba(180,255,220,.55)'; x.font = '30px VT323, monospace'; x.textAlign = 'center';
    x.fillText('z z z', mx + mw / 2, my + mh / 2 + 8);
    glow(x, mx + mw / 2, my + mh / 2, 260, 'rgba(120,255,200,A)', 0.07);
    // alarm clock prop
    x.fillStyle = '#3b0d14'; x.beginPath(); x.arc(1450, 586, 34, 0, 7); x.fill();
    x.fillStyle = '#e6dccc'; x.beginPath(); x.arc(1450, 586, 26, 0, 7); x.fill();
    x.strokeStyle = '#1a0b0d'; x.lineWidth = 3; x.beginPath(); x.moveTo(1450, 586); x.lineTo(1450, 566); x.moveTo(1450, 586); x.lineTo(1464, 592); x.stroke();
    x.fillStyle = '#3b0d14'; x.beginPath(); x.arc(1424, 552, 12, 0, 7); x.arc(1476, 552, 12, 0, 7); x.fill();
    // papers
    x.save(); x.fillStyle = 'rgba(220,210,190,.6)';
    for (let i = 0; i < 4; i++) { x.save(); x.translate(1170 + i * 70, dy + 22); x.rotate((r() - 0.5) * 0.5); x.fillRect(-28, -10, 56, 20); x.restore(); }
    x.restore();

    // door frames
    for (const side of ['left', 'right']) {
      const d = CFG.office.doors[side];
      const fx = d.x * OW, fy = d.y * H, fw = d.w * OW, fh = d.h * H;
      x.fillStyle = '#2a1712'; x.fillRect(fx - 26, fy - 26, fw + 52, fh + 26);
      x.fillStyle = '#1a0e0b'; x.fillRect(fx - 12, fy - 12, fw + 24, fh + 12);
      x.fillStyle = '#000'; x.fillRect(fx, fy, fw, fh);
      // little sigil above the door
      x.save(); x.strokeStyle = 'rgba(157,132,255,.4)'; x.lineWidth = 2;
      x.beginPath(); x.arc(fx + fw / 2, fy - 60, 16, 0, 7); x.moveTo(fx + fw / 2 - 26, fy - 60); x.lineTo(fx + fw / 2 + 26, fy - 60); x.stroke(); x.restore();
    }
    // edge darkness
    g = x.createLinearGradient(0, 0, OW, 0);
    g.addColorStop(0, 'rgba(0,0,0,.55)'); g.addColorStop(0.2, 'rgba(0,0,0,0)'); g.addColorStop(0.8, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,.55)');
    x.fillStyle = g; x.fillRect(0, 0, OW, H);
    return c;
  }

  function paintDoorway(w, h, lit, side) {
    const c = makeCanvas(w, h), x = c.getContext('2d');
    const vx = w * (side === 'left' ? 0.42 : 0.58), vy = h * 0.42;
    if (!lit) {
      const g = x.createLinearGradient(0, 0, 0, h);
      g.addColorStop(0, '#020103'); g.addColorStop(1, '#0b0710');
      x.fillStyle = g; x.fillRect(0, 0, w, h);
      x.fillStyle = 'rgba(157,132,255,.035)';
      x.beginPath(); x.moveTo(0, h); x.lineTo(vx - 18, vy + 40); x.lineTo(vx + 18, vy + 40); x.lineTo(w, h); x.fill();
      return c;
    }
    // lit hallway in sickly yellow light, fading to black at the back
    x.fillStyle = '#2b2414'; x.fillRect(0, 0, w, h);
    const bw = w * 0.22, bh = h * 0.26;
    const bx = vx - bw / 2, by = vy - bh / 2;
    const quad = (pts, fill) => { x.beginPath(); x.moveTo(pts[0], pts[1]); for (let i = 2; i < pts.length; i += 2) x.lineTo(pts[i], pts[i + 1]); x.closePath(); x.fillStyle = fill; x.fill(); };
    let g = x.createLinearGradient(0, by + bh, 0, h);
    g.addColorStop(0, '#2a2312'); g.addColorStop(1, '#8a7a4a');
    quad([0, h, w, h, bx + bw, by + bh, bx, by + bh], g);                      // floor
    g = x.createLinearGradient(0, 0, 0, by); g.addColorStop(0, '#5a5030'); g.addColorStop(1, '#1d180c');
    quad([0, 0, w, 0, bx + bw, by, bx, by], g);                                // ceiling
    g = x.createLinearGradient(0, 0, bx, 0); g.addColorStop(0, '#6f6340'); g.addColorStop(1, '#231d0e');
    quad([0, 0, bx, by, bx, by + bh, 0, h], g);                                // left wall
    g = x.createLinearGradient(w, 0, bx + bw, 0); g.addColorStop(0, '#6f6340'); g.addColorStop(1, '#231d0e');
    quad([w, 0, bx + bw, by, bx + bw, by + bh, w, h], g);                      // right wall
    x.fillStyle = '#050403'; x.fillRect(bx, by, bw, bh);                       // the dark end
    // checker floor tiles for dream-weirdness
    x.save(); x.globalAlpha = 0.18; x.fillStyle = '#000';
    for (let i = 0; i < 7; i++) {
      const t0 = i / 7, t1 = (i + 1) / 7;
      const y0 = lerp(by + bh, h, t0 * t0), y1 = lerp(by + bh, h, t1 * t1);
      for (let j = 0; j < 6; j++) {
        if ((i + j) % 2) continue;
        const l0 = lerp(bx, 0, t0 * t0), r0 = lerp(bx + bw, w, t0 * t0), l1 = lerp(bx, 0, t1 * t1), r1 = lerp(bx + bw, w, t1 * t1);
        const a0 = lerp(l0, r0, j / 6), b0 = lerp(l0, r0, (j + 1) / 6), a1 = lerp(l1, r1, j / 6), b1 = lerp(l1, r1, (j + 1) / 6);
        x.beginPath(); x.moveTo(a0, y0); x.lineTo(b0, y0); x.lineTo(b1, y1); x.lineTo(a1, y1); x.closePath(); x.fill();
      }
    }
    x.restore();
    // light cone from above
    g = x.createRadialGradient(w / 2, 0, 10, w / 2, h * 0.3, h * 0.9);
    g.addColorStop(0, 'rgba(255,240,180,.45)'); g.addColorStop(1, 'rgba(255,240,180,0)');
    x.fillStyle = g; x.fillRect(0, 0, w, h);
    noiseFill(x, w, h, 0.08, side === 'left' ? 11 : 12, 2);
    return c;
  }

  function paintShutter(w, h, side) {
    const c = makeCanvas(w, h), x = c.getContext('2d');
    let g = x.createLinearGradient(0, 0, w, 0);
    g.addColorStop(0, '#16121c'); g.addColorStop(0.5, '#2a2433'); g.addColorStop(1, '#141019');
    x.fillStyle = g; x.fillRect(0, 0, w, h);
    for (let y = 0; y < h; y += 34) {
      x.fillStyle = 'rgba(0,0,0,.45)'; x.fillRect(0, y, w, 4);
      x.fillStyle = 'rgba(255,255,255,.05)'; x.fillRect(0, y + 4, w, 2);
    }
    x.fillStyle = 'rgba(0,0,0,.6)';
    for (let y = 18; y < h; y += 68) for (const px of [10, w - 14]) { x.beginPath(); x.arc(px, y, 3, 0, 7); x.fill(); }
    // glowing sigil
    x.save(); x.translate(w / 2, h * 0.45);
    x.shadowColor = '#9d84ff'; x.shadowBlur = 18; x.strokeStyle = 'rgba(190,170,255,.65)'; x.lineWidth = 3;
    x.beginPath(); x.arc(0, 0, w * 0.18, 0, Math.PI * 2); x.stroke();
    x.beginPath(); x.ellipse(0, 0, w * 0.12, w * 0.06, 0, 0, Math.PI * 2); x.stroke();
    x.fillStyle = 'rgba(190,170,255,.8)'; x.beginPath(); x.arc(0, 0, w * 0.03, 0, 7); x.fill();
    x.restore();
    g = x.createLinearGradient(0, h - 30, 0, h); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,.6)');
    x.fillStyle = g; x.fillRect(0, h - 30, w, 30);
    noiseFill(x, w, h, 0.06, side === 'left' ? 21 : 22, 2);
    return c;
  }

  /* camera stand-ins: one dreamlike room per theme */
  function paintRoom(cam) {
    const c = makeCanvas(W, H), x = c.getContext('2d');
    const seed = 101 + cam.index * 17, r = mulberry32(seed);
    const themes = [
      { wall: ['#2a1f3a', '#140e1f'], floor: ['#2b1a2a', '#0c070c'], accent: '#d8b4ff' },
      { wall: ['#2a1414', '#120808'], floor: ['#3a1010', '#0e0505'], accent: '#ffb0a0' },
      { wall: ['#10283a', '#06121c'], floor: ['#0d3344', '#03121a'], accent: '#9fe8ff' },
      { wall: ['#1f1a2c', '#0b0912'], floor: ['#221d30', '#08060c'], accent: '#c8c0ff' },
      { wall: ['#2a2516', '#100e08'], floor: ['#2c2614', '#0c0a05'], accent: '#ffe6a0' },
      { wall: ['#16261c', '#08100b'], floor: ['#1a2c20', '#060c08'], accent: '#b0ffd0' },
    ];
    const th = themes[cam.index % themes.length];
    const kind = ['nursery', 'hall', 'parlor', 'stairs', 'corridor', 'corridor'][cam.index] || 'corridor';
    const deep = kind === 'hall' ? 0.13 : kind === 'corridor' ? 0.24 : 0.5;
    const bw = W * deep, bh = H * deep * 1.15;
    const bx = (W - bw) / 2 + (kind === 'corridor' ? (cam.index % 2 ? 80 : -80) : 0), by = H * 0.4 - bh / 2;
    const quad = (p, f) => { x.beginPath(); x.moveTo(p[0], p[1]); for (let i = 2; i < p.length; i += 2) x.lineTo(p[i], p[i + 1]); x.closePath(); x.fillStyle = f; x.fill(); };
    let g = x.createLinearGradient(0, 0, 0, H); g.addColorStop(0, th.wall[0]); g.addColorStop(1, th.wall[1]);
    x.fillStyle = g; x.fillRect(0, 0, W, H);
    g = x.createLinearGradient(0, by + bh, 0, H); g.addColorStop(0, th.floor[1]); g.addColorStop(1, th.floor[0]);
    quad([0, H, W, H, bx + bw, by + bh, bx, by + bh], g);
    g = x.createLinearGradient(0, 0, 0, by); g.addColorStop(0, '#050307'); g.addColorStop(1, th.wall[1]);
    quad([0, 0, W, 0, bx + bw, by, bx, by], g);
    g = x.createLinearGradient(0, 0, bx, 0); g.addColorStop(0, th.wall[0]); g.addColorStop(1, th.wall[1]);
    quad([0, 0, bx, by, bx, by + bh, 0, H], g);
    g = x.createLinearGradient(W, 0, bx + bw, 0); g.addColorStop(0, th.wall[0]); g.addColorStop(1, th.wall[1]);
    quad([W, 0, bx + bw, by, bx + bw, by + bh, W, H], g);
    x.fillStyle = th.wall[1]; x.fillRect(bx, by, bw, bh);
    // floor pattern (checker for dream rooms, water lines for the parlor)
    if (kind === 'parlor') {
      for (let i = 0; i < 70; i++) {
        const t = r(), y = lerp(by + bh, H, t * t);
        x.strokeStyle = `rgba(160,230,255,${0.05 + 0.12 * t})`; x.lineWidth = 1 + t * 3;
        const half = lerp(bw / 2, W / 2, t * t) * (0.2 + r() * 0.5), cx = lerp(bx + bw / 2, W / 2, t) + (r() - 0.5) * 400;
        x.beginPath(); x.moveTo(cx - half, y); x.lineTo(cx + half, y); x.stroke();
      }
    } else {
      x.save(); x.globalAlpha = kind === 'hall' ? 0.0 : 0.22; x.fillStyle = '#000';
      for (let i = 0; i < 9; i++) {
        const t0 = i / 9, t1 = (i + 1) / 9, e0 = t0 * t0, e1 = t1 * t1;
        const y0 = lerp(by + bh, H, e0), y1 = lerp(by + bh, H, e1);
        for (let j = 0; j < 10; j++) {
          if ((i + j) % 2) continue;
          const l0 = lerp(bx, 0, e0), r0 = lerp(bx + bw, W, e0), l1 = lerp(bx, 0, e1), r1 = lerp(bx + bw, W, e1);
          x.beginPath(); x.moveTo(lerp(l0, r0, j / 10), y0); x.lineTo(lerp(l0, r0, (j + 1) / 10), y0); x.lineTo(lerp(l1, r1, (j + 1) / 10), y1); x.lineTo(lerp(l1, r1, j / 10), y1); x.closePath(); x.fill();
        }
      }
      x.restore();
    }
    if (kind === 'hall') { // long red runner + many doors receding
      quad([W / 2 - 250, H, W / 2 + 250, H, bx + bw * 0.62, by + bh, bx + bw * 0.38, by + bh], '#4a0d16');
      for (let i = 0; i < 9; i++) {
        const t = Math.pow(i / 9, 1.6);
        for (const s of [0, 1]) {
          const wx = s ? lerp(W, bx + bw, 1 - t) : lerp(0, bx, 1 - t);
          const dh = lerp(bh, H * 0.75, t), dwid = lerp(8, 70, t);
          const yb = lerp(by + bh, H * 0.95, t);
          x.fillStyle = 'rgba(0,0,0,.55)'; x.fillRect(s ? wx - dwid - 10 : wx + 10, yb - dh, dwid, dh);
        }
      }
      for (let i = 0; i < 6; i++) { const t = 1 - i / 6; glow(x, W / 2, lerp(by, 40, t * t), lerp(30, 160, t), 'rgba(255,220,180,A)', 0.18); }
    }
    if (kind === 'nursery') {
      // crib
      x.strokeStyle = 'rgba(230,215,255,.25)'; x.lineWidth = 6;
      x.strokeRect(1000, 520, 360, 200);
      for (let i = 1; i < 12; i++) { x.beginPath(); x.moveTo(1000 + i * 30, 520); x.lineTo(1000 + i * 30, 720); x.stroke(); }
      // hanging mobile
      x.lineWidth = 2; x.beginPath(); x.moveTo(1180, 0); x.lineTo(1180, 300); x.moveTo(1080, 300); x.lineTo(1280, 300); x.stroke();
      for (const [mx, my] of [[1080, 360], [1180, 390], [1280, 350]]) { x.beginPath(); x.moveTo(mx, 300); x.lineTo(mx, my - 20); x.stroke(); moon(x, mx, my, 20, th.accent, 0.5); }
      // window light beam
      x.save(); x.globalAlpha = 0.08; x.fillStyle = th.accent;
      x.beginPath(); x.moveTo(250, 150); x.lineTo(450, 150); x.lineTo(800, H); x.lineTo(300, H); x.fill(); x.restore();
      x.fillStyle = 'rgba(0,0,0,.6)'; x.fillRect(240, 130, 220, 260);
      glow(x, 350, 260, 140, 'rgba(200,190,255,A)', 0.25);
    }
    if (kind === 'parlor') {
      // half-sunk armchairs + chandelier
      for (const [ax, s] of [[300, 1], [1180, 1.2]]) {
        x.fillStyle = '#1e3d4c'; x.fillRect(ax, 600, 170 * s, 90 * s); x.fillRect(ax, 470, 40 * s, 200 * s); x.fillRect(ax + 130 * s, 470, 40 * s, 200 * s); x.fillRect(ax + 20, 440, 130 * s, 120 * s);
        x.fillStyle = 'rgba(8,40,60,.7)'; x.fillRect(ax - 20, 640, 220 * s, 140);
      }
      x.strokeStyle = 'rgba(200,240,255,.4)'; x.lineWidth = 3; x.beginPath(); x.moveTo(W / 2, 0); x.lineTo(W / 2, 120); x.stroke();
      for (let i = 0; i < 7; i++) glow(x, W / 2 - 150 + i * 50, 140 + (i % 2) * 20, 30, 'rgba(200,250,255,A)', 0.5);
      // floating frames
      x.strokeStyle = 'rgba(255,240,200,.25)'; x.lineWidth = 5;
      x.save(); x.translate(950, 250); x.rotate(0.2); x.strokeRect(-60, -80, 120, 160); x.restore();
      x.save(); x.translate(560, 300); x.rotate(-0.3); x.strokeRect(-45, -55, 90, 110); x.restore();
    }
    if (kind === 'stairs') {
      // staircase climbing into a void
      for (let i = 0; i < 14; i++) {
        const t = i / 14;
        const sw = lerp(700, 120, t), sx = W / 2 - sw / 2, sy = lerp(H, by + bh * 0.2, t), sh = lerp(70, 10, t);
        x.fillStyle = `rgba(${40 - i * 2},${34 - i * 2},${60 - i * 3},1)`; x.fillRect(sx, sy - sh, sw, sh);
        x.fillStyle = 'rgba(255,255,255,.05)'; x.fillRect(sx, sy - sh, sw, 3);
      }
      x.fillStyle = '#000'; x.fillRect(W / 2 - 70, by - 30, 140, bh * 0.4);
      // an upside-down door on the ceiling
      x.fillStyle = 'rgba(0,0,0,.6)'; x.fillRect(W / 2 + 260, 20, 120, 210);
      x.fillStyle = 'rgba(255,220,150,.4)'; x.beginPath(); x.arc(W / 2 + 280, 120, 6, 0, 7); x.fill();
    }
    if (kind === 'corridor') {
      // a door at the end, slightly open, plus a buzzing bulb
      x.fillStyle = '#0a0604'; x.fillRect(bx + bw * 0.3, by + bh * 0.15, bw * 0.4, bh * 0.85);
      x.fillStyle = 'rgba(255,220,160,.25)'; x.fillRect(bx + bw * 0.3 + bw * 0.36, by + bh * 0.15, 4, bh * 0.85);
      glow(x, W / 2, 70, 300, 'rgba(255,230,170,A)', 0.2);
      x.fillStyle = 'rgba(255,240,200,.8)'; x.beginPath(); x.arc(W / 2, 70, 10, 0, 7); x.fill();
      for (let i = 0; i < 3; i++) { // old posters on the side wall
        const left = cam.index % 2 === 0;
        x.save(); x.fillStyle = 'rgba(220,200,170,.12)';
        x.translate(left ? 140 + i * 120 : W - 260 - i * 120, 260 + i * 30); x.rotate(left ? 0.08 : -0.08);
        x.fillRect(0, 0, 90 - i * 15, 130 - i * 20); x.restore();
      }
    }
    // dust + fog
    for (let i = 0; i < 120; i++) { x.fillStyle = `rgba(255,255,255,${r() * 0.12})`; x.beginPath(); x.arc(r() * W, r() * H, r() * 2.2, 0, 7); x.fill(); }
    g = x.createLinearGradient(0, H * 0.55, 0, H); g.addColorStop(0, 'rgba(180,170,220,0)'); g.addColorStop(1, 'rgba(180,170,220,.12)');
    x.fillStyle = g; x.fillRect(0, 0, W, H);
    noiseFill(x, W, H, 0.06, seed, 3);
    x.font = '46px "Fell SC", serif'; x.fillStyle = 'rgba(233,223,207,.07)'; x.textAlign = 'center';
    x.fillText(cam.name, W / 2, H * 0.18);
    return c;
  }

  function paintFx() {
    for (let i = 0; i < 5; i++) {
      const c = makeCanvas(320, 180), x = c.getContext('2d');
      const id = x.createImageData(320, 180), d = id.data;
      for (let p = 0; p < d.length; p += 4) {
        const v = Math.random() * 255;
        d[p] = v * 0.9; d[p + 1] = v; d[p + 2] = v * 0.95; d[p + 3] = 255;
      }
      x.putImageData(id, 0, 0);
      Art.noise.push(c);
    }
    let c = makeCanvas(W, H), x = c.getContext('2d');
    const g = x.createRadialGradient(W / 2, H / 2, H * 0.32, W / 2, H / 2, H * 0.98);
    g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,.85)');
    x.fillStyle = g; x.fillRect(0, 0, W, H);
    Art.vignette = c;
    c = makeCanvas(4, 4); x = c.getContext('2d');
    x.fillStyle = 'rgba(0,0,0,.35)'; x.fillRect(0, 0, 4, 2);
    Art.scan = c;
    c = makeCanvas(32, 32); x = c.getContext('2d');
    const gg = x.createRadialGradient(16, 16, 0, 16, 16, 16);
    gg.addColorStop(0, 'rgba(255,255,255,1)'); gg.addColorStop(1, 'rgba(255,255,255,0)');
    x.fillStyle = gg; x.fillRect(0, 0, 32, 32);
    Art.dot = c;
  }

  /* ------------------------------------------------------------------ */
  /*  GAME STATE                                                        */
  /* ------------------------------------------------------------------ */
  const freshDoor = () => ({ closed: false, p: 0, light: false });
  const freshCams = () => ({ up: false, t: 0, cur: CFG.cameras[0].id, staticAmt: 0, lost: 0, forceDown: 0 });
  const freshFlicker = () => ({ on: false, t: 0, a: 0 });
  const G = {
    state: 'boot', paused: false, t: 0,
    night: 1, endless: false, nightT: 0, hour: 0, timeScale: 1,
    luc: 100, usage: 1, powerOut: false, powerT: 0, killAt: 0,
    scroll: 0, officeW: W, panV: 0, glide: null,
    doors: { left: freshDoor(), right: freshDoor() },
    cams: freshCams(),
    monsters: [], inside: null, insideT: 0,
    pinchCd: 0, danger: 0, flash: 0, flashColor: '255,255,255',
    trauma: 0, kick: { x: 0, y: 0 },   // camera shake (see hit)
    later: [],                          // pause-safe timers (see after)
    parts: [],                          // particles (see spawnParts)
    cueLog: [],                         // the last 40 threat sounds (see cue)
    stats: {},
    stutter: { left: freshFlicker(), right: freshFlicker() }, lampFlick: freshFlicker(), menuFlick: freshFlicker(),
    whisperT: 20, jumpT: 0, killer: null, cardT: 0,
    voice: { text: '', shown: 0, active: false, hold: 0 },
    motes: [], devGhost: false, devPose: null, devPoseLabel: '', devMon: 0,
  };

  /* where a monster may walk next from a room (unknown rooms send it home) */
  const optionsFrom = (def, room) => (def.path && def.path[room]) || [def.start];

  class Monster {
    constructor(def) {
      this.def = def; this.id = def.id;
      this.art = Art.monsters[def.id];
      this.room = def.start; this.state = 'roam'; this.door = null;
      this.level = 0; this.boost = 0;
      this.timer = (def.moveEvery || 5) * rand(0.8, 1.2);
      this.linger = 0; this.alerted = false; this.seen = false; this.breathT = 0;
      this.animOffset = Math.random() * 10;
    }
    frame(fps) { const n = this.art.frames.length; return Math.floor((G.t + this.animOffset) * (fps || this.def.fps || 4)) % n; }
    get lvl() { return clamp(this.level + this.boost, 0, 20); }
  }

  function initMotes() {
    G.motes = [];
    for (let i = 0; i < 70; i++) G.motes.push({ x: Math.random() * W, y: Math.random() * H, vx: rand(-6, 6), vy: rand(-14, -3), r: rand(1, 4.5), a: rand(0.05, 0.35), ph: Math.random() * 7 });
  }

  /* ------------------------------------------------------------------ */
  /*  EFFECT HELPERS: shake, timers, particles, slow flickers           */
  /* ------------------------------------------------------------------ */
  /* shake the view. a: 0..1 (1 = jumpscare). dirX -1 / 1 also shoves it sideways. Scaled by Dream effects. */
  function hit(a, dirX) {
    const k = fxMul();
    G.trauma = Math.min(1, G.trauma + a * k);
    G.kick.x += (dirX || 0) * 16 * k;
  }

  /* run fn after sec seconds of night time. Freezes while paused; forgotten when the night ends. */
  function after(sec, fn) { G.later.push({ t: sec, fn }); }
  function runLater(dt) {
    if (!G.later.length) return;
    const due = [];
    G.later = G.later.filter((e) => { e.t -= dt; if (e.t > 0) return true; due.push(e.fn); return false; });
    for (const fn of due) fn();
  }

  /* spawnParts(10, { x, y, spreadX, spreadY, vx, vy, jitter, gravity, life, r, col }) — at most 200 alive */
  function spawnParts(n, o) {
    for (let i = 0; i < n && G.parts.length < 200; i++) {
      const life = (o.life || 1) * rand(0.7, 1.3), j = o.jitter == null ? 20 : o.jitter;
      G.parts.push({
        x: o.x + rand(-1, 1) * (o.spreadX || 0), y: o.y + rand(-1, 1) * (o.spreadY || 0),
        vx: (o.vx || 0) + rand(-j, j), vy: (o.vy || 0) + rand(-j, j), g: o.gravity || 0,
        life, max: life, r: (o.r || 3) * rand(0.6, 1.4), col: o.col || '#fff',
      });
    }
  }
  function updateParts(dt) {
    if (!G.parts.length) return;
    for (const p of G.parts) { p.life -= dt; p.vy += p.g * dt; p.x += p.vx * dt; p.y += p.vy * dt; }
    G.parts = G.parts.filter((p) => p.life > 0);
  }

  /* a random dim that can never strobe: each dip lasts .06-.14 s, then at least .3 s of calm */
  function flickerStep(f, dt, chancePerSec, depthMin, depthMax) {
    f.t -= dt;
    if (f.t > 0) return;
    if (f.on) { f.on = false; f.t = 0.3; return; }
    if (Math.random() < chancePerSec * dt) { f.on = true; f.a = rand(depthMin, depthMax); f.t = rand(0.06, 0.14); }
  }
  /* the hallway light stutters while something real stands in it: at most ~3 flips a second */
  function stutterStep(s, dt) {
    s.t -= dt;
    if (s.t <= 0) { s.on = !s.on; s.t = s.on ? rand(0.12, 0.3) : rand(0.25, 0.6); s.a = rand(0.45, 0.8); }
  }
  function updateFlickers(dt) {
    const k = fxMul();
    flickerStep(G.lampFlick, dt, 1.2, 0.05 * k, 0.25 * k);
    flickerStep(G.menuFlick, dt, 1.8, 0.4 * k, 0.4 * k);
    for (const side of ['left', 'right']) {
      const s = G.stutter[side];
      if (G.state === 'night' && G.doors[side].light && !G.powerOut && G.monsters.some((m) => m.state === 'door' && m.door === side)) stutterStep(s, dt);
      else { s.on = false; s.t = 0; }
    }
  }
  const flick = (f) => f.on ? f.a : 0;

  /* ------------------------------------------------------------------ */
  /*  THREAT SOUNDS: every footstep, breath and bang goes through cue() */
  /* ------------------------------------------------------------------ */
  const CUE = { steps: 'footsteps', breath: 'breathing', bang: 'door_bang', far: 'moan', whisper: 'whisper' };
  const Captions = { show() { /* sound captions come in a later update */ } };
  /* cue('breath', 'left', { monster, vol, rate, lowpass, pan, fake }). side: 'left' / 'right' / anything else = o.pan */
  function cue(kind, side, o) {
    o = o || {};
    const own = o.monster && o.monster.def.sounds && o.monster.def.sounds[kind];
    const name = own && Sound.has(own) ? own : CUE[kind];
    const opts = { vol: o.vol == null ? 1 : o.vol, rate: o.rate || 1, pan: sidePan(side, o.pan), lowpass: o.lowpass || 0 };
    let h;
    if (o.fake && Sound.web) h = Sound.play(Sound.reversed(name), opts);     // the dream lies: it plays backwards
    else if (o.fake) {                                                       // file mode can't reverse: slow + echo
      const slow = Object.assign({}, opts, { rate: opts.rate * 0.8 });
      h = Sound.play(name, slow);
      after(0.14, () => Sound.play(name, Object.assign({}, slow, { vol: slow.vol * 0.45 })));
    } else h = Sound.play(name, opts);
    G.cueLog.push({ t: G.nightT, kind, side: side || null, fake: !!o.fake, who: o.monster ? o.monster.id : null });
    if (G.cueLog.length > 40) G.cueLog.shift();
    Captions.show(kind, opts.pan, opts.vol, o);
    return h;
  }

  /* ------------------------------------------------------------------ */
  /*  MONSTER PATHS                                                     */
  /* ------------------------------------------------------------------ */
  const pathCache = {};
  /* for every room: how many steps to the nearest door, and which door that is */
  function pathInfo(def) {
    if (pathCache[def.id]) return pathCache[def.id];
    const info = {};
    for (const start in camById) {
      const seen = {}; seen[start] = true;
      let frontier = [start], d = 0, side = null;
      while (frontier.length && !side) {
        d++;
        const next = [];
        for (const r of frontier) for (const o of optionsFrom(def, r)) {
          if (isDoor(o)) side = side || o.slice(5);
          else if (camById[o] && !seen[o]) { seen[o] = true; next.push(o); }
        }
        frontier = next;
      }
      info[start] = side ? { dist: d, side } : { dist: Infinity, side: null };
    }
    return (pathCache[def.id] = info);
  }
  /* steps from a room to the nearest door: 1 = right next to a door, 0 = at a door, Infinity = can't get there */
  function doorDist(def, room) { if (isDoor(room)) return 0; const i = pathInfo(def)[room]; return i ? i.dist : Infinity; }
  function doorSide(def, room) { if (isDoor(room)) return room.slice(5); const i = pathInfo(def)[room]; return i ? i.side : null; }
  /* nobody is at a door or inside, and every walker is at least minDist steps away */
  function calm(minDist) { return G.monsters.every((m) => m.state === 'roam' && doorDist(m.def, m.room) >= minDist); }

  /* a monster walks into a room (or up to a door) */
  function arrive(m, next, viewing) {
    const from = m.room;
    if (isDoor(next)) {
      const side = next.slice(5);
      m.state = 'door'; m.door = side; m.room = null; m.seen = false;
      m.linger = rand(m.def.waitAtDoor[0], m.def.waitAtDoor[1]);
      m.breathT = rand(0.6, 1.6);
      cue('steps', side, { monster: m, vol: 0.75 });
    } else {
      m.room = camById[next] ? next : m.def.start;
      if (doorDist(m.def, m.room) === 1) cue('steps', null, { monster: m, vol: 0.5, pan: (camById[m.room].map.x - 0.5) * 1.6, lowpass: 2400 });
      else if (Math.random() < 0.3) cue('far', null, { monster: m, vol: 0.32, lowpass: 900, rate: rand(0.85, 1.05), pan: rand(-0.5, 0.5) });
    }
    if (viewing && (viewing === from || viewing === m.room)) camDisrupt();
  }
  /* one step along the shortest way to a door (ties are random) */
  function stepToward(m) {
    if (m.state !== 'roam') return;
    let best = Infinity, choices = [];
    for (const o of optionsFrom(m.def, m.room)) {
      const d = doorDist(m.def, o);
      if (d < best) { best = d; choices = [o]; } else if (d === best) choices.push(o);
    }
    arrive(m, pick(choices), G.cams.up ? G.cams.cur : null);
  }

  /* ------------------------------------------------------------------ */
  /*  NIGHT FLOW                                                        */
  /* ------------------------------------------------------------------ */
  function startNight(n, endless) {
    G.night = n; G.endless = !!endless;
    G.nightT = 0; G.hour = 0; G.timeScale = 1; G.paused = false;
    G.luc = 100; G.usage = 1; G.powerOut = false; G.powerT = 0; G.killAt = 0;
    G.doors.left = freshDoor(); G.doors.right = freshDoor();
    G.cams = freshCams();
    G.inside = null; G.insideT = 0; G.pinchCd = 0; G.danger = 0; G.flash = 0;
    G.trauma = 0; G.kick = { x: 0, y: 0 }; G.later = []; G.parts = []; G.cueLog = []; G.glide = null;
    G.stats = { bangs: 0, pinches: 0, fakesLit: 0, fakeCloses: 0, minLuc: 100, lunges: 0 };
    G.whisperT = rand(18, 40); G.killer = null; G.jumpT = 0;
    G.officeW = officeWidthFor(Art.office);
    G.scroll = Math.max(0, (G.officeW - W) / 2);
    G.monsters = CFG.monsters.map((def) => {
      const m = new Monster(def);
      if (endless) m.level = clamp(save.custom[def.id] != null ? save.custom[def.id] : 10, 0, 20);
      else m.level = (def.levels || [])[n - 1] != null ? def.levels[n - 1] : (def.levels || [5]).slice(-1)[0];
      return m;
    });
    G.grace = n === 1 && !endless ? 22 : 10;
    Sound.resume();
    Sound.stopAll();
    hideScreens(); hide($('#hud')); hide($('#voiceBox')); G.voice.active = false;
    // night card
    setHtml($('#cardNight'), null, numify(endless ? 'Endless Dream' : 'Night ' + n));
    setHtml($('#cardTime'), null, numify('12:00 AM'));
    const card = $('#nightCard');
    card.classList.remove('fade'); show(card);
    // restart the intro animation
    const inner = card.querySelector('.cardInner'); inner.style.animation = 'none'; void inner.offsetWidth; inner.style.animation = '';
    G.state = 'card'; G.cardT = 0;
    Sound.play('hour_chime', { vol: 0.6, rate: 0.8 });
  }

  /* the night card has faded: the night really starts */
  function beginNight() {
    const card = $('#nightCard'), hud = $('#hud');
    card.classList.add('fade');
    G.state = 'night';
    hud.classList.remove('enter'); void hud.offsetWidth; hud.classList.add('enter');
    show(hud);
    updateHud(true);
    const voice = CFG.dreamVoice || {};
    startVoice(G.endless ? voice.endless : voice[G.night]);
    after(1.3, () => hide(card));
  }

  function startVoice(text) {
    const box = $('#voiceBox');
    if (!text) { hide(box); G.voice.active = false; return; }
    G.voice = { text, shown: 0, active: true, hold: 0 };
    $('#voiceText').textContent = '';
    show(box); box.style.opacity = 1;
  }
  function endVoice() {
    G.voice.active = false;
    const box = $('#voiceBox');
    box.style.transition = 'opacity .8s'; box.style.opacity = 0;
    setTimeout(() => { if (!G.voice.active) { hide(box); box.style.transition = ''; } }, 850);
  }

  function setDoor(side, closed) {
    const D = G.doors[side];
    if (G.state !== 'night' || G.powerOut || G.paused) return;
    if (G.inside) { // jammed: the dream won't let you
      Sound.play('ui_click', { vol: 0.5, rate: 0.6 });
      const b = side === 'left' ? $('#btnLDoor') : $('#btnRDoor');
      b.classList.add('jammed'); setTimeout(() => b.classList.remove('jammed'), 300);
      return;
    }
    if (D.closed === closed) return;
    D.closed = closed;
    Sound.play(closed ? 'door_close' : 'door_open', { vol: 0.85, pan: side === 'left' ? -0.7 : 0.7 });
  }
  function setLight(side, on) {
    if (G.state !== 'night' || G.powerOut || G.paused || G.cams.up) return;
    const other = side === 'left' ? 'right' : 'left';
    if (on) G.doors[other].light = false;
    G.doors[side].light = on;
    if (on) G.glide = side; // turn the view toward that doorway so you can see what the light shows
    Sound.play('ui_click', { vol: 0.35, rate: on ? 1 : 0.8, pan: side === 'left' ? -0.6 : 0.6 });
  }
  function toggleCams(force) {
    if (G.state !== 'night' || G.paused) return;
    const want = force != null ? force : !G.cams.up;
    if (want && (G.powerOut || G.inside)) return; // can't hide in the cameras once it's in the room
    if (want === G.cams.up) return;
    G.cams.up = want;
    if (want) {
      G.doors.left.light = false; G.doors.right.light = false;
      G.cams.staticAmt = 1;
      Sound.play('cam_open', { vol: 0.7 });
    } else {
      Sound.play('cam_close', { vol: 0.6 });
    }
  }
  function switchCam(id) {
    if (!G.cams.up || !camById[id] || G.cams.cur === id) return;
    G.cams.cur = id; G.cams.staticAmt = 1;
    Sound.play('cam_switch', { vol: 0.7, rate: rand(0.95, 1.05) });
    updateCamUi();
  }
  function pinch() {
    if (G.state !== 'night' || G.paused || G.pinchCd > 0 || G.powerOut) return;
    const p = CFG.pinch || { amount: 7, cooldown: 25 };
    G.luc = Math.min(100, G.luc + p.amount);
    G.pinchCd = p.cooldown;
    for (const m of G.monsters) if (m.level > 0) m.alerted = true; // level 0 sleeps through it
    G.flash = save.fx === 'off' ? 0.15 : 0.45; G.flashColor = '230,220,255';
    hit(0.25);
    G.stats.pinches++;
    Sound.play('heartbeat', { vol: 0.8, rate: 1.4 });
    Sound.play('whisper', { vol: 0.5, rate: 1.3 });
  }

  function monsterMove(m, forced) {
    if (G.state !== 'night' || G.inside) return;
    if (m.level <= 0 && !forced) return; // level 0 = it never moves tonight
    // after its wait at a SHUT door it always gives up (no endless camping that tempts you to reopen)
    const atShutDoor = m.state === 'door' && m.linger <= 0 && G.doors[m.door].closed;
    if (!(forced || atShutDoor || m.alerted || randi(1, 20) <= m.lvl)) return;
    const viewing = G.cams.up ? G.cams.cur : null;
    if (m.state === 'roam') {
      arrive(m, pick(optionsFrom(m.def, m.room)), viewing);
    } else if (m.state === 'door') {
      if (m.linger > 0) return; // still waiting: a pinch alert stays saved for its next chance
      if (G.doors[m.door].closed) {
        cue('bang', m.door, { monster: m, vol: 0.95 });
        hit(0.3, m.door === 'left' ? 1 : -1);
        G.stats.bangs++;
        m.state = 'roam'; m.door = null;
        m.room = pick(m.def.retreat.length ? m.def.retreat : [m.def.start]);
        if (viewing === m.room) camDisrupt();
      } else {
        enterOffice(m);
      }
    }
    m.alerted = false; // only once a move has really happened
  }

  function camDisrupt() {
    G.cams.staticAmt = 1;
    G.cams.lost = rand(0.7, 1.3);
    Sound.play('cam_switch', { vol: 0.5, rate: 0.6 });
  }

  function enterOffice(m) {
    G.inside = m; m.state = 'inside';
    G.doors.left.light = false; G.doors.right.light = false;
    cue('breath', 'center', { monster: m, vol: 1, rate: 0.9 });
    if (G.cams.up) { G.cams.forceDown = rand(1.2, 2.6); G.insideT = 99; }
    else G.insideT = rand(0.9, 1.7);
  }

  function powerOutStart() {
    G.powerOut = true; G.powerT = 0; G.luc = 0;
    for (const s of ['left', 'right']) {
      if (G.doors[s].closed) Sound.play('door_open', { vol: 0.8, pan: s === 'left' ? -0.7 : 0.7 });
      G.doors[s].closed = false; G.doors[s].light = false;
    }
    if (G.cams.up) { G.cams.up = false; Sound.play('cam_close', { vol: 0.6 }); }
    G.killAt = rand(13, 26);
    G.killer = G.monsters.length ? pick(G.monsters) : null;
    if (G.inside) { // it is already in the room: the dark doesn't save you
      G.killer = G.inside; G.cams.forceDown = 0;
      G.insideT = clamp(G.insideT, 0.3, 1.7);
      G.killAt = G.insideT + 0.2;
    }
    Sound.play('power_down', { vol: 0.95 });
    Sound.stopLoop('ambience', 0.4); Sound.stopLoop('light_buzz', 0.1); Sound.stopLoop('static', 0.1);
    if (G.voice.active) endVoice();
  }

  function jumpscare(m) {
    if (G.state !== 'night') return;
    G.state = 'jumpscare'; G.killer = m; G.jumpT = 0; G.later = [];
    G.cams.up = false; G.cams.t = 0;
    hide($('#hud')); if (G.voice.active) endVoice();
    Sound.stopAll();
    Sound.play((m && m.def.jumpscareSound) || 'jumpscare', { vol: 1 });
    hit(1);
  }

  function die() {
    G.state = 'dead';
    Sound.stopAll();
    Sound.loop('static', 0.35, { fade: 0.05, music: false });
    setTimeout(() => Sound.stopLoop('static', 1.5), 900);
    const tips = [
      'Check the lights before you shut a door — a shut door drains Lucidity fast.',
      'Footsteps nearby mean it is in the West or East Hall.',
      'Breathing at the door? Shut it. Now.',
      'Pinching yourself restores Lucidity, but it hears you.',
      'If it bangs on the door, the door held. Open it again to save Lucidity.',
      'The cameras cost Lucidity too. Don’t stare.',
    ];
    $('#deadTip').innerHTML = numify(G.powerOut ? 'Your Lucidity ran out. Spend it more carefully.' : pick(tips));
    $('#deadTitle').textContent = G.killer ? (G.killer.def.name.toUpperCase() + ' FOUND YOU') : 'IT FOUND YOU';
    showScreen('#dead');
  }

  function win() {
    G.state = 'win'; G.later = [];
    Sound.stopAll();
    hide($('#hud')); if (G.voice.active) endVoice();
    Sound.play('alarm', { vol: 0.9 });
    setTimeout(() => { if (G.state === 'win') Sound.loop('morning', 0.8, { fade: 3, music: true }); }, 2600);
    if (!G.endless) {
      save.beaten = Math.max(save.beaten, G.night);
      save.night = clamp(G.night + 1, 1, NIGHTS);
      writeSave();
    }
    const hEl = $('#winH'); hEl.textContent = '5'; hEl.classList.remove('roll');
    const title = $('#winTitle'); title.classList.remove('show');
    const last = !G.endless && G.night >= NIGHTS;
    $('#winSub').innerHTML = numify(G.endless ? 'The endless dream let you go… this time.'
      : last ? 'All five nights. The alarm rang, and this time you heard it.'
        : 'Night ' + G.night + ' survived. But you’ll fall asleep again tonight.');
    $('#wNext').textContent = (G.endless || last) ? 'Back to the menu' : 'Next night';
    showScreen('#win');
    G.flash = 1; G.flashColor = '255,244,220';
    setTimeout(() => { void hEl.offsetWidth; hEl.classList.add('roll'); setTimeout(() => { hEl.textContent = '6'; }, 330); }, 1100);
    setTimeout(() => title.classList.add('show'), 2000);
  }

  /* ------------------------------------------------------------------ */
  /*  UPDATE                                                            */
  /* ------------------------------------------------------------------ */
  const keys = {};
  const pointer = { x: W / 2, y: H / 2, inside: false, type: 'mouse', dragId: null, lastX: 0 };

  function update(dt) {
    G.t += dt;
    for (const m of G.motes) {
      m.x += m.vx * dt; m.y += m.vy * dt; m.ph += dt;
      if (m.y < -10) { m.y = H + 10; m.x = Math.random() * W; }
      if (m.x < -10) m.x = W + 10; if (m.x > W + 10) m.x = -10;
    }
    G.flash = Math.max(0, G.flash - dt * 1.8);
    G.trauma = Math.max(0, G.trauma - dt * 1.5);
    G.kick.x *= Math.exp(-12 * dt);
    if (!G.paused) { updateParts(dt); updateFlickers(dt); }

    if (G.state === 'card') { G.cardT += dt; if (G.cardT >= 3.2) beginNight(); }
    if (G.state === 'night' && !G.paused) updateNight(dt * G.timeScale, dt);
    if (G.state === 'jumpscare') {
      G.jumpT += dt;
      if (G.jumpT > 1.45) die();
    }
    Sound.update(dt);
  }

  /* the scroll that brings that doorway fully into view (or the current one if it already is) */
  function glideTarget(side, maxScroll) {
    const d = CFG.office.doors[side], margin = 60;
    if (side === 'left') return clamp(Math.min(G.scroll, d.x * G.officeW - margin), 0, maxScroll);
    return clamp(Math.max(G.scroll, (d.x + d.w) * G.officeW - W + margin), 0, maxScroll);
  }

  function updateNight(dt, realDt) {
    const C = G.cams;
    runLater(dt);
    if (G.state !== 'night') return; // a timer ended the night
    // clock
    G.nightT += dt;
    const hs = Math.max(5, CFG.hourSeconds || 75);
    const hour = Math.floor(G.nightT / hs);
    if (hour >= 6) { win(); return; }
    if (hour !== G.hour) {
      G.hour = hour;
      Sound.play('hour_chime', { vol: 0.55, rate: 0.9 });
      for (const m of G.monsters) { const b = (m.def.hourBoost || {})[hour]; if (b && m.level > 0) m.boost += b; }
    }

    // looking around (mouse at the edges, arrow keys, or a glide toward a light you just turned on)
    const maxScroll = Math.max(0, G.officeW - W);
    if (!C.up) {
      let v = 0;
      if (keys.ArrowLeft) v -= 950;
      if (keys.ArrowRight) v += 950;
      if (pointer.inside && pointer.type === 'mouse' && !v) {
        const edge = W * 0.22;
        if (pointer.x < edge) v = -1150 * Math.pow((edge - pointer.x) / edge, 1.3);
        else if (pointer.x > W - edge) v = 1150 * Math.pow((pointer.x - (W - edge)) / edge, 1.3);
      }
      if (v) G.glide = null; // the player is steering
      G.panV = lerp(G.panV, v, clamp(realDt * 10, 0, 1));
      G.scroll = clamp(G.scroll + G.panV * realDt, 0, maxScroll);
      if (G.glide) {
        const target = glideTarget(G.glide, maxScroll);
        G.scroll = lerp(G.scroll, target, 1 - Math.exp(-7 * realDt));
        if (Math.abs(G.scroll - target) < 1) G.glide = null;
      }
    }

    // doors slide
    for (const s of ['left', 'right']) {
      const D = G.doors[s];
      D.p = clamp(D.p + (D.closed ? 1 : -1) * realDt / 0.22, 0, 1);
    }
    // camera monitor
    C.t = clamp(C.t + (C.up ? 1 : -1) * realDt / 0.28, 0, 1);
    C.staticAmt = Math.max(0, C.staticAmt - realDt * 2.6);
    C.lost = Math.max(0, C.lost - realDt);

    // lucidity
    if (!G.powerOut) {
      G.usage = 1 + (G.doors.left.closed ? 1 : 0) + (G.doors.right.closed ? 1 : 0)
        + ((G.doors.left.light || G.doors.right.light) ? 1 : 0) + (C.up ? 1 : 0);
      G.luc -= rule('drain', 0.12) * G.usage * dt;
      G.stats.minLuc = Math.min(G.stats.minLuc, Math.max(0, G.luc));
      if (G.luc <= 0) powerOutStart();
    }

    // monsters
    if (G.grace > 0) G.grace -= dt;
    for (const m of G.monsters) {
      if (m.state === 'door') {
        m.linger -= dt;
        m.breathT -= dt;
        if (m.breathT <= 0) {
          m.breathT = rand(5, 9);
          const D = G.doors[m.door];
          cue('breath', m.door, { monster: m, vol: D.closed ? 0.35 : 0.6, lowpass: D.closed ? 700 : 0, rate: rand(0.9, 1.05) });
        }
        if (G.doors[m.door].light && !m.seen && !G.powerOut) {
          m.seen = true;
          cue('breath', m.door, { monster: m, vol: 1 });
          hit(0.18);
        }
      }
      if (G.powerOut || G.inside || G.grace > 0) continue;
      m.timer -= dt;
      if (m.timer <= 0) {
        m.timer += (m.def.moveEvery || 5) * rand(0.85, 1.15);
        monsterMove(m);
      }
    }

    // something got in
    if (G.inside) {
      if (C.forceDown > 0) {
        C.forceDown -= dt;
        C.staticAmt = Math.max(C.staticAmt, 0.6);
        if (C.forceDown <= 0) { toggleCams(false); G.insideT = rand(0.35, 0.6); }
      } else if (!C.up) {
        G.insideT -= dt;
        if (G.insideT <= 0) { jumpscare(G.inside); return; }
      }
    }

    // out of lucidity: the dream stops listening
    if (G.powerOut) {
      G.powerT += dt;
      if (G.powerT > 3 && G.powerT - dt <= 3) Sound.loop('music_box', 0.9, { fade: 1, music: true });
      if (G.powerT >= G.killAt) { Sound.stopLoop('music_box', 0.05); if (G.killer) { jumpscare(G.killer); return; } }
    }

    // pinch cooldown
    G.pinchCd = Math.max(0, G.pinchCd - dt);

    // how scary is it right now?
    let danger = 0;
    for (const m of G.monsters) {
      if (m.state === 'door' && m.seen) danger = Math.max(danger, 0.75);
      if (m.state === 'inside') danger = 1;
    }
    if (!G.powerOut && G.luc < 12) danger = Math.max(danger, 0.5);
    if (G.powerOut) danger = Math.max(danger, 0.7);
    G.danger = lerp(G.danger, danger, clamp(realDt * 2, 0, 1));

    // sound beds
    if (!G.powerOut) Sound.loop('ambience', C.up ? 0.4 : 0.6, { fade: 2 });
    Sound.loop('static', C.t > 0.5 ? 0.12 + C.staticAmt * 0.35 + (C.lost > 0 ? 0.3 : 0) : 0, { fade: 0.15, music: false });
    const lightSide = G.doors.left.light ? 'left' : G.doors.right.light ? 'right' : null;
    Sound.loop('light_buzz', lightSide && !G.powerOut ? 0.4 : 0, { fade: 0.08, music: false, pan: lightSide === 'right' ? 0.6 : -0.6 });
    Sound.loop('heartbeat', G.danger > 0.45 ? clamp((G.danger - 0.3) * 1.2, 0, 0.85) : 0, { fade: 0.6, music: false, rate: 0.9 + G.danger * 0.35 });

    G.whisperT -= dt;
    if (G.whisperT <= 0) {
      G.whisperT = rand(28, 70);
      Sound.play('whisper', { vol: rand(0.18, 0.35), rate: rand(0.75, 1.1), pan: rand(-0.9, 0.9) });
    }

    // dream voice typewriter
    if (G.voice.active) {
      const v = G.voice;
      if (v.shown < v.text.length) {
        v.shown = Math.min(v.text.length, v.shown + realDt * 34);
        $('#voiceText').innerHTML = escapeHtml(v.text.slice(0, Math.floor(v.shown))) + '<span class="caret">▌</span>';
      } else {
        v.hold += realDt;
        if (v.hold > 7) endVoice();
      }
    }

    updateHud(false);
  }

  /* ------------------------------------------------------------------ */
  /*  RENDER                                                            */
  /* ------------------------------------------------------------------ */
  const canvas = $('#screen'), ctx = canvas.getContext('2d');
  const buf = makeCanvas(W, H), bx = buf.getContext('2d');
  const bloom = makeCanvas(160, 90), blx = bloom.getContext('2d');

  function drawCover(c, img, x, y, w, h) {
    const s = Math.max(w / img.width, h / img.height);
    const dw = img.width * s, dh = img.height * s;
    c.drawImage(img, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh);
  }

  function drawSprite(c, img, box, pose, alpha) {
    const p = pose || { x: 0.5, y: 1.02, h: 0.7 };
    const h = (p.h || 0.7) * box.h, w = h * img.width / img.height;
    const cx = box.x + (p.x != null ? p.x : 0.5) * box.w, by = box.y + (p.y != null ? p.y : 1) * box.h;
    c.save(); c.globalAlpha = alpha == null ? 1 : alpha;
    if (p.flip) { c.translate(cx, 0); c.scale(-1, 1); c.drawImage(img, -w / 2, by - h, w, h); }
    else c.drawImage(img, cx - w / 2, by - h, w, h);
    c.restore();
  }

  function officeOriginX() { return G.officeW <= W ? (W - G.officeW) / 2 : -G.scroll; }

  function drawOffice(c) {
    const ox = officeOriginX(), ow = G.officeW;
    c.fillStyle = '#000'; c.fillRect(0, 0, W, H);
    // gentle dream "breathing" of the room
    const br = 0.006 * fxMul();
    const s = 1 + br + Math.sin(G.t * 0.6) * br;
    c.save();
    c.translate(W / 2, H / 2); c.scale(s, s); c.translate(-W / 2, -H / 2);
    c.drawImage(Art.office, ox, 0, ow, H);
    for (const side of ['left', 'right']) drawDoorway(c, side, ox, ow);
    c.restore();

    // lamp flicker (a slow timer, never a strobe) & darkness
    c.fillStyle = `rgba(0,0,0,${0.08 + flick(G.lampFlick)})`; c.fillRect(0, 0, W, H);
    if (G.powerOut) {
      const dark = clamp(G.powerT / 1.2, 0, 1) * 0.86;
      c.fillStyle = `rgba(0,0,0,${dark})`; c.fillRect(0, 0, W, H);
      // it stands in the dark doorway, barely there: a slow 1.4 Hz pulse, or steady with effects Off
      const off = save.fx === 'off';
      if (G.powerT > 3 && G.killer && (off || Math.sin(G.t * 9) > -0.2)) {
        const d = CFG.office.doors.left;
        const box = { x: ox + d.x * ow, y: d.y * H, w: d.w * ow, h: d.h * H };
        c.save(); c.beginPath(); c.rect(box.x, box.y, box.w, box.h); c.clip();
        drawSprite(c, G.killer.art.soft[G.killer.frame()], box, doorPoseOf(G.killer, 'left'), off ? 0.2 : 0.22 + 0.1 * Math.sin(G.t * 3));
        c.restore();
      }
    }
  }

  /* where a monster stands in a lit doorway (config doorPose, or a pose that fits the whole body in) */
  function doorPoseOf(m, side) {
    return (m.def.doorPose && m.def.doorPose[side]) || { x: side === 'left' ? 0.55 : 0.45, y: 1, h: 0.7, flip: side === 'right' };
  }

  function drawDoorway(c, side, ox, ow) {
    const d = CFG.office.doors[side], D = G.doors[side], A = Art.doors[side];
    const box = { x: ox + d.x * ow, y: d.y * H, w: d.w * ow, h: d.h * H };
    if (box.x > W + 40 || box.x + box.w < -40) return;
    const lit = D.light && !G.powerOut;
    c.save();
    c.beginPath(); c.rect(box.x, box.y, box.w, box.h); c.clip();
    c.drawImage(lit ? A.lit : A.dark, box.x, box.y, box.w, box.h);
    if (lit) {
      const here = G.monsters.filter((m) => m.state === 'door' && m.door === side);
      for (const m of here) drawSprite(c, m.art.soft[m.frame()], box, doorPoseOf(m, side), 1);
      // the light stutters while something real stands there (slow timer; a steady dim with effects Off)
      const dim = here.length ? (save.fx === 'off' ? 0.3 : flick(G.stutter[side])) : 0;
      if (dim) { c.fillStyle = `rgba(0,0,0,${dim})`; c.fillRect(box.x, box.y, box.w, box.h); }
      const g = c.createLinearGradient(0, box.y, 0, box.y + box.h);
      g.addColorStop(0, 'rgba(255,230,160,.12)'); g.addColorStop(1, 'rgba(0,0,0,.25)');
      c.fillStyle = g; c.fillRect(box.x, box.y, box.w, box.h);
    }
    if (D.p > 0) {
      const y = box.y - box.h * (1 - ease(D.p));
      c.drawImage(A.closed, box.x, y, box.w, box.h);
      c.fillStyle = 'rgba(0,0,0,.5)'; c.fillRect(box.x, y + box.h - 6, box.w, 6);
    }
    c.restore();
    if (DEV) {
      c.save(); c.strokeStyle = '#3f3'; c.lineWidth = 2; c.setLineDash([8, 6]); c.strokeRect(box.x, box.y, box.w, box.h);
      c.fillStyle = '#3f3'; c.font = '22px VT323, monospace';
      c.fillText(side + ' door  x:' + d.x + ' y:' + d.y + ' w:' + d.w + ' h:' + d.h, box.x + 4, box.y - 8); c.restore();
    }
  }

  function camFeedBox() {
    const zoom = 1.14, fw = W * zoom, fh = H * zoom;
    const cam = camById[G.cams.cur];
    const pan = (G.devGhost ? 0.5 : Math.sin(G.t * 0.23 + cam.index * 1.7) * 0.5 + 0.5);
    return { x: -(fw - W) * pan, y: -(fh - H) / 2, w: fw, h: fh };
  }

  function drawCams(c) {
    const C = G.cams, cam = camById[C.cur];
    const box = camFeedBox();
    c.fillStyle = '#000'; c.fillRect(0, 0, W, H);
    drawCover(c, Art.cams[cam.id], box.x, box.y, box.w, box.h);
    const lost = C.lost > 0;
    if (!lost) {
      for (const m of G.monsters) {
        if (m.state === 'roam' && m.room === cam.id) drawSprite(c, m.art.soft[m.frame()], box, m.def.poses && m.def.poses[cam.id], 1);
      }
    }
    if (DEV && G.devGhost) {
      const def = devMonDef();
      if (def) {
        const pose = (def.poses && def.poses[cam.id]) || { x: 0.5, y: 1.02, h: 0.7 };
        drawSprite(c, Art.monsters[def.id].soft[Math.floor(G.t * (def.fps || 4)) % Art.monsters[def.id].soft.length], box, pose, 0.85);
      }
    }
    // night-vision grade
    c.save();
    c.globalCompositeOperation = 'multiply'; c.fillStyle = 'rgb(205, 232, 216)'; c.fillRect(0, 0, W, H);
    c.globalCompositeOperation = 'source-over';
    // static
    c.imageSmoothingEnabled = false;
    c.globalAlpha = clamp(0.1 + C.staticAmt * 0.7 + (lost ? 0.85 : 0) + (G.inside ? 0.25 : 0), 0, 0.97);
    c.drawImage(Art.noise[Math.floor(G.t * 24) % Art.noise.length], 0, 0, W, H);
    c.imageSmoothingEnabled = true;
    c.globalAlpha = 1;
    // rolling bar
    const ry = ((G.t * 140) % (H + 200)) - 100;
    const g = c.createLinearGradient(0, ry - 60, 0, ry + 60);
    g.addColorStop(0, 'rgba(255,255,255,0)'); g.addColorStop(0.5, 'rgba(255,255,255,.06)'); g.addColorStop(1, 'rgba(255,255,255,0)');
    c.fillStyle = g; c.fillRect(0, ry - 60, W, 120);
    c.fillStyle = c.createPattern(Art.scan, 'repeat'); c.fillRect(0, 0, W, H);
    c.drawImage(Art.vignette, 0, 0);
    c.restore();
    // monitor frame
    c.strokeStyle = 'rgba(0,0,0,.9)'; c.lineWidth = 40; c.strokeRect(0, 0, W, H);
  }

  function drawMenuScene(c) {
    c.fillStyle = '#05030a'; c.fillRect(0, 0, W, H);
    // drifting fog
    for (let i = 0; i < 5; i++) {
      const fx = W * (0.5 + 0.45 * Math.sin(G.t * 0.05 + i * 1.7)), fy = H * (0.5 + 0.35 * Math.cos(G.t * 0.07 + i * 2.3));
      const g = c.createRadialGradient(fx, fy, 0, fx, fy, 520);
      g.addColorStop(0, i % 2 ? 'rgba(120, 30, 60, .16)' : 'rgba(80, 60, 160, .14)'); g.addColorStop(1, 'rgba(0,0,0,0)');
      c.fillStyle = g; c.fillRect(0, 0, W, H);
    }
    const def = CFG.monsters[0];
    if (def && Art.monsters[def.id]) {
      const A = Art.monsters[def.id];
      // a short glitch once every 7 s (none with effects Off); its double image stays put during the burst
      const glitch = save.fx !== 'off' && (G.t % 7) > 6.75;
      const fi = glitch ? Math.floor(G.t * 30) % A.frames.length : Math.floor(G.t * (def.fps || 4)) % A.frames.length;
      const box = { x: W * 0.56, y: 0, w: W * 0.44, h: H };
      const alpha = 0.78 + 0.12 * Math.sin(G.t * 0.9) - flick(G.menuFlick);
      if (glitch) {
        const off = (mulberry32(Math.floor(G.t / 7))() - 0.5) * 28 * fxMul();
        c.save(); c.globalCompositeOperation = 'lighter';
        drawSprite(c, A.soft[fi], { x: box.x + off, y: box.y, w: box.w, h: box.h }, { x: 0.5, y: 1.08, h: 1.02 }, 0.35);
        c.restore();
      }
      drawSprite(c, A.soft[fi], box, { x: 0.5, y: 1.08, h: 1.02 }, alpha);
      const g = c.createLinearGradient(W * 0.4, 0, W, 0);
      g.addColorStop(0, 'rgba(5,3,10,1)'); g.addColorStop(0.25, 'rgba(5,3,10,0)');
      c.fillStyle = g; c.fillRect(W * 0.4, 0, W * 0.6, H);
    }
  }

  function drawJumpscare(c) {
    const m = G.killer; const t = G.jumpT;
    c.fillStyle = '#000'; c.fillRect(0, 0, W, H);
    if (!m) return;
    const frames = m.art.jump;
    const fi = Math.floor(t * (m.def.jumpscareFps || 14)) % frames.length;
    const img = frames[fi];
    const grow = 1.1 + ease(clamp(t / 0.35, 0, 1)) * 0.8 + t * 0.15;
    const h = H * grow, w = h * img.width / img.height;
    const focus = m.def.jumpscareFocus || { x: 0.5, y: 0.2 };   // the point of the picture that rushes at you
    const ix = W / 2 - focus.x * w, iy = H * 0.42 - focus.y * h;
    const jx = rand(-30, 30) * fxMul(), jy = rand(-20, 20) * fxMul();
    c.save();
    if (save.fx !== 'off') {
      c.globalCompositeOperation = 'lighter'; c.globalAlpha = 0.35;
      c.drawImage(img, ix + jx + 18, iy + jy, w, h);
      c.globalCompositeOperation = 'source-over'; c.globalAlpha = 1;
    }
    c.drawImage(img, ix + jx, iy + jy, w, h);
    c.restore();
    if (t > 1.2) { c.fillStyle = `rgba(0,0,0,${clamp((t - 1.2) / 0.25, 0, 1)})`; c.fillRect(0, 0, W, H); }
  }

  function drawMotes(c, alphaMul) {
    c.save(); c.globalCompositeOperation = 'lighter';
    for (const m of G.motes) {
      const a = m.a * (0.6 + 0.4 * Math.sin(m.ph * 1.3)) * alphaMul;
      c.globalAlpha = a; c.drawImage(Art.dot, m.x - m.r * 2, m.y - m.r * 2, m.r * 4, m.r * 4);
    }
    c.restore();
  }

  function drawParts(c) {
    if (!G.parts.length) return;
    c.save();
    for (const p of G.parts) {
      c.globalAlpha = clamp(p.life / p.max, 0, 1);
      c.drawImage(tinted(Art.dot, p.col), p.x - p.r * 2, p.y - p.r * 2, p.r * 4, p.r * 4);
    }
    c.restore();
  }

  /* eyelids over the whole screen: closed 0 = wide open, 1 = shut (falling asleep, waking up) */
  function drawEyelids(c, closed) {
    closed = clamp(closed, 0, 1);
    if (closed <= 0) return;
    const mid = H / 2 * closed, end = mid - H * 0.15 * closed; // the lid's corners sit higher than its middle
    c.save(); c.fillStyle = c.strokeStyle = '#000'; c.lineWidth = 40;
    for (const top of [true, false]) {
      const edge = top ? 0 : H, ym = top ? mid : H - mid, ye = top ? end : H - end, cy = 2 * ym - ye;
      c.globalAlpha = 1;
      c.beginPath(); c.moveTo(0, edge); c.lineTo(0, ye); c.quadraticCurveTo(W / 2, cy, W, ye); c.lineTo(W, edge); c.closePath(); c.fill();
      c.globalAlpha = 0.5; // a soft edge
      c.beginPath(); c.moveTo(0, ye); c.quadraticCurveTo(W / 2, cy, W, ye); c.stroke();
    }
    if (closed > 0.85) { c.globalAlpha = (closed - 0.85) / 0.15; c.fillRect(0, 0, W, H); } // the corners close too
    c.restore();
  }

  /* art-helper only: which file would replace the stand-in picture on screen right now */
  function drawStandInHint(c, path) {
    const text = 'stand-in art — your picture goes at ' + path;
    c.save();
    c.font = '24px VT323, monospace'; c.textAlign = 'center'; c.textBaseline = 'middle';
    const w = c.measureText(text).width + 28;
    c.fillStyle = 'rgba(0,0,0,.6)'; c.fillRect(W / 2 - w / 2, 44, w, 34);
    c.fillStyle = 'rgba(233,223,207,.85)'; c.fillText(text, W / 2, 62);
    c.restore();
  }

  function render() {
    const st = G.state;
    const fx = save.fx;
    let ghost = 1, warp = 0;
    if (st === 'menu' || st === 'boot' || st === 'card') {
      drawMenuScene(bx);
      drawMotes(bx, 1);
      drawParts(bx);
      warp = fx === 'full' ? 2 : 0;
      ghost = fx === 'full' ? 0.75 : 1;
    } else if (st === 'night' || st === 'win' || st === 'dead') {
      if (G.cams.t >= 1) drawCams(bx);
      else {
        drawOffice(bx);
        drawMotes(bx, G.powerOut ? 0.3 : 1);
        drawParts(bx);
        if (G.cams.t > 0) {
          const y = H * (1 - ease(G.cams.t));
          bx.save(); bx.translate(0, y);
          bx.fillStyle = '#050806'; bx.fillRect(0, 0, W, H);
          bx.globalAlpha = 0.9; bx.imageSmoothingEnabled = false;
          bx.drawImage(Art.noise[Math.floor(G.t * 24) % Art.noise.length], 0, 0, W, H);
          bx.imageSmoothingEnabled = true; bx.globalAlpha = 1;
          bx.strokeStyle = '#000'; bx.lineWidth = 40; bx.strokeRect(0, 0, W, H);
          bx.restore();
        }
      }
      const amt = fx === 'full' ? 1 : fx === 'low' ? 0.35 : 0;
      warp = (1.5 + G.danger * 7) * amt;
      ghost = fx === 'full' ? 0.82 : 1;
    } else if (st === 'jumpscare') {
      drawJumpscare(bx);
      warp = fx === 'full' ? 9 : fx === 'low' ? 3 : 0;
    } else {
      bx.fillStyle = '#000'; bx.fillRect(0, 0, W, H);
    }

    // present: dream warp + ghosting + bloom + vignette
    ctx.save();
    const s = 26 * G.trauma * G.trauma; // shake grows with the square of trauma, so small hits stay small
    if (s > 0.05 || Math.abs(G.kick.x) > 0.05) {
      ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
      ctx.translate(W / 2 + s * nz(G.t * 31) + G.kick.x, H / 2 + s * nz(G.t * 27 + 9));
      ctx.rotate(s * 0.0012 * nz(G.t * 19));
      ctx.translate(-W / 2, -H / 2);
    }
    ctx.globalAlpha = ghost;
    if (warp < 0.3) ctx.drawImage(buf, 0, 0);
    else {
      const SH = 6;
      for (let y = 0; y < H; y += SH) {
        const dx = Math.sin(y * 0.011 + G.t * 1.6) * warp + Math.sin(y * 0.037 - G.t * 0.8) * warp * 0.35;
        ctx.drawImage(buf, 0, y, W, SH, dx - warp, y, W + warp * 2, SH);
      }
    }
    ctx.globalAlpha = 1;
    if (fx !== 'off') {
      blx.clearRect(0, 0, 160, 90); blx.drawImage(buf, 0, 0, 160, 90);
      ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = 0.16;
      ctx.drawImage(bloom, 0, 0, W, H);
      ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
    }
    ctx.drawImage(Art.vignette, 0, 0);
    if (G.danger > 0.05 && (st === 'night')) {
      const pulse = 0.5 + 0.5 * Math.sin(G.t * (4 + G.danger * 5)) * fxMul(); // a slow pulse; steady with effects Off
      const g = ctx.createRadialGradient(W / 2, H / 2, H * 0.35, W / 2, H / 2, H);
      g.addColorStop(0, 'rgba(150,0,20,0)'); g.addColorStop(1, `rgba(150,0,20,${G.danger * 0.45 * (0.5 + pulse * 0.5)})`);
      ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    }
    ctx.restore();
    if (DEV && st === 'night') {
      if (G.cams.t >= 1) { if (Art.camMissing[G.cams.cur]) drawStandInHint(ctx, camById[G.cams.cur].image); }
      else if (Art.officeMissing) drawStandInHint(ctx, CFG.office.image);
    }
    const fl = fx === 'off' ? Math.min(G.flash, 0.25) : G.flash;
    flashEl.style.opacity = fl > 0.01 ? fl : 0;
    if (fl > 0.01) flashEl.style.background = `rgb(${G.flashColor})`;
  }
  const flashEl = $('#flash');

  /* ------------------------------------------------------------------ */
  /*  HUD + UI                                                          */
  /* ------------------------------------------------------------------ */
  const hudEls = {
    night: $('#hudNight'), time: $('#hudTime'), pct: $('#lucPct'), fill: $('#lucFill'), pips: Array.from(document.querySelectorAll('#usage i')),
    lDoor: $('#btnLDoor'), lLight: $('#btnLLight'), rDoor: $('#btnRDoor'), rLight: $('#btnRLight'),
    camBar: $('#camBar'), pinch: $('#pinchBtn'), pinchCd: $('#pinchCd'), overlay: $('#camOverlay'),
    stamp: $('#camStamp'), signal: $('#camSignal'), dev: $('#devInfo'), camLabel: $('#camBar span'), voice: $('#voiceBox'),
  };
  let lastHud = {};
  function setText(el, key, v) { if (lastHud[key] !== v) { lastHud[key] = v; el.textContent = v; } }
  /* like setText, but for trusted HTML (e.g. numify); key null = always write */
  function setHtml(el, key, html) { if (key == null || lastHud[key] !== html) { if (key != null) lastHud[key] = html; el.innerHTML = html; } }
  function setCls(el, cls, on) { if (el.classList.contains(cls) !== !!on) el.classList.toggle(cls, !!on); }

  function updateHud(force) {
    if (force) lastHud = {};
    setHtml(hudEls.night, 'night', G.endless ? 'ENDLESS' : numify('NIGHT ' + G.night));
    setText(hudEls.time, 'time', fmtHour(G.hour));
    const pct = Math.max(0, Math.ceil(G.luc));
    setText(hudEls.pct, 'pct', pct + '%');
    hudEls.fill.style.width = clamp(G.luc, 0, 100) + '%';
    setCls(hudEls.pct, 'low', pct <= 15); setCls(hudEls.fill, 'low', pct <= 15);
    hudEls.pips.forEach((p, i) => { setCls(p, 'on', !G.powerOut && i < G.usage); setCls(p, 'hot', i >= 3); });
    setCls(hudEls.lDoor, 'on', G.doors.left.closed); setCls(hudEls.rDoor, 'on', G.doors.right.closed);
    setCls(hudEls.lLight, 'on', G.doors.left.light); setCls(hudEls.rLight, 'on', G.doors.right.light);
    for (const b of [hudEls.lDoor, hudEls.lLight, hudEls.rDoor, hudEls.rLight, hudEls.camBar, hudEls.pinch]) setCls(b, 'dead', G.powerOut);
    const camsShown = G.cams.t >= 0.98;
    setCls(hudEls.overlay, 'hidden', !camsShown);
    setCls($('#leftPanel'), 'hidden', G.cams.t > 0.05);
    setCls($('#rightPanel'), 'hidden', G.cams.t > 0.05);
    setCls(hudEls.pinch, 'hidden', G.cams.t > 0.05);
    setCls(hudEls.camBar, 'up', G.cams.up);
    setHtml(hudEls.camLabel, 'camLabel', G.cams.up ? '▼&nbsp;&nbsp;LOWER&nbsp;&nbsp;▼' : '▲&nbsp;&nbsp;CAMERAS&nbsp;&nbsp;▲');
    setCls(hudEls.voice, 'docked', G.cams.t > 0.5); // tuck the voice out of the camera picture
    setCls(hudEls.pinch, 'cool', G.pinchCd > 0);
    hudEls.pinchCd.style.width = G.pinchCd > 0 ? (100 * (1 - G.pinchCd / ((CFG.pinch && CFG.pinch.cooldown) || 25))) + '%' : '0';
    if (camsShown) {
      const mins = Math.floor((G.nightT % (CFG.hourSeconds || 75)) / (CFG.hourSeconds || 75) * 60);
      setText(hudEls.stamp, 'stamp', (G.hour === 0 ? 12 : G.hour) + ':' + String(mins).padStart(2, '0') + ' AM');
      setCls(hudEls.signal, 'hidden', !(G.cams.lost > 0));
    }
    if (DEV) updateDev();
  }

  function buildCamMap() {
    const map = $('#camMap'), svg = $('#camLinks');
    map.querySelectorAll('.camBtn').forEach((b) => b.remove());
    svg.innerHTML = '';
    const P = (p) => ({ x: p.x * 100, y: p.y * 100 });
    const links = new Set(), lines = [];
    const you = { x: 50, y: (93 - 6) / 88 * 100 };
    for (const m of CFG.monsters) {
      for (const from in (m.path || {})) {
        for (const to of m.path[from]) {
          if (!camById[from]) continue;
          if (String(to).indexOf('door:') === 0) {
            const k = from + '>you'; if (links.has(k)) continue; links.add(k);
            lines.push([P(camById[from].map), you]);
          } else if (camById[to]) {
            const k = [from, to].sort().join('|'); if (links.has(k)) continue; links.add(k);
            lines.push([P(camById[from].map), P(camById[to].map)]);
          }
        }
      }
    }
    for (const [a, b] of lines) {
      const l = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      l.setAttribute('x1', a.x); l.setAttribute('y1', a.y); l.setAttribute('x2', b.x); l.setAttribute('y2', b.y);
      svg.appendChild(l);
    }
    CFG.cameras.forEach((c, i) => {
      const b = document.createElement('button');
      b.className = 'camBtn'; b.dataset.cam = c.id;
      b.textContent = c.label || ('CAM ' + (i + 1));
      b.title = c.name + (i < 9 ? '  [' + (i + 1) + ']' : '');
      b.style.left = (6 + c.map.x * 88) + '%'; b.style.top = (6 + c.map.y * 88) + '%';
      b.addEventListener('pointerdown', (e) => { e.stopPropagation(); switchCam(c.id); });
      map.appendChild(b);
    });
  }
  function updateCamUi() {
    const cam = camById[G.cams.cur];
    $('#camName').textContent = (cam.label || '') + ' — ' + cam.name.toUpperCase();
    document.querySelectorAll('.camBtn').forEach((b) => b.classList.toggle('sel', b.dataset.cam === cam.id));
  }

  const SCREENS = ['#boot', '#menu', '#nightCard', '#pause', '#settings', '#extras', '#custom', '#dead', '#win'];
  function hideScreens() { SCREENS.forEach((s) => hide($(s))); }
  function showScreen(sel) {
    hideScreens(); show($(sel));
    // screens you reach mid-game get keyboard focus, so Enter picks the obvious button
    if (sel === '#dead' || sel === '#win' || sel === '#pause') {
      const b = $(sel).querySelector('button:not(.hidden):not([disabled])');
      if (b) b.focus({ preventScroll: true });
    }
  }

  let returnTo = '#menu';
  function goMenu() {
    if (G.paused) Sound.pauseAll(false); // quitting from Pause must not leave the sound switched off
    G.state = 'menu'; G.paused = false; G.later = [];
    hide($('#hud')); hide($('#voiceBox'));
    Sound.resume();
    Sound.stopAll();
    Sound.loop('menu_music', 0.75, { fade: 2.5 });
    refreshMenu();
    showScreen('#menu');
  }
  function refreshMenu() {
    $('#menuTitle').textContent = CFG.title || 'UNTIL THE ALARM';
    $('#menuSub').textContent = CFG.subtitle || '';
    document.title = toTitleCase(CFG.title || 'Until the Alarm');
    // Continue only makes sense past Night 1; after the last night it becomes a replay
    const cont = $('#mContinue');
    cont.classList.toggle('hidden', save.night <= 1);
    cont.firstChild.textContent = save.beaten >= NIGHTS && save.night >= NIGHTS ? 'Replay ' : 'Continue ';
    $('#mContinueN').innerHTML = numify('— Night ' + save.night);
    const open = endlessUnlocked(), e = $('#mEndless');
    e.disabled = !open; // a locked button can't be reached with the keyboard either
    e.classList.toggle('locked', !open);
    e.title = open ? '' : 'Survive all five nights to unlock';
    e.innerHTML = open ? 'Endless Dream' : 'Endless Dream <em>— locked</em>';
    $('#mNew').innerHTML = 'New Dream';
    $('#mNew').dataset.confirm = '';
  }
  const endlessUnlocked = () => save.beaten >= NIGHTS || DEV;
  function toTitleCase(s) { return s.toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase()); }

  function pauseGame(p) {
    if (G.state !== 'night') return;
    if (p === G.paused) return;
    G.paused = p;
    Sound.pauseAll(p);
    if (p) showScreen('#pause'); else hideScreens();
  }

  function openSettings(from) {
    returnTo = from;
    $('#sVol').value = save.vol; $('#sMusic').value = save.music;
    document.querySelectorAll('#sFx button').forEach((b) => b.classList.toggle('sel', b.dataset.v === save.fx));
    $('#sReset').textContent = 'Erase save'; $('#sReset').dataset.confirm = '';
    showScreen('#settings');
  }

  const galleryCanvases = [];
  function openExtras() {
    const gal = $('#gallery'); gal.innerHTML = ''; galleryCanvases.length = 0;
    for (const def of CFG.monsters) {
      const item = document.createElement('div'); item.className = 'gItem';
      const cv = makeCanvas(240, 240); item.appendChild(cv);
      const txt = document.createElement('div');
      txt.innerHTML = '<div class="gName"></div><div class="gDesc"></div>';
      txt.querySelector('.gName').textContent = def.name;
      txt.querySelector('.gDesc').textContent = def.description || '';
      item.appendChild(txt); gal.appendChild(item);
      galleryCanvases.push({ cv, def });
    }
    const cl = $('#creditList'); cl.innerHTML = '';
    for (const c of (CFG.credits || [])) {
      const d = document.createElement('div');
      const b = document.createElement('b'); b.textContent = c.what; d.appendChild(b);
      d.appendChild(document.createTextNode(' — ' + c.who + (c.license ? ' (' + c.license + ')' : '')));
      if (c.url) { d.appendChild(document.createTextNode(' ')); const a = document.createElement('a'); a.href = c.url; a.target = '_blank'; a.rel = 'noopener'; a.textContent = 'source'; d.appendChild(a); }
      cl.appendChild(d);
    }
    showScreen('#extras');
  }
  function drawGallery() {
    for (const { cv, def } of galleryCanvases) {
      const x = cv.getContext('2d'), A = Art.monsters[def.id];
      x.clearRect(0, 0, cv.width, cv.height);
      const f = A.frames[Math.floor(G.t * (def.fps || 4)) % A.frames.length];
      const s = Math.min(cv.width / f.width, cv.height / f.height);
      x.drawImage(f, (cv.width - f.width * s) / 2, (cv.height - f.height * s) / 2, f.width * s, f.height * s);
    }
  }

  function openCustom() {
    const list = $('#customList'); list.innerHTML = '';
    for (const def of CFG.monsters) {
      const row = document.createElement('label'); row.className = 'row';
      const v = save.custom[def.id] != null ? save.custom[def.id] : 10;
      row.innerHTML = '<span></span><input type="range" min="0" max="20"><output></output>';
      row.querySelector('span').textContent = def.name;
      const inp = row.querySelector('input'), out = row.querySelector('output');
      inp.value = v; out.textContent = v;
      inp.addEventListener('input', () => { out.textContent = inp.value; save.custom[def.id] = parseInt(inp.value, 10); writeSave(); });
      list.appendChild(row);
    }
    showScreen('#custom');
  }

  /* ------------------------------------------------------------------ */
  /*  INPUT                                                             */
  /* ------------------------------------------------------------------ */
  const stage = $('#stage');
  let stageScale = 1, stageX = 0, stageY = 0;
  /* the size you can really see (phones report a bigger innerWidth while anything overflows) */
  function viewSize() {
    const de = document.documentElement, vv = window.visualViewport;
    if (vv && Math.abs((vv.scale || 1) - 1) < 0.01) return { w: vv.width, h: vv.height };
    return { w: de.clientWidth || window.innerWidth, h: de.clientHeight || window.innerHeight };
  }
  function layout() {
    const v = viewSize();
    stageScale = Math.min(v.w / W, v.h / H);
    stageX = (v.w - W * stageScale) / 2; stageY = (v.h - H * stageScale) / 2;
    stage.style.transform = `translate(${stageX}px, ${stageY}px) scale(${stageScale})`;
    // CSS uses this to keep text and touch targets a real-world size on small screens
    document.documentElement.style.setProperty('--scale', stageScale.toFixed(4));
  }
  window.addEventListener('resize', layout);
  window.addEventListener('orientationchange', () => setTimeout(layout, 200));
  if (window.visualViewport) visualViewport.addEventListener('resize', layout);

  function toStage(e) { return { x: (e.clientX - stageX) / stageScale, y: (e.clientY - stageY) / stageScale }; }

  /* touch: the finger that started looking around owns the view; other fingers (on buttons) can't move it */
  window.addEventListener('pointermove', (e) => {
    if (pointer.dragId != null && e.pointerId !== pointer.dragId) return;
    const p = toStage(e);
    pointer.type = e.pointerType || 'mouse';
    pointer.inside = p.x >= 0 && p.y >= 0 && p.x <= W && p.y <= H;
    if (pointer.dragId != null && G.state === 'night' && !G.cams.up && !G.paused && p.x !== pointer.lastX) {
      G.glide = null;
      G.scroll = clamp(G.scroll - (p.x - pointer.lastX) * 1.4, 0, Math.max(0, G.officeW - W));
    }
    pointer.lastX = p.x; pointer.x = p.x; pointer.y = p.y;
  });
  document.addEventListener('pointerleave', () => { pointer.inside = false; });
  window.addEventListener('blur', () => { // another window got the focus: let go of everything and pause
    pointer.inside = false; pointer.dragId = null;
    for (const k in keys) keys[k] = false;
    if (G.state === 'night') pauseGame(true);
  });

  stage.addEventListener('pointerdown', (e) => {
    if (pointer.dragId != null && e.pointerId !== pointer.dragId) return;
    const p = toStage(e);
    pointer.type = e.pointerType || 'mouse';
    pointer.x = p.x; pointer.y = p.y; pointer.lastX = p.x;
    if (e.target.closest('button, input, label, textarea, a')) return;
    if (G.state === 'night' && !G.paused) {
      if (DEV && G.cams.up && G.devGhost) { devPlace(p); return; }
      if (DEV && !G.cams.up) devOfficeClick(p);
      if (pointer.type !== 'mouse') pointer.dragId = e.pointerId;
    }
  });
  const endDrag = (e) => { if (e.pointerId === pointer.dragId) pointer.dragId = null; };
  window.addEventListener('pointerup', endDrag);
  window.addEventListener('pointercancel', endDrag);
  stage.addEventListener('wheel', (e) => {
    if (DEV && G.devGhost && G.cams.up) { e.preventDefault(); devScale(e.deltaY < 0 ? 1.04 : 1 / 1.04); }
  }, { passive: false });

  window.addEventListener('keydown', (e) => {
    if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
    const k = e.key;
    if (k === 'ArrowLeft' || k === 'ArrowRight') { keys[k] = true; e.preventDefault(); }
    const playing = G.state === 'night' && !G.paused;
    if ((k === ' ' || k === 'Spacebar') && (playing || G.state === 'boot')) e.preventDefault(); // elsewhere Space presses buttons
    if (e.repeat) return;
    if (G.state === 'boot' && (k === 'Enter' || k === ' ')) { bootGo(); return; }
    if (G.state === 'card' && (k === 'Enter' || k === ' ' || k === 'Escape')) return;
    if (k === 'Escape' || k === 'p' || k === 'P') {
      // a sub-screen (even one opened from Pause) goes back first; only then does Esc pause/resume
      if (['#settings', '#extras', '#custom'].some((s) => !$(s).classList.contains('hidden'))) backFromSub();
      else if (G.state === 'night') pauseGame(!G.paused);
      return;
    }
    if (DEV && playing && k === 'Tab') { e.preventDefault(); devKey('tab'); return; }
    if (!playing) return;
    const lk = k.toLowerCase();
    if (lk === 'q') setDoor('left', !G.doors.left.closed);
    else if (lk === 'e') setDoor('right', !G.doors.right.closed);
    else if (lk === 'a') setLight('left', !G.doors.left.light);
    else if (lk === 'd') setLight('right', !G.doors.right.light);
    else if (k === ' ' || lk === 's' || k === 'ArrowUp' || k === 'ArrowDown') toggleCams(k === 'ArrowUp' ? true : k === 'ArrowDown' ? false : null);
    else if (lk === 'f') pinch();
    else if (/^[1-9]$/.test(k)) { const c = CFG.cameras[parseInt(k, 10) - 1]; if (c) { if (!G.cams.up) toggleCams(true); switchCam(c.id); } }
    else if (DEV) devKey(lk);
  });
  window.addEventListener('keyup', (e) => { keys[e.key] = false; });

  document.addEventListener('visibilitychange', () => { if (document.hidden && G.state === 'night') pauseGame(true); });

  function bind(sel, fn) {
    $(sel).addEventListener('click', (e) => { e.preventDefault(); Sound.play('ui_click', { vol: 0.45 }); fn(e); });
  }
  // HUD buttons respond on pointerdown so they feel instant (and work while the other hand pans)
  function bindHud(sel, fn) { $(sel).addEventListener('pointerdown', (e) => { e.preventDefault(); e.stopPropagation(); fn(); }); }
  bindHud('#btnLDoor', () => setDoor('left', !G.doors.left.closed));
  bindHud('#btnRDoor', () => setDoor('right', !G.doors.right.closed));
  bindHud('#btnLLight', () => setLight('left', !G.doors.left.light));
  bindHud('#btnRLight', () => setLight('right', !G.doors.right.light));
  bindHud('#camBar', () => toggleCams(null));
  bindHud('#pinchBtn', () => pinch());
  bindHud('#voiceSkip', () => endVoice());
  bindHud('#pauseBtn', () => pauseGame(true));

  bind('#mContinue', () => startNight(save.night, false));
  bind('#mNew', () => {
    const b = $('#mNew');
    if (save.night > 1 && !b.dataset.confirm) { b.dataset.confirm = '1'; b.innerHTML = `New Dream <em>— forget your progress? ${TAP} again</em>`; return; }
    save.night = 1; writeSave(); startNight(1, false);
  });
  bind('#mEndless', () => { if (endlessUnlocked()) openCustom(); });
  bind('#mExtras', () => openExtras());
  bind('#mSettings', () => openSettings('#menu'));
  bind('#pResume', () => pauseGame(false));
  bind('#pSettings', () => openSettings('#pause'));
  bind('#pQuit', () => goMenu());
  bind('#sBack', () => backFromSub());
  bind('#xBack', () => backFromSub());
  bind('#cBack', () => backFromSub());
  bind('#cGo', () => { if (endlessUnlocked()) startNight(NIGHTS, true); });
  bind('#dRetry', () => startNight(G.night, G.endless));
  bind('#dMenu', () => goMenu());
  bind('#wNext', () => { if (G.endless || G.night >= NIGHTS) goMenu(); else startNight(G.night + 1, false); });
  bind('#wMenu', () => goMenu());
  bind('#sFull', () => {
    const d = document, el = d.documentElement;
    if (d.fullscreenElement || d.webkitFullscreenElement) (d.exitFullscreen || d.webkitExitFullscreen).call(d);
    else if (el.requestFullscreen || el.webkitRequestFullscreen) (el.requestFullscreen || el.webkitRequestFullscreen).call(el);
  });
  bind('#sReset', () => {
    const b = $('#sReset');
    if (!b.dataset.confirm) { b.dataset.confirm = '1'; b.textContent = `Really erase? ${TAP === 'tap' ? 'Tap' : 'Click'} again`; return; }
    save.night = 1; save.beaten = 0; save.custom = {}; writeSave();
    b.textContent = 'Save erased'; b.dataset.confirm = '';
  });
  $('#sVol').addEventListener('input', (e) => { save.vol = parseInt(e.target.value, 10); Sound.applyVolumes(); writeSave(); });
  $('#sMusic').addEventListener('input', (e) => { save.music = parseInt(e.target.value, 10); Sound.applyVolumes(); writeSave(); });
  document.querySelectorAll('#sFx button').forEach((b) => b.addEventListener('click', () => {
    save.fx = b.dataset.v; writeSave(); applyFxSetting();
    document.querySelectorAll('#sFx button').forEach((x) => x.classList.toggle('sel', x === b));
  }));

  function backFromSub() {
    if (returnTo === '#pause' && G.state === 'night') { showScreen('#pause'); returnTo = '#menu'; return; }
    returnTo = '#menu';
    refreshMenu(); showScreen('#menu');
  }

  /* ------------------------------------------------------------------ */
  /*  ART HELPER (dev mode: open index.html?dev)                        */
  /* ------------------------------------------------------------------ */
  /* which monster the art helper works on (Tab switches) */
  const devMonDef = () => CFG.monsters[G.devMon % Math.max(1, CFG.monsters.length)];
  const devMon = () => G.monsters.find((m) => m.def === devMonDef());

  function updateDev() {
    const el = hudEls.dev;
    if (el.classList.contains('hidden')) show(el);
    if (el.querySelector('textarea') && document.activeElement === el.querySelector('textarea')) return;
    const def = devMonDef();
    const ms = G.monsters.map((m) => `${m.def === def ? '▸ ' : '  '}${m.def.name}: ${m.state}${m.room ? ' @' + m.room : ''}${m.door ? ' @door:' + m.door : ''} lvl ${m.lvl} next ${m.timer.toFixed(1)}s${m.state === 'door' ? ' wait ' + Math.max(0, m.linger).toFixed(1) : ''}`).join('\n');
    const pose = G.devPose ? `\n\n${G.devPoseLabel}:\n<textarea readonly>${escapeHtml(G.devPose)}</textarea>` : '';
    const warn = configWarnings.length ? '\n\nCONFIG.JS WARNINGS:\n' + configWarnings.map((w) => '• ' + w).join('\n') : '';
    const html = escapeHtml(`ART HELPER (dev mode)   monster: ${def ? def.name : '-'}  (Tab: next monster)\n` +
      `T: time x${G.timeScale}  N: skip to 5:59  K: test jumpscare  M: move now\n` +
      `Z/X: put monster at left/right door  L: lucidity 5%  G: ghost placer (${G.devGhost ? 'ON' : 'off'})\n` +
      (G.devGhost ? 'Ghost placer: open cameras, CLICK where its feet go, scroll wheel / +/- to resize, R to flip\n' : '') +
      `night ${G.night}  t ${G.nightT.toFixed(1)}s  luc ${G.luc.toFixed(1)}  usage ${G.usage}  danger ${G.danger.toFixed(2)}\n${ms}`) + pose + escapeHtml(warn);
    if (el._last !== html) { el._last = html; el.innerHTML = html; }
  }
  function devKey(k) {
    const m = devMon();
    if (k === 'tab' && CFG.monsters.length) { G.devMon = (G.devMon + 1) % CFG.monsters.length; G.devPose = null; hudEls.dev._last = ''; }
    if (k === 't') G.timeScale = G.timeScale === 1 ? 10 : G.timeScale === 10 ? 40 : 1;
    if (k === 'n') G.nightT = 6 * (CFG.hourSeconds || 75) - 2;
    if (k === 'k' && m) jumpscare(m);
    if (k === 'm') for (const mm of G.monsters) monsterMove(mm, true);
    if (k === 'l') G.luc = 5;
    if ((k === 'z' || k === 'x') && m) { m.state = 'door'; m.door = k === 'z' ? 'left' : 'right'; m.room = null; m.linger = 999; m.seen = false; }
    if (k === 'g') { G.devGhost = !G.devGhost; G.grace = G.devGhost ? 1e9 : 0; }
    if (G.devGhost && (k === '+' || k === '=')) devScale(1.05);
    if (G.devGhost && (k === '-' || k === '_')) devScale(1 / 1.05);
    if (G.devGhost && k === 'r') { const p = devPoseObj(); p.flip = !p.flip; devWrite(); }
  }
  function devPoseObj() {
    const def = devMonDef(); def.poses = def.poses || {};
    return (def.poses[G.cams.cur] = def.poses[G.cams.cur] || { x: 0.5, y: 1.02, h: 0.7 });
  }
  function devWrite() {
    const p = devPoseObj();
    G.devPoseLabel = `Paste into config.js (monster "${devMonDef().id}", under poses)`;
    G.devPose = `${G.cams.cur}: { x: ${p.x.toFixed(2)}, y: ${p.y.toFixed(2)}, h: ${p.h.toFixed(2)}${p.flip ? ', flip: true' : ''} },`;
    hudEls.dev._last = '';
  }
  function devPlace(p) {
    const box = camFeedBox();
    const pose = devPoseObj();
    pose.x = clamp((p.x - box.x) / box.w, -0.5, 1.5); pose.y = clamp((p.y - box.y) / box.h, -0.5, 2);
    devWrite();
  }
  function devScale(f) { const p = devPoseObj(); p.h = clamp(p.h * f, 0.05, 3); devWrite(); }
  function devOfficeClick(p) {
    const ox = officeOriginX();
    const nx = (p.x - ox) / G.officeW, ny = p.y / H;
    G.devPoseLabel = 'That spot in your desk room picture';
    G.devPose = `x: ${nx.toFixed(3)}, y: ${ny.toFixed(3)}`;
    hudEls.dev._last = '';
  }

  /* ------------------------------------------------------------------ */
  /*  BOOT + LOOP                                                       */
  /* ------------------------------------------------------------------ */
  let last = performance.now();
  let loggedError = false;
  function frame(now) {
    requestAnimationFrame(frame);           // keep going even if one frame fails
    const dt = clamp((now - last) / 1000, 0, 0.05);
    last = now;
    try {
      update(dt);
      if (G.ready || G.state !== 'boot') render();
      if (!$('#extras').classList.contains('hidden')) drawGallery();
    } catch (err) {
      if (!loggedError) { loggedError = true; console.error(err); }
    }
  }

  function bootGo() {
    if (G.state !== 'boot' || !G.ready) return;
    Sound.unlock();
    goMenu();
  }

  async function boot() {
    loadSave();
    layout();
    $('#bootTitle').textContent = CFG.title || 'UNTIL THE ALARM';
    Sound.init();
    initMotes();
    let done = 0, total = 1;
    const tick = () => { done++; $('#loadFill').style.width = Math.min(100, (done / total) * 100) + '%'; };
    // fonts first so the stand-in art can use them
    const fontLoads = ['48px "Fell SC"', '20px "Fell"', '20px VT323', '20px "Special Elite"', '20px Eater'].map((f) => document.fonts ? document.fonts.load(f).catch(() => {}) : Promise.resolve());
    await Promise.race([Promise.all(fontLoads), new Promise((r) => setTimeout(r, 3000))]);
    total = CFG.cameras.length + 1 + 6 + CFG.monsters.reduce((a, m) => a + (m.frames || []).length + (m.jumpscareFrames || []).length, 0) + Object.keys(CFG.sounds || {}).length;
    const soundP = Sound.load(tick);
    await loadArt(tick);
    $('#bootMsg').textContent = 'listening for the dream…';
    await Promise.race([soundP, new Promise((r) => setTimeout(r, 9000))]);
    $('#loadFill').style.width = '100%';
    buildCamMap(); updateCamUi();
    G.ready = true;
    $('#bootMsg').textContent = DEV ? devBootNote() : '';
    $('#bootGo').textContent = TAP + ' to fall asleep';
    show($('#bootGo'));
    $('#boot').addEventListener('click', bootGo);
    if (DEV) console.log('[dev] art helper on. Missing art:', { office: Art.officeMissing, cams: Art.camMissing }, 'missing sounds:', Array.from(Sound.missing));
  }
  /* sound slots the game copes without (each one has a stand-in sound) */
  const OPTIONAL_SOUNDS = ['clock_tick', 'type_key', 'reality_snap', 'redhorn_click', 'door_strain', 'hypnic_jolt', 'water_drip'];
  function devBootNote() {
    const miss = Array.from(Sound.missing), must = miss.filter((n) => OPTIONAL_SOUNDS.indexOf(n) < 0);
    const parts = [];
    if (must.length) parts.push(must.length + ' sound file(s) missing: ' + must.join(', '));
    if (miss.length > must.length) parts.push((miss.length - must.length) + ' optional sound(s) not added yet');
    if (configWarnings.length) parts.push(configWarnings.length + ' config.js warning(s), see the art-helper box');
    return parts.length ? '(' + parts.join(' · ') + ')' : '';
  }

  /* for testers and bots: drive the game from the browser console */
  window.__game = {
    G, Sound, Art, CFG, startNight, beginNight, goMenu, pauseGame, monsterMove, jumpscare, win, powerOutStart,
    setDoor, setLight, toggleCams, switchCam, pinch, enterOffice, layout,
    after, cue, hit, rule, fxMul, doorDist, doorSide, calm, arrive, stepToward, spawnParts,
    tinted, ghostOf, drawEyelids, numify, configWarnings,
  };
  requestAnimationFrame((t) => { last = t; requestAnimationFrame(frame); });
  boot();
})();
