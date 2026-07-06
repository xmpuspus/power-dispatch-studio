import type { Dispatch, GridKey, ReserveCategory, ReserveGridRow } from '../lib/types'
import { num, php, pct, fuelLabel, useReserve } from '../lib/data'
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
        subtitle={`${cap(grid)}: modeled vs observed, sorted high to low over the market window.`}
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
            hint="oversupply, real WESM floor"
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
        subtitle={`${cap(grid)}: share of ${num(mf.n_intervals)} market intervals each block is on the margin.`}
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
        title="Probabilistic reliability"
        subtitle={`${num(mc.draws)} Monte Carlo draws, forced outages at sourced rates. Loss-of-load probability, not a point estimate.`}
        right={<Source href={mc.src_for} label="forced-outage source" />}
      >
        <div className="stat-row">
          <StatTile
            label="LOLP today"
            value={pct(base.lolp_pct / 100, 2)}
            hint="Luzon evening peak"
            tone="positive"
          />
          <StatTile
            label="LOLP with DICT 1.5 GW"
            value={pct(dc.lolp_pct / 100, 2)}
            hint="the data-center wave"
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
        title="Storage buys back the adequacy gap"
        subtitle={`${num(st.assets.luzon.total_mw)} MW on Luzon (${num(st.assets.luzon.bess_mw)} MW batteries, ${num(st.assets.luzon.pumped_hydro_mw)} MW Kalayaan pumped hydro).`}
        right={<Source href={st.src_pumped_hydro} label="pumped-hydro source" />}
      >
        <CompareBars
          items={[
            {
              label: 'DICT-wave loss-of-load probability',
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
        Reserve schedules not baked. Run{' '}
        <code>archive_iemop.py --backfill --only RTDRS --sample-days 3</code> then{' '}
        <code>make data</code>.
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
        title="WESM Reserve Market"
        subtitle={`Live since ${res.commercial_since}. Real-time dispatch co-optimises energy and reserves; the studio's merit order clears energy only. Sample of ${num(res.n_intervals)} intervals over ${res.sample_days?.join(', ')}.`}
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
          The dearest reserve products clear well above the energy coal margin. A unit
          holding reserve cannot also sell that MW as energy, so this cost is real and the
          energy-only stack cannot see it. These are the operator's own published reserve
          clearing prices, not a model output. <Source href={res.src_data} label="data" />
        </p>
        {res.mapping_note && <p className="note">* {res.mapping_note}</p>}
      </Panel>

      {dearest && (
        <Panel
          title="Reserve versus energy"
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
              {php(res.reserve_cap_php_kwh)} reserve cap: scarcity prices reserve and
              energy together. {res.disclaimer}
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
    </div>
  )
}
