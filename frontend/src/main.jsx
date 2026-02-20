/**
 * Application entry point — bootstraps the React app into the DOM.
 *
 * Mounts the root <App /> component inside React.StrictMode, which
 * enables additional development-time checks (double-rendering to
 * catch side effects, deprecation warnings, etc.).
 *
 * The global stylesheet (index.css) is imported here so it's included
 * in the Vite build's CSS bundle.
 */

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>
)
