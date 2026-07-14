import { useMemo, useState } from 'react'
import type { Dispatch, GridKey } from '../lib/types'
import { fuelLabel, num, php, useEmissions, useGenerators } from '../lib/data'
import { Panel, StatTile, Chip, EmptyNote } from '../ui/kit'
import { MeritStack, FlowDiagram } from './charts'
import { buildTemplateCsv, type ImportResult } from './importData'
import { initLevers } from './levers'
import { downloadCsv } from './runs'
import { solveScenario, type Levers, type TrippableUnit } from './engine'
import {
  CARBON_DISCLAIMER,
  CARBON_FUEL_ID,
  CARBON_PROP,
  GAS_FUEL_ID,
  GAS_PROP,
  GAS_SOURCE_NOTE,
  carbonCostDelta,
  carbonPriceOf,
  gasSupplyPctOf,
  type ClassId,
  type ObjRow,
  type Overrides,
} from './model'

const cap = (g: string) => g[0].toUpperCase() + g.slice(1)

export function ScenarioView({
  d,
  grid,
  objects,
  overrides,
  onEdit,
  onRevert,
  onImportCsv,
  importedKeys,
}: {
  d: Dispatch
  grid: GridKey
  objects: Record<ClassId, ObjRow[]>
  overrides: Overrides
  onEdit: (cls: ClassId, id: string, prop: string, value: number) => void
  onRevert: (cls: ClassId, id: string, prop: string) => void
  onImportCsv?: (text: string) => ImportResult
  importedKeys?: string[]
}) {
  const gens = useGenerators()
  const em = useEmissions()
  const [lv, setLv] = useState<Levers>(() => initLevers(d, grid))

  // reset the levers when the grid changes (levers are grid-scoped)
  const [lastGrid, setLastGrid] = useState<GridKey>(grid)
  if (grid !== lastGrid) {
    setLastGrid(grid)
    setLv(initLevers(d, grid))
  }

  const units: TrippableUnit[] = useMemo(
    () =>
      (gens.data?.features ?? []).map((f) => ({
        name: f.properties.name,
        grid: f.properties.grid,
        fuel: f.properties.fuel,
        capacity_mw: f.properties.capacity_mw,
      })),
    [gens.data]
  )
  const gridUnits = units
    .filter((u) => u.grid.toLowerCase() === grid)
    .sort((a, b) => b.capacity_mw - a.capacity_mw)

  const out = useMemo(() => solveScenario(d, lv, units), [d, lv, units])
  const mo = d.merit_order[grid]
  const set = (patch: Partial<Levers>) => setLv((p) => ({ ...p, ...patch }))

  const hy = d.assumptions.hydrology
  const hydroOpts = [
    { key: 'dry', label: 'Dry (El Nino)', mult: hy.dry_multiplier },
    { key: 'normal', label: 'Normal', mult: hy.normal_multiplier },
    { key: 'wet', label: 'Wet', mult: hy.wet_multiplier },
  ]

  const delta = out.single.price - out.base.price
  const feedName =
    out.feed === 'mvip' ? 'MVIP (from Visayas)' : 'Leyte-Luzon (from Luzon)'
  const feedCor = out.feed ? out.coupled[out.feed] : null

  const prices: Record<string, number | null> = {
    luzon: out.coupled.price.luzon,
    visayas: out.coupled.price.visayas,
    mindanao: out.coupled.price.mindanao,
  }
  const corridors = [
    {
      from: 'luzon',
      to: 'visayas',
      flow_mw: out.coupled.leyte.flow,
      saturated: out.coupled.leyte.sat,
      rent: out.coupled.leyte.rent,
    },
    {
      from: 'visayas',
      to: 'mindanao',
      flow_mw: out.coupled.mvip.flow,
      saturated: out.coupled.mvip.sat,
      rent: out.coupled.mvip.rent,
    },
  ]

  const coalFloor = d.assumptions.coal_commit_php_kwh
  const storageOnGrid = grid === 'luzon' ? d.storage.assets.luzon.total_mw : 0

  // carbon price lever: a synthetic scenario override, not a real object, so
  // it survives a remount. Writes each carbon-emitting fuel's Price directly,
  // the SAME override chronoOptsFrom already folds into opts.fuel_cost, so
  // every chronological view (Chronology, Emissions, Runs, reports) that
  // reads this scenario's overrides inherits the effect with no extra wiring.
  const factors = em.data?.factor_map ?? {}
  const carbonPrice = carbonPriceOf(overrides)
  const carbonRows = objects.fuel
    .map((f) => ({ fuel: f.id, delta: carbonCostDelta(carbonPrice, factors[f.id]) }))
    .filter((r) => r.delta > 0)
  const gasSupplyPct = gasSupplyPctOf(overrides)
  const setGasSupply = (v: number) => {
    const p = Math.round(v)
    if (p < 100) onEdit('fuel', GAS_FUEL_ID, GAS_PROP, p)
    else onRevert('fuel', GAS_FUEL_ID, GAS_PROP)
  }

  const setCarbonPrice = (v: number) => {
    const cp = Math.max(0, Math.round(v))
    if (cp > 0) onEdit('fuel', CARBON_FUEL_ID, CARBON_PROP, cp)
    else onRevert('fuel', CARBON_FUEL_ID, CARBON_PROP)
    // only ever touches fuels with a nonzero baked factor, so a manual edit to
    // a zero-carbon fuel's price (solar, wind, hydro, storage) is never
    // clobbered; a manual edit to coal/gas/oil/geo price IS overwritten while
    // this lever is nonzero, since both share the one Price override slot
    for (const f of objects.fuel) {
      const factor = factors[f.id]
      if (!factor) continue
      const delta = carbonCostDelta(cp, factor)
      const base = f.props.cost as number
      if (delta > 0)
        onEdit('fuel', f.id, 'cost', Math.round((base + delta) * 1000) / 1000)
      else onRevert('fuel', f.id, 'cost')
    }
  }
  const [importMsg, setImportMsg] = useState<string>('')
  const onImportFile = (file: File | undefined) => {
    if (!file || !onImportCsv) return
    const reader = new FileReader()
    reader.onload = () => {
      const res: ImportResult = onImportCsv(String(reader.result ?? ''))
      const parts = [`Imported ${res.matched} value${res.matched === 1 ? '' : 's'}.`]
      if (res.skipped.length) parts.push(`No object matched: ${res.skipped.join(', ')}.`)
      if (res.warnings.length) parts.push(res.warnings.join(' '))
      setImportMsg(parts.join(' '))
    }
    reader.onerror = () => setImportMsg('Could not read that file.')
    reader.readAsText(file)
  }

  const resetLevers = () => {
    setLv(initLevers(d, grid))
    setCarbonPrice(0)
  }

  return (
    <div className="view" data-testid="scenario">
      <p className="scn__lede">
        A merit-order model, <b>not a full production-cost suite</b>: it stacks the
        sourced fleet by marginal cost against demand and clears the three grids as one
        HiGHS linear program, here in your browser, on the same stack the pipeline baked
        and against the same LP its Python engine solves. Prices are locational marginals
        from the solve. It is calibrated against observed prices, not a predictor of them.
      </p>

      <div className="scn">
        <Panel
          title="Levers"
          subtitle={`${cap(grid)}, evening reference hour ${mo.reference_hour}:00.`}
        >
          <div className="levers">
            <Slider
              label="Add a data center (flat 24/7 load)"
              value={lv.addDC}
              min={0}
              max={4000}
              step={50}
              tick="DICT 2028 forecast: 1,500 MW"
              onChange={(v) => set({ addDC: v })}
            />
            <Slider
              label="Add solar"
              value={lv.addSolar}
              min={0}
              max={4000}
              step={100}
              tick={`delivers ${num(out.solarDeliveredMW)} MW now, ${num(out.solarMiddayMW)} MW at midday`}
              onChange={(v) => set({ addSolar: v })}
            />
            <Slider
              label="Add gas"
              value={lv.addGas}
              min={0}
              max={3000}
              step={50}
              tick={`firm, at ₱${d.assumptions.fuel_marginal_cost_php_kwh.natural_gas.toFixed(2)}/kWh`}
              onChange={(v) => set({ addGas: v })}
            />
            <Slider
              label="Add coal"
              value={lv.addCoal}
              min={0}
              max={3000}
              step={50}
              tick={`firm, at the coal price below`}
              onChange={(v) => set({ addCoal: v })}
            />
            <Slider
              label="Discharge storage at the peak"
              value={lv.addStorage}
              min={0}
              max={2000}
              step={50}
              tick={
                grid === 'luzon'
                  ? `Luzon has ${num(storageOnGrid)} MW today`
                  : 'no grid-scale storage sourced here yet'
              }
              onChange={(v) => set({ addStorage: v })}
            />
            <Slider
              label="Administered coal price (marginal tranche)"
              value={lv.coalPrice}
              min={coalFloor}
              max={12}
              step={0.25}
              fmt={(v) => `₱${v.toFixed(2)}`}
              tick={`committed tranche stays at ₱${coalFloor.toFixed(2)}`}
              onChange={(v) => set({ coalPrice: v })}
            />
            {out.feed && (
              <Slider
                label={`Relieve the feeding corridor (${feedName})`}
                value={lv.reliefMW}
                min={0}
                max={500}
                step={25}
                tick="extra operating limit on the HVDC link"
                onChange={(v) => set({ reliefMW: v })}
              />
            )}
            <label className="lever lever--check">
              <input
                type="checkbox"
                checked={lv.lngSwitch}
                onChange={(e) => set({ lngSwitch: e.target.checked })}
              />
              <span>
                <span className="lever__label">Switch gas to imported LNG</span>
                <span className="lever__tick">
                  Malampaya depletes around 2027; gas reprices from ₱
                  {d.assumptions.fuel_marginal_cost_php_kwh.natural_gas.toFixed(2)} to ₱
                  {d.assumptions.fuel_marginal_cost_php_kwh.lng.toFixed(2)}/kWh
                </span>
              </span>
            </label>
            <div className="lever">
              <span className="lever__label">Hydrology (wet / dry year)</span>
              <span className="lever__tick">
                dry reproduces the DOE 2024 El Nino hydro availability (
                {num(hy.dry_avail_mw_national)} MW nationally)
              </span>
              <div className="gselrow">
                {hydroOpts.map((o) => (
                  <button
                    key={o.key}
                    className={`gsel${Math.abs(lv.hydrology - o.mult) < 1e-6 ? ' on' : ''}`}
                    onClick={() => set({ hydrology: o.mult })}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            </div>
            <label className="lever">
              <span className="lever__label">Trip a unit (N-1)</span>
              <select
                className="lever__select"
                value={lv.trip}
                onChange={(e) => set({ trip: e.target.value })}
              >
                <option value="">none (all units running)</option>
                {gridUnits.map((u) => (
                  <option key={u.name} value={u.name}>
                    {u.name} (-{num(u.capacity_mw)} MW {fuelLabel(u.fuel)})
                  </option>
                ))}
              </select>
            </label>
            <Slider
              label="Carbon price, system-wide"
              value={carbonPrice}
              min={0}
              max={5000}
              step={250}
              fmt={(v) => `₱${num(v)}/tCO2`}
              tick={`${CARBON_DISCLAIMER}. Raises each carbon-emitting fuel's Price by carbon price times its baked tCO2/MWh factor, divided by 1000, so higher-carbon fuels climb the merit order.`}
              onChange={setCarbonPrice}
            />
            {carbonRows.length > 0 && (
              <p className="note">
                Applies now, Fuels &gt; Price:{' '}
                {carbonRows
                  .map((r) => `${fuelLabel(r.fuel)} +₱${r.delta.toFixed(2)}/kWh`)
                  .join(', ')}
                .
              </p>
            )}
            <Slider
              label="Malampaya gas supply"
              value={gasSupplyPct}
              min={0}
              max={100}
              step={5}
              fmt={(v) => `${v}%`}
              tick={`${GAS_SOURCE_NOTE}. Caps the gas fleet's daily energy to this percent of its flat-out day, a fuel budget applied in the chronology (the Malampaya supply cliff what-if).`}
              onChange={setGasSupply}
            />
            <button className="btn btn--ghost lever__reset" onClick={resetLevers}>
              Reset levers
            </button>
            {onImportCsv && (
              <div className="byo">
                <div className="byo__head">Bring your own data</div>
                <p className="note">
                  Load a CSV of your own unit parameters (dependable MW, fuel price,
                  forced outage), region load, or corridor limits. It stays in this
                  browser and is never uploaded. Imported values are labeled user-supplied
                  everywhere.
                </p>
                <div className="byo__actions">
                  <label className="btn btn--ghost btn--sm">
                    Import CSV
                    <input
                      type="file"
                      accept="text/csv,.csv"
                      style={{ display: 'none' }}
                      onChange={(e) => {
                        onImportFile(e.target.files?.[0])
                        e.target.value = ''
                      }}
                    />
                  </label>
                  <button
                    className="btn btn--ghost btn--sm"
                    onClick={() =>
                      downloadCsv(
                        'power-dispatch-import-template.csv',
                        buildTemplateCsv()
                      )
                    }
                  >
                    Download template
                  </button>
                  {importedKeys && importedKeys.length > 0 && (
                    <span className="byo__badge">
                      {importedKeys.length} user-supplied value
                      {importedKeys.length === 1 ? '' : 's'} active
                    </span>
                  )}
                </div>
                {importMsg && <p className="byo__msg note">{importMsg}</p>}
                <p className="note">
                  Full hourly load shapes and hydro inflow series are consumed by the
                  baked chronology, not these per-object overrides, so they are out of
                  this import.
                </p>
              </div>
            )}
          </div>
        </Panel>

        <div className="scn__results">
          <Panel
            title="Clearing price"
            subtitle="The selected grid, cleared on its own stack."
          >
            <div className="stat-row">
              <StatTile
                label="Clearing price"
                value={php(out.single.price)}
                hint={out.single.marginal ? fuelLabel(out.single.marginal) : 'unserved'}
                tone={out.single.shortfall > 0 ? 'danger' : 'default'}
              />
              <StatTile
                label="vs base case"
                value={`${delta >= 0 ? '+' : ''}${php(delta)}`}
                hint={`base ${php(out.base.price)}`}
                tone={delta > 0.001 ? 'accent' : delta < -0.001 ? 'positive' : 'default'}
              />
              <StatTile
                label="Available vs demand"
                value={num(out.single.avail)}
                unit="MW"
                hint={`demand ${num(out.demandSel)} MW`}
              />
              {out.single.shortfall > 0 && (
                <StatTile
                  label="Supply shortfall"
                  value={num(out.single.shortfall)}
                  unit="MW"
                  hint="load shed"
                  tone="danger"
                />
              )}
            </div>
            <MeritStack blocks={out.stack} demand={out.demandSel} />
          </Panel>

          <Panel
            title="Coupled with the two other islands"
            subtitle="The selected grid cleared together with the others over the HVDC links."
          >
            <FlowDiagram prices={prices} corridors={corridors} />
            {out.feed ? (
              <div className="kvs">
                <div className="kv">
                  <span>Coupled clearing price</span>
                  <span className="mono">
                    <b>{php(out.coupled.price[grid])}</b>
                  </span>
                </div>
                <div className="kv">
                  <span>{feedName} link</span>
                  <span className="mono">
                    {num(Math.abs(feedCor?.flow ?? 0))} MW{' '}
                    {feedCor?.sat ? (
                      <Chip tone="danger">saturated</Chip>
                    ) : (
                      <Chip tone="default">open</Chip>
                    )}
                  </span>
                </div>
                {feedCor?.sat && (
                  <div className="kv">
                    <span>Congestion rent across the binding link</span>
                    <span className="mono">
                      <b>{php(feedCor.rent)}</b>
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <p className="note">
                Luzon is the exporting grid: it sets the floor the others import from.
                Relieving a corridor helps the grid downstream, not Luzon.
              </p>
            )}
          </Panel>
        </div>
      </div>

      <p className="note">
        Solar is derated by the availability profile at the evening reference hour, which
        is near zero: adding solar barely moves the evening peak the headline is about.
        Storage (a time-shifter that discharges at the peak) does. A unit trip is
        subtracted from raw fuel availability before the coal commit tranche is split, so
        it reproduces the pipeline dispatch exactly. Every price traces to a sourced fuel
        cost; the scarcity premium lives in the calibration residual, not a tuned number.
      </p>
      {gens.error && <EmptyNote>Generator list unavailable: {gens.error}.</EmptyNote>}
    </div>
  )
}

function Slider({
  label,
  value,
  min,
  max,
  step,
  tick,
  fmt,
  onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  step: number
  tick?: string
  fmt?: (v: number) => string
  onChange: (v: number) => void
}) {
  const shown = fmt ? fmt(value) : `${num(value)} MW`
  return (
    <label className="lever">
      <span className="lever__label">
        {label} <b className="lever__val mono">{shown}</b>
      </span>
      {tick && <span className="lever__tick">{tick}</span>}
      <input
        type="range"
        className="lever__range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  )
}
