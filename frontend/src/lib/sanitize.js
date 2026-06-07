import DOMPurify from 'dompurify'

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
