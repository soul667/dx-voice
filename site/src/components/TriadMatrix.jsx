import { motion } from 'framer-motion';
import Reveal from './Reveal.jsx';
import { spotlightHandler } from '../hooks.js';

export default function TriadMatrix({ c, activeMode, onSelectMode }) {
  const t = c.triad;
  return (
    <section className="section-block" id="triad">
      <div className="wrap">
        <Reveal className="section-header">
          <div className="eyebrow-line">
            <span className="pulse-dot" />
            <span>{t.eyebrow}</span>
          </div>
          <h2>{t.h2}</h2>
          <p>{t.p}</p>
        </Reveal>

        <div className="triad-cards-grid">
          {t.cards.map((card, idx) => {
            const focused = activeMode === card.id;
            return (
              <Reveal
                as="article"
                key={card.id}
                delay={idx * 0.08}
                className={`triad-arch-card accent-${card.accent} ${focused ? 'is-focused' : ''} spot-card`}
                onPointerMove={spotlightHandler}
                onClick={() => onSelectMode(card.id)}
              >
                <div className="arch-card-top">
                  <span className="arch-num">{card.num}</span>
                  <div className="arch-chords">
                    {card.chord.map((k) => (
                      <kbd key={k} className="keycap-3d sm">{k}</kbd>
                    ))}
                  </div>
                </div>

                <div className="arch-titles">
                  <h3>{card.title}</h3>
                  <span className="arch-hold">{card.hold}</span>
                </div>

                <p className="arch-sub">{card.subtitle}</p>
                <p className="arch-desc">{card.desc}</p>

                <div className="arch-pipeline">
                  {card.pipeline.map((node, i) => (
                    <div key={node.step} className="pipe-step">
                      <span className="pipe-index">{i + 1}</span>
                      <div>
                        <strong>{node.step}</strong>
                        <small>{node.detail}</small>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="arch-boundary">
                  <span className="shield-dot" />
                  <span>{card.boundary}</span>
                </div>

                {focused && (
                  <motion.div
                    layoutId="triad-card-ring"
                    className="triad-card-ring"
                    transition={{ type: 'spring', stiffness: 320, damping: 30 }}
                  />
                )}
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}
