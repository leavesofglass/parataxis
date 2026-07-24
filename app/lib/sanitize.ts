/**
 * Minimal HTML sanitizer for poem body markup.
 * Allows only <em> and </em>; escapes all other angle-bracket content.
 */
export function sanitizePoemHtml(html: string): string {
  // Split on <em> / </em> (case-insensitive). Captured groups land at odd indices.
  return html
    .split(/(<\/?em>)/i)
    .map((chunk, i) => {
      if (i % 2 === 1) return chunk.toLowerCase() === '<em>' ? '<em>' : '</em>'
      return chunk.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    })
    .join('')
}
