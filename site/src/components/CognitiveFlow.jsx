import Reveal from './Reveal.jsx';
import { spotlightHandler } from '../hooks.js';

export default function CognitiveFlow({ c }) {
  const f = c.flow;
  return (
    <section className="section-block" id="flow">
      <div className="wrap">
        <Reveal className="section-header">
          <div className="eyebrow-line">
            <span className="pulse-dot" />
            <span>{f.eyebrow}</span>
          </div>
          <h2>{f.h2}</h2>
          <p>{f.p}</p>
        </Reveal>

        <div className="flow-compare-grid">
          <Reveal
            as="article"
            className="flow-card is-old spot-card"
            delay={0.08}
            onPointerMove={spotlightHandler}
          >
            <div className="flow-card-head">
              <span className="flow-tag">{f.old.tag}</span>
              <div className="flow-metric">
                <strong>{f.old.metric}</strong>
                <span>{f.old.metricSub}</span>
              </div>
            </div>
            <h3>{f.old.title}</h3>
            <ul className="flow-step-list">
              {f.old.steps.map((s) => (
                <li key={s.t}>
                  <span className="step-idx">{s.t}</span>
                  <span>{s.text}</span>
                </li>
              ))}
            </ul>
          </Reveal>

          <Reveal
            as="article"
            className="flow-card is-modern spot-card"
            delay={0.16}
            onPointerMove={spotlightHandler}
          >
            <div className="flow-card-head">
              <span className="flow-tag modern">{f.modern.tag}</span>
              <div className="flow-metric modern">
                <strong>{f.modern.metric}</strong>
                <span>{f.modern.metricSub}</span>
              </div>
            </div>
            <h3>{f.modern.title}</h3>
            <ul className="flow-step-list modern">
              {f.modern.steps.map((s) => (
                <li key={s.t}>
                  <span className={`step-idx badge-${s.t.toLowerCase()}`}>{s.t}</span>
                  <span>{s.text}</span>
                </li>
              ))}
            </ul>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
