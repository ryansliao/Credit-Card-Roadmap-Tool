import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

// Font faces — variable fonts, full weight range each
import '@fontsource-variable/inter'
import '@fontsource-variable/jetbrains-mono'

import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
