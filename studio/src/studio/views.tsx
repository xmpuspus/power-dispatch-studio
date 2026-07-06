import type { Dispatch, GridKey } from '../lib/types'
import { num, php, pct, fuelLabel } from '../lib/data'
import { Panel, StatTile, Chip, Source, EmptyNote } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'
import { MeritStack, DurationCurve, ShareBars, FlowDiagram, CompareBars } from './charts'

const cap = (g: string) => g[0].toUpperCase() + g.slice(1)

export function MeritView({ d, grid }: { d: Dispatch; grid: GridKey }) {
  const mo = d.merit_order[grid]
  const cal = d.calibration[grid]
  const uc = d.unit_commitment.per_grid[grid]
  return (
    <div className="view">
      <div className="stat-row">
        <StatTile label="Installed" value={num(mo.installed_mw)} unit="MW" />
        <StatTile label="Available at peak" value={num(mo.avail_mw)} unit="MW" />
        <StatTile
          label="Typical evening"
          value={num(mo.typical_evening_demand_mw)}
          unit="MW"
        />
        <StatTile
          label="Modeled vs observed"
          value={php(cal.modeled_mean_php_kwh)}
          hint={`observed ${php(cal.observed_mean_php_kwh)}`}
        />
      </div>
      <Panel
        title="Merit-order supply stack"
        subtitle={`${cap(grid)}, evening reference hour. Blocks by marginal cost against the demand cursor.`}
      >
        <MeritStack blocks={mo.blocks} demand={mo.typical_evening_demand_mw} />
        <LegendFromBlocks blocks={mo.blocks.map((b) => b.fuel)} />
      </Panel>
      <Panel
        title="Unit commitment (before / after)"
        subtitle="Committed baseload coal offers below the administered price at light load. Sourced, not tuned to the trough."
        right={<Source href={d.unit_commitment.src_offer} label="offer source" />}
      >
        <div className="stat-row">
          <StatTile
            label="MAE"
            value={php(uc.mae_after_php_kwh)}
            hint={`was ${php(uc.mae_before_php_kwh)}`}
            tone="positive"
          />
          <StatTile
            label="Correlation"
            value={uc.correlation_after == null ? '-' : uc.correlation_after.toFixed(2)}
            hint={`was ${uc.correlation_before == null ? 'flat' : uc.correlation_before.toFixed(2)}`}
            tone="positive"
          />
          <StatTile
            label="Evening residual"
            value={php(cal.evening_peak_residual_php_kwh)}
            hint="scarcity, preserved"
            tone="accent"
          />
        </div>
        <p className="note">{d.unit_commitment.note}</p>
      </Panel>
    </div>
  )
}

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

export function FlowsView({ d }: { d: Dispatch }) {
  const c = d.coupling
  const sd = c.spread_decomposition
  const os = c.outage_scenario
  const prices: Record<string, number | null> = {
    luzon: c.per_grid.luzon.coupled_modeled_mean_php_kwh,
    visayas: c.per_grid.visayas.coupled_modeled_mean_php_kwh,
    mindanao: c.per_grid.mindanao.coupled_modeled_mean_php_kwh,
  }
  const corridors = c.corridors.map((cor) => ({
    from: cor.id === 'leyte_luzon_hvdc' ? 'luzon' : 'visayas',
    to: cor.id === 'leyte_luzon_hvdc' ? 'visayas' : 'mindanao',
    flow_mw: cor.mean_abs_flow_mw,
    saturated: (cor.saturated_pct ?? 0) > 5,
    rent: cor.mean_congestion_rent_php_kwh,
  }))
  return (
    <div className="view">
      <Panel
        title="Inter-island coupled dispatch"
        subtitle="Cheap Luzon energy flows south over the HVDC links up to their operating limits. Mean coupled prices shown."
      >
        <FlowDiagram prices={prices} corridors={corridors} />
        <div className="corridor-row">
          {c.corridors.map((cor) => (
            <div className="corridor" key={cor.id}>
              <div className="corridor__name">
                {cor.name} <Chip tone="default">{cor.limit_mw} MW</Chip>
              </div>
              <div className="corridor__meta mono">
                bound {pct((cor.saturated_pct ?? 0) / 100, 1)} of intervals · rent{' '}
                {php(cor.mean_congestion_rent_php_kwh)}
              </div>
              <div className="corridor__kind">
                {cor.limit_kind.replace(/_/g, ' ')} <Source href={cor.src} />
              </div>
            </div>
          ))}
        </div>
      </Panel>
      <Panel title="How much of the spread the corridor explains" subtitle={sd.note}>
        <div className="stat-row">
          <StatTile
            label="Observed Visayas − Luzon"
            value={php(sd.visayas_vs_luzon.observed_php_kwh)}
          />
          <StatTile
            label="Coupled model reproduces"
            value={pct(sd.visayas_vs_luzon.explained_fraction, 0)}
            hint="at baseline demand"
            tone="accent"
          />
        </div>
        <p className="note">
          At baseline the islands sit on the coal margin, so the link barely binds and
          coupling explains almost none of the spread. The spread is scarcity during the
          52-day streak, not transmission.
        </p>
      </Panel>
      <Panel
        title="The mechanism, under the documented outage"
        subtitle={os.label}
        right={<Source href={os.src} />}
      >
        <div className="stat-row">
          <StatTile
            label="Leyte-Luzon bound"
            value={pct((os.leyte_luzon_saturated_pct ?? 0) / 100, 1)}
            tone="danger"
          />
          <StatTile
            label="Congestion rent"
            value={php(os.leyte_luzon_mean_rent_php_kwh)}
            tone="danger"
          />
          <StatTile
            label="Spread explained"
            value={pct(os.explained_fraction, 0)}
            tone="accent"
          />
          <StatTile
            label="Load to bind the link"
            value={num(c.dc_binding_threshold.added_visayas_load_to_bind_leyte_mw)}
            unit="MW"
            hint="added Visayas load, typical evening"
          />
        </div>
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

export function N1View({ d, grid }: { d: Dispatch; grid: GridKey }) {
  const rows = d.n1.filter((n) => n.grid === grid)
  const cols: Column<(typeof rows)[number]>[] = [
    { key: 'unit', header: 'Unit', render: (r) => r.unit },
    { key: 'fuel', header: 'Fuel', render: (r) => fuelLabel(r.fuel) },
    {
      key: 'cap',
      header: 'MW',
      align: 'right',
      mono: true,
      render: (r) => num(r.capacity_mw),
    },
    {
      key: 'price',
      header: 'Evening price',
      align: 'right',
      mono: true,
      render: (r) =>
        `${php(r.base_price_php_kwh, 0)} → ${php(r.tripped_price_php_kwh, 0)}`,
    },
    {
      key: 'shed',
      header: 'Shed at peak',
      align: 'right',
      mono: true,
      render: (r) => num(r.shortfall_at_peak_mw),
    },
  ]
  return (
    <div className="view">
      <Panel
        title={`Generators on ${cap(grid)}`}
        subtitle="Trip each named unit (N-1) and read the price move and the shortfall at the annual peak."
      >
        <DataGrid
          columns={cols}
          rows={rows}
          getKey={(r) => r.unit}
          empty="No named generators on this grid."
        />
      </Panel>
    </div>
  )
}

export function RegionsView({ d }: { d: Dispatch }) {
  const grids: GridKey[] = ['luzon', 'visayas', 'mindanao']
  const cols: Column<GridKey>[] = [
    { key: 'g', header: 'Region', render: (g) => cap(g) },
    {
      key: 'inst',
      header: 'Installed MW',
      align: 'right',
      mono: true,
      render: (g) => num(d.adequacy[g].installed_mw),
    },
    {
      key: 'peak',
      header: 'Peak MW',
      align: 'right',
      mono: true,
      render: (g) => num(d.adequacy[g].peak_demand_mw),
    },
    {
      key: 'rm',
      header: 'Reserve margin',
      align: 'right',
      mono: true,
      render: (g) => pct((d.adequacy[g].reserve_margin_pct ?? 0) / 100, 1),
    },
    {
      key: 'obs',
      header: 'Observed price',
      align: 'right',
      mono: true,
      render: (g) => php(d.calibration[g].observed_mean_php_kwh),
    },
  ]
  return (
    <div className="view">
      <Panel
        title="Regions"
        subtitle="Adequacy and the observed market-window price by grid."
      >
        <DataGrid columns={cols} rows={grids} getKey={(g) => g} />
      </Panel>
    </div>
  )
}

export function InterfacesView({ d }: { d: Dispatch }) {
  const cols: Column<(typeof d.coupling.corridors)[number]>[] = [
    { key: 'name', header: 'Interface', render: (c) => c.name },
    {
      key: 'limit',
      header: 'Limit MW',
      align: 'right',
      mono: true,
      render: (c) => num(c.limit_mw),
    },
    {
      key: 'kind',
      header: 'Limit basis',
      render: (c) => c.limit_kind.replace(/_/g, ' '),
    },
    {
      key: 'sat',
      header: 'Bound %',
      align: 'right',
      mono: true,
      render: (c) => pct((c.saturated_pct ?? 0) / 100, 1),
    },
    {
      key: 'flow',
      header: 'Mean flow MW',
      align: 'right',
      mono: true,
      render: (c) => num(c.mean_abs_flow_mw),
    },
  ]
  return (
    <div className="view">
      <Panel
        title="Interfaces (HVDC corridors)"
        subtitle="The two links that couple the grids, with how often each binds."
      >
        <DataGrid columns={cols} rows={d.coupling.corridors} getKey={(c) => c.id} />
      </Panel>
    </div>
  )
}

function LegendFromBlocks({ blocks }: { blocks: string[] }) {
  const seen = [...new Set(blocks)]
  const color: Record<string, string> = {
    coal: 'var(--fuel-coal)',
    oil: 'var(--fuel-oil)',
    natural_gas: 'var(--fuel-gas)',
    hydro: 'var(--fuel-hydro)',
    geothermal: 'var(--fuel-geothermal)',
    solar: 'var(--fuel-solar)',
    wind: 'var(--series-flow)',
    biomass: 'var(--positive)',
  }
  return (
    <div className="legend legend--wrap">
      {seen.map((f) => (
        <span className="legend__item" key={f}>
          <i style={{ background: color[f] ?? 'var(--text-faint)' }} />
          {fuelLabel(f)}
        </span>
      ))}
    </div>
  )
}
