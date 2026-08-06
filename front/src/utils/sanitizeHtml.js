/**
 * Lightweight HTML sanitizer for controlled rich text rendering.
 * Removes dangerous tags/attributes and normalizes URLs.
 */
const ALLOWED_TAGS = new Set([
  'div', 'span', 'p', 'br', 'hr',
  'strong', 'b', 'em', 'i', 'u', 'small', 'code', 'pre',
  'ul', 'ol', 'li',
  'table', 'thead', 'tbody', 'tr', 'th', 'td',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'a'
])

const ALLOWED_ATTRS = new Set([
  'class', 'style', 'title', 'role',
  'href', 'target', 'rel',
  'colspan', 'rowspan'
])

const BLOCKED_TAGS = new Set([
  'script', 'style', 'iframe', 'object', 'embed', 'link', 'meta', 'base'
])

function isSafeUrl(url) {
  const value = (url || '').trim().toLowerCase()
  if (!value) return false
  return (
    value.startsWith('http://') ||
    value.startsWith('https://') ||
    value.startsWith('/') ||
    value.startsWith('#') ||
    value.startsWith('mailto:') ||
    value.startsWith('tel:')
  )
}

function sanitizeElement(el) {
  const tag = el.tagName.toLowerCase()

  if (BLOCKED_TAGS.has(tag)) {
    el.remove()
    return
  }

  if (!ALLOWED_TAGS.has(tag)) {
    const parent = el.parentNode
    if (!parent) return
    while (el.firstChild) parent.insertBefore(el.firstChild, el)
    el.remove()
    return
  }

  const attrs = Array.from(el.attributes)
  for (const attr of attrs) {
    const name = attr.name.toLowerCase()
    const value = attr.value

    if (name.startsWith('on')) {
      el.removeAttribute(attr.name)
      continue
    }

    if (!ALLOWED_ATTRS.has(name)) {
      el.removeAttribute(attr.name)
      continue
    }

    if ((name === 'href' || name === 'src') && !isSafeUrl(value)) {
      el.removeAttribute(attr.name)
      continue
    }

    if (tag === 'a' && name === 'target') {
      const target = (value || '').trim().toLowerCase()
      if (target === '_blank') {
        el.setAttribute('rel', 'noopener noreferrer')
      }
    }
  }

  const children = Array.from(el.children)
  for (const child of children) sanitizeElement(child)
}

export function sanitizeHtml(input) {
  if (typeof input !== 'string' || !input.trim()) return ''
  const doc = globalThis?.document
  if (!doc) return ''
  const template = doc.createElement('template')
  template.innerHTML = input

  const roots = Array.from(template.content.children)
  for (const root of roots) sanitizeElement(root)

  return template.innerHTML
}

export default sanitizeHtml
