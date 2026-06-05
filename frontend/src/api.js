function getCsrf() {
  return document.getElementById('funnel-root')?.dataset?.csrf || ''
}

export async function fetchConfig(slug) {
  const res = await fetch(`/f/api/${slug}/config/`)
  if (!res.ok) throw new Error('Error al cargar el formulario')
  return res.json()
}

export async function postResolver(slug, respuestas, tracking = {}) {
  const res = await fetch(`/f/api/${slug}/resolver/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrf(),
    },
    body: JSON.stringify({ respuestas, tracking }),
  })
  if (!res.ok) throw new Error('Error al procesar las respuestas')
  return res.json()
}

export async function postReservar(slug, data) {
  const res = await fetch(`/f/api/${slug}/reservar/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrf(),
    },
    body: JSON.stringify(data),
  })
  return res.json()
}
