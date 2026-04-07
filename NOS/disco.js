// ── DISCO MODE ──────────────────────────
// Adds a "DISCO MODE" button to the topbar. When activated:
// - Disco ball canvas overlay with rotating light beams
// - Color-cycling background on all elements
// - Disco music via Web Audio API
// - Click again to deactivate

(function() {
  let discoActive = false;
  let discoCanvas = null;
  let discoCtx = null;
  let discoRaf = null;
  let discoAudioCtx = null;
  let discoGain = null;
  let discoStyleEl = null;
  let discoNodes = []; // audio nodes to stop

  // ── INJECT BUTTON INTO TOPBAR ──────────
  function injectButton() {
    const spacer = document.querySelector('.topbar-spacer');
    if (!spacer) return;
    const btn = document.createElement('button');
    btn.id = 'disco-btn';
    btn.textContent = 'DISCO MODE';
    btn.style.cssText = `
      font-family:var(--mono,monospace); font-size:9px; font-weight:700;
      padding:4px 12px; border-radius:3px; cursor:pointer;
      letter-spacing:0.08em; text-transform:uppercase;
      border:1px solid #a855f7; color:#a855f7;
      background:rgba(168,85,247,0.08);
      transition:all 0.2s; margin-left:8px;
    `;
    btn.addEventListener('mouseenter', () => {
      if (!discoActive) { btn.style.background = 'rgba(168,85,247,0.15)'; btn.style.borderColor = '#c084fc'; }
    });
    btn.addEventListener('mouseleave', () => {
      if (!discoActive) { btn.style.background = 'rgba(168,85,247,0.08)'; btn.style.borderColor = '#a855f7'; }
    });
    btn.addEventListener('click', toggleDisco);
    spacer.insertAdjacentElement('afterend', btn);
  }

  // ── TOGGLE ──────────
  function toggleDisco() {
    discoActive = !discoActive;
    const btn = document.getElementById('disco-btn');
    if (discoActive) {
      btn.style.background = '#a855f7';
      btn.style.color = '#fff';
      btn.textContent = 'EXIT DISCO';
      startDisco();
    } else {
      btn.style.background = 'rgba(168,85,247,0.08)';
      btn.style.color = '#a855f7';
      btn.textContent = 'DISCO MODE';
      stopDisco();
    }
  }

  // ── START DISCO ──────────
  function startDisco() {
    // Canvas overlay for disco ball lights
    discoCanvas = document.createElement('canvas');
    discoCanvas.id = 'disco-canvas';
    discoCanvas.style.cssText = 'position:fixed;inset:0;z-index:9998;pointer-events:none;opacity:0;transition:opacity 0.5s;';
    document.body.appendChild(discoCanvas);
    requestAnimationFrame(() => { discoCanvas.style.opacity = '1'; });

    const dpr = window.devicePixelRatio || 1;
    const W = window.innerWidth, H = window.innerHeight;
    discoCanvas.width = W * dpr;
    discoCanvas.height = H * dpr;
    discoCanvas.style.width = W + 'px';
    discoCanvas.style.height = H + 'px';
    discoCtx = discoCanvas.getContext('2d');
    discoCtx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // Inject CSS animations
    discoStyleEl = document.createElement('style');
    discoStyleEl.textContent = `
      @keyframes discoHue {
        0% { filter:hue-rotate(0deg) saturate(1.5) brightness(1.1); }
        25% { filter:hue-rotate(90deg) saturate(1.8) brightness(1.2); }
        50% { filter:hue-rotate(180deg) saturate(1.5) brightness(1.1); }
        75% { filter:hue-rotate(270deg) saturate(1.8) brightness(1.2); }
        100% { filter:hue-rotate(360deg) saturate(1.5) brightness(1.1); }
      }
      @keyframes discoPulse {
        0%,100% { box-shadow:0 0 20px 5px rgba(168,85,247,0.3), 0 0 60px 10px rgba(236,72,153,0.15); }
        25% { box-shadow:0 0 20px 5px rgba(59,130,246,0.3), 0 0 60px 10px rgba(16,185,129,0.15); }
        50% { box-shadow:0 0 20px 5px rgba(245,158,11,0.3), 0 0 60px 10px rgba(239,68,68,0.15); }
        75% { box-shadow:0 0 20px 5px rgba(16,185,129,0.3), 0 0 60px 10px rgba(59,130,246,0.15); }
      }
      body.disco-mode { animation:discoHue 4s linear infinite; }
      body.disco-mode .topbar { animation:discoPulse 2s ease infinite; }
      body.disco-mode * { transition:none !important; }
    `;
    document.head.appendChild(discoStyleEl);
    document.body.classList.add('disco-mode');

    // Start light beams animation
    const beams = [];
    const COLORS = [
      'rgba(168,85,247,', 'rgba(236,72,153,', 'rgba(59,130,246,',
      'rgba(16,185,129,', 'rgba(245,158,11,', 'rgba(239,68,68,',
      'rgba(234,179,8,', 'rgba(14,165,233,',
    ];
    for (let i = 0; i < 14; i++) {
      beams.push({
        angle: Math.random() * Math.PI * 2,
        speed: 0.005 + Math.random() * 0.015,
        width: 0.04 + Math.random() * 0.08,
        color: COLORS[Math.floor(Math.random() * COLORS.length)],
        length: 0.6 + Math.random() * 0.5,
        osc: Math.random() * Math.PI * 2,
        oscSpeed: 0.01 + Math.random() * 0.02,
      });
    }

    // Disco ball dots
    const dots = [];
    for (let i = 0; i < 40; i++) {
      dots.push({
        x: Math.random() * W,
        y: Math.random() * H,
        r: 3 + Math.random() * 8,
        color: COLORS[Math.floor(Math.random() * COLORS.length)],
        speed: 0.3 + Math.random() * 1.5,
        angle: Math.random() * Math.PI * 2,
        pulse: Math.random() * Math.PI * 2,
      });
    }

    let t = 0;
    function drawDisco() {
      if (!discoActive) return;
      t += 0.016;
      const ctx = discoCtx;
      const cW = W, cH = H;
      ctx.clearRect(0, 0, cW, cH);

      // Disco ball center point
      const ballX = cW / 2;
      const ballY = cH * 0.12;

      // Draw light beams from ball
      for (const beam of beams) {
        beam.angle += beam.speed;
        beam.osc += beam.oscSpeed;
        const a = beam.angle + Math.sin(beam.osc) * 0.3;
        const len = Math.max(cW, cH) * beam.length;

        ctx.save();
        ctx.translate(ballX, ballY);
        ctx.rotate(a);
        const grad = ctx.createLinearGradient(0, 0, len, 0);
        grad.addColorStop(0, beam.color + '0.25)');
        grad.addColorStop(0.5, beam.color + '0.08)');
        grad.addColorStop(1, beam.color + '0)');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(len, -len * beam.width);
        ctx.lineTo(len, len * beam.width);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
      }

      // Disco ball
      ctx.save();
      const ballR = 18;
      const ballGrad = ctx.createRadialGradient(ballX - 4, ballY - 4, 2, ballX, ballY, ballR);
      ballGrad.addColorStop(0, '#ffffff');
      ballGrad.addColorStop(0.3, '#d4d4d8');
      ballGrad.addColorStop(1, '#71717a');
      ctx.fillStyle = ballGrad;
      ctx.beginPath();
      ctx.arc(ballX, ballY, ballR, 0, Math.PI * 2);
      ctx.fill();
      // Mirror facets
      for (let i = 0; i < 12; i++) {
        const fa = (Math.PI * 2 / 12) * i + t * 0.5;
        const fx = ballX + Math.cos(fa) * ballR * 0.65;
        const fy = ballY + Math.sin(fa) * ballR * 0.65;
        ctx.fillStyle = `rgba(255,255,255,${0.4 + Math.sin(t * 3 + i) * 0.3})`;
        ctx.fillRect(fx - 2, fy - 2, 4, 4);
      }
      ctx.restore();

      // Floating light dots
      for (const dot of dots) {
        dot.pulse += 0.05;
        dot.x += Math.cos(dot.angle) * dot.speed;
        dot.y += Math.sin(dot.angle) * dot.speed;
        dot.angle += (Math.random() - 0.5) * 0.1;
        // Wrap
        if (dot.x < -20) dot.x = cW + 20;
        if (dot.x > cW + 20) dot.x = -20;
        if (dot.y < -20) dot.y = cH + 20;
        if (dot.y > cH + 20) dot.y = -20;

        const alpha = 0.3 + Math.sin(dot.pulse) * 0.25;
        ctx.fillStyle = dot.color + alpha + ')';
        ctx.beginPath();
        ctx.arc(dot.x, dot.y, dot.r, 0, Math.PI * 2);
        ctx.fill();
        // Glow
        ctx.fillStyle = dot.color + (alpha * 0.3) + ')';
        ctx.beginPath();
        ctx.arc(dot.x, dot.y, dot.r * 3, 0, Math.PI * 2);
        ctx.fill();
      }

      discoRaf = requestAnimationFrame(drawDisco);
    }
    drawDisco();

    // Start disco music
    startDiscoMusic();
  }

  // ── STOP DISCO ──────────
  function stopDisco() {
    document.body.classList.remove('disco-mode');
    if (discoStyleEl) { discoStyleEl.remove(); discoStyleEl = null; }
    if (discoCanvas) {
      discoCanvas.style.opacity = '0';
      setTimeout(() => { discoCanvas.remove(); discoCanvas = null; }, 500);
    }
    if (discoRaf) { cancelAnimationFrame(discoRaf); discoRaf = null; }
    // Stop music
    if (discoLoopTimer) { clearTimeout(discoLoopTimer); discoLoopTimer = null; }
    if (discoGain) {
      discoGain.gain.linearRampToValueAtTime(0, discoAudioCtx.currentTime + 0.5);
      setTimeout(() => {
        discoNodes.forEach(n => { try { n.stop(); } catch(e) {} });
        discoNodes = [];
      }, 600);
    }
  }

  // ── DISCO MUSIC — 70s Funk/Disco (looping) ──────────
  // 104 BPM, Fm groove, octave-pumping bass, wah guitar, falsetto synth
  let discoLoopTimer = null;

  function startDiscoMusic() {
    discoAudioCtx = discoAudioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const c = discoAudioCtx;
    c.resume();
    discoGain = c.createGain();
    discoGain.gain.value = 0.22;
    discoGain.connect(c.destination);
    discoNodes = [];
    scheduleDiscoLoop();
  }

  function scheduleDiscoLoop() {
    if (!discoActive) return;
    const c = discoAudioCtx;
    const t = c.currentTime + 0.05; // small lookahead

    const bpm = 104;
    const beat = 60 / bpm;
    const sixteenth = beat / 4;
    const bars = 16; // shorter loop = re-schedule more often
    const totalBeats = bars * 4;

    // ── KICK: four-on-the-floor with punch ──
    for (let i = 0; i < totalBeats; i++) {
      const s = t + i * beat;
      const kick = c.createOscillator();
      kick.type = 'sine';
      kick.frequency.setValueAtTime(160, s);
      kick.frequency.exponentialRampToValueAtTime(35, s + 0.18);
      const kg = c.createGain();
      kg.gain.setValueAtTime(0.45, s);
      kg.gain.exponentialRampToValueAtTime(0.001, s + 0.22);
      // Click transient
      const click = c.createOscillator();
      click.type = 'square'; click.frequency.value = 1200;
      const cg = c.createGain();
      cg.gain.setValueAtTime(0.08, s);
      cg.gain.exponentialRampToValueAtTime(0.001, s + 0.01);
      kick.connect(kg).connect(discoGain);
      click.connect(cg).connect(discoGain);
      kick.start(s); kick.stop(s + 0.25);
      click.start(s); click.stop(s + 0.015);
      discoNodes.push(kick, click);
    }

    // ── HI-HAT: 16ths with accented off-beats ──
    for (let i = 0; i < totalBeats * 4; i++) {
      const s = t + i * sixteenth;
      const dur = 0.03;
      const buf = c.createBuffer(1, c.sampleRate * dur, c.sampleRate);
      const d = buf.getChannelData(0);
      for (let j = 0; j < d.length; j++) d[j] = (Math.random() * 2 - 1) * Math.pow(1 - j/d.length, 8);
      const src = c.createBufferSource(); src.buffer = buf;
      // Accent pattern: louder on off-8ths
      const accent = (i % 4 === 2) ? 0.14 : (i % 2 === 0) ? 0.04 : 0.08;
      const hg = c.createGain(); hg.gain.value = accent;
      const hp = c.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 9000;
      src.connect(hp).connect(hg).connect(discoGain);
      src.start(s);
      discoNodes.push(src);
    }

    // ── BASS: Octave-pumping funk pattern in Fm ──
    // Classic disco bass: low note → octave up, syncopated
    // Fm: F2=87.31, Ab2=103.83, Bb2=116.54, C3=130.81, Eb3=155.56
    const bassSeq = [
      // Bar pattern (in 16ths): root, -, oct, -, root, oct, -, root
      // Each entry: [freq, 16th position within 2-bar phrase]
      // 2 bars of Fm
      [87.31,0],[174.61,2],[87.31,4],[174.61,5],[87.31,7],
      [87.31,8],[174.61,10],[87.31,12],[174.61,13],[130.81,15],
      // 2 bars of Db
      [69.30,16],[138.59,18],[69.30,20],[138.59,21],[69.30,23],
      [69.30,24],[138.59,26],[69.30,28],[138.59,29],[116.54,31],
    ];
    for (let loop = 0; loop < bars / 4; loop++) {
      bassSeq.forEach(([freq, pos]) => {
        const s = t + (loop * 32 + pos) * sixteenth;
        const osc = c.createOscillator();
        osc.type = 'sawtooth';
        osc.frequency.value = freq;
        const bg = c.createGain();
        bg.gain.setValueAtTime(0.2, s);
        bg.gain.exponentialRampToValueAtTime(0.01, s + sixteenth * 1.5);
        const lp = c.createBiquadFilter();
        lp.type = 'lowpass';
        // Envelope the filter for that funky "bwow" sound
        lp.frequency.setValueAtTime(800, s);
        lp.frequency.exponentialRampToValueAtTime(200, s + sixteenth * 1.5);
        lp.Q.value = 4;
        osc.connect(lp).connect(bg).connect(discoGain);
        osc.start(s); osc.stop(s + sixteenth * 2);
        discoNodes.push(osc);
      });
    }

    // ── WAH GUITAR: Choppy chords with sweeping filter ──
    const wahChords = [
      { notes: [349.23, 415.30, 523.25], beats: 8 },  // Fm
      { notes: [277.18, 349.23, 415.30], beats: 8 },  // Db
    ];
    // Rhythm: 16th note chops, muted on some beats
    const wahPattern = [1,0,1,1, 0,1,0,1, 1,0,1,1, 0,1,1,0]; // 1=play, 0=mute
    for (let loop = 0; loop < bars / 4; loop++) {
      wahChords.forEach((ch, ci) => {
        for (let beat16 = 0; beat16 < 16; beat16++) {
          if (!wahPattern[beat16]) continue;
          const s = t + (loop * 32 + ci * 16 + beat16) * sixteenth;
          ch.notes.forEach(freq => {
            const osc = c.createOscillator();
            osc.type = 'sawtooth';
            osc.frequency.value = freq;
            const g = c.createGain();
            g.gain.setValueAtTime(0.035, s);
            g.gain.exponentialRampToValueAtTime(0.001, s + sixteenth * 0.8);
            // Wah filter — sweeps up and down with the 16th pattern
            const wah = c.createBiquadFilter();
            wah.type = 'bandpass';
            wah.Q.value = 6;
            const wahFreq = 600 + Math.sin((loop * 32 + ci * 16 + beat16) * 0.4) * 400;
            wah.frequency.setValueAtTime(wahFreq, s);
            wah.frequency.setValueAtTime(wahFreq * 0.5, s + sixteenth * 0.7);
            osc.connect(wah).connect(g).connect(discoGain);
            osc.start(s); osc.stop(s + sixteenth);
            discoNodes.push(osc);
          });
        }
      });
    }

    // ── FALSETTO SYNTH: High register melody line ──
    // Pentatonic Fm riffs in the falsetto range
    const melodyNotes = [
      // Phrase 1 (2 bars)
      [698.46,0,3],[0,3,1],[784.00,4,2],[698.46,6,2],
      [523.25,8,2],[0,10,2],[622.25,12,3],[523.25,15,1],
      // Phrase 2 (2 bars)
      [698.46,16,2],[784.00,18,1],[698.46,19,2],[622.25,21,1],
      [523.25,22,4],[0,26,2],[466.16,28,2],[523.25,30,2],
    ];
    for (let loop = 0; loop < bars / 4; loop++) {
      melodyNotes.forEach(([freq, pos, dur]) => {
        if (!freq) return;
        const s = t + (loop * 32 + pos) * sixteenth;
        const d = dur * sixteenth;
        const osc = c.createOscillator();
        osc.type = 'sine';
        osc.frequency.value = freq;
        // Add slight vibrato
        const vib = c.createOscillator();
        vib.type = 'sine'; vib.frequency.value = 5.5;
        const vibG = c.createGain(); vibG.gain.value = 3;
        vib.connect(vibG).connect(osc.frequency);
        vib.start(s); vib.stop(s + d + 0.1);

        const g = c.createGain();
        g.gain.setValueAtTime(0, s);
        g.gain.linearRampToValueAtTime(0.045, s + 0.03);
        g.gain.setValueAtTime(0.04, s + d - 0.05);
        g.gain.linearRampToValueAtTime(0, s + d);
        osc.connect(g).connect(discoGain);
        osc.start(s); osc.stop(s + d + 0.01);
        discoNodes.push(osc, vib);
      });
    }

    // ── STRING PAD: Lush Fm → Db ──
    const padChords = [
      { notes: [174.61, 207.65, 261.63], dur: 8 }, // Fm (F3 Ab3 C4)
      { notes: [138.59, 174.61, 207.65], dur: 8 }, // Db (Db3 F3 Ab3)
    ];
    for (let loop = 0; loop < bars / 4; loop++) {
      padChords.forEach((ch, ci) => {
        ch.notes.forEach(freq => {
          const s = t + (loop * 32 + ci * 16) * sixteenth;
          const d = ch.dur * beat;
          // Two detuned oscillators for thickness
          [-3, 3].forEach(detune => {
            const osc = c.createOscillator();
            osc.type = 'sawtooth';
            osc.frequency.value = freq;
            osc.detune.value = detune;
            const g = c.createGain();
            g.gain.setValueAtTime(0, s);
            g.gain.linearRampToValueAtTime(0.015, s + beat);
            g.gain.setValueAtTime(0.015, s + d - beat);
            g.gain.linearRampToValueAtTime(0, s + d);
            const lp = c.createBiquadFilter();
            lp.type = 'lowpass'; lp.frequency.value = 1200;
            osc.connect(lp).connect(g).connect(discoGain);
            osc.start(s); osc.stop(s + d + 0.1);
            discoNodes.push(osc);
          });
        });
      });
    }

    // Schedule next loop before this one ends
    const loopDur = totalBeats * beat;
    discoLoopTimer = setTimeout(() => {
      if (discoActive) scheduleDiscoLoop();
    }, (loopDur - 0.5) * 1000);
  }

  // ── INIT ──────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectButton);
  } else {
    injectButton();
  }
})();
