import { useEffect, useMemo, useState } from 'react'
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
  onScenarioFile,
  scenarioMsg,
  onLive,
}: {
  d: Dispatch
  grid: GridKey
  objects: Record<ClassId, ObjRow[]>
  overrides: Overrides
  onEdit: (cls: ClassId, id: string, prop: string, value: number) => void
  onRevert: (cls: ClassId, id: string, prop: string) => void
  onImportCsv?: (text: string) => ImportResult
  importedKeys?: string[]
  /** Write the scenario to a file, or read one back. Studio owns both sides. */
  onScenarioFile?: (mode: 'save' | 'load', file?: File) => void
  /** What the last save or load did, shown under the buttons. */
  scenarioMsg?: string
  /** Reports the live coupled clear so the run summary can show it beside the
      solved scenario. These controls preview; they do not write the model. */
  onLive?: (p: Record<GridKey, number> | null) => void
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
  const cp = out.coupled.price
  useEffect(() => {
    onLive?.({ luzon: cp.luzon, visayas: cp.visayas, mindanao: cp.mindanao })
    return () => onLive?.(null)
  }, [cp.luzon, cp.visayas, cp.mindanao, onLive])
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
  // the lever writes per-fuel Price via the generated tCO2/MWh factors; with no factors
  // loaded it would move but change no solve, so gate it on the factors being ready
  const factorsReady = Object.keys(factors).length > 0
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
    // only ever touches fuels with a nonzero generated factor, so a manual edit to
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
      {/* Seventy-seven words used to sit between the reader and the first
          slider, which put the control below the fold on a phone. One line
          stays, and the model description moves under the controls where a
          reader goes looking for it rather than past it. */}
      <p className="scn__how">Move a slider and all three grids recalculate at once.</p>

      <div className="scn">
        <Panel
          title="Quick what-if settings"
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
                disabled={!feedCor?.sat}
                tick={
                  feedCor?.sat
                    ? 'additional transfer capacity on the high-voltage direct-current link'
                    : `${feedName} is below its limit at this demand. More capacity has no effect until the link reaches its limit. Add demand to test that point.`
                }
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
                  Malampaya depletes around 2027. Gas changes from ₱
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
              <span className="lever__label">
                Remove one unit from service (N-1 test)
              </span>
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
              fmt={(v) => `₱${num(v)} per metric tonne CO2`}
              tick={`${CARBON_DISCLAIMER}. The carbon price is multiplied by each fuel's sourced emissions factor in metric tonnes CO2 per MWh and divided by 1000. This raises the cost of fuels with higher emissions in the lowest-cost-first order. It appears in Hourly market replay and Emissions, not in this evening-hour calculation.`}
              onChange={setCarbonPrice}
              disabled={!factorsReady}
            />
            {!factorsReady && (
              <p className="note">
                {em.error
                  ? 'Emission factors failed to load, so the carbon price setting is off.'
                  : 'Loading emission factors. The carbon price setting will be available shortly.'}
              </p>
            )}
            {factorsReady && carbonRows.length > 0 && (
              <p className="note">
                Current fuel-price changes in Review and edit model inputs &gt; Fuels{' '}
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
              tick={`${GAS_SOURCE_NOTE}. Caps the gas fleet's daily energy to this percent of its flat-out day. Hourly market replay and Emissions use this limit; this single-evening calculation does not.`}
              onChange={setGasSupply}
            />
            <button className="btn btn--ghost lever__reset" onClick={resetLevers}>
              Reset what-if settings
            </button>
            {onImportCsv && (
              <div className="byo">
                <div className="byo__head">Bring your own data</div>
                <p className="note">
                  Load a CSV of your own unit parameters (dependable MW, fuel price,
                  forced outage), region load, or inter-grid link limits. It stays in this
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
                  hourly market replay, not these individual input overrides. They cannot
                  be imported here.
                </p>
              </div>
            )}
            {onScenarioFile && (
              <div className="byo">
                <div className="byo__head">Take this scenario to Python</div>
                <p className="note">
                  The same file runs here and on the command line. Download it, then
                  <code> power-dispatch run --scenario yours.json</code>, or load a file
                  someone sent you.
                </p>
                <div className="byo__actions">
                  <button
                    className="btn btn--ghost btn--sm"
                    onClick={() => onScenarioFile('save')}
                  >
                    Download scenario
                  </button>
                  <label className="btn btn--ghost btn--sm">
                    Load scenario
                    <input
                      type="file"
                      accept="application/json,.json"
                      style={{ display: 'none' }}
                      onChange={(e) => {
                        onScenarioFile('load', e.target.files?.[0])
                        e.target.value = ''
                      }}
                    />
                  </label>
                </div>
                {scenarioMsg && <p className="byo__msg note">{scenarioMsg}</p>}
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
            title="The selected grid clears together with the other two island grids"
            subtitle="Power can move between them over the high-voltage direct-current (HVDC) links."
          >
            <FlowDiagram prices={prices} corridors={corridors} />
            {out.feed ? (
              <div className="kvs">
                <div className="kv">
                  <span>Clearing price with all three island grids</span>
                  <span className="mono">
                    <b>{php(out.coupled.price[grid])}</b>
                  </span>
                </div>
                <div className="kv">
                  <span>{feedName} link</span>
                  <span className="mono">
                    {num(Math.abs(feedCor?.flow ?? 0))} MW{' '}
                    {feedCor?.sat ? (
                      <Chip tone="danger">at its limit</Chip>
                    ) : (
                      <Chip tone="default">open</Chip>
                    )}
                  </span>
                </div>
                {feedCor?.sat && (
                  <div className="kv">
                    <span>
                      Value of the price gap across the constrained link (congestion rent)
                    </span>
                    <span className="mono">
                      <b>{php(feedCor.rent)}</b>
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <p className="note">
                Luzon is the exporting grid and sets the starting price for imports to the
                other grids. Raising an inter-grid transfer limit helps the importing
                grid, not Luzon.
              </p>
            )}
          </Panel>
        </div>
      </div>

      {/* the model description that used to sit above the first slider. A
          reader who wants it goes looking; a reader who wants a slider does not
          have to scroll past it. */}
      <details className="scn__about">
        <summary>What this calculation does, and what it leaves out</summary>
        <p>
          This <b>lowest-cost-first model (merit order)</b> stacks the sourced fleet from
          lowest to highest operating cost, then calculates all three island grids
          together. Prices are the cost of serving one additional unit of demand in each
          island grid. The model is checked against recorded prices but does not predict
          them.
        </p>
        <p>
          The carbon-price and Malampaya gas settings apply to Hourly market replay and
          Emissions, and not to this evening-hour calculation.
        </p>
      </details>

      <p className="note">
        The evening solar availability is near zero, so added solar barely changes this
        evening-peak calculation. Storage can discharge at the peak and does change it. A
        unit outage is removed from available capacity before committed and marginal coal
        capacity are separated, matching the reference dispatch. Fuel costs come from
        published sources except for the oil peaker price, which is labeled as an
        assumption. The cost-only calculation does not include scarcity pricing; the
        historical replay reports the remaining difference from recorded prices.
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
  disabled = false,
}: {
  label: string
  value: number
  min: number
  max: number
  step: number
  tick?: string
  fmt?: (v: number) => string
  onChange: (v: number) => void
  disabled?: boolean
}) {
  const shown = fmt ? fmt(value) : `${num(value)} MW`
  return (
    <label className={`lever${disabled ? ' lever--off' : ''}`}>
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
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  )
}
