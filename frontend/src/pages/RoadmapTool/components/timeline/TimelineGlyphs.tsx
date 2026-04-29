import { useState } from 'react'

export function EditAffordance() {
  return (
    <svg
      className="shrink-0 ml-1 text-ink-faint opacity-0 group-hover:opacity-100 transition-opacity"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
    </svg>
  )
}

export function CardThumb({ slug, name }: { slug: string | null; name: string }) {
  if (!slug) {
    return (
      <div className="w-14 h-9 rounded bg-surface border border-divider shrink-0" />
    )
  }
  return (
    <img
      src={`/photos/cards/${slug}.png`}
      alt={name}
      className="w-14 h-9 object-contain shrink-0"
      onError={(e) => {
        const el = e.currentTarget
        el.style.display = 'none'
      }}
    />
  )
}

export function CurrencyPhoto({
  slug,
  name,
  fallbackColor,
  isCash,
}: {
  slug: string | null
  name: string
  fallbackColor: string
  isCash?: boolean
}) {
  const [failed, setFailed] = useState(false)
  if (!slug || failed) {
    if (isCash) {
      return (
        <div className="w-7 h-7 rounded-full shrink-0 bg-pos flex items-center justify-center">
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="white"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="12" y1="1" x2="12" y2="23" />
            <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
          </svg>
        </div>
      )
    }
    return (
      <div
        className="w-7 h-7 rounded-full shrink-0"
        style={{ backgroundColor: fallbackColor }}
      />
    )
  }
  return (
    <img
      src={`/photos/currencies/${slug}`}
      alt={name}
      className="w-7 h-7 rounded-full object-cover shrink-0"
      onError={() => setFailed(true)}
    />
  )
}
