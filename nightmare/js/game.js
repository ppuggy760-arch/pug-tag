/* =====================================================================
   UNTIL THE ALARM — game engine
   You normally don't need to touch this file: pictures, monsters,
   rooms, sounds and text all live in js/config.js.
   ===================================================================== */
(function () {
  'use strict';

  const CFG = window.GAME_CONFIG;
  if (!CFG || typeof CFG !== 'object') return; // config.js has a mistake: index.html already says where (see #oops)
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
  /* captions: Sound captions on/off (on by default on touch screens, whose one speaker can't tell left from right).
     scare: 'normal' or 'gentle' (softer, quieter jumpscares for younger dreamers; the nights are just as hard).
     hints: lessons the game has already taught (it never repeats them). tutorialDone: the first-night lesson is
     over (finished or skipped). deaths: deaths per night since you last woke up from it ("Dream lighter" after 3).
     met: the monsters you have really seen in the dream (Extras keeps the others a secret: see meet). */
  const save = { night: 1, beaten: 0, vol: 85, music: 70, fx: 'full', custom: {}, captions: null, scare: 'normal', hints: {}, tutorialDone: null, deaths: {}, met: {} };
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
    // a hand-edited or broken save can't break the sound or the Endless sliders
    const num = (v, d) => (isFinite(parseFloat(v)) ? parseFloat(v) : d);
    save.vol = clamp(num(save.vol, 85), 0, 100); save.music = clamp(num(save.music, 70), 0, 100);
    if (!save.custom || typeof save.custom !== 'object' || Array.isArray(save.custom)) save.custom = {};
    for (const k of Object.keys(save.custom)) {
      const v = parseInt(save.custom[k], 10);
      if (isNaN(v)) delete save.custom[k]; else save.custom[k] = clamp(v, 0, 20);
    }
    if (typeof save.captions !== 'boolean') save.captions = TOUCH;
    if (save.scare !== 'gentle') save.scare = 'normal';
    if (!save.hints || typeof save.hints !== 'object') save.hints = {};
    if (typeof save.tutorialDone !== 'boolean') save.tutorialDone = save.beaten > 0; // (an older save that already beat a night skips it)
    if (!save.deaths || typeof save.deaths !== 'object') save.deaths = {};
    if (!stored || !stored.met || typeof stored.met !== 'object' || Array.isArray(stored.met)) {
      save.met = {};
      // a save from before Extras kept monsters a secret, that already beat a night: it has met every monster awake on those nights
      if (stored && save.beaten > 0) for (const m of Array.isArray(CFG.monsters) ? CFG.monsters : []) {
        if (m && m.id != null && Array.isArray(m.levels) && m.levels.slice(0, save.beaten).some((l) => +l > 0)) save.met[m.id] = true;
      }
    }
    applyFxSetting();
  }
  function writeSave() { try { localStorage.setItem(SAVE_KEY, JSON.stringify(save)); } catch (e) { /* ignore */ } }

  /* "Dream effects" setting as a number: Full 1, Low .4, Off 0. Multiply anything flashy or moving by it. */
  const fxMul = () => ({ full: 1, low: 0.4, off: 0 })[save.fx];
  const gentle = () => save.scare === 'gentle';
  function applyFxSetting() { document.documentElement.dataset.fx = save.fx; }

  /* ------------------------------------------------------------------ */
  /*  SOUND  (Web Audio when served from a website, plain <audio> when  */
  /*  opened straight from a file, because browsers block the former)   */
  /* ------------------------------------------------------------------ */
  const Sound = {
    defs: CFG.sounds || {},
    /* long music and ambience tracks are streamed while they play instead of being decoded up front
       (decoding all of them took about 100 MB of memory, and the game had to wait for it) */
    STREAM: ['ambience', 'menu_music', 'morning', 'music_box'],
    RANDOM_START: ['ambience', 'static'], // loops that start somewhere in the middle, so they never sound the same
    web: false, ctx: null, master: null, musicBus: null, sfxBus: null, paused: false,
    buffers: {}, pools: {}, loops: {}, missing: new Set(), loaded: 0, total: 0,
    spare: {},       // streamed tracks downloading in the background (the first loop that plays one takes it)
    media: {},       // a streamed loop's <audio> + its Web Audio input, kept for the next time the loop plays
    shots: new Set(), // streamed one-shots that are playing
    held: [],        // <audio> elements paused by the pause menu (they carry on when you resume)

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

    /* is this a long track that plays straight from its file? (very old browsers decode everything) */
    isStream(name) { return this.STREAM.indexOf(name) >= 0 && (!this.web || !!this.ctx.createMediaElementSource); },

    /* short sounds are decoded (the promise waits for them); streamed tracks only start downloading */
    load(onEach) {
      const names = Object.keys(this.defs);
      this.total = names.length;
      return Promise.all(names.map((name) => {
        const url = this.defs[name];
        const done = (ok) => { if (!ok) this.missing.add(name); this.loaded++; if (onEach) onEach(); };
        if (!url) { done(false); return Promise.resolve(); }
        if (this.isStream(name)) { // a missing file reports itself later (see _el)
          const a = this._el(name); a.load();
          if (this.web) this.spare[name] = a; else this.pools[name] = [a];
          done(true); return Promise.resolve();
        }
        if (this.web) {
          return fetch(url)
            .then((r) => { if (!r.ok) throw new Error(r.status); return r.arrayBuffer(); })
            // (newer browsers also return a promise here: catch it too, or a broken file shows up as an error)
            .then((ab) => new Promise((res, rej) => { const p = this.ctx.decodeAudioData(ab, res, rej); if (p && p.catch) p.catch(rej); }))
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
      // (iPhone/iPad, Safari 16.4+: play even with the silent switch on, like a game should)
      try { if (navigator.audioSession) navigator.audioSession.type = 'playback'; } catch (e) { /* not allowed */ }
      this.resume();
      if (!this.web) { // poke every element once (muted) so mobile browsers allow later playback
        for (const k in this.pools) for (const a of this.pools[k]) {
          a.muted = true; a.poke = true;
          // (no seeking here: rewinding an element that was just paused made its first real play stall after 0.2 s)
          const done = () => { a.muted = false; if (a.poke) { a.poke = false; a.pause(); } };
          const p = a.play();
          if (p && p.then) p.then(done, done); else done();
        }
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
    has(name) {
      if (!name || this.missing.has(name)) return false;
      return this.web ? !!this.buffers[name] || (this.isStream(name) && !!this.defs[name]) : !!this.defs[name];
    },
    /* play the first sound in the list that exists, e.g. playAny(['reality_snap', 'ui_click']) */
    playAny(names, opts) { for (const n of names) if (this.has(n)) return this.play(n, opts); return null; },

    /* a backwards copy of a sound (Web Audio only; null when opened from a file or for a streamed track) */
    reversed(name) {
      if (!this.web || !this.has(name) || !this.buffers[name]) return null;
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

    /* Web Audio: src -> (lowpass) -> (pan) -> gain -> the music or sound-effects bus */
    _chain(src, lowpass, pan, vol, music) {
      const c = this.ctx;
      let node = src, f = null, p = null;
      if (lowpass != null) { f = c.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = lowpass; node.connect(f); node = f; }
      if (pan != null && c.createStereoPanner) { p = c.createStereoPanner(); p.pan.value = clamp(pan, -1, 1); node.connect(p); node = p; }
      const g = c.createGain(); g.gain.value = vol;
      node.connect(g); g.connect(music ? this.musicBus : this.sfxBus);
      return { f, pan: p, g };
    },
    /* a streamed track's <audio>, wired into Web Audio (that can only be done once per element) */
    _mediaIn(name) {
      const el = this.spare[name] || this._el(name);
      delete this.spare[name];
      return { el, src: this.ctx.createMediaElementSource(el), sound: name };
    },
    _playEl(el) { const pr = el.play(); if (pr && pr.catch) pr.catch(() => {}); },

    /* one-shot sound. opts: vol, rate, pan (-1..1), lowpass (Hz), music.
       Returns a handle { stop(fade), gain, filter, src } (Web Audio) or { stop, el } (file mode), or null. */
    play(name, opts) {
      if (!this.has(name)) return null;
      const o = Object.assign({ vol: 1, rate: 1, pan: 0, lowpass: 0, music: false }, opts || {});
      if (this.web) {
        const c = this.ctx, buf = this.buffers[name];
        let src, el = null;
        if (buf) { src = c.createBufferSource(); src.buffer = buf; src.playbackRate.value = o.rate; } else { // streamed
          el = this._el(name); el.playbackRate = o.rate; src = c.createMediaElementSource(el);
          this.shots.add(el); el.addEventListener('ended', () => { this.shots.delete(el); src.disconnect(); }, { once: true });
        }
        const ch = this._chain(src, o.lowpass || null, o.pan || null, o.vol, o.music);
        if (el) this._playEl(el); else src.start();
        const shots = this.shots;
        return {
          src, gain: ch.g, filter: ch.f,
          stop(fade) {
            const f = fade || 0.05;
            try { ch.g.gain.setTargetAtTime(0, c.currentTime, f / 3); if (el) setTimeout(() => { el.pause(); shots.delete(el); }, (f + 0.05) * 1000); else src.stop(c.currentTime + f + 0.05); } catch (e) { /* already stopped */ }
          },
        };
      }
      const pool = this.pools[name] || (this.pools[name] = []);
      let a = pool.find((x) => x.paused || x.ended);
      if (!a) {
        if (pool.length < 4) { a = this._el(name); pool.push(a); } else { a = pool.shift(); pool.push(a); }
      }
      try { a.currentTime = 0; } catch (e) { /* not ready */ }
      a.poke = false; a.muted = false; // (a real play: unlock's poke must not pause it)
      a.loop = false; a.playbackRate = o.rate; a.volume = this._htmlVol(o.vol, o.music);
      this._playEl(a);
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
    /* stop a loop right now, with no fade (stopLoop's fade needs the frame loop, which a hidden tab doesn't run) */
    cutLoop(key) { const L = this.loops[key]; if (L) { L.target = 0; L.vol = 0; this._stopH(L); } },
    killLoops() { for (const k in this.loops) this.cutLoop(k); },
    stopAll() {
      this.killLoops();
      this.paused = false; this.held = [];
      for (const a of this.shots) a.pause();
      this.shots.clear();
      if (!this.web) for (const k in this.pools) for (const a of this.pools[k]) { try { a.pause(); } catch (e) { /* ignore */ } }
      else if (this.ctx) { // swap the sfx bus so every playing one-shot is cut
        try { this.sfxBus.disconnect(); } catch (e) { /* ignore */ }
        this.sfxBus = this.ctx.createGain(); this.sfxBus.connect(this.master);
      }
    },
    _tune(L) {
      if (!L.h) return;
      if (L.h.el) L.h.el.playbackRate = L.rate; else L.h.src.playbackRate.value = L.rate;
      if (this.web) {
        if (L.h.pan) L.h.pan.pan.value = clamp(L.pan, -1, 1);
        if (L.h.f) L.h.f.frequency.setTargetAtTime(L.lp || 20000, this.ctx.currentTime, 0.1);
      }
    },
    _startH(L) {
      if (!this.has(L.sound)) return;
      const random = this.RANDOM_START.indexOf(L.sound) >= 0;
      if (this.web) {
        const buf = this.buffers[L.sound];
        let src, el = null;
        if (buf) { src = this.ctx.createBufferSource(); src.buffer = buf; src.loop = true; src.playbackRate.value = L.rate; } else {
          let M = this.media[L.key]; // streamed: the same <audio> every time this loop plays (it carries on where it stopped)
          if (!M || M.sound !== L.sound) {
            M = this.media[L.key] = this._mediaIn(L.sound);
            if (random) { const el0 = M.el, seek = () => { try { el0.currentTime = Math.random() * Math.max(0, el0.duration - 0.1); } catch (e) { /* not seekable */ } };
              if (isFinite(el0.duration)) seek(); else el0.addEventListener('loadedmetadata', seek, { once: true }); }
          }
          el = M.el; src = M.src; el.loop = true; el.playbackRate = L.rate;
        }
        const ch = this._chain(src, L.filt ? (L.lp || 20000) : null, L.pan, 0, L.music);
        if (el) this._playEl(el); else src.start(0, random ? Math.random() * Math.max(0, buf.duration - 0.1) : 0);
        L.h = { src, el, g: ch.g, pan: ch.pan, f: ch.f };
      } else {
        const el = this._el(L.sound); el.loop = true; el.volume = 0; el.playbackRate = L.rate;
        this._playEl(el);
        L.h = { el };
      }
    },
    _stopH(L) {
      if (!L.h) return;
      try {
        if (!this.web) L.h.el.pause();
        else if (L.h.el) { L.h.el.pause(); L.h.src.disconnect(); L.h.g.disconnect(); } // (kept, see media)
        else L.h.src.stop();
      } catch (e) { /* ignore */ }
      L.h = null;
    },
    update(dt) {
      if (this.paused) return; // nothing fades or starts while the game is paused
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
    /* the pause menu: everything holds its breath and carries on from the same spot afterwards.
       Web Audio stops its clock; plain <audio> elements (file mode, streamed tracks) are paused one by one. */
    pauseAll(p) {
      if (p === this.paused) return;
      this.paused = p;
      if (p) {
        const els = [...this.shots];
        for (const k in this.loops) if (this.loops[k].h && this.loops[k].h.el) els.push(this.loops[k].h.el);
        if (!this.web) for (const k in this.pools) els.push(...this.pools[k]);
        this.held = els.filter((a) => !a.paused && !a.ended);
        for (const a of this.held) a.pause();
      } else {
        for (const a of this.held) this._playEl(a);
        this.held = [];
      }
      if (this.web && this.ctx) { if (p) this.ctx.suspend().catch(() => {}); else this.ctx.resume().catch(() => {}); }
    },
  };

  /* ------------------------------------------------------------------ */
  /*  CONFIG CHECK: fix capital letters quietly, warn about real typos   */
  /*  (warnings go to the console and to the ?dev art-helper panel)      */
  /* ------------------------------------------------------------------ */
  const configWarnings = [];
  function warnCfg(msg) {
    configWarnings.push(msg); console.warn('[config.js] ' + msg);
    if (window.__oopsWarn) window.__oopsWarn.push(msg); // (shown too if something then stops the game from starting)
  }
  const TOP_KEYS = ['title', 'subtitle', 'hourSeconds', 'lucidityDrain', 'endlessDrain', 'nights', 'endlessRules', 'pinch',
    'doorStrain', 'lies', 'minWarning', 'office', 'cameras', 'monsters', 'sounds', 'captions', 'dreamVoice', 'credits', 'bedroom',
    'fallAsleep', 'morning', 'finale', 'director', 'youCam', 'tutorial'];
  /* the words a first-night lesson step can wait for (plus cam:<id> and time:N), and what its ring can go around */
  const LESSON_WAITS = ['lookLeft', 'lookRight', 'light', 'cams', 'door', 'doorOpen', 'pinch'];
  const LESSON_POINTS = ['left', 'right', 'leftLight', 'rightLight', 'leftDoor', 'rightDoor', 'cameras', 'pinch', 'lucidity', 'clock', 'none'];
  const MONSTER_KEYS = ['id', 'name', 'description', 'behavior', 'color', 'frames', 'sleepFrames', 'fps', 'jumpscareFrames', 'jumpscareFps', 'jumpscareFocus',
    'jumpscareSound', 'presenceSound', 'sounds', 'levels', 'hourBoost', 'moveEvery', 'waitAtDoor', 'start', 'path', 'retreat', 'poses', 'doorPose'];
  const CAMERA_KEYS = ['id', 'label', 'name', 'dreamName', 'image', 'map', 'sound', 'soundVol'];
  const CUE_KINDS = ['steps', 'breath', 'bang', 'far', 'whisper']; // what a monster's own sounds: { … } can change
  /* a sound name used somewhere in config.js must be one of the sounds: */
  function checkSoundName(name, where) {
    if (name && CFG.sounds && !CFG.sounds[name]) warnCfg(`${where}: there is no sound called "${name}" in sounds.`);
  }
  /* an unknown key is only reported when it looks like a misspelt known one */
  function checkKeys(obj, known, where) {
    for (const k in obj) {
      if (known.indexOf(k) >= 0) continue;
      const g = didYouMean(k, known);
      if (g) warnCfg(`${where}"${k}" isn't a setting the game knows. Did you mean "${g}"?`);
    }
  }

  /* a number setting ("5" in quotes works too). Anything else is reported and gets the default. */
  function numCfg(obj, key, dflt, where, min, max) {
    if (obj[key] == null) return;
    const v = Number(obj[key]);
    if (isFinite(v)) { obj[key] = clamp(v, min, max); return; }
    warnCfg(`${where}${key}: "${obj[key]}" isn't a number, so the game uses ${dflt}.`);
    obj[key] = dflt;
  }

  /* "a, , b" or a stray value in a list: keep only the real { … } blocks */
  function onlyBlocks(list, what) {
    if (!Array.isArray(list)) return list;
    const out = list.filter((x) => x && typeof x === 'object');
    if (out.length !== list.length) warnCfg(`${what}: there is an extra comma or an empty spot in the list. The game skipped it.`);
    return out;
  }

  function validateConfig() {
    checkKeys(CFG, TOP_KEYS, '');
    numCfg(CFG, 'hourSeconds', 75, '', 5, 3600);
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
      c.name = String(c.name);
      checkKeys(c, CAMERA_KEYS, `cameras: "${c.id}": `);
      if (!c.map || typeof c.map.x !== 'number' || typeof c.map.y !== 'number') {
        // (it still gets a button: spread out along the bottom of the map, so the buttons never sit on top of each other)
        c.map = { x: 0.1 + 0.8 * (i % 5) / 4, y: 0.9 - 0.12 * Math.floor(i / 5) };
        warnCfg(`cameras: "${c.id}" needs map: { x: …, y: … } (where its button sits on the camera map). For now it sits at the bottom.`);
      }
      checkSoundName(c.sound, `cameras: "${c.id}" sound`);
    });
    const ids = CFG.cameras.map((c) => c.id), byLower = {};
    ids.forEach((id) => { byLower[id.toLowerCase()] = id; });
    /* a room name: capital letters are fixed quietly; a small typo uses the closest room (and says so) */
    const fixRoom = (name, where, allowDoor) => {
      const s = String(name).trim();
      if (allowDoor && /^door\s*:\s*(left|right)$/i.test(s)) return s.replace(/\s+/g, '').toLowerCase(); // ("door: Right" works too)
      if (byLower[s.toLowerCase()]) return byLower[s.toLowerCase()];
      const g = didYouMean(s, allowDoor ? ids.concat(['door:left', 'door:right']) : ids);
      warnCfg(`${where}: room "${s}" doesn't exist` + (g ? `. Did you mean "${g}"? (Using "${g}" for now.)` : `. The rooms are: ${ids.join(', ')}.`));
      return g;
    };

    if (!Array.isArray(CFG.monsters)) { warnCfg('monsters: this should be a list [ … ].'); CFG.monsters = []; }
    const monIds = {};
    CFG.monsters.forEach((m, i) => {
      if (!m.id) { m.id = 'monster' + (i + 1); warnCfg(`monsters: monster number ${i + 1} has no id, so it is called "${m.id}".`); }
      m.id = String(m.id);
      if (monIds[m.id]) { // (a copied block: each monster needs its own pictures, so it gets its own id for now)
        const was = m.id; m.id = was + '_' + (i + 1);
        warnCfg(`monsters: two monsters are both called "${was}". Give each one its own id (for now the second one is "${m.id}").`);
      }
      monIds[m.id] = true;
      if (!m.name) m.name = m.id;
      const who = m.name;
      checkKeys(m, MONSTER_KEYS, who + ': ');
      for (const k of ['frames', 'jumpscareFrames', 'sleepFrames']) {
        if (m[k] != null && !Array.isArray(m[k])) { warnCfg(`${who} ${k}: write it as a list of pictures, like ["assets/monsters/${m.id}/frame1.png"].`); m[k] = null; }
      }
      if (!m.frames) m.frames = [];
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
      for (const [k, P] of Object.entries(m.poses).concat(Object.entries(m.doorPose || {}))) {
        if (!P || typeof P !== 'object' || ['x', 'y', 'h'].some((q) => P[q] != null && !isFinite(+P[q]))) {
          warnCfg(`${who} pose for "${k}": write it like { x: 0.5, y: 1.0, h: 0.7 }.`);
          if (m.poses[k] === P) delete m.poses[k]; else delete m.doorPose[k];
        }
      }
      numCfg(m, 'fps', 4, who + ' ', 0.5, 60);
      numCfg(m, 'jumpscareFps', 14, who + ' ', 1, 60);
      numCfg(m, 'moveEvery', 5, who + ' ', 0.5, 120);
      // waitAtDoor: two numbers [shortest, longest] (one number works too)
      const wa = [].concat(m.waitAtDoor == null ? [4, 7] : m.waitAtDoor).map(Number);
      if (!wa.length || wa.length > 2 || wa.some((v) => !isFinite(v))) { warnCfg(`${who} waitAtDoor: write it as two numbers, like [3.5, 7].`); m.waitAtDoor = [4, 7]; }
      else m.waitAtDoor = [Math.max(0, wa[0]), Math.max(0, wa[wa.length - 1])].sort((a, b) => a - b);
      if (m.levels != null && (!Array.isArray(m.levels) || !m.levels.length)) { warnCfg(`${who} levels: write one number per night, like [3, 6, 9, 12, 16].`); m.levels = null; }
      if (m.levels) m.levels = m.levels.map((v, n) => { const x = Number(v); if (isFinite(x)) return clamp(x, 0, 20); warnCfg(`${who} levels: the number for night ${n + 1} ("${v}") isn't a number, so it is 5.`); return 5; });
      for (const h in (m.hourBoost || {})) { const x = Number(m.hourBoost[h]); if (!isFinite(x)) { warnCfg(`${who} hourBoost: "${m.hourBoost[h]}" at ${h} AM isn't a number.`); delete m.hourBoost[h]; } else m.hourBoost[h] = x; }
      const f = m.jumpscareFocus;
      if (f != null && (typeof f !== 'object' || !isFinite(+f.x) || !isFinite(+f.y))) { warnCfg(`${who} jumpscareFocus: write it like { x: 0.5, y: 0.2 }.`); m.jumpscareFocus = null; }
      checkSoundName(m.jumpscareSound, who + ' jumpscareSound');
      checkSoundName(m.presenceSound, who + ' presenceSound');
      if (m.sounds && typeof m.sounds === 'object') {
        checkKeys(m.sounds, CUE_KINDS, who + ' sounds: ');
        for (const k of CUE_KINDS) checkSoundName(m.sounds[k], `${who} sounds.${k}`);
      }
      if (m.behavior != null) m.behavior = String(m.behavior).trim().toLowerCase(); // (checked once the brains exist, see validateBrains)
    });

    if (!CFG.office || typeof CFG.office !== 'object') { if (CFG.office != null) warnCfg('office: this should be a { … } block.'); CFG.office = {}; }
    if (!CFG.office.doors || typeof CFG.office.doors !== 'object') CFG.office.doors = {};
    const doors = CFG.office.doors;
    for (const side of ['left', 'right']) {
      const d = doors[side];
      if (!d || ['x', 'y', 'w', 'h'].some((k) => typeof d[k] !== 'number')) {
        warnCfg(`office.doors.${side} needs x, y, w and h numbers. Using the built-in spot for now.`);
        doors[side] = Object.assign({}, d || {}, { x: side === 'left' ? 0.03 : 0.82, y: 0.178, w: 0.15, h: 0.7 });
      }
    }
    if (CFG.nights != null && !Array.isArray(CFG.nights)) { warnCfg('nights: this should be a list of 5 { … } blocks.'); CFG.nights = null; }
    for (const k in (CFG.sounds || {})) if (typeof CFG.sounds[k] !== 'string') warnCfg(`sounds.${k}: write the file path in quotes, like "assets/audio/${k}.mp3".`);
    checkTutorial(ids);
  }
  /* the first-night lesson's steps: a wait or point word the game doesn't know is reported (did you mean …?) */
  function checkTutorial(ids) {
    if (CFG.tutorial == null) return;
    if (!Array.isArray(CFG.tutorial)) { warnCfg('tutorial: this should be a list of { say: …, wait: … } steps. Using the built-in lesson.'); CFG.tutorial = null; return; }
    CFG.tutorial = onlyBlocks(CFG.tutorial, 'tutorial');
    CFG.tutorial.forEach((st, i) => {
      const where = `tutorial step ${i + 1}`, w = st.wait == null ? 'time:4' : String(st.wait);
      if (!st.say) warnCfg(`${where} has no say: "…" (what the voice says). The game skips it.`);
      if (/^cam:/.test(w)) { if (ids.indexOf(w.slice(4)) < 0) warnCfg(`${where} waits for camera "${w.slice(4)}", but there is no camera with that id. The game skips this step.`); }
      else if (!/^time:\d+(\.\d+)?$/.test(w) && LESSON_WAITS.indexOf(w) < 0) {
        const g = didYouMean(w, LESSON_WAITS);
        warnCfg(`${where}: wait "${w}" isn't something the lesson knows` + (g ? `. Did you mean "${g}"?` : `. Try one of: ${LESSON_WAITS.join(', ')}, cam:<camera id>, time:4.`));
      }
      if (st.point != null && !/^cam:/.test(st.point) && LESSON_POINTS.indexOf(st.point) < 0) {
        const g = didYouMean(st.point, LESSON_POINTS);
        warnCfg(`${where}: point "${st.point}" isn't something the ring can go around` + (g ? `. Did you mean "${g}"?` : `. Try one of: ${LESSON_POINTS.join(', ')}.`));
      }
    });
  }
  validateConfig();

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
    { drain: 0.125, stepChance: 0.5, lies: true, pinchRadius: 2, youCam: true, stare: 4, gasp: 28, doorFree: 10, falseDawn: 5.33 },
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

  /* the pinch and held-door settings with every number filled in (config.js can leave any out) */
  function pinchCfg() {
    const p = Object.assign({ amount: 3, cooldown: 60, lowBonus: 2, highPenalty: 0.25 }, CFG.pinch || {});
    p.cooldown = Math.max(1, +p.cooldown || 60);
    return p;
  }
  function strainCfg() {
    const d = Object.assign({ rampSeconds: 10, maxCost: 3, giveUpAfter: 8 }, CFG.doorStrain || {});
    d.rampSeconds = Math.max(0.1, +d.rampSeconds || 10); d.maxCost = Math.max(1, +d.maxCost || 1);
    return d;
  }
  /* the dream's lies: below `below` % Lucidity a fake can appear, one every `every` [min, max] seconds */
  function liesCfg() {
    const l = Object.assign({ below: 60, every: [35, 60] }, CFG.lies || {});
    l.below = clamp(isFinite(+l.below) ? +l.below : 60, 0, 100);
    l.every = Array.isArray(l.every) && l.every.length === 2 ? l.every.map((v) => Math.max(5, +v || 35)) : [35, 60];
    return l;
  }
  /* seconds a monster must have been breathing at your door before it can come in (config minWarning) */
  const minWarning = () => (CFG.minWarning != null && isFinite(+CFG.minWarning) ? Math.max(0, +CFG.minWarning) : 2.5);
  const hourSec = () => Math.max(5, CFG.hourSeconds || 75);

  /* ------------------------------------------------------------------ */
  /*  ART: load pictures, or use the stand-ins when they're missing     */
  /* ------------------------------------------------------------------ */
  const CAM_ZOOM = 1.14; // camera pictures are shown 14% bigger than the screen (see camFeedBox)
  /* officeMissing / camMissing / bedroomMissing: YOUR picture is missing (a stand-in shows). standIn says which:
     'photo' (the game's own picture from assets/scenes/) or 'painted' (drawn by the code), per config.js slot. */
  const Art = { office: null, officeMissing: true, doors: { left: {}, right: {} }, cams: {}, camMissing: {}, monsters: {}, noise: [], vignette: null, scan: null, dot: null,
    bedroomNight: null, bedroomBlur: [], bedroomMorning: null, bedroomMissing: true, evidence: {}, drawing: null, youCam: null,
    standIn: {}, officePhoto: false, bedroomPhoto: false, youCamPhoto: false, menu: null, clock: null, youCamChair: null, evPatch: {},
    restReady: false, bootP: null, restP: null, startRest: () => {} };

  /* THE GAME'S OWN PHOTO STAND-INS (assets/scenes/): rooms put together from lots of free photos and textures
     (wood, plaster, wallpaper, velvet, old-house photos, old paintings, the moon; see CREDITS.md and art-src/).
     One is shown only while YOUR picture for that slot is missing: draw yours into assets/rooms/ and it wins.
     If a photo is missing too, the game paints its old stand-in. (None of them has a monster in it.) */
  const SCENE_DIR = 'assets/scenes/';
  const SCENES = {
    office: 'office.jpg',
    door: (side, kind) => `door_${side}_${kind}.jpg`,              // kind: dark / lit / closed (360 x 630)
    cams: { nursery: 'cam1_nursery.jpg', hall: 'cam2_hall.jpg', parlor: 'cam3_parlor.jpg', stairs: 'cam4_stairs.jpg', west: 'cam5_west.jpg', east: 'cam6_east.jpg' },
    bedroom: 'bedroom.jpg', morning: 'bedroom_morning.jpg', youCam: 'cam7_you.jpg',
    menu: 'menu.jpg', menuLight: 'menu_light.png', menuFog: 'menu_fog.png', paper: 'paper.jpg', clock: 'clock.png',
    youCamChair: 'cam7_chair.png', evidence: (n) => `bedroom_ev${n}.jpg`,  // CAM 7's chair back (drawn over you); Nights 2 and 4's mornings
  };
  const SCENE_SEAT = { x: 0.459, y: 0.603, size: 0.47 }; // where your head goes in cam7_you.jpg (its own chair is in the picture)
  const MENU_LIGHT_BOX = { x: 712, y: 20, w: 644, h: 880 };  // the part of menu_light.png that has any light in it (kept, the rest is dropped)

  /* bust: a number added to the address so the browser fetches the file again (the art helper's U key) */
  function loadImage(url, bust) {
    return new Promise((res) => {
      if (!url) return res(null);
      const im = new Image();
      im.onload = () => res(im.naturalWidth ? im : null);
      im.onerror = () => res(null);
      im.src = bust ? url + (url.indexOf('?') < 0 ? '?' : '&') + 'v=' + bust : url;
    });
  }

  /* every picture config.js asks for: Art.files = [{ slot, path, img, w, h }] (img only in ?dev, for the art checklist).
     Two parts, so a slow connection gets to the title screen quickly:
       Art.bootP  the pictures the title screen and falling asleep need (all of YOUR pictures in assets/rooms, the monster
                  frames, the menu photo, the paper and the night bedroom). The boot screen waits for these.
       Art.restP  the rest of the game's own photos (desk room, doorways, cameras, CAM 7, the morning). They are fetched
                  once Art.startRest() is called (boot calls it as soon as its own files are in; o.lazy false: at once)
                  and load behind the menu; a night waits for them with your eyes shut (Art.restReady). The returned
                  promise is the whole lot. */
  function loadArt(tick, bust, o) {
    o = o || {};
    const jobs = [], restJobs = [];
    Art.files = []; Art.standIn = {}; Art.restReady = false;
    let go; const gate = new Promise((r) => { go = r; });
    Art.startRest = () => go(true);
    if (!o.lazy) go(true);
    const job = (slot, url, opt) => {
      url = url ? String(url) : '';
      const order = jobs.length; // (the checklist lists them in config.js order, whichever loads first)
      const p = loadImage(url, bust).then((img) => {
        if (url || !opt) Art.files.push({ slot, order, path: url || '', opt: !!opt, img: DEV ? img : null, w: img ? img.naturalWidth : 0, h: img ? img.naturalHeight : 0 });
        tick(); return img;
      });
      jobs.push(p); return p;
    };
    /* one of the game's own photos (assets/scenes/), fetched only once `needed` says yes (a promise: true / false).
       later: one of the background part's (fetched after Art.startRest(), not counted on the loading bar) */
    const photo = (name, needed, later) => {
      const p = Promise.all([needed, later ? gate : true]).then(([yes]) => (yes && name ? loadImage(SCENE_DIR + name, bust) : null))
        .then((img) => { if (!later) tick(); return img; });
      (later ? restJobs : jobs).push(p); return p;
    };
    const not = (p) => Promise.resolve(p).then((img) => !img);

    // the title screen first (its photo also dims in behind the boot screen as soon as it is here)
    const menuShot = { base: photo(SCENES.menu, true), light: photo(SCENES.menuLight, true), fog: photo(SCENES.menuFog, true) };
    if (o.backdrop) menuShot.base.then((img) => { if (img) o.backdrop(img); });
    const officeP = job('office.image', CFG.office.image), officeShot = photo(SCENES.office, not(officeP), true);
    const doorP = {}, doorShot = {};
    for (const side of ['left', 'right']) {
      const d = CFG.office.doors[side], at = `office.doors.${side}.`;
      doorP[side] = { dark: job(at + 'darkImage', d.darkImage, true), lit: job(at + 'litImage', d.litImage, true), closed: job(at + 'closedImage', d.closedImage, true) };
      doorShot[side] = { // (your own desk room without a darkImage shows the doorway you painted: no dark photo then)
        dark: photo(SCENES.door(side, 'dark'), Promise.all([doorP[side].dark, officeP]).then(([a, b]) => !a && !b), true),
        lit: photo(SCENES.door(side, 'lit'), not(doorP[side].lit), true), closed: photo(SCENES.door(side, 'closed'), not(doorP[side].closed), true),
      };
    }
    const camP = {}, camShot = {};
    for (const c of CFG.cameras) { camP[c.id] = job(`camera "${c.id}"`, c.image); camShot[c.id] = photo(SCENES.cams[c.id], not(camP[c.id]), true); }
    const bed = CFG.bedroom || {};
    const bedP = { image: job('bedroom.image', bed.image), morning: job('bedroom.morningImage', bed.morningImage, true) };
    const bedShot = { night: photo(SCENES.bedroom, not(bedP.image)), morning: photo(SCENES.morning, Promise.all([bedP.image, bedP.morning]).then(([a, b]) => !a && !b), true) };
    const evP = {};
    for (const n of [2, 3, 4]) evP[n] = job(`morning.evidence ${n}`, evidenceCfg(n).image, true);
    const youP = job('youCam.image', (CFG.youCam || {}).image, true), youShot = photo(SCENES.youCam, not(youP), true); // CAM 7 (optional)
    const chairShot = photo(SCENES.youCamChair, not(youP), true);
    // the photo bedroom's mornings after Nights 2 and 4 (the closet door ajar, a scrap of collar on the floor): pieces of
    // bedroom_morning.jpg rendered with the evidence in them, laid over it (not with your own bedroom or evidence picture)
    const evShot = {};
    for (const n of [2, 4]) evShot[n] = photo(SCENES.evidence(n), Promise.all([bedP.image, bedP.morning, evP[n]]).then((a) => a.every((x) => !x)), true);
    const paperShot = photo(SCENES.paper, true); // the sheet the crayon drawing is drawn on
    const clockShot = photo(SCENES.clock, true); // the twin-bell alarm clock (a photo; the game draws its hands)
    const monP = {};
    for (const m of CFG.monsters) {
      const list = (key, what, opt) => Promise.all((m[key] || []).map((u, i) => job(`${m.name} ${what} ${i + 1}`, u, opt)));
      monP[m.id] = { frames: list('frames', 'frame'), jump: list('jumpscareFrames', 'jumpscare frame', true), sleep: list('sleepFrames', 'sleep frame', true) };
    }
    Art.total = jobs.length;
    const standIn = (slot, img) => { Art.standIn[slot] = img ? 'photo' : 'painted'; return img; };

    Art.bootP = (async () => {
      await Promise.all(jobs);
      Art.files.sort((a, b) => a.order - b.order);
      for (const m of CFG.monsters) {
        let frames = (await monP[m.id].frames).filter(Boolean);
        const missing = frames.length === 0;
        if (missing) frames = shadowFigure(m);
        let jump = (await monP[m.id].jump).filter(Boolean);
        if (!jump.length) jump = frames;
        const soft = frames.map((f) => softFrame(f, 820));
        const sleep = (await monP[m.id].sleep).filter(Boolean).map((f) => softFrame(f, 820)); // (the sleeper brain's own frames)
        Art.monsters[m.id] = { frames, jump, soft, sleep, sil: soft.map((f) => silhouette(f, '#05030a')), missing };
      }
      Art.clock = await clockShot;
      Art.drawing = paintKidDrawing(await paperShot); Art.drawingDay = null; // the crayon drawing (desk-room wall, Night 3's morning): no monster in it
      // your real bedroom: one picture, tinted dark blue for the night and warm for the morning.
      // The photo stand-in has its own night and morning pictures (already lit for the night: no dark-blue tint).
      const bedImg = await bedP.image, night = await bedShot.night;
      Art.bedroomMissing = !bedImg; Art.bedroomPhoto = !bedImg && !!standIn('bedroom.image', night);
      if (Art.bedroomPhoto) {
        Art.bedroomNight = shadeCopy(night);
        drawClockPhoto(Art.bedroomNight.getContext('2d'), 1500, TABLE_TOP - 34, 30, { h: 11, m: 59 }, NIGHT_CLOCK_LIGHT); // (the little clock on the bedside table)
      } else Art.bedroomNight = shadeCopy(bedImg || paintBedroom('night'), 'multiply', '#1a2346', 0.75);
      Art.bedroomBlur = TOUCH ? [] : bakeBlurs(Art.bedroomNight, [2, 4, 7, 10]); // (phones darken instead of blurring: no need to keep them)
      for (const n of [2, 3, 4]) Art.evidence[n] = await evP[n];
      Art.menu = menuArt(await menuShot.base, await menuShot.light, await menuShot.fog);
      paintFx();
    })();

    Art.restP = (async () => {
      await Art.bootP;
      await Promise.all(restJobs);
      const office = await officeP, officeImg = await officeShot;
      Art.officeMissing = !office; Art.officePhoto = !office && !!standIn('office.image', officeImg);
      if (office) Object.assign(Art, fitOffice(office));
      else { Art.office = Art.officePhoto ? photoOffice(officeImg) : paintOffice(); Art.officeBand = { y0: 0, k: 1 }; }
      for (const side of ['left', 'right']) {
        const own = { dark: await doorP[side].dark, lit: await doorP[side].lit, closed: await doorP[side].closed };
        const shot = { dark: await doorShot[side].dark, lit: await doorShot[side].lit, closed: await doorShot[side].closed };
        for (const k in shot) if (!own[k] && (k !== 'dark' || !office)) standIn(`office.doors.${side}.${k}Image`, shot[k]);
        // your own desk room without a darkImage: what you painted in the doorway shows (under a soft darkness, see drawDoorway)
        Art.doors[side] = { own, shot, dark: own.dark || (office ? null : fitDoor(side, shot.dark) || paintDoorway(side, false)),
          lit: own.lit || fitDoor(side, shot.lit) || paintDoorway(side, true), closed: own.closed || fitDoor(side, shot.closed) || paintShutter(side) };
      }
      for (const c of CFG.cameras) {
        const im = await camP[c.id], shot = im ? null : standIn(`camera "${c.id}"`, await camShot[c.id]);
        Art.camMissing[c.id] = !im;
        Art.cams[c.id] = im || shot ? fitPicture(im || shot, W * CAM_ZOOM, H * CAM_ZOOM) : paintRoom(c);
      }
      const bedImg = await bedP.image, bedMorning = await bedP.morning, morning = await bedShot.morning;
      if (!bedImg && !bedMorning) standIn('bedroom.morningImage', morning);
      // (no morning picture: a warmed copy of whichever bedroom the night showed)
      Art.bedroomMorning = bedMorning ? shadeCopy(bedMorning) : !bedImg && morning ? shadeCopy(morning)
        : shadeCopy(bedImg || (Art.bedroomPhoto ? await bedShot.night : null) || paintBedroom('morning'), 'overlay', '#ffb070', 0.25);
      const you = await youP, youPhoto = you ? null : standIn('youCam.image', await youShot);
      Art.youCamPhoto = !!youPhoto;
      Art.youCam = (you || youPhoto) && fitPicture(you || youPhoto, W * CAM_ZOOM, H * CAM_ZOOM);
      if (Art.youCamPhoto) Art.youCam = youCamWithDrawing(Art.youCam);
      Art.youCamChair = Art.youCamPhoto ? await chairShot : null;
      Art.evPatch = {};
      for (const n of [2, 4]) Art.evPatch[n] = Art.bedroomPhoto && !bedMorning ? await evShot[n] : null;
      Art.restReady = true;
    })();
    Art.restP.catch((err) => console.error(err));
    return Art.restP;
  }

  /* a photo doorway at exactly its door box's size: as it is when the shapes match (the built-in desk room's boxes),
     otherwise cut to fit (never stretched), keeping its floor at the bottom */
  function fitDoor(side, img) {
    if (!img) return null;
    const { w, h } = doorPx(side), a = w / h, ia = img.width / img.height;
    if (Math.abs(ia / a - 1) < 0.02) return img;
    const c = makeCanvas(w, h), sw = ia > a ? img.height * a : img.width, sh = ia > a ? img.height : img.width / a;
    c.getContext('2d').drawImage(img, (img.width - sw) / 2, img.height - sh, sw, sh, 0, 0, c.width, c.height);
    return c;
  }

  /* the title screen's hall: the picture, its door light on its own (only the part with light in it, plus a dark copy
     for the moments it sputters) and the low fog. null without the picture (then the old drifting fog shows) */
  function menuArt(base, light, fog) {
    if (!base) return null;
    let lit = null, dim = null;
    if (light) {
      const B = MENU_LIGHT_BOX, k = light.width / W;
      lit = makeCanvas(B.w, B.h);
      lit.getContext('2d').drawImage(light, B.x * k, B.y * k, B.w * k, B.h * k, 0, 0, B.w, B.h);
      dim = tinted(lit, '#05030a');
    }
    return { base, lit, dim, fog };
  }

  function officeWidthFor(img) { return img.width * (H / img.height); }

  /* ----- the desk room picture, made once at the size it is shown (big pictures are shrunk here, not every frame).
     A picture too narrow to look around in (a 4:3 or square canvas, like 2732 x 2048) is zoomed in until at most
     70% of its width fits on the screen; its top and bottom are cut off, keeping the doorways in view.
     officeBand says which part of the picture's height is shown: y0 = its top, k = its height (fractions). ----- */
  const OFFICE_MIN_W = Math.round(W / 0.7);
  function fitOffice(img) {
    const w0 = officeWidthFor(img), D = CFG.office.doors;
    let y0 = 0, k = 1;
    if (w0 < OFFICE_MIN_W) {
      k = w0 / OFFICE_MIN_W;
      const top = Math.min(D.left.y, D.right.y), bottom = Math.max(D.left.y + D.left.h, D.right.y + D.right.h);
      y0 = clamp((top + bottom) / 2 - k / 2, 0, 1 - k);
    }
    if (k === 1 && img.height === H) return { office: img, officeBand: { y0, k } };
    const c = makeCanvas(w0 / k, H);
    c.getContext('2d').drawImage(img, 0, y0 * img.height, img.width, k * img.height, 0, 0, c.width, H);
    return { office: c, officeBand: { y0, k } };
  }
  /* a box or spot from config.js (fractions of your desk room picture) -> fractions of the part that is shown */
  function inBand(r) {
    const B = Art.officeBand;
    if (!B || (B.k === 1 && B.y0 === 0)) return r;
    const o = Object.assign({}, r, { y: (r.y - B.y0) / B.k });
    if (r.h != null) o.h = r.h / B.k;
    if (r.r != null) o.r = r.r / B.k;
    return o;
  }
  /* where a doorway is in the desk room (fractions of what is shown) */
  const officeDoor = (side) => inBand(CFG.office.doors[side]);
  /* a camera picture bigger than it is ever shown (w x h, cover-fit) is shrunk once */
  function fitPicture(img, w, h) {
    const s = Math.max(w / img.width, h / img.height);
    if (s >= 1) return img;
    const c = makeCanvas(img.width * s, img.height * s);
    c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
    return c;
  }

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
  /* can this browser blend with 'saturation' / 'overlay'? (older ones silently ignore unknown blend modes) */
  function blendOk(op) { const x = makeCanvas(1, 1).getContext('2d'); x.globalCompositeOperation = op; return x.globalCompositeOperation === op; }
  const SAT_OK = blendOk('saturation');
  const ghostCache = new WeakMap();
  /* the "dream lie" look: colour drained out, then a violet wash */
  function ghostOf(img) {
    let c = ghostCache.get(img);
    if (c) return c;
    c = makeCanvas(img.width, img.height);
    const x = c.getContext('2d');
    x.drawImage(img, 0, 0);
    if (SAT_OK) { // older browsers get the wash only
      x.globalCompositeOperation = 'saturation'; x.fillStyle = '#888'; x.fillRect(0, 0, c.width, c.height);
      x.globalCompositeOperation = 'destination-in'; x.drawImage(img, 0, 0);
    }
    x.globalCompositeOperation = 'source-atop'; x.fillStyle = 'rgba(157,132,255,.35)'; x.fillRect(0, 0, c.width, c.height);
    ghostCache.set(img, c);
    return c;
  }
  /* softer and softer copies of a picture (half size: a blurred picture needs no detail), baked once so falling
     asleep never runs a blur filter while it plays. [] when the browser can't blur a canvas. */
  function bakeBlurs(img, radii) {
    const probe = makeCanvas(1, 1).getContext('2d');
    if (!('filter' in probe)) return [];
    return radii.map((b) => {
      const c = makeCanvas(W / 2, H / 2), x = c.getContext('2d');
      x.filter = `blur(${b / 2}px)`; x.drawImage(img, -8, -8, W / 2 + 16, H / 2 + 16); // (a little oversized: no dark rim at the edges)
      return { b, img: c };
    });
  }
  /* a 1600x900 copy of a picture (cover-fit), optionally with a colour blended over it (op: 'multiply', 'overlay' …) */
  function shadeCopy(img, op, color, alpha) {
    const c = makeCanvas(W, H), x = c.getContext('2d');
    x.fillStyle = '#000'; x.fillRect(0, 0, W, H); // see-through bits of a picture stay dark, never show the last frame
    drawCover(x, img, 0, 0, W, H);
    if (op) {
      const ok = blendOk(op);
      x.globalCompositeOperation = ok ? op : 'source-over'; x.globalAlpha = ok ? alpha : alpha * 0.6;
      x.fillStyle = color; x.fillRect(0, 0, W, H);
    }
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

  /* a monster without frames yet: a hunched shadow with glowing eyes, breathing in 4 frames.
     config color (optional, like "#ff2040") tints its eyes and the faint edge that keeps it readable in the dark. */
  function shadowFigure(def) {
    const col = /^#[0-9a-f]{3,8}$|^rgb/i.test(String(def.color || '')) ? def.color : '#ff2040', out = [];
    for (let i = 0; i < 4; i++) {
      const c = makeCanvas(600, 900), x = c.getContext('2d');
      const ph = i / 4 * Math.PI * 2, br = Math.sin(ph) * 9, sw = Math.cos(ph) * 7; // breathing, and the arms swaying
      const parts = [], part = () => { const P = new Path2D(); parts.push(P); return P; }; // (each part is filled on its own)
      let P = part(); // legs, from the hips to the floor
      P.moveTo(232, 560); P.quadraticCurveTo(222, 740, 196, 900); P.lineTo(258, 900); P.quadraticCurveTo(272, 720, 296, 600);
      P.quadraticCurveTo(322, 720, 344, 900); P.lineTo(404, 900); P.quadraticCurveTo(384, 740, 374, 560); P.closePath();
      P = part(); // the hunched back: a hump on the left, the shoulders thrown forward
      P.moveTo(226, 600); P.bezierCurveTo(150, 470, 168 + br * 0.4, 300 + br, 262, 262 + br);
      P.bezierCurveTo(330, 236 + br, 392, 262 + br, 404, 318 + br); P.bezierCurveTo(414, 420, 396, 520, 376, 604); P.closePath();
      P = part(); P.ellipse(402, 286 + br * 0.7, 64, 78, 0.5, 0, Math.PI * 2); // the head, low and pushed forward
      // long arms that hang past the knees, bony at the elbow, with three claws
      for (const [sx, sy, hx, hy] of [[376, 326, 432 + sw, 700], [258, 314, 212 - sw, 690]]) {
        const ex = (sx + hx) / 2 + (hx > sx ? 26 : -26), ey = (sy + hy) / 2;
        P = part(); P.moveTo(sx - 30, sy + br); P.quadraticCurveTo(ex - 30, ey, hx - 16, hy);
        for (let f = 0; f < 3; f++) { P.lineTo(hx - 14 + f * 14, hy + 50 - Math.abs(f - 1) * 10); P.lineTo(hx - 7 + f * 14, hy + 8); }
        P.lineTo(hx + 24, hy); P.quadraticCurveTo(ex + 30, ey, sx + 30, sy + br); P.closePath();
      }
      // a faint coloured edge all the way round (only round the outside: the body is drawn over it), and a hint of colour
      x.fillStyle = col; x.globalAlpha = 0.45;
      for (const [dx, dy] of [[-3, 0], [3, 0], [0, -3], [0, 3]]) { x.save(); x.translate(dx, dy); for (const Q of parts) x.fill(Q); x.restore(); }
      x.globalAlpha = 1; x.fillStyle = '#0c0710'; for (const Q of parts) x.fill(Q);
      x.globalCompositeOperation = 'source-atop'; x.globalAlpha = 0.14; x.fillStyle = col; x.fillRect(0, 0, 600, 900);
      x.globalCompositeOperation = 'source-over';
      x.globalAlpha = 1; x.fillStyle = '#ffe9e0'; x.shadowColor = col; x.shadowBlur = 26;
      x.beginPath(); x.arc(412, 270 + br * 0.7, 9, 0, 7); x.arc(446, 286 + br * 0.7, 8, 0, 7); x.fill(); // eyes
      if (DEV) { // tell the artist (never the player) why this monster looks like a shadow
        x.shadowBlur = 0; x.fillStyle = '#e9dfcf'; x.font = '28px VT323, monospace'; x.textAlign = 'center';
        x.fillText('(no frames for ' + def.name + ')', 300, 840);
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

    // the crayon drawing pinned to the wall
    pinDrawing(x, PIN_SPOT.x, PIN_SPOT.y, null);

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
    // the alarm clock's shadow (the clock itself is drawn live, with hands that show the night's time: see drawDeskClock)
    x.fillStyle = 'rgba(0,0,0,.4)'; x.beginPath(); x.ellipse(1452, 623, 44, 6, 0, 0, 7); x.fill();
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

  /* ----- the crayon drawing: a child's drawing of the house at night under a huge moon, one window lit, the
     front door left open and little footprints going in ("he walks at night"). It hangs on the desk-room wall and
     turns up on your bedside table after Night 3. On purpose it has NO monster in it: you only ever see the
     monster in the real dream. paper: the sheet (assets/scenes/paper.jpg) or null for a plain one.
     Drawn at 380 x 460 (twice the size it hangs on the wall), the same way every time. ----- */
  const KID_CAPTION = 'he walks at night';
  /* a child's handwriting, one stroke list per letter: [width, strokes]. x-height 1, baseline at y 1 (tall
     letters reach up to -0.75, g hangs down to 1.55). Letters missing here are written with a font instead. */
  const KID_FONT = (() => {
    const ring = (cx, cy, rx, ry, a0, a1) => { const p = []; for (let i = 0; i <= 18; i++) { const a = a0 + (a1 - a0) * i / 18; p.push([cx + Math.cos(a) * rx, cy + Math.sin(a) * ry]); } return p; };
    const TAU = Math.PI * 2;
    return {
      a: [0.8, [ring(0.32, 0.56, 0.31, 0.44, -0.5, -0.5 - TAU), [[0.66, 0.06], [0.66, 1.0]]]],
      e: [0.7, [[[0.05, 0.56], [0.64, 0.56]].concat(ring(0.34, 0.56, 0.3, 0.44, 0, -TAU + 0.85))]],
      g: [0.76, [ring(0.31, 0.45, 0.3, 0.4, -0.5, -0.5 - TAU), [[0.65, 0.04], [0.65, 1.28], [0.55, 1.5], [0.3, 1.55], [0.07, 1.4]]]],
      h: [0.68, [[[0.06, -0.75], [0.06, 1.0]], [[0.06, 0.52], [0.16, 0.18], [0.36, 0.04], [0.56, 0.18], [0.62, 0.48], [0.62, 1.0]]]],
      i: [0.3, [[[0.13, 0.08], [0.13, 1.0]], [[0.12, -0.4], [0.14, -0.34]]]],
      k: [0.66, [[[0.06, -0.75], [0.06, 1.0]], [[0.58, 0.04], [0.08, 0.6], [0.62, 1.0]]]],
      l: [0.3, [[[0.13, -0.78], [0.13, 1.0]]]],
      n: [0.68, [[[0.06, 0.04], [0.06, 1.0]], [[0.06, 0.5], [0.16, 0.16], [0.36, 0.04], [0.56, 0.18], [0.62, 0.48], [0.62, 1.0]]]],
      s: [0.62, [[[0.56, 0.16], [0.38, 0.02], [0.14, 0.08], [0.08, 0.3], [0.3, 0.5], [0.54, 0.66], [0.54, 0.88], [0.32, 1.0], [0.04, 0.9]]]],
      t: [0.6, [[[0.28, -0.58], [0.28, 0.86], [0.36, 1.0], [0.54, 0.94]], [[0.02, 0.08], [0.56, 0.04]]]],
      w: [0.88, [[[0.02, 0.04], [0.2, 1.0], [0.42, 0.34], [0.64, 1.0], [0.84, 0.04]]]],
      ' ': [0.46, []],
    };
  })();

  function paintKidDrawing(paper) {
    const pw = 380, ph = 460, c = makeCanvas(pw, ph), x = c.getContext('2d'), r = mulberry32(1313);
    if (paper) x.drawImage(paper, 0, 0, pw, ph);
    else { x.fillStyle = '#ddd0b0'; x.fillRect(0, 0, pw, ph); noiseFill(x, pw, ph, 0.05, 77, 2); }
    // the crayon goes on its own layer first, then the paper's tooth shows through it (where the wax skipped)
    const L = makeCanvas(pw, ph), l = L.getContext('2d');
    l.lineCap = 'round'; l.lineJoin = 'round';
    const jit = (a) => (r() - 0.5) * 2 * a;
    const line = (pts, col, w, passes) => { // a crayon line: a few wobbly passes over the same path
      l.strokeStyle = col;
      for (let p = 0; p < (passes || 3); p++) {
        l.globalAlpha = 0.55 + r() * 0.3; l.lineWidth = w * (0.65 + r() * 0.5);
        l.beginPath();
        pts.forEach(([px, py], i) => { const X = px + jit(1.3), Y = py + jit(1.3); if (i) l.lineTo(X, Y); else l.moveTo(X, Y); });
        l.stroke();
      }
      l.globalAlpha = 1;
    };
    const ring = (cx, cy, rx, ry, n, wob) => { const p = []; for (let i = 0; i <= n; i++) { const a = -0.4 + i / n * (Math.PI * 2 + 0.5); p.push([cx + Math.cos(a) * (rx + jit(wob)), cy + Math.sin(a) * (ry + jit(wob))]); } return p; };
    const poly = (pts) => { const P = new Path2D(); pts.forEach(([px, py], i) => (i ? P.lineTo(px, py) : P.moveTo(px, py))); P.closePath(); return P; };
    // colouring in: back-and-forth strokes across the shape (clipped to it), tilted by ang
    const fill = (shape, bx, by, bw, bh, col, w, gap, ang, alpha, rule) => {
      l.save(); l.clip(shape, rule || 'nonzero');
      l.strokeStyle = col; l.lineWidth = w; l.globalAlpha = alpha;
      const R = Math.hypot(bw, bh) / 2 + 6;
      l.translate(bx + bw / 2, by + bh / 2); l.rotate(ang);
      l.beginPath(); l.moveTo(-R, -R);
      for (let y = -R, k = 1; y <= R; y += gap, k++) l.lineTo((k % 2 ? R : -R) + jit(8), y + jit(gap * 0.35));
      l.stroke(); l.restore();
    };
    const moon = { x: 94, y: 94, r: 56 };
    const house = [[138, 212], [236, 128], [334, 212], [322, 212], [322, 322], [150, 322], [150, 212]];
    // the night sky, coloured round the moon and the house (a kid leaves a gap round things)
    const sky = new Path2D(); sky.rect(16, 16, 348, 306);
    sky.arc(moon.x, moon.y, moon.r + 7, 0, Math.PI * 2);
    house.forEach(([px, py], i) => (i ? sky.lineTo(px, py - 6) : sky.moveTo(px, py - 6))); sky.closePath();
    fill(sky, 16, 16, 348, 306, '#262c66', 7, 5.5, -0.12, 0.72, 'evenodd');
    // the huge moon
    const M = new Path2D(); M.arc(moon.x, moon.y, moon.r, 0, Math.PI * 2);
    fill(M, moon.x - moon.r, moon.y - moon.r, moon.r * 2, moon.r * 2, '#f3c84c', 6, 6, 0.6, 0.85);
    line(ring(moon.x, moon.y, moon.r, moon.r, 26, 1.5), '#dc9f2a', 5);
    for (const [sx, sy, k] of [[198, 42, 1], [262, 62, 0.8], [336, 42, 1.1], [318, 118, 0.8], [166, 150, 0.9], [36, 196, 0.8]]) { // stars
      const q = 9 * k;
      line([[sx - q, sy], [sx + q, sy]], '#f0d468', 4, 2); line([[sx, sy - q], [sx, sy + q]], '#f0d468', 4, 2);
      line([[sx - q * 0.6, sy - q * 0.6], [sx + q * 0.6, sy + q * 0.6]], '#f0d468', 3, 1);
    }
    // the house: lilac walls, a crimson roof, a chimney
    const body = poly([[150, 212], [322, 212], [322, 322], [150, 322]]), roof = poly([[138, 212], [236, 128], [334, 212]]);
    fill(body, 150, 212, 172, 110, '#8d78b4', 6, 8, 0.3, 0.42);
    fill(roof, 138, 128, 196, 84, '#a03238', 6, 7, -0.5, 0.8);
    const ink = '#33222f';
    line([[288, 172], [288, 138], [308, 138], [308, 189]], ink, 5);
    line([[138, 212], [236, 128], [334, 212], [138, 212]], ink, 5);
    line([[150, 212], [150, 322], [322, 322], [322, 212]], ink, 5);
    // one window lit, one dark
    const winLit = poly([[172, 228], [214, 228], [214, 266], [172, 266]]), winDark = poly([[258, 228], [300, 228], [300, 266], [258, 266]]);
    fill(winLit, 172, 228, 42, 38, '#f6cf4a', 5, 5, 0.9, 0.95);
    fill(winDark, 258, 228, 42, 38, '#141019', 5, 5, -0.9, 0.9);
    for (const [wx, wy] of [[172, 228], [258, 228]]) {
      line([[wx, wy], [wx + 42, wy], [wx + 42, wy + 38], [wx, wy + 38], [wx, wy]], ink, 4.5);
      line([[wx + 21, wy], [wx + 21, wy + 38]], ink, 3.5, 2); line([[wx, wy + 19], [wx + 42, wy + 19]], ink, 3.5, 2);
    }
    // the front door, open: black inside, the door swung out
    const doorHole = poly([[218, 262], [254, 262], [254, 322], [218, 322]]);
    fill(doorHole, 218, 262, 36, 60, '#0f0a12', 5, 4, 1.2, 0.95);
    fill(poly([[254, 262], [276, 270], [276, 318], [254, 322]]), 254, 262, 22, 60, '#7b5232', 5, 6, 0.2, 0.75);
    line([[218, 322], [218, 262], [254, 262], [254, 322]], ink, 4.5);
    line([[254, 262], [276, 270], [276, 318], [254, 322]], '#4a3020', 4);
    // the grass, and a path from the door
    const grass = new Path2D(); grass.moveTo(16, 324); for (let gx = 16; gx <= 364; gx += 12) grass.lineTo(gx, 318 + jit(4)); grass.lineTo(364, 356); grass.lineTo(16, 360); grass.closePath();
    fill(grass, 16, 312, 348, 50, '#3f7a3c', 6, 6, -0.25, 0.7);
    for (let gx = 22; gx < 360; gx += 15 + r() * 10) line([[gx, 326], [gx + jit(3), 312 + jit(3)]], '#2f6a30', 3, 1);
    line([[220, 323], [194, 352], [168, 386]], '#6e5236', 4, 2); line([[252, 323], [262, 352], [276, 386]], '#6e5236', 4, 2);
    // little dark footprints, from the edge of the paper right up to the open door
    l.fillStyle = '#1b1421';
    for (let i = 0; i < 9; i++) {
      const t = i / 8, u = 1 - t, px = u * u * 26 + 2 * u * t * 140 + t * t * 236, py = u * u * 352 + 2 * u * t * 378 + t * t * 328;
      const dx = 2 * u * (140 - 26) + 2 * t * (236 - 140), dy = 2 * u * (378 - 352) + 2 * t * (328 - 378), a = Math.atan2(dy, dx), side = i % 2 ? 1 : -1;
      const k = 1 - 0.45 * t;
      l.save(); l.translate(px - Math.sin(a) * 6 * side * k, py + Math.cos(a) * 6 * side * k); l.rotate(a + Math.PI / 2);
      l.globalAlpha = 0.85; l.beginPath(); l.ellipse(0, 0, 4.2 * k, 6.5 * k, 0, 0, Math.PI * 2); l.fill(); l.restore();
    }
    l.globalAlpha = 1;
    // the words, in the same crayon, a little wonky
    const U = 21, chars = KID_CAPTION.split(''), gapU = 0.16;
    const wide = chars.reduce((t, ch) => t + (KID_FONT[ch] ? KID_FONT[ch][0] : 0.62) + gapU, -gapU) * U;
    let cx = (pw - wide) / 2;
    for (const ch of chars) {
      const g = KID_FONT[ch], cw = (g ? g[0] : 0.62) * U, base = 438 + jit(2.5), sz = U * (0.92 + r() * 0.16), rot = jit(0.07);
      if (g) for (const st of g[1]) line(st.map(([gx, gy]) => { const X = gx * sz, Y = (gy - 1) * sz; return [cx + X * Math.cos(rot) - Y * Math.sin(rot), base + X * Math.sin(rot) + Y * Math.cos(rot)]; }), '#2a1a30', 4.2, 2);
      else if (ch.trim()) { l.fillStyle = '#2a1a30'; l.font = Math.round(U * 1.4) + 'px Fell, serif'; l.fillText(ch, cx, base); }
      cx += cw + gapU * U;
    }
    // the paper's tooth: tiny gaps in the wax
    const T = makeCanvas(pw, ph), tx = T.getContext('2d'), id = tx.createImageData(pw, ph), d = id.data;
    for (let i = 0; i < d.length; i += 4) { const v = r(); if (v < 0.16) { d[i + 3] = 70 + v * 600; if (v < 0.05 && i + 4 < d.length) d[i + 7] = 120; } } // (some gaps two pixels wide)
    tx.putImageData(id, 0, 0);
    l.globalCompositeOperation = 'destination-out'; l.drawImage(T, 0, 0); l.globalCompositeOperation = 'source-over';
    x.globalAlpha = 0.94; x.drawImage(L, 0, 0); x.globalAlpha = 1;
    // a soft fold across the middle, and the red pin
    x.fillStyle = 'rgba(60,40,20,.07)'; x.fillRect(0, ph * 0.49, pw, 2); x.fillStyle = 'rgba(255,250,235,.12)'; x.fillRect(0, ph * 0.49 + 2, pw, 2);
    x.fillStyle = 'rgba(20,10,10,.35)'; x.beginPath(); x.ellipse(pw / 2 + 5, 26, 11, 7, 0, 0, Math.PI * 2); x.fill();
    x.fillStyle = '#a8162a'; x.beginPath(); x.arc(pw / 2, 20, 11, 0, Math.PI * 2); x.fill();
    x.fillStyle = 'rgba(255,200,200,.55)'; x.beginPath(); x.arc(pw / 2 - 4, 16, 3.5, 0, Math.PI * 2); x.fill();
    return c;
  }
  /* the drawing in the light of a wall: shade = [colour at its top, colour at its bottom], multiplied over it, plus a
     fine grain like the photo's. Without multiply (very old browsers) it is just darkened. */
  function shadedDrawing(shade) {
    const d = Art.drawing, c = makeCanvas(d.width, d.height), x = c.getContext('2d'), ok = blendOk('multiply');
    x.drawImage(d, 0, 0);
    const g = x.createLinearGradient(0, 0, 0, c.height); g.addColorStop(0, shade[0]); g.addColorStop(1, shade[1]);
    x.globalCompositeOperation = ok ? 'multiply' : 'source-over'; x.globalAlpha = ok ? 1 : 0.5;
    x.fillStyle = ok ? g : '#07050c'; x.fillRect(0, 0, c.width, c.height);
    x.globalAlpha = 1; x.globalCompositeOperation = 'source-over';
    noiseFill(x, c.width, c.height, 0.04, 5, 1.5);
    return c;
  }
  /* pin the drawing on a wall: its top-left corner at left, top (in a 2400 x 900 room), 190 x 230, a little crooked,
     with a soft shadow. shade: the wall's light (see shadedDrawing), or null */
  const PIN_SPOT = { x: 1700, y: 190 }; // the empty piece of wall both built-in desk rooms keep for it
  function pinDrawing(x, left, top, shade) {
    const d = shade ? shadedDrawing(shade) : Art.drawing, w = 190, h = 230;
    x.save(); x.translate(left + w / 2, top + h / 2); x.rotate(0.05);
    x.shadowColor = 'rgba(4,2,8,.65)'; x.shadowBlur = 12; x.shadowOffsetX = 5; x.shadowOffsetY = 8;
    x.drawImage(d, -w / 2, -h / 2, w, h);
    x.restore();
  }
  /* the built-in photo desk room (made at 2400 x 900), with the drawing pinned on its empty piece of wall, in the dim
     violet light of that wall. Made once, at the size it is shown. */
  function photoOffice(img) {
    const c = makeCanvas(officeWidthFor(img), H), x = c.getContext('2d');
    x.drawImage(img, 0, 0, c.width, H);
    x.save(); x.scale(c.width / 2400, 1);
    pinDrawing(x, PIN_SPOT.x, PIN_SPOT.y, ['rgb(66,68,94)', 'rgb(80,82,110)']);
    x.restore();
    return c;
  }

  /* CAM 7's photo shows the same desk room from behind: the drawing is pinned there too, on the same piece of wall
     (its corners in cam7_you.jpg's 1824 x 1026 pixels, seen in perspective from the high corner; the wall's light there) */
  const CAM7_PIN = { tl: [1559.9, 228.5], tr: [1772.7, 249.9], br: [1708.9, 471.0], bl: [1512.6, 437.4], shade: ['rgb(47,56,69)', 'rgb(57,67,80)'] };
  function youCamWithDrawing(img) {
    if (!Art.drawing) return img;
    const c = makeCanvas(img.width, img.height), x = c.getContext('2d'), k = img.width / 1824, P = CAM7_PIN;
    x.drawImage(img, 0, 0);
    const pt = (a, b, t) => [(a[0] + (b[0] - a[0]) * t) * k, (a[1] + (b[1] - a[1]) * t) * k];
    x.save(); // its soft shadow on the wallpaper
    x.shadowColor = 'rgba(4,2,8,.6)'; x.shadowBlur = 10 * k; x.shadowOffsetX = 4 * k; x.shadowOffsetY = 7 * k;
    x.fillStyle = 'rgb(40,46,56)'; x.beginPath();
    [P.tl, P.tr, P.br, P.bl].forEach((q, i) => x[i ? 'lineTo' : 'moveTo'](q[0] * k, q[1] * k)); x.closePath(); x.fill();
    x.restore();
    const d = shadedDrawing(P.shade), n = 32; // drawn in thin strips, each one fitted between the left and right edges
    for (let i = 0; i < n; i++) {
      const t0 = i / n, t1 = (i + 1) / n, L0 = pt(P.tl, P.bl, t0), R0 = pt(P.tr, P.br, t0), L1 = pt(P.tl, P.bl, t1);
      const sy = d.height * t0, sh = d.height / n;
      x.save();
      x.setTransform((R0[0] - L0[0]) / d.width, (R0[1] - L0[1]) / d.width, (L1[0] - L0[0]) / sh, (L1[1] - L0[1]) / sh, L0[0], L0[1]);
      x.drawImage(d, 0, sy, d.width, sh + (i < n - 1 ? 0.6 : 0), 0, 0, d.width, sh + (i < n - 1 ? 0.6 : 0));
      x.restore();
    }
    return c;
  }
  /* how big a doorway is drawn in the desk room (the stand-ins are painted at exactly that size) */
  function doorPx(side) { const d = officeDoor(side); return { w: d.w * officeWidthFor(Art.office), h: d.h * H }; }
  function paintDoorway(side, lit) {
    const { w, h } = doorPx(side), c = makeCanvas(w, h), x = c.getContext('2d');
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

  function paintShutter(side) {
    const { w, h } = doorPx(side), c = makeCanvas(w, h), x = c.getContext('2d');
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

  /* ----- your real bedroom (stand-in): seen from the bed, a closet door on the left, a window with blinds,
     a bedside table on the right. mode 'night' or 'morning' changes the sky behind the blinds (and the night one
     has the little alarm clock on the table). ----- */
  /* where the morning's evidence goes (fractions of the bedroom picture, like the door boxes) */
  const EVIDENCE_SPOTS = {
    2: { x: 0.094, y: 0.167, w: 0.169, h: 0.556 }, // the closet door (it is open a crack)
    3: { x: 0.880, y: 0.510, w: 0.070, h: 0.157 }, // on the bedside table: the drawing from the desk room
    4: { x: 0.150, y: 0.762, w: 0.075, h: 0.038 }, // on the floor: a scrap of pink collar
  };
  function evidenceCfg(n) {
    const v = ((CFG.morning || {}).evidence || {})[n];
    return Object.assign({}, EVIDENCE_SPOTS[n], v && typeof v === 'object' ? v : { image: v || '' });
  }
  const spotPx = (b) => ({ x: b.x * W, y: b.y * H, w: b.w * W, h: b.h * H });
  const WINDOW_PX = { x: 1050, y: 150, w: 300, h: 320 };
  const TABLE_TOP = 600; // the bedside table's top (the clock stands on it)

  function paintBedroom(mode) {
    const c = makeCanvas(W, H), x = c.getContext('2d'), r = mulberry32(5), day = mode === 'morning';
    let g = x.createLinearGradient(0, 0, 0, 650); g.addColorStop(0, '#80747f'); g.addColorStop(1, '#605560');
    x.fillStyle = g; x.fillRect(0, 0, W, 650);                                       // wall
    x.fillStyle = 'rgba(244,236,255,.08)';
    for (let i = 0; i < 70; i++) { x.beginPath(); x.arc(r() * W, 60 + r() * 540, 3 + r() * 4, 0, 7); x.fill(); } // dotty wallpaper
    x.fillStyle = 'rgba(0,0,0,.16)'; x.fillRect(0, 0, W, 36);
    g = x.createLinearGradient(0, 650, 0, H); g.addColorStop(0, '#6a5342'); g.addColorStop(1, '#3a2b21');
    x.fillStyle = g; x.fillRect(0, 650, W, H - 650);                                 // floor
    x.fillStyle = '#3e3442'; x.fillRect(0, 640, W, 16);                              // skirting
    x.strokeStyle = 'rgba(0,0,0,.25)'; x.lineWidth = 2;
    for (let i = -12; i <= 12; i++) { x.beginPath(); x.moveTo(W / 2 + i * 70, 656); x.lineTo(W / 2 + i * 190, H); x.stroke(); }
    x.fillStyle = 'rgba(122,74,94,.75)'; x.beginPath(); x.ellipse(760, 742, 390, 62, 0, 0, 7); x.fill(); // rug
    // the closet door
    const D = spotPx(EVIDENCE_SPOTS[2]);
    x.fillStyle = '#433740'; x.fillRect(D.x - 16, D.y - 16, D.w + 32, D.h + 16);
    g = x.createLinearGradient(D.x, 0, D.x + D.w, 0); g.addColorStop(0, '#8a7569'); g.addColorStop(1, '#6c5a51');
    x.fillStyle = g; x.fillRect(D.x, D.y, D.w, D.h);
    x.strokeStyle = 'rgba(0,0,0,.22)'; x.lineWidth = 4;
    for (const [py, ph] of [[0.06, 0.38], [0.52, 0.42]]) x.strokeRect(D.x + D.w * 0.14, D.y + D.h * py, D.w * 0.72, D.h * ph);
    x.fillStyle = '#d9c27e'; x.beginPath(); x.arc(D.x + D.w - 26, D.y + D.h * 0.5, 9, 0, 7); x.fill();
    // a framed drawing of the moon
    x.fillStyle = '#2f2632'; x.fillRect(600, 190, 170, 140); x.fillStyle = '#1d2142'; x.fillRect(612, 202, 146, 116);
    x.fillStyle = '#f2e6b8'; x.beginPath(); x.arc(690, 258, 30, 0, 7); x.fill();
    x.fillStyle = '#1d2142'; x.beginPath(); x.arc(704, 252, 27, 0, 7); x.fill();       // (a crescent, painted: no holes in the picture)
    // the window with blinds (night sky or morning sky behind them)
    const Wn = WINDOW_PX;
    g = x.createLinearGradient(0, Wn.y, 0, Wn.y + Wn.h);
    if (day) { g.addColorStop(0, '#cfe6f6'); g.addColorStop(1, '#fff0d2'); } else { g.addColorStop(0, '#0b1534'); g.addColorStop(1, '#1d1745'); }
    x.fillStyle = g; x.fillRect(Wn.x, Wn.y, Wn.w, Wn.h);
    if (!day) { for (let i = 0; i < 25; i++) { x.fillStyle = `rgba(255,255,255,${0.3 + r() * 0.6})`; x.fillRect(Wn.x + r() * Wn.w, Wn.y + r() * Wn.h, 2, 2); }
      glow(x, Wn.x + Wn.w * 0.7, Wn.y + 80, 120, 'rgba(230,225,255,A)', 0.5); }
    for (let y = Wn.y + 4; y < Wn.y + Wn.h - 8; y += 21) {
      x.fillStyle = day ? 'rgba(244,236,222,.92)' : 'rgba(214,206,196,.85)'; x.fillRect(Wn.x, y, Wn.w, 13);
      x.fillStyle = 'rgba(0,0,0,.18)'; x.fillRect(Wn.x, y + 13, Wn.w, 2);
    }
    x.strokeStyle = '#3a3038'; x.lineWidth = 16; x.strokeRect(Wn.x, Wn.y, Wn.w, Wn.h);
    x.fillStyle = '#4a3e46'; x.fillRect(Wn.x - 26, Wn.y + Wn.h + 6, Wn.w + 52, 16);   // sill
    // the bedside table (its clock is drawn live, see drawAlarmClock)
    x.fillStyle = '#4a3428'; x.fillRect(1385, TABLE_TOP + 16, 180, 170);
    x.fillStyle = '#5c4031'; x.fillRect(1368, TABLE_TOP, 214, 18);
    x.strokeStyle = 'rgba(0,0,0,.3)'; x.lineWidth = 3; x.strokeRect(1402, TABLE_TOP + 40, 146, 56);
    x.fillStyle = '#d9c27e'; x.beginPath(); x.arc(1475, TABLE_TOP + 68, 6, 0, 7); x.fill();
    if (!day) drawAlarmClock(x, 1500, TABLE_TOP - 34, 30, { h: 11, m: 59 }); // in the morning it's the big one by your face
    // the end of your bed: the quilt over your feet
    x.beginPath(); x.moveTo(0, 812); x.quadraticCurveTo(420, 748, 800, 776); x.quadraticCurveTo(1180, 806, W, 770); x.lineTo(W, H); x.lineTo(0, H); x.closePath();
    g = x.createLinearGradient(0, 750, 0, H); g.addColorStop(0, '#6e5d92'); g.addColorStop(1, '#3a3056');
    x.fillStyle = g; x.fill();
    x.strokeStyle = 'rgba(255,255,255,.1)'; x.lineWidth = 3;
    for (const [a, b] of [[260, 860], [620, 830], [1020, 850], [1360, 840]]) { x.beginPath(); x.moveTo(a, b); x.quadraticCurveTo(a + 90, b - 30, a + 200, b - 6); x.stroke(); }
    noiseFill(x, W, H, 0.05, 9, 3);
    return c;
  }

  /* a twin-bell wind-up alarm clock. o: { h, m, s (hands; s = second hand, optional), ring (0..1 shake), squash (0..1) } */
  function drawAlarmClock(c, x, y, r, o) {
    const ring = (o.ring || 0) * fxMul(), wob = Math.sin(G.t * Math.PI * 2 * 12); // the hammer rattles 12 times a second
    c.save(); c.translate(x + wob * 6 * ring, y + Math.cos(G.t * 71) * 2 * ring);
    if (o.squash) { c.translate(0, r * 1.05); c.scale(1 + 0.12 * o.squash, 1 - 0.18 * o.squash); c.translate(0, -r * 1.05); }
    c.lineCap = 'round'; c.strokeStyle = '#2a0c10'; c.lineWidth = r * 0.13;
    for (const s of [-1, 1]) { c.beginPath(); c.moveTo(s * r * 0.5, r * 0.72); c.lineTo(s * r * 0.72, r * 1.05); c.stroke(); } // legs
    c.save(); c.translate(0, -r * 0.98); c.rotate(wob * 0.5 * ring);                                                   // hammer
    c.lineWidth = r * 0.07; c.strokeStyle = '#6b5a2a'; c.beginPath(); c.moveTo(0, 0); c.lineTo(0, -r * 0.42); c.stroke();
    c.fillStyle = '#d9c27e'; c.beginPath(); c.arc(0, -r * 0.44, r * 0.1, 0, 7); c.fill(); c.restore();
    for (const s of [-1, 1]) {                                                                                       // bells
      c.save(); c.translate(s * r * 0.6, -r * 0.78); c.rotate(s * 0.65);
      c.fillStyle = '#d9c27e'; c.strokeStyle = '#7a6426'; c.lineWidth = r * 0.05;
      c.beginPath(); c.arc(0, 0, r * 0.42, Math.PI, 0); c.closePath(); c.fill(); c.stroke(); c.restore();
    }
    c.fillStyle = '#a3202c'; c.strokeStyle = '#5a0e16'; c.lineWidth = r * 0.08;                                   // body + face
    c.beginPath(); c.arc(0, 0, r, 0, 7); c.fill(); c.stroke();
    c.fillStyle = '#f3ead6'; c.beginPath(); c.arc(0, 0, r * 0.78, 0, 7); c.fill();
    c.strokeStyle = '#3a2a22';
    for (let i = 0; i < 12; i++) { const a = i / 12 * Math.PI * 2; c.lineWidth = r * (i % 3 ? 0.03 : 0.06); c.beginPath(); c.moveTo(Math.sin(a) * r * 0.62, -Math.cos(a) * r * 0.62); c.lineTo(Math.sin(a) * r * 0.72, -Math.cos(a) * r * 0.72); c.stroke(); }
    clockHands(c, r * 0.78, o);
    c.restore();
  }
  /* the hands of a clock whose face (radius F) is centred at 0,0. o: { h, m, s } */
  function clockHands(c, F, o) {
    c.lineCap = 'round';
    const hand = (turns, len, wid, col) => { const a = turns * Math.PI * 2; c.strokeStyle = col; c.lineWidth = wid; c.beginPath(); c.moveTo(0, 0); c.lineTo(Math.sin(a) * len, -Math.cos(a) * len); c.stroke(); };
    hand(((o.h || 0) % 12 + (o.m || 0) / 60) / 12, F * 0.54, F * 0.128, '#1d1210');
    hand((o.m || 0) / 60, F * 0.79, F * 0.083, '#1d1210');
    if (o.s != null) hand(o.s / 60, F * 0.85, F * 0.032, '#c4132b');
    c.fillStyle = '#1d1210'; c.beginPath(); c.arc(0, 0, F * 0.09, 0, 7); c.fill();
  }
  /* sound rings around a ringing clock: three arcs on each side that wobble with the hammer (still with Dream effects Off) */
  function drawRingArcs(c, x, y, r, alpha) {
    c.save(); c.lineCap = 'round'; c.lineWidth = Math.max(2, r * 0.09);
    for (let i = 0; i < 3; i++) {
      const R = r * (1.45 + 0.42 * i) + Math.sin(G.t * Math.PI * 2 * 12 + i * 1.3) * r * 0.08 * fxMul();
      c.strokeStyle = `rgba(255,248,230,${alpha * (0.75 - 0.2 * i)})`;
      for (const a of [0, Math.PI]) { c.beginPath(); c.arc(x, y - r * 0.2, R, a - 0.45, a + 0.45); c.stroke(); }
    }
    c.restore();
  }

  function paintFx() {
    Art.noise = [];
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
    // the cameras' scanlines and vignette, baked into one picture (one draw a frame instead of a pattern fill + a draw)
    c = makeCanvas(W, H); x = c.getContext('2d');
    x.fillStyle = x.createPattern(Art.scan, 'repeat'); x.fillRect(0, 0, W, H);
    x.drawImage(Art.vignette, 0, 0);
    Art.camOver = c;
    // the red edge of danger: made once, then drawn as strong as the danger is (a small one, stretched: it's soft anyway)
    c = makeCanvas(320, 180); x = c.getContext('2d');
    let rg = x.createRadialGradient(160, 90, 180 * 0.35, 160, 90, 180);
    rg.addColorStop(0, 'rgba(150,0,20,0)'); rg.addColorStop(1, 'rgba(150,0,20,1)');
    x.fillStyle = rg; x.fillRect(0, 0, 320, 180);
    Art.danger = c;
    // the menu's drifting fog: one soft blob per colour, drawn big
    Art.fog = ['rgba(80, 60, 160, .14)', 'rgba(120, 30, 60, .16)'].map((col) => {
      const b = makeCanvas(128, 128), bx2 = b.getContext('2d');
      rg = bx2.createRadialGradient(64, 64, 0, 64, 64, 64);
      rg.addColorStop(0, col); rg.addColorStop(1, 'rgba(0,0,0,0)');
      bx2.fillStyle = rg; bx2.fillRect(0, 0, 128, 128);
      return b;
    });
    c = makeCanvas(32, 32); x = c.getContext('2d');
    const gg = x.createRadialGradient(16, 16, 0, 16, 16, 16);
    gg.addColorStop(0, 'rgba(255,255,255,1)'); gg.addColorStop(1, 'rgba(255,255,255,0)');
    x.fillStyle = gg; x.fillRect(0, 0, 32, 32);
    Art.dot = c;
  }

  /* ------------------------------------------------------------------ */
  /*  GAME STATE                                                        */
  /* ------------------------------------------------------------------ */
  /* p: how far the shutter is down (0 open, 1 shut) and v its speed; held: seconds it has been shut (it breathes
     back out three times faster while open); cost: what it drains right now; gaspT: a tired door about to give way;
     groan: how loud it groans; landT / bangT: short thud and bang effects */
  const freshDoor = () => ({ closed: false, p: 0, v: 0, landed: false, light: false, held: 0, cost: 0, gaspT: 0, groan: 0, landT: 0, bangT: 0 });
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
    clarity: 0,                         // a pinch snaps the picture sharp for a moment
    hudLock: 0,                         // … and the HUD's words don't slip until then (see dreamy)
    lies: [], lieT: 0, taught: false,   // fakes the dream is showing right now (a pinch clears them), see spawnLie
    punch: null,                        // a small flinch toward a doorway when the light finds something
    trauma: 0, kick: { x: 0, y: 0 },   // camera shake (see hit)
    later: [],                          // pause-safe timers (see after)
    parts: [],                          // particles (see spawnParts)
    cueLog: [],                         // the last 40 threat sounds (see cue)
    stats: {},
    stutter: { left: freshFlicker(), right: freshFlicker() }, lampFlick: freshFlicker(),
    whisperT: 20, jumpT: 0, killer: null,
    preScare: 0,                        // 0..1: the room goes dark and silent just before it gets you
    // the room notices: roomP 1 = something is at a door, .5 = next to one; the lamp dims, dust drifts, a shadow
    // crosses the window, and at low Lucidity the desk clock's hands lurch (clockSkew: hours it has run ahead)
    roomP: 0, lampDim: 0, windowPass: null, clockSpin: 0, clockSkew: 0,
    // the dream director's small events (see DREAM_EVENTS): lampBreath (seconds), wrongDoor, the room's stretch,
    // CAM 7 (youCam, youCamAt = the hour it may come); the final half hour (tickShown, nearRang); Night 5's
    // False Dawn (fd while it plays, freeze: monsters and Lucidity hold still, fdRolled: the clock rolled back)
    lampBreath: null, wrongDoor: null, stretch: 1, stretchTo: 1, stretchT: 0, youCam: null, youCamAt: 3,
    tickShown: false, nearRang: false, fd: null, fdDone: false, fdRolled: false, freeze: false,
    scare: null,                        // the jumpscare playing now (see jumpscare)
    // falling asleep (state 'asleep'): introT runs to introDur, then the hypnic jolt starts the night
    introT: 0, introDur: 6.4, retry: false, cardShown: false, joltPlayed: false, settle: 0,
    tickPh: 0,                          // the ticking clock's phase: a new tick at every whole number (see clockTick)
    hush: false,                        // Lucidity zero: the clock has stopped and every sound is gone
    // waking up (states 'waking' -> 'morning' -> 'win'): wakeT counts from 6 AM
    wakeT: 0, wakeView: 'office', wakeClear: false, wakePan: 0, frozen: [], winWait: 0, deadWait: 0, slapT: 0, finale: null,
    voice: { active: false, beats: [], typing: false, stay: false }, // the dream voice (see startVoice)
    // the first-night lesson (see LESSON): the step it is on; did: what you have done since that step began
    lesson: null, did: {}, practice: false,
    // the death recap (see die): spend = where your Lucidity went; litAt = when each doorway was last lit;
    // lighter = "Dream lighter" (after three deaths on one night); recap = the lines typing on the death screen
    spend: {}, litAt: {}, powerAt: 0, lighter: false, recap: null,
    motes: [],
    devGhost: false, devMon: 0, devDrag: false, // the art helper (?dev): see-through placer on, which monster, dragging a door box
  };

  /* a spot in the desk room picture from config office.clock / office.window / office.lamp. The stand-in office has its own;
     a custom office without the key gets null, so nothing is drawn in the wrong place. */
  const OFFICE_SPOTS = { clock: { x: 0.604, y: 0.651, r: 0.029 }, window: { x: 0.233, y: 0.178, w: 0.104, h: 0.3 }, lamp: { x: 0.396, y: 0.567 } };
  function officeSpot(key) {
    const v = CFG.office[key];
    if (v && typeof v.x === 'number' && typeof v.y === 'number') return inBand(v);
    return Art.officeMissing ? OFFICE_SPOTS[key] : null;
  }

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
      this.hurry = false; // a pinch with it breathing at an open door: it doesn't wait for its next move (see walkerHear)
      this.doorT = 0;     // seconds at the door it is standing at
      this.breathed = false; // has it breathed at that door yet? (it must before it can come in)
      this.watched = 0;   // seconds you have been staring at it on a camera
      this.anim = 0; this.animSpeed = 1; this.animOffset = Math.random() * 10; // its own animation clock (it can slow down)
      this.extra = 0;     // levels its brain adds (a shy one you ignore gets braver)
      this.ignored = 0;   // shy: seconds since you last looked at it
      this.awake = 0;     // sleeper: seconds it stays awake after a noise
    }
    frame() { return Math.floor(this.anim + this.animOffset) % this.art.frames.length; }
    get lvl() { return clamp(this.level + this.boost + this.extra, 0, 20); }
  }

  function initMotes() {
    G.motes = [];
    for (let i = 0; i < 70; i++) { const vx = rand(-6, 6); G.motes.push({ x: Math.random() * W, y: Math.random() * H, vx, bvx: vx, vy: rand(-14, -3), r: rand(1, 4.5), a: rand(0.05, 0.35), ph: Math.random() * 7 }); }
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

  /* spawnParts(10, { x, y, spreadX, spreadY, vx, vy, jitter, gravity, life, r, col, office }) — at most 200 alive.
     office: true = x is measured across the desk-room picture, so the bits stay put when you look around.
     vx can be a function (p => speed) for bits that fly away from a point. */
  function spawnParts(n, o) {
    for (let i = 0; i < n && G.parts.length < 200; i++) {
      const life = (o.life || 1) * rand(0.7, 1.3), j = o.jitter == null ? 20 : o.jitter;
      const p = {
        x: o.x + rand(-1, 1) * (o.spreadX || 0), y: o.y + rand(-1, 1) * (o.spreadY || 0),
        vx: 0, vy: (o.vy || 0) + rand(-j, j), g: o.gravity || 0, o: !!o.office,
        life, max: life, r: (o.r || 3) * rand(0.6, 1.4), col: o.col || '#fff',
      };
      p.vx = (typeof o.vx === 'function' ? o.vx(p) : (o.vx || 0)) + rand(-j, j);
      G.parts.push(p);
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
    const p = G.state === 'night' ? G.roomP : 0; // the lamp gets nervous when something is close
    flickerStep(G.lampFlick, dt, 1.2 + 3.6 * p, 0.05 * k, (0.25 + 0.2 * p) * k);
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
  const THREAT = ['steps', 'breath', 'bang']; // the cues that light the edge of the screen on their side

  /* ----- sound captions (Settings): each sound as words, in a lane on the side it came from, plus a red glow
     at that edge of the screen for footsteps, breathing and bangs. Phone speakers can't tell left from right;
     this can. The words come from config.js captions (a missing one uses these). Never names a room. ----- */
  const CAPTIONS = {
    steps: 'footsteps', stepsNear: 'footsteps, close', breath: 'breathing', breathMuffled: 'breathing, muffled',
    breathClose: 'breathing, very close', bang: 'BANG', far: 'a low moan, far off', whisper: 'whispering',
    chime: 'the clock chimes: {0}', powerDown: 'everything goes quiet', clockSlow: 'the clock is slowing down', strain: 'the door groans',
    whisperAbove: 'whispering, right above you', ticking: 'the clock ticks louder', nearRing: 'a muffled ring… almost', alarm: 'the alarm rings!',
  };
  const Captions = {
    box: $('#captions'),
    lanes: { L: $('#captions .capL'), C: $('#captions .capC'), R: $('#captions .capR') },
    edges: { left: $('#edgeL'), right: $('#edgeR') },
    text(key) { const own = (CFG.captions || {})[key]; return own != null ? String(own) : CAPTIONS[key] || ''; },
    /* key: a CAPTIONS name. pan -1..1 picks the lane. vol 0..1 sets size and brightness.
       o: { arg (fills {0}), fake ('backwards' / 'echoing'), edge (light that side's edge), breath } */
    show(key, pan, vol, o) {
      o = o || {};
      if (!save.captions || G.state !== 'night') return;
      let text = this.text(key).replace('{0}', o.arg != null ? o.arg : '');
      if (!text) return;
      if (o.fake) text += ' (' + o.fake + ')'; // what the sound itself says: the dream is lying
      const v = clamp(vol == null ? 1 : vol, 0, 1), lane = pan < -0.3 ? 'L' : pan > 0.3 ? 'R' : 'C';
      const label = lane === 'L' ? '‹ ' + text : lane === 'R' ? text + ' ›' : text;
      const box = this.lanes[lane], now = performance.now() / 1000; // (real time: captions are for your eyes)
      let el = Array.prototype.find.call(box.children, (c) => c.label === label && now - c.at < 1.2);
      if (el) { // the same sound again: "footsteps ×2"
        el.n++; el.firstChild.textContent = label + ' ×' + el.n;
        el.style.animation = 'none'; void el.offsetWidth; el.style.animation = '';
      } else {
        el = document.createElement('div'); el.className = 'cap'; el.label = label; el.n = 1;
        const s = document.createElement('span'); s.textContent = label; el.appendChild(s);
        box.appendChild(el);
        while (box.children.length > 3) box.firstChild.remove();
      }
      el.at = now; el.style.setProperty('--v', v.toFixed(2));
      if (o.edge && lane !== 'C') this.glow(lane === 'L' ? 'left' : 'right', v, o.breath);
    },
    /* one soft rise and fade at that edge (it never blinks, so it stays on with every Dream effects setting) */
    glow(side, v, breath) {
      const el = this.edges[side];
      el.style.transition = 'none'; el.style.opacity = (0.25 + 0.5 * v).toFixed(2);
      void el.offsetWidth; el.style.transition = ''; el.style.opacity = 0;
      if (breath && G.cams.up) pulseCls(hudEls.you, side === 'left' ? 'breathL' : 'breathR'); // on the map: breathing at YOUR door
    },
    clear() {
      this.box.classList.remove('paused');
      for (const k in this.lanes) this.lanes[k].textContent = '';
      for (const k in this.edges) { this.edges[k].style.transition = 'none'; this.edges[k].style.opacity = 0; }
    },
  };

  /* the night's story, for the death screen: every threat sound (see cue) and what you did about it.
     { t, kind, side, who, … } — kinds: steps / breath / bang / far / whisper (sounds; fake = a lie), reach (it got
     to a door), door, light, pinch, lunge, gasp, in (it came in). Only the last LOG_MAX are kept. */
  const LOG_MAX = 80;
  function logStory(e) { e.t = G.nightT; G.cueLog.push(e); if (G.cueLog.length > LOG_MAX) G.cueLog.shift(); }
  const atDoor = (side) => G.monsters.find((m) => m.state === 'door' && m.door === side) || null;

  /* every threat sound: cue('breath', 'left', { monster, vol, rate, lowpass, pan, fake, cap }).
     side: 'left' / 'right' / anything else = o.pan. cap: which caption (default: the kind). */
  function cue(kind, side, o) {
    o = o || {};
    const own = o.monster && o.monster.def.sounds && o.monster.def.sounds[kind];
    const name = own && Sound.has(own) ? own : CUE[kind];
    const opts = { vol: o.vol == null ? 1 : o.vol, rate: o.rate || 1, pan: sidePan(side, o.pan), lowpass: o.lowpass || 0 };
    const back = o.fake && Sound.reversed(name); // the dream lies: it plays backwards
    let h;
    if (back) h = Sound.play(back, opts);
    else if (o.fake) {                            // file mode can't reverse: slower, with an echo
      const slow = Object.assign({}, opts, { rate: opts.rate * 0.8 });
      h = Sound.play(name, slow);
      after(0.14, () => Sound.play(name, Object.assign({}, slow, { vol: slow.vol * 0.45 })));
    } else h = Sound.play(name, opts);
    logStory({ kind, side: side || null, fake: !!o.fake, trick: !!o.trick, who: o.monster ? o.monster.id : null, cap: o.cap || kind });
    Captions.show(o.cap || kind, opts.pan, opts.vol, { fake: o.fake ? (back ? 'backwards' : 'echoing') : null,
      edge: THREAT.indexOf(kind) >= 0, breath: kind === 'breath' });
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
    for (const { id: start } of CFG.cameras) {
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
  /* which of your doors a monster's path ever reaches: { left: true, right: false } */
  function doorsOf(def) {
    const out = { left: false, right: false };
    for (const from in def.path || {}) for (const to of def.path[from]) if (isDoor(to)) out[to.slice(5)] = true;
    return out;
  }
  /* nobody is at a door or inside, and every walker is at least minDist steps away */
  function calm(minDist) { return G.monsters.every((m) => m.state === 'roam' && doorDist(m.def, m.room) >= minDist); }

  /* later nights it walks quietly: footsteps play only some of the time (rule stepChance). Breathing never skips. */
  const quietSteps = () => Math.random() < rule('stepChance', 1) + (G.lighter ? LIGHTER.steps : 0);
  /* a monster walks into a room (or up to a door) */
  function arrive(m, next, viewing) {
    const from = m.room;
    const trick = brainOf(m).stepSide; // (a trickster's footsteps come from the wrong side)
    if (isDoor(next)) {
      const side = next.slice(5);
      m.state = 'door'; m.door = side; m.room = null; m.seen = false; m.doorT = 0; m.breathed = false; m.hurry = false;
      m.linger = rand(m.def.waitAtDoor[0], m.def.waitAtDoor[1]);
      m.breathT = rand(0.6, 1.6); // (its first breath: it can't come in before that, see walkerMove)
      logStory({ kind: 'reach', side, who: m.id });
      if (quietSteps()) cue('steps', trick ? trick(side) : side, { monster: m, vol: 0.75, cap: 'stepsNear', trick: !!trick });
    } else {
      m.room = camById[next] ? next : m.def.start;
      if (doorDist(m.def, m.room) === 1) {
        startWindowPass(m); // its shadow crosses the window: it has reached a side hall
        if (quietSteps()) cue('steps', null, { monster: m, vol: 0.5, pan: (camById[m.room].map.x - 0.5) * 1.6 * (trick ? -1 : 1), lowpass: 2400 });
      }
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

  /* a loud noise in your room: kind 'pinch' (you) or 'bang' (something hit a shut door). Each monster's brain
     decides what it does about it (see walkerHear). Asleep-all-night monsters (level 0) never hear anything. */
  function noise(kind, radius) {
    if (G.inside) return;
    for (const m of G.monsters) {
      if (m.level <= 0) continue;
      if (G.freeze) { if (kind === 'pinch') m.alerted = true; continue; } // (the False Dawn holds everything still: it comes once it is over)
      (brainOf(m).hear || walkerHear)(m, kind, radius);
    }
  }

  /* ------------------------------------------------------------------ */
  /*  MONSTER BRAINS: config.js behavior: "walker" (the default),        */
  /*  "shy", "sleeper" or "trickster". A brain can change how its        */
  /*  monster moves (move), what it does every moment (tick), how it     */
  /*  hears a noise (hear), how it looks on a camera (drawCam) and where  */
  /*  its footsteps seem to come from (stepSide). Whatever it leaves out  */
  /*  works like the walker. Every brain keeps the promise: at your door  */
  /*  it always breathes first (see walkerMove).                          */
  /* ------------------------------------------------------------------ */
  /* the walker (Redhorn): along its path, room by room; at your door it waits, then comes in, or bangs and leaves.
     Returns false when it didn't really move (still waiting at the door). */
  function walkerMove(m) {
    const viewing = G.cams.up ? G.cams.cur : null;
    if (m.state === 'roam') { arrive(m, pick(optionsFrom(m.def, m.room)), viewing); return true; }
    if (m.state !== 'door') return false;
    if (m.linger > 0) return false; // still waiting: a pinch alert stays saved for its next chance
    if (!m.breathed || m.doorT < minWarning()) return false; // the promise: it always breathes at your door first, and gives you time
    if (G.doors[m.door].closed) {
      bangDoor(m.door, m);
      m.state = 'roam'; m.door = null;
      m.room = pick(m.def.retreat.length ? m.def.retreat : [m.def.start]);
      if (viewing === m.room) camDisrupt();
    } else enterOffice(m);
    return true;
  }
  /* how a walker hears a pinch: near a door it steps closer at once (up to `radius` rooms away), waiting at a door
     it stops waiting (at an OPEN door that means it comes in), and the rest move at their next chance.
     It doesn't mind banging. */
  function walkerHear(m, kind, radius) {
    if (kind !== 'pinch') return;
    if (m.state === 'roam' && doorDist(m.def, m.room) <= radius) stepToward(m); // (stepToward shakes a camera that is watching)
    else if (m.state === 'door') {
      m.linger = Math.min(m.linger, 0.8); m.alerted = true;
      // you pinched while it BREATHED at an OPEN door: it comes in the moment it may (still never before minWarning)
      if (m.breathed && !G.doors[m.door].closed) m.hurry = true;
    } else m.alerted = true;
  }
  /* you are watching it on a camera right now */
  const watchedNow = (m) => G.cams.up && G.cams.lost <= 0 && m.state === 'roam' && m.room === G.cams.cur;

  const SHY = { every: 15, add: 2 };   // every 15 s you don't look at a shy one, it gets 2 levels braver
  const SLEEPER = { awake: 6 };       // seconds a noise keeps a sleeper awake
  const BRAINS = {
    walker: {},
    /* shy: it can't move while you watch it (it freezes, even its animation). Each 15 s you don't, it gets braver.
       Counter: keep glancing at it. (Staring doesn't make it step closer: it's shy.) */
    shy: {
      noStare: true,
      tick(m, dt) {
        const seen = watchedNow(m);
        if (seen) m.ignored = 0; else if (G.grace <= 0) m.ignored += dt;
        m.animSpeed = seen ? 0 : 1;
        m.extra = SHY.add * Math.floor(m.ignored / SHY.every);
      },
      move: (m, forced) => (forced || !watchedNow(m) ? walkerMove(m) : false),
      hear(m, kind, radius) { if (!watchedNow(m)) walkerHear(m, kind, radius); else if (kind === 'pinch') m.alerted = true; },
    },
    /* sleeper: it sleeps where it stands until a noise (a pinch, a bang) wakes it. Then it takes one step at once
       and stays awake 6 s. Once at your door it acts like a walker. Counter: play quietly. */
    sleeper: {
      tick(m, dt) { m.awake = Math.max(0, m.awake - dt); },
      move: (m, forced) => (forced || m.awake > 0 || m.state === 'door' ? walkerMove(m) : false),
      hear(m) {
        m.awake = SLEEPER.awake;
        if (m.state === 'roam') stepToward(m);
        else if (m.state === 'door') { m.linger = Math.min(m.linger, 0.8); m.alerted = true; }
      },
      drawCam: (c, m, box, pose, ground) => drawSleeper(c, m, box, pose, ground),
    },
    /* trickster: a walker whose footsteps near your doors come from the WRONG side. Its breathing never lies.
       Counter: trust the breathing, the light and the cameras. */
    trickster: { stepSide: (side) => (side === 'left' ? 'right' : side === 'right' ? 'left' : side) },
  };
  const brainOf = (m) => BRAINS[m.def.behavior] || BRAINS.walker;

  /* at boot: a behavior word the game doesn't know becomes "walker" (and says so); a monster that can never reach
     one of your doors is reported too */
  function validateBrains() {
    const words = Object.keys(BRAINS);
    for (const def of CFG.monsters) {
      if (def.behavior != null && !BRAINS[def.behavior]) {
        const g = didYouMean(def.behavior, words);
        warnCfg(`${def.name} behavior: "${def.behavior}" isn't a brain the game knows` + (g ? `. Did you mean "${g}"? (Using "${g}" for now.)` : `, so it is a walker. The brains are: ${words.join(', ')}.`));
        def.behavior = g || 'walker';
      }
      const awake = (def.levels || [5]).some((v) => v > 0);
      if (awake && doorDist(def, def.start) === Infinity) warnCfg(`${def.name} can never reach your doors from "${def.start}": give its path a "door:left" or "door:right" somewhere it can walk to.`);
    }
  }

  /* a sleeper on a camera: its sleepFrames (config), or its normal frame darker, with z's drifting up from its head */
  function drawSleeper(c, m, box, pose, ground) {
    if (m.awake > 0) { drawMonster(c, m, box, pose, ground); return; }
    meet(m.def);
    const A = m.art, own = A.sleep.length > 0, img = own ? A.sleep[m.frame() % A.sleep.length] : A.soft[m.frame()];
    const p = Object.assign({ x: 0.5, y: 1.02, h: 0.7 }, pose);
    if (ground) footShadow(c, img, box, p, 1);
    drawSprite(c, img, box, p);
    if (!own) drawSprite(c, tinted(img, 'rgba(0,0,0,.4)'), box, p); // (60% brightness: a dark copy over it, made once)
    const r = spriteRect(img, box, p), k = fxMul();
    c.save(); c.font = `${Math.round(r.h * 0.09)}px "Fell SC", serif`; c.textAlign = 'center'; c.fillStyle = '#d8ccff';
    for (let i = 0; i < 3; i++) {
      const u = ((G.t * 0.25 + i / 3) % 1), rise = k ? u : i / 3; // (Dream effects Off: three still z's)
      c.globalAlpha = 0.75 * Math.sin(Math.PI * rise);
      c.fillText('z', r.x + r.w * (0.62 + 0.12 * rise) + Math.sin(G.t + i) * 6 * k, r.y + r.h * (0.12 - 0.2 * rise));
    }
    c.restore();
  }

  /* ------------------------------------------------------------------ */
  /*  NIGHT FLOW                                                        */
  /* ------------------------------------------------------------------ */
  /* falling asleep: each slow blink is [when, how long] (the eyes stay shut after the last one), then the night card */
  const INTRO = {
    full: { dur: 6.4, dips: [[1.3, 0.15], [2.8, 0.25], [4.2, 0.45]], card: 4.6, text: 0.5 },
    retry: { dur: 1.5, dips: [[0.2, 0.1], [0.62, 0.16]], card: 0.7 },  // after "Dream again": one blink, the card, the jolt
  };
  const JOLT_LEAD = 0.6; // hypnic_jolt.mp3 falls for .6 s before its thud, so it starts that early

  /* "Dream lighter" (offered after three deaths on the same night): a fifth less drain, a sleepier monster, more footsteps */
  const LIGHTER = { deaths: 3, drain: 0.8, levels: 3, steps: 0.3 };
  /* n: night number. endless: the Endless Dream. retry: "Dream again" (the short way to fall asleep).
     mode: { practice: the lesson from Extras (progress is never touched), lighter: "Dream lighter" } */
  function startNight(n, endless, retry, mode) {
    mode = mode || {};
    G.night = n; G.endless = !!endless; G.retry = !!retry;
    G.practice = !!mode.practice && !endless; G.lighter = !!mode.lighter && !endless && !G.practice;
    G.nightT = 0; G.hour = 0; G.timeScale = 1; G.paused = false;
    G.luc = 100; G.usage = 1; G.powerOut = false; G.powerT = 0; G.killAt = 0;
    G.doors.left = freshDoor(); G.doors.right = freshDoor();
    G.cams = freshCams();
    G.inside = null; G.insideT = 0; G.pinchCd = 0; G.danger = 0; G.flash = 0; G.clarity = 0; G.punch = null; G.hudLock = 0;
    G.lies = []; G.taught = false;
    G.trauma = 0; G.kick = { x: 0, y: 0 }; G.later = []; G.parts = []; G.cueLog = []; G.glide = null;
    G.settle = 0; G.hush = false; G.frozen = []; G.finale = null;
    document.querySelectorAll('.lucGain').forEach((el) => el.remove());
    G.stats = { bangs: 0, pinches: 0, fakesLit: 0, fakeCloses: 0, minLuc: 100, lunges: 0 };
    G.spend = { base: 0, doors: 0, lights: 0, cams: 0 }; G.litAt = { left: -1e9, right: -1e9 }; G.powerAt = 0;
    resetLesson(); voiceLog.length = 0;
    G.whisperT = rand(18, 40); G.killer = null; G.jumpT = 0; G.preScare = 0; G.scare = null;
    G.roomP = 0; G.lampDim = 0; G.windowPass = null; G.clockSpin = 0; G.clockSkew = 0; G.tickShown = false;
    resetDirector(true);
    roomsIn(); // (or, on a slow connection, once the rooms are in: beginNight waits for them with your eyes shut)
    if (ghostCam()) { hide(ghostCam()); delete camById._you; }
    G.monsters = CFG.monsters.map((def) => {
      const m = new Monster(def);
      if (endless) m.level = clamp(save.custom[def.id] != null ? save.custom[def.id] : 10, 0, 20);
      else m.level = (def.levels || [])[n - 1] != null ? def.levels[n - 1] : (def.levels || [5]).slice(-1)[0];
      if (G.lighter && m.level > 0) m.level = Math.max(1, m.level - LIGHTER.levels); // (sleepier, but still awake)
      return m;
    });
    G.grace = n === 1 && !endless ? 22 : 10;
    G.lieT = nextLieIn();
    Sound.resume();
    Sound.stopAll();
    hideScreens(); resetHud(); Captions.clear(); G.voice.active = false;
    // you fall asleep in your own bedroom (the night card comes once your eyes are shut)
    G.state = 'asleep'; G.introT = 0; G.introDur = (retry ? INTRO.retry : INTRO.full).dur;
    G.cardShown = false; G.joltPlayed = false; G.tickPh = -0.16;
    setHtml($('#cardNight'), null, numify(endless ? 'Endless Dream' : 'Night ' + n));
    setHtml($('#cardTime'), null, numify('12:00 AM' + (G.practice ? ' · a practice dream' : G.lighter ? ' · a lighter dream' : '')));
    $('#nightCard').classList.remove('fade');
    G.sleepBreath = retry ? null : Sound.play('breathing', { vol: 0.25, lowpass: 600, rate: 0.8 }); // your own sleepy breath
  }
  /* the desk room's width and the starting look (the middle of the room) */
  function roomsIn() {
    G.roomsLate = !Art.office;
    if (G.roomsLate) { G.officeW = W; G.scroll = 0; return; }
    G.officeW = officeWidthFor(Art.office);
    G.scroll = Math.max(0, (G.officeW - W) / 2);
  }
  /* the HUD back to normal and hidden (between nights) */
  function resetHud() {
    const hud = $('#hud');
    hud.classList.remove('fadeOut', 'dissolve', 'onlyVoice');
    hudEls.time.classList.remove('dawn');
    hide(hud); hide($('#voiceBox'));
  }

  /* how open your eyes are while you fall asleep (1 open, 0 shut) */
  function lidOpen(t) {
    const dips = (G.retry ? INTRO.retry : INTRO.full).dips;
    if (t >= dips[dips.length - 1][0]) return 0;
    let o = 1;
    for (const [at, w] of dips) o -= Math.exp(-(((t - at) / w) ** 2));
    return clamp(o, 0, 1);
  }
  function updateAsleep(dt) {
    const P = G.retry ? INTRO.retry : INTRO.full;
    G.introT += dt;
    clockTick(dt, 0.5, 1, 0.5);
    if (!G.cardShown && G.introT >= P.card) showNightCard(G.retry ? 0.5 : 1.2);
    if (!G.joltPlayed && G.introT >= G.introDur - JOLT_LEAD && Sound.has('hypnic_jolt')) { G.joltPlayed = true; Sound.play('hypnic_jolt', { vol: 0.9 }); }
    if (G.introT >= G.introDur) {
      if (Art.restReady) beginNight();
      else G.introT = G.introDur; // (a slow connection: the rooms are still loading; your eyes stay shut until they are in)
    }
  }
  /* "Night 3 · 12:00 AM" fades in behind your closed eyes */
  function showNightCard(fadeIn) {
    const card = $('#nightCard'), inner = card.querySelector('.cardInner');
    G.cardShown = true;
    card.classList.remove('fade'); show(card);
    inner.style.animation = 'none'; void inner.offsetWidth; inner.style.animation = ''; inner.style.animationDuration = fadeIn + 's';
    Sound.play('hour_chime', { vol: 0.6, rate: 0.8 });
  }
  /* a click, tap or key while you fall asleep skips to the jolt */
  function skipIntro() { G.introT = Math.max(G.introT, G.introDur - 0.4); }

  /* the hypnic jolt: you fall into the dream and land in the desk room */
  function beginNight() {
    const card = $('#nightCard'), hud = $('#hud');
    if (G.roomsLate) roomsIn(); // (the rooms came in while you fell asleep)
    card.classList.add('fade');
    G.state = 'night'; G.settle = 1.2;
    Sound.stopLoop('clock_tick', 0.3);
    if (G.sleepBreath) { G.sleepBreath.stop(0.4); G.sleepBreath = null; } // (a skipped intro: no uncaptioned breath in the night)
    if (!G.joltPlayed) { // (the real jolt sound already started a moment ago; its stand-in is a deep, muffled bang)
      G.joltPlayed = true;
      Sound.playAny(['hypnic_jolt'], { vol: 0.9 }) || Sound.play('door_bang', { rate: 0.55, lowpass: 260, vol: 0.8 });
    }
    hit(0.5);
    hud.classList.remove('enter'); void hud.offsetWidth; hud.classList.add('enter');
    show(hud);
    updateHud(true);
    const voice = CFG.dreamVoice || {};
    if (wantLesson(G.night, G.endless, G.retry)) startLesson();
    else startVoice(G.endless ? voice.endless : voice[G.night], { then: G.endless ? null : (voice.after || {})[G.night] });
    after(0.5, () => hide(card));
    after(1.6, () => hud.classList.remove('enter')); // (or the voice box would fade in that slowly every time it comes back)
  }

  /* the wind-up clock ticking (falling asleep, Lucidity zero). rate 1 = a tick a second; fade: seconds to fade in.
     Without clock_tick.mp3 a soft, low click plays on every tick instead. */
  function clockTick(dt, vol, rate, fade) {
    const before = Math.floor(G.tickPh);
    G.tickPh += dt * rate;
    if (Sound.has('clock_tick')) Sound.loop('clock_tick', vol, { music: false, rate, fade: fade || 0.3 });
    else if (Math.floor(G.tickPh) !== before) Sound.play('ui_click', { vol: vol * 0.6, rate: 0.42 * rate + (before % 2 ? 0.06 : 0) });
  }

  /* ----- THE DREAM VOICE speaks in beats: a blank line in config.js starts the next one. Each beat types itself
     out with a typewriter's clack, stays long enough to read, then the next one comes. A click on the box (or
     Enter) finishes the typing or goes on; "skip" ends it. Two tricks inside the text:
       {wrong|right}  it types the wrong words in a red, dripping hand, stops, rubs them out and writes the right ones
       {A}            a key to press, shown like the keys on the buttons (left out on touch screens) ----- */
  const VOICE = { cps: 38, delCps: 70, wrongWait: 0.55, hold: 1.5, perChar: 0.05, after: 20, retry: 5 };
  const VOICE_TOKEN = /\{([^{}|]*)\|([^{}]*)\}|\{([^{}|]+)\}/g; // {wrong|right} or {KEY}
  const freshVoice = () => ({ active: false, beats: [], bi: 0, ops: [], oi: 0, acc: 0, segs: [], final: [], typing: false, hold: 0, holdFor: 0, n: 0 });
  /* the night's beats, for the pause screen ("What the voice said") */
  const voiceLog = [];

  /* one beat -> what the typewriter does (ops), the text it ends with (final) and what the pause screen shows (log).
     A segment is { s, cls }: cls 'txt' (plain), 'bad' (the dream's words), 'key' (a key hint). */
  function compileBeat(text) {
    const ops = [], final = [], log = [];
    const add = (list, s, cls) => { const l = list[list.length - 1]; if (l && l.cls === cls && cls !== 'key') l.s += s; else if (s) list.push({ s, cls }); };
    const plain = (s) => { if (!s) return; ops.push({ k: 'type', s, cls: 'txt', i: 0 }); add(final, s, 'txt'); add(log, s, 'txt'); };
    if (TOUCH) text = text.replace(/\s*\{[^{}|]+\}/g, ''); // no keyboard: no key hints
    let at = 0, mm;
    VOICE_TOKEN.lastIndex = 0;
    while ((mm = VOICE_TOKEN.exec(text))) {
      plain(text.slice(at, mm.index)); at = VOICE_TOKEN.lastIndex;
      if (mm[3] != null) { ops.push({ k: 'key', s: mm[3].trim() }); add(final, mm[3].trim(), 'key'); add(log, mm[3].trim(), 'key'); continue; }
      const wrong = mm[1], right = mm[2];
      if (wrong) {
        ops.push({ k: 'type', s: wrong, cls: 'bad', i: 0 }, { k: 'wait', t: VOICE.wrongWait }, { k: 'del', n: wrong.length, i: 0 });
        add(log, wrong, 'bad');
      }
      plain(right);
    }
    plain(text.slice(at));
    return { ops, final, log, len: final.reduce((a, g) => a + g.s.length, 0) };
  }
  const segHtml = (g) => g.cls === 'bad' ? '<span class="intrude">' + escapeHtml(g.s) + '</span>' : g.cls === 'key' ? '<kbd>' + escapeHtml(g.s) + '</kbd>' : escapeHtml(g.s);

  /* text: the words (beats split by blank lines). o: { hold: seconds the LAST beat stays (default: long enough to read),
     stay: the last beat stays until something else ends it (the lesson), then: words that come back later (dreamVoice.after) }.
     A plain number for o still means hold. */
  function startVoice(text, o) {
    o = typeof o === 'number' ? { hold: o } : (o || {});
    const box = hudEls.voice;
    const beats = String(text || '').split(/\n\s*\n/).map((s) => s.trim().replace(/\s*\n\s*/g, ' ')).filter(Boolean); // (one line break inside a beat is a space)
    if (!beats.length) { hide(box); G.voice.active = false; return; }
    G.voice = Object.assign(freshVoice(), { active: true, beats, lastHold: o.hold, stay: !!o.stay, then: o.then || null });
    beginBeat(0);
    show(box); box.style.transition = ''; box.style.opacity = 1;
  }
  function beginBeat(i) {
    const v = G.voice, c = compileBeat(v.beats[i]);
    Object.assign(v, { bi: i, ops: c.ops, final: c.final, len: c.len, oi: 0, acc: 0, segs: [], typing: true, hold: 0, n: 0 });
    voiceLog.push(c.log);
    drawVoice();
  }
  /* the typewriter: it works through the ops on a time budget (typing, waiting, rubbing out) */
  function updateVoice(dt) {
    const v = G.voice;
    if (!v.typing) {
      if (v.stay && v.bi === v.beats.length - 1) return; // the lesson decides when this one is over
      if ((v.hold += dt) >= v.holdFor) nextBeat();
      return;
    }
    v.acc += dt;
    let clack = 0, changed = false;
    while (v.typing) {
      const op = v.ops[v.oi];
      if (!op) { finishBeat(); changed = true; break; }
      if (op.k === 'wait') { const use = Math.min(v.acc, op.t); op.t -= use; v.acc -= use; if (op.t > 0) break; v.oi++; continue; }
      const cost = 1 / (op.k === 'del' ? VOICE.delCps : VOICE.cps);
      if (v.acc < cost) break;
      v.acc -= cost; changed = true;
      if (op.k === 'del') { popChar(v.segs); clack = 0.7; if (++op.i >= op.n) v.oi++; }
      else if (op.k === 'key') { v.segs.push({ s: op.s, cls: 'key' }); v.oi++; clack = clack || 1; }
      else {
        const l = v.segs[v.segs.length - 1], ch = op.s[op.i++];
        if (l && l.cls === op.cls) l.s += ch; else v.segs.push({ s: ch, cls: op.cls });
        if (++v.n % 2 === 0) clack = clack || 1; // every second letter clacks
        if (op.i >= op.s.length) v.oi++;
      }
    }
    if (clack) Sound.play('type_key', { vol: 0.12, rate: clack < 1 ? 0.7 : rand(0.9, 1.15) }); // (silent without type_key.mp3)
    if (changed) drawVoice();
  }
  function popChar(segs) {
    const l = segs[segs.length - 1];
    if (!l) return;
    l.s = l.s.slice(0, -1);
    if (!l.s) segs.pop();
  }
  /* the beat is fully written (the wrong words already gone); it stays long enough to read */
  function finishBeat() {
    const v = G.voice;
    v.typing = false; v.segs = v.final.map((g) => Object.assign({}, g)); v.hold = 0;
    v.holdFor = v.bi === v.beats.length - 1 && v.lastHold ? v.lastHold : VOICE.hold + VOICE.perChar * v.len;
  }
  function nextBeat() { if (G.voice.bi + 1 < G.voice.beats.length) beginBeat(G.voice.bi + 1); else if (!G.voice.stay) endVoice(); }
  /* a click on the voice box, or Enter: finish the typing, or go on to the next beat */
  function voiceAdvance() {
    const v = G.voice;
    if (!v.active) return;
    if (v.typing) { finishBeat(); drawVoice(); } else nextBeat();
  }
  function drawVoice() {
    const v = G.voice, caret = v.typing || !v.stay ? '<span class="caret">▌</span>' : '';
    $('#voiceText').innerHTML = '<span>' + v.segs.map(segHtml).join('') + caret + '</span>'; // one inline run: the caret follows the last letter
  }
  function endVoice() {
    const v = G.voice;
    if (v.active && v.then && G.state === 'night' && !G.powerOut) { const t = v.then; after(VOICE.after, () => voiceAfter(t)); }
    v.active = false;
    const box = hudEls.voice;
    box.style.transition = 'opacity .8s'; box.style.opacity = 0;
    setTimeout(() => { if (!G.voice.active) { hide(box); box.style.transition = ''; } }, 850); // (only hides the faded box)
  }
  /* config dreamVoice.after: a while after the night's voice has gone quiet, it speaks once more */
  function voiceAfter(text) {
    if (G.state !== 'night' || G.powerOut) return;
    if (G.voice.active || G.lesson || G.fd) { after(VOICE.retry, () => voiceAfter(text)); return; } // not over someone else
    startVoice(text);
  }
  /* the pause screen's "What the voice said" */
  function fillVoiceLog() {
    const box = $('#pVoice');
    setCls(box, 'hidden', !voiceLog.length);
    $('#pVoiceLog').innerHTML = voiceLog.map((parts) => '<p>' + parts.map((g) => g.cls === 'bad' ? '<s>' + escapeHtml(g.s) + '</s>' : segHtml(g)).join('') + '</p>').join('');
  }

  /* ----- THE FIRST-NIGHT LESSON (Night 1, until you have finished or skipped it once; Extras can replay it).
     The voice says one step at a time and waits until you have done it. The clock waits too, the monster sleeps,
     and only what you use costs Lucidity. A dashed ring shows what to press. After 15 s the ring pulses;
     after 25 s the lesson moves on by itself. config.js "tutorial" can change the steps. ----- */
  const LESSON = [
    { say: 'Look to your left.', wait: 'lookLeft' },
    { say: 'That doorway. Turn on the light. {A}', wait: 'light' },
    { say: 'Now the other side.', wait: 'lookRight' },
    { say: 'Open the cameras. {SPACE}', wait: 'cams' },
    { say: 'Find the West Hall. It is right outside your left door.', wait: 'cam:west' },
    { say: 'Close the cameras. Shut a door and watch your Lucidity. {Q}', wait: 'door' },
    { say: 'Doors are like holding your breath. Open it again.', wait: 'doorOpen' },
    { say: 'If you\'re slipping, pinch yourself. But it hears you. {F}', wait: 'time:4', point: 'pinch' },
    { say: 'Make it to six. Listen for breathing at the doors.', wait: 'time:4', point: 'clock' },
  ];
  /* read: seconds a written step stays before it can move on; watch: seconds you watch your Lucidity with a door shut;
     hint / auto: the ring pulses / the step moves on by itself; floor: the lesson can't take your Lucidity below this */
  const LESSON_T = { read: 0.6, watch: 2.5, hint: 15, auto: 25, floor: 80 };
  /* the steps from config.js (or the built-in ones), without any that can't work here (a camera that doesn't exist) */
  function lessonSteps() {
    const own = Array.isArray(CFG.tutorial) ? CFG.tutorial : LESSON;
    return own.filter((s) => s && s.say && !(/^cam:/.test(s.wait || '') && !camById[s.wait.slice(4)]));
  }
  const wantLesson = (n, endless, retry) => n === 1 && !endless && !retry && (G.practice || !save.tutorialDone) && lessonSteps().length > 0;
  function startLesson() {
    G.lesson = { steps: lessonSteps(), i: -1 };
    $('#voiceSkip').textContent = 'skip lesson ▸';
    lessonStep(0);
  }
  function lessonStep(i) {
    const L = G.lesson;
    if (i >= L.steps.length) { endLesson(false); return; }
    Object.assign(L, { i, t: 0, read: 0, met: 0, born: G.t });
    G.did = {};
    startVoice(L.steps[i].say, { stay: true });
  }
  /* skipped: the "skip lesson" button (the usual Night 1 voice plays instead, so nobody starts with nothing) */
  function endLesson(skipped) {
    if (!G.lesson) return;
    G.lesson = null; G.grace = 10;
    save.tutorialDone = true; writeSave(); // (finished or skipped: it doesn't come back by itself)
    hide($('#clockNote')); hideCoach();
    $('#voiceSkip').textContent = 'skip ▸';
    if (G.voice.active) endVoice();
    if (skipped && !G.practice) startVoice((CFG.dreamVoice || {})[1]);
  }
  /* no lesson any more (a new night, the menu, a scare) */
  function resetLesson() {
    G.lesson = null; G.did = {};
    hideCoach(); hide($('#clockNote'));
    $('#voiceSkip').textContent = 'skip ▸';
  }
  /* has the player done what this step asks? */
  function lessonMet(step) {
    const w = String(step.wait || 'time:4'), max = Math.max(0, G.officeW - W), L = G.doors.left, R = G.doors.right;
    if (w === 'lookLeft') return !G.cams.up && (max <= 0 || G.scroll <= 0.15 * max);
    if (w === 'lookRight') return !G.cams.up && (max <= 0 || G.scroll >= 0.85 * max);
    if (w === 'light') return G.did.light || L.light || R.light;
    if (w === 'cams') return G.cams.up && G.cams.t >= 1;
    if (w.indexOf('cam:') === 0) return G.cams.up && G.cams.t >= 1 && G.cams.cur === w.slice(4);
    if (w === 'door') return G.did.door || L.closed || R.closed;
    if (w === 'doorOpen') return !L.closed && !R.closed;
    if (w === 'pinch') return !!G.did.pinch;
    return true; // time:N (see lessonUpdate)
  }
  function lessonUpdate(realDt) {
    const L = G.lesson, step = L.steps[L.i], w = String(step.wait || 'time:4');
    G.grace = Math.max(G.grace, 8); // it sleeps through the lesson
    L.t += realDt;
    if (!G.voice.typing) L.read += realDt;
    const need = /^time:/.test(w) ? Math.max(0, parseFloat(w.slice(5)) || 4) : LESSON_T.read;
    L.met = lessonMet(step) ? L.met + realDt : 0;
    const watch = w === 'door' ? LESSON_T.watch : 0; // a door shut: the ring moves to your Lucidity for a moment
    if ((L.read >= need && L.met > watch) || L.t >= LESSON_T.auto) {
      if (L.t < LESSON_T.auto && !/^time:/.test(w)) Sound.play('ui_click', { vol: 0.3, rate: 1.35 }); // well done
      lessonStep(L.i + 1);
    }
  }

  /* ----- coach marks: a dashed ring that draws itself around a button (it follows the button every frame), or
     arrows at the edge of the screen when the thing to find is in the room itself ----- */
  const coachEls = { svg: $('#coach'), ring: $('#coach .ring'), draw: $('#coach .draw'), wob: $('#coach .wob'), edge: $('#coachEdge'), drag: $('#coachDrag') };
  const coach = { x: W / 2, y: H / 2, rx: 60, ry: 40, el: null, born: 0 };
  function defaultPoint(step) {
    const w = String(step.wait || '');
    if (w === 'lookLeft') return 'left';
    if (w === 'lookRight') return 'right';
    if (w === 'light') return 'leftLight';
    if (w === 'cams') return 'cameras';
    if (w.indexOf('cam:') === 0) return w;
    if (w === 'door') return G.lesson && G.lesson.met > 0 ? 'lucidity' : 'leftDoor'; // shut: now watch what it costs
    if (w === 'doorOpen') return G.doors.right.closed && !G.doors.left.closed ? 'rightDoor' : 'leftDoor';
    if (w === 'pinch') return 'pinch';
    return 'none';
  }
  /* what to point at right now: { el } (a button), { edge: 'left' / 'right' } or null. Anything hidden behind the
     cameras points at the camera bar instead ("close the cameras first"). */
  function coachTarget(step) {
    const p = String(step.point || defaultPoint(step)), camsUp = G.cams.t > 0.5;
    if (p === 'none') return null;
    if (p === 'left' || p === 'right') return camsUp ? { el: hudEls.camBar } : { edge: p };
    let el;
    if (p.indexOf('cam:') === 0) el = camsUp ? document.querySelector('#camMap .camBtn[data-cam="' + p.slice(4).replace(/["\\]/g, '') + '"]') : hudEls.camBar;
    else el = { leftLight: hudEls.lLight, rightLight: hudEls.rLight, leftDoor: hudEls.lDoor, rightDoor: hudEls.rDoor,
      cameras: hudEls.camBar, pinch: hudEls.pinch, lucidity: hudEls.lucBox, clock: $('#clockBox') }[p];
    if (!el || !el.getClientRects().length) return camsUp ? { el: hudEls.camBar } : null;
    return { el };
  }
  function hideCoach() { hide(coachEls.svg); hide(coachEls.edge); hide(coachEls.drag); coach.el = null; }
  function updateCoach(dt) {
    const L = G.lesson;
    const tgt = L && G.state === 'night' && !G.paused ? coachTarget(L.steps[L.i]) : null;
    const urgent = !!L && L.t >= LESSON_T.hint, k = fxMul();
    // arrows at the edge (and on touch screens a finger showing which way to drag the room)
    const edge = tgt && tgt.edge;
    setCls(coachEls.edge, 'hidden', !edge); setCls(coachEls.drag, 'hidden', !edge || !TOUCH);
    if (edge) {
      setCls(coachEls.edge, 'right', edge === 'right'); setCls(coachEls.drag, 'right', edge === 'right');
      setCls(coachEls.edge, 'urgent', urgent);
      coachEls.edge.querySelector('b').textContent = edge === 'left' ? '‹ ‹ ‹' : '› › ›';
      coachEls.edge.querySelector('span').textContent = TOUCH ? 'look ' + edge : edge === 'left' ? 'mouse here, or ←' : 'mouse here, or →';
      coachEls.drag.querySelector('span').textContent = edge === 'left' ? 'drag the room →' : '← drag the room'; // (the room follows your finger)
    }
    if (!tgt || !tgt.el) { hide(coachEls.svg); coach.el = null; return; }
    // the ring: glides to its button, draws itself in, wobbles a little, pulses once the step has waited a while
    const r = tgt.el.getBoundingClientRect();
    const x = (r.left + r.width / 2 - stageX) / stageScale, y = (r.top + r.height / 2 - stageY) / stageScale;
    const rx = Math.max(40, r.width / stageScale / 2 + 22), ry = Math.max(30, r.height / stageScale / 2 + 18);
    if (coach.el !== tgt.el) { // a new target: it jumps there (a new step) and draws itself in again
      if (!coach.el || coachEls.svg.classList.contains('hidden')) Object.assign(coach, { x, y, rx, ry });
      coach.el = tgt.el; coach.born = G.t;
    }
    const f = 1 - Math.exp(-14 * dt);
    coach.x = lerp(coach.x, x, f); coach.y = lerp(coach.y, y, f); coach.rx = lerp(coach.rx, rx, f); coach.ry = lerp(coach.ry, ry, f);
    const pulse = urgent ? 0.5 + 0.5 * Math.sin(G.t * Math.PI * 2 * 0.8) : 0; // .8 Hz: a slow breath, never a flicker
    const grow = 1 + 0.07 * pulse * k;
    const a = coach.rx * grow, b = coach.ry * grow;
    const per = Math.PI * (3 * (a + b) - Math.sqrt((3 * a + b) * (a + 3 * b))); // (Ramanujan's ellipse perimeter)
    const drawn = save.fx === 'off' ? 1 : ease(clamp((G.t - coach.born) / 0.6, 0, 1));
    for (const e of [coachEls.ring, coachEls.draw]) { e.setAttribute('cx', coach.x.toFixed(1)); e.setAttribute('cy', coach.y.toFixed(1)); e.setAttribute('rx', a.toFixed(1)); e.setAttribute('ry', b.toFixed(1)); }
    coachEls.draw.setAttribute('stroke-dasharray', (per * drawn).toFixed(1) + ' ' + (per + 10).toFixed(1));
    coachEls.wob.setAttribute('transform', `rotate(${(1.5 * Math.sin(G.t * 2.2) * k).toFixed(2)} ${coach.x.toFixed(1)} ${coach.y.toFixed(1)})`);
    setCls(coachEls.svg, 'urgent', urgent);
    show(coachEls.svg);
  }

  function setDoor(side, closed) {
    const D = G.doors[side];
    if (G.state !== 'night' || G.powerOut || G.paused) return;
    if (G.inside) { // jammed: the dream won't let you
      Sound.play('ui_click', { vol: 0.5, rate: 0.6 });
      pulseCls(side === 'left' ? hudEls.lDoor : hudEls.rDoor, 'deny');
      return;
    }
    if (D.closed === closed) return;
    D.closed = closed; // the state changes at once; the shutter only shows it (see moveDoor)
    G.did[closed ? 'door' : 'doorOpen'] = true;
    const there = atDoor(side);
    logStory({ kind: 'door', side, closed, there: there ? there.id : null });
    if (closed) for (const L of G.lies) if (L.kind === 'door' && L.side === side && !L.shut) { L.shut = true; G.stats.fakeCloses++; } // it cost you Lucidity, nothing more
    if (closed) { D.v = Math.max(D.v, 1.5); D.landed = false; }
    Sound.play(closed ? 'door_close' : 'door_open', { vol: 0.85, pan: side === 'left' ? -0.7 : 0.7 });
  }
  function setLight(side, on) {
    if (G.state !== 'night' || G.powerOut || G.paused || G.cams.up) return;
    const other = side === 'left' ? 'right' : 'left';
    if (on) G.doors[other].light = false;
    G.doors[side].light = on;
    if (on) {
      G.glide = side; // turn the view toward that doorway so you can see what the light shows
      G.did.light = true;
      const there = atDoor(side);
      logStory({ kind: 'light', side, there: there ? there.id : null });
    }
    Sound.play('ui_click', { vol: 0.35, rate: on ? 1 : 0.8, pan: side === 'left' ? -0.6 : 0.6 });
  }
  function toggleCams(force) {
    if (G.state !== 'night' || G.paused) return;
    const want = force != null ? force : !G.cams.up;
    if (want && (G.powerOut || G.inside)) return; // can't hide in the cameras once it's in the room
    if (want === G.cams.up) return;
    G.cams.up = want;
    if (want) G.did.cams = true;
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
    for (const L of G.lies) if (L.kind === 'cam' && L.room === G.cams.cur) L.ttl = 0; // look away from a lie and it's gone
    youCamSwitch(G.cams.cur, id);
    G.cams.cur = id; G.cams.staticAmt = 1; G.did.cam = id;
    Sound.play('cam_switch', { vol: 0.7, rate: rand(0.95, 1.05) });
    updateCamUi();
  }
  /* how much Lucidity a pinch would give right now: more the deeper you have sunk */
  function pinchGain() {
    const p = pinchCfg();
    return Math.round(p.amount * (G.luc < 30 ? p.lowBonus : G.luc > 60 ? p.highPenalty : 1));
  }
  function pinch() {
    if (G.state !== 'night' || G.paused || G.powerOut) return;
    if (G.pinchCd > 0) { pulseCls(hudEls.pinch, 'deny'); return; }
    const gain = pinchGain();
    G.luc = Math.min(100, G.luc + gain);
    G.pinchCd = pinchCfg().cooldown;
    showGain(gain);
    const open = G.monsters.find((m) => m.state === 'door' && !G.doors[m.door].closed); // (breathing at an open door: a bad moment)
    logStory({ kind: 'pinch', side: open ? open.door : null, who: open ? open.id : null });
    G.did.pinch = true;
    noise('pinch', rule('pinchRadius', 2)); // it's loud, and it hears you
    G.flash = save.fx === 'off' ? 0.1 : 0.3; G.flashColor = '230,220,255';
    if (Director.active && Director.active.id !== 'youCam') endEvent(); // the room snaps back to normal
    if (G.lies.length) { // the cure for the dream's lies
      G.lies = [];
      Sound.playAny(['reality_snap'], { vol: 0.8, rate: 0.7 }) || Sound.play('ui_click', { vol: 0.7, rate: 0.5 });
      G.flashColor = '190,170,255';
    }
    G.clarity = 0.6; // the picture snaps sharp, then the dream seeps back in
    G.hudLock = G.t + pinchCfg().cooldown; // … and the HUD's words stop slipping for a while
    pulseCls(hudEls.eye, 'blink');
    pulseCls(hudEls.you, 'ripple'); // on the camera map the noise spreads out from YOU
    hit(0.25);
    G.stats.pinches++;
    Sound.playAny(['reality_snap'], { vol: 0.9 }) || Sound.play('heartbeat', { vol: 0.8, rate: 1.4 });
    Sound.play('heartbeat', { vol: 0.6 });
  }

  function monsterMove(m, forced) {
    if (G.state !== 'night' || G.inside) return;
    if (m.level <= 0 && !forced) return; // level 0 = it never moves tonight
    // after its wait at a SHUT door it always gives up (no endless camping that tempts you to reopen)
    const atShutDoor = m.state === 'door' && m.linger <= 0 && G.doors[m.door].closed;
    if (!(forced || atShutDoor || m.alerted || randi(1, 20) <= m.lvl)) return;
    if ((brainOf(m).move || walkerMove)(m, forced)) m.alerted = false; // (only once a move has really happened)
  }

  /* it slams into a shut door: the door held */
  function bangDoor(side, m) {
    const D = G.doors[side], d = officeDoor(side), dir = side === 'left' ? 1 : -1;
    cue('bang', side, { monster: m, vol: 0.95 });
    D.bangT = 0.6;
    hit(0.35, dir);
    const x = (d.x + d.w / 2) * G.officeW;
    spawnParts(Math.round(14 * fxMul()), { office: true, x, y: d.y * H + 4, spreadX: d.w * G.officeW * 0.5, spreadY: 3,
      vx: 0, vy: 60, jitter: 45, gravity: 650, life: 0.9, r: 2.2, col: 'rgb(214,204,188)' }); // plaster from the frame
    G.stats.bangs++;
    if (G.cams.up) pulseCls(hudEls.you, side === 'left' ? 'bangL' : 'bangR'); // the door buttons are hidden on cameras
    else pulseCls(side === 'left' ? hudEls.lDoor : hudEls.rDoor, 'hit');
    noise('bang', 1);
  }

  function camDisrupt() {
    G.cams.staticAmt = 1;
    G.cams.lost = rand(0.7, 1.3);
    Sound.play('cam_switch', { vol: 0.5, rate: 0.6 });
  }

  function enterOffice(m) {
    logStory({ kind: 'in', side: m.door, who: m.id, doorOpen: !!m.door && !G.doors[m.door].closed, camsUp: G.cams.up, lastLit: m.door ? G.litAt[m.door] : null });
    G.inside = m; m.state = 'inside';
    G.doors.left.light = false; G.doors.right.light = false;
    cue('breath', 'center', { monster: m, vol: 1, rate: 0.9, cap: 'breathClose' });
    if (G.cams.up) { G.cams.forceDown = rand(1.2, 2.6); G.insideT = 99; }
    else G.insideT = insideWait(rand(0.9, 1.7));
  }
  /* seconds from "it's in the room" to the scare. Gentle scares always leave a whole second of darkness first. */
  const insideWait = (t) => (gentle() ? Math.max(t, PRE_SCARE.gentle) : t);

  function powerOutStart() {
    resetDirector(false);
    G.powerOut = true; G.powerT = 0; G.luc = 0; G.powerAt = G.nightT;
    for (const s of ['left', 'right']) {
      if (G.doors[s].closed) Sound.play('door_open', { vol: 0.8, pan: s === 'left' ? -0.7 : 0.7 });
      G.doors[s].closed = false; G.doors[s].light = false;
    }
    if (G.cams.up) { G.cams.up = false; Sound.play('cam_close', { vol: 0.6 }); }
    G.killAt = rand(13, 26);
    const awake = G.monsters.filter((m) => m.level > 0);
    G.killer = awake.length ? pick(awake) : G.monsters.length ? pick(G.monsters) : null; // (one that is awake tonight)
    if (G.inside) { // it is already in the room: the dark doesn't save you
      G.killer = G.inside; G.cams.forceDown = 0;
      G.insideT = clamp(G.insideT, 0.3, 1.7);
      G.killAt = G.insideT + 0.2;
    }
    Sound.play('power_down', { vol: 0.95 });
    Sound.stopLoop('ambience', 0.4); Sound.stopLoop('light_buzz', 0.1); Sound.stopLoop('static', 0.1);
    Sound.stopLoops('presence:', 0.3); Sound.stopLoops('room:', 0.3);
    G.lies = [];
    Captions.show('powerDown', 0, 1);
    if (G.voice.active) endVoice();
    // the controls fall away (only the clock stays); the alarm clock starts to wind down
    $('#hud').classList.add('dissolve');
    G.tickPh = -0.16; G.hush = false;
    after(1.6, () => Captions.show('clockSlow', 0, 0.9));
  }

  /* ----- the jumpscare, in phases: silence, the lunge, the stare, the collapse (no strobe on any setting) ----- */
  /* the pre-scare: seconds of darkness and silence before it gets you (Gentle scares get a whole second) */
  const PRE_SCARE = { normal: 0.45, gentle: 1 };
  /* lunge until .3 s, stare until 1 s, then the picture collapses like an old TV; Gentle: a fade in and out, 1.2 s */
  const JUMP = { lunge: 0.3, stare: 1, end: 1.5, gentleEnd: 1.2, gentleIn: 0.35, gentleOut: 0.85 };
  /* the room has gone silent and dark: no sound beds, no breaths, no groaning doors */
  const silent = () => G.hush || G.preScare > 0;

  /* k 0..1: how dark the room is. The first call cuts every sound, and it breathes once, right next to you. */
  function startPreScare(k) {
    if (!G.preScare) {
      Sound.stopLoops('', 0.05);
      cue('breath', 'center', { monster: G.inside, vol: 0.7, rate: 0.75, cap: 'breathClose' });
    }
    G.preScare = Math.max(G.preScare, k, 0.001);
  }

  function jumpscare(m) {
    if (G.state !== 'night') return;
    const soft = gentle();
    resetDirector(false);
    G.state = 'jumpscare'; G.killer = m; G.jumpT = 0; G.later = []; G.lies = [];
    if (m) meet(m.def);
    resetLesson();
    G.cams.up = false; G.cams.t = 0;
    Captions.clear();
    hide($('#hud')); if (G.voice.active) endVoice();
    Sound.stopAll();
    Sound.play((m && m.def.jumpscareSound) || 'jumpscare', soft ? { vol: 0.5, lowpass: 3000 } : { vol: 1 });
    hit(soft ? 0.35 : 1);
    const n = m ? m.art.jump.length : 1;
    G.scare = { gentle: soft, len: soft ? JUMP.gentleEnd : JUMP.end, fi: m ? m.frame() % n : 0, off: false, tear: [] };
    // Dream effects Full: the picture tears in six bands for a moment (picked once, so it never flickers)
    if (!soft && save.fx === 'full') for (let i = 0; i < 6; i++) { const y = rand(0, H - 40); G.scare.tear.push({ y0: y, y1: y + rand(20, 90), dx: rand(-40, 40) }); }
  }

  function die() {
    G.state = 'dead';
    Sound.stopAll();
    Sound.loop('static', 0.35, { fade: 0.05, music: false });
    setTimeout(() => Sound.stopLoop('static', 1.5), 900); // (the night is over: a plain timer is fine here)
    const story = !G.endless && !G.practice;
    if (story) { save.deaths[G.night] = (save.deaths[G.night] || 0) + 1; writeSave(); } // (waking up clears it)
    const r = G.powerOut ? lucidityRecap() : caughtRecap();
    $('#deadTitle').textContent = G.killer ? (G.killer.def.name.toUpperCase() + ' FOUND YOU') : 'IT FOUND YOU';
    showRecap(r);
    setCls($('#dLighter'), 'hidden', !story || G.lighter || save.deaths[G.night] < LIGHTER.deaths);
    // the buttons wait a moment (like the morning's), so a key or tap still on its way from the scare presses nothing
    if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
    G.deadWait = RECAP.buttons;
    showScreen('#dead');
    $('#dead').classList.add('wait');
  }

  /* ------------------------------------------------------------------ */
  /*  WHAT HAPPENED: the death screen types out the moment you missed  */
  /*  (from the night's story, see logStory) and gives the tip for      */
  /*  exactly that. A Lucidity death shows where your Lucidity went.    */
  /* ------------------------------------------------------------------ */
  const RECAP = { cps: 25, wait: 0.9, buttons: 1.1 }; // wait: the title lands first, then the words come; buttons: when they appear
  const TIPS = {
    cams: 'When you hear breathing, drop the cameras and check your doors.',
    pinch: 'Never pinch with breathing at an open door.',
    opened: 'It was still out there when you opened the door. Wait for the BANG, then open it.',
    stare: 'You stared at it on the cameras, and it stepped closer. It likes that. Look away, and drop the cameras when you hear breathing.',
    gasp: 'Your door ran out of breath and opened by itself. Let your doors rest when nothing is there.',
    light: 'It always breathes before it comes in. Check that light.',
    saw: 'Your light found it. Shut that door right away!',
    other: 'It always breathes before it comes in. Listen for it, then check the light.',
    trick: 'Its footsteps came from the wrong side. Footsteps can lie; breathing never does. Check with the light.',
    // a Lucidity death: the tip for whatever cost you the most
    doors: 'Doors are like holding your breath. Open them again once it bangs, or once the breathing stops.',
    camsSpend: 'The cameras cost Lucidity too. Take a look, then put them down.',
    lights: 'Every light costs Lucidity. Flick it on to check, then off again.',
    base: 'Just being asleep costs Lucidity. Pinch yourself when you are low, but never with breathing at an open door.',
  };
  /* "3:12 AM" for a moment of the night (short: "3:12") */
  function fmtClock(t, short) {
    const hs = hourSec(), h = clamp(Math.floor(t / hs), 0, 5), m = Math.floor((t % hs) / hs * 60);
    return (h === 0 ? 12 : h) + ':' + String(m).padStart(2, '0') + (short ? '' : ' AM');
  }
  /* one moment of the story, in words */
  function storyLine(e) {
    const S = e.side ? String(e.side).toUpperCase() : '';
    switch (e.kind) {
      case 'reach': return `it reached the ${S} door without a sound`;
      case 'steps': return e.side === 'left' || e.side === 'right' ? `footsteps, close, on the ${S}` + (e.trick ? ' (it throws its footsteps)' : '') : 'footsteps in the halls';
      case 'breath': return e.cap === 'breathMuffled' ? `breathing behind the shut ${S} door` : `breathing at the ${S} door`;
      case 'bang': return `BANG on the ${S} door. It held`;
      case 'door': return e.closed ? `you shut the ${S} door` : `you opened the ${S} door` + (e.there ? ' while it was still there' : '');
      case 'light': return e.there ? `your light found it in the ${S} doorway` : `you checked the ${S} light`;
      case 'pinch': return e.who ? `you pinched yourself while it breathed at the open ${S} door` : 'you pinched yourself';
      case 'lunge': return 'you stared at it on the cameras, and it stepped closer';
      case 'gasp': return `the ${S} door ran out of breath and opened by itself`;
      case 'in': return e.doorOpen ? `it came in through the open ${S} door` + (e.camsUp ? ' while you watched the cameras' : '') : 'it came in';
      default: return e.kind;
    }
  }
  /* it got you: its last visit to your door, in up to three lines, and what to do differently */
  function caughtRecap() {
    const log = G.cueLog.filter((e) => !e.fake), K = G.killer && G.killer.id;
    let inAt = -1;
    for (let i = log.length - 1; i >= 0; i--) if (log[i].kind === 'in' && (!K || log[i].who === K)) { inAt = i; break; }
    if (inAt < 0) { // (no visit on record: only the last things it did)
      const last = log.filter((e) => e.who === K && e.kind !== 'far' && e.kind !== 'whisper')
        .filter((e, i, a) => !i || storyLine(e) !== storyLine(a[i - 1])).slice(-3); // (the same thing twice in a row is told once)
      return { lines: last.map((e) => ({ t: e.t, s: storyLine(e) })), tip: TIPS.other };
    }
    const IN = log[inAt], side = IN.side;
    let reach = inAt;
    while (reach > 0 && !(log[reach].kind === 'reach' && log[reach].who === IN.who)) reach--;
    const reachT = log[reach].kind === 'reach' ? log[reach].t : IN.t;
    const visit = log.slice(reach, inAt + 1);
    const warn = visit.find((e) => (e.kind === 'steps' || e.kind === 'breath') && e.who === IN.who) || log[reach];
    const opened = visit.find((e) => e.kind === 'door' && e.side === side && !e.closed && e.there === IN.who);
    const pinched = visit.find((e) => e.kind === 'pinch' && e.who === IN.who);
    const found = visit.find((e) => e.kind === 'light' && e.side === side && e.there === IN.who);
    const before = log.slice(0, reach + 1).filter((e) => IN.t - e.t < 40);
    const lunge = before.filter((e) => e.who === IN.who && (e.kind === 'lunge' || e.kind === 'reach')).slice(-2).find((e) => e.kind === 'lunge');
    const gasp = log.slice(0, inAt).find((e) => e.kind === 'gasp' && e.side === side && IN.t - e.t < 30);
    const neverLit = !(IN.lastLit >= reachT); // its whole visit, that doorway stayed dark
    const breaths = visit.filter((e) => e.kind === 'breath' && e.who === IN.who);
    const askT = (breaths[breaths.length - 1] || warn).t; // when you should have looked
    // the moment that mattered most: what you did, then what the dream did, then what you didn't do
    const key = opened || pinched || lunge || gasp || (neverLit ? { t: askT, s: `you never checked the ${String(side).toUpperCase()} light` } : null)
      || found || (IN.camsUp ? { t: askT, s: 'you were watching the cameras' } : null);
    // in the order they happened (at the same moment, a lunge comes before what it led to, and coming in is last)
    const order = (a, b) => (a.t - b.t) || ((b.kind === 'lunge') - (a.kind === 'lunge')) || ((a === IN) - (b === IN));
    const lines = [warn, key, IN].filter((e, i, a) => e && a.indexOf(e) === i).sort(order).map((e) => ({ t: e.t, s: e.s || storyLine(e) }));
    const tip = pinched ? TIPS.pinch : opened ? TIPS.opened : lunge ? TIPS.stare : gasp ? TIPS.gasp : IN.camsUp ? TIPS.cams
      : warn.trick ? TIPS.trick : neverLit ? TIPS.light : found ? TIPS.saw : TIPS.other;
    return { lines, tip };
  }
  /* your Lucidity ran out: when, where it went (doors / cameras / light / just being asleep), and a tip for the biggest */
  function lucidityRecap() {
    const S = G.spend, parts = [['doors', 'doors', S.doors], ['cams', 'cameras', S.cams], ['lights', 'light', S.lights], ['base', 'just being asleep', S.base]];
    const total = parts.reduce((a, p) => a + p[2], 0) || 1;
    const spend = parts.map(([k, label, v]) => ({ k, label, pct: Math.round(100 * v / total) }));
    const top = parts.reduce((a, p) => (p[2] > a[2] ? p : a), parts[3])[0];
    return { lines: [{ s: `Your Lucidity ran out at ${fmtClock(G.powerAt)}.` }], tip: TIPS[top === 'cams' ? 'camsSpend' : top], spend };
  }
  /* the lines type themselves out (a click shows them all); the tip and the bar come after */
  function showRecap(r) {
    const lines = r.lines.map((l, i) => (l.t != null ? fmtClock(l.t, i > 0) + ': ' : '') + l.s);
    G.recap = { lines, shown: 0, total: lines.reduce((a, l) => a + l.length, 0), n: 0, done: false, wait: RECAP.wait };
    $('#deadRecap').innerHTML = lines.map(() => '<div><span class="on"></span><span class="rest"></span></div>').join('');
    drawRecap();
    $('#deadTip').innerHTML = numify(r.tip);
    const sp = $('#deadSpend');
    setCls(sp, 'hidden', !r.spend);
    if (r.spend) {
      sp.querySelector('.bar').innerHTML = r.spend.filter((p) => p.pct > 0).map((p) => `<i class="${p.k}" style="width:${p.pct}%"></i>`).join('');
      sp.querySelector('.legend').innerHTML = r.spend.filter((p) => p.pct > 0).map((p) => `<span class="${p.k}"><b></b>${escapeHtml(p.label)} ${numify(p.pct + '%')}</span>`).join('');
    }
    for (const el of [$('#deadTip'), sp]) el.classList.remove('show');
    if (!G.recap.total) finishRecap();
  }
  /* every line keeps its full width from the start (the untyped rest is invisible), so nothing jumps around */
  function drawRecap() {
    const R = G.recap;
    let left = Math.floor(R.shown);
    $('#deadRecap').querySelectorAll('div').forEach((d, i) => {
      const l = R.lines[i], k = clamp(left, 0, l.length); left -= l.length;
      d.firstChild.innerHTML = numify(l.slice(0, k)); d.lastChild.textContent = l.slice(k);
    });
  }
  function updateDead(dt) {
    if (G.deadWait > 0 && (G.deadWait -= dt) <= 0) { // the buttons are ready: Enter now means "Dream again"
      $('#dead').classList.remove('wait');
      const b = $('#dead').querySelector('button:not(.hidden)'); if (b) b.focus({ preventScroll: true });
    }
    const R = G.recap;
    if (!R || R.done || (R.wait -= dt) > 0) return;
    const before = Math.floor(R.shown);
    R.shown = Math.min(R.total, R.shown + dt * RECAP.cps);
    const now = Math.floor(R.shown);
    if (now !== before) { drawRecap(); if ((R.n += now - before) % 2 === 0) Sound.play('type_key', { vol: 0.1, rate: rand(0.85, 1.05) }); }
    if (R.shown >= R.total) finishRecap();
  }
  function finishRecap() {
    const R = G.recap;
    if (!R || R.done) return;
    R.done = true; R.shown = R.total; drawRecap();
    for (const el of [$('#deadTip'), $('#deadSpend')]) el.classList.add('show');
  }

  /* ------------------------------------------------------------------ */
  /*  WAKING UP: the alarm rings inside the dream, you blink into your  */
  /*  bedroom, slap it off, and something has followed you out          */
  /* ------------------------------------------------------------------ */
  /* wakeT: 6 AM = 0. Two blinks (one slow one with Dream effects Off), then the morning; the eyes are open at OPEN */
  const WAKE = { morning: 2.05, open: 2.5, listen: 0.6, autoSlap: 8 };
  function wakeLids(t) {
    const up = (a, b) => ease(clamp((t - a) / (b - a), 0, 1));
    if (t >= WAKE.morning) return 1 - up(WAKE.morning, WAKE.open);
    if (save.fx === 'off') return up(1.4, 1.9);
    return t < 1.4 ? up(1.1, 1.25) - up(1.25, 1.4) : up(1.7, 1.9);
  }
  /* where the desk clock sits on screen right now (null = this desk room has none) */
  function clockOnScreen() {
    const k = officeSpot('clock');
    return k ? { x: officeOriginX() + k.x * G.officeW, y: k.y * H, r: (k.r || 0.03) * H } : null;
  }
  /* the alarm's left/right: from the desk clock (0 when the room has no clock) */
  function clockPan() { const k = clockOnScreen(); return k ? clamp((k.x / W - 0.5) * 1.2, -1, 1) : 0; }

  function startWaking() {
    if (!G.endless && !G.practice) { // progress is saved the moment the alarm rings (a practice dream never touches it)
      save.beaten = Math.max(save.beaten, G.night);
      save.night = clamp(G.night + 1, 1, NIGHTS);
      delete save.deaths[G.night]; // ("Dream lighter" waits for three new deaths)
      writeSave();
    }
    G.state = 'waking'; G.wakeT = 0; G.later = []; G.lies = []; // (first, so whatever stops now knows the night is over)
    // the monitor: one on its way up or down snaps to where it was going; on CAM 7 (your own room) it drops at once
    const C = G.cams;
    if (C.up && C.cur !== YOU_CAM.id) C.t = 1; else { C.up = false; C.t = 0; }
    resetDirector(false);
    Captions.clear();
    G.wakeClear = G.powerOut; // saved at Lucidity zero: no pillow in the way, it rings loud and clear
    G.wakePan = clockPan();
    G.hour = 6; setText(hudEls.time, 'time', fmtHour(6));
    $('#hud').classList.add('fadeOut');
    if (G.voice.active) endVoice();
    Sound.killLoops();
    // whatever you could see freezes, then melts away
    G.wakeView = C.t >= 1 ? 'cams' : 'office';
    G.frozen = G.monsters.filter((m) => G.wakeView === 'cams'
      ? m.state === 'roam' && m.room === G.cams.cur && G.cams.lost <= 0
      : m.state === 'door' && G.doors[m.door].light && !G.powerOut);
    for (const m of G.monsters) m.animSpeed = 0;
  }

  /* how far a frozen monster has melted (0..1) */
  const meltK = () => clamp(G.wakeT / 1.2, 0, 1);
  /* the rectangle a visible monster fills on screen (for the red bits that rise off it) */
  function frozenRect(m) {
    if (G.wakeView === 'cams') {
      const pose = leanPose(m.def.poses && m.def.poses[G.cams.cur], stareK(m, rule('stare', 0)));
      return spriteRect(m.art.soft[m.frame()], camFeedBox(), pose);
    }
    return spriteRect(m.art.soft[m.frame()], doorBox(m.door), doorPoseOf(m, m.door));
  }

  function updateWaking(dt) {
    G.wakeT += dt;
    // the alarm, heard through a pillow at first, then clear (file mode can't muffle: it gets louder instead)
    const k = G.wakeClear ? 1 : clamp((G.wakeT - 0.3) / 2.2, 0, 1);
    Sound.loop('wake', Sound.web ? 0.9 : lerp(0.4, 0.9, k), { sound: 'alarm', lowpass: Math.round(500 * Math.pow(36, k)),
      pan: lerp(G.wakePan, 0, clamp((G.wakeT - WAKE.morning) / 0.5, 0, 1)), fade: 0.1, music: false });
    if (G.state === 'waking') {
      if (G.wakeView === 'cams' && G.wakeT > 1.1) G.cams.t = Math.max(0, G.cams.t - dt * 4 / 0.28); // the monitor drops during the blink
      const melt = meltK();
      if (melt < 1) for (const m of G.frozen) {
        const r = frozenRect(m), n = 40 * fxMul() * dt / 1.2; // about 40 red bits over the melt
        spawnParts(Math.floor(n) + (Math.random() < n % 1 ? 1 : 0), { x: r.x + r.w / 2, y: r.y + r.h * (0.15 + 0.7 * melt), spreadX: r.w * 0.4, spreadY: r.h * 0.15,
          vy: -70, jitter: 22, life: 1.1, r: 4, col: 'rgb(226,58,76)' });
      }
      if (G.wakeT >= WAKE.morning) enterMorning();
    } else if (G.wakeT >= WAKE.open + WAKE.autoSlap) slapAlarm(); // nobody turned it off: it gives up by itself
    if (G.state === 'morning' && G.wakeT >= WAKE.open + WAKE.listen) show($('#wakePrompt'));
  }

  /* your eyes are shut: when they open you are in your own bedroom */
  function enterMorning() {
    G.state = 'morning'; G.wakeT = Math.max(G.wakeT, WAKE.morning);
    G.parts = []; G.cams.up = false; G.cams.t = 0;
    setCls(hudEls.voice, 'docked', false);
    hide($('#hud'));
    $('#wakePrompt').textContent = TAP + ' to turn off the alarm';
  }

  /* you slap the alarm off: the real morning */
  function slapAlarm() {
    if (G.state === 'waking') enterMorning();
    if (G.state !== 'morning') return;
    G.state = 'win'; G.slapT = 0.25;
    hide($('#wakePrompt'));
    Sound.stopLoop('wake', 0.05);
    Sound.play('door_close', { vol: 0.5, rate: 1.6 }); // the clunk of the button
    Sound.loop('morning', 0.8, { fade: 3, music: true }); // birds
    if (!G.endless && !G.practice && G.night >= NIGHTS) startFinale(); else showWinPanel();
  }

  /* "You woke up", what happened tonight, and the buttons (they wait a moment, so a fast second tap can't press one) */
  function showWinPanel() {
    const last = !G.endless && !G.practice && G.night >= NIGHTS, S = G.stats;
    $('#winSub').innerHTML = numify(G.endless ? 'The endless dream let you go… this time.'
      : G.practice ? 'Practice is over. The real nights are waiting.'
        : last ? 'All five nights. The alarm rang, and this time you heard it.'
          : 'Night ' + G.night + ' survived. But you’ll fall asleep again tonight.');
    const bits = [];
    if (S.bangs) bits.push('Turned it away ×' + S.bangs);
    bits.push(G.powerOut ? 'Saved by the alarm at 0% Lucidity' : 'Lucidity left ' + Math.max(0, Math.ceil(G.luc)) + '%');
    if (S.pinches) bits.push('Pinched ×' + S.pinches);
    if (S.fakesLit) bits.push('Saw through the dream ×' + S.fakesLit);
    $('#winStats').innerHTML = numify(bits.join('  ·  '));
    $('#wNext').textContent = (G.endless || G.practice || last) ? 'Back to the menu' : 'Next night';
    const title = $('#winTitle'); title.classList.remove('show');
    showScreen('#win');
    $('#win').classList.add('wait'); G.winWait = 0.9;
    void title.offsetWidth; title.classList.add('show');
  }

  /* after Night 5: the voice has the last word, then the credits roll (they start with the person who drew the monsters) */
  function startFinale() {
    const F = CFG.finale || {};
    G.finale = { phase: 'line', t: 0, y: 0 };
    const hud = $('#hud');
    hud.classList.remove('fadeOut', 'enter', 'dissolve'); hud.classList.add('onlyVoice'); show(hud);
    startVoice(F.line || 'See? I told you I’d be the one ringing.', 2.5);
  }
  function buildCredits() {
    const roll = $('#creditRoll'), list = CFG.credits || [];
    roll.innerHTML = '';
    const add = (cls, text) => { const d = document.createElement('div'); d.className = cls; d.textContent = text; roll.appendChild(d); };
    const groups = { Sound: [], Font: [], Picture: [] }, singles = [];
    for (const c of list) {
      if (!c || !c.who) continue;
      const g = /^\s*(Sound|Font|Picture)/i.exec(c.what || '');
      if (g) { const k = g[1][0].toUpperCase() + g[1].slice(1).toLowerCase(); if (groups[k].indexOf(c.who) < 0) groups[k].push(c.who); } else singles.push(c);
    }
    singles.forEach((c, i) => { add('cRole', c.what || ''); add(i ? 'cWho' : 'cWho cYou', c.who); }); // the first one is YOU
    add('cTitle', CFG.title || 'UNTIL THE ALARM');
    if (groups.Sound.length) { add('cRole', 'Sounds'); add('cNames', groups.Sound.join('  ·  ')); }
    if (groups.Font.length) { add('cRole', 'Fonts'); add('cNames', groups.Font.join('  ·  ')); }
    if (groups.Picture.length) { add('cRole', 'Pictures in the rooms'); add('cNames', groups.Picture.join('  ·  ')); }
    add('cEnd', (CFG.finale || {}).thanks || 'Thank you for waking up.');
  }
  function updateWin(dt) {
    G.slapT = Math.max(0, G.slapT - dt);
    if (G.winWait > 0 && (G.winWait -= dt) <= 0) { // the buttons are ready
      $('#win').classList.remove('wait');
      const b = $('#win').querySelector('button'); if (b) b.focus({ preventScroll: true });
    }
    const F = G.finale;
    if (!F) return;
    F.t += dt;
    if (F.phase === 'line' && !G.voice.active && F.t > 0.5) { // the voice has faded: roll the credits
      F.phase = 'credits'; F.y = H;
      buildCredits(); show($('#credits'));
    } else if (F.phase === 'credits') {
      const roll = $('#creditRoll');
      F.y -= Math.max(85, (H + roll.offsetHeight) / 24) * dt; // 85 px a second: about 20 s, never more than 24
      roll.style.transform = `translateY(${F.y.toFixed(1)}px)`;
      if (F.y < -roll.offsetHeight) endFinale();
    }
  }
  /* the credits are over (or skipped) */
  function endFinale() {
    G.finale = null;
    if (G.voice.active) endVoice();
    resetHud();
    showWinPanel(); // (this hides the credits too)
  }

  /* a click, tap or key outside the night: skip ahead (returns true when it used the input) */
  function skipInput() {
    if (G.paused) return false;
    if (G.state === 'asleep') { skipIntro(); return true; }
    if (G.state === 'waking') { enterMorning(); return true; }
    if (G.state === 'morning') { if (G.wakeT >= WAKE.open + WAKE.listen) slapAlarm(); return true; }
    if (G.state === 'win' && G.finale) { endFinale(); return true; }
    if (G.state === 'dead' && G.deadWait > 0) return true; // (a tap left over from the scare)
    if (G.state === 'dead' && G.recap && !G.recap.done) { finishRecap(); return true; } // a click shows the whole recap
    return false;
  }

  /* ------------------------------------------------------------------ */
  /*  THE DREAM LIES: below the line on the Lucidity bar it shows fakes. */
  /*  A fake always has the same tells: it never moves (one frozen       */
  /*  frame), it is see-through violet, its breathing runs backwards,    */
  /*  and the light never stutters on it. It never touches the real      */
  /*  monsters, and it goes the moment real danger comes close.          */
  /* ------------------------------------------------------------------ */
  const LIE = { doorTtl: 9, camTtl: 25, seen: 1.1, fade: 0.35, alpha: 0.75 };
  const LIE_VOICE = 'Not real. The real one always moves. If its breathing runs backwards, the dream is lying.';
  /* seconds until the dream tries to lie again (sooner once you have sunk below 30%) */
  function nextLieIn() { const e = liesCfg().every; return rand(e[0], e[1]) * (G.luc < 30 ? 0.6 : 1); }
  /* never on top of real danger: nobody at a door or next to one, no power-out, the voice is quiet, before 5:30 */
  function canLie() {
    return rule('lies', false) && !G.lies.length && G.monsters.length > 0 && !G.powerOut && !G.inside && !G.voice.active
      && G.nightT < 5.5 * hourSec() && calm(2) && !Director.active && !Director.queued && !G.fd; // (one trick at a time)
  }
  /* kind 'door': footsteps, then backwards breathing at a door. kind 'cam': it just stands in a camera room. */
  function spawnLie(kind) {
    const m = pick(G.monsters);
    const L = { kind: kind || (Math.random() < 0.6 ? 'door' : 'cam'), who: m, frame: randi(0, m.art.soft.length - 1), litT: 0, lit: false, shut: false };
    if (L.kind === 'door') { // a side no monster is heading for
      const sides = ['left', 'right'].filter((s) => !G.monsters.some((x) => doorSide(x.def, x.room) === s));
      if (!sides.length && kind) return null;
      if (sides.length) L.side = pick(sides); else L.kind = 'cam';
    }
    if (L.kind === 'cam') { // a room with nobody in it, and not the one on screen
      const rooms = CFG.cameras.filter((c) => !G.monsters.some((x) => x.room === c.id) && !(G.cams.up && G.cams.cur === c.id));
      if (!rooms.length) return null;
      L.room = pick(rooms).id; L.ttl = LIE.camTtl;
    } else {
      L.ttl = LIE.doorTtl;
      if (quietSteps()) cue('steps', L.side, { monster: m, fake: true, vol: 0.6, cap: 'stepsNear' });
      after(rand(1.2, 2.2), () => {
        if (G.lies.indexOf(L) < 0) return; // it's already gone
        const shut = G.doors[L.side].closed;
        cue('breath', L.side, { monster: m, fake: true, vol: shut ? 0.3 : 0.45, lowpass: shut ? 700 : 0, cap: shut ? 'breathMuffled' : 'breath' });
      });
    }
    G.lies.push(L);
    G.lieT = nextLieIn(); // the next one comes `every` seconds after this one has gone
    return L;
  }
  /* how far a door fake has dissolved (0..1): it lets go once the light has been on it for a moment */
  const lieFade = (L) => clamp((L.litT - LIE.seen) / LIE.fade, 0, 1);
  function updateLies(dt, realDt) {
    if (!rule('lies', false)) return;
    if (G.lies.length && !calm(2)) G.lies = []; // real danger is close: every lie goes at once
    for (const L of G.lies) {
      L.ttl -= dt;
      if (L.kind !== 'door') continue;
      const D = G.doors[L.side];
      if (!D.light || D.closed) continue;
      L.litT += realDt;
      if (!L.lit) { // the light found it
        L.lit = true; G.stats.fakesLit++;
        if (!save.hints.lie) { save.hints.lie = true; writeSave(); startVoice((CFG.dreamVoice || {}).lie || LIE_VOICE, 4); }
      }
    }
    G.lies = G.lies.filter((L) => L.ttl > 0 && !(L.kind === 'door' && lieFade(L) >= 1)
      && !(L.kind === 'cam' && G.monsters.some((x) => x.room === L.room)));
    // Night 2 teaches it once: a fake at a door between 1:30 and 3 AM, whatever your Lucidity (until you have seen one)
    const h = G.nightT / hourSec();
    if (G.night === 2 && !G.endless && !save.hints.lie && !G.taught && h >= 1.5 && h < 3 && canLie() && spawnLie('door')) G.taught = true;
    // the next lie: `every` seconds after the last one ended. If real danger is near right then, it waits for a calm moment.
    if (!G.lies.length && (G.lieT -= dt) <= 0) {
      if (G.luc >= liesCfg().below) G.lieT = nextLieIn(); // above the line the dream is honest
      else if (!canLie() || !spawnLie()) G.lieT = rand(4, 8);
    }
  }


  /* ------------------------------------------------------------------ */
  /*  THE DREAM DIRECTOR: every night gets a shape. A quiet 12 AM, then  */
  /*  small "wrong" things from about 1 AM, each after a moment of       */
  /*  silence, and never while real danger is near. From 5:30 the clock  */
  /*  ticks louder and the HUD counts the minutes. Night 5 fakes the     */
  /*  dawn once (it never kills).                                        */
  /* ------------------------------------------------------------------ */
  /* config director: enabled (false = no small events; CAM 7 still comes), quietMinutes before the first one,
     minGap / maxGap seconds between two */
  function directorCfg() {
    const d = Object.assign({ enabled: true, quietMinutes: 50, minGap: 40, maxGap: 90 }, CFG.director || {});
    d.enabled = d.enabled !== false;
    d.quietMinutes = Math.max(0, isFinite(+d.quietMinutes) ? +d.quietMinutes : 50);
    d.minGap = Math.max(5, +d.minGap || 40); d.maxGap = Math.max(d.minGap, +d.maxGap || 90);
    return d;
  }
  /* cd: countdown to the next small event (it runs faster when the night is tense); lull: the silence before
     the queued event; duck: how loud the ambience and room sounds are allowed to be (1 = normal) */
  const Director = { cd: 45, lull: 0, duck: 1, active: null, queued: null, done: new Set() };
  const FINAL_MIN = 330; // 5:30 AM, in minutes after midnight
  const nightMin = () => G.nightT / hourSec() * 60;
  /* nothing real is close, nothing fake is showing, the voice is quiet */
  function safe() {
    return calm(2) && !G.powerOut && !G.inside && !G.preScare && !G.voice.active && G.danger < 0.25 && !G.lies.length && !G.fd;
  }
  /* how tense the night is right now (later hours, later nights, lower Lucidity) */
  function tension() { return [0.15, 0.35, 0.55, 0.65, 0.8, 1][clamp(G.hour, 0, 5)] * (0.7 + 0.08 * G.night) + (1 - clamp(G.luc, 0, 100) / 100) * 0.3; }

  /* the small wrong things. weight: how likely it is picked; can: can it happen right now?
     update(dt) returns true when it is over; end() puts everything back. once: one per night.
     eager: starts at its first chance instead of waiting for the countdown. */
  const DREAM_EVENTS = [
    { // the lamp breathes, slowly, like something asleep
      id: 'lampBreath', minNight: 1, weight: () => 1, can: () => !!officeSpot('lamp') && !G.cams.up,
      start() { G.lampBreath = 0; },
      update(dt) { return (G.lampBreath += dt) >= 15; },
      end() { G.lampBreath = null; },
    },
    { // light a doorway and the hall behind it is some other room of the house
      id: 'wrongDoorway', minNight: 2, weight: () => 1, can: () => !G.cams.up,
      start() { G.wrongDoor = { side: pick(['left', 'right']), cam: pick(CFG.cameras).id, t: 0, lit: 0 }; },
      update(dt) { // it waits up to 20 s for your light; after 6 s lit (or once you turn the light off) it is gone
        const D = G.wrongDoor; D.t += dt;
        if (G.doors[D.side].light) D.lit += dt; else if (D.lit > 0) return true;
        return D.lit >= 6 || (D.lit === 0 && D.t >= 20);
      },
      end() { G.wrongDoor = null; },
    },
    { // whispering right above you, in the ceiling
      id: 'ceilingWhisper', minNight: 2, weight: () => 0.8, can: () => true,
      start() { Sound.play('whisper', { pan: 0, lowpass: 700, rate: 0.7, vol: 0.6 }); Captions.show('whisperAbove', 0, 0.6); },
      update: () => true, end() {},
    },
    { // the room stretches wider for a while (the halls were longer tonight)
      id: 'roomStretch', minNight: 3, once: true, weight: () => 0.7, can: () => !G.cams.up,
      start() { G.stretchTo = 1.1; G.stretchT = 0; },
      update(dt) { return (G.stretchT += dt) >= 20; },
      end() { G.stretchTo = 1; },
    },
    { // CAM 7: once a night, the camera that films you (see YOUR ROOM below)
      id: 'youCam', rule: 'youCam', once: true, eager: true, weight: () => 1,
      can: () => G.nightT >= G.youCamAt * hourSec() && G.cams.up && G.cams.t >= 1 && G.cams.lost <= 0,
      start: () => startYouCam(), update: (dt) => updateYouCam(dt), end: () => endYouCam(),
    },
  ];
  const eligible = (e) => (e.rule ? !!rule(e.rule, false) : (G.endless ? NIGHTS : G.night) >= e.minNight) && !(e.once && Director.done.has(e.id));

  function startEvent(e) { endEvent(); const D = Director; D.queued = null; D.active = e; D.done.add(e.id); e.start(); }
  function endEvent() { const e = Director.active; Director.active = null; if (e) e.end(); }
  /* stop whatever the director is doing (full: a new night, everything back to the start) */
  function resetDirector(full) {
    endEvent();
    const D = Director;
    D.queued = null; D.lull = 0;
    if (G.fd) Sound.stopLoop('wake', 0.1); // (a False Dawn in progress is over too)
    G.fd = null; G.freeze = false;
    if (!full) return;
    D.cd = 45; D.duck = 1; D.done = new Set();
    G.lampBreath = null; G.wrongDoor = null; G.stretch = 1; G.stretchTo = 1; G.youCam = null;
    G.youCamAt = rand(1.5, 4.5); // CAM 7 can come from this hour on (1:30 - 4:30 AM)
    G.fdDone = false; G.fdRolled = false; G.nearRang = false;
  }

  function directorUpdate(dt) {
    const D = Director, cfg = directorCfg(), ok = safe();
    if (D.active) {
      if (!ok || D.active.update(dt)) endEvent(); // real danger close: the trick ends at once
    } else if (D.queued) {
      if (!ok) D.queued = null; // it keeps its trick for later
      else if ((D.lull -= dt) <= 0) { const e = D.queued; D.queued = null; if (e.can()) startEvent(e); }
    } else {
      const min = nightMin(), open = ok && min >= (cfg.enabled ? cfg.quietMinutes : 0) && min < FINAL_MIN;
      const eager = open && DREAM_EVENTS.find((e) => e.eager && eligible(e) && e.can());
      if (eager) { if (cfg.enabled) { D.queued = eager; D.lull = rand(1.8, 3); } else startEvent(eager); }
      else if (cfg.enabled) {
        D.cd -= dt * (0.5 + tension());
        if (D.cd <= 0 && open) {
          const list = DREAM_EVENTS.filter((e) => !e.eager && eligible(e) && e.can());
          let r = Math.random() * list.reduce((a, e) => a + e.weight(), 0), e = null;
          for (const x of list) if ((r -= x.weight()) <= 0) { e = x; break; }
          if (e) { D.queued = e; D.lull = rand(1.8, 3); D.cd = rand(cfg.minGap, cfg.maxGap) / (0.6 + tension()); }
          else D.cd = rand(4, 8);
        }
      }
    }
    // the silence before it: the ambience and the room sounds sink while an event waits, then come back
    const hushed = D.queued || (G.fd && G.fd.phase !== 'after'); // (the False Dawn's alarm drowns them too)
    D.duck = hushed ? lerp(D.duck, 0.15, 1 - Math.exp(-dt * 2.5)) : Math.min(1, D.duck + 0.5 * dt);
    updateStretch(dt);
  }

  /* the room's width eases toward G.stretchTo; the middle of your view stays where it is */
  function updateStretch(dt) {
    if (G.stretch === G.stretchTo) return;
    const before = G.officeW;
    G.stretch = Math.abs(G.stretchTo - G.stretch) < 0.0005 ? G.stretchTo : lerp(G.stretch, G.stretchTo, 1 - Math.exp(-dt * 0.6));
    G.officeW = officeWidthFor(Art.office) * G.stretch;
    G.scroll = clamp((G.scroll + W / 2) * G.officeW / before - W / 2, 0, Math.max(0, G.officeW - W));
  }

  /* ----- the final half hour: minutes on the clock, ticking louder, and on Nights 1-4 the alarm almost rings ----- */
  function updateFinalStretch(dt) {
    const min = nightMin();
    if (min < FINAL_MIN || G.powerOut || silent() || G.fd) return;
    if (!G.tickShown) { G.tickShown = true; Captions.show('ticking', 0, 0.5); }
    clockTick(dt, 0.25 + 0.5 * clamp((min - FINAL_MIN) / 30, 0, 1), 1, 1);
    if (!G.endless && G.night < NIGHTS && !G.nearRang && min >= 358) { // 5:58: it almost rang
      G.nearRang = true;
      const h = Sound.play('alarm', { vol: 0.12, rate: 0.8, lowpass: 450 });
      if (h) after(1.2, () => h.stop(0.5));
      Captions.show('nearRing', 0, 0.35);
    }
  }

  /* ----- FALSE DAWN (config nights[].falseDawn, Night 5): the alarm rings, but it isn't morning yet ----- */
  const FALSE_DAWN = { ring: 2.6, wind: 0.6, unfreeze: 5, latest: 5 + 40 / 60 };
  function updateFalseDawn(dt) {
    const F = G.fd;
    if (!F) {
      const at = +rule('falseDawn', 0);
      if (!at || G.fdDone || G.nightT < at * hourSec()) return;
      if (G.powerOut || G.nightT > FALSE_DAWN.latest * hourSec()) { G.fdDone = true; return; } // too late: it gives up
      if (G.preScare || G.monsters.some((m) => m.state === 'door' || m.state === 'inside')) return; // not now: wait
      startFalseDawn();
      return;
    }
    F.t += dt;
    if (F.phase === 'ring' && F.t >= FALSE_DAWN.ring) F.phase = 'wind';
    if (F.phase === 'wind') { // the ringing sags, lower and duller, and dies
      const k = clamp((F.t - FALSE_DAWN.ring) / FALSE_DAWN.wind, 0, 1);
      Sound.loop('wake', 0.6, { sound: 'alarm', lowpass: Math.round(lerp(1600, 500, k)), rate: +lerp(1, 0.45, k).toFixed(3), fade: 0.1, music: false, pan: F.pan });
    }
    if (F.phase === 'wind' && F.t >= FALSE_DAWN.ring + FALSE_DAWN.wind) { // the clock rolls back
      F.phase = 'after'; G.fdRolled = true;
      Sound.stopLoop('wake', 0.15);
      pulseCls(hudEls.time, 'rollBack');
      startVoice((CFG.dreamVoice || {}).falseDawn || 'Not yet.', 2.5);
    } else if (F.phase === 'after' && F.t >= FALSE_DAWN.unfreeze) { // and the dream starts moving again, hungrier
      G.fd = null; G.freeze = false;
      for (const m of G.monsters) if (m.state === 'roam' && m.level > 0) m.boost += 1;
    }
  }
  function startFalseDawn() {
    endEvent(); Director.queued = null;
    G.fdDone = true; G.freeze = true; // the monsters, their timers and your Lucidity hold still (the doors don't)
    G.lies = [];
    G.fd = { t: 0, phase: 'ring', pan: clockPan() };
    Sound.loop('wake', 0.6, { sound: 'alarm', lowpass: 1600, fade: 0.1, music: false, pan: G.fd.pan });
    Captions.show('alarm', G.fd.pan, 0.8);
  }
  /* how strongly the false morning shows (0..1) */
  const falseDawnK = () => (G.fd ? 0.4 * (1 - clamp((G.fd.t - FALSE_DAWN.ring) / FALSE_DAWN.wind, 0, 1)) : 0);

  /* ----- CAM 7, YOUR ROOM: a camera that was never on the map. Look once: it's you, from behind. Look away,
     look back: something stands right behind your chair (a lie: frozen, violet, breathing backwards).
     On Night 5 the chair is empty. It costs nothing; it is only there to be remembered. ----- */
  const YOU_CAM = { id: '_you', label: 'CAM 7', name: 'Your Room', index: 7, map: { x: 0.5, y: 0.8 } };
  const ghostCam = () => document.querySelector('#camMap .ghostCam');
  function startYouCam() {
    camById._you = YOU_CAM; // (never in config cameras, so no number key reaches it and no monster walks there)
    const b = ghostCam();
    show(b); pulseCls(b, 'ghostIn');
    document.querySelectorAll('#camLinks .ghostLink').forEach((l) => l.classList.add('on'));
    Sound.play('cam_switch', { rate: 0.5, vol: 0.6 });
    G.youCam = { stage: 0, t: 0, life: 0 };
  }
  /* stage 0: it appeared. 1: you looked at it and looked away. 2: you came back to it */
  function updateYouCam(dt) {
    const Y = G.youCam;
    if (!Y || !G.cams.up) return true; // the cameras went down: the moment is gone
    Y.life += dt;
    if (Y.stage === 2) return (Y.t += dt) >= 1.6;
    return Y.life >= 30; // never looked at: it slips away
  }
  function endYouCam() {
    const Y = G.youCam;
    G.youCam = null;
    hide(ghostCam());
    document.querySelectorAll('#camLinks .ghostLink').forEach((l) => l.classList.remove('on'));
    delete camById._you;
    const night = G.state === 'night'; // (at 6 AM it just goes: no static over the waking)
    if (G.cams.cur === YOU_CAM.id) { // the picture cuts back to the first camera
      G.cams.cur = CFG.cameras[0].id; updateCamUi();
      if (G.cams.up && night) camDisrupt();
    } else if (Y && Y.stage === 2 && G.cams.up && night) camDisrupt();
  }
  /* switching cameras moves CAM 7 along (see switchCam) */
  function youCamSwitch(from, to) {
    const Y = G.youCam;
    if (!Y) return;
    if (from === YOU_CAM.id && Y.stage === 0) Y.stage = 1;
    else if (to === YOU_CAM.id && Y.stage === 1) {
      Y.stage = 2; Y.t = 0;
      const m = G.monsters[0];
      Y.empty = !G.endless && G.night >= NIGHTS; // the last night: nobody in the chair
      if (m && !Y.empty) { Y.lie = { who: m, frame: randi(0, m.art.soft.length - 1) }; cue('breath', 'center', { monster: m, vol: 0.9, fake: true, cap: 'breathClose' }); }
    }
  }

  /* ------------------------------------------------------------------ */
  /*  UPDATE                                                            */
  /* ------------------------------------------------------------------ */
  const keys = {};
  const pointer = { x: W / 2, y: H / 2, inside: false, type: 'mouse', dragId: null, lastX: 0 };

  function update(dt) {
    G.t += dt;
    const pull = dustPull(), settle = Math.pow(0.995, dt * 60);
    for (const m of G.motes) {
      if (pull != null) m.vx += clamp((pull - m.x) / 400, -1, 1) * 12 * dt;
      m.vx = m.bvx + (m.vx - m.bvx) * settle; // (and it drifts back to its own way afterwards)
      m.x += m.vx * dt; m.y += m.vy * dt; m.ph += dt;
      if (m.y < -10) { m.y = H + 10; m.x = Math.random() * W; }
      if (m.x < -10) m.x = W + 10; if (m.x > W + 10) m.x = -10;
    }
    G.flash = Math.max(0, G.flash - dt * 1.8);
    G.trauma = Math.max(0, G.trauma - dt * 1.5);
    G.kick.x *= Math.exp(-12 * dt);
    if (!G.paused) {
      updateParts(dt); updateFlickers(dt);
      G.clarity = Math.max(0, G.clarity - dt * 0.3);
      if (G.punch && (G.punch.t -= dt) <= 0) G.punch = null;
      for (const m of G.monsters) m.anim += dt * (m.def.fps || 4) * m.animSpeed;
    }

    if (G.state === 'menu' || G.state === 'boot') updateMenuScene(dt);
    if (G.state === 'asleep' && !G.paused) updateAsleep(dt);
    if (G.state === 'night' && !G.paused) updateNight(dt * G.timeScale, dt);
    if (G.state === 'waking' || G.state === 'morning') updateWaking(dt);
    if (G.state === 'win') updateWin(dt);
    if (G.state === 'dead') updateDead(dt);
    if (G.lesson) updateCoach(dt);
    if (G.voice.active && !G.paused && (G.state === 'night' || G.state === 'win')) updateVoice(dt);
    if (G.state === 'jumpscare') {
      G.jumpT += dt;
      const S = G.scare;
      if (S && !S.gentle && !S.off && G.jumpT >= JUMP.stare) { S.off = true; Sound.play('cam_close', { rate: 0.6, vol: 0.8 }); } // the picture switches off
      if (G.jumpT >= (S ? S.len : JUMP.end)) die();
    }
    Sound.update(dt);
  }

  /* the scroll that brings that doorway fully into view (or the current one if it already is) */
  function glideTarget(side, maxScroll) {
    const d = officeDoor(side), margin = 60;
    if (side === 'left') return clamp(Math.min(G.scroll, d.x * G.officeW - margin), 0, maxScroll);
    return clamp(Math.max(G.scroll, (d.x + d.w) * G.officeW - W + margin), 0, maxScroll);
  }

  /* ----- held-breath doors ----- */
  /* how strained a door is: 0 = still free, 1 = costing the most it can */
  function strainK(D) { const S = strainCfg(); return S.maxCost > 1 ? clamp((D.cost - 1) / (S.maxCost - 1), 0, 1) : 0; }

  function holdDoor(side, D, dt) {
    const S = strainCfg(), free = rule('doorFree', 12), gasp = rule('gasp', 0);
    D.held = D.closed ? D.held + dt : Math.max(0, D.held - dt * 3);
    D.cost = D.closed ? 1 + clamp((D.held - free) / S.rampSeconds, 0, 1) * (S.maxCost - 1) : 0;
    // a tired door gasps open (Night 4+), but never with something behind it
    const behind = G.monsters.some((m) => m.state === 'door' && m.door === side);
    if (D.gaspT > 0) {
      if (behind || !D.closed || G.powerOut) D.gaspT = 0;           // it held on after all, or you opened it
      else if ((D.gaspT -= dt) <= 0) {
        D.gaspT = 0; D.closed = false; D.held = 0;
        logStory({ kind: 'gasp', side });
        Sound.play('door_open', { vol: 0.9, rate: 0.7, pan: side === 'left' ? -0.7 : 0.7 });
      }
    } else if (gasp && D.closed && !behind && D.held > gasp && !G.powerOut) {
      D.gaspT = 1.5;
      hit(0.15, side === 'left' ? 1 : -1);
    }
    const groan = D.gaspT > 0 ? 0.8 : D.cost > 1 ? 0.15 + 0.35 * strainK(D) : 0;
    if (groan > 0 && (!D.groan || (D.gaspT > 0 && D.groan < 0.8))) Captions.show('strain', sidePan(side) * 0.8, Math.max(0.5, groan)); // it starts to groan; the gasp
    D.groan = groan;
    Sound.loop('strain:' + side, silent() ? 0 : groan, { sound: 'door_strain', pan: side === 'left' ? -0.7 : 0.7, fade: 0.4, music: false });
  }

  /* the shutter falls under its own weight, bounces once and lands with a thud; it lifts with an ease-out */
  function moveDoor(side, D, realDt) {
    if (!D.closed) { D.landed = false; D.v = 0; D.p = Math.max(0, D.p - realDt * (1.5 + 6 * D.p)); return; }
    if (D.p >= 1 && D.v >= 0 && D.landed) { D.p = 1; D.v = 0; return; }
    D.v += 18 * realDt; D.p += D.v * realDt;
    if (D.p < 1) return;
    D.p = 1;
    const fell = D.v > 2.5; // a door shut again before it had really lifted just settles
    if (D.landed || !fell) { D.landed = true; D.v = 0; return; }
    D.landed = true;
    const k = fxMul();
    D.v = -D.v * 0.22 * k; // one small bounce (none with Dream effects Off)
    D.landT = 0.5;
    hit(0.12, side === 'left' ? 1 : -1);
    const d = officeDoor(side), cx = (d.x + d.w / 2) * G.officeW, half = d.w * G.officeW / 2;
    spawnParts(Math.round(10 * k), { office: true, x: cx, y: (d.y + d.h) * H - 4, spreadX: half, spreadY: 2,
      vx: (p) => Math.sign(p.x - cx || 1) * rand(25, 70), vy: -14, jitter: 10, life: 1.1, r: 3.2, col: 'rgb(180,170,160)' }); // dust puffs out
  }

  /* ----- it likes being watched: stare too long and it steps closer. Returns how far it is leaning in (0..1). */
  function stareK(m, lim) { return lim ? ease(clamp(m.watched / lim, 0, 1)) : 0; }
  function updateStare(dt) {
    const C = G.cams, lim = rule('stare', 0);
    let lean = 0;
    for (const m of G.monsters) {
      if (brainOf(m).noStare) { m.watched = 0; continue; } // (a shy one only freezes when you look)
      const on = C.up && C.t >= 1 && C.lost <= 0 && m.state === 'roam' && m.room === C.cur;
      m.watched = on ? m.watched + dt : Math.max(0, m.watched - dt * 2);
      if (on && lim && m.watched >= lim && m.level > 0 && !G.inside && !G.powerOut && !G.freeze && G.grace <= 0) {
        m.watched = 0; // it lunges one room closer (the camera it was on cuts out)
        logStory({ kind: 'lunge', who: m.id }); // (before the step, so the story reads in order)
        stepToward(m);
        m.timer = m.def.moveEvery || 5;
        G.stats.lunges++;
      }
      const k = stareK(m, lim);
      m.animSpeed = 1 - 0.75 * k; // it holds still to look back at you
      if (on) lean = Math.max(lean, k);
    }
    C.staticAmt = Math.max(C.staticAmt, 0.3 * lean);
    return lean;
  }

  /* ----- what you hear: every camera room has its own sound, and each monster makes its noise in the walls ----- */
  /* the room you are watching plays its sound (config cameras[].sound / soundVol); the others are quiet */
  function updateRoomTones(C) {
    const watching = C.t > 0.5 && C.lost <= 0;
    for (const cam of CFG.cameras) {
      if (!cam.sound) continue;
      const vol = watching && C.cur === cam.id ? clamp(cam.soundVol != null ? +cam.soundVol || 0 : 0.3, 0, 1) * Director.duck : 0;
      Sound.loop('room:' + cam.id, vol, { sound: cam.sound, fade: 0.25, music: false });
    }
  }
  /* its presence sound (config presenceSound) by how many rooms it is from a door: louder and clearer as it
     comes closer, through the walls (muffled) when far. Coarse on purpose: the breathing still warns you, and
     the light still tells you. */
  const PRESENCE = { vol: [0, 0.26, 0.12, 0.06, 0.03], lowpass: [0, 2200, 1100, 650, 450], farVol: 0.02, farLowpass: 400 };
  const presenceDist = (m) => (m.state === 'roam' ? doorDist(m.def, m.room) : 0);
  function updatePresence(C) {
    const watching = C.up && C.t > 0.5 && C.lost <= 0;
    let nearest = null; // file mode: only the closest monster clicks (phones limit how many sounds play at once)
    if (!Sound.web) for (const m of G.monsters) if (m.def.presenceSound && (!nearest || presenceDist(m) < presenceDist(nearest))) nearest = m;
    for (const m of G.monsters) {
      if (!m.def.presenceSound) continue;
      let vol = 0, lowpass = 20000, pan = 0;
      if (!G.powerOut && (Sound.web || m === nearest)) {
        if (m.state === 'inside') vol = 0.9;
        else if (m.state === 'door') { const shut = G.doors[m.door].closed; vol = shut ? 0.22 : 0.55; lowpass = shut ? 600 : 20000; pan = sidePan(m.door); }
        else if (watching && m.room === C.cur) vol = 0.5; // the room you are looking at: right there, clear
        else {
          const d = doorDist(m.def, m.room), cam = camById[m.room];
          vol = PRESENCE.vol[d] != null ? PRESENCE.vol[d] : PRESENCE.farVol;
          lowpass = PRESENCE.lowpass[d] || PRESENCE.farLowpass;
          pan = cam ? (cam.map.x - 0.5) * 1.2 : 0;
        }
      }
      Sound.loop('presence:' + m.id, vol, { sound: m.def.presenceSound, lowpass, pan, fade: 0.6, music: false });
    }
  }

  /* ----- the room notices: it reacts to how close something is, so dread builds before anything costs you ----- */
  const WINDOW_PASS = 2.6; // seconds a shadow takes to cross the window
  function updateRoom(dt, realDt) {
    let p = 0;
    for (const m of G.monsters) {
      if (m.state === 'door' || m.state === 'inside') p = 1;
      else if (m.state === 'roam' && doorDist(m.def, m.room) === 1) p = Math.max(p, 0.5);
    }
    G.roomP = G.powerOut ? 0 : p;
    G.lampDim = lerp(G.lampDim, G.roomP === 1 ? 0.08 : 0, clamp(realDt * 3, 0, 1)); // a steady dim while it is at a door
    if (G.windowPass && (G.windowPass.t += dt) >= WINDOW_PASS) G.windowPass = null;
    // below 20% the desk clock can't be trusted: now and then its hands lurch ahead (20x for .3 s), then creep back
    if (G.clockSpin > 0) { G.clockSpin -= realDt; G.clockSkew += 19 * dt / hourSec(); }
    else {
      G.clockSkew *= Math.exp(-realDt / 2.5);
      if (G.luc < 20 && !G.powerOut && Math.random() < 0.24 * realDt) G.clockSpin = 0.3;
    }
  }
  /* the dust drifts toward the doorway something is standing in (x on screen; null = no pull) */
  function dustPull() {
    if (G.state !== 'night' || G.paused || G.cams.up) return null;
    const m = G.monsters.find((x) => x.state === 'door');
    if (!m) return null;
    const d = officeDoor(m.door);
    return officeOriginX() + (d.x + d.w / 2) * G.officeW;
  }
  /* a shadow walks past the window toward the side it is heading for (needs office.window, or the stand-in room) */
  function startWindowPass(m) {
    if (!officeSpot('window') || G.powerOut || G.windowPass) return;
    G.windowPass = { m, t: 0, dir: doorSide(m.def, m.room) === 'left' ? -1 : 1 };
  }

  function updateNight(dt, realDt) {
    const C = G.cams;
    runLater(dt);
    if (G.state !== 'night') return; // a timer ended the night
    G.settle = Math.max(0, G.settle - realDt); // landing in the chair after the jolt
    if (G.lesson) lessonUpdate(realDt);
    // clock (it waits while the first-night lesson runs)
    if (!G.lesson) G.nightT += dt;
    const hs = hourSec();
    const hour = Math.floor(G.nightT / hs);
    if (hour >= 6) { startWaking(); return; }
    if (hour !== G.hour) {
      G.hour = hour;
      hourLands(hour);
      Sound.play('hour_chime', { vol: 0.55, rate: 0.9 });
      Captions.show('chime', 0, 0.55, { arg: fmtHour(hour) });
      for (const m of G.monsters) { const b = (m.def.hourBoost || {})[hour]; if (b && m.level > 0) m.boost += b; }
    }

    // looking around (mouse at the edges, arrow keys, or a glide toward a light you just turned on)
    const maxScroll = Math.max(0, G.officeW - W);
    if (!C.up) {
      let v = 0;
      if (keys.ArrowLeft) v -= 950;
      if (keys.ArrowRight) v += 950;
      if (pointer.inside && pointer.type === 'mouse' && !v && !G.devDrag) { // (not while the art helper drags a door box)
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

    // doors: held like a breath (free for a while, then dearer and dearer), and a tired door can give way
    for (const s of ['left', 'right']) {
      const D = G.doors[s];
      holdDoor(s, D, dt);
      moveDoor(s, D, realDt);
      D.landT = Math.max(0, D.landT - realDt); D.bangT = Math.max(0, D.bangT - realDt);
    }
    // camera monitor
    C.t = clamp(C.t + (C.up ? 1 : -1) * realDt / 0.28, 0, 1);
    C.staticAmt = Math.max(0, C.staticAmt - realDt * 2.6);
    C.lost = Math.max(0, C.lost - realDt);
    const lean = updateStare(dt);

    // lucidity: what each thing costs goes into G.spend (the death screen shows where it went)
    if (!G.powerOut) {
      const L = G.doors.left, R = G.doors.right;
      const parts = { base: 1, doors: L.cost + R.cost, lights: (L.light || R.light) ? 1 : 0, cams: C.up ? 1 : 0 };
      G.usage = parts.base + parts.doors + parts.lights + parts.cams;
      if (!G.freeze) { // (the False Dawn holds it still)
        if (G.lesson) parts.base = 0; // the lesson: the clock waits, so just being asleep costs nothing; what you use still does
        const before = G.luc, rate = rule('drain', 0.12) * (G.lighter ? LIGHTER.drain : 1) * dt;
        for (const k in parts) { const d = rate * parts[k]; G.spend[k] += d; G.luc -= d; }
        if (G.lesson) G.luc = Math.max(G.luc, Math.min(before, LESSON_T.floor));
      }
      G.stats.minLuc = Math.min(G.stats.minLuc, Math.max(0, G.luc));
      if (G.luc <= 0) powerOutStart();
    }
    for (const s of ['left', 'right']) if (G.doors[s].light) G.litAt[s] = G.nightT; // (the death screen: did you check?)

    // monsters
    if (G.grace > 0) G.grace -= dt;
    const giveUp = strainCfg().giveUpAfter;
    for (const m of G.monsters) {
      if (G.freeze) break; // the False Dawn: every monster holds still, timers and all
      if (m.state === 'door') {
        m.linger -= dt;
        m.doorT += dt;
        m.breathT -= dt;
        if (m.breathT <= 0 && !silent()) {
          m.breathT = rand(5, 9); m.breathed = true;
          const D = G.doors[m.door];
          cue('breath', m.door, { monster: m, vol: D.closed ? 0.35 : 0.6, lowpass: D.closed ? 700 : 0, rate: rand(0.9, 1.05), cap: D.closed ? 'breathMuffled' : 'breath' });
        }
        if (G.doors[m.door].light && !m.seen && !G.powerOut) {
          m.seen = true; m.breathed = true;
          cue('breath', m.door, { monster: m, vol: 1, cap: 'breathClose' });
          hit(0.18);
          G.punch = { t: 0.3, side: m.door }; // you flinch toward it
        }
      }
      const B = brainOf(m);
      if (B.tick) B.tick(m, dt);
      if (G.powerOut || G.inside || G.grace > 0) continue;
      // a shut door wins: it doesn't camp there for ages, tempting you to hold your breath
      if (m.state === 'door' && G.doors[m.door].closed && m.linger <= 0 && m.doorT > giveUp) { monsterMove(m, true); continue; }
      if (m.hurry) { // it heard your pinch at its open door
        if (m.state !== 'door' || G.doors[m.door].closed) m.hurry = false; // (shut in time: it just bangs at its next chance)
        else if (m.linger <= 0) { monsterMove(m); continue; } // (walkerMove still keeps the promise: breath first, minWarning)
      }
      m.timer -= dt;
      if (m.timer <= 0) {
        m.timer += (m.def.moveEvery || 5) * rand(0.85, 1.15);
        monsterMove(m);
      }
    }

    updateLies(dt, realDt);
    updateRoom(dt, realDt);
    directorUpdate(dt);
    updateFalseDawn(dt);
    updateFinalStretch(dt);

    // something got in
    if (G.inside) {
      if (C.forceDown > 0) {
        C.forceDown -= dt;
        C.staticAmt = Math.max(C.staticAmt, 0.6);
        if (C.forceDown <= 0) { toggleCams(false); G.insideT = insideWait(rand(0.35, 0.6)); }
      } else if (!C.up) {
        G.insideT -= dt;
        const win = gentle() ? PRE_SCARE.gentle : PRE_SCARE.normal;
        if (G.insideT < win) startPreScare(1 - Math.max(0, G.insideT) / win);
        if (G.insideT <= 0) { jumpscare(G.inside); return; }
      }
    }

    // out of lucidity: the dream stops listening. The clock ticks slower and lower, stops, two seconds of silence…
    if (G.powerOut) {
      G.powerT += dt;
      if (G.killAt - G.powerT >= 2.2) clockTick(dt, 0.9, 1 - 0.55 * clamp(G.powerT / G.killAt, 0, 1));
      else if (!G.hush) { G.hush = true; Sound.stopLoop('clock_tick', 0.05); Sound.killLoops(); }
      if (G.powerT >= G.killAt && G.killer) { jumpscare(G.killer); return; }
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

    if (silent()) { updateHud(false); return; } // total silence before it comes

    // sound beds
    if (!G.powerOut) Sound.loop('ambience', (C.up ? 0.4 : 0.6) * Director.duck, { fade: 2 });
    const hushCam = C.cur === YOU_CAM.id ? 0.4 : 1; // CAM 7 is too quiet
    Sound.loop('static', C.t > 0.5 ? (0.12 + C.staticAmt * 0.35 + (C.lost > 0 ? 0.3 : 0)) * hushCam : 0, { fade: 0.15, music: false, rate: 1 + 0.4 * lean });
    const lightSide = G.doors.left.light ? 'left' : G.doors.right.light ? 'right' : null;
    Sound.loop('light_buzz', lightSide && !G.powerOut ? 0.4 : 0, { fade: 0.08, music: false, pan: lightSide === 'right' ? 0.6 : -0.6 });
    Sound.loop('heartbeat', G.danger > 0.45 ? clamp((G.danger - 0.3) * 1.2, 0, 0.85) : 0, { fade: 0.6, music: false, rate: 0.9 + G.danger * 0.35 });
    updateRoomTones(C);
    updatePresence(C);

    if (!G.lesson) G.whisperT -= dt; // (not in the middle of the lesson)
    if (G.whisperT <= 0) {
      G.whisperT = rand(28, 70);
      const w = { vol: rand(0.18, 0.35), rate: rand(0.75, 1.1), pan: rand(-0.9, 0.9) };
      Sound.play('whisper', w);
      Captions.show('whisper', w.pan, w.vol);
    }

    updateHud(false);
  }

  /* ------------------------------------------------------------------ */
  /*  RENDER                                                            */
  /* ------------------------------------------------------------------ */
  const canvas = $('#screen'), ctx = canvas.getContext('2d');
  const buf = makeCanvas(W, H), bx = buf.getContext('2d');
  /* Sharper on big and high-DPI screens: with Dream effects Full (not on phones) the picture is drawn with more
     pixels than 1600 x 900 (the shown size x devicePixelRatio, up to 2400 x 1350), so the photos stay crisp on a
     1080p or Retina screen. Everything is still drawn in the same 1600 x 900 coordinates (a scale on both canvases).
     If that makes the frame rate drop, it quietly goes back to 1600 x 900 for the rest of the visit. */
  const RES_MAX = 1.5;
  const sharp = { res: 1, slow: 0, off: false };
  function wantRes() {
    if (sharp.off || TOUCH || save.fx !== 'full') return 1;
    const r = stageScale * (window.devicePixelRatio || 1);
    return r > 1.1 ? Math.min(RES_MAX, Math.round(r * 4) / 4) : 1;
  }
  function applyRes() {
    const r = wantRes();
    if (r === sharp.res && canvas.width === Math.round(W * r)) return;
    sharp.res = r; sharp.slow = 0;
    for (const [c, x] of [[canvas, ctx], [buf, bx]]) {
      c.width = Math.round(W * r); c.height = Math.round(H * r);
      x.setTransform(r, 0, 0, r, 0, 0);
    }
  }
  /* the frame-rate guard: half a second at a time below ~40 fps, a few times running, and it gives up on it */
  function watchRes(dt) {
    if (sharp.res === 1 || G.paused || document.hidden || dt > 0.25) return; // (a hiccup or a tab switch is not slowness)
    sharp.slow = dt > 1 / 40 ? sharp.slow + dt : Math.max(0, sharp.slow - dt * 0.5);
    if (sharp.slow > 2.5) { sharp.off = true; applyRes(); }
  }
  const bloom = makeCanvas(160, 90), blx = bloom.getContext('2d');
  let bloomN = 0; // frames since the bloom started (it is refreshed every third one)

  function drawCover(c, img, x, y, w, h) {
    const s = Math.max(w / img.width, h / img.height);
    const dw = img.width * s, dh = img.height * s;
    c.drawImage(img, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh);
  }

  /* where a sprite lands in a box. pose: x = middle of its body, y = its feet, h = its height (fractions of the box),
     flip mirrors it, sy stretches it taller from the feet */
  function spriteRect(img, box, pose) {
    const p = pose || { x: 0.5, y: 1.02, h: 0.7 };
    const base = (p.h || 0.7) * box.h, h = base * (p.sy || 1), w = base * img.width / img.height;
    const cx = box.x + (p.x != null ? p.x : 0.5) * box.w, by = box.y + (p.y != null ? p.y : 1) * box.h;
    return { x: cx - w / 2, y: by - h, w, h };
  }
  function drawSprite(c, img, box, pose, alpha) {
    const r = spriteRect(img, box, pose);
    c.save(); c.globalAlpha = alpha == null ? 1 : alpha;
    if (pose && pose.flip) { c.translate(r.x + r.w / 2, 0); c.scale(-1, 1); c.drawImage(img, -r.w / 2, r.y, r.w, r.h); }
    else c.drawImage(img, r.x, r.y, r.w, r.h);
    c.restore();
  }
  /* the first time a monster's picture is really shown to you (on a camera, in a lit doorway, as one of the dream's
     lies, or when it catches you), Extras learns its name and story (save.met) */
  function meet(def) {
    if (!def || save.met[def.id] || (G.state !== 'night' && G.state !== 'jumpscare' && G.state !== 'waking')) return;
    save.met[def.id] = true; writeSave();
  }
  /* a monster in a lit doorway or on a camera. At 6 AM it stops moving, stretches and melts away.
     ground: 'floor' = a soft contact shadow under its feet; 'water' = that, and its reflection in the water */
  function drawMonster(c, m, box, pose, ground) {
    const k = G.state === 'waking' ? meltK() : 0;
    if (k >= 1) return;
    meet(m.def);
    const img = m.art.soft[m.frame()], p = Object.assign({ x: 0.5, y: 1.02, h: 0.7 }, pose, { sy: 1 + 0.15 * k });
    if (ground) footShadow(c, img, box, p, 1 - k);
    if (ground === 'water') reflection(c, img, box, p, 1 - k);
    drawSprite(c, img, box, p, 1 - k);
  }
  /* a soft dark pool where its feet meet the floor (so it stands in the room instead of hovering over it) */
  function footShadow(c, img, box, pose, a) {
    const r = spriteRect(img, box, pose), cx = r.x + r.w / 2, cy = r.y + r.h - r.h * 0.025, rx = r.w * 0.27, ry = Math.max(3, rx * 0.2);
    c.save(); c.globalAlpha = 0.42 * a; c.translate(cx, cy); c.scale(1, ry / rx);
    const g = c.createRadialGradient(0, 0, 0, 0, 0, rx);
    g.addColorStop(0, 'rgba(4,2,8,1)'); g.addColorStop(0.55, 'rgba(4,2,8,.55)'); g.addColorStop(1, 'rgba(4,2,8,0)');
    c.fillStyle = g; c.beginPath(); c.arc(0, 0, rx, 0, Math.PI * 2); c.fill();
    c.restore();
  }
  /* its upside-down twin in still black water: faint, fading with depth, trembling in thin bands */
  function reflection(c, img, box, pose, a) {
    const r = spriteRect(img, box, pose), feet = r.y + r.h, n = 14, band = r.h * 0.6 / n, k = fxMul();
    c.save();
    for (let i = 0; i < n; i++) {
      const y0 = feet + i * band, sy = img.height * (1 - (i + 1) * band / r.h), sh = img.height * band / r.h; // (rows going up the body)
      const dx = Math.sin(G.t * 1.7 + i * 0.9) * (1 + i * 0.35) * k;
      c.globalAlpha = 0.24 * a * (1 - i / n) ** 1.5;
      c.save(); c.translate(r.x + r.w / 2 + dx, y0 + band / 2); c.scale(pose.flip ? -1 : 1, -1);
      c.drawImage(img, 0, Math.max(0, sy), img.width, sh, -r.w / 2, -band / 2, r.w, band + 0.5);
      c.restore();
    }
    c.restore();
  }

  function officeOriginX() { return G.officeW <= W ? (W - G.officeW) / 2 : -G.scroll; }
  /* a doorway's box on screen right now */
  function doorBox(side) {
    const d = officeDoor(side), ox = officeOriginX(), ow = G.officeW;
    return { x: ox + d.x * ow, y: d.y * H, w: d.w * ow, h: d.h * H };
  }

  /* the desk-room view: the room's slow "breathing", the flinch toward a doorway, and at Lucidity zero you
     seem to shrink in your chair while the room grows away from you */
  function officeView(c) {
    const br = 0.006 * fxMul();
    let s = 1 + br + Math.sin(G.t * 0.6) * br;
    if (G.powerOut) s *= 1 - 0.16 * ease(clamp(G.powerT / G.killAt, 0, 1)) * fxMul();
    c.translate(W / 2, H / 2); c.scale(s, s); c.translate(-W / 2, -H / 2);
    if (G.punch) { // the flinch: a quick lean toward the doorway the light just found something in
      const b = doorBox(G.punch.side), px = b.x + b.w / 2, py = b.y + b.h / 2;
      const k = 1 + 0.02 * ease(clamp(G.punch.t / 0.3, 0, 1)) * fxMul();
      c.translate(px, py); c.scale(k, k); c.translate(-px, -py);
    }
  }

  function drawOffice(c) {
    c.fillStyle = '#000'; c.fillRect(0, 0, W, H);
    c.save(); officeView(c);
    c.drawImage(Art.office, officeOriginX(), 0, G.officeW, H);
    drawWindowPass(c);
    drawDeskClock(c);
    drawLampBreath(c);
    for (const side of ['left', 'right']) drawDoorway(c, side);
    c.restore();

    // lamp flicker (a slow timer, never a strobe; more nervous when something is close) & darkness
    c.fillStyle = `rgba(0,0,0,${(0.08 + flick(G.lampFlick) + G.lampDim).toFixed(3)})`; c.fillRect(0, 0, W, H);
    if (G.powerOut) {
      c.fillStyle = `rgba(0,0,0,${clamp(G.powerT / 1.2, 0, 1) * 0.86})`; c.fillRect(0, 0, W, H);
      c.save(); officeView(c); drawApproach(c); c.restore();
    }
    if (G.preScare > 0) { c.fillStyle = `rgba(0,0,0,${(0.92 * ease(G.preScare)).toFixed(3)})`; c.fillRect(0, 0, W, H); } // the dark before it
  }

  /* the lamp breathes: a warm glow swelling and sinking at its light (director event; office.lamp or the stand-in) */
  function drawLampBreath(c) {
    const L = officeSpot('lamp');
    if (G.lampBreath == null || !L) return;
    const t = G.lampBreath, env = clamp(t / 1.5, 0, 1) * clamp((15 - t) / 1.5, 0, 1);
    const x = officeOriginX() + L.x * G.officeW, y = L.y * H;
    c.save(); c.globalCompositeOperation = 'lighter';
    glow(c, x, y, H * 0.42, 'rgba(255,186,104,A)', ((0.1 + 0.1 * Math.sin(t * 2)) * env).toFixed(3));
    c.restore();
  }
  /* the four panes of glass in office.jpg (x, y, w, h in its 2400 x 900 pixels): around them are the sash, the cross
     bars and the meeting rail */
  const OFFICE_PANES = [[591, 182, 103, 109], [701, 182, 81, 109], [591, 304, 103, 112], [701, 304, 81, 112]];
  /* the shadow crossing the window (clipped to the glass, walking, never stopping) */
  function drawWindowPass(c) {
    const P = G.windowPass, w = officeSpot('window');
    if (!P || !w || G.powerOut) return;
    const r = { x: officeOriginX() + w.x * G.officeW, y: w.y * H, w: w.w * G.officeW, h: w.h * H };
    const img = P.m.art.sil[P.m.frame()], h = r.h * 1.5, sw = h * img.width / img.height;
    const k = P.t / WINDOW_PASS, from = r.x + r.w / 2 - P.dir * (r.w + sw) / 2;
    const cx = from + P.dir * (r.w + sw) * k, feet = r.y + r.h * 1.4 - Math.abs(Math.sin(P.t * 4.5)) * 5 * fxMul(); // (a slow, heavy step)
    c.save(); c.beginPath();
    if (Art.officePhoto) { // the photo desk room: only the four panes of glass (the frame and the cross bars stay in front of it)
      const ox = officeOriginX(), kx = G.officeW / 2400, ky = H / 900;
      for (const [x, y, w, h] of OFFICE_PANES) c.rect(ox + x * kx, y * ky, w * kx, h * ky);
    } else c.rect(r.x + r.w * 0.1, r.y, r.w * 0.8, r.h); // (inset: it passes behind curtains and frame)
    c.clip();
    c.globalAlpha = 0.94; c.translate(cx, 0); if (P.dir < 0) c.scale(-1, 1);
    c.drawImage(img, -sw / 2, feet - h, sw, h);
    c.restore();
  }
  /* the desk clock tells the night's real time (12 to 6), unless your Lucidity is so low it starts to lie.
     The stand-in room gets the whole twin-bell clock; your own desk room picture just gets the hands. */
  function drawDeskClock(c) {
    const k = clockOnScreen();
    if (!k) return;
    const ringing = G.state === 'waking' || (G.fd && G.fd.phase === 'ring');
    const hrs = ringing ? 6 : clamp(G.nightT / hourSec(), 0, 6) + G.clockSkew; // (it says six while it rings)
    const o = { h: Math.floor(hrs), m: (hrs % 1) * 60, ring: ringing ? 1 : 0 };
    if (Art.officePhoto) drawClockPhoto(c, k.x, k.y, k.r / 0.78, o, DESK_CLOCK_LIGHT);
    else if (Art.officeMissing) drawAlarmClock(c, k.x, k.y, k.r / 0.78, o);
    else { c.save(); c.translate(k.x, k.y); clockHands(c, k.r, o); c.restore(); }
  }
  /* the whole clock in the light of a photo room (drawn on a small canvas of its own and shaded there, so the room
     around it is untouched). light: [left, right] colours laid over it. The desk clock: a little warm lamplight on
     its left, its right side in the monitor's shadow. The morning clock: in the shade on the left, sun on the right. */
  const DESK_CLOCK_LIGHT = ['rgba(46,24,12,.32)', 'rgba(10,6,22,.62)'], MORNING_CLOCK_LIGHT = ['rgba(52,28,14,.3)', 'rgba(255,236,200,.03)'];
  /* the photo clock (assets/scenes/clock.png, a real twin-bell alarm clock cut out of its photo, in the game's grade):
     where its dial is (cx, cy: fractions of its width and height) and how big its round body and its dial are
     (body, face: radius, a fraction of its width). The code draws its hands.
     Its light: colours it is multiplied by, [left, right, top, bottom] (the warm lamp, the moon, the morning sun) */
  const CLOCK_PHOTO = { cx: 0.5, cy: 0.604, body: 0.4217, face: 0.3842 }; // (printed by art-src/compose/scene_clock.py)
  const CLOCK_LIGHT = {
    desk: ['rgb(226,170,118)', 'rgb(74,64,104)', 'rgb(255,255,255)', 'rgb(150,140,160)'],
    night: ['rgb(132,126,184)', 'rgb(104,98,150)', 'rgb(255,255,255)', 'rgb(170,166,196)'],
    morning: ['rgb(182,160,146)', 'rgb(255,246,230)', 'rgb(255,255,255)', 'rgb(200,184,170)'],
  };
  const NIGHT_CLOCK_LIGHT = CLOCK_LIGHT.night;
  /* the photo clock with its hands, lit by light (CLOCK_LIGHT), ringing and squashed like drawAlarmClock.
     Without the photo: the painted clock, shaded the old way */
  let photoClockCanvas = null;
  function drawClockPhoto(c, x, y, r, o, light) {
    const P = Art.clock;
    if (!P) {
      const old = light === CLOCK_LIGHT.morning ? MORNING_CLOCK_LIGHT : light === CLOCK_LIGHT.night ? null : DESK_CLOCK_LIGHT;
      if (old) drawShadedClock(c, x, y, r, o, old); else drawAlarmClock(c, x, y, r, o);
      return;
    }
    if (!Array.isArray(light) || light.length < 4) light = CLOCK_LIGHT.desk;
    const s = r / (CLOCK_PHOTO.body * P.width), w = Math.ceil(P.width * s), h = Math.ceil(P.height * s);
    if (!photoClockCanvas || photoClockCanvas.width < w || photoClockCanvas.height < h) photoClockCanvas = makeCanvas(Math.max(w, 8), Math.max(h, 8));
    const k = photoClockCanvas.getContext('2d'), cx = CLOCK_PHOTO.cx * w, cy = CLOCK_PHOTO.cy * h;
    k.globalCompositeOperation = 'source-over'; k.clearRect(0, 0, photoClockCanvas.width, photoClockCanvas.height);
    k.drawImage(P, 0, 0, w, h);
    k.save(); k.translate(cx, cy); clockHands(k, CLOCK_PHOTO.face * w, o); k.restore();
    if (blendOk('multiply')) { // the room's light on it: across (left to right), then a little from above
      k.globalCompositeOperation = 'multiply';
      let g = k.createLinearGradient(0, 0, w, 0); g.addColorStop(0, light[0]); g.addColorStop(1, light[1]);
      k.fillStyle = g; k.fillRect(0, 0, w, h);
      g = k.createLinearGradient(0, 0, 0, h); g.addColorStop(0, light[2]); g.addColorStop(1, light[3]);
      k.fillStyle = g; k.fillRect(0, 0, w, h);
      k.globalCompositeOperation = 'destination-in'; k.drawImage(P, 0, 0, w, h); // (keep only the clock)
      k.globalCompositeOperation = 'source-over';
    }
    const ring = (o.ring || 0) * fxMul(), wob = Math.sin(G.t * Math.PI * 2 * 12);
    c.save(); c.translate(x + wob * 0.065 * r * ring, y + Math.cos(G.t * 71) * 0.02 * r * ring);
    if (ring) c.rotate(wob * 0.035 * ring);
    if (o.squash) { c.translate(0, r * 1.05); c.scale(1 + 0.12 * o.squash, 1 - 0.18 * o.squash); c.translate(0, -r * 1.05); }
    c.drawImage(photoClockCanvas, 0, 0, w, h, -cx, -cy, w, h);
    c.restore();
  }
  let clockCanvas = null;
  function drawShadedClock(c, x, y, r, o, light) {
    const s = Math.ceil(r * 2.4), n = s * 2;
    if (!clockCanvas || clockCanvas.width !== n) clockCanvas = makeCanvas(n, n);
    const k = clockCanvas.getContext('2d');
    k.globalCompositeOperation = 'source-over'; k.clearRect(0, 0, n, n);
    drawAlarmClock(k, s, s, r, o);
    k.globalCompositeOperation = 'source-atop';
    const g = k.createLinearGradient(s - r, 0, s + r, 0);
    g.addColorStop(0, light[0]); g.addColorStop(1, light[1]);
    k.fillStyle = g; k.fillRect(0, 0, n, n);
    c.drawImage(clockCanvas, x - s, y - s);
  }

  /* Lucidity zero: on each tick it stands somewhere new, bigger every time: the left door, the window, the right door …
     (only the doors it can really reach: a monster whose path only ends at the right door never shows up on the left) */
  function approachAnchors() {
    const sides = doorsOf(G.killer.def), w = officeSpot('window'), list = [];
    if (sides.left) list.push(Object.assign(doorBox('left'), { side: 'left' }));
    if (w) list.push({ x: officeOriginX() + w.x * G.officeW, y: w.y * H, w: w.w * G.officeW, h: w.h * H, side: 'window' });
    if (sides.right) list.push(Object.assign(doorBox('right'), { side: 'right' }));
    if (!list.length) list.push(Object.assign(doorBox('left'), { side: 'left' }));
    return list;
  }
  function drawApproach(c) {
    const m = G.killer;
    if (!m || G.hush || G.powerT < 1.5) return;
    const k = clamp(G.powerT / G.killAt, 0, 1), off = save.fx === 'off';
    if (!off && ((G.tickPh % 1) + 1) % 1 >= 0.5) return; // seen only on the "tick" half of each tick (1 Hz or slower)
    const anchors = approachAnchors(), a = anchors[Math.floor(G.powerT / 3.4) % anchors.length];
    const h = 0.55 + 0.6 * k, f = m.frame();
    const pose = a.side === 'window' ? { x: 0.5, y: 1 + h * 0.45, h } // in the window: from the chest up
      : Object.assign({}, doorPoseOf(m, a.side), { h, y: 1 });
    c.save(); c.beginPath(); c.rect(a.x, a.y, a.w, a.h); c.clip();
    drawSprite(c, rimmedSil(m.art.sil[f]), a, pose, off ? lerp(0.15, 0.5, k) : 0.9);
    c.restore();
  }
  /* a black silhouette with a thin red edge, so it reads in the dark (baked once per frame, so it fades as one shape) */
  const rimCache = new WeakMap();
  function rimmedSil(sil) {
    let c = rimCache.get(sil);
    if (c) return c;
    c = makeCanvas(sil.width + 8, sil.height + 6);
    const x = c.getContext('2d');
    for (const [dx, dy] of [[0, 4], [8, 4], [4, 0]]) x.drawImage(sil, dx, dy);
    x.globalCompositeOperation = 'source-in'; x.fillStyle = 'rgba(200,20,40,.35)'; x.fillRect(0, 0, c.width, c.height);
    x.globalCompositeOperation = 'source-over'; x.drawImage(sil, 4, 4);
    rimCache.set(sil, c);
    return c;
  }

  /* a camera pose, leaning in toward the lens by k (0..1) while you stare at it (no zoom with Dream effects Off) */
  function leanPose(pose, k) {
    const p = pose || { x: 0.5, y: 1.02, h: 0.7 };
    if (!k || save.fx === 'off') return p;
    return Object.assign({}, p, { h: (p.h || 0.7) * (1 + 0.28 * k), y: (p.y != null ? p.y : 1) + 0.1 * k, x: lerp(p.x != null ? p.x : 0.5, 0.5, 0.35 * k) });
  }

  /* a lie: the monster's frozen frame, its colour drained and washed violet, with a faint glowing rim (no filters).
     fade 0..1: it dissolves, with one smear as it lets go (a door fake the light has found) */
  function drawLie(c, L, box, pose, fade) {
    const alpha = LIE.alpha * (1 - fade);
    if (alpha <= 0.01) return;
    meet(L.who.def);
    const img = ghostOf(L.who.art.soft[L.frame]), p = Object.assign({ x: 0.5, y: 1.02, h: 0.7 }, pose);
    const at = (dx) => ({ x: box.x + dx, y: box.y, w: box.w, h: box.h });
    drawSprite(c, img, box, p, alpha);
    c.save(); c.globalCompositeOperation = 'lighter';
    for (const dx of [-2, 2]) drawSprite(c, img, at(dx), p, 0.15 * (1 - fade));
    if (fade > 0 && save.fx !== 'off') drawSprite(c, img, at(p.flip ? -6 : 6), p, alpha * 0.6);
    c.restore();
  }

  /* where a monster stands in a lit doorway (config doorPose, or a pose that fits the whole body in) */
  function doorPoseOf(m, side) {
    return (m.def.doorPose && m.def.doorPose[side]) || { x: side === 'left' ? 0.55 : 0.45, y: 1, h: 0.7, flip: side === 'right' };
  }

  function drawDoorway(c, side) {
    const D = G.doors[side], A = Art.doors[side];
    const box = doorBox(side);
    if (box.x > W + 40 || box.x + box.w < -40) return;
    const lit = D.light && !G.powerOut;
    c.save();
    c.beginPath(); c.rect(box.x, box.y, box.w, box.h); c.clip();
    const here = G.monsters.filter((m) => m.state === 'door' && m.door === side);
    const wrong = lit && !here.length && G.wrongDoor && G.wrongDoor.side === side; // the light shows some other room
    if (wrong) {
      drawCover(c, Art.cams[G.wrongDoor.cam], box.x, box.y, box.w, box.h);
      c.save(); c.globalCompositeOperation = 'multiply'; c.fillStyle = 'rgb(130,215,200)'; c.fillRect(box.x, box.y, box.w, box.h);
      c.globalCompositeOperation = 'lighter'; glow(c, box.x + box.w / 2, box.y + box.h * 0.2, box.h * 0.7, 'rgba(150,255,225,A)', 0.22); c.restore();
    } else if (lit || A.dark) c.drawImage(lit ? A.lit : A.dark, box.x, box.y, box.w, box.h);
    else { // your own desk room, no darkImage: the doorway you painted, in a soft darkness that deepens toward the back
      const g = c.createLinearGradient(0, box.y, 0, box.y + box.h);
      g.addColorStop(0, 'rgba(0,0,0,.5)'); g.addColorStop(0.6, 'rgba(0,0,0,.32)'); g.addColorStop(1, 'rgba(0,0,0,.2)');
      c.fillStyle = g; c.fillRect(box.x, box.y, box.w, box.h);
    }
    if (lit) {
      for (const m of here) drawMonster(c, m, box, doorPoseOf(m, side), 'floor');
      if (!here.length) for (const L of G.lies) if (L.kind === 'door' && L.side === side) drawLie(c, L, box, doorPoseOf(L.who, side), lieFade(L));
      if (DEV) Dev.inDoorway(c, side, box); // (the art helper's see-through monster, for placing doorPose)
      // the light stutters while something real stands there (slow timer; a steady dim with effects Off)
      const dim = here.length ? (save.fx === 'off' ? 0.3 : flick(G.stutter[side])) : 0;
      if (dim) { c.fillStyle = `rgba(0,0,0,${dim})`; c.fillRect(box.x, box.y, box.w, box.h); }
      const g = c.createLinearGradient(0, box.y, 0, box.y + box.h); // (the bulb is above the door: a warm wash from the top)
      g.addColorStop(0, 'rgba(255,200,130,.16)'); g.addColorStop(0.6, 'rgba(255,200,130,0)'); g.addColorStop(1, 'rgba(0,0,0,.08)');
      c.fillStyle = g; c.fillRect(box.x, box.y, box.w, box.h);
    }
    if (D.p > 0) drawShutter(c, side, D, A.closed, box);
    c.restore();
    if (DEV) Dev.doorFrame(c, side, box); // (the art helper's green door box)
  }

  /* the shut door: it judders and cracks when held too long, wobbles when something bangs on it */
  function drawShutter(c, side, D, img, box) {
    const k = fxMul(), strain = D.cost > 1 ? strainK(D) : 0;
    let y = box.y - box.h * (1 - D.p);
    if (strain) y += Math.sin(G.t * 38) * (D.cost - 1) * 2.5 * k * (D.gaspT > 0 ? 2 : 1);
    if (D.gaspT > 0) y -= 10 * k * (1 - D.gaspT / 1.5); // it starts to lift off its seat
    const b = D.bangT / 0.6;
    c.save();
    if (b > 0) { // one decaying wobble, not a flicker
      const cx = box.x + box.w / 2;
      c.translate(cx, 4 * b * Math.sin(b * 55) * k); c.scale(1 + 0.04 * b * Math.sin(b * 40) * k, 1); c.translate(-cx, 0);
    }
    c.drawImage(img, box.x, y, box.w, box.h);
    if (strain) drawCracks(c, side, box, y, strain);
    c.restore();
    const seat = 6 + 10 * (D.landT / 0.5); // the shadow where it meets the floor (darker just after it lands)
    c.fillStyle = 'rgba(0,0,0,.5)'; c.fillRect(box.x, y + box.h - seat, box.w, seat);
    if (b > 0) glow(c, box.x + box.w / 2, y + box.h * 0.45, box.w * 0.75, 'rgba(255,32,56,A)', 0.6 * b);
  }

  /* 2-4 dark cracks that spread as a held door strains (the same cracks every time, over any door picture) */
  const crackCache = {};
  function crackLines(side) {
    if (crackCache[side]) return crackCache[side];
    const r = mulberry32(side === 'left' ? 41 : 42), lines = [];
    for (let i = 0; i < 4; i++) {
      let x = 0.2 + r() * 0.6, y = 0.12 + r() * 0.7;
      const pts = [[x, y]], dir = r() * Math.PI * 2;
      for (let j = 0; j < 5; j++) { const a = dir + (r() - 0.5) * 1.6; x += Math.cos(a) * 0.09; y += Math.sin(a) * 0.07; pts.push([x, y]); }
      lines.push(pts);
    }
    return (crackCache[side] = lines);
  }
  function drawCracks(c, side, box, y, strain) {
    const n = 2 + Math.round(2 * strain);
    c.save(); c.lineJoin = 'round'; c.lineCap = 'round';
    for (const [lw, col] of [[3.5, `rgba(0,0,0,${0.25 + 0.6 * strain})`], [1, `rgba(255,236,220,${0.12 * strain})`]]) {
      c.lineWidth = lw; c.strokeStyle = col;
      for (const pts of crackLines(side).slice(0, n)) {
        c.beginPath();
        pts.forEach(([px, py], i) => { const X = box.x + px * box.w + (lw < 2 ? 1 : 0), Y = y + py * box.h; if (i) c.lineTo(X, Y); else c.moveTo(X, Y); });
        c.stroke();
      }
    }
    c.restore();
  }

  /* what a monster stands on in a camera room: the game's own photos have floors (and the Drowned Parlor, water);
     a picture of your own gets the soft floor shadow too (water only where the photo has it) */
  const SCENE_WATER = { parlor: true };
  function camGround(cam) { return Art.standIn[`camera "${cam.id}"`] === 'photo' && SCENE_WATER[cam.id] ? 'water' : 'floor'; }
  /* the camera picture is zoomed in a little and pans slowly (so its very edges come and go) */
  function camFeedBox() {
    const fw = W * CAM_ZOOM, fh = H * CAM_ZOOM;
    const cam = camById[G.cams.cur];
    const pan = (G.devGhost ? 0.5 : Math.sin(G.t * 0.23 + cam.index * 1.7) * 0.5 + 0.5);
    return { x: -(fw - W) * pan, y: -(fh - H) / 2, w: fw, h: fh };
  }

  function drawCams(c) {
    const C = G.cams, cam = camById[C.cur];
    const box = camFeedBox();
    c.fillStyle = '#000'; c.fillRect(0, 0, W, H);
    const lost = C.lost > 0;
    if (cam.id === YOU_CAM.id) drawYouCam(c, box);
    else drawCover(c, Art.cams[cam.id], box.x, box.y, box.w, box.h);
    if (!lost && cam.id !== YOU_CAM.id) {
      const lim = rule('stare', 0);
      for (const m of G.monsters) {
        if (m.state !== 'roam' || m.room !== cam.id) continue;
        const pose = leanPose(m.def.poses && m.def.poses[cam.id], stareK(m, lim)), B = brainOf(m);
        if (B.drawCam) B.drawCam(c, m, box, pose, camGround(cam)); else drawMonster(c, m, box, pose, camGround(cam)); // (a sleeper is drawn asleep)
      }
      const real = G.monsters.some((m) => m.state === 'roam' && m.room === cam.id);
      if (!real) for (const L of G.lies) if (L.kind === 'cam' && L.room === cam.id) drawLie(c, L, box, L.who.def.poses && L.who.def.poses[cam.id], 0);
    }
    if (DEV) Dev.camGhost(c, cam, box); // (the art helper's see-through monster, for placing poses)
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
    c.drawImage(Art.camOver, 0, 0); // scanlines + vignette
    c.restore();
    // monitor frame
    c.strokeStyle = 'rgba(0,0,0,.9)'; c.lineWidth = 40; c.strokeRect(0, 0, W, H);
  }

  /* you from behind in CAM 7's photo (made once for each size): head and shoulders, dark, a warm rim of lamplight on
     the left, the monitor's faint teal glow round the top, and the room's film grain. The back of the photo's chair
     (assets/scenes/cam7_chair.png, drawn over you) hides where you end. */
  const CAM7_CHAIR = { x: 670, y: 700 }; // where cam7_chair.png sits in cam7_you.jpg (its top-left corner, in pixels; scene_cam7.CHAIR_LAYER)
  const youFigures = {};
  function youFigure(k) {
    const key = k.toFixed(3);
    if (youFigures[key]) return youFigures[key];
    const w = Math.ceil(480 * k), h = Math.ceil(420 * k), hx = w / 2, hy = 92 * k;
    const c = makeCanvas(w, h), x = c.getContext('2d');
    const path = (g) => {
      g.beginPath(); // shoulders and neck
      g.moveTo(hx - 215 * k, hy + 320 * k); g.bezierCurveTo(hx - 215 * k, hy + 150 * k, hx - 140 * k, hy + 105 * k, hx - 42 * k, hy + 88 * k);
      g.lineTo(hx - 34 * k, hy + 40 * k); g.lineTo(hx + 34 * k, hy + 40 * k); g.lineTo(hx + 42 * k, hy + 88 * k);
      g.bezierCurveTo(hx + 140 * k, hy + 105 * k, hx + 215 * k, hy + 150 * k, hx + 215 * k, hy + 320 * k); g.closePath();
      g.ellipse(hx, hy, 62 * k, 78 * k, 0, 0, 7); // head
    };
    let g = x.createLinearGradient(0, 0, w, 0); // a dark jumper and dark hair, a little warmer on the lamp side
    g.addColorStop(0, '#22171a'); g.addColorStop(0.4, '#120d14'); g.addColorStop(1, '#0a080e');
    path(x); x.fillStyle = g; x.fill();
    const rimOf = (color, dx, dy, x0, x1) => { // an edge light: you, minus you moved away from the light (a thin crescent)
      const rim = makeCanvas(w, h), r = rim.getContext('2d');
      path(r); r.fillStyle = color; r.fill();
      r.globalCompositeOperation = 'destination-out'; r.save(); r.translate(dx, dy); path(r); r.fillStyle = '#000'; r.fill(); r.restore();
      if (x1 != null) { // fading out across you
        r.globalCompositeOperation = 'destination-in';
        const m = r.createLinearGradient(x0, 0, x1, 0); m.addColorStop(0, 'rgba(0,0,0,1)'); m.addColorStop(1, 'rgba(0,0,0,0)');
        r.fillStyle = m; r.fillRect(0, 0, w, h);
      }
      return rim;
    };
    x.globalCompositeOperation = 'source-atop'; // (only on you, never outside your edge)
    x.drawImage(rimOf('rgba(255,184,112,.75)', 7 * k, 2 * k, hx - 120 * k, hx + 90 * k), 0, 0); // the lamp, on your left
    x.drawImage(rimOf('rgba(140,240,200,.22)', 0, 5 * k), 0, 0); // the monitor's glow round your head and shoulders
    noiseFill(x, w, h, 0.05, 23, Math.max(1, 1.6 * k));
    x.globalCompositeOperation = 'destination-in'; path(x); x.fillStyle = '#000'; x.fill(); // (grain only inside)
    x.globalCompositeOperation = 'source-over';
    return (youFigures[key] = { canvas: c, hx, hy });
  }
  /* CAM 7: your desk room from behind and above, and you in your chair, lit by the monitor.
     config youCam.image replaces the room (then seat: { x, y, size } says where the back of your head goes).
     The game's own photo of it (assets/scenes/cam7_you.jpg) has its chair in it, and its own seat (SCENE_SEAT). */
  function drawYouCam(c, box) {
    const Y = G.youCam || {}, own = Art.youCam, cfg = Art.youCamPhoto ? { seat: SCENE_SEAT } : CFG.youCam || {};
    if (own) drawCover(c, own, box.x, box.y, box.w, box.h);
    else { // the desk room picture, centred on the desk and darkened, with the monitor's teal glow
      const s = box.h / H, ow = officeWidthFor(Art.office) * s;
      c.drawImage(Art.office, box.x + box.w / 2 - ow / 2, box.y, ow, box.h);
      c.fillStyle = 'rgba(0,0,0,.45)'; c.fillRect(box.x, box.y, box.w, box.h);
      c.save(); c.globalCompositeOperation = 'lighter';
      glow(c, box.x + box.w * 0.5, box.y + box.h * 0.55, box.w * 0.32, 'rgba(110,255,200,A)', 0.16);
      c.restore();
    }
    // you, from behind: shoulders and head over the back of your chair (the chair is empty on the last night)
    const seat = Object.assign({ x: 0.5, y: 0.5, size: 1 }, own ? cfg.seat : null);
    const k = seat.size * box.h / H, hx = box.x + seat.x * box.w, hy = box.y + seat.y * box.h; // the middle of your head
    if (!Y.empty && Art.youCamPhoto) { // in the photo: you, lit like the room (lamp on your left, the monitor in front of you)
      const f = youFigure(k);
      c.drawImage(f.canvas, hx - f.hx, hy - f.hy);
    }
    if (Art.youCamPhoto && Art.youCamChair) { // the back of the chair in the photo, in front of you
      const s = Math.max(box.w / own.width, box.h / own.height), x0 = box.x + (box.w - own.width * s) / 2, y0 = box.y + (box.h - own.height * s) / 2;
      const ch = Art.youCamChair, q = own.width / 1824; // (CAM7_CHAIR is in cam7_you.jpg's own pixels)
      c.drawImage(ch, x0 + CAM7_CHAIR.x * q * s, y0 + CAM7_CHAIR.y * q * s, ch.width * q * s, ch.height * q * s);
    }
    c.save(); c.lineWidth = 3; c.lineJoin = 'round';
    if (!Y.empty && !Art.youCamPhoto) {
      c.fillStyle = '#050307'; c.strokeStyle = 'rgba(150,255,210,.28)'; // dark, with the monitor's light on the edges
      c.beginPath(); // shoulders and neck
      c.moveTo(hx - 215 * k, hy + 300 * k); c.bezierCurveTo(hx - 215 * k, hy + 150 * k, hx - 140 * k, hy + 105 * k, hx - 42 * k, hy + 88 * k);
      c.lineTo(hx - 34 * k, hy + 40 * k); c.lineTo(hx + 34 * k, hy + 40 * k); c.lineTo(hx + 42 * k, hy + 88 * k);
      c.bezierCurveTo(hx + 140 * k, hy + 105 * k, hx + 215 * k, hy + 150 * k, hx + 215 * k, hy + 300 * k); c.closePath();
      c.fill(); c.stroke();
      c.beginPath(); c.ellipse(hx, hy, 62 * k, 78 * k, 0, 0, 7); c.fill(); c.stroke(); // head
    }
    if (!own) { // the back of the chair, in front of you (a picture of your own has its chair in it)
      const cx = hx - 165 * k, cy = hy + 135 * k, cw = 330 * k, ch = 420 * k;
      c.beginPath();
      if (c.roundRect) c.roundRect(cx, cy, cw, ch, 46 * k); else c.rect(cx, cy, cw, ch);
      c.fillStyle = '#0d0912'; c.fill();
      c.strokeStyle = 'rgba(150,255,210,.16)'; c.stroke();
      c.fillStyle = 'rgba(255,255,255,.03)'; c.fillRect(cx + 30 * k, cy + 40 * k, cw - 60 * k, 8 * k); // a seam in the leather
    }
    c.restore();
    // look back a second time: it is standing right behind you, looming over your shoulder (a lie: frozen, violet,
    // breathing backwards). It stays to one side, so your head and chair still say "that's you"
    if (Y.stage === 2 && Y.lie) drawLie(c, Y.lie, box, { x: 0.3, y: 1.1, h: 0.95 }, 0);
  }

  /* ----- the title screen: the game's photo of the dark hall (a door left ajar, its lamplight breathing and now and
     then sputtering, low fog drifting by), leaning a little with the mouse or with the tilt of a phone. Dream effects
     Low: calmer; Off: it stands still. Without the photo: the old drifting fog. There is never a monster here:
     you meet it in the dream. ----- */
  const menuPar = { x: 0, y: 0, tx: 0, ty: 0 };      // the lean (-1..1): smoothed toward the mouse or the tilt
  const menuLamp = { wait: 2.5, t: 0, dur: 0, a: 0 }; // the door light's sputters: each one a slow dip, 1.5-5 s apart
  const tilt = { x: 0, y: 0, bx: null, by: null, at: 0 };
  window.addEventListener('deviceorientation', (e) => { // a phone held in landscape: tilting it turns the hall a little
    if (e.beta == null || e.gamma == null) return;
    const ang = (screen.orientation && screen.orientation.angle) || window.orientation || 0;
    const rx = ang === 90 ? e.beta : ang === -90 || ang === 270 ? -e.beta : e.gamma, ry = ang === 90 ? -e.gamma : ang === -90 || ang === 270 ? e.gamma : e.beta;
    if (tilt.bx == null) { tilt.bx = rx; tilt.by = ry; }
    tilt.bx += (rx - tilt.bx) * 0.01; tilt.by += (ry - tilt.by) * 0.01; // (the way you hold it drifts back to "straight")
    tilt.x = clamp((rx - tilt.bx) / 18, -1, 1); tilt.y = clamp((ry - tilt.by) / 18, -1, 1); tilt.at = performance.now();
  });
  function updateMenuScene(dt) {
    const still = save.fx === 'off';
    const mouse = pointer.type === 'mouse' && pointer.inside, tilted = performance.now() - tilt.at < 1000;
    menuPar.tx = still ? 0 : mouse ? clamp(pointer.x / W * 2 - 1, -1, 1) : tilted ? tilt.x : 0;
    menuPar.ty = still ? 0 : mouse ? clamp(pointer.y / H * 2 - 1, -1, 1) : tilted ? tilt.y : 0;
    const k = 1 - Math.exp(-dt * 2.2); // (slow and soft)
    menuPar.x += (menuPar.tx - menuPar.x) * k; menuPar.y += (menuPar.ty - menuPar.y) * k;
    const L = menuLamp;
    if (L.dur > 0) { L.t += dt; if (L.t >= L.dur) { L.dur = 0; L.wait = rand(1.5, 5); } }
    else if ((L.wait -= dt) <= 0) { L.dur = rand(0.35, 0.8); L.t = 0; L.a = rand(0.45, 1); }
  }
  function drawMenuScene(c) {
    const M = Art.menu;
    if (!M) { // no photo: the old scene, fog drifting in the dark
      c.fillStyle = '#05030a'; c.fillRect(0, 0, W, H);
      for (let i = 0; i < 5; i++) {
        const fx = W * (0.5 + 0.45 * Math.sin(G.t * 0.05 + i * 1.7)), fy = H * (0.5 + 0.35 * Math.cos(G.t * 0.07 + i * 2.3));
        c.drawImage(Art.fog[i % 2], fx - 520, fy - 520, 1040, 1040);
      }
      return;
    }
    const fx = save.fx, calm = fx === 'off' ? 0 : fx === 'low' ? 0.5 : 1;
    // the lean: the picture is drawn 2% bigger, so its edges never show; the near fog moves more than the room
    const S = 1.02, dx = -menuPar.x * 13 * calm, dy = -menuPar.y * 7 * calm; // (half as much with effects Low)
    c.save(); c.translate(W / 2 + dx, H / 2 + dy); c.scale(S, S); c.translate(-W / 2, -H / 2);
    c.drawImage(M.base, 0, 0, W, H);
    if (M.lit) { // the light through the door: it breathes (the picture has it at 80%: this adds up to ~20% more) …
      const B = MENU_LIGHT_BOX, up = 0.1 + (0.07 * Math.sin(G.t * 0.8) + 0.03 * Math.sin(G.t * 2.3 + 1)) * calm;
      c.save(); c.globalCompositeOperation = 'lighter'; c.globalAlpha = clamp(up, 0, 0.25); c.drawImage(M.lit, B.x, B.y); c.restore();
      const L = menuLamp, dip = L.dur > 0 ? L.a * Math.sin(Math.PI * L.t / L.dur) * 0.55 * calm : 0; // … and now and then it sputters (a slow dip, never a flash)
      if (dip > 0.01) { c.save(); c.globalAlpha = dip; c.drawImage(M.dim, B.x, B.y); c.restore(); }
    }
    c.restore();
    if (M.fog) { // the low fog: two copies side by side, drifting left (slower with effects Low, still with Off)
      const fw = W * 1.1, fh = 420 * fw / W, y = 450 - menuPar.y * 12 * calm, off = ((G.t * 9 * calm) % fw + fw) % fw, x0 = -off - menuPar.x * 22 * calm;
      c.save(); c.globalAlpha = 0.9;
      for (let x = x0 - fw; x < W; x += fw) c.drawImage(M.fog, x, y, fw + 1, fh);
      c.restore();
    }
  }

  /* overshoots its target, then settles back (the lunge) */
  const easeOutBack = (u) => 1 + 2.70158 * Math.pow(u - 1, 3) + 1.70158 * Math.pow(u - 1, 2);
  const easeOut = (u) => 1 - (1 - u) * (1 - u);
  /* red and cyan copies of a jumpscare frame for the colour split (small: they are only fringes), made once */
  const splitCache = new WeakMap();
  function splitTints(img) {
    let T = splitCache.get(img);
    if (!T) {
      const k = Math.min(1, 600 / img.height), small = makeCanvas(img.width * k, img.height * k);
      small.getContext('2d').drawImage(img, 0, 0, small.width, small.height);
      splitCache.set(img, T = { red: tinted(small, '#ff2a3a'), cyan: tinted(small, '#25f0ff') });
    }
    return T;
  }

  /* where the picture goes: its jumpscareFocus (the face) at the middle, a little above centre. Once it is bigger
     than the screen it is kept covering it (no empty edge); smaller, it stays inside it. Grows smoothly either way. */
  function scareRect(m, img, s, dx, dy) {
    const h = H * s, w = h * img.width / img.height, f = m.def.jumpscareFocus || { x: 0.5, y: 0.2 };
    const x = W / 2 - f.x * w + dx, y = H * 0.42 - f.y * h + dy;
    return { w, h, x: clamp(x, Math.min(0, W - w), Math.max(0, W - w)), y: clamp(y, Math.min(0, H - h), Math.max(0, H - h)) };
  }

  /* the jumpscare (t = G.jumpT). Normal: LUNGE 0-.3 s (overshoots, colour split), STARE .3-1 s (it sways, one red
     pulse), COLLAPSE 1-1.5 s (it freezes and folds into a line like an old TV switching off).
     Dream effects Low: half the split, no tearing. Off: a calm zoom and a fade. Gentle: it fades in and out, smaller. */
  function drawJumpscare(c) {
    const m = G.killer, t = G.jumpT, S = G.scare;
    c.fillStyle = '#000'; c.fillRect(0, 0, W, H);
    if (!m || !S) return;
    const frames = m.art.jump, n = frames.length, fx = save.fx;
    const calm = S.gentle || fx === 'off'; // Gentle and Dream effects Off: its calm walking pace, no frantic flicker of frames
    const fps = calm ? m.def.fps || 4 : m.def.jumpscareFps || 14;
    const playing = (from) => (S.fi + Math.floor(Math.max(0, t - from) * fps)) % n;
    let fi = playing(0), s = 1.15, alpha = 1, dx = 0, dy = 0, split = 0, pulse = 0, fold = 0;
    if (S.gentle) {
      alpha = Math.min(1, t / JUMP.gentleIn) * (1 - clamp((t - JUMP.gentleOut) / (JUMP.gentleEnd - JUMP.gentleOut), 0, 1));
    } else if (fx === 'off') {
      s = 0.8 + 0.8 * easeOut(clamp(t / 0.5, 0, 1));
      alpha = 1 - clamp((t - JUMP.stare) / (JUMP.end - JUMP.stare), 0, 1);
    } else if (t < JUMP.lunge) {
      const u = t / JUMP.lunge;
      fi = S.fi; s = 0.6 + 1.5 * easeOutBack(u);
      split = 22 * (1 - u) * (fx === 'low' ? 0.5 : 1);
    } else if (t < JUMP.stare) {
      fi = playing(JUMP.lunge); s = 2.1 + 0.1 * (t - JUMP.lunge);
      const sway = (Math.sin(t * 5.1) + Math.sin(t * 3.3 + 1)) * 5 * fxMul();
      dx = sway; dy = sway * 0.4;
      pulse = 0.28 * Math.sin(Math.PI * clamp((t - JUMP.lunge) / (JUMP.stare - JUMP.lunge), 0, 1));
    } else {
      fi = (S.fi + Math.floor((JUMP.stare - JUMP.lunge) * fps)) % n; // frozen
      s = 2.1 + 0.1 * (JUMP.stare - JUMP.lunge);
      fold = clamp((t - JUMP.stare) / (JUMP.end - JUMP.stare), 0, 1);
    }
    const img = frames[fi], r = scareRect(m, img, s, dx, dy);
    const sx = t > 1.35 ? Math.max(0.004, 1 - ease(clamp((t - 1.35) / 0.15, 0, 1))) : 1; // (the line shrinks to a dot at the end)
    c.save();
    if (fold > 0) { // squash what is on screen (only that: the rest of the picture stays out of sight) to a line
      c.translate(W / 2, H / 2); c.scale(sx, Math.max(0.006, 1 - ease(fold))); c.translate(-W / 2, -H / 2);
      c.beginPath(); c.rect(0, 0, W, H); c.clip();
    }
    c.globalAlpha = alpha;
    if (split > 0.5) {
      const T = splitTints(frames[S.fi]);
      c.globalCompositeOperation = 'lighter'; c.globalAlpha = 0.5;
      c.drawImage(T.red, r.x - split, r.y, r.w, r.h); c.drawImage(T.cyan, r.x + split, r.y, r.w, r.h);
      c.globalCompositeOperation = 'source-over'; c.globalAlpha = alpha;
    }
    c.drawImage(img, r.x, r.y, r.w, r.h);
    if (fold > 0) { // static eats the frozen picture as it folds
      c.globalAlpha = fold; c.imageSmoothingEnabled = false;
      c.drawImage(Art.noise[Math.floor(G.t * 24) % Art.noise.length], 0, 0, W, H);
      c.imageSmoothingEnabled = true;
    }
    c.restore();
    if (pulse > 0) { c.fillStyle = `rgba(200,0,20,${pulse.toFixed(3)})`; c.fillRect(0, 0, W, H); } // one red pulse, never a strobe
    if (fold > 0) { // the bright line it collapses into (it brightens as the picture folds into it)
      const lw = W * sx;
      c.save(); c.globalCompositeOperation = 'lighter'; c.globalAlpha = Math.min(1, fold * 2);
      c.fillStyle = '#fff'; c.fillRect(W / 2 - lw / 2, H / 2 - 2, lw, 4);
      c.restore();
    }
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
    const ox = officeOriginX();
    c.save();
    for (const p of G.parts) {
      c.globalAlpha = clamp(p.life / p.max, 0, 1);
      const x = p.o ? ox + p.x : p.x;
      c.drawImage(tinted(Art.dot, p.col), x - p.r * 2, p.y - p.r * 2, p.r * 4, p.r * 4);
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

  /* ----- falling asleep, waking up, the morning ----- */
  const FALL_ASLEEP = { // what you count in your head (config.js fallAsleep can change any of them)
    1: 'one… two… three…', 2: 'one… two… two… two…', 3: 'one… three… nine… the house is counting with you',
    4: 'don’t count. it counts backwards.', 5: 'don’t count. just listen for the alarm.', endless: 'there is no counting here.',
  };
  function fallAsleepLine() {
    const own = CFG.fallAsleep || {}, key = G.endless ? 'endless' : G.night;
    return String(own[key] != null ? own[key] : FALL_ASLEEP[key] || '');
  }
  const MORNING_CLOCK = { x: 800, y: 770, r: 92 }; // the alarm clock right by your face in the morning

  /* your bedroom at night: streetlight sliding through the blinds, three slow blinks, counting, then sleep */
  function drawFallAsleep(c) {
    const t = G.introT, o = lidOpen(t), P = G.retry ? INTRO.retry : INTRO.full;
    c.drawImage(Art.bedroomNight, 0, 0);
    if (save.fx === 'full' && !TOUCH && Art.bedroomBlur.length) drawBlurred(c, (1 - o) * 6 + t * 0.8); // your eyes go out of focus
    else { c.fillStyle = `rgba(0,0,0,${(1 - o) * 0.5})`; c.fillRect(0, 0, W, H); }
    c.save(); c.globalCompositeOperation = 'lighter'; c.fillStyle = 'rgba(190,200,255,.06)';
    for (let i = 0; i < 4; i++) { // a car's headlights pass through the blinds
      const x = ((t * 260 * fxMul() + i * 90 + 500) % (W + 600)) - 300;
      c.beginPath(); c.moveTo(x, 0); c.lineTo(x + 46, 0); c.lineTo(x - 214, H); c.lineTo(x - 260, H); c.closePath(); c.fill();
    }
    c.restore();
    drawEyelids(c, 1 - o);
    c.save(); c.textAlign = 'center';
    if (P.text != null && t > P.text) { // counting in your head, typed slowly, fading with every blink
      const line = fallAsleepLine(), n = Math.min(line.length, Math.floor((t - P.text) * 22));
      c.globalAlpha = o; c.font = '38px "Special Elite", monospace'; c.fillStyle = '#e6dccc';
      c.shadowColor = 'rgba(157,132,255,.6)'; c.shadowBlur = 12;
      c.fillText(line.slice(0, n), W / 2, H * 0.78);
    }
    if (t > 0.8 && !G.cardShown) { // how to skip it
      c.globalAlpha = 0.35; c.shadowBlur = 0; c.font = Math.round(TOUCH ? Math.max(26, 14 / stageScale) : 26) + 'px VT323, monospace'; // >= 14 real px on a phone
      c.fillStyle = '#e9dfcf'; c.textAlign = 'right';
      c.fillText(TAP + ' to skip', W - 40, H - 34);
    }
    c.restore();
  }

  /* the bedroom blurred by b px: the two nearest baked copies, cross-faded */
  function drawBlurred(c, b) {
    const L = [{ b: 0, img: null }].concat(Art.bedroomBlur);
    let i = 0;
    while (i < L.length - 1 && L[i + 1].b <= b) i++;
    if (L[i].img) c.drawImage(L[i].img, 0, 0, W, H);
    if (i < L.length - 1) { c.globalAlpha = clamp((b - L[i].b) / (L[i + 1].b - L[i].b), 0, 1); c.drawImage(L[i + 1].img, 0, 0, W, H); c.globalAlpha = 1; }
  }

  /* the dream as you leave it at 6 AM: the colour drains, daylight floods in from the window, the desk clock rings.
     t: seconds since it rang; k: how strongly (1 = the real morning, .4 = the False Dawn); rgb: the light's colour */
  function drawWakeOverlay(c, t, k, rgb) {
    c.save();
    if (SAT_OK) { c.globalCompositeOperation = 'saturation'; c.globalAlpha = Math.min(1, t / 2.5) * k; c.fillStyle = '#888'; }
    else { c.globalAlpha = 0.35 * Math.min(1, t / 2.5) * k; c.fillStyle = '#777'; }
    c.fillRect(0, 0, W, H);
    c.restore();
    const w = officeSpot('window');
    const gx = w ? officeOriginX() + (w.x + w.w / 2) * G.officeW : W / 2, gy = w ? (w.y + w.h / 2) * H : H * 0.3;
    const g = c.createRadialGradient(gx, gy, 0, gx, gy, W * 0.8);
    g.addColorStop(0, `rgba(${rgb},${(clamp(t / 3.2, 0, 1) * k).toFixed(3)})`); g.addColorStop(1, `rgba(${rgb},0)`);
    c.fillStyle = g; c.fillRect(0, 0, W, H);
    const clk = clockOnScreen();
    if (clk && G.cams.t < 1) drawRingArcs(c, clk.x, clk.y, clk.r, k);
  }

  /* your real bedroom in the morning: warm light through the blinds, the alarm clock, and whatever followed you out */
  function drawMorning(c) {
    c.drawImage(Art.bedroomMorning, 0, 0);
    c.save(); c.fillStyle = 'rgba(255,220,160,.10)';
    for (let i = 0; i < 5; i++) { // sunlight bars from the blinds across the wall
      const y = 190 + i * 58;
      c.beginPath(); c.moveTo(1040, y); c.lineTo(1040, y + 24); c.lineTo(380, y + 354); c.lineTo(380, y + 330); c.closePath(); c.fill();
    }
    c.restore();
    drawEvidence(c);
    drawMotes(c, 0.45);
    const ringing = G.state !== 'win', K = MORNING_CLOCK;
    if (ringing) drawRingArcs(c, K.x, K.y, K.r, 0.8);
    const o = { h: 6, m: 0, ring: ringing ? 1 : 0, squash: G.state === 'win' ? G.slapT / 0.25 : 0 };
    if (Art.bedroomPhoto) { // (in the photo bedroom: a soft shadow on the quilt, and the room's light on it)
      c.save(); c.fillStyle = 'rgba(20,10,6,.35)'; c.beginPath(); c.ellipse(K.x + 10, K.y + K.r * 1.08, K.r * 0.95, K.r * 0.16, 0, 0, Math.PI * 2); c.fill(); c.restore();
      drawClockPhoto(c, K.x, K.y, K.r, o, CLOCK_LIGHT.morning);
    } else drawAlarmClock(c, K.x, K.y, K.r, o);
    if (G.state === 'morning') drawEyelids(c, wakeLids(G.wakeT));
  }

  /* where bedroom_ev2.jpg / bedroom_ev4.jpg go on bedroom_morning.jpg (their top-left corners, in its pixels) */
  const EV_PATCH = { 2: { x: 96, y: 110 }, 4: { x: 200, y: 650 } }; // (scene_bedroom.EV_PATCH)
  /* something followed you out of the dream (Nights 2-4; config morning.evidence can use your own pictures) */
  function drawEvidence(c) {
    const n = G.night;
    if (G.endless || !EVIDENCE_SPOTS[n]) return;
    const b = spotPx(evidenceCfg(n)), img = Art.evidence[n], patch = !img && Art.evPatch && Art.evPatch[n];
    c.save();
    if (patch) c.drawImage(patch, EV_PATCH[n].x, EV_PATCH[n].y); // (the photo bedroom: the evidence is in the photo)
    else if (img) { // your picture, fitted into the spot and standing on its bottom edge
      const s = Math.min(b.w / img.width, b.h / img.height);
      c.drawImage(img, b.x + (b.w - img.width * s) / 2, b.y + b.h - img.height * s, img.width * s, img.height * s);
    } else if (n === 2) { // the closet door is open a crack
      c.strokeStyle = '#2a2026'; c.lineWidth = 6; c.strokeRect(b.x, b.y, b.w, b.h);
      const g = c.createLinearGradient(b.x + b.w - 44, 0, b.x + b.w, 0); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,.45)');
      c.fillStyle = g; c.fillRect(b.x + b.w - 44, b.y, 44, b.h);
      c.fillStyle = '#050307'; c.fillRect(b.x + b.w - 4, b.y + 3, 4, b.h - 3);
    } else if (n === 3) { // the drawing from the desk-room wall, leaning on your bedside table (in the morning light)
      const d = Art.drawingDay || (Art.drawingDay = shadedDrawing(['rgb(236,222,200)', 'rgb(214,196,172)']));
      const s = Math.min(b.w / d.width, b.h / d.height), dw = d.width * s, dh = d.height * s;
      c.translate(b.x + b.w / 2, b.y + b.h); c.rotate(-0.07);
      c.fillStyle = 'rgba(0,0,0,.25)'; c.fillRect(-dw / 2 + 6, -dh + 4, dw, dh);
      c.drawImage(d, -dw / 2, -dh, dw, dh);
    } else { // a ragged scrap of pink collar on the floor
      const pts = [[0, 0.35], [0.18, 0.1], [0.4, 0.3], [0.62, 0.05], [0.85, 0.25], [1, 0.55], [0.78, 0.9], [0.45, 0.7], [0.15, 0.95]];
      c.fillStyle = '#e8828f'; c.strokeStyle = '#a54d5b'; c.lineWidth = 2;
      c.beginPath(); pts.forEach(([px, py], i) => c[i ? 'lineTo' : 'moveTo'](b.x + px * b.w, b.y + py * b.h)); c.closePath(); c.fill(); c.stroke();
      c.fillStyle = 'rgba(120,40,52,.6)'; for (let i = 1; i < 6; i++) c.fillRect(b.x + b.w * i / 6.5, b.y + b.h * 0.48, 3, 2);
      c.strokeStyle = '#d9c27e'; c.lineWidth = 2.5; c.beginPath(); c.arc(b.x + b.w + 5, b.y + b.h * 0.55, 5, 0, 7); c.stroke(); // its tag ring
    }
    c.restore();
  }

  /* the dream itself: the desk room or the cameras (with the monitor sliding in between) */
  function drawDreamView(c) {
    if (G.cams.t >= 1) { drawCams(c); return; }
    const settling = G.state === 'night' && G.settle > 0;
    const drop = settling ? 50 * ease(G.settle / 1.2) * fxMul() : 0; // you land in the chair after the jolt
    c.save(); if (drop) c.translate(0, drop);
    drawOffice(c);
    drawMotes(c, G.powerOut ? 0.3 : 1);
    drawParts(c);
    c.restore();
    if (drop) { c.fillStyle = '#000'; c.fillRect(0, 0, W, drop); }
    if (G.cams.t > 0) {
      const y = H * (1 - ease(G.cams.t));
      c.save(); c.translate(0, y);
      c.fillStyle = '#050806'; c.fillRect(0, 0, W, H);
      c.globalAlpha = 0.9; c.imageSmoothingEnabled = false;
      c.drawImage(Art.noise[Math.floor(G.t * 24) % Art.noise.length], 0, 0, W, H);
      c.imageSmoothingEnabled = true; c.globalAlpha = 1;
      c.strokeStyle = '#000'; c.lineWidth = 40; c.strokeRect(0, 0, W, H);
      c.restore();
    }
    if (settling && save.fx === 'off' && G.settle > 0.8) { c.fillStyle = `rgba(0,0,0,${(G.settle - 0.8) / 0.4})`; c.fillRect(0, 0, W, H); } // Off: a plain fade-in
  }

  function render() {
    const st = G.state;
    const fx = save.fx, amt = fx === 'full' ? 1 : fx === 'low' ? 0.35 : 0;
    let ghost = 1, warp = 0, vignette = 1;
    if (st === 'menu' || st === 'boot') {
      drawMenuScene(bx);
      drawMotes(bx, 1);
      drawParts(bx);
      warp = fx === 'full' ? 2 : 0;
      ghost = fx === 'full' ? 0.75 : 1;
    } else if (st === 'asleep') {
      drawFallAsleep(bx);
    } else if (st === 'night' || st === 'dead' || st === 'waking') {
      drawDreamView(bx);
      warp = (1.5 + G.danger * 7) * amt;
      ghost = fx === 'full' ? 0.82 : 1;
      if (st === 'night') warp += 10 * G.settle * amt; // the jolt
      if (st === 'waking') { // the dream lets go of you
        drawWakeOverlay(bx, G.wakeT, 1, '255,255,255');
        drawEyelids(bx, wakeLids(G.wakeT));
        warp *= clamp(1 - G.wakeT, 0, 1); ghost = lerp(ghost, 1, clamp(G.wakeT, 0, 1));
      } else if (G.fd) { // the False Dawn: a warm, weak morning that isn't one
        const fk = falseDawnK();
        if (fk > 0) drawWakeOverlay(bx, G.fd.t, fk, '255,226,180');
        warp *= 1 - fk;
      }
    } else if (st === 'morning' || st === 'win') {
      drawMorning(bx); // the real world: no warp, no ghosting
      vignette = 0.45;
    } else if (st === 'jumpscare') {
      drawJumpscare(bx);
      warp = (fx === 'full' ? 9 : fx === 'low' ? 3 : 0) * (G.scare && G.scare.gentle ? 0.25 : 1);
    } else {
      bx.fillStyle = '#000'; bx.fillRect(0, 0, W, H);
    }
    // just after a pinch the dream is sharp, then it seeps back in
    const dreamy = 1 - clamp(G.clarity / 0.6, 0, 1);
    warp *= dreamy; ghost = lerp(1, ghost, dreamy);

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
    // the first moment of a jumpscare tears the picture sideways in a few bands (Dream effects Full only)
    const tear = st === 'jumpscare' && G.scare && G.scare.tear.length && G.jumpT < 0.18 ? G.scare.tear : null, tk = tear ? 1 - G.jumpT / 0.18 : 0;
    // "Low" is also the lighter mode for slower devices: no wavy strips and no bloom (the shake and ghosting stay calm)
    const R = sharp.res;
    if ((warp < 1 || fx !== 'full') && !tear) ctx.drawImage(buf, 0, 0, W, H);
    else {
      const SH = tear ? 6 : clamp(Math.floor(40 / warp), 6, 24); // (taller strips while it barely wobbles: neighbours stay within ~1 px)
      for (let y = 0; y < H; y += SH) {
        let dx = Math.sin(y * 0.011 + G.t * 1.6) * warp + Math.sin(y * 0.037 - G.t * 0.8) * warp * 0.35;
        if (tear) for (const b of tear) if (y >= b.y0 && y < b.y1) dx += b.dx * tk;
        ctx.drawImage(buf, 0, y * R, W * R, SH * R, dx - warp, y, W + warp * 2, SH);
      }
    }
    ctx.globalAlpha = 1;
    if (fx === 'full') {
      if (++bloomN % 3 === 1) { blx.clearRect(0, 0, 160, 90); blx.drawImage(buf, 0, 0, 160, 90); } // (a soft glow: every third frame is plenty)
      ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = 0.16;
      ctx.drawImage(bloom, 0, 0, W, H);
      ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
    }
    ctx.globalAlpha = vignette; ctx.drawImage(Art.vignette, 0, 0); ctx.globalAlpha = 1;
    if (G.danger > 0.05 && (st === 'night')) {
      const pulse = 0.5 + 0.5 * Math.sin(G.t * (4 + G.danger * 5)) * fxMul(); // a slow pulse; steady with effects Off
      ctx.globalAlpha = clamp(G.danger * 0.45 * (0.5 + pulse * 0.5), 0, 1);
      ctx.drawImage(Art.danger, 0, 0, W, H); ctx.globalAlpha = 1;
    }
    ctx.restore();
    if (DEV) Dev.overlay(ctx); // (the art helper: which file a stand-in picture is waiting for, the jumpscare focus)
    const fl = fx === 'off' ? Math.min(G.flash, 0.25) : G.flash;
    flashEl.style.opacity = fl > 0.01 ? fl : 0;
    if (fl > 0.01) flashEl.style.background = `rgb(${G.flashColor})`;
  }
  const flashEl = $('#flash');

  /* ------------------------------------------------------------------ */
  /*  HUD + UI                                                          */
  /* ------------------------------------------------------------------ */
  const hudEls = {
    night: $('#hudNight'), time: $('#hudTime'), pct: $('#lucPct'), fill: $('#lucFill'), lucBox: $('#lucBox'),
    glyph: {}, // the drain glyphs, by data-k: you, ldoor, rdoor, light, cam
    lDoor: $('#btnLDoor'), lLight: $('#btnLLight'), rDoor: $('#btnRDoor'), rLight: $('#btnRLight'), lPanel: $('#leftPanel'), rPanel: $('#rightPanel'),
    camBar: $('#camBar'), pinch: $('#pinchBtn'), pinchCd: $('#pinchCd'), pinchAmt: $('#pinchAmt'), overlay: $('#camOverlay'),
    stamp: $('#camStamp'), signal: $('#camSignal'), camLabel: $('#camBar span'), voice: $('#voiceBox'), you: $('#youMark'),
    eye: $('#lucEye'), lid: $('#lucEye .lid'), lash: $('#lucEye .lash'), label: $('#lucLabel'), camName: $('#camName'), ghost: $('#hourGhost'),
  };
  document.querySelectorAll('#usage i').forEach((i) => { hudEls.glyph[i.dataset.k] = i; });
  let lastHud = {};
  function setText(el, key, v) { if (lastHud[key] !== v) { lastHud[key] = v; el.textContent = v; } }
  /* like setText, but for trusted HTML (e.g. numify); key null = always write */
  function setHtml(el, key, html) { if (key == null || lastHud[key] !== html) { if (key != null) lastHud[key] = html; el.innerHTML = html; } }
  function setCls(el, cls, on) { if (el.classList.contains(cls) !== !!on) el.classList.toggle(cls, !!on); }
  function setVar(el, key, name, v) { if (lastHud[key] !== v) { lastHud[key] = v; el.style.setProperty(name, v); } }

  /* one-shot CSS effects (style.css has a @keyframes with the same name as each class): adding the class plays it
     from the start, and the class takes itself off when its animation ends. Hidden elements are skipped, so an
     effect never plays late when they show up again. */
  const PULSES = ['pressed', 'deny', 'hit', 'ripple', 'bangL', 'bangR', 'breathL', 'breathR', 'rollBack', 'ghostIn', 'blink', 'hourLand', 'ghostOut'];
  function pulseCls(el, cls) {
    if (!el.getClientRects().length) return;
    el.classList.remove(cls); if (cls !== 'pressed') el.classList.remove('pressed'); // a bigger effect replaces the press flash
    void el.offsetWidth; el.classList.add(cls);
  }
  const endPulse = (e) => {
    const name = e.animationName;
    if (PULSES.indexOf(name) >= 0) {
      // (restarting an effect cancels the old one a moment later: that must not switch off the new one)
      if (e.type === 'animationcancel' && e.target.getAnimations && e.target.getAnimations().some((a) => a.animationName === name)) return;
      (e.target.closest('.' + name) || e.target).classList.remove(name); // (the eye blinks its inner part)
    } else if (name === 'gainUp' || name === 'capLife') e.target.remove();
  };
  document.addEventListener('animationend', endPulse);
  document.addEventListener('animationcancel', endPulse);
  /* hide or show a HUD group; hiding it also drops any effect that had not finished (it must not replay later) */
  function showHud(el, on) {
    if (!on && !el.classList.contains('hidden')) for (const x of [el, ...el.querySelectorAll('*')]) x.classList.remove(...PULSES);
    setCls(el, 'hidden', !on);
  }
  /* a key press shows on its HUD button too */
  function pressFx(el) { if (el) pulseCls(el, 'pressed'); }
  /* "+8" rises out of the Lucidity box */
  function showGain(n) {
    const el = document.createElement('div');
    el.className = 'lucGain'; el.textContent = '+' + n;
    hudEls.lucBox.appendChild(el);
  }

  /* ----- the HUD dreams too: below 30% Lucidity its words slip for a blink ("13 AM", "LUCKILY", "NIGHT 33").
     Never with Dream effects Off, never at Lucidity zero, never for a while after a pinch (G.hudLock),
     and never the percentage. ----- */
  const SLIP = { below: 30, perSec: 0.72, show: 0.12, gap: 0.4 }; // perSec: how often at 0% (each word, at most every .52 s)
  const slips = {};
  /* the real text, or now and then (more often the lower you are) one of the alts, for 120 ms */
  function dreamy(key, real, alts) {
    const now = performance.now() / 1000, S = slips[key] || (slips[key] = { until: 0, alt: '', next: 0, last: now });
    const dt = Math.min(0.1, now - S.last);
    S.last = now;
    if (now < S.until) return S.alt;
    const on = alts.length && G.state === 'night' && !G.paused && save.fx !== 'off' && !G.powerOut && G.hudLock <= G.t && G.luc < SLIP.below;
    if (on && now >= S.next && Math.random() < (SLIP.below - G.luc) / SLIP.below * SLIP.perSec * dt) {
      S.alt = pick(alts); S.until = now + SLIP.show; S.next = S.until + SLIP.gap;
      return S.alt;
    }
    return real;
  }
  /* write a HUD word that can slip (num: its digits in the VT323 font) */
  function slipText(el, key, real, alts, num) {
    const t = dreamy(key, real, alts);
    if (num) setHtml(el, key, numify(t)); else setText(el, key, t);
    setCls(el, 'slip', t !== real);
  }
  /* your eye's lid droops as Lucidity sinks: its edge goes from above the eye (2) to halfway down (12) */
  function eyeLid(pct) {
    const e = 2 + 10 * (1 - clamp(pct, 0, 100) / 100), c = (2 * e - 12).toFixed(1); // (c: the curve's control point)
    if (lastHud.lid !== c) {
      lastHud.lid = c;
      hudEls.lid.setAttribute('d', `M0 0 L48 0 L48 12 L46 12 Q24 ${c} 2 12 L0 12 Z`);
      hudEls.lash.setAttribute('d', `M2 12 Q24 ${c} 46 12`);
    }
    setCls(hudEls.eye, 'low', pct <= 15); setCls(hudEls.eye, 'twitch', pct <= 15 && !G.powerOut);
  }
  /* a new hour lands: the clock drops into place, and the hour drifts past, huge and faint */
  function hourLands(hour) {
    pulseCls(hudEls.time, 'hourLand');
    setHtml(hudEls.ghost, null, numify(fmtHour(hour)));
    pulseCls(hudEls.ghost, 'ghostOut');
  }

  function updateHud(force) {
    if (force) lastHud = {};
    const n = G.night, nightTxt = G.endless ? 'ENDLESS' : 'NIGHT ' + n;
    slipText(hudEls.night, 'night', nightTxt, G.endless ? ['ENDLESS?', 'NIGHT ∞', 'NIGHT 0'] : ['NIGHT ' + n + n, 'NIGHT ∞', 'NIGHT ' + (n + 1)], true);
    // the clock: hours, then minutes in the final half hour (warm, like the dawn); "6 AM" while the False Dawn rings
    const min = nightMin(), ringing = !!G.fd && G.fd.phase !== 'after', late = G.state === 'night' && (min >= FINAL_MIN || G.fdRolled);
    const timeTxt = ringing ? fmtHour(6) : late ? Math.floor(min / 60) + ':' + String(Math.floor(min % 60)).padStart(2, '0') : fmtHour(G.hour);
    slipText(hudEls.time, 'time', timeTxt, ringing ? [] : [fmtHour(G.hour) + '?', '13 AM', (G.hour ? G.hour + 12 : 24) + ' AM']);
    setCls(hudEls.time, 'dawn', ringing || late);
    slipText(hudEls.label, 'label', 'LUCIDITY', ['LUCIDLY', 'LUCKILY', 'L U C I D', 'LUCIDITY?']);
    const pct = Math.max(0, Math.ceil(G.luc));
    setText(hudEls.pct, 'pct', pct + '%'); // (the percentage itself never lies)
    eyeLid(pct);
    hudEls.fill.style.width = clamp(G.luc, 0, 100) + '%';
    setCls(hudEls.pct, 'low', pct <= 15); setCls(hudEls.fill, 'low', pct <= 15);
    // the line where the dream starts to lie (Nights 2+)
    const lies = rule('lies', false) && !G.powerOut, below = liesCfg().below;
    setCls(hudEls.lucBox, 'lies', lies); setCls(hudEls.lucBox, 'under', lies && G.luc < below);
    setVar(hudEls.lucBox, 'lieAt', '--lieAt', below + '%');
    // what is draining you: the glyph lights up; a door's fills while you hold it and turns red once it costs extra
    const L = G.doors.left, R = G.doors.right, g = hudEls.glyph, on = !G.powerOut;
    setCls(g.you, 'on', on); setCls(g.light, 'on', on && (L.light || R.light)); setCls(g.cam, 'on', on && G.cams.up);
    const free = rule('doorFree', 12);
    for (const [D, glyph, btn, k] of [[L, g.ldoor, hudEls.lDoor, 'l'], [R, g.rdoor, hudEls.rDoor, 'r']]) {
      const fill = (Math.round(clamp(D.held / free, 0, 1) * 50) / 50).toFixed(2), over = on && D.cost > 1;
      setCls(glyph, 'on', on && D.closed); setCls(glyph, 'over', over); setCls(btn, 'over', over);
      setVar(glyph, k + 'gs', '--s', fill); setVar(btn, k + 'bs', '--s', fill);
    }
    setCls(hudEls.lDoor, 'on', L.closed); setCls(hudEls.rDoor, 'on', R.closed);
    setCls(hudEls.lLight, 'on', G.doors.left.light); setCls(hudEls.rLight, 'on', G.doors.right.light);
    setCls(hudEls.lPanel, 'lit', G.doors.left.light); setCls(hudEls.rPanel, 'lit', G.doors.right.light); // (phones: see-through over the lit doorway)
    for (const b of [hudEls.lDoor, hudEls.lLight, hudEls.rDoor, hudEls.rLight, hudEls.camBar, hudEls.pinch]) setCls(b, 'dead', G.powerOut);
    const camsShown = G.cams.t >= 0.98;
    showHud(hudEls.overlay, camsShown);
    showHud(hudEls.lPanel, G.cams.t <= 0.05);
    showHud(hudEls.rPanel, G.cams.t <= 0.05);
    showHud(hudEls.pinch, G.cams.t <= 0.05);
    setCls(hudEls.camBar, 'up', G.cams.up);
    setHtml(hudEls.camLabel, 'camLabel', G.cams.up ? '▼&nbsp;&nbsp;LOWER&nbsp;&nbsp;▼' : '▲&nbsp;&nbsp;CAMERAS&nbsp;&nbsp;▲');
    setCls(hudEls.voice, 'docked', G.cams.t > 0.5); // tuck the voice out of the camera picture
    setCls(hudEls.voice, 'lesson', !!G.lesson);
    setCls($('#clockNote'), 'hidden', !G.lesson || G.cams.t > 0.5); // (the camera's name goes there)
    setCls(Captions.box, 'cams', G.cams.t > 0.5);    // captions make room for the camera map
    setCls(Captions.box, 'voice', G.voice.active);    // … and for the docked voice
    setCls(hudEls.pinch, 'cool', G.pinchCd > 0);
    hudEls.pinchCd.style.width = G.pinchCd > 0 ? (100 * (1 - G.pinchCd / pinchCfg().cooldown)) + '%' : '0';
    const gain = pinchGain();
    setText(hudEls.pinchAmt, 'pinchAmt', '+' + gain);
    setCls(hudEls.pinch, 'big', G.luc < 30); // it pays most when you have sunk deep
    if (camsShown) {
      const cam = camById[G.cams.cur];
      if (cam !== YOU_CAM) slipText(hudEls.camName, 'camName', camTitle(cam), [camTitle(cam, true)]);
      const mins = Math.floor((G.nightT % hourSec()) / hourSec() * 60);
      setText(hudEls.stamp, 'stamp', (G.hour === 0 ? 12 : G.hour) + ':' + String(mins).padStart(2, '0') + ' AM');
      setCls(hudEls.signal, 'hidden', !(G.cams.lost > 0));
    }
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
    lines.push([P(YOU_CAM.map), you, 'ghostLink']); // CAM 7's line to YOU (hidden until it appears)
    for (const [a, b, cls] of lines) {
      const l = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      l.setAttribute('x1', a.x); l.setAttribute('y1', a.y); l.setAttribute('x2', b.x); l.setAttribute('y2', b.y);
      if (cls) l.setAttribute('class', cls);
      svg.appendChild(l);
    }
    const addBtn = (c, label, title, cls) => {
      const b = document.createElement('button');
      b.className = 'camBtn' + (cls ? ' ' + cls : ''); b.dataset.cam = c.id;
      b.textContent = label; b.title = title;
      b.style.left = (6 + c.map.x * 88) + '%'; b.style.top = (6 + c.map.y * 88) + '%';
      b.addEventListener('pointerdown', (e) => { e.stopPropagation(); switchCam(c.id); });
      map.appendChild(b);
      return b;
    };
    CFG.cameras.forEach((c, i) => addBtn(c, c.label || ('CAM ' + (i + 1)), c.name + (i < 9 ? '  [' + (i + 1) + ']' : '')));
    addBtn(YOU_CAM, YOU_CAM.label, YOU_CAM.name, 'ghostCam hidden'); // CAM 7: always built, shown once a night
  }
  /* "CAM 1 — THE NURSERY" (dream: the name it slips into, config dreamName, or the words of its name backwards) */
  function camTitle(cam, dream) {
    const name = dream ? cam.dreamName || cam.name.split(/\s+/).reverse().join(' ') : cam.name;
    return (cam.label || '') + ' — ' + String(name).toUpperCase();
  }
  function updateCamUi() {
    const cam = camById[G.cams.cur];
    setText(hudEls.camName, 'camName', camTitle(cam)); setCls(hudEls.camName, 'slip', false);
    document.querySelectorAll('.camBtn').forEach((b) => b.classList.toggle('sel', b.dataset.cam === cam.id));
  }

  const SCREENS = ['#boot', '#menu', '#nightCard', '#pause', '#settings', '#extras', '#custom', '#dead', '#win', '#wakePrompt', '#credits'];
  function hideScreens() { SCREENS.forEach((s) => hide($(s))); }
  function showScreen(sel) {
    hideScreens(); show($(sel));
    // screens you reach mid-game get keyboard focus, so Enter picks the obvious button
    if (sel === '#pause') { // (#win and #dead focus their first button once their buttons appear: updateWin, updateDead)
      const b = $(sel).querySelector('button:not(.hidden):not([disabled])');
      if (b) b.focus({ preventScroll: true });
    }
  }

  let returnTo = '#menu';
  function goMenu() {
    if (G.paused) Sound.pauseAll(false); // quitting from Pause must not leave the sound switched off
    G.state = 'menu'; G.paused = false; G.later = []; G.finale = null; G.lies = [];
    resetLesson(); G.recap = null;
    resetHud(); Captions.clear(); G.voice.active = false;
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

  /* the night (or falling asleep) holds its breath */
  function pauseGame(p) {
    if (G.state !== 'night' && G.state !== 'asleep') return;
    if (p === G.paused) return;
    G.paused = p;
    Sound.pauseAll(p);
    setCls(Captions.box, 'paused', p);
    if (p) { fillVoiceLog(); $('#pVoice').open = false; showScreen('#pause'); }
    else { hideScreens(); if (G.state === 'asleep' && G.cardShown) show($('#nightCard')); }
  }

  function openSettings(from) {
    returnTo = from;
    $('#sVol').value = save.vol; $('#sMusic').value = save.music;
    document.querySelectorAll('#sFx button').forEach((b) => b.classList.toggle('sel', b.dataset.v === save.fx));
    document.querySelectorAll('#sCap button').forEach((b) => b.classList.toggle('sel', (b.dataset.v === 'on') === save.captions));
    document.querySelectorAll('#sScare button').forEach((b) => b.classList.toggle('sel', b.dataset.v === save.scare));
    $('#sReset').textContent = 'Erase save'; $('#sReset').dataset.confirm = '';
    showScreen('#settings');
  }

  /* Extras: one card per monster, with a little door emblem and NEVER its picture (you meet it in the dream).
     Its name and story show only once you have met it (see meet); until then "???".
     The art helper (?dev) shows the frames here instead, for the artist. */
  const galleryCanvases = [];
  function openExtras() {
    const gal = $('#gallery'); gal.innerHTML = ''; galleryCanvases.length = 0;
    for (const def of CFG.monsters) {
      const met = !!save.met[def.id];
      const item = document.createElement('div'); item.className = 'gItem' + (met ? ' met' : ' locked');
      const cv = makeCanvas(240, 240); item.appendChild(cv);
      const txt = document.createElement('div');
      txt.innerHTML = '<div class="gName"></div><div class="gDesc"></div>';
      txt.querySelector('.gName').textContent = met ? def.name : '???';
      txt.querySelector('.gDesc').textContent = met ? def.description || '' : 'You haven\u2019t met this one yet.';
      item.appendChild(txt); gal.appendChild(item);
      if (DEV) galleryCanvases.push({ cv, def }); // (the art helper animates the frames in it)
      else { cv.className = 'emblem'; drawEmblem(cv, met); }
    }
    const cl = $('#creditList'); cl.innerHTML = '';
    // (a monster you haven't met yet stays a secret in the credits too: its name shows as ???)
    const secret = (s) => { s = String(s || ''); for (const def of CFG.monsters) if (!save.met[def.id] && def.name) s = s.split(def.name).join('???'); return s; };
    for (const c of (CFG.credits || [])) {
      const d = document.createElement('div');
      const b = document.createElement('b'); b.textContent = secret(c.what); d.appendChild(b);
      d.appendChild(document.createTextNode(' — ' + c.who + (c.license ? ' (' + c.license + ')' : '')));
      if (c.url) { d.appendChild(document.createTextNode(' ')); const a = document.createElement('a'); a.href = c.url; a.target = '_blank'; a.rel = 'noopener'; a.textContent = 'source'; d.appendChild(a); }
      cl.appendChild(d);
    }
    showScreen('#extras');
    const pnl = $('#extras .panel'); if (pnl) pnl.scrollTop = 0; // (always open at the top, where the cards are)
  }
  /* a small closed door with a keyhole (once you have met what is behind it, a warm light shows through the keyhole) */
  function drawEmblem(cv, met) {
    const x = cv.getContext('2d'), w = cv.width, h = cv.height, cx = w / 2;
    x.clearRect(0, 0, w, h);
    const dw = w * 0.42, top = h * 0.16, bot = h * 0.86, arch = dw / 2;
    const door = () => { x.beginPath(); x.moveTo(cx - dw / 2, bot); x.lineTo(cx - dw / 2, top + arch); x.arc(cx, top + arch, arch, Math.PI, 0); x.lineTo(cx + dw / 2, bot); x.closePath(); };
    door(); x.fillStyle = '#140c18'; x.fill();
    x.lineWidth = 4; x.strokeStyle = met ? 'rgba(233,223,207,.7)' : 'rgba(167,155,138,.45)'; x.stroke();
    x.lineWidth = 2; x.strokeStyle = 'rgba(167,155,138,.22)'; // two panels
    x.strokeRect(cx - dw * 0.32, top + arch * 0.9, dw * 0.64, (bot - top) * 0.3);
    x.strokeRect(cx - dw * 0.32, top + arch * 0.9 + (bot - top) * 0.36, dw * 0.64, (bot - top) * 0.3);
    const ky = top + (bot - top) * 0.58, kx = cx + dw * 0.26;
    if (met) { const g = x.createRadialGradient(kx, ky, 0, kx, ky, w * 0.16); g.addColorStop(0, 'rgba(255,180,102,.55)'); g.addColorStop(1, 'rgba(255,180,102,0)'); x.fillStyle = g; x.fillRect(0, 0, w, h); }
    x.fillStyle = met ? '#ffb466' : '#05030a';
    x.beginPath(); x.arc(kx, ky - 4, 6, 0, Math.PI * 2); x.moveTo(kx - 3, ky); x.lineTo(kx + 3, ky); x.lineTo(kx + 5, ky + 14); x.lineTo(kx - 5, ky + 14); x.closePath(); x.fill();
    x.strokeStyle = 'rgba(217,194,126,.6)'; x.lineWidth = 2; x.beginPath(); x.arc(kx, ky + 3, 13, 0, Math.PI * 2); x.stroke(); // the brass plate
  }
  function drawGallery() {
    if (!DEV) return;
    for (const { cv, def } of galleryCanvases) {
      const x = cv.getContext('2d'), A = Art.monsters[def.id];
      x.clearRect(0, 0, cv.width, cv.height);
      if (DEV) Dev.gallery(x, A, cv); // (the art helper's onion skin: every frame at once, with its outline)
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
    applyRes();
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
    if (DEV) Dev.move(p);
  });
  document.addEventListener('pointerleave', () => { pointer.inside = false; });
  window.addEventListener('blur', () => { // another window got the focus: let go of everything and pause
    pointer.inside = false; pointer.dragId = null;
    for (const k in keys) keys[k] = false;
    if (G.state === 'night' || G.state === 'asleep') pauseGame(true);
  });

  stage.addEventListener('pointerdown', (e) => {
    if (pointer.dragId != null && e.pointerId !== pointer.dragId) return;
    const p = toStage(e);
    pointer.type = e.pointerType || 'mouse';
    pointer.x = p.x; pointer.y = p.y; pointer.lastX = p.x;
    if (e.target.closest('button, input, label, textarea, a, #devPanel')) return;
    if (skipInput()) return; // falling asleep, waking up, the credits
    if (G.state === 'night' && !G.paused) {
      if (DEV && Dev.down(p, e)) return; // (the art helper: placing a monster, dragging a door box …)
      if (pointer.type !== 'mouse') pointer.dragId = e.pointerId;
    }
  });
  const endDrag = (e) => { if (e.pointerId === pointer.dragId) pointer.dragId = null; if (DEV) Dev.up(toStage(e)); };
  window.addEventListener('pointerup', endDrag);
  window.addEventListener('pointercancel', endDrag);
  stage.addEventListener('wheel', (e) => { if (DEV && Dev.wheel(e)) e.preventDefault(); }, { passive: false });

  const KEY_BTN = { q: hudEls.lDoor, e: hudEls.rDoor, a: hudEls.lLight, d: hudEls.rLight, f: hudEls.pinch, s: hudEls.camBar };
  window.addEventListener('keydown', (e) => {
    if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
    const k = e.key;
    if (k === 'ArrowLeft' || k === 'ArrowRight') { keys[k] = true; e.preventDefault(); }
    const playing = G.state === 'night' && !G.paused;
    const scene = !G.paused && (['asleep', 'waking', 'morning'].indexOf(G.state) >= 0 || !!G.finale); // no buttons on screen
    if ((k === ' ' || k === 'Spacebar') && (playing || scene || G.state === 'boot')) e.preventDefault(); // elsewhere Space presses buttons
    if (scene && k === 'Enter') e.preventDefault();
    if (e.repeat && (k === 'Enter' || k === ' ') && (G.state === 'win' || G.state === 'dead')) e.preventDefault(); // a key held through the slap or the scare presses nothing
    if ((k === 'Enter' || k === ' ') && ((G.state === 'dead' && G.deadWait > 0) || (G.state === 'win' && G.winWait > 0))) { e.preventDefault(); return; } // (no buttons yet)
    if (e.repeat) return;
    if (G.state === 'boot' && (k === 'Enter' || k === ' ')) { bootGo(); return; }
    if (DEV && Dev.key(k)) { e.preventDefault(); return; } // (the art helper's keys: see js/devtools.js)
    if (k === 'Escape' || k === 'p' || k === 'P') {
      // a sub-screen (even one opened from Pause) goes back first; only then does Esc pause/resume
      if (['#settings', '#extras', '#custom'].some((s) => !$(s).classList.contains('hidden'))) backFromSub();
      else if (G.state === 'night' || G.state === 'asleep') pauseGame(!G.paused);
      else skipInput();
      return;
    }
    if (scene && k !== 'Tab' && k.length && !/^(Shift|Control|Alt|Meta|CapsLock|Fn)$/.test(k)) { skipInput(); return; } // any key skips ahead
    if (!playing) return;
    if (k === 'Enter') { e.preventDefault(); voiceAdvance(); return; } // the voice: finish typing, or go on
    const lk = k.toLowerCase();
    if (!G.powerOut) pressFx(KEY_BTN[lk === ' ' || k === 'ArrowUp' || k === 'ArrowDown' ? 's' : lk]); // (the buttons are falling away at Lucidity zero)
    if (lk === 'q') setDoor('left', !G.doors.left.closed);
    else if (lk === 'e') setDoor('right', !G.doors.right.closed);
    else if (lk === 'a') setLight('left', !G.doors.left.light);
    else if (lk === 'd') setLight('right', !G.doors.right.light);
    else if (k === ' ' || lk === 's' || k === 'ArrowUp' || k === 'ArrowDown') toggleCams(k === 'ArrowUp' ? true : k === 'ArrowDown' ? false : null);
    else if (lk === 'f') pinch();
    else if (/^[1-9]$/.test(k)) { const c = CFG.cameras[parseInt(k, 10) - 1]; if (c) { if (!G.cams.up) toggleCams(true); switchCam(c.id); } }
  });
  window.addEventListener('keyup', (e) => { keys[e.key] = false; });

  /* another tab: the night pauses; anywhere else the sound holds its breath until you come back
     (a hidden tab runs no frames, so nothing could fade out or stop by itself) */
  let tabHush = false;
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) { if (tabHush) { tabHush = false; if (!G.paused) Sound.pauseAll(false); } return; }
    if (G.state === 'night' || G.state === 'asleep') { pauseGame(true); return; }
    if (G.state === 'boot' || G.paused) return;
    if (G.state === 'waking' || G.state === 'morning') { slapAlarm(); Sound.cutLoop('wake'); } // no alarm ringing in a hidden tab
    tabHush = true; Sound.pauseAll(true);
  });

  function bind(sel, fn) {
    $(sel).addEventListener('click', (e) => { e.preventDefault(); Sound.play('ui_click', { vol: 0.45 }); fn(e); });
  }
  // HUD buttons respond on pointerdown so they feel instant (and work while the other hand pans)
  function bindHud(sel, fn) { const el = $(sel); el.addEventListener('pointerdown', (e) => { e.preventDefault(); e.stopPropagation(); pressFx(el); fn(); }); }
  bindHud('#btnLDoor', () => setDoor('left', !G.doors.left.closed));
  bindHud('#btnRDoor', () => setDoor('right', !G.doors.right.closed));
  bindHud('#btnLLight', () => setLight('left', !G.doors.left.light));
  bindHud('#btnRLight', () => setLight('right', !G.doors.right.light));
  bindHud('#camBar', () => toggleCams(null));
  bindHud('#pinchBtn', () => pinch());
  bindHud('#voiceSkip', () => { if (G.lesson) endLesson(true); else endVoice(); });
  // a click on the voice box finishes the typing or goes on (it never starts a drag of the room)
  hudEls.voice.addEventListener('pointerdown', (e) => { if (e.target.closest('button')) return; e.stopPropagation(); voiceAdvance(); });
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
  bind('#dRetry', () => startNight(G.night, G.endless, true, { practice: G.practice, lighter: G.lighter })); // the short way to fall asleep
  bind('#dLighter', () => startNight(G.night, false, true, { lighter: true }));
  bind('#xLesson', () => startNight(1, false, false, { practice: true })); // Night 1 with the lesson, progress untouched
  bind('#dMenu', () => goMenu());
  bind('#wNext', () => { if (G.endless || G.practice || G.night >= NIGHTS) goMenu(); else startNight(G.night + 1, false); });
  bind('#wMenu', () => goMenu());
  bind('#sFull', () => {
    const d = document, el = d.documentElement;
    if (d.fullscreenElement || d.webkitFullscreenElement) (d.exitFullscreen || d.webkitExitFullscreen).call(d);
    else if (el.requestFullscreen || el.webkitRequestFullscreen) (el.requestFullscreen || el.webkitRequestFullscreen).call(el);
  });
  bind('#sReset', () => {
    const b = $('#sReset');
    if (!b.dataset.confirm) { b.dataset.confirm = '1'; b.textContent = `Really erase? ${TAP === 'tap' ? 'Tap' : 'Click'} again`; return; }
    save.night = 1; save.beaten = 0; save.custom = {}; save.tutorialDone = false; save.deaths = {}; save.hints = {}; save.met = {}; writeSave();
    b.textContent = 'Save erased'; b.dataset.confirm = '';
  });
  $('#sVol').addEventListener('input', (e) => { save.vol = parseInt(e.target.value, 10); Sound.applyVolumes(); writeSave(); });
  $('#sMusic').addEventListener('input', (e) => { save.music = parseInt(e.target.value, 10); Sound.applyVolumes(); writeSave(); });
  document.querySelectorAll('#sFx button').forEach((b) => b.addEventListener('click', () => {
    save.fx = b.dataset.v; writeSave(); applyFxSetting(); applyRes();
    document.querySelectorAll('#sFx button').forEach((x) => x.classList.toggle('sel', x === b));
  }));
  document.querySelectorAll('#sCap button').forEach((b) => b.addEventListener('click', () => {
    save.captions = b.dataset.v === 'on'; writeSave();
    if (!save.captions) Captions.clear();
    document.querySelectorAll('#sCap button').forEach((x) => x.classList.toggle('sel', x === b));
  }));
  document.querySelectorAll('#sScare button').forEach((b) => b.addEventListener('click', () => {
    save.scare = b.dataset.v === 'gentle' ? 'gentle' : 'normal'; writeSave();
    document.querySelectorAll('#sScare button').forEach((x) => x.classList.toggle('sel', x === b));
  }));

  function backFromSub() {
    if (returnTo === '#pause' && G.paused) { showScreen('#pause'); returnTo = '#menu'; return; } // (paused at night or while falling asleep)
    returnTo = '#menu';
    refreshMenu(); showScreen('#menu');
  }

  /* ------------------------------------------------------------------ */
  /*  ART HELPER (open index.html?dev): js/devtools.js is loaded only    */
  /*  then, and fills in these hooks. Players never load it.             */
  /* ------------------------------------------------------------------ */
  const Dev = {
    inDoorway() {}, doorFrame() {}, camGhost() {}, overlay() {}, gallery() {}, booted() {}, error() {},
    key: () => false, down: () => false, move() {}, up() {}, wheel: () => false,
  };
  function loadDevtools() {
    const s = document.createElement('script');
    s.src = 'js/devtools.js';
    s.onerror = () => console.warn('[dev] js/devtools.js is missing, so the art helper is off.');
    document.head.appendChild(s);
  }

  /* ------------------------------------------------------------------ */
  /*  BOOT + LOOP                                                       */
  /* ------------------------------------------------------------------ */
  let last = performance.now();
  let loggedError = false;
  function frame(now) {
    requestAnimationFrame(frame);           // keep going even if one frame fails
    const raw = (now - last) / 1000, dt = clamp(raw, 0, 0.05);
    last = now;
    try {
      watchRes(raw);
      update(dt);
      if (G.ready || G.state !== 'boot') render();
      if (!$('#extras').classList.contains('hidden')) drawGallery();
    } catch (err) {
      if (!loggedError) { loggedError = true; console.error(err); }
      if (DEV) Dev.error(err); // (the art helper counts them and shows the latest)
    }
  }

  function bootGo() {
    if (G.state !== 'boot' || !G.ready) return;
    Sound.unlock();
    goMenu();
  }

  async function boot() {
    const bootT0 = performance.now();
    if (DEV) loadDevtools();
    loadSave();
    layout();
    $('#bootTitle').textContent = CFG.title || 'UNTIL THE ALARM';
    Sound.init();
    initMotes();
    validateBrains();
    let done = 0, total = 1;
    const tick = () => { done++; $('#loadFill').style.width = Math.min(100, (done / total) * 100) + '%'; };
    // fonts first so the stand-in art can use them
    const fontLoads = ['48px "Fell SC"', '20px "Fell"', '20px VT323', '20px "Special Elite"', '20px Eater'].map((f) => document.fonts ? document.fonts.load(f).catch(() => {}) : Promise.resolve());
    await Promise.race([Promise.all(fontLoads), new Promise((r) => setTimeout(r, 3000))]);
    const soundP = Sound.load(tick), artP = loadArt(tick, 0, { lazy: true, backdrop: bootBackdrop });
    total = Sound.total + Art.total; // (both count their files straight away)
    await Art.bootP;
    $('#bootMsg').textContent = 'listening for the dream…';
    await Promise.race([soundP, new Promise((r) => setTimeout(r, 9000))]);
    // the desk room, doorways and cameras load now, behind the title screen (a night waits for them with your eyes
    // shut). On a quick connection they are in before the button shows; the art helper always waits for them.
    Art.startRest();
    const quick = performance.now() - bootT0 < 2500; // (a quick connection: the rooms are in a moment later, so wait for them)
    await Promise.race([artP.catch(() => {}), new Promise((r) => setTimeout(r, DEV ? 60000 : quick ? 900 : 0))]);
    $('#loadFill').style.width = '100%';
    buildCamMap(); updateCamUi();
    G.ready = true;
    window.__oopsReady = true; // (from now on a problem is the game's to report, not the "Oops" screen's)
    $('#bootMsg').textContent = bootNote();
    // an iPhone has no fullscreen for pages (only "Add to Home Screen"): no button that does nothing
    if (!(document.fullscreenEnabled || document.webkitFullscreenEnabled)) hide($('#sFull'));
    $('#bootGo').textContent = TAP + ' to fall asleep';
    show($('#bootGo'));
    $('#boot').addEventListener('click', bootGo);
    if (DEV) Dev.booted();
  }
  /* the boot screen: the title screen's hall, dark and soft, fades in behind the title as soon as its photo is here */
  function bootBackdrop(img) {
    const el = $('#boot'); if (!el || el.querySelector('.bootBack')) return;
    const cv = makeCanvas(W / 2, H / 2), x = cv.getContext('2d');
    const sm = makeCanvas(W / 8, H / 8); sm.getContext('2d').drawImage(img, 0, 0, sm.width, sm.height); // (shrunk and grown again: a soft blur anywhere)
    x.drawImage(img, 0, 0, cv.width, cv.height);
    x.globalAlpha = 0.65; x.drawImage(sm, 0, 0, cv.width, cv.height); x.globalAlpha = 1;
    x.fillStyle = 'rgba(7,5,12,.58)'; x.fillRect(0, 0, cv.width, cv.height);
    const g = x.createRadialGradient(cv.width / 2, cv.height * 0.4, cv.height * 0.1, cv.width / 2, cv.height * 0.45, cv.width * 0.6);
    g.addColorStop(0, 'rgba(27,16,48,.15)'); g.addColorStop(1, 'rgba(7,5,12,.75)');
    x.fillStyle = g; x.fillRect(0, 0, cv.width, cv.height);
    cv.className = 'bootBack'; el.insertBefore(cv, el.firstChild);
    requestAnimationFrame(() => requestAnimationFrame(() => cv.classList.add('on')));
  }
  /* sound slots the game copes without (each one has a stand-in sound) */
  const OPTIONAL_SOUNDS = ['clock_tick', 'type_key', 'reality_snap', 'redhorn_click', 'door_strain', 'hypnic_jolt', 'water_drip'];
  /* an iPhone or iPad whose browser can't play past the silent switch (older than Safari 16.4) */
  const IOS_SILENT = (/iP(hone|ad|od)/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)) && !navigator.audioSession;
  /* the boot screen's small print */
  function bootNote() {
    const note = artNote();
    return IOS_SILENT ? 'no sound? flip the silent switch off' + (note ? ' · ' + note : '') : note;
  }
  /* what is missing or misspelt (with ?dev in full; otherwise one hint, for the artist) */
  function artNote() {
    const miss = Array.from(Sound.missing), must = miss.filter((n) => OPTIONAL_SOUNDS.indexOf(n) < 0);
    const frames = Art.files.filter((f) => /frame/.test(f.slot) && !f.opt && f.path && !f.w).length;
    if (!DEV) return must.length || configWarnings.length || frames ? 'something needs a look: add ?dev to the address to see what' : '';
    const parts = [];
    if (must.length) parts.push('missing sounds: ' + must.join(', '));
    if (miss.length > must.length) parts.push((miss.length - must.length) + ' optional sound(s) not added yet');
    if (frames) parts.push(frames + ' monster frame(s) missing');
    if (configWarnings.length) parts.push(configWarnings.length + ' config.js warning(s): see the art helper box (H)');
    return parts.length ? '(' + parts.join(' · ') + ')' : '';
  }

  /* for testers and bots: drive the game from the browser console */
  window.__game = {
    G, Sound, Art, CFG, startNight, beginNight, goMenu, pauseGame, monsterMove, jumpscare, powerOutStart,
    startWaking, enterMorning, slapAlarm, skipInput, skipIntro, showWinPanel, endFinale, clockTick, clockPan, officeSpot,
    lidOpen, wakeLids, fallAsleepLine, paintBedroom, drawAlarmClock, evidenceCfg,
    setDoor, setLight, toggleCams, switchCam, pinch, enterOffice, layout,
    after, cue, hit, rule, fxMul, doorDist, doorSide, calm, arrive, stepToward, spawnParts,
    noise, pinchGain, pinchCfg, strainCfg, bangDoor, pulseCls,
    Captions, spawnLie, canLie, liesCfg, minWarning, writeSave, save,
    tinted, ghostOf, drawEyelids, numify, configWarnings, render,
    Director, DREAM_EVENTS, directorUpdate, startEvent, endEvent, safe, tension, startFalseDawn, startYouCam, endYouCam,
    startPreScare, splitTints, drawJumpscare, updateRoom, startWindowPass, nightMin,
    startVoice, endVoice, voiceAdvance, compileBeat, voiceLog, fillVoiceLog, VOICE,
    startLesson, endLesson, lessonStep, lessonSteps, lessonMet, coachTarget, coach, LESSON, LESSON_T,
    die, caughtRecap, lucidityRecap, finishRecap, fmtClock, storyLine, logStory, TIPS, LIGHTER,
    // the dreaming HUD, monster brains, the art helper (js/devtools.js) and the office fitting
    dreamy, SLIP, eyeLid, hourLands, BRAINS, brainOf, walkerMove, walkerHear, validateBrains, doorsOf, approachAnchors, SHY, SLEEPER,
    Dev, loadArt, fitOffice, inBand, officeDoor, officeWidthFor, OFFICE_MIN_W, paintOffice, paintDoorway, paintShutter, shadowFigure,
    sharp, applyRes, wantRes, SCENES, SCENE_DIR, SCENE_SEAT, fitDoor, photoOffice, menuArt, menuPar, menuLamp, paintKidDrawing, shadedDrawing, KID_CAPTION, meet, drawEmblem, PIN_SPOT,
    officeOriginX, doorBox, camFeedBox, spriteRect, drawSprite, doorPoseOf, camById, YOU_CAM, OPTIONAL_SOUNDS, escapeHtml, hourSec, setText,
    loadSave, bootNote, updateHud, updateCamUi, camTitle,
  };
  requestAnimationFrame((t) => { last = t; requestAnimationFrame(frame); });
  boot().catch((e) => { console.error(e); if (window.__oops) window.__oops({ msg: 'Something in <b>js/config.js</b> isn\'t the way the game expects, so it couldn\'t start.', hint: 'shape', tech: String(e && e.message || e) }); });
})();
