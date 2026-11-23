// Light-background illustration: laptop ⇄ central server ⇄ laptop, folders moving between them.
// Inline SVG (works offline). Brand colours follow the active theme through CSS variables.
const B = (k: number) => `rgb(var(--brand-${k}))`

function Laptop({ x, y }: { x: number; y: number }) {
  return (
    <g transform={`translate(${x}, ${y})`}>
      <rect x="0" y="0" width="96" height="62" rx="6" fill="#3a3436" />
      <rect x="5" y="5" width="86" height="52" rx="3" fill={B(700)} />
      <rect x="5" y="5" width="86" height="52" rx="3" fill="url(#ti-shine)" />
      {/* folder on screen */}
      <path d="M30 22 h12 l4 5 h20 a3 3 0 0 1 3 3 v16 a3 3 0 0 1-3 3 H30 a3 3 0 0 1-3-3 V25 a3 3 0 0 1 3-3z" fill="#fbbf24" />
      <path d="M27 31 h42 v15 a3 3 0 0 1-3 3 H30 a3 3 0 0 1-3-3z" fill="#f59e0b" />
      <path d="M-10 62 H106 l-8 9 H-2 Z" fill="#cfc8ca" />
      <rect x="36" y="62" width="24" height="3" rx="1.5" fill="#a8a0a3" />
    </g>
  )
}

export default function TransferIllustration({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 560 190" className={className} role="img" aria-label="Files moving between office laptops through the central server">
      <defs>
        <linearGradient id="ti-shine" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#fff" stopOpacity=".18" /><stop offset=".5" stopColor="#fff" stopOpacity="0" /></linearGradient>
        <linearGradient id="ti-srv" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stopColor="#2b2527" /><stop offset=".5" stopColor="#4a4245" /><stop offset="1" stopColor="#2b2527" /></linearGradient>
        <radialGradient id="ti-disc" cx=".5" cy=".5" r=".5"><stop offset="0" stopColor="#fff" /><stop offset="1" stopColor={B(100)} /></radialGradient>
        <filter id="ti-sh" x="-20%" y="-20%" width="140%" height="160%"><feDropShadow dx="0" dy="6" stdDeviation="6" floodColor="#330f19" floodOpacity=".22" /></filter>
      </defs>
      {/* swoosh */}
      <path d="M330 190 C 420 120, 480 60, 560 20 L560 190 Z" fill={B(200)} opacity=".55" />
      <path d="M380 190 C 450 140, 500 100, 560 80 L560 190 Z" fill={B(400)} opacity=".35" />
      {/* platform rings */}
      <ellipse cx="280" cy="150" rx="110" ry="26" fill="url(#ti-disc)" stroke={B(200)} />
      <ellipse cx="280" cy="150" rx="78" ry="17" fill="none" stroke={B(300)} strokeDasharray="3 5" className="ti-dash" />

      <g filter="url(#ti-sh)"><Laptop x={52} y={58} /></g>
      <g filter="url(#ti-sh)"><Laptop x={412} y={58} /></g>

      {/* server */}
      <g filter="url(#ti-sh)">
        <rect x="245" y="14" width="70" height="132" rx="8" fill="url(#ti-srv)" />
        {[0, 1, 2, 3].map((i) => (
          <g key={i}>
            <rect x="253" y={24 + i * 29} width="54" height="22" rx="3" fill="#1d1819" stroke="#5a5154" />
            <rect x="259" y={33 + i * 29} width="24" height="3" rx="1.5" fill="#6b6265" />
            <circle cx="297" cy={35 + i * 29} r="2.6" fill={i === 1 ? '#f87171' : '#4ade80'} className="ti-blink" style={{ animationDelay: `${i * 0.35}s` }} />
          </g>
        ))}
      </g>

      {/* arrows */}
      <g stroke={B(700)} strokeWidth="5" fill="none" strokeLinecap="round" strokeLinejoin="round">
        <path d="M168 64 C 190 44, 214 40, 236 44" className="ti-arrow" />
        <path d="M226 36 l12 8 -12 8" />
        <path d="M178 54 l-12 10 14 4" />
        <path d="M324 44 C 352 40, 378 46, 400 64" className="ti-arrow" style={{ animationDelay: '.6s' }} />
        <path d="M392 52 l10 13 -15 2" />
      </g>
      {/* moving packets */}
      <circle r="5" fill="#f59e0b"><animateMotion dur="2.4s" repeatCount="indefinite" path="M168 64 C 190 44, 214 40, 236 44" /></circle>
      <circle r="5" fill="#f59e0b"><animateMotion dur="2.4s" begin="1.2s" repeatCount="indefinite" path="M324 44 C 352 40, 378 46, 400 64" /></circle>
    </svg>
  )
}
