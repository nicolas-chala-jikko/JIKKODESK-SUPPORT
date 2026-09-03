import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './app.jsx'
import '../styles/tokens.css'
import '../styles/shell.css'
import '../styles/components.css'
import '../styles/pages.css'

createRoot(document.getElementById('root')).render(<App />)
