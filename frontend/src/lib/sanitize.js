// isomorphic-dompurify: en el build cliente resuelve al DOMPurify del navegador
// (sin jsdom, vía el campo "browser"); en el build SSR usa jsdom. Así `safeHtml`
// produce la MISMA salida en servidor y cliente y no hay hydration mismatch.
import DOMPurify from 'isomorphic-dompurify'

/**
 * Sanitiza HTML para usar con dangerouslySetInnerHTML. Solo formato básico.
 */
export function sanitizeHtml(html) {
  if (!html) return ''
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'br', 'span', 'p', 'ul', 'ol', 'li', 'a', 'sub', 'sup'],
    ALLOWED_ATTR: ['href', 'target', 'rel', 'class', 'style'],
  })
}

export function safeHtml(html) {
  return { __html: sanitizeHtml(html) }
}
