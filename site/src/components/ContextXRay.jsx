import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import Reveal from './Reveal.jsx';

export default function ContextXRay({ c }) {
  const cx = c.context;
  const [activeIdx, setActiveIdx] = useState(0);
  const sc = cx.scenarios[activeIdx] || cx.scenarios[0];

  return (
    <section className="section-block" id="context">
      <div className="wrap">
        <Reveal className="section-header">
          <div className="eyebrow-line">
            <span className="pulse-dot" />
            <span>{cx.eyebrow}</span>
          </div>
          <h2>{cx.h2}</h2>
          <p>{cx.p}</p>
        </Reveal>

        <Reveal className="privacy-ribbon" delay={0.08}>
          {cx.privacyBadges.map((b) => (
            <span key={b} className="privacy-chip">
              <i aria-hidden="true">◆</i> {b}
            </span>
          ))}
        </Reveal>

        <Reveal className="xray-console" delay={0.14}>
          <div className="xray-tabs" role="tablist" aria-label="Workspace Context Scenarios">
            {cx.scenarios.map((item, idx) => {
              const selected = idx === activeIdx;
              return (
                <button
                  key={item.id}
                  type="button"
                  role="tab"
                  aria-selected={selected}
                  className={`xray-tab ${selected ? 'is-active' : ''}`}
                  onClick={() => setActiveIdx(idx)}
                >
                  {selected && (
                    <motion.span
                      layoutId="xray-tab-pill"
                      className="xray-tab-bg"
                      transition={{ type: 'spring', stiffness: 380, damping: 32 }}
                    />
                  )}
                  <span>{item.tab}</span>
                </button>
              );
            })}
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={sc.id}
              className="xray-body"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.24 }}
            >
              <div className="xray-col probe-col">
                <div className="xray-label">01 · X11 FOCUS + /PROC CWD PROBE (&lt; 2ms · 0 PX UPLOADED)</div>
                <div className="probe-line">{sc.focusWin}</div>
                <div className="probe-line accent">{sc.procCwd}</div>

                <div className="xray-label mt">02 · SQLITE FTS5 VOCABULARY HINTS (SESSION.UPDATE)</div>
                <div className="symbol-cloud">
                  {sc.symbols.map((sym) => (
                    <code key={sym} className="sym-pill">{sym}</code>
                  ))}
                </div>

                <div className="xray-label mt">03 · AUTOMATIC SECRET &amp; KEY REDACTION</div>
                <div className="scrub-list">
                  {sc.scrubbed.map((line) => (
                    <div key={line} className="scrub-item">
                      <span className="scrub-shield">REDACTED</span>
                      <span>{line}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="xray-col diff-col">
                <div className="diff-box raw">
                  <span className="diff-tag">WITHOUT CONTEXTINDEX · GENERIC ASR</span>
                  <p>{sc.rawAsr}</p>
                </div>
                <div className="diff-arrow" aria-hidden="true">↓ session.update vocabulary + light context</div>
                <div className="diff-box enhanced">
                  <span className="diff-tag ok">WITH DX VOICE CONTEXTINDEX</span>
                  <p>{sc.enhancedAsr}</p>
                </div>
              </div>
            </motion.div>
          </AnimatePresence>
        </Reveal>
      </div>
    </section>
  );
}
