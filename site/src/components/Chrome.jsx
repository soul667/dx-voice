import { motion, useScroll, useSpring } from 'framer-motion';

export function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 160, damping: 28, mass: 0.25 });
  return <motion.div className="scroll-progress" aria-hidden="true" style={{ scaleX }} />;
}

export function AmbientField({ activeMode }) {
  return (
    <div className="ambient-stage" data-mode={activeMode} aria-hidden="true">
      <div className="ambient-orb orb-a" />
      <div className="ambient-orb orb-b" />
      <div className="ambient-orb orb-c" />
      <div className="ambient-grid" />
      <div className="ambient-grain" />
    </div>
  );
}

export function Nav({ c, theme, onToggleTheme, onToggleLang }) {
  return (
    <header className="site-nav">
      <div className="nav-inner">
        <a className="brand-cluster" href="#top" aria-label="DX Voice Home">
          <span className="dex-monogram">d.</span>
          <span className="brand-dex">{c.nav.parentBrand}</span>
          <span className="brand-slash">{c.nav.moduleTag}</span>
          <span className="brand-version">{c.nav.badge}</span>
        </a>

        <nav className="nav-links" aria-label="Primary Navigation">
          {c.nav.links.map((item) => (
            <a key={item.href} href={item.href}>
              {item.label}
            </a>
          ))}
        </nav>

        <div className="nav-controls">
          <button
            type="button"
            className="ctrl-pill"
            onClick={onToggleTheme}
            aria-label="Switch color theme"
          >
            <span className="theme-dot" data-theme-dot={theme} />
            <span>{theme === 'obsidian' ? c.nav.themeLabels.alabaster : c.nav.themeLabels.obsidian}</span>
          </button>

          <button
            type="button"
            className="ctrl-pill mono"
            onClick={onToggleLang}
            aria-label="Switch language"
          >
            {c.nav.langToggle}
          </button>

          <a className="nav-cta" href="#install">
            <span>{c.nav.cta}</span>
            <span aria-hidden="true">↘</span>
          </a>
        </div>
      </div>
    </header>
  );
}

export function Footer({ c }) {
  return (
    <footer className="site-footer">
      <div className="wrap footer-inner">
        <div className="footer-brand">
          <span className="dex-monogram sm">d.</span>
          <span>{c.closing.footerLeft}</span>
        </div>
        <span className="footer-meta">{c.closing.footerRight}</span>
      </div>
    </footer>
  );
}
