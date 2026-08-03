// Siting what-if: pick an announced load, size it, decide how much power it
// makes itself, and see what its own connection can actually deliver.
//
// The network solve is precomputed (pipeline/sites.py) because it depends only on the
// grid and the day, never on what is typed here. What is typed here is
// arithmetic against those limits, so the whole view is instant.

import { useMemo, useState } from 'react'
import type { Site } from '../lib/types'
import { useSites, useProfiles } from '../lib/data'
import { Panel, StatTile, EmptyNote } from '../ui/kit'

const HOUR_LABEL = (h: number) =>
  h === 0 ? '12am' : h === 12 ? 'noon' : h < 12 ? `${h}am` : `${h - 12}pm`
const fmt = (v: number) => Math.round(v).toLocaleString()

interface Split {
  ownFirm: number
  ownSolar: number
  overLines: number
  missing: number
}

/** Where each megawatt of the hour's demand comes from. */
function split(
  need: number,
  firm: number,
  solarMw: number,
  solarShape: number,
  limit: number | null
): Split {
  const ownSolar = Math.min(solarMw * solarShape, need)
  const ownFirm = Math.min(firm, need - ownSolar)
  const residual = need - ownFirm - ownSolar
  const overLines = limit == null ? 0 : Math.min(residual, limit)
  return { ownFirm, ownSolar, overLines, missing: residual - overLines }
}

/** The day in one strip: what the lines can take each hour, the site's own sun
 * beneath it, and where the chosen hour sits. This replaces three things the
 * view could otherwise only assert, that the limit moves through the day, that
 * solar has a shape, and that the evening is the hour without any. */
function DayStrip({
  limits,
  solar,
  solarMw,
  hour,
  onPick,
}: {
  limits: (number | null)[]
  solar: number[]
  solarMw: number
  hour: number
  onPick: (h: number) => void
}) {
  const W = 560
  const H = 128
  const SUN_TOP = H - 56
  const good = limits.filter((v): v is number => v != null)
  const lo = good.length ? Math.min(...good) : 0
  const hi = good.length ? Math.max(...good) : 1
  // the limit moves by about a tenth across the day, so anchoring at zero
  // flattens the only thing this panel exists to show. A line chart may sit off
  // zero as long as the floor is printed, which it is, at both ends.
  const pad = Math.max((hi - lo) * 0.35, hi * 0.02, 1)
  const top = hi + pad
  const bot = Math.max(0, lo - pad)
  const x = (h: number) => (h / 23) * (W - 54) + 8
  const y = (v: number) => 16 + (1 - (v - bot) / (top - bot)) * (SUN_TOP - 26)
  const path = good.length
    ? limits
        .map(
          (v, h) => `${h === 0 ? 'M' : 'L'}${x(h).toFixed(1)},${y(v ?? bot).toFixed(1)}`
        )
        .join(' ')
    : ''
  const sun = solar
    .map(
      (sv, h) =>
        `${h === 0 ? 'M' : 'L'}${x(h).toFixed(1)},${(H - 26 - sv * 26).toFixed(1)}`
    )
    .join(' ')

  return (
    <svg
      className="daystrip"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="What the site's lines can take in each hour of the day"
    >
      {path ? (
        <>
          <path
            d={`${path} L${x(23)},${SUN_TOP - 10} L${x(0)},${SUN_TOP - 10} Z`}
            className="daystrip__fill"
          />
          <path d={path} className="daystrip__limit" />
          <text x={W - 42} y={y(hi) + 4} className="daystrip__scale">
            {Math.round(hi).toLocaleString()}
          </text>
          <text x={W - 42} y={y(lo) + 4} className="daystrip__scale">
            {Math.round(lo).toLocaleString()}
          </text>
        </>
      ) : (
        <text x={x(0)} y={40} className="daystrip__scale">
          no headroom in any hour
        </text>
      )}

      {/* the sun always shows its shape, because the point is WHEN it stops,
          not how much of it the site happens to have bought yet */}
      <path
        d={`${sun} L${x(23)},${H - 26} L${x(0)},${H - 26} Z`}
        className={`daystrip__sunfill ${solarMw > 0 ? '' : 'is-off'}`}
      />
      <text x={x(0)} y={H - 30} className="daystrip__sunlabel">
        {solarMw > 0
          ? `its own solar, ${Math.round(solarMw).toLocaleString()} MW`
          : 'its own solar (none set)'}
      </text>

      <line x1={x(hour)} x2={x(hour)} y1={10} y2={H - 22} className="daystrip__now" />
      <text
        x={x(hour)}
        y={8}
        className="daystrip__nowlabel"
        textAnchor={hour > 18 ? 'end' : hour < 4 ? 'start' : 'middle'}
      >
        {HOUR_LABEL(hour)}
      </text>
      {[0, 6, 12, 18].map((h) => (
        <text
          key={h}
          x={x(h)}
          y={H - 8}
          className="daystrip__tick"
          textAnchor={h === 0 ? 'start' : 'middle'}
        >
          {HOUR_LABEL(h)}
        </text>
      ))}
      {limits.map((_, h) => (
        <rect
          key={h}
          x={x(h) - 11}
          y={0}
          width={22}
          height={H - 20}
          fill="transparent"
          style={{ cursor: 'pointer' }}
          onClick={() => onPick(h)}
        />
      ))}
    </svg>
  )
}

export function SitesView() {
  const sites = useSites()
  const profiles = useProfiles()
  const [siteId, setSiteId] = useState<string | null>(null)
  const [mw, setMw] = useState<number | null>(null)
  const [firm, setFirm] = useState(0)
  const [solarMw, setSolarMw] = useState(0)
  const [hour, setHour] = useState(19)
  const [outage, setOutage] = useState(false)

  const d = sites.data
  const site: Site | undefined = useMemo(() => {
    if (!d?.sites?.length) return undefined
    return d.sites.find((s) => s.id === siteId) ?? d.sites[0]
  }, [d, siteId])

  const need = mw ?? site?.mw ?? 0
  const solar = profiles.data?.solar_profile ?? []
  const solarShape = solar[hour] ?? 0

  const worstOutage = useMemo(() => {
    if (!site?.outages?.length) return null
    const cut = site.outages.find((o) => o.cuts_site_off)
    if (cut) return { limit: 0, circuit: cut.circuit.join(', ') }
    const withLimit = site.outages.filter((o) => o.limit_mw != null)
    if (!withLimit.length) return null
    const worst = withLimit.reduce((a, b) =>
      (a.limit_mw as number) <= (b.limit_mw as number) ? a : b
    )
    return { limit: worst.limit_mw as number, circuit: worst.circuit.join(', ') }
  }, [site])

  const limit = useMemo(() => {
    if (!site) return null
    if (outage) return worstOutage ? worstOutage.limit : null
    return site.limit_mw_by_hour[hour]
  }, [site, hour, outage, worstOutage])

  const now = useMemo(
    () => split(need, firm, solarMw, solarShape, limit),
    [need, firm, solarMw, solarShape, limit]
  )

  if (sites.loading || profiles.loading)
    return (
      <div className="view">
        <Panel title="Where new demand can connect" subtitle="Loading connection limits.">
          <EmptyNote>Loading.</EmptyNote>
        </Panel>
      </div>
    )

  if (!d?.available || !site)
    return (
      <div className="view">
        <Panel
          title="Site connection limits are not available"
          subtitle="The network and node-price data are unavailable in this data release."
        >
          <EmptyNote>
            This view needs the archive of prices at individual grid connection points.
          </EmptyNote>
        </Panel>
      </div>
    )

  const short = now.missing > 0.5
  const pct = (v: number) => (need > 0 ? (100 * v) / need : 0)
  const bands: [string, number, string][] = [
    ['from the grid, over its lines', now.overLines, 'var(--steel)'],
    ['its own power station', now.ownFirm, 'var(--navy)'],
    ['its own solar farm', now.ownSolar, 'var(--gold)'],
    ['no source for this', now.missing, 'var(--coral)'],
  ]
  const maxMw = Math.max(3000, Math.ceil(site.mw * 1.5))

  return (
    <div className="view view--wide">
      <div className="sites">
        <aside className="sites__side">
          <div className="sites__sidehead">Site</div>
          <ul className="sitelist">
            {d.sites.map((s) => {
              const room = s.limit_max_mw ?? 0
              return (
                <li key={s.id}>
                  <button
                    className={`sitelist__item ${s.id === site.id ? 'is-active' : ''}`}
                    onClick={() => {
                      setSiteId(s.id)
                      setMw(s.mw)
                      setFirm(0)
                      setSolarMw(0)
                      setOutage(false)
                    }}
                  >
                    <span className="sitelist__name">{s.name}</span>
                    <span className="sitelist__nums">
                      <span>{fmt(s.mw)} MW</span>
                      <span className={room < s.mw ? 'is-tight' : ''}>
                        lines {fmt(room)}
                      </span>
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>

          <div className="sites__sidehead">Demand</div>
          <label className="lever lever--primary">
            <span className="lever__label">
              <b>{fmt(need)} MW</b>, every hour
            </span>
            <input
              type="range"
              min={0}
              max={maxMw}
              step={10}
              value={need}
              onChange={(e) => setMw(Number(e.target.value))}
            />
          </label>

          <div className="sites__sidehead">Power it builds on site</div>
          <label className="lever">
            <span className="lever__label">
              Power station, running day and night: <b>{fmt(firm)} MW</b>
            </span>
            <input
              type="range"
              min={0}
              max={maxMw}
              step={10}
              value={firm}
              onChange={(e) => setFirm(Number(e.target.value))}
            />
          </label>
          <label className="lever">
            <span className="lever__label">
              Solar farm: <b>{fmt(solarMw)} MW</b>
            </span>
            <input
              type="range"
              min={0}
              max={2000}
              step={10}
              value={solarMw}
              onChange={(e) => setSolarMw(Number(e.target.value))}
            />
          </label>

          <div className="sites__sidehead">Outage</div>
          <label className="lever lever--check">
            <input
              type="checkbox"
              checked={outage}
              disabled={!worstOutage}
              onChange={(e) => setOutage(e.target.checked)}
            />
            <span>
              Take its worst circuit out of service
              {worstOutage ? <em> ({worstOutage.circuit})</em> : ' (none modelled)'}
            </span>
          </label>
        </aside>

        <div className="sites__main">
          <Panel
            title={
              short
                ? `${fmt(now.missing)} MW has no way to reach ${site.name}`
                : `${site.name} gets every megawatt at ${HOUR_LABEL(hour)}`
            }
            subtitle={`Its lines can take ${
              limit == null ? 'nothing' : `${fmt(limit)} MW`
            } at ${HOUR_LABEL(hour)}${
              outage ? ', with its worst circuit out' : ''
            }. Solved per hour on ${d.day}, everything else is arithmetic.`}
          >
            <div
              className={`site-bar ${short ? 'is-short' : 'is-met'}`}
              role="img"
              aria-label={`Where the ${need} MW comes from`}
            >
              {bands.map(([label, value, color]) =>
                value > 0.5 ? (
                  <div
                    key={label}
                    className="site-bar__seg"
                    style={{ width: `${pct(value)}%`, background: color }}
                    title={`${label}, ${fmt(value)} MW`}
                  >
                    {pct(value) > 11 ? fmt(value) : ''}
                  </div>
                ) : null
              )}
            </div>
            <div className="site-bar__key">
              {bands.map(([label, value, color]) => (
                <span
                  key={label}
                  className={`site-bar__keyitem ${value > 0.5 ? '' : 'is-off'}`}
                >
                  <i style={{ background: color }} /> {label}
                </span>
              ))}
            </div>

            <div className="stat-row">
              <StatTile
                label="short at this hour"
                value={`${fmt(now.missing)} MW`}
                tone={short ? 'danger' : 'positive'}
                hint={short ? 'nothing supplies this' : 'every megawatt has a source'}
              />
              <StatTile
                label="its lines can take"
                value={limit == null ? 'nothing' : `${fmt(limit)} MW`}
                hint={outage ? 'worst circuit out' : `at ${HOUR_LABEL(hour)}`}
              />
              <StatTile
                label="range across the day"
                value={
                  site.limit_min_mw == null
                    ? 'n/a'
                    : `${fmt(site.limit_min_mw)} to ${fmt(site.limit_max_mw ?? 0)}`
                }
                unit="MW"
                hint="what its lines can take, hour by hour"
              />
              <StatTile
                label="distance to the modelled bus"
                value={`${site.snap_km} km`}
                hint={site.precision ?? 'precision not stated'}
              />
            </div>
          </Panel>

          <Panel
            title="The limit moves through the day, because the circuits already carry other load"
            subtitle="Click any hour to move to it. The gold shape is when its own solar produces, which is why the evening is the hard part."
          >
            <DayStrip
              limits={site.limit_mw_by_hour}
              solar={solar}
              solarMw={solarMw}
              hour={hour}
              onPick={setHour}
            />
          </Panel>

          {site.already_over_rating ? (
            <p className="note note--warn">
              A circuit here already carries{' '}
              {Math.round((site.worst_base_loading ?? 0) * 100)}% of its estimated rating
              before new demand is added. The model therefore reports no spare connection
              capacity. NGCP does not publish the actual rating, so this result may
              reflect the rating estimate as much as the site itself.
            </p>
          ) : null}

          {site.radially_fed ? (
            <p className="note note--warn">
              The public map shows one circuit as this site&apos;s only connection to the
              rest of the grid. If that circuit fails, the mapped network has no second
              route. The public map cannot confirm whether the real grid has another
              route.
            </p>
          ) : null}

          <Panel
            title="Every megawatt this site draws passes through these circuits"
            subtitle="Ratings are estimates unless the market record named a limit."
          >
            <table className="grid-table">
              <thead>
                <tr>
                  <th>circuit</th>
                  <th>length</th>
                  <th>rating</th>
                  <th>where the rating came from</th>
                  <th>if it is out</th>
                </tr>
              </thead>
              <tbody>
                {site.circuits.map((c, i) => {
                  const o = site.outages[i]
                  return (
                    <tr key={`${c.names.join()}-${i}`}>
                      <td>{c.names.join(', ')}</td>
                      <td>{c.km} km</td>
                      <td>{fmt(c.rating_mw)} MW</td>
                      <td>{c.rating_src ?? 'estimated'}</td>
                      <td>
                        {!o
                          ? 'not tested'
                          : o.cuts_site_off
                            ? 'the site is cut off'
                            : o.limit_mw == null
                              ? 'no result'
                              : `${fmt(o.limit_mw)} MW left`}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <p className="note">{d.note}</p>
          </Panel>
        </div>
      </div>
    </div>
  )
}
