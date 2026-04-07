// ── BONDSCRAPE SOUND ENGINE ──────────────────────────
// Web Audio API sound effects for UI interactions
// Usage: BondSound.click(), BondSound.hover(), etc.

window.BondSound = (function() {
  let ctx = null;
  let muted = false;
  let masterGain = null;

  function getCtx() {
    if (!ctx) {
      ctx = new (window.AudioContext || window.webkitAudioContext)();
      masterGain = ctx.createGain();
      masterGain.gain.value = 0.35;
      masterGain.connect(ctx.destination);
    }
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  }

  function out() { getCtx(); return masterGain; }

  function mute(v) { muted = v; if (masterGain) masterGain.gain.value = v ? 0 : 0.35; }
  function isMuted() { return muted; }

  // ── INDIVIDUAL SOUNDS ──────────────────────

  // Short crisp click for buttons
  function click() {
    const c = getCtx(), t = c.currentTime;
    const osc = c.createOscillator();
    const g = c.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(800, t);
    osc.frequency.exponentialRampToValueAtTime(400, t + 0.06);
    g.gain.setValueAtTime(0.3, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.06);
    osc.connect(g).connect(out());
    osc.start(t); osc.stop(t + 0.06);
  }

  // Soft hover tone
  function hover() {
    const c = getCtx(), t = c.currentTime;
    const osc = c.createOscillator();
    const g = c.createGain();
    osc.type = 'sine';
    osc.frequency.value = 1200;
    g.gain.setValueAtTime(0.06, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.08);
    osc.connect(g).connect(out());
    osc.start(t); osc.stop(t + 0.08);
  }

  // Section scroll reveal — gentle rising tone
  function reveal() {
    const c = getCtx(), t = c.currentTime;
    const osc = c.createOscillator();
    const g = c.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(300, t);
    osc.frequency.exponentialRampToValueAtTime(600, t + 0.25);
    g.gain.setValueAtTime(0.08, t);
    g.gain.linearRampToValueAtTime(0.04, t + 0.1);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.3);
    osc.connect(g).connect(out());
    osc.start(t); osc.stop(t + 0.3);
  }

  // Counter tick
  function tick() {
    const c = getCtx(), t = c.currentTime;
    const osc = c.createOscillator();
    const g = c.createGain();
    osc.type = 'square';
    osc.frequency.value = 2400 + Math.random() * 400;
    g.gain.setValueAtTime(0.04, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.02);
    osc.connect(g).connect(out());
    osc.start(t); osc.stop(t + 0.02);
  }

  // Success ding — pleasant two-note ascending
  function success() {
    const c = getCtx(), t = c.currentTime;
    [523, 784].forEach((freq, i) => {
      const osc = c.createOscillator();
      const g = c.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      const start = t + i * 0.12;
      g.gain.setValueAtTime(0.15, start);
      g.gain.exponentialRampToValueAtTime(0.001, start + 0.35);
      osc.connect(g).connect(out());
      osc.start(start); osc.stop(start + 0.35);
    });
  }

  // Error — descending buzz
  function error() {
    const c = getCtx(), t = c.currentTime;
    const osc = c.createOscillator();
    const g = c.createGain();
    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(300, t);
    osc.frequency.exponentialRampToValueAtTime(100, t + 0.2);
    g.gain.setValueAtTime(0.12, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.25);
    const lp = c.createBiquadFilter();
    lp.type = 'lowpass'; lp.frequency.value = 800;
    osc.connect(lp).connect(g).connect(out());
    osc.start(t); osc.stop(t + 0.25);
  }

  // Navigation / tab switch
  function nav() {
    const c = getCtx(), t = c.currentTime;
    const osc = c.createOscillator();
    const g = c.createGain();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(600, t);
    osc.frequency.exponentialRampToValueAtTime(900, t + 0.05);
    g.gain.setValueAtTime(0.12, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.08);
    osc.connect(g).connect(out());
    osc.start(t); osc.stop(t + 0.08);
  }

  // Agent blip — electronic chirp
  function blip() {
    const c = getCtx(), t = c.currentTime;
    const osc = c.createOscillator();
    const g = c.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(1800, t);
    osc.frequency.exponentialRampToValueAtTime(600, t + 0.08);
    g.gain.setValueAtTime(0.15, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.1);
    osc.connect(g).connect(out());
    osc.start(t); osc.stop(t + 0.1);
  }

  // Console log line — subtle terminal keystroke
  function terminal() {
    const c = getCtx(), t = c.currentTime;
    const bufSize = c.sampleRate * 0.015;
    const buf = c.createBuffer(1, bufSize, c.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < bufSize; i++) data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i/bufSize, 3);
    const src = c.createBufferSource();
    src.buffer = buf;
    const g = c.createGain();
    g.gain.value = 0.06;
    const hp = c.createBiquadFilter();
    hp.type = 'highpass'; hp.frequency.value = 4000;
    src.connect(hp).connect(g).connect(out());
    src.start(t);
  }

  // Expand / collapse — whoosh
  function toggle() {
    const c = getCtx(), t = c.currentTime;
    const osc = c.createOscillator();
    const g = c.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(400, t);
    osc.frequency.exponentialRampToValueAtTime(200, t + 0.12);
    g.gain.setValueAtTime(0.08, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.15);
    osc.connect(g).connect(out());
    osc.start(t); osc.stop(t + 0.15);
  }

  // Pipeline step transition — glassy sweep
  function stepChange() {
    const c = getCtx(), t = c.currentTime;
    const osc = c.createOscillator();
    const osc2 = c.createOscillator();
    const g = c.createGain();
    osc.type = 'sine'; osc.frequency.value = 440;
    osc2.type = 'sine'; osc2.frequency.value = 554;
    g.gain.setValueAtTime(0.1, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.2);
    osc.connect(g).connect(out());
    osc2.connect(g);
    osc.start(t); osc.stop(t + 0.2);
    osc2.start(t); osc2.stop(t + 0.2);
  }

  // Consensus stamp — big impactful tone
  function stamp() {
    const c = getCtx(), t = c.currentTime;
    // Low thud
    const osc = c.createOscillator();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(120, t);
    osc.frequency.exponentialRampToValueAtTime(50, t + 0.3);
    const g = c.createGain();
    g.gain.setValueAtTime(0.25, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.4);
    osc.connect(g).connect(out());
    osc.start(t); osc.stop(t + 0.4);
    // High ring
    const ring = c.createOscillator();
    ring.type = 'sine'; ring.frequency.value = 800;
    const rg = c.createGain();
    rg.gain.setValueAtTime(0.1, t);
    rg.gain.exponentialRampToValueAtTime(0.001, t + 0.5);
    ring.connect(rg).connect(out());
    ring.start(t); ring.stop(t + 0.5);
  }

  // Scraper running ambient pulse — call repeatedly
  function pulse() {
    const c = getCtx(), t = c.currentTime;
    const osc = c.createOscillator();
    const g = c.createGain();
    osc.type = 'sine';
    osc.frequency.value = 200 + Math.random() * 50;
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(0.04, t + 0.1);
    g.gain.linearRampToValueAtTime(0, t + 0.4);
    osc.connect(g).connect(out());
    osc.start(t); osc.stop(t + 0.4);
  }

  // Validation check pass
  function checkPass() {
    const c = getCtx(), t = c.currentTime;
    const osc = c.createOscillator();
    const g = c.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, t);
    osc.frequency.setValueAtTime(1100, t + 0.05);
    g.gain.setValueAtTime(0.1, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.12);
    osc.connect(g).connect(out());
    osc.start(t); osc.stop(t + 0.12);
  }

  // Drop zone hover
  function dropHover() {
    const c = getCtx(), t = c.currentTime;
    const osc = c.createOscillator();
    const g = c.createGain();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(300, t);
    osc.frequency.linearRampToValueAtTime(500, t + 0.3);
    g.gain.setValueAtTime(0.06, t);
    g.gain.linearRampToValueAtTime(0.08, t + 0.15);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.35);
    osc.connect(g).connect(out());
    osc.start(t); osc.stop(t + 0.35);
  }

  return {
    click, hover, reveal, tick, success, error, nav, blip,
    terminal, toggle, stepChange, stamp, pulse, checkPass,
    dropHover, mute, isMuted
  };
})();

// ── AUTO-WIRE: CLICK SOUND ON ANY INTERACTIVE ELEMENT ──────
document.addEventListener('DOMContentLoaded', () => {
  document.addEventListener('click', (e) => {
    const el = e.target.closest('a, button, [onclick], .deal-card, .firm-card, .fp-card, .source-card, .pip-progress-step, .progress-step, .mode-option, .select-pill, .tag-option, .firms-tag-option, .scraped-filter-btn');
    if (el) BondSound.click();
  });
});
