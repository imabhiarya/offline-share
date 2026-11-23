// Clipboard helpers. The async Clipboard API needs a secure context (HTTPS or localhost);
// on plain-HTTP LAN deployments we fall back to a hidden textarea + execCommand('copy').

export async function copyText(text: string): Promise<'clipboard-api' | 'fallback'> {
  if (window.isSecureContext && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return 'clipboard-api'
    } catch {
      /* fall through to legacy path */
    }
  }
  const ta = document.createElement('textarea')
  ta.value = text
  ta.setAttribute('readonly', '')
  ta.style.position = 'fixed'
  ta.style.top = '-1000px'
  ta.style.opacity = '0'
  document.body.appendChild(ta)
  const sel = document.getSelection()
  const prev = sel && sel.rangeCount ? sel.getRangeAt(0) : null
  ta.select()
  ta.setSelectionRange(0, text.length)
  let ok = false
  try {
    ok = document.execCommand('copy')
  } finally {
    ta.remove()
    if (prev && sel) {
      sel.removeAllRanges()
      sel.addRange(prev)
    }
  }
  if (!ok) throw new Error('Copy was blocked by the browser. Select the text and press Ctrl+C.')
  return 'fallback'
}

/** Copy rich text (HTML + plain) where supported, else plain text. */
export async function copyRich(html: string, text: string): Promise<void> {
  const CI = (window as any).ClipboardItem
  if (window.isSecureContext && navigator.clipboard?.write && CI) {
    try {
      await navigator.clipboard.write([new CI({
        'text/html': new Blob([html], { type: 'text/html' }),
        'text/plain': new Blob([text], { type: 'text/plain' }),
      })])
      return
    } catch {
      /* fall back */
    }
  }
  await copyText(text)
}

/** Copy an image file to the clipboard (PNG/JPEG). Browsers cannot place arbitrary files on the OS clipboard. */
export async function copyImageFromUrl(url: string): Promise<boolean> {
  const CI = (window as any).ClipboardItem
  if (!(window.isSecureContext && typeof navigator.clipboard?.write === 'function' && CI)) return false
  const res = await fetch(url, { credentials: 'same-origin' })
  let blob = await res.blob()
  if (blob.type !== 'image/png') {
    // Chrome only accepts image/png on the clipboard: convert via canvas
    const bmp = await createImageBitmap(blob)
    const canvas = document.createElement('canvas')
    canvas.width = bmp.width
    canvas.height = bmp.height
    canvas.getContext('2d')!.drawImage(bmp, 0, 0)
    blob = await new Promise<Blob>((r) => canvas.toBlob((b) => r(b!), 'image/png'))
  }
  await navigator.clipboard.write([new CI({ 'image/png': blob })])
  return true
}
