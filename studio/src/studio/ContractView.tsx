// What a scenario does to a contract position, which is the question a retail
// supplier or a plant owner actually brings.
//
// The dispatch model answers half of it by producing an hourly spot price. The
// other half is a contract book, and the book belongs to the reader, so this
// view holds an editable one and never uploads it. The arithmetic lives in
// contracts.ts, and src/power_dispatch/contracts.py runs the same on the
// command line, so a position marked here re-marks in a notebook.

import { useMemo, useState } from 'react'
import type { ClassId, ObjRow, Overrides } from './model'
import type { Dispatch, GridKey, Profiles } from '../lib/types'
import { chronoOptsFrom } from './model'
import { runChronology } from './chrono'
import { Panel, StatTile, EmptyNote } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'
import { GRIDS, comparePosition, validateBook, type Contract } from './contracts'

const cap = (g: string) => g[0].toUpperCase() + g.slice(1)

/** Pesos, at the size a position actually reaches. */
function peso(v: number): string {
  const a = Math.abs(v)
  const sign = v < 0 ? '-' : ''
  if (a >= 1e6) return `${sign}₱${(a / 1e6).toFixed(2)}M`
  if (a >= 1e3) return `${sign}₱${(a / 1e3).toFixed(0)}k`
  return `${sign}₱${a.toFixed(0)}`
}

const HOURS_ALL = 'all day'
const HOURS_PEAK = '6pm to 9pm'

export function ContractView({
  d,
  profiles,
  objects,
  overrides,
  date,
  scenarioName,
}: {
  d: Dispatch
  profiles: Profiles
  objects: Record<ClassId, ObjRow[]>
  overrides: Overrides
  date: string
  scenarioName: string
}) {
  const [book, setBook] = useState<Contract[]>([])
  const [load, setLoad] = useState<Partial<Record<GridKey, number>>>({})

  const runs = useMemo(() => {
    if (!profiles?.days?.length || !date) return null
    try {
      const base = runChronology(d, profiles, date, {})
      const scen = runChronology(d, profiles, date, chronoOptsFrom(objects, overrides))
      return { base, scen }
    } catch {
      return null
    }
  }, [d, profiles, date, objects, overrides])

  const who = scenarioName === 'Base Case' ? 'Your edits' : scenarioName
  const problems = validateBook(book)
  const hasPosition = book.length > 0 || Object.values(load).some((mw) => (mw ?? 0) > 0)
  const cmp =
    runs && hasPosition && !problems.length
      ? comparePosition(runs.base.hours, runs.scen.hours, book, load)
      : null

  const edit = (i: number, patch: Partial<Contract>) =>
    setBook((b) => b.map((c, j) => (j === i ? { ...c, ...patch } : c)))

  const cols: Column<Contract>[] = [
    {
      key: 'name',
      header: 'Contract',
      render: (c) => (
        <input
          className="propgrid__input ctr__name"
          value={c.name ?? ''}
          aria-label={`Contract ${book.indexOf(c) + 1} name`}
          onChange={(e) => edit(book.indexOf(c), { name: e.target.value })}
        />
      ),
    },
    {
      key: 'grid',
      header: 'Grid',
      render: (c) => (
        <select
          value={c.grid}
          aria-label={`Contract ${book.indexOf(c) + 1} grid`}
          onChange={(e) => edit(book.indexOf(c), { grid: e.target.value as GridKey })}
        >
          {GRIDS.map((g) => (
            <option key={g} value={g}>
              {cap(g)}
            </option>
          ))}
        </select>
      ),
    },
    {
      key: 'side',
      header: 'Side',
      render: (c) => (
        <select
          value={c.side ?? 'buy'}
          aria-label={`Contract ${book.indexOf(c) + 1} side`}
          onChange={(e) =>
            edit(book.indexOf(c), { side: e.target.value as 'buy' | 'sell' })
          }
        >
          <option value="buy">buy</option>
          <option value="sell">sell</option>
        </select>
      ),
    },
    {
      key: 'mw',
      header: 'MW',
      align: 'right',
      mono: true,
      render: (c) => (
        <input
          className="propgrid__input"
          type="number"
          value={c.mw}
          aria-label={`Contract ${book.indexOf(c) + 1} volume MW`}
          onChange={(e) => edit(book.indexOf(c), { mw: Number(e.target.value) })}
        />
      ),
    },
    {
      key: 'strike',
      header: 'Strike',
      align: 'right',
      mono: true,
      render: (c) => (
        <input
          className="propgrid__input"
          type="number"
          step="0.01"
          value={c.strike_php_kwh}
          aria-label={`Contract ${book.indexOf(c) + 1} strike price`}
          onChange={(e) =>
            edit(book.indexOf(c), { strike_php_kwh: Number(e.target.value) })
          }
        />
      ),
    },
    {
      key: 'hours',
      header: 'Hours',
      render: (c) => (
        <select
          value={c.hours ? HOURS_PEAK : HOURS_ALL}
          aria-label={`Contract ${book.indexOf(c) + 1} hours`}
          onChange={(e) =>
            edit(book.indexOf(c), {
              hours: e.target.value === HOURS_PEAK ? [18, 19, 20, 21] : undefined,
            })
          }
        >
          <option>{HOURS_ALL}</option>
          <option>{HOURS_PEAK}</option>
        </select>
      ),
    },
    {
      key: 'chg',
      header: 'Position, change',
      align: 'right',
      mono: true,
      render: (c) => {
        const i = book.indexOf(c)
        if (!cmp) return '-'
        const now = cmp.scenario.contracts[i].position
        const v = now - cmp.base.contracts[i].position
        return v === 0
          ? `${peso(now)}, no change`
          : `${peso(now)}, ${v > 0 ? '+' : ''}${peso(v)}`
      },
    },
  ]

  if (!runs)
    return <EmptyNote>Pick a recorded day to mark a position against it.</EmptyNote>

  return (
    <div className="view">
      <Panel
        title={
          // "Base Case moves this position" reads wrong when the edits sit on
          // the base scenario, which is where a first-time reader makes them
          cmp && cmp.netChange !== 0
            ? `${who} move this position by ${peso(cmp.netChange)} on ${date}`
            : hasPosition
              ? `This position does not move under ${who} on ${date}`
              : 'Enter your contract position'
        }
        subtitle={
          'Your contracts marked against the modeled spot price, base case against ' +
          'the active scenario. The book stays in this browser and is never uploaded.'
        }
      >
        {problems.length > 0 && <p className="note note--warn">{problems.join(' ')}</p>}
        {cmp && (
          <div className="stat-row">
            <StatTile
              label="Contracts gain or lose"
              value={`${cmp.positionChange > 0 ? '+' : ''}${peso(cmp.positionChange)}`}
              hint="What the book is worth against spot, scenario less base"
              tone={cmp.positionChange >= 0 ? 'positive' : 'danger'}
            />
            <StatTile
              label="Uncontracted load costs"
              value={`${cmp.openCostChange > 0 ? '+' : ''}${peso(cmp.openCostChange)}`}
              hint="The load you declared and have not covered, priced at spot"
              tone={cmp.openCostChange > 0 ? 'danger' : 'positive'}
            />
            <StatTile
              label="Net for the day"
              value={`${cmp.netChange > 0 ? '+' : ''}${peso(cmp.netChange)}`}
              hint="The contract gain less the extra cost of the open position"
              tone={cmp.netChange >= 0 ? 'positive' : 'danger'}
            />
            <StatTile
              label="Cover on your Luzon load"
              value={`${(cmp.base.open[0]?.coveredPct ?? 0).toFixed(0)}%`}
              hint={`${cmp.base.open[0]?.loadMw ?? 0} MW declared`}
            />
          </div>
        )}
        <DataGrid
          columns={cols}
          rows={book}
          getKey={(_c, i) => i}
          empty="No contracts entered. Add a contract or enter your own load to start."
        />
        <div className="ctr__actions">
          <button
            className="btn btn--ghost btn--sm"
            onClick={() =>
              setBook((b) => [
                ...b,
                {
                  name: `Contract ${b.length + 1}`,
                  grid: 'luzon',
                  mw: 0,
                  strike_php_kwh: 0,
                  side: 'buy',
                },
              ])
            }
          >
            Add a contract
          </button>
          <button
            className="btn btn--ghost btn--sm"
            onClick={() => setBook((b) => b.slice(0, -1))}
            disabled={book.length === 0}
          >
            Remove the last one
          </button>
          <label className="ctr__load">
            Your own load, Luzon MW
            <input
              className="propgrid__input"
              type="number"
              value={load.luzon ?? 0}
              aria-label="Your own Luzon load MW"
              onChange={(e) => setLoad({ luzon: Number(e.target.value) })}
            />
          </label>
        </div>
        <p className="note">
          Energy marked against modeled spot, and nothing else. No capacity fee, no
          wheeling charge, no tax, and no credit terms. A settlement statement has more
          lines than this. The same arithmetic runs on the command line through
          <code> power-dispatch run --scenario yours.json --position</code>.
        </p>
      </Panel>
    </div>
  )
}
