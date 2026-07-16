// Backcast: the trust artifact. Every full-coverage market day replayed against
// the observed hourly LWAP, error stated, nothing tuned. Two engines: the base
// COST model, and the operator's own OBSERVED OFFER BOOKS. The gap (scarcity,
// offers, caps, outages the cost model cannot see) is the finding; the offer
// books close most of it, which is the point of the toggle.

import { useMemo, useState, type ReactNode } from 'react'
import type { Dispatch, GridKey, Profiles } from '../lib/types'
import { num, php, pct, useOfferDay, downloadCsv } from '../lib/data'
import { Panel, Segmented, StatTile } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'
import { HourLines } from './charts'
import { runChronology } from './chrono'

const GRIDS: GridKey[] = ['luzon', 'visayas', 'mindanao']
const cap = (g: string) => g[0].toUpperCase() + g.slice(1)

export function BackcastView({
  d,
  profiles,
  grid,
}: {
  d: Dispatch
  profiles: Profiles
  grid: GridKey
}) {
  // Lead with the offer replay: it tracks the observed hourly price far better
  // than the pure cost stack, so it is the calibrated view. The cost model is the
  // counterfactual you subtract to read the offer premium.
  const [engine, setEngine] = useState<'cost' | 'offers'>('offers')
  const offers = engine === 'offers'
  const bc = offers ? profiles.offer_backcast : profiles.backcast

  const marketDays = useMemo(
    () =>
      profiles.days.filter(
        (x) =>
          x.market &&
          GRIDS.every(
            (g) =>
              (x.lwap?.[g] ?? []).length === 24 && x.lwap![g]!.every((v) => v != null)
          )
      ),
    [profiles.days]
  )
  const [date, setDate] = useState(
    () => profiles.default_day ?? marketDays[marketDays.length - 1]?.date
  )
  const day = marketDays.find((x) => x.date === date) ?? marketDays[0]

  // the one-day chart replays the selected engine: cost proxy, or the day's book
  const offerDay = useOfferDay(offers ? (day?.date ?? null) : null)
  const runReady = !offers || !!offerDay.data
  const run = useMemo(
    () =>
      day && runReady
        ? runChronology(
            d,
            profiles,
            day.date,
            offerDay.data ? { offer_day: offerDay.data } : {}
          )
        : null,
    [d, profiles, day, runReady, offerDay.data]
  )

  const engineToggle = (
    <Segmented
      ariaLabel="Validation engine"
      value={engine}
      onChange={(v) => setEngine(v as 'cost' | 'offers')}
      options={[
        { value: 'offers', label: 'Observed offers' },
        { value: 'cost', label: 'Cost model' },
      ]}
    />
  )

  if (!bc.available || !day)
    return (
      <div className="view">
        <div className="chrono__controls">{engineToggle}</div>
        <Panel title="Backcast" subtitle="Model vs observed prices.">
          <p className="note">
            {offers
              ? 'No derived offer books in the archive window yet.'
              : 'No full-coverage market day in the archive window yet.'}
          </p>
        </Panel>
      </div>
    )

  const stats = bc.per_grid[grid]
  // on the offer view, show how each figure moved from the base cost model
  const costStats = offers ? profiles.backcast?.per_grid?.[grid] : undefined
  const fromCost = (base: string, from: ReactNode) =>
    costStats != null && from != null ? (
      <>
        {base} <span className="stat__delta">from {from}</span>
      </>
    ) : (
      base
    )
  const residual =
    run != null
      ? day.lwap![grid]!.map((obs, h) =>
          obs == null ? null : obs - run.hours[h].price[grid]
        )
      : null
  const peakResid = (residual ?? []).slice(17, 22).filter((v): v is number => v != null)
  const peakResidMean = peakResid.length
    ? peakResid.reduce((s, v) => s + v, 0) / peakResid.length
    : null

  const cols: Column<GridKey>[] = [
    { key: 'g', header: 'Grid', render: (g) => cap(g) },
    {
      key: 'obs',
      header: 'Observed mean',
      align: 'right',
      mono: true,
      render: (g) => php(bc.per_grid[g]?.observed_mean_php_kwh),
    },
    {
      key: 'mod',
      header: 'Modeled mean',
      align: 'right',
      mono: true,
      render: (g) => php(bc.per_grid[g]?.modeled_mean_php_kwh),
    },
    {
      key: 'mae',
      header: 'MAE',
      align: 'right',
      mono: true,
      render: (g) => php(bc.per_grid[g]?.mae_php_kwh),
    },
    {
      key: 'bias',
      header: 'Bias',
      align: 'right',
      mono: true,
      render: (g) => php(bc.per_grid[g]?.bias_php_kwh),
    },
    {
      key: 'corr',
      header: 'Correlation',
      align: 'right',
      mono: true,
      render: (g) => num(bc.per_grid[g]?.correlation ?? NaN, 2),
    },
    {
      key: 'hit',
      header: 'High-hour hit rate',
      align: 'right',
      mono: true,
      render: (g) => {
        const v = bc.per_grid[g]?.high_hour_hit_rate_pct
        return v == null ? 'n/a (flat model)' : pct(v / 100, 0)
      },
    },
  ]

  const engineLabel = offers
    ? "the operator's observed offer books"
    : 'the base cost model'

  return (
    <div className="view">
      <div className="chrono__controls">
        {engineToggle}
        <span className="note">
          {offers
            ? 'The calibrated view: every market day replayed on the operator’s own published offer books. The correlation and error below are live from the bake.'
            : 'The counterfactual: the pure merit-order cost model, fundamentals only, nothing tuned. The gap up to the offer replay is the measured offer premium.'}
        </span>
      </div>

      <div className="stat-row">
        <StatTile
          label={`MAE, ${cap(grid)}`}
          value={php(stats?.mae_php_kwh)}
          hint={fromCost(
            `${bc.days} market days, hourly`,
            costStats ? php(costStats.mae_php_kwh) : null
          )}
        />
        <StatTile
          label="Bias"
          value={php(stats?.bias_php_kwh)}
          hint={fromCost(
            'model minus observed; negative = under-priced',
            costStats ? php(costStats.bias_php_kwh) : null
          )}
        />
        <StatTile
          label="Correlation"
          value={num(stats?.correlation ?? NaN, 2)}
          hint={fromCost(
            'hourly, whole window',
            costStats ? num(costStats.correlation ?? NaN, 2) : null
          )}
        />
        <StatTile
          label={`Evening residual, ${date}`}
          value={peakResidMean == null ? '-' : php(peakResidMean)}
          hint="observed minus modeled, hours 17-21"
          tone={peakResidMean != null && peakResidMean > 2 ? 'danger' : 'default'}
        />
      </div>

      <Panel
        title="Model vs observed LWAP, whole market window"
        subtitle={`Every full-coverage market day since ${bc.window?.from} replayed with ${engineLabel}.`}
        right={
          <button
            className="btn btn--ghost btn--sm"
            onClick={() => {
              const sets: [string, typeof bc][] = [
                ['offer_replay', profiles.offer_backcast],
                ['cost_model', profiles.backcast],
              ]
              const rows = sets.flatMap(([engineName, set]) =>
                GRIDS.map((g) => {
                  const s = set?.per_grid?.[g]
                  return {
                    engine: engineName,
                    grid: g,
                    days: set?.days ?? '',
                    observed_mean_php_kwh: s?.observed_mean_php_kwh ?? '',
                    modeled_mean_php_kwh: s?.modeled_mean_php_kwh ?? '',
                    mae_php_kwh: s?.mae_php_kwh ?? '',
                    bias_php_kwh: s?.bias_php_kwh ?? '',
                    correlation: s?.correlation ?? '',
                    high_hour_hit_rate_pct: s?.high_hour_hit_rate_pct ?? '',
                  }
                })
              )
              downloadCsv(rows, 'backcast_whole_window.csv')
            }}
          >
            Export CSV
          </button>
        }
      >
        <DataGrid columns={cols} rows={GRIDS} getKey={(g) => g} />
        {bc.high_hour_note ? <p className="note">{bc.high_hour_note}</p> : null}
      </Panel>

      {bc.flows ? (
        <Panel
          title="Corridor flows against the observed imports and exports"
          subtitle="With native-load demand the replay must move real MW to serve each grid; this scores whether it does."
        >
          <DataGrid
            columns={[
              {
                key: 'c',
                header: 'Corridor',
                render: (k: string) => bc.flows![k].corridor,
              },
              {
                key: 'obs',
                header: 'Observed mean',
                align: 'right',
                mono: true,
                render: (k: string) => `${num(bc.flows![k].observed_mean_mw)} MW`,
              },
              {
                key: 'mod',
                header: 'Modeled mean',
                align: 'right',
                mono: true,
                render: (k: string) => `${num(bc.flows![k].modeled_mean_mw)} MW`,
              },
              {
                key: 'mae',
                header: 'MAE',
                align: 'right',
                mono: true,
                render: (k: string) => `${num(bc.flows![k].mae_mw)} MW`,
              },
              {
                key: 'dir',
                header: 'Direction agreement',
                align: 'right',
                mono: true,
                render: (k: string) => {
                  const v = bc.flows![k].direction_agreement_pct
                  return v == null ? 'n/a' : pct(v / 100, 0)
                },
              },
            ]}
            rows={Object.keys(bc.flows)}
            getKey={(k) => k}
          />
          {bc.flows_note ? <p className="note">{bc.flows_note}</p> : null}
        </Panel>
      ) : null}

      {bc.flows_rtdhs ? (
        <Panel
          title="Corridor flows against the operator's own HVDC record"
          subtitle="The per-interval RTDHS schedule, independent of the demand construction; binding share is the operator's congestion flag."
        >
          <DataGrid
            columns={[
              {
                key: 'c',
                header: 'Corridor',
                render: (k: string) => bc.flows_rtdhs![k].corridor,
              },
              {
                key: 'obs',
                header: 'Observed mean',
                align: 'right',
                mono: true,
                render: (k: string) => `${num(bc.flows_rtdhs![k].observed_mean_mw)} MW`,
              },
              {
                key: 'mod',
                header: 'Modeled mean',
                align: 'right',
                mono: true,
                render: (k: string) => `${num(bc.flows_rtdhs![k].modeled_mean_mw)} MW`,
              },
              {
                key: 'mae',
                header: 'MAE',
                align: 'right',
                mono: true,
                render: (k: string) => `${num(bc.flows_rtdhs![k].mae_mw)} MW`,
              },
              {
                key: 'bind',
                header: 'Observed binding share',
                align: 'right',
                mono: true,
                render: (k: string) => {
                  const v = bc.flows_rtdhs![k].observed_binding_share_pct
                  return v == null ? 'n/a' : pct(v / 100, 0)
                },
              },
              {
                key: 'atcap',
                header: 'Modeled at-cap share',
                align: 'right',
                mono: true,
                render: (k: string) => {
                  const v = bc.flows_rtdhs![k].modeled_at_cap_share_pct
                  return v == null ? 'n/a' : pct(v / 100, 0)
                },
              },
            ]}
            rows={Object.keys(bc.flows_rtdhs)}
            getKey={(k) => k}
          />
          {bc.flows_rtdhs_note ? <p className="note">{bc.flows_rtdhs_note}</p> : null}
        </Panel>
      ) : null}

      {bc.per_grid_mcp ? (
        <Panel
          title="Same replays against the observed clearing price (MCP)"
          subtitle="The ex-ante regional marginal price, the target commensurate with a dispatch dual."
        >
          <DataGrid
            columns={cols.map((c) =>
              c.key === 'g'
                ? c
                : {
                    ...c,
                    render: (g: GridKey) => {
                      const s = bc.per_grid_mcp?.[g]
                      if (!s) return '-'
                      if (c.key === 'obs') return php(s.observed_mean_php_kwh)
                      if (c.key === 'mod') return php(s.modeled_mean_php_kwh)
                      if (c.key === 'mae') return php(s.mae_php_kwh)
                      if (c.key === 'bias') return php(s.bias_php_kwh)
                      if (c.key === 'corr') return num(s.correlation ?? NaN, 2)
                      const v = s.high_hour_hit_rate_pct
                      return v == null ? 'n/a (flat model)' : pct(v / 100, 0)
                    },
                  }
            )}
            rows={GRIDS}
            getKey={(g) => g}
          />
          {bc.mcp_note ? <p className="note">{bc.mcp_note}</p> : null}
        </Panel>
      ) : null}

      <Panel
        title={`One day against the tape, ${cap(grid)}`}
        subtitle={`Replayed with ${engineLabel} (no edits, no storage cycling) against the observed hourly LWAP.`}
      >
        <div className="chrono__controls">
          <label className="chrono__ctl">
            Market day
            <select
              className="ribbon__select"
              value={day.date}
              onChange={(e) => setDate(e.target.value)}
              aria-label="Backcast day"
            >
              {marketDays.map((x) => (
                <option key={x.date} value={x.date}>
                  {x.date}
                </option>
              ))}
            </select>
          </label>
        </div>
        {run != null ? (
          <HourLines
            series={[
              {
                label: 'modeled',
                color: 'var(--series-modeled)',
                pts: run.hours.map((h) => h.price[grid]),
              },
              {
                label: 'observed',
                color: 'var(--series-observed)',
                pts: day.lwap![grid]!,
                dash: '4 3',
              },
            ]}
          />
        ) : (
          <p className="note">
            {offerDay.loading
              ? 'Loading the day’s offer book.'
              : 'No derived offer book for this day. Books cover the market window with a few days’ publication lag; pick an earlier day or switch to the cost model.'}
          </p>
        )}
      </Panel>

      <p className="note">{bc.note}</p>
    </div>
  )
}
