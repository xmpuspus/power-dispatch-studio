import type { ReactNode } from 'react'

export function Panel({
  title,
  subtitle,
  right,
  children,
  className = '',
}: {
  title?: ReactNode
  subtitle?: ReactNode
  right?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`panel ${className}`}>
      {(title || right) && (
        <header className="panel__head">
          <div>
            {title && <h3 className="panel__title">{title}</h3>}
            {subtitle && <p className="panel__sub">{subtitle}</p>}
          </div>
          {right && <div className="panel__right">{right}</div>}
        </header>
      )}
      <div className="panel__body">{children}</div>
    </section>
  )
}

export function StatTile({
  label,
  value,
  unit,
  hint,
  tone = 'default',
}: {
  label: string
  value: ReactNode
  unit?: string
  hint?: ReactNode
  tone?: 'default' | 'accent' | 'danger' | 'positive'
}) {
  return (
    <div className={`stat stat--${tone}`}>
      <div className="stat__label">{label}</div>
      <div className="stat__value mono">
        {value}
        {unit && <span className="stat__unit"> {unit}</span>}
      </div>
      {hint && <div className="stat__hint">{hint}</div>}
    </div>
  )
}

export function Chip({
  children,
  tone = 'default',
}: {
  children: ReactNode
  tone?: 'default' | 'accent' | 'danger' | 'positive' | 'primary'
}) {
  return <span className={`chip chip--${tone}`}>{children}</span>
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  ariaLabel,
}: {
  options: { value: T; label: string }[]
  value: T
  onChange: (v: T) => void
  ariaLabel: string
}) {
  return (
    <div className="segmented" role="tablist" aria-label={ariaLabel}>
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          aria-selected={o.value === value}
          className={`segmented__item ${o.value === value ? 'is-active' : ''}`}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Source({
  href,
  label = 'source',
}: {
  href?: string | null
  label?: string
}) {
  if (!href) return null
  return (
    <a className="source" href={href} target="_blank" rel="noopener noreferrer">
      {label}
      <svg width="10" height="10" viewBox="0 0 24 24" aria-hidden="true">
        <path
          fill="none"
          stroke="currentColor"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M14 5h5v5M19 5l-9 9M11 5H6a1 1 0 00-1 1v12a1 1 0 001 1h12a1 1 0 001-1v-5"
        />
      </svg>
    </a>
  )
}

export function Meter({ frac, tone = 'primary' }: { frac: number; tone?: string }) {
  const w = Math.max(0, Math.min(1, frac)) * 100
  return (
    <div className="meter" aria-hidden="true">
      <span className={`meter__fill meter__fill--${tone}`} style={{ width: `${w}%` }} />
    </div>
  )
}

export function EmptyNote({ children }: { children: ReactNode }) {
  return <p className="empty-note">{children}</p>
}

export function ThemeToggle({
  theme,
  onToggle,
}: {
  theme: 'light' | 'dark'
  onToggle: () => void
}) {
  return (
    <button
      className="btn btn--ghost btn--icon"
      onClick={onToggle}
      aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
    >
      {theme === 'light' ? (
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
          <path
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"
          />
        </svg>
      ) : (
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
          <circle
            cx="12"
            cy="12"
            r="4.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          />
          <path
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            d="M12 2v2M12 20v2M4 12H2M22 12h-2M5 5l1.4 1.4M17.6 17.6L19 19M19 5l-1.4 1.4M6.4 17.6L5 19"
          />
        </svg>
      )}
    </button>
  )
}
