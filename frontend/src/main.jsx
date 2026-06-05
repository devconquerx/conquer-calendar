import React from 'react'
import { createRoot } from 'react-dom/client'
import Funnel from './Funnel'

const container = document.getElementById('funnel-root')
const slug = container.dataset.slug
const csrf = container.dataset.csrf

createRoot(container).render(<Funnel slug={slug} csrf={csrf} />)
