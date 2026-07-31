import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'

type Edge = 'none' | 'right' | 'left' | 'both'

/**
 * A sideways scroller that says so.
 *
 * A wide table on a phone cuts at the viewport edge and reads as a table that
 * ends there. This reports which side still holds content in `data-more`, and
 * app.css fades that edge. The state is measured, so a table that fits carries
 * no fade and the last column is never dimmed once the reader reaches it.
 */
export function ScrollBox({
  className,
  children,
}: {
  className: string
  children: ReactNode
}) {
  const ref = useRef<HTMLDivElement | null>(null)
  const [edge, setEdge] = useState<Edge>('none')

  const measure = useCallback(() => {
    const el = ref.current
    if (!el) return
    const slack = el.scrollWidth - el.clientWidth
    if (slack <= 2) return setEdge('none')
    const atStart = el.scrollLeft <= 2
    const atEnd = el.scrollLeft >= slack - 2
    setEdge(atStart ? 'right' : atEnd ? 'left' : 'both')
  }, [])

  useEffect(() => {
    const el = ref.current
    if (!el) return
    measure()
    el.addEventListener('scroll', measure, { passive: true })
    // the column count changes with the canvas, and with the rows themselves
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    const table = el.firstElementChild
    if (table) ro.observe(table)
    return () => {
      el.removeEventListener('scroll', measure)
      ro.disconnect()
    }
  }, [measure, children])

  return (
    <div ref={ref} className={className} data-more={edge}>
      {children}
    </div>
  )
}
