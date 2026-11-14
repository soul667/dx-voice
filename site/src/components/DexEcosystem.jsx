import Reveal from './Reveal.jsx';
import { spotlightHandler } from '../hooks.js';

export default function DexEcosystem({ c }) {
  const dx = c.dex;
  return (
    <section className="section-block" id="dex">
      <div className="wrap">
        <Reveal className="section-header">
          <div className="eyebrow-line">
            <span className="pulse-dot lime" />
            <span>{dx.eyebrow}</span>
          </div>
          <h2>{dx.h2}</h2>
          <p>{dx.p}</p>
        </Reveal>

        <div className="dex-bus-layout">
          {/* Central Dex Command Layer Hub */}
          <Reveal as="div" className="dex-hub-card spot-card" delay={0.08} onPointerMove={spotlightHandler}>
            <div className="dex-hub-badge">
              <span className="dex-monogram lg">{dx.hub.mark}</span>
              <div>
                <h3>{dx.hub.title}</h3>
                <small>{dx.hub.sub}</small>
              </div>
            </div>

            <div className="dex-dual-channels">
              <div className="channel-box">
                <span className="channel-tag">HUMAN</span>
                <code>{dx.hub.humanCmd}</code>
              </div>
              <div className="channel-box agent">
                <span className="channel-tag">AGENT RPC</span>
                <code>{dx.hub.agentCmd}</code>
              </div>
            </div>

            <div className="dex-shared-traits">
              <span>dx tui.engine</span>
              <span>versioned rollback</span>
              <span>local-first</span>
              <span>alias: rh</span>
            </div>
          </Reveal>

          {/* Module Bus Grid */}
          <div className="dex-modules-grid">
            {dx.siblings.map((mod, idx) => (
              <Reveal
                as="article"
                key={mod.name}
                delay={0.1 + idx * 0.06}
                className={`dex-module-card ${mod.active ? 'is-featured' : ''} spot-card`}
                onPointerMove={spotlightHandler}
              >
                <div className="dex-mod-top">
                  <span className="dex-mod-name">{mod.name}</span>
                  <code className="dex-mod-cmd">{mod.cmd}</code>
                </div>
                <p>{mod.role}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
