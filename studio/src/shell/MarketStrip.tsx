import { useEffect, useRef } from 'react'
import type { GridKey } from '../lib/types'
import { num, php } from '../lib/data'
import type { MarketStripItem } from './marketStripData'

const GRID_LABEL: Record<GridKey, string> = {
  luzon: 'Luzon',
  visayas: 'Visayas',
  mindanao: 'Mindanao',
}

export function MarketStrip({
  date,
  grid,
  items,
  selectedHour,
  onSelectHour,
}: {
  date: string
  grid: GridKey
  items: MarketStripItem[]
  selectedHour: number
  onSelectHour: (hour: number) => void
}) {
  const hourList = useRef<HTMLDivElement>(null)
  const maxPrice = Math.max(
    1,
    ...items.map((item) => Math.max(item.replayedPrice, item.recordedPrice ?? 0))
  )
  const minPrice = Math.min(
    0,
    ...items.map((item) => Math.min(item.replayedPrice, item.recordedPrice ?? 0))
  )
  const priceRange = Math.max(1, maxPrice - minPrice)
  const maxDemand = Math.max(1, ...items.map((item) => item.demandMw))
  const selected = items.find((item) => item.hour === selectedHour) ?? items[0] ?? null

  useEffect(() => {
    const list = hourList.current
    const button = list?.querySelector<HTMLElement>('.is-selected')
    if (!list || !button || list.scrollWidth <= list.clientWidth) return
    list.scrollTo({
      left: button.offsetLeft - (list.clientWidth - button.clientWidth) / 2,
      behavior: 'auto',
    })
  }, [date, grid, selectedHour])

  if (!selected) return null

  return (
    <section
      className="marketstrip"
      aria-label={`Market day timeline for ${GRID_LABEL[grid]}`}
    >
      <div className="marketstrip__head">
        <div>
          <span className="marketstrip__title">Market day</span>
          <span className="marketstrip__scope mono">
            {date} · {GRID_LABEL[grid]}
          </span>
        </div>
        <div className="marketstrip__legend" aria-label="Timeline legend">
          <span>
            <i className="marketstrip__key marketstrip__key--recorded" />
            Recorded price
          </span>
          <span>
            <i className="marketstrip__key marketstrip__key--replayed" />
            Model replay
          </span>
          <span>
            <i className="marketstrip__key marketstrip__key--demand" />
            Demand
          </span>
          <span>
            <i className="marketstrip__key marketstrip__key--flag" />
            Limit or shortfall
          </span>
        </div>
      </div>
      <div ref={hourList} className="marketstrip__hours" aria-label="Hours">
        {items.map((item) => {
          const replayHeight = 10 + (46 * (item.replayedPrice - minPrice)) / priceRange
          const recordedHeight =
            item.recordedPrice == null
              ? null
              : 10 + (46 * (item.recordedPrice - minPrice)) / priceRange
          const demandHeight = 8 + (24 * item.demandMw) / maxDemand
          const state =
            item.shortfallMw > 0 ? 'shortfall' : item.constraint ? 'limited' : 'normal'
          return (
            <button
              key={item.hour}
              type="button"
              className={`marketstrip__hour ${item.hour === selected.hour ? 'is-selected' : ''} is-${state}`}
              aria-pressed={item.hour === selected.hour}
              aria-label={`${String(item.hour).padStart(2, '0')}:00, recorded ${item.recordedPrice == null ? 'unavailable' : php(item.recordedPrice)}, replay ${php(item.replayedPrice)}, demand ${num(item.demandMw)} MW${item.constraint ? ', transfer limit reached' : ''}${item.shortfallMw > 0 ? `, ${num(item.shortfallMw)} MW shortfall` : ''}`}
              onClick={() => onSelectHour(item.hour)}
            >
              <span className="marketstrip__plot" aria-hidden="true">
                <i
                  className="marketstrip__demand"
                  style={{ height: `${demandHeight}%` }}
                />
                <i
                  className="marketstrip__replayed"
                  style={{ height: `${replayHeight}%` }}
                />
                {recordedHeight != null && (
                  <i
                    className="marketstrip__recorded"
                    style={{ bottom: `${recordedHeight}%` }}
                  />
                )}
                {(item.constraint || item.shortfallMw > 0) && (
                  <i className="marketstrip__flag">{item.shortfallMw > 0 ? 'S' : 'L'}</i>
                )}
              </span>
              <span className="marketstrip__hourlabel mono">
                {item.hour % 3 === 0 ? String(item.hour).padStart(2, '0') : ''}
              </span>
            </button>
          )
        })}
      </div>
      <div className="marketstrip__readout" aria-live="polite">
        <b className="mono">{String(selected.hour).padStart(2, '0')}:00</b>
        <span>
          Recorded{' '}
          {selected.recordedPrice == null
            ? 'not available'
            : `${php(selected.recordedPrice)}/kWh`}
        </span>
        <span>Replay {php(selected.replayedPrice)}/kWh</span>
        <span>Demand {num(selected.demandMw)} MW</span>
        <span>Price-setting block {selected.marginal ?? 'not identified'}</span>
        {selected.constraint && <strong>Transfer limit reached</strong>}
        {selected.shortfallMw > 0 && (
          <strong>{num(selected.shortfallMw)} MW shortfall</strong>
        )}
      </div>
    </section>
  )
}
