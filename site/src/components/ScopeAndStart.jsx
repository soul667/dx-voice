import { useState } from 'react';
import * as Tabs from '@radix-ui/react-tabs';
import Reveal from './Reveal.jsx';
import { spotlightHandler } from '../hooks.js';

export default function ScopeAndStart({ c, onTriggerPreview }) {
  const ins = c.install;
  const cl = c.closing;
  const [activeTab, setActiveTab] = useState(ins.tabs[0].id);
  const [copied, setCopied] = useState(false);

  const currentTab = ins.tabs.find((t) => t.id === activeTab) || ins.tabs[0];

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(currentTab.code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };

  return (
    <>
      <section className="section-block" id="install">
        <div className="wrap">
          <Reveal className="section-header">
            <div className="eyebrow-line">
              <span className="pulse-dot lime" />
              <span>{ins.eyebrow}</span>
            </div>
            <h2>{ins.h2}</h2>
            <p>{ins.p}</p>
          </Reveal>

          <Reveal delay={0.08}>
            <Tabs.Root
              className="install-console"
              value={activeTab}
              onValueChange={(v) => {
                setActiveTab(v);
                setCopied(false);
              }}
            >
              <div className="install-bar">
                <Tabs.List className="install-tablist" aria-label="Installation methods">
                  {ins.tabs.map((tab) => (
                    <Tabs.Trigger key={tab.id} value={tab.id} className="install-trigger">
                      {tab.label}
                    </Tabs.Trigger>
                  ))}
                </Tabs.List>

                <button type="button" className="copy-btn" onClick={handleCopy}>
                  {copied ? `✓ ${ins.copiedLabel}` : ins.copyLabel}
                </button>
              </div>

              {ins.tabs.map((tab) => (
                <Tabs.Content key={tab.id} value={tab.id} className="install-code-panel">
                  <pre>
                    <code>{tab.code}</code>
                  </pre>
                </Tabs.Content>
              ))}
            </Tabs.Root>
          </Reveal>

          {/* Engineering Honesty Split: Shipped v0.6.0 vs Roadmap */}
          <div className="scope-split-grid">
            <Reveal
              as="article"
              className="scope-card shipped spot-card"
              delay={0.14}
              onPointerMove={spotlightHandler}
            >
              <div className="scope-head">
                <span className="scope-dot ok" />
                <h3>{ins.shippedTitle}</h3>
              </div>
              <ul>
                {ins.shipped.map((line) => (
                  <li key={line}>
                    <span className="mark ok">✓</span>
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
            </Reveal>

            <Reveal
              as="article"
              className="scope-card roadmap spot-card"
              delay={0.2}
              onPointerMove={spotlightHandler}
            >
              <div className="scope-head">
                <span className="scope-dot amber" />
                <h3>{ins.roadmapTitle}</h3>
              </div>
              <ul>
                {ins.roadmap.map((line) => (
                  <li key={line}>
                    <span className="mark">◌</span>
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
            </Reveal>
          </div>
        </div>
      </section>

      {/* Monumental Closing Manifesto */}
      <section className="closing-manifesto">
        <div className="wrap closing-inner">
          <Reveal as="div" className="eyebrow-pill center">
            <span className="pulse-dot lime" />
            <span>{cl.eyebrow}</span>
          </Reveal>
          <Reveal as="h2" className="closing-triad" delay={0.08}>
            {cl.triad}
          </Reveal>
          <Reveal as="p" className="closing-sub" delay={0.16}>
            {cl.sub}
          </Reveal>
          <Reveal as="div" className="closing-actions" delay={0.24}>
            <a
              href="#top"
              className="btn-primary mode-act"
              onClick={() => {
                window.setTimeout(() => onTriggerPreview(), 250);
              }}
            >
              <span>{cl.ctaPrimary}</span>
              <span aria-hidden="true">↑</span>
            </a>
            <a href="#install" className="btn-ghost">
              <span>{cl.ctaSecondary}</span>
            </a>
          </Reveal>
        </div>
      </section>
    </>
  );
}
