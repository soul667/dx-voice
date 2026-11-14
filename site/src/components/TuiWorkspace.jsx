import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import Reveal from './Reveal.jsx';

export default function TuiWorkspace({ c, onTriggerPreview }) {
  const tui = c.tui;
  const [activeTabId, setActiveTabId] = useState('overview');
  const [query, setQuery] = useState('');
  const [toastVisible, setToastVisible] = useState(false);

  const activeTab = tui.tabs.find((t) => t.id === activeTabId) || tui.tabs[0];

  const handlePreview = () => {
    setToastVisible(true);
    onTriggerPreview();
    window.setTimeout(() => setToastVisible(false), 3200);
  };

  const filteredHistory = (activeTab.historyItems || []).filter((row) => {
    if (!query.trim()) return true;
    const q = query.toLowerCase();
    return (
      row.out.toLowerCase().includes(q) ||
      row.mode.toLowerCase().includes(q) ||
      row.status.toLowerCase().includes(q)
    );
  });

  return (
    <section className="section-block" id="tui">
      <div className="wrap">
        <Reveal className="section-header">
          <div className="eyebrow-line">
            <span className="pulse-dot" />
            <span>{tui.eyebrow}</span>
          </div>
          <h2>{tui.h2}</h2>
          <p>{tui.p}</p>
        </Reveal>

        <Reveal className="textual-frame" delay={0.1}>
          {/* Terminal Top Bar */}
          <div className="textual-titlebar">
            <div className="traffic-dots" aria-hidden="true">
              <i />
              <i />
              <i />
            </div>
            <span className="textual-cmd">dx v · Textual + dx tui.engine · ~/.config/dx-voice/settings.txt (0600)</span>
            <button
              type="button"
              id="preview-hud-btn"
              className="textual-preview-btn"
              onClick={handlePreview}
            >
              <span>▶ dx v preview</span>
            </button>
          </div>

          {toastVisible && (
            <div className="textual-toast" role="status">
              {tui.previewToast}
            </div>
          )}

          {/* 7 Textual Tabs */}
          <div className="textual-tabs" role="tablist" aria-label="dx v workspace tabs">
            {tui.tabs.map((tab) => {
              const selected = tab.id === activeTabId;
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={selected}
                  className={`textual-tab ${selected ? 'is-active' : ''}`}
                  onClick={() => setActiveTabId(tab.id)}
                >
                  <span className="tab-key">[{tab.shortcut}]</span>
                  <span>{tab.label}</span>
                  {selected && (
                    <motion.span
                      layoutId="textual-tab-underline"
                      className="textual-tab-line"
                      transition={{ type: 'spring', stiffness: 400, damping: 34 }}
                    />
                  )}
                </button>
              );
            })}
          </div>

          {/* Tab Panel Content */}
          <div className="textual-body">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2 }}
              >
                {activeTab.cards && (
                  <div className="textual-stat-grid">
                    {activeTab.cards.map((card) => (
                      <div key={card.k} className={`textual-stat-card tone-${card.tone}`}>
                        <span className="stat-k">{card.k}</span>
                        <strong className="stat-v">{card.v}</strong>
                      </div>
                    ))}
                  </div>
                )}

                {activeTab.rows && (
                  <div className="textual-kv-table">
                    {activeTab.rows.map(([k, v]) => (
                      <div key={k} className="textual-kv-row">
                        <code>{k}</code>
                        <span>{v}</span>
                      </div>
                    ))}
                  </div>
                )}

                {activeTab.historyItems && (
                  <div className="textual-history-pane">
                    <div className="textual-search-row">
                      <span className="search-slash">/</span>
                      <input
                        type="search"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder={tui.searchPlaceholder}
                        aria-label="Search local voice history"
                      />
                    </div>
                    <div className="textual-history-table">
                      {filteredHistory.map((item) => (
                        <div key={`${item.time}-${item.mode}`} className="history-row">
                          <span className="h-time">{item.time}</span>
                          <span className={`h-mode mode-${item.mode.toLowerCase()}`}>{item.mode}</span>
                          <span className="h-out">{item.out}</span>
                          <span className="h-status">{item.status}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </motion.div>
            </AnimatePresence>
          </div>

          <div className="textual-statusbar">
            <span>^S Save</span>
            <span>/ Filter History</span>
            <span>p Preview HUD</span>
            <span>r Refresh Context</span>
            <span>q Quit</span>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
