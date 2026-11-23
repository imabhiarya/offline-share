import { forwardRef, ReactNode, useEffect, useImperativeHandle, useRef } from 'react'
import { Bold, Eraser, Italic, List, ListOrdered, Underline } from 'lucide-react'
import { cx } from './ui'

export interface RichEditorHandle { clear: () => void; focus: () => void }

// Minimal rich text editor (bold / italic / underline / bullets / numbering). The server sanitises the HTML.
const RichEditor = forwardRef<RichEditorHandle, { value: string; onChange: (html: string) => void; placeholder?: string; label?: ReactNode; toolbarExtra?: ReactNode; footer?: ReactNode; editorClassName?: string }>(
  function RichEditor({ value, onChange, placeholder, label, toolbarExtra, footer, editorClassName }, ref) {
    const el = useRef<HTMLDivElement>(null)
    useEffect(() => {
      if (el.current && el.current.innerHTML !== value) el.current.innerHTML = value
    }, [value])
    useImperativeHandle(ref, () => ({
      clear: () => { if (el.current) el.current.innerHTML = ''; onChange('') },
      focus: () => el.current?.focus(),
    }))
    const exec = (cmd: string) => {
      el.current?.focus()
      document.execCommand(cmd, false)
      onChange(el.current?.innerHTML || '')
    }
    const onPaste = (e: React.ClipboardEvent) => {
      // keep pasted content simple: plain text keeps line breaks; formatting is re-applied by the user
      e.preventDefault()
      const text = e.clipboardData.getData('text/plain')
      document.execCommand('insertText', false, text)
    }
    const tools = [
      { cmd: 'bold', icon: Bold, label: 'Bold (Ctrl+B)' }, { cmd: 'italic', icon: Italic, label: 'Italic (Ctrl+I)' },
      { cmd: 'underline', icon: Underline, label: 'Underline (Ctrl+U)' }, { cmd: 'insertUnorderedList', icon: List, label: 'Bullet points' },
      { cmd: 'insertOrderedList', icon: ListOrdered, label: 'Numbering' },
    ]
    return (
      <div>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">{label}</div>
          <div className="flex items-center gap-0.5 rounded-lg border border-ink-200 bg-white px-1 py-0.5 shadow-sm">
            {tools.map((t) => (
              <button key={t.cmd} type="button" title={t.label} aria-label={t.label} onMouseDown={(e) => { e.preventDefault(); exec(t.cmd) }}
                className="rounded-md p-1.5 text-ink-800 hover:bg-maroon-50 hover:text-maroon-700"><t.icon className="h-[18px] w-[18px]" /></button>
            ))}
            <span className="mx-1 h-5 w-px bg-ink-200" />
            <button type="button" title="Clear message" aria-label="Clear message" onMouseDown={(e) => { e.preventDefault(); if (el.current) el.current.innerHTML = ''; onChange('') }}
              className="rounded-md p-1.5 text-ink-800 hover:bg-red-50 hover:text-red-600"><Eraser className="h-[18px] w-[18px]" /></button>
            {toolbarExtra}
          </div>
        </div>
        <div className="overflow-hidden rounded-xl border border-ink-200 bg-white focus-within:border-maroon-400 focus-within:ring-2 focus-within:ring-maroon-100">
          <div ref={el} contentEditable suppressContentEditableWarning data-placeholder={placeholder}
            onInput={() => onChange(el.current?.innerHTML || '')} onPaste={onPaste}
            className={cx('editor rich min-h-[210px] max-h-[380px] overflow-y-auto px-4 py-3 text-[15px] text-ink-900 focus:outline-none', editorClassName)} />
          {footer && <div className="flex justify-end px-3 pb-2 text-xs text-ink-500">{footer}</div>}
        </div>
      </div>
    )
  })

export default RichEditor
