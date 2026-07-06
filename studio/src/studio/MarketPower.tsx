import type { Dispatch } from '../lib/types'
import { num, pct, useMarketPower } from '../lib/data'
import { Panel, StatTile, Source, EmptyNote } from '../ui/kit'

// Market-power / concentration lens. The merit-order price cannot show who owns the
// stack; a concentrated fleet can move price even with physical headroom. Built from
// the ERC's published capacity shares, framed against the reserve margin the dispatch
// already computes. Display-only (sourced), no solve.
export function MarketPowerView({ d }: { d: Dispatch }) {
  const m = useMarketPower()
  if (m.loading) return <EmptyNote>Loading the concentration layer.</EmptyNote>
  if (m.error || !m.data?.available)
    return <EmptyNote>Market-power layer not baked. Run make data.</EmptyNote>
  const mp = m.data
  const firms = mp.companies ?? []
  const others = mp.others_share_pct ?? 0
  const cap = mp.cap_demand_pct ?? 25
  const margin = d.adequacy.luzon.reserve_margin_pct ?? 0
  const bars = [
    ...firms.map((c) => ({ name: c.name, share: c.share_pct, other: false })),
    { name: 'All other firms', share: others, other: true },
  ]
  const maxShare = Math.max(...bars.map((b) => b.share), cap)

  return (
    <div className="view">
      <Panel
        title="Who owns the fleet"
        subtitle={`ERC national generation-capacity shares, ${mp.as_of}. The merit order prices energy; it cannot show concentration.`}
        right={<Source href={mp.src} label="ERC source" />}
      >
        <div className="stat-row">
          <StatTile
            label="HHI (floor)"
            value={num(mp.hhi_floor)}
            hint={mp.hhi_band}
            tone={(mp.hhi_floor ?? 0) >= 1500 ? 'danger' : 'accent'}
          />
          <StatTile
            label="Two largest, combined"
            value={pct((mp.top2_combined_pct ?? 0) / 100, 0)}
            hint="near half of national capacity"
            tone="accent"
          />
          <StatTile
            label="Largest single firm"
            value={pct((mp.largest?.share_pct ?? 0) / 100, 1)}
            hint={mp.largest?.name}
          />
        </div>
        <div className="mixbars" style={{ marginTop: 'var(--sp-3)' }}>
          {bars.map((b) => (
            <div className="mixbars__row" key={b.name}>
              <span className="mixbars__label">{b.name}</span>
              <span className="mixbars__track">
                <span
                  className={`mixbars__fill${!b.other && b.share > cap ? ' mixbars__fill--over' : b.other ? '' : ' mixbars__fill--spot'}`}
                  style={{ width: `${(b.share / maxShare) * 100}%` }}
                />
              </span>
              <span className="mixbars__val mono">{b.share.toFixed(1)}%</span>
            </div>
          ))}
        </div>
        <p className="note">
          EPIRA caps a single firm at {mp.cap_installed_pct}% of a grid's installed
          capacity and {cap}% of national demand. The largest firm sits at{' '}
          {pct((mp.largest?.share_pct ?? 0) / 100, 1)}, under the cap but approaching it.{' '}
          {mp.note} <Source href={mp.src_cap} label="EPIRA" />
        </p>
      </Panel>

      <Panel
        title="Pivotal supplier"
        subtitle="Is the grid served without its largest generator at the peak?"
      >
        <div className="stat-row">
          <StatTile
            label="Largest firm's capacity share"
            value={pct((mp.largest?.share_pct ?? 0) / 100, 1)}
            tone="danger"
          />
          <StatTile
            label="Luzon reserve margin at peak"
            value={pct(margin / 100, 1)}
            hint="the cushion above peak demand"
          />
        </div>
        <p className="note">{mp.pivotal_supplier_note}</p>
        <p className="note">{mp.rsi_note}</p>
        <p className="note">{mp.disclaimer}</p>
      </Panel>
    </div>
  )
}
