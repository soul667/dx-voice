import { createRoot } from 'react-dom/client';
import App from './App.jsx';

import '@fontsource-variable/inter';
import '@fontsource-variable/playfair-display';
import '@fontsource-variable/playfair-display/wght-italic.css';
import '@fontsource/noto-sans-sc/400.css';
import '@fontsource/noto-sans-sc/500.css';
import '@fontsource/noto-sans-sc/700.css';

import './styles.css';

createRoot(document.getElementById('root')).render(<App initialLang="zh" />);
