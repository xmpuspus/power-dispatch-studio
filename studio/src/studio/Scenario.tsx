import { useEffect, useMemo, useState } from 'react'
import type { Dispatch, GridKey } from '../lib/types'
import { fuelLabel, num, php, useEmissions } from '../lib/data'
import { Panel, StatTile, Chip } from '../ui/kit'
import { MeritStack, FlowDiagram } from './charts'
import { buildTemplateCsv, type ImportResult } from './importData'
import { downloadCsv } from './runs'
import { clearGrid } from './engine'
import {
  CARBON_DISCLAIMER,
  CARBON_FUEL_ID,
  CARBON_PROP,
  GAS_FUEL_ID,
  GAS_PROP,
  GAS_SOURCE_NOTE,
  carbonCostDelta,
  carbonPriceOf,
  effNum,
  gasSupplyPctOf,
  solveSnapshot,
  type ClassId,
  type ObjRow,
  type Overrides,
  type ScenarioSettings,
} from './model'
import { SCENARIO_PRESETS, type ScenarioPresetId } from './presets'

const cap = (g: string) => g[0].toUpperCase() + g.slice(1)

export function ScenarioView({
  d,
  grid,
  objects,
  overrides,
  scenarioName,
  settings,
  onEdit,
  onRevert,
  onSettings,
  onRenameScenario,
  onApplyPreset,
  onImportCsv,
  importStatus,
  importedKeys,
  onScenarioFile,
  scenarioMsg,
  onLive,
}: {
  d: Dispatch
  grid: GridKey
  objects: Record<ClassId, ObjRow[]>
  overrides: Overrides
  scenarioName: string
  settings: ScenarioSettings
  onEdit: (cls: ClassId, id: string, prop: string, value: number) => void
  onRevert: (cls: ClassId, id: string, prop: string) => void
  onSettings: (settings: ScenarioSettings) => void
  onRenameScenario: (name: string) => void
  onApplyPreset: (id: ScenarioPresetId) => void
  onImportCsv?: (text: string) => ImportResult
  importStatus?: string
  importedKeys?: string[]
  /** Write the scenario to a file, or read one back. Studio owns both sides. */
  onScenarioFile?: (mode: 'save' | 'load', file?: File) => void
  /** What the last save or load did, shown under the buttons. */
  scenarioMsg?: string
  /** Reports the live coupled clear so the run summary can show it beside the
      solved scenario. These controls preview; they do not write the model. */
  onLive?: (p: Record<GridKey, number> | null) => void
}) {
  const [draftName, setDraftName] = useState(scenarioName)
  useEffect(() => setDraftName(scenarioName), [scenarioName])
  const em = useEmissions()
  const region = objects.region.find((row) => row.id === grid)!
  const fuel = (id: string) => objects.fuel.find((row) => row.id === id)!
  const availability = (id: string) => {
    const row = fuel(id)
    const prop = `${grid}_mw`
    const base = row.props[prop] as number
    return { row, prop, base, value: effNum(overrides, 'fuel', id, prop, base) }
  }
  const demandBase = region.props.demand_mw as number
  const demandValue = effNum(overrides, 'region', grid, 'demand_mw', demandBase)
  const solar = availability('solar')
  const gas = availability('natural_gas')
  const coal = availability('coal')
  const coalBase = coal.row.props.cost as number
  const coalCost = effNum(overrides, 'fuel', 'coal', 'cost', coalBase)
  const feedInterface =
    grid === 'visayas'
      ? objects.interface.find((row) => row.id === 'leyte_luzon_hvdc')
      : grid === 'mindanao'
        ? objects.interface.find((row) => row.id !== 'leyte_luzon_hvdc')
        : undefined
  const feedLimitBase = (feedInterface?.props.limit_mw as number | undefined) ?? 0
  const feedLimit = feedInterface
    ? effNum(overrides, 'interface', feedInterface.id, 'limit_mw', feedLimitBase)
    : 0
  const setDelta = (
    cls: ClassId,
    id: string,
    prop: string,
    base: number,
    delta: number
  ) => {
    if (Math.abs(delta) < 1e-9) onRevert(cls, id, prop)
    else onEdit(cls, id, prop, base + delta)
  }
  const preview = useMemo(
    () => solveSnapshot(d, objects, overrides),
    [d, objects, overrides]
  )
  const basePreview = useMemo(() => solveSnapshot(d, objects, {}), [d, objects])
  const own = clearGrid(preview.stacks[grid], preview.demand[grid])
  const ownBase = clearGrid(basePreview.stacks[grid], basePreview.demand[grid])
  const cp = preview.coupled.price
  useEffect(() => {
    onLive?.({ luzon: cp.luzon, visayas: cp.visayas, mindanao: cp.mindanao })
    return () => onLive?.(null)
  }, [cp.luzon, cp.visayas, cp.mindanao, onLive])
  const mo = d.merit_order[grid]
  const delta = own.price - ownBase.price
  const feedKey = grid === 'mindanao' ? 'mvip' : grid === 'visayas' ? 'leyte' : null
  const feedName = feedKey === 'mvip' ? 'MVIP' : 'Leyte-Luzon'
  const feedCor = feedKey ? preview.coupled[feedKey] : null

  const prices: Record<string, number | null> = {
    luzon: preview.coupled.price.luzon,
    visayas: preview.coupled.price.visayas,
    mindanao: preview.coupled.price.mindanao,
  }
  const corridors = [
    {
      from: 'luzon',
      to: 'visayas',
      flow_mw: preview.coupled.leyte.flow,
      saturated: preview.coupled.leyte.sat,
      rent: preview.coupled.leyte.rent,
      limit_mw: objects.interface.find((row) => row.id === 'leyte_luzon_hvdc')
        ? effNum(
            overrides,
            'interface',
            'leyte_luzon_hvdc',
            'limit_mw',
            objects.interface.find((row) => row.id === 'leyte_luzon_hvdc')!.props
              .limit_mw as number
          )
        : null,
    },
    {
      from: 'visayas',
      to: 'mindanao',
      flow_mw: preview.coupled.mvip.flow,
      saturated: preview.coupled.mvip.sat,
      rent: preview.coupled.mvip.rent,
      limit_mw: objects.interface.find((row) => row.id !== 'leyte_luzon_hvdc')
        ? effNum(
            overrides,
            'interface',
            objects.interface.find((row) => row.id !== 'leyte_luzon_hvdc')!.id,
            'limit_mw',
            objects.interface.find((row) => row.id !== 'leyte_luzon_hvdc')!.props
              .limit_mw as number
          )
        : null,
    },
  ]

  const coalFloor = d.assumptions.coal_commit_php_kwh

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
  const onImportFile = (file: File | undefined) => {
    if (!file || !onImportCsv) return
    const reader = new FileReader()
    reader.onload = () => onImportCsv(String(reader.result ?? ''))
    reader.readAsText(file)
  }

  const resetLevers = () => {
    onRevert('region', grid, 'demand_mw')
    onRevert('fuel', 'solar', solar.prop)
    onRevert('fuel', 'natural_gas', gas.prop)
    onRevert('fuel', 'coal', coal.prop)
    onRevert('fuel', 'coal', 'cost')
    if (feedInterface) onRevert('interface', feedInterface.id, 'limit_mw')
    setGasSupply(100)
    setCarbonPrice(0)
    onSettings({ ...settings, reserveHoldback: false })
  }

  return (
    <div className="view" data-testid="scenario">
      <section className="preset-picker" aria-labelledby="preset-picker-title">
        <div className="preset-picker__head">
          <div>
            <h2 id="preset-picker-title">Start from an analyst task</h2>
            <p>Each case states its base data and its analyst assumption.</p>
          </div>
          <label className="scenario-name">
            Scenario name
            <input
              type="text"
              value={draftName}
              maxLength={80}
              onChange={(event) => setDraftName(event.target.value)}
              onBlur={() => {
                if (draftName.trim()) onRenameScenario(draftName)
                else setDraftName(scenarioName)
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter') event.currentTarget.blur()
              }}
            />
          </label>
        </div>
        <div className="preset-grid">
          {SCENARIO_PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              className="preset-card"
              onClick={() => onApplyPreset(preset.id)}
              data-testid={`preset-${preset.id}`}
            >
              <span className="preset-card__type">
                {preset.purpose === 'stress-test' ? 'Stress test' : 'Reference case'}
              </span>
              <strong>{preset.name}</strong>
              <span>{preset.summary}</span>
              <small>{preset.basis}</small>
            </button>
          ))}
        </div>
        <label className="scenario-setting">
          <input
            type="checkbox"
            checked={!!settings.reserveHoldback}
            onChange={(event) =>
              onSettings({ ...settings, reserveHoldback: event.target.checked })
            }
          />
          <span>
            <b>Hold reserves out of energy clearing</b>
            <small>
              Uses the recorded average reserve requirements. Press Run after a change.
            </small>
          </span>
        </label>
      </section>

      <p className="scn__how">Or adjust individual inputs for the selected grid.</p>

      <div className="scn">
        <Panel
          title="Scenario settings"
          subtitle={`${cap(grid)}, evening reference hour ${mo.reference_hour}:00.`}
        >
          <div className="levers">
            <Slider
              label="Add a data center (flat 24/7 load)"
              value={demandValue - demandBase}
              min={0}
              max={4000}
              step={50}
              tick="DICT reference scale: 1,500 MW; not a project forecast"
              onChange={(v) => setDelta('region', grid, 'demand_mw', demandBase, v)}
            />
            <Slider
              label="Add solar"
              value={solar.value - solar.base}
              min={0}
              max={4000}
              step={100}
              tick="installed-equivalent MW; the hourly replay applies the solar shape"
              onChange={(v) => setDelta('fuel', 'solar', solar.prop, solar.base, v)}
            />
            <Slider
              label="Add gas"
              value={gas.value - gas.base}
              min={0}
              max={3000}
              step={50}
              tick={`firm, at ₱${d.assumptions.fuel_marginal_cost_php_kwh.natural_gas.toFixed(2)}/kWh`}
              onChange={(v) => setDelta('fuel', 'natural_gas', gas.prop, gas.base, v)}
            />
            <Slider
              label="Add coal"
              value={coal.value - coal.base}
              min={0}
              max={3000}
              step={50}
              tick={`firm, at the coal price below`}
              onChange={(v) => setDelta('fuel', 'coal', coal.prop, coal.base, v)}
            />
            <Slider
              label="Administered coal price (marginal tranche)"
              value={coalCost}
              min={coalFloor}
              max={12}
              step={0.25}
              fmt={(v) => `₱${v.toFixed(2)}`}
              tick={`committed tranche stays at ₱${coalFloor.toFixed(2)}`}
              onChange={(v) =>
                Math.abs(v - coalBase) < 1e-9
                  ? onRevert('fuel', 'coal', 'cost')
                  : onEdit('fuel', 'coal', 'cost', v)
              }
            />
            {feedInterface && (
              <Slider
                label={`Relieve the feeding corridor (${feedName})`}
                value={feedLimit - feedLimitBase}
                min={0}
                max={500}
                step={25}
                tick={
                  feedCor?.sat
                    ? 'additional transfer capacity on the high-voltage direct-current link'
                    : `${feedName} is below its limit in this case; added capacity may have no price effect.`
                }
                onChange={(v) =>
                  setDelta('interface', feedInterface.id, 'limit_mw', feedLimitBase, v)
                }
              />
            )}
            <Slider
              label="Carbon price, system-wide"
              value={carbonPrice}
              min={0}
              max={5000}
              step={250}
              fmt={(v) => `₱${num(v)} per metric tonne CO2`}
              tick={`${CARBON_DISCLAIMER}. The carbon price is multiplied by each fuel's sourced emissions factor in metric tonnes CO2 per MWh and divided by 1000. This raises the cost of fuels with higher emissions in this preview, Hourly market replay, and Emissions.`}
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
                Current fuel-price changes in Assumptions and model inputs &gt; Fuels{' '}
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
                {importStatus && <p className="byo__msg note">{importStatus}</p>}
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
                value={`${php(own.price)}/kWh`}
                hint={own.marginal ? fuelLabel(own.marginal) : 'unserved'}
                tone={own.shortfall > 0 ? 'danger' : 'default'}
              />
              <StatTile
                label="vs base case"
                value={`${delta >= 0 ? '+' : ''}${php(delta)}/kWh`}
                hint={`base ${php(ownBase.price)}/kWh`}
                tone={delta > 0.001 ? 'accent' : delta < -0.001 ? 'positive' : 'default'}
              />
              <StatTile
                label="Available vs demand"
                value={num(own.avail)}
                unit="MW"
                hint={`demand ${num(preview.demand[grid])} MW`}
              />
              {own.shortfall > 0 && (
                <StatTile
                  label="Supply shortfall"
                  value={num(own.shortfall)}
                  unit="MW"
                  hint="load shed"
                  tone="danger"
                />
              )}
            </div>
            <MeritStack blocks={preview.stacks[grid]} demand={preview.demand[grid]} />
          </Panel>

          <Panel
            title="Connected-grid clearing"
            subtitle="Power can move between them over the high-voltage direct-current (HVDC) links."
          >
            <FlowDiagram prices={prices} corridors={corridors} />
            {feedKey ? (
              <div className="kvs">
                <div className="kv">
                  <span>Clearing price with all three island grids</span>
                  <span className="mono">
                    <b>{php(preview.coupled.price[grid])}/kWh</b>
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
                      <b>{php(feedCor.rent)}/kWh</b>
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
          The same saved inputs drive this preview, the Run button, comparisons, and
          hourly replay. Malampaya supply is a daily energy constraint, so its effect is
          visible in hourly replay rather than this one-hour panel.
        </p>
      </details>

      <p className="note">
        The evening solar availability is near zero, so added solar barely changes this
        evening-peak calculation. Configure storage and plant outage rates in Model and
        data. Fuel costs come from published sources except for the oil peaker price,
        which is labeled as an assumption. The cost-only calculation does not include
        scarcity pricing; the historical replay reports the remaining difference from
        recorded prices.
      </p>
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
