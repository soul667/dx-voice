import { motion } from 'framer-motion';
import Reveal from './Reveal.jsx';
import CarbonHudSimulator from './CarbonHudSimulator.jsx';

export default function HeroStage({
  c,
  activeMode,
  onSelectMode,
  previewPulse,
  onTriggerPreview,
}) {
  return (
    <section className="hero-section" id="top">
      <div className="wrap hero-grid">
        <div className="hero-copy">
          <Reveal as="div" className="eyebrow-pill" delay={0.04}>
            <span className="pulse-dot" />
            <span>{c.hero.eyebrow}</span>
          </Reveal>

          {/* Interactive Kinetic Philosophy Triad */}
          <Reveal as="div" className="triad-headline" delay={0.1}>
            <h1 aria-label="Just speak. Just think. Just act.">
              {c.hero.triad.map((item) => {
                const isSelected = activeMode === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    className={`triad-line mode-${item.id} ${isSelected ? 'is-selected' : ''}`}
                    onClick={() => onSelectMode(item.id)}
                    onMouseEnter={() => onSelectMode(item.id)}
                  >
                    {isSelected && (
                      <motion.span
                        layoutId="triad-active-bar"
                        className="triad-active-bar"
                        transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                      />
                    )}
                    <span className="triad-words">
                      <span className="triad-verb">{item.verb}</span>{' '}
                      <em className="triad-focus">{item.focus}</em>
                    </span>
                    <span className="triad-meta">
                      <kbd>{item.chord}</kbd>
                      <small>{item.tag}</small>
                    </span>
                  </button>
                );
              })}
            </h1>
          </Reveal>

          <Reveal as="p" className="manifesto-banner-line" delay={0.18}>
            {c.hero.manifestoEn}
          </Reveal>

          <Reveal as="p" className="hero-lede" delay={0.24}>
            {c.hero.manifestoSub}
          </Reveal>

          <Reveal as="div" className="hero-cta-row" delay={0.3}>
            <button
              type="button"
              className={`btn-primary mode-${activeMode}`}
              onClick={onTriggerPreview}
            >
              <span>{c.hero.primaryCta}</span>
              <span aria-hidden="true">✦</span>
            </button>
            <a className="btn-ghost" href="#dex">
              <span>{c.hero.secondaryCta}</span>
              <span aria-hidden="true">↘</span>
            </a>
          </Reveal>

          <Reveal as="div" className="hero-telemetry" delay={0.36}>
            {c.hero.metrics.map((m) => (
              <div key={m.label} className="telemetry-cell">
                <strong>{m.value}</strong>
                <span>{m.label}</span>
              </div>
            ))}
          </Reveal>
        </div>

        <Reveal as="div" className="hero-stage-col" delay={0.18}>
          <CarbonHudSimulator
            c={c}
            activeMode={activeMode}
            onSelectMode={onSelectMode}
            previewPulse={previewPulse}
          />
        </Reveal>
      </div>
    </section>
  );
}
