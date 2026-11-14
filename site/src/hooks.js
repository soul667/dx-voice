import { useEffect, useRef } from 'react';

/* Spotlight cursor tracker: writes --mx / --my onto target card */
export function spotlightHandler(e) {
  const el = e.currentTarget;
  const r = el.getBoundingClientRect();
  el.style.setProperty('--mx', `${e.clientX - r.left}px`);
  el.style.setProperty('--my', `${e.clientY - r.top}px`);
}

const MODE_COLORS = {
  speak: ['#67e8f9', '#818cf8'],
  think: ['#fbbf24', '#fb923c'],
  act: ['#c9f56a', '#34d399'],
};

/* 60 FPS HiDPI 24-bar harmonic & live WebAudio waveform renderer */
export function useHarmonicCanvas({ canvasRef, mode, hudState, analyserRef }) {
  const stateRef = useRef({ mode, hudState });
  stateRef.current = { mode, hudState };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const ctx = canvas.getContext('2d');
    if (!ctx) return undefined;

    const bars = 28;
    const levels = new Float32Array(bars);
    for (let i = 0; i < bars; i += 1) {
      const d = Math.abs(i - (bars - 1) / 2) / ((bars - 1) / 2);
      levels[i] = 0.18 + (Math.cos(d * Math.PI * 0.48) ** 1.4) * 0.46;
    }
    let freqBuf = null;
    let rafId = 0;
    const t0 = performance.now();

    const render = (now) => {
      const { mode: curMode, hudState: curState } = stateRef.current;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const rect = canvas.getBoundingClientRect();
      const w = Math.max(180, Math.round(rect.width || 280));
      const h = Math.max(28, Math.round(rect.height || 40));

      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr;
        canvas.height = h * dpr;
      }

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      const elapsed = (now - t0) / 1000;
      const analyser = analyserRef?.current;
      if (analyser) {
        if (!freqBuf || freqBuf.length !== analyser.frequencyBinCount) {
          freqBuf = new Uint8Array(analyser.frequencyBinCount);
        }
        analyser.getByteFrequencyData(freqBuf);
      }

      const [c1, c2] = MODE_COLORS[curMode] || MODE_COLORS.speak;
      const grad = ctx.createLinearGradient(0, 0, w, 0);
      grad.addColorStop(0, c1);
      grad.addColorStop(1, c2);
      ctx.fillStyle = grad;

      const gap = 4;
      const barW = Math.max(2.5, (w - gap * (bars - 1)) / bars);
      const midY = h / 2;

      for (let i = 0; i < bars; i += 1) {
        const centerDist = Math.abs(i - (bars - 1) / 2) / ((bars - 1) / 2);
        const bell = Math.cos(centerDist * Math.PI * 0.48) ** 1.45;
        let target = 0.1;

        if (analyser && freqBuf && (curState === 'listening' || curState === 'idle')) {
          const idx = Math.min(freqBuf.length - 1, Math.floor((i / bars) * (freqBuf.length * 0.55)) + 2);
          const norm = freqBuf[idx] / 255;
          target = 0.12 + norm * 0.86 * (0.45 + 0.55 * bell);
        } else if (curState === 'listening') {
          const w1 = Math.sin(elapsed * 7.8 + i * 0.52) * 0.5 + 0.5;
          const w2 = Math.sin(elapsed * 13.4 - i * 0.85) * 0.5 + 0.5;
          const cadence = 0.66 + 0.34 * Math.sin(elapsed * 3.1 + i * 0.15);
          target = 0.16 + (0.58 * w1 + 0.42 * w2) * bell * cadence * 0.82;
        } else if (curState === 'arming') {
          const sweep = Math.sin(elapsed * 5.2 - i * 0.28) * 0.5 + 0.5;
          target = 0.12 + sweep * bell * 0.34;
        } else if (curState === 'processing') {
          const travel = Math.exp(-(((i / (bars - 1)) - ((elapsed * 0.85) % 1)) ** 2) / 0.035);
          target = 0.13 + travel * 0.58;
        } else if (curState === 'success') {
          target = 0.14 + bell * 0.22 * Math.max(0, Math.cos(elapsed * 3.2));
        } else {
          const breath = Math.sin(elapsed * 2.1 + i * 0.32) * 0.5 + 0.5;
          target = 0.09 + breath * bell * 0.16;
        }

        const rate = target > levels[i] ? 0.32 : 0.14;
        levels[i] += (target - levels[i]) * rate;

        const bh = Math.max(3.5, levels[i] * (h - 4));
        const x = i * (barW + gap);
        const y = midY - bh / 2;
        const r = Math.min(barW / 2, bh / 2);

        ctx.globalAlpha = curState === 'idle' && !analyser ? 0.52 : 0.95;
        ctx.beginPath();
        if (ctx.roundRect) {
          ctx.roundRect(x, y, barW, bh, r);
        } else {
          ctx.rect(x, y, barW, bh);
        }
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      rafId = window.requestAnimationFrame(render);
    };

    rafId = window.requestAnimationFrame(render);
    return () => window.cancelAnimationFrame(rafId);
  }, [canvasRef, analyserRef]);
}
