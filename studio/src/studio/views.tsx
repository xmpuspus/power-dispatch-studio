import type { Dispatch, GridKey, ReserveCategory, ReserveGridRow } from '../lib/types'
import { num, php, pct, fuelLabel, useMarketOps, useReserve } from '../lib/data'
import { Panel, StatTile, Source, EmptyNote } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'
import { DurationCurve, ShareBars, CompareBars } from './charts'

const cap = (g: string) => g[0].toUpperCase() + g.slice(1)

export function DurationView({ d, grid }: { d: Dispatch; grid: GridKey }) {
  const pd = d.price_duration[grid]
  if (!pd) return <EmptyNote>No duration curve for this grid.</EmptyNote>
  return (
    <div className="view">
      <Panel
        title="Price-duration curve"
        subtitle={`${cap(grid)} modeled and recorded prices, sorted from highest to lowest over the market window.`}
        right={<Source href={pd.src} label="cap source" />}
      >
        <div className="legend">
          <span className="legend__item">
            <i style={{ background: 'var(--series-modeled)' }} />
            modeled
          </span>
          <span className="legend__item">
            <i style={{ background: 'var(--series-observed)' }} />
            observed
          </span>
        </div>
        <DurationCurve modeled={pd.modeled} observed={pd.observed} />
        <div className="stat-row">
          <StatTile
            label="Observed peak"
            value={php(pd.observed_max_php_kwh)}
            hint="scarcity + congestion"
            tone="danger"
          />
          <StatTile
            label="Observed floor"
            value={php(pd.observed_min_php_kwh)}
            hint="recorded WESM floor during oversupply"
          />
        </div>
        <p className="note">{pd.note}</p>
      </Panel>
    </div>
  )
}

export function MarginalView({ d, grid }: { d: Dispatch; grid: GridKey }) {
  const mf = d.marginal_frequency[grid]
  if (!mf) return <EmptyNote>No marginal-block data for this grid.</EmptyNote>
  return (
    <div className="view">
      <Panel
        title="Who sets the price"
        subtitle={`${cap(grid)} share of ${num(mf.n_intervals)} market intervals in which each fuel block sets the price.`}
      >
        <ShareBars rows={mf.by_block} />
        <p className="note">
          Block dispatch cannot name the individual plant, so this is at the fuel level.
          Coal splits into its committed (overnight) and marginal (peak) tranches.
        </p>
      </Panel>
    </div>
  )
}

export function ReliabilityView({ d }: { d: Dispatch }) {
  const mc = d.reliability_mc
  const st = d.storage
  const base = mc.per_grid.luzon
  const dc = mc.dict_2028_luzon.distribution
  const bk = st.reliability_buyback.luzon_dict_2028
  return (
    <div className="view">
      <Panel
        title="Chance that available supply cannot meet evening demand"
        subtitle={`${num(mc.draws)} repeated simulations apply random plant outages at sourced rates. The result is loss-of-load probability (LOLP), not one predicted outcome.`}
        right={<Source href={mc.src_for} label="plant-outage source" />}
      >
        <div className="stat-row">
          <StatTile
            label="Current shortfall chance (LOLP)"
            value={pct(base.lolp_pct / 100, 2)}
            hint="Luzon evening peak"
            tone="positive"
          />
          <StatTile
            label="Shortfall chance with DICT 1.5 GW (LOLP)"
            value={pct(dc.lolp_pct / 100, 2)}
            hint="with the announced added demand"
            tone="danger"
          />
          <StatTile
            label="1-in-100 shortfall"
            value={num(dc.shortfall_mw_p99)}
            unit="MW"
            tone="danger"
          />
        </div>
        <p className="note">{mc.note}</p>
      </Panel>
      <Panel
        title="Storage reduces the modeled shortfall risk"
        subtitle={`${num(st.assets.luzon.total_mw)} MW on Luzon (${num(st.assets.luzon.bess_mw)} MW batteries, ${num(st.assets.luzon.pumped_hydro_mw)} MW Kalayaan pumped hydro).`}
        right={<Source href={st.src_pumped_hydro} label="pumped-hydro source" />}
      >
        <CompareBars
          items={[
            {
              label: 'Shortfall probability with DICT demand',
              a: bk.without.lolp_pct,
              b: bk.with_storage.lolp_pct,
              aLabel: 'without storage',
              bLabel: 'with storage',
            },
          ]}
        />
        <div className="stat-row">
          <StatTile
            label="Tight-evening peak, without"
            value={php(st.dict_wave_peak_price.without_storage_php_kwh)}
            hint={fuelLabel(st.dict_wave_peak_price.without_storage_marginal_fuel)}
            tone="danger"
          />
          <StatTile
            label="With storage"
            value={php(st.dict_wave_peak_price.with_storage_php_kwh)}
            hint={fuelLabel(st.dict_wave_peak_price.with_storage_marginal_fuel)}
            tone="positive"
          />
        </div>
        <p className="note">{st.note}</p>
      </Panel>
    </div>
  )
}

export function ReserveView({ d, grid }: { d: Dispatch; grid: GridKey }) {
  const r = useReserve()
  if (r.loading) return <EmptyNote>Loading the reserve market.</EmptyNote>
  if (r.error || !r.data?.available)
    return (
      <EmptyNote>
        Recorded reserve schedules are not available in this data release.
      </EmptyNote>
    )
  const res = r.data
  const cats: ReserveCategory[] = res.categories ?? []
  const gridRows: ReserveGridRow[] = res.by_grid?.[grid] ?? []
  const energy = d.calibration[grid].observed_mean_php_kwh
  const dearest = cats[0]
  const cols: Column<ReserveGridRow>[] = [
    { key: 'label', header: 'Reserve product', render: (x) => x.label },
    {
      key: 'price',
      header: 'Mean clearing price',
      align: 'right',
      mono: true,
      render: (x) => php(x.mean_php_kwh),
    },
    {
      key: 'mw',
      header: 'Mean scheduled MW',
      align: 'right',
      mono: true,
      render: (x) => num(x.mean_mw),
    },
  ]
  return (
    <div className="view">
      <Panel
        title="WESM backup-capacity market (reserves)"
        subtitle={`Operating since ${res.commercial_since}. Real-time dispatch buys energy and reserve capacity together. The studio's Hourly market replay holds the scheduled reserve requirement out of the energy supply stack but does not calculate reserve prices. The sample covers ${num(res.n_intervals)} intervals on ${res.sample_days?.join(', ')}.`}
        right={<Source href={res.src_market} label="market source" />}
      >
        <div className="stat-row">
          {cats.map((c) => (
            <StatTile
              key={c.code}
              label={c.code_mapping === 'inferred' ? c.label + ' *' : c.label}
              value={php(c.mean_php_kwh)}
              hint={`${num(c.mean_system_mw)} MW · at cap ${pct(c.cap_hit_pct / 100, 0)} of the time`}
              tone={c.mean_php_kwh > energy ? 'danger' : 'default'}
            />
          ))}
        </div>
        <p className="note">
          The highest-priced reserve products clear above the price-setting coal energy
          block. A plant holding MW in reserve cannot sell the same MW as energy, so an
          energy-only supply stack misses this cost. These are the operator's published
          reserve clearing prices, not model results.{' '}
          <Source href={res.src_data} label="source data" />
        </p>
        {res.mapping_note && <p className="note">* {res.mapping_note}</p>}
      </Panel>

      {dearest && (
        <Panel
          title="Backup-capacity price compared with the energy price"
          subtitle={`${dearest.label} is the scarcest product. Compared with the observed energy clearing price on ${cap(grid)}.`}
        >
          <CompareBars
            unit=""
            dp={2}
            items={[
              {
                label: 'Clearing price, PhP/kWh',
                a: dearest.mean_php_kwh,
                b: energy ?? 0,
                aLabel: dearest.label + ' reserve',
                bLabel: 'energy (observed mean)',
              },
            ]}
          />
          {res.scarcity && (
            <p className="note">
              In the tightest tenth of intervals the {res.scarcity.label.toLowerCase()}{' '}
              reserve price averages {php(res.scarcity.top_decile_mean_php_kwh)}, near the{' '}
              {php(res.reserve_cap_php_kwh)} reserve price cap. Scarcity raises reserve
              and energy prices together. {res.disclaimer}
            </p>
          )}
        </Panel>
      )}

      <Panel
        title={`Reserve clearing prices on ${cap(grid)}`}
        subtitle="Mean price and scheduled quantity per reserve product for this grid."
      >
        <DataGrid
          columns={cols}
          rows={gridRows}
          getKey={(x) => x.code}
          empty="No reserve rows for this grid in the sample."
        />
      </Panel>

      <OfficialReservePrices grid={grid} />
      <ReserveValidation grid={grid} />
      <ReserveAware grid={grid} />
    </div>
  )
}

/** Show the observed energy price beside calculated and operator-set reserve prices. */
function ReserveAware({ grid }: { grid: GridKey }) {
  const mo = useMarketOps()
  const ra = mo.data?.reserve_aware
  const v = ra?.by_grid?.[grid]
  if (!ra?.available || !v) return null
  return (
    <Panel
      title={`Combined energy and reserve price on ${cap(grid)}`}
      subtitle="Energy and reserve capacity are bought together. Capacity held in reserve cannot be sold as energy at the same time."
    >
      <div className="stat-row">
        <StatTile label="Energy" value={php(v.energy_php_kwh)} hint="observed mean" />
        <StatTile
          label="Reserve from published offers"
          value={php(v.reserve_offer_clear_php_kwh)}
          hint="when reserve requirements are met"
        />
        <StatTile
          label="Operator-set scarcity addition"
          value={php(v.reserve_scarcity_wedge_php_kwh)}
          hint="when scheduled reserve is short"
        />
        <StatTile
          label="Energy plus reserve"
          value={php(v.reserve_aware_php_kwh)}
          hint="energy + reserve"
          tone="accent"
        />
      </div>
      <p className="note">
        The reserve price has two parts. The first comes from the published reserve offers
        and matches the official regional reserve price when requirements are met. The
        second is an operator-set scarcity addition when scheduled reserve falls short.
        That addition is not present in the public offers and is shown separately.
        {ra.note ? '' : ''}
      </p>
    </Panel>
  )
}

const RESERVE_LABEL: Record<string, string> = {
  Fr: 'Contingency reserve (Fr)',
  Dr: 'Dispatchable reserve (Dr)',
  Ru: 'Regulation up (Ru)',
  Rd: 'Regulation down (Rd)',
}

/** Show the operator's published regional reserve prices over the archive window. */
function OfficialReservePrices({ grid }: { grid: GridKey }) {
  const mo = useMarketOps()
  const rp = mo.data?.reserve_prices
  if (mo.loading || !rp?.available || !rp.stats?.[grid]) return null
  const rows = Object.entries(rp.stats[grid]!).sort((a, b) => b[1].mean - a[1].mean)
  return (
    <Panel
      title={`Official regional reserve prices, ${cap(grid)}`}
      subtitle={`IEMOP's published prices over ${rp.dates?.length ?? 0} archive days. Plain product names are inferred because IEMOP publishes the codes without a key.`}
      right={<Source href={rp.src} label="source data" />}
    >
      <DataGrid
        columns={[
          {
            key: 'code',
            header: 'Reserve product (inferred)',
            render: (x) => RESERVE_LABEL[x[0]] ?? x[0],
          },
          {
            key: 'mean',
            header: 'Window mean',
            align: 'right',
            mono: true,
            render: (x) => php(x[1].mean),
          },
          {
            key: 'max',
            header: 'Dearest daily mean',
            align: 'right',
            mono: true,
            render: (x) => php(x[1].max),
          },
        ]}
        rows={rows}
        getKey={(x) => x[0]}
        empty="No official series for this grid yet."
      />
      <p className="note">{rp.commodity_note}</p>
    </Panel>
  )
}

/** Compare prices calculated from offers with the operator's published prices. */
function ReserveValidation({ grid }: { grid: GridKey }) {
  const mo = useMarketOps()
  const rv = mo.data?.reserve_validation
  const rr = mo.data?.reserve_results
  if (mo.loading || !rv?.available || !rv.pools?.[grid]) return null
  const pool = rv.pools[grid]!
  const rrPool = rr?.pools?.[grid]
  const rows = ['Fr', 'Dr', 'Ru', 'Rd']
    .filter((c) => pool[c])
    .map((c) => ({ c, v: pool[c]!, f: rrPool?.[c] }))
  return (
    <Panel
      title={`Published reserve prices exceed the offer-book calculation on average, ${cap(grid)}`}
      subtitle={`The calculation uses the first 5-minute reserve offers of each hour and the operator's scheduled capacity over ${rv.days ?? 0} days.${rr?.available ? ` Final plant-level results cover ${rr.resources_named ?? 0} resources.` : ''} Source files: RTDOR offers, RSVPR regional prices, and DIPCRF final results.`}
      right={<Source href={rv.src} label="data" />}
    >
      <DataGrid
        columns={[
          {
            key: 'product',
            header: 'Reserve product',
            render: (x) => RESERVE_LABEL[x.c] ?? x.c,
          },
          {
            key: 'obs',
            header: 'Published mean',
            align: 'right',
            mono: true,
            render: (x) => php(x.v.observed_mean_php_kwh),
          },
          {
            key: 'mod',
            header: 'Calculated from offers',
            align: 'right',
            mono: true,
            render: (x) => php(x.v.modeled_mean_php_kwh),
          },
          {
            key: 'wedge',
            header: 'Average difference',
            align: 'right',
            mono: true,
            render: (x) => php(x.v.bias_php_kwh),
          },
          {
            key: 'final',
            header: 'Difference from final results',
            align: 'right',
            mono: true,
            render: (x) =>
              x.f?.replay_vs_final ? php(x.f.replay_vs_final.bias_php_kwh) : 'n/a',
          },
        ]}
        rows={rows}
        getKey={(x) => x.c}
        empty="No reserve replay for this grid yet."
      />
      <p className="note">{rv.wedge_note}</p>
    </Panel>
  )
}
