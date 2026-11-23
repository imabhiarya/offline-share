// Thin fetch wrapper: same-origin cookies, CSRF header on mutations, readable errors.

export class ApiError extends Error {
  status: number
  data: any
  constructor(status: number, message: string, data?: any) {
    super(message)
    this.status = status
    this.data = data
  }
}

let csrfToken = ''
let onUnauthorised: (() => void) | null = null

export function setCsrf(token: string) {
  csrfToken = token
}
export function setUnauthorisedHandler(fn: () => void) {
  onUnauthorised = fn
}

function readCookie(name: string): string {
  const m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'))
  return m ? decodeURIComponent(m[1]) : ''
}

export function csrf(): string {
  return csrfToken || readCookie('os_csrf')
}

function messageFrom(data: any, status: number): string {
  if (!data) return `Request failed (${status})`
  if (typeof data.detail === 'string') return data.detail
  if (Array.isArray(data.detail)) {
    return data.detail.map((d: any) => `${(d.loc || []).slice(-1)[0] ?? ''}: ${d.msg}`).join('; ')
  }
  return `Request failed (${status})`
}

export async function request<T = any>(method: string, url: string, body?: any, opts: { raw?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = {}
  let payload: BodyInit | undefined
  if (body instanceof FormData) payload = body
  else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  if (method !== 'GET') headers['X-CSRF-Token'] = csrf()
  let res: Response
  try {
    res = await fetch(url, { method, headers, body: payload, credentials: 'same-origin' })
  } catch {
    throw new ApiError(0, 'Cannot reach the OFFLINE SHARE server. Check the LAN/Wi-Fi connection.')
  }
  if (opts.raw) {
    if (!res.ok) throw new ApiError(res.status, `Request failed (${res.status})`)
    return res as any
  }
  const text = await res.text()
  let data: any = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = { detail: text }
  }
  if (!res.ok) {
    if (res.status === 401 && !url.startsWith('/api/auth/login')) onUnauthorised?.()
    throw new ApiError(res.status, messageFrom(data, res.status), data)
  }
  return data as T
}

export const api = {
  get: <T = any>(url: string) => request<T>('GET', url),
  post: <T = any>(url: string, body?: any) => request<T>('POST', url, body ?? {}),
  put: <T = any>(url: string, body?: any) => request<T>('PUT', url, body ?? {}),
  patch: <T = any>(url: string, body?: any) => request<T>('PATCH', url, body ?? {}),
  del: <T = any>(url: string) => request<T>('DELETE', url),
}

export function qs(params: Record<string, any>): string {
  const p = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '' && v !== false) p.set(k, String(v))
  })
  const s = p.toString()
  return s ? `?${s}` : ''
}

/** Upload one file with progress using XHR (fetch has no upload progress). */
export function uploadFile(url: string, file: File, fields: Record<string, string> = {},
  onProgress?: (pct: number) => void): { promise: Promise<any>; abort: () => void } {
  const xhr = new XMLHttpRequest()
  const promise = new Promise<any>((resolve, reject) => {
    const fd = new FormData()
    Object.entries(fields).forEach(([k, v]) => fd.append(k, v))
    fd.append('file', file, file.name)
    xhr.open('POST', url)
    xhr.withCredentials = true
    xhr.setRequestHeader('X-CSRF-Token', csrf())
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100))
    }
    xhr.onload = () => {
      let data: any = null
      try {
        data = JSON.parse(xhr.responseText)
      } catch {
        data = { detail: xhr.responseText }
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data)
      else reject(new ApiError(xhr.status, messageFrom(data, xhr.status), data))
    }
    xhr.onerror = () => reject(new ApiError(0, 'Network error during upload'))
    xhr.onabort = () => reject(new ApiError(-1, 'Upload cancelled'))
    xhr.send(fd)
  })
  return { promise, abort: () => xhr.abort() }
}

/** Trigger a browser download of a same-origin URL. */
export function download(url: string) {
  const a = document.createElement('a')
  a.href = url
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
}
