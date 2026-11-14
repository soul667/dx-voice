import { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useHarmonicCanvas } from '../hooks.js';

const MODE_ORDER = ['speak', 'think', 'act'];

export default function CarbonHudSimulator({
  c,
  activeMode,
  onSelectMode,
  previewPulse,
}) {
  const [hudState, setHudState] = useState('listening');
  const [streamStep, setStreamStep] = useState(2);
  const [isHolding, setIsHolding] = useState(false);
  const [autoCinema, setAutoCinema] = useState(true);
  const [micActive, setMicActive] = useState(false);
  const [micError, setMicError] = useState('');

  const canvasRef = useRef(null);
  const analyserRef = useRef(null);
  const audioCtxRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const timersRef = useRef([]);

  useHarmonicCanvas({ canvasRef, mode: activeMode, hudState, analyserRef });

  const clearTimers = useCallback(() => {
    timersRef.current.forEach((id) => window.clearTimeout(id));
    timersRef.current = [];
  }, []);

  const schedule = useCallback((fn, ms) => {
    const id = window.setTimeout(fn, ms);
    timersRef.current.push(id);
    return id;
  }, []);

  const modeSpec = c.hud.modes[activeMode] || c.hud.modes.speak;
  const maxSteps = modeSpec.streamTokens.length;

  /* Manual Hold Start */
  const beginHold = useCallback(() => {
    clearTimers();
    setAutoCinema(false);
    setIsHolding(true);
    setStreamStep(0);
    setHudState('arming');

    schedule(() => {
      setHudState('listening');
      for (let i = 1; i <= maxSteps; i += 1) {
        schedule(() => setStreamStep(i), i * 380);
      }
    }, 280);
  }, [clearTimers, maxSteps, schedule]);

  /* Manual Hold Release */
  const releaseHold = useCallback(() => {
    if (!isHolding) return;
    clearTimers();
    setIsHolding(false);
    setStreamStep(maxSteps);
    setHudState('processing');

    schedule(() => {
      setHudState('success');
      schedule(() => {
        setHudState('idle');
      }, 2100);
    }, 520);
  }, [clearTimers, isHolding, maxSteps, schedule]);

  /* Safe keyboard hold: V key (avoids triggering live Linux X11 Ctrl daemon or scrolling page) */
  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.repeat) return;
      const tag = document.activeElement?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      if (e.code === 'KeyV' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        beginHold();
      }
    };
    const onKeyUp = (e) => {
      if (e.code === 'KeyV') {
        releaseHold();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keyup', onKeyUp);
    };
  }, [beginHold, releaseHold]);

  /* External preview trigger from dx v TUI section */
  useEffect(() => {
    if (!previewPulse) return;
    clearTimers();
    setAutoCinema(false);
    setStreamStep(0);
    setHudState('arming');
    schedule(() => {
      setHudState('listening');
      setStreamStep(2);
    }, 260);
    schedule(() => {
      setStreamStep(maxSteps);
      setHudState('processing');
    }, 1350);
    schedule(() => {
      setHudState('success');
    }, 1900);
  }, [previewPulse, clearTimers, maxSteps, schedule]);

  /* Gentle Auto-Cinema Choreography when user isn't manually holding */
  useEffect(() => {
    if (!autoCinema || isHolding) return undefined;
    clearTimers();

    setStreamStep(0);
    setHudState('arming');
    schedule(() => {
      setHudState('listening');
      for (let i = 1; i <= maxSteps; i += 1) {
        schedule(() => setStreamStep(i), i * 440);
      }
    }, 360);

    schedule(() => {
      setHudState('processing');
    }, 360 + maxSteps * 440 + 360);

    schedule(() => {
      setHudState('success');
    }, 360 + maxSteps * 440 + 920);

    schedule(() => {
      const nextIdx = (MODE_ORDER.indexOf(activeMode) + 1) % MODE_ORDER.length;
      onSelectMode(MODE_ORDER[nextIdx]);
    }, 360 + maxSteps * 440 + 2650);

    return () => clearTimers();
  }, [autoCinema, activeMode, isHolding, maxSteps, onSelectMode, clearTimers, schedule]);

  /* Opt-in local WebAudio microphone visualizer */
  const toggleMic = async () => {
    setMicError('');
    if (micActive) {
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((t) => t.stop());
        mediaStreamRef.current = null;
      }
      if (audioCtxRef.current) {
        audioCtxRef.current.close().catch(() => {});
        audioCtxRef.current = null;
      }
      analyserRef.current = null;
      setMicActive(false);
      return;
    }

    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        setMicError('WebAudio unavailable');
        return;
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      const audioCtx = new AudioCtx();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 128;
      analyser.smoothingTimeConstant = 0.76;
      source.connect(analyser);

      mediaStreamRef.current = stream;
      audioCtxRef.current = audioCtx;
      analyserRef.current = analyser;
      setAutoCinema(false);
      setHudState('listening');
      setStreamStep(maxSteps);
      setMicActive(true);
    } catch {
      setMicError('Mic permission declined');
    }
  };

  useEffect(() => () => {
    clearTimers();
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop());
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
    }
  }, [clearTimers]);

  const streamedText = modeSpec.streamTokens.slice(0, streamStep).join('');
  const keysDepressed = isHolding || hudState === 'arming' || hudState === 'listening';

  return (
    <div className="stage-shell" data-stage-mode={activeMode}>
      {/* Mode Switcher Bar */}
      <div className="stage-toolbar">
        <div className="stage-modes" role="tablist" aria-label="HUD Mode">
          {MODE_ORDER.map((mId) => {
            const spec = c.hud.modes[mId];
            const selected = activeMode === mId;
            return (
              <button
                key={mId}
                type="button"
                role="tab"
                aria-selected={selected}
                className={`stage-mode-tab ${selected ? 'is-active' : ''}`}
                data-tab-mode={mId}
                onClick={() => {
                  setAutoCinema(false);
                  onSelectMode(mId);
                  setStreamStep(c.hud.modes[mId].streamTokens.length);
                  setHudState('listening');
                }}
              >
                {selected && (
                  <motion.span
                    layoutId="hud-mode-bg"
                    className="stage-mode-pill-bg"
                    transition={{ type: 'spring', stiffness: 380, damping: 32 }}
                  />
                )}
                <span className="stage-mode-label">{spec.pill}</span>
                <span className="stage-mode-chord">{spec.keys.join('+')}</span>
              </button>
            );
          })}
        </div>

        <div className="stage-toggles">
          <button
            type="button"
            className={`mini-toggle ${autoCinema ? 'is-on' : ''}`}
            onClick={() => setAutoCinema((v) => !v)}
          >
            <span className="mini-dot" />
            {c.hud.autoDemoLabel}
          </button>
          <button
            type="button"
            className={`mini-toggle ${micActive ? 'is-on' : ''}`}
            id="mic-toggle"
            onClick={toggleMic}
          >
            <span className="mini-dot mic" />
            {micActive ? c.hud.micActiveLabel : c.hud.micLabel}
          </button>
        </div>
      </div>

      {/* Live Desktop Viewport + Floating Carbon Fluid Glass HUD */}
      <div className="desktop-viewport">
        <div className="viewport-chrome">
          <div className="traffic-dots" aria-hidden="true">
            <i />
            <i />
            <i />
          </div>
          <span className="viewport-title">{modeSpec.editorTitle}</span>
          <span className="viewport-tag">{c.hud.windowTitle}</span>
        </div>

        {/* Underlying Live Target Application */}
        <div className="viewport-editor">
          <AnimatePresence mode="wait">
            {activeMode === 'speak' && (
              <motion.div
                key="editor-speak"
                className="editor-pane"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.22 }}
              >
                <div className="code-line dim">01  class SpringCapsule:</div>
                <div className="code-line dim">02      stiffness = 340.0</div>
                <div className="code-line active-line">
                  <span className="ln">03</span>
                  <span className="code-comment"># Note: </span>
                  <span className="dictated-live">
                    {streamedText}
                    <span className="live-caret" />
                  </span>
                </div>
              </motion.div>
            )}

            {activeMode === 'think' && (
              <motion.div
                key="editor-think"
                className="editor-pane"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.22 }}
              >
                <div className="spoken-quote">{modeSpec.spokenPrompt}</div>
                <div className="shell-preview">
                  <span className="shell-prompt">❯</span>
                  <code>{hudState === 'success' || hudState === 'processing' || streamStep >= 2 ? modeSpec.generatedCmd : '...'}</code>
                </div>
              </motion.div>
            )}

            {activeMode === 'act' && (
              <motion.div
                key="editor-act"
                className="editor-pane"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.22 }}
              >
                <div className="shell-preview act">
                  <span className="shell-prompt">dx ❯</span>
                  <code>{modeSpec.dxCall}</code>
                </div>
                <pre className="dx-json-out">{modeSpec.dxOutput}</pre>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Floating Carbon Fluid Glass Capsule (v0.6.0 replica) */}
        <div className="hud-float-zone">
          <motion.div
            layout
            transition={{ type: 'spring', stiffness: 340, damping: 30 }}
            className={`carbon-hud state-${hudState} mode-${activeMode}`}
            data-state={hudState}
            data-mode={activeMode}
          >
            {hudState === 'processing' && <div className="hud-beam-ring" aria-hidden="true" />}

            <div className="hud-top-row">
              <div className="hud-status-cluster">
                <span className="hud-glyph-badge" aria-hidden="true">
                  {hudState === 'success' ? (
                    <svg className="hud-check-svg" viewBox="0 0 20 20" fill="none">
                      <motion.path
                        d="M4.5 10.5L8.2 14.2L15.8 6.2"
                        stroke="currentColor"
                        strokeWidth="2.3"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        initial={{ pathLength: 0 }}
                        animate={{ pathLength: 1 }}
                        transition={{ duration: 0.24, ease: 'easeOut' }}
                      />
                    </svg>
                  ) : (
                    <svg className="hud-mic-svg" viewBox="0 0 20 20" fill="none">
                      <rect x="7" y="2.5" width="6" height="9.5" rx="3" stroke="currentColor" strokeWidth="1.7" />
                      <path d="M4.5 9.5a5.5 5.5 0 0 0 11 0M10 15v2.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
                    </svg>
                  )}
                </span>
                <span className="hud-mode-badge">{modeSpec.pill}</span>
                <span className="hud-state-label">{c.hud.states[hudState]}</span>
              </div>

              <div className="hud-keycaps" aria-label="Active shortcut">
                {modeSpec.keys.map((k) => (
                  <kbd key={k} className={`keycap-3d ${keysDepressed ? 'is-pressed' : ''}`}>
                    {k}
                  </kbd>
                ))}
              </div>
            </div>

            {/* 28-bar HiDPI Harmonic Waveform Canvas */}
            <div className="hud-wave-row">
              <canvas ref={canvasRef} className="hud-wave-canvas" />
            </div>

            {/* ContextIndex Chip + Live Transcript / Result Footer */}
            <AnimatePresence mode="popLayout">
              {hudState !== 'arming' && (
                <motion.div
                  key={`${activeMode}-${hudState}`}
                  className="hud-context-row"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.18 }}
                >
                  <span className="context-chip">{modeSpec.contextChip}</span>
                  <span className="hud-result-pill">
                    {hudState === 'success' ? modeSpec.finalBadge : streamedText || modeSpec.name}
                  </span>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </div>
      </div>

      {/* Tactile Hold Control Bar */}
      <div className="stage-action-bar">
        <button
          type="button"
          id="hold-trigger"
          className={`hold-button mode-${activeMode} ${isHolding ? 'is-holding' : ''}`}
          onPointerDown={beginHold}
          onPointerUp={releaseHold}
          onPointerLeave={releaseHold}
          onPointerCancel={releaseHold}
        >
          <span className="hold-pulse-ring" aria-hidden="true" />
          <span className="hold-btn-label">{c.hud.holdButton}</span>
          <span className="hold-btn-sub">{c.hud.holdKeyHint}</span>
        </button>

        <div className="stage-footnote">
          {micError ? <span className="mic-err">{micError}</span> : <span>{modeSpec.footNote}</span>}
        </div>
      </div>
    </div>
  );
}
