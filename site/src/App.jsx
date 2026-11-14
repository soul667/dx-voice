import { useEffect, useState } from 'react';
import { MotionConfig } from 'framer-motion';
import { CONTENT } from './content.jsx';
import { AmbientField, Footer, Nav, ScrollProgress } from './components/Chrome.jsx';
import HeroStage from './components/HeroStage.jsx';
import CognitiveFlow from './components/CognitiveFlow.jsx';
import TriadMatrix from './components/TriadMatrix.jsx';
import ContextXRay from './components/ContextXRay.jsx';
import DexEcosystem from './components/DexEcosystem.jsx';
import TuiWorkspace from './components/TuiWorkspace.jsx';
import ScopeAndStart from './components/ScopeAndStart.jsx';

export default function App({ initialLang = 'zh' }) {
  const [lang, setLang] = useState(() => {
    if (typeof window !== 'undefined') {
      const q = new URLSearchParams(window.location.search).get('lang');
      if (q === 'en' || q === 'zh') return q;
    }
    return initialLang;
  });

  const [theme, setTheme] = useState('obsidian');
  const [activeMode, setActiveMode] = useState('speak');
  const [previewPulse, setPreviewPulse] = useState(0);

  const c = CONTENT[lang] || CONTENT.zh;

  useEffect(() => {
    document.documentElement.lang = c.lang;
    document.documentElement.setAttribute('data-theme', theme);
  }, [c.lang, theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'obsidian' ? 'alabaster' : 'obsidian'));
  };

  const toggleLang = () => {
    setLang((prev) => (prev === 'zh' ? 'en' : 'zh'));
  };

  const triggerHudPreview = () => {
    setPreviewPulse((n) => n + 1);
  };

  return (
    <MotionConfig reducedMotion="user">
      <ScrollProgress />
      <AmbientField activeMode={activeMode} />
      <Nav
        c={c}
        theme={theme}
        onToggleTheme={toggleTheme}
        onToggleLang={toggleLang}
      />

      <main>
        <HeroStage
          c={c}
          activeMode={activeMode}
          onSelectMode={setActiveMode}
          previewPulse={previewPulse}
          onTriggerPreview={triggerHudPreview}
        />
        <CognitiveFlow c={c} />
        <TriadMatrix
          c={c}
          activeMode={activeMode}
          onSelectMode={setActiveMode}
        />
        <ContextXRay c={c} />
        <DexEcosystem c={c} />
        <TuiWorkspace
          c={c}
          onTriggerPreview={triggerHudPreview}
        />
        <ScopeAndStart
          c={c}
          onTriggerPreview={triggerHudPreview}
        />
      </main>

      <Footer c={c} />
    </MotionConfig>
  );
}
