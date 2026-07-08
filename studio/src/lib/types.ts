// Types for the baked dispatch model (web/data/dispatch.json). Only the fields the
// Studio reads are typed; the pipeline (pipeline/dispatch.py) is the source of truth.

export type GridKey = 'luzon' | 'visayas' | 'mindanao'
export const GRIDS: GridKey[] = ['luzon', 'visayas', 'mindanao']

export interface Block {
  fuel: string
  cost: number
  mw: number
}

export interface MeritOrder {
  reference_hour: number
  installed_mw: number
  avail_mw: number
  typical_evening_demand_mw: number
  peak_demand_mw: number
  // dispatchable MW per fuel at the reference hour, before the coal commit/marginal
  // split. The scenario engine rebuilds the stack from this (see engine.ts).
  fuel_avail_mw: Record<string, number>
  solar_avail_frac_ref: number
  solar_avail_frac_midday: number
  solar_installed_mw: number
  blocks: Block[]
}

export interface Hydrology {
  normal_multiplier: number
  dry_multiplier: number
  wet_multiplier: number
  modeled_normal_hydro_avail_mw: number
  dry_avail_mw_national: number
  dependable_mw_national: number
  dry_label: string
  src_dry: string
  note: string
}

export interface Assumptions {
  fuel_marginal_cost_php_kwh: Record<string, number>
  national_fuel_mw: Record<string, number>
  coal_commit_php_kwh: number
  coal_min_load_frac: number
  wheeling_cost_php_kwh: number
  hydrology: Hydrology
  note: string
}

export interface GoldenCase {
  label: string
  lp_sha256?: string
  input: {
    demand: Record<GridKey, number>
    removed: Partial<Record<GridKey, Record<string, number>>>
    caps: { leyte: number; mvip: number }
  }
  expect: {
    price: Record<GridKey, number>
    gen_mw: Record<GridKey, number>
    shortfall_mw: Record<GridKey, number>
    flow_lv_mw: number
    flow_vm_mw: number
    leyte_saturated: boolean
    leyte_rent_php_kwh: number
    mvip_saturated: boolean
    mvip_rent_php_kwh: number
  }
}

export interface ScenarioGolden {
  reference_hour: number
  tolerance_php_kwh: number
  tolerance_mw: number
  note: string
  cases: GoldenCase[]
}

export interface Calibration {
  n_intervals: number
  observed_mean_php_kwh: number
  modeled_mean_php_kwh: number
  mae_php_kwh: number
  bias_php_kwh: number
  evening_peak_residual_php_kwh: number | null
  correlation: number | null
  note: string | null
}

export interface N1Row {
  unit: string
  grid: string
  fuel: string
  capacity_mw: number
  tight_evening_demand_mw: number
  base_price_php_kwh: number
  tripped_price_php_kwh: number
  delta_price_php_kwh: number
  peak_demand_mw: number
  shortfall_at_peak_mw: number
}

export interface CorridorStat {
  id: string
  name: string
  limit_mw: number
  limit_kind: string
  nameplate_mw: number
  src: string
  saturated_pct: number | null
  mean_congestion_rent_php_kwh: number
  mean_abs_flow_mw: number | null
  peak_abs_flow_mw: number | null
}

export interface SpreadPair {
  observed_php_kwh: number | null
  coupled_model_php_kwh: number | null
  explained_fraction: number | null
}

export interface Coupling {
  model: string
  wheeling_cost_php_kwh: number
  n_coupled_intervals: number
  corridors: CorridorStat[]
  per_grid: Record<
    GridKey,
    {
      observed_mean_php_kwh: number | null
      coupled_modeled_mean_php_kwh: number | null
      mae_php_kwh: number | null
      correlation: number | null
    }
  >
  spread_decomposition: {
    note: string
    visayas_vs_luzon: SpreadPair
    mindanao_vs_luzon: SpreadPair
    uncapped_counterfactual: {
      note: string
      visayas_vs_luzon_php_kwh: number | null
      mindanao_vs_luzon_php_kwh: number | null
    }
  }
  outage_scenario: {
    label: string
    outage_mw: number
    src: string
    window: { from: string; to: string }
    n_intervals: number
    leyte_luzon_saturated_pct: number | null
    leyte_luzon_mean_rent_php_kwh: number
    visayas_vs_luzon_observed_php_kwh: number | null
    visayas_vs_luzon_coupled_php_kwh: number | null
    explained_fraction: number | null
  }
  dc_binding_threshold: {
    available: boolean
    reference_hour: number
    typical_evening_demand_mw: Record<GridKey, number>
    added_visayas_load_to_bind_leyte_mw: number | null
    note: string
  }
}

export interface UnitCommitment {
  layer: string
  min_load_frac: number
  commit_offer_php_kwh: number
  src_min_load: string
  src_offer: string
  note: string
  per_grid: Record<
    GridKey,
    {
      mae_before_php_kwh: number
      mae_after_php_kwh: number
      correlation_before: number | null
      correlation_after: number | null
      modeled_mean_before_php_kwh: number
      modeled_mean_after_php_kwh: number
    }
  >
}

export interface McDist {
  lolp_pct: number
  expected_shortfall_mw: number
  shortfall_mw_p50: number
  shortfall_mw_p90: number
  shortfall_mw_p99: number
  shortfall_mw_max: number
  eue_mwh_evening_window: number
}

export interface ReliabilityMc {
  method: string
  draws: number
  seed: number
  load_hours: string
  forced_outage_rates: Record<string, number>
  src_for: string
  note: string
  per_grid: Record<GridKey, McDist>
  load_dist: Record<GridKey, { mean: number; std: number }>
  dict_2028_luzon: {
    added_mw: number
    owner: string
    date: string
    src: string
    distribution: McDist
  }
}

export interface Storage {
  assets: Record<'luzon', { bess_mw: number; pumped_hydro_mw: number; total_mw: number }>
  round_trip_eff: number
  discharge_offer_php_kwh: number
  src_bess: string
  src_pumped_hydro: string
  note: string
  dict_wave_peak_price: {
    reference: string
    demand_mw: number
    without_storage_php_kwh: number
    with_storage_php_kwh: number
    without_storage_marginal_fuel: string
    with_storage_marginal_fuel: string
    shortfall_without_mw: number
    shortfall_with_mw: number
  }
  reliability_buyback: {
    luzon_baseline: { lolp_without_pct: number; lolp_with_pct: number }
    luzon_dict_2028: { without: McDist; with_storage: McDist }
  }
}

export interface DurationPoint {
  pct: number
  price: number
}

export interface PriceDuration {
  modeled: DurationPoint[]
  observed: DurationPoint[]
  observed_min_php_kwh: number
  observed_max_php_kwh: number
  note: string
  src: string
}

export interface MarginalFrequency {
  n_intervals: number
  by_block: { block: string; share_pct: number }[]
}

export interface Adequacy {
  installed_mw: number
  avail_at_peak_mw: number
  peak_demand_mw: number
  reserve_margin_pct: number | null
}

export interface Dispatch {
  available: boolean
  model: string
  days: number
  assumptions: Assumptions
  calibration_window: { regime: string; from: string; days: number; note: string }
  merit_order: Record<GridKey, MeritOrder>
  scenario_golden: ScenarioGolden
  coupling: Coupling
  unit_commitment: UnitCommitment
  price_duration: Record<GridKey, PriceDuration>
  marginal_frequency: Record<GridKey, MarginalFrequency>
  calibration: Record<GridKey, Calibration>
  n1: N1Row[]
  adequacy: Record<GridKey, Adequacy> & {
    dict_2028: {
      added_mw: number
      reserve_margin_now_pct: number | null
      reserve_margin_with_dc_pct: number | null
      shortfall_intervals_with_dc: number
      eue_mwh_with_dc: number
      src: string | null
    }
  }
  reliability_mc: ReliabilityMc
  storage: Storage
}

export interface ReserveCategory {
  code: string
  category: string
  label: string
  code_mapping: string
  mean_php_kwh: number
  min_php_kwh: number
  max_php_kwh: number
  cap_hit_pct: number
  mean_system_mw: number
}

export interface ReserveGridRow {
  code: string
  category: string
  label: string
  mean_php_kwh: number
  mean_mw: number
}

export interface Reserve {
  available: boolean
  commercial_since?: string
  sample_days?: string[]
  n_intervals?: number
  reserve_cap_php_kwh?: number
  categories?: ReserveCategory[]
  by_grid?: Record<GridKey, ReserveGridRow[]>
  scarcity?: {
    category: string
    label: string
    mean_php_kwh: number
    top_decile_mean_php_kwh: number
  }
  mapping_note?: string
  note: string
  disclaimer?: string
  src_market?: string
  src_data?: string
}

// observed market operations (market_ops.json); only the sections the studio
// renders are typed strictly
export interface MarketOps {
  price_setters?: {
    available: boolean
    days?: number
    per_grid?: Partial<
      Record<
        GridKey,
        {
          n_intervals: number
          n_setters: number
          fuel_matched_share_pct: number | null
          top: {
            resource: string
            fuel: string | null
            share_pct: number
            mean_price_php_kwh: number
          }[]
        }
      >
    >
    note?: string
  }
  reserve_prices?: {
    available: boolean
    dates?: string[]
    series?: Partial<Record<GridKey, Record<string, (number | null)[]>>>
    stats?: Partial<Record<GridKey, Record<string, { mean: number; max: number }>>>
    unit?: string
    commodity_note?: string
    src?: string
  }
  advisories?: { available: boolean }
  outlook?: { available: boolean }
}

export interface MixMonth {
  period: string
  wesm_pct: number
  psa_pct: number
  ipp_pct: number
  generation_charge_php_kwh: number
  total_rate_php_kwh: number
  src: string
  src_news: string
}

export interface Bill {
  available: boolean
  period?: string
  supply_mix_pct?: Record<string, number>
  wesm_share_pct?: number
  src_mix?: string
  total_rate_php_kwh?: number
  generation_charge_php_kwh?: number
  wesm_cost_in_gen_charge_php_kwh?: number
  src_bill?: string
  household_kwh_month?: number
  pass_through_factor?: number
  mix_history?: MixMonth[]
  mix_history_note?: string
  june_moves?: {
    psa_delta_php_kwh: number
    ipp_delta_php_kwh: number
    src_psa: string
    src_ipp: string
  }
  note: string
  gwap_lwap_note?: string
  disclaimer?: string
}

export interface EmissionFactor {
  fuel: string
  tco2_per_mwh: number | null
  basis: string
  src: string
  src2?: string
}

export interface Emissions {
  available: boolean
  unit?: string
  factors?: EmissionFactor[]
  factor_map?: Record<string, number>
  ngef?: {
    luzon_visayas_tco2_per_mwh: number
    mindanao_tco2_per_mwh: number
    vintage: string
    src: string
    note: string
  }
  note: string
  disclaimer?: string
}

export interface PasaResource {
  resource: string
  grid: GridKey | null
  plant: string | null
  fuel: string | null
  unit_mw: number | null
  match: 'verified' | 'unmatched' | 'storage'
}

export interface PasaDay {
  date: string
  out: string[]
  matched_mw: Record<GridKey, number>
  n_out: number
  n_unmatched: number
}

export interface Pasa {
  available: boolean
  days?: PasaDay[]
  resources?: PasaResource[]
  n_resources?: number
  n_verified?: number
  n_unmatched?: number
  n_storage?: number
  grid_mapping_note?: string
  coverage_note?: string
  note: string
  src?: string
  disclaimer?: string
}

export interface ProjectRow {
  grid: GridKey
  status: 'committed' | 'indicative'
  fuel: string
  mw: number
  target: string | null
  target_year: number | null
}

export interface ProjectSection {
  grid: GridKey
  status: 'committed' | 'indicative'
  fuel: string
  subtotal_mw: number
  n_rows: number
  rows_reconciled: boolean
}

export interface TdpCorridor {
  name: string
  iface: string | null
  adds_mw: number | null
  target: string
  target_year: number | null
  cost_mphp: number | null
  detail: string
  src: string
}

export interface Projects {
  available: boolean
  as_of?: string
  editions?: Record<string, Record<string, { src: string; original_url: string }>>
  totals?: Record<string, Record<string, { gen_mw: number; ess_mw: number } | number>>
  sections?: ProjectSection[]
  rows?: ProjectRow[]
  n_rows?: number
  n_sections_aggregate_only?: number
  corridors?: TdpCorridor[]
  src_tdp?: string
  note: string
  ess_note?: string
  disclaimer?: string
}

export interface MarketPower {
  available: boolean
  as_of?: string
  national_cap_mw_2025?: number
  companies?: { name: string; mw: number; share_pct: number }[]
  others_share_pct?: number
  hhi_floor?: number
  hhi_ceiling?: number
  hhi_band?: string
  top2_combined_pct?: number
  largest?: { name: string; mw: number; share_pct: number }
  cap_installed_pct?: number
  cap_demand_pct?: number
  pivotal_supplier_note?: string
  rsi_note?: string
  note: string
  disclaimer?: string
  src?: string
  src_cap?: string
}

export interface DayProfile {
  date: string
  market: boolean
  demand: Record<GridKey, number[]>
  lwap: Partial<Record<GridKey | 'system', (number | null)[]>>
  // observed daily hydro energy (DIPCEF-derived); null when the day is not
  // covered by the derived window
  hydro_budget_mwh?: Partial<Record<GridKey, number>> | null
  // recorded curtailment summed over the day (MWh per grid); absent when zero
  curtailed_mwh?: Partial<Record<GridKey, number>> | null
  // the day's scheduled-outage deviation from the window mean, per grid and
  // fuel (PASA-matched MW; hydro and storage excluded); null when OUTRTD
  // does not cover the date
  out_dev_mw?: Partial<Record<GridKey, Record<string, number>>> | null
  // observed hourly regional clearing price (MCP, PhP/kWh); the backcast's
  // second target; null when the MCP archive does not cover the date
  mcp?: Partial<Record<GridKey, (number | null)[]>> | null
  // observed corridor flows (MW; lv = Luzon->Visayas southbound positive,
  // vm = Visayas->Mindanao southbound positive), from the RTDSUM net
  // market imports/exports
  net_flow?: { lv: (number | null)[]; vm: (number | null)[] } | null
  // the day's scheduled reserve requirement per grid and commodity (MW)
  reserve_req_mw?: Partial<Record<GridKey, Record<string, number>>> | null
}

export interface StorageDefault {
  id: string
  label: string
  grid: GridKey
  power_mw: number
  energy_mwh: number
  src_power: string
  energy_note: string
}

export interface ChronoGoldenCase {
  label: string
  lp_sha256?: string
  input: {
    date: string
    demand_delta?: Partial<Record<GridKey, number>>
    solar_delta_mw?: Partial<Record<GridKey, number>>
    fuel_avail_delta?: Partial<Record<GridKey, Record<string, number>>>
    fuel_cost?: Record<string, number>
    hydrology?: number
    storage?: { grid: GridKey; power_mw: number; energy_mwh: number }[]
    reserve_deduction?: boolean
    // marker only: the replaying engine loads the same per-day offer book
    // artifact (web/data/offers/) the Python bake used
    offer_mode?: boolean
  }
  expect: {
    price: Record<GridKey, number[]>
    flow_lv: number[]
    flow_vm: number[]
    soc_mwh: number[]
    shortfall_luzon: number[]
    marginal_luzon: (string | null)[]
    summary: {
      mean_price: Record<GridKey, number>
      peak_price: Record<GridKey, number>
      unserved_mwh: Record<GridKey, number>
      leyte_rent_m_php: number
      mvip_rent_m_php: number
    }
  }
}

export interface BackcastGrid {
  n_hours: number
  observed_mean_php_kwh: number
  modeled_mean_php_kwh: number
  mae_php_kwh: number
  bias_php_kwh: number
  correlation: number | null
  high_hour_hit_rate_pct: number | null
}

export interface Profiles {
  unit: string
  note: string
  resumed: string
  days: DayProfile[]
  default_day: string | null
  stress_day: string | null
  solar_profile: number[]
  solar_profile_note: string
  storage_defaults: StorageDefault[]
  storage_round_trip_eff: number
  storage_note: string
  reserve_req_mean_mw: Record<GridKey, Record<string, number>>
  reserve_req_note: string
  hydro_budget?: {
    n_days: number
    matched_cores: Record<string, string>
    suspects_mwh: Record<string, number>
    excluded_note: string
    note: string
  } | null
  chrono_golden: {
    available: boolean
    date?: string
    tolerance_php_kwh?: number
    tolerance_mw?: number
    note?: string
    cases?: ChronoGoldenCase[]
  }
  backcast: {
    available: boolean
    days: number
    window: { from: string; to: string } | null
    per_grid: Partial<Record<GridKey, BackcastGrid>>
    // same replays scored against the observed regional clearing price (MCP),
    // the target commensurate with a dispatch dual; null when the MCP archive
    // is absent
    per_grid_mcp?: Partial<Record<GridKey, BackcastGrid>> | null
    mcp_note?: string
    // modeled corridor flows scored against the observed net market
    // imports/exports (the third validation table)
    flows?: Record<
      string,
      {
        corridor: string
        n_hours: number
        observed_mean_mw: number
        modeled_mean_mw: number
        mae_mw: number
        direction_agreement_pct: number | null
        n_decisive_hours: number
      }
    > | null
    flows_note?: string
    high_hour_note: string
    note: string
  }
}

export interface FleetPlant {
  name: string
  grid: GridKey
  fuel: string
  connection: 'grid' | 'embedded'
  installed_mw: number
  dependable_mw: number
  units: number
}

export interface Fleet {
  available: boolean
  note: string
  editions: Record<
    GridKey,
    {
      as_of: string
      src: string
      original_url: string
      sections_total_mw: number
      doe_total_mw: number | null
    }
  >
  n_plants: number
  plants: FleetPlant[]
}

export interface GeneratorProps {
  name: string
  grid: string
  fuel: string
  capacity_mw: number
  city: string
  owner: string
  note: string
  src: string
  marginal_cost_php_kwh: number | null
}

export interface Meta {
  built_utc?: string
  [k: string]: unknown
}
