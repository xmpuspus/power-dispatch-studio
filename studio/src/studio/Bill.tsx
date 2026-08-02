import { useState } from 'react'
import { num, php, pct, useBill } from '../lib/data'
import { Panel, StatTile, Source, EmptyNote } from '../ui/kit'
import { ScrollBox } from '../ui/ScrollBox'

const MIX_LABEL: Record<string, string> = {
  psa: 'Bilateral PSAs',
  ipp_first_gas_prime_coregen: 'First Gas / Prime CoreGen',
  wesm: 'WESM spot',
}

// A WESM price change reaches the bill only through the utility's spot-market share.
export function BillView() {
  const b = useBill()
  const base = b.data?.wesm_price_php_kwh ?? 7.03
  const [wesm, setWesm] = useState<number | null>(null)
  if (b.loading) return <EmptyNote>Loading the bill layer.</EmptyNote>
  if (b.error || !b.data?.available)
    return <EmptyNote>Bill data are not available in this data release.</EmptyNote>
  const d = b.data
  const w = wesm ?? base
  const genBase = d.generation_charge_php_kwh ?? 9.07
  const ptf = d.pass_through_factor ?? 0.1
  const kwh = d.household_kwh_month ?? 200

  const move = w - base // WESM move from the June baseline
  const buffered = ptf * move // what actually reaches the generation charge
  const naive = move // what a full-spot reading would pass through
  const genBuffered = genBase + buffered
  const billBuffered = buffered * kwh // peso/month on the reference household
  const billNaive = naive * kwh
  const saved = billNaive - billBuffered

  const mix = d.supply_mix_pct ?? {}
  const mixMax = Math.max(...Object.values(mix), 1)

  return (
    <div className="view">
      <p className="scn__lede">
        The Wholesale Electricity Spot Market (WESM) prices only the portion of a
        utility's supply that is not covered by bilateral contracts. Contract prices do
        not move with the spot market, so only that uncovered portion passes a WESM price
        spike to the bill. Move the WESM price to compare the likely bill change with a
        household charged the full spot-price change.
      </p>

      <div className="scn">
        <Panel
          title="Only Meralco's WESM share moves with the spot price"
          subtitle={`${d.period}. Share of energy by source. Only the WESM share is exposed to the spot market.`}
        >
          <div className="mixbars">
            {Object.entries(mix).map(([k, v]) => (
              <div className="mixbars__row" key={k}>
                <span className="mixbars__label">{MIX_LABEL[k] ?? k}</span>
                <span className="mixbars__track">
                  <span
                    className={`mixbars__fill${k === 'wesm' ? ' mixbars__fill--spot' : ''}`}
                    style={{ width: `${(v / mixMax) * 100}%` }}
                  />
                </span>
                <span className="mixbars__val mono">{v}%</span>
              </div>
            ))}
          </div>
          <label className="lever" style={{ marginTop: 'var(--sp-3)' }}>
            <span className="lever__label">
              WESM spot price <b className="lever__val mono">{php(w)}</b>
            </span>
            <span className="lever__tick">
              June baseline {php(base)} · move the slider to test another spot price
            </span>
            <input
              type="range"
              className="lever__range"
              min={0}
              max={20}
              step={0.25}
              value={w}
              onChange={(e) => setWesm(Number(e.target.value))}
            />
          </label>
          <p className="note">
            {d.note} <Source href={d.src_mix} label="mix source" />
          </p>
        </Panel>

        {(d.mix_history?.length ?? 0) > 0 && (
          <Panel
            title="Meralco's WESM share rose from 6% in April to 10% in June 2026"
            subtitle="Meralco's own published mix and generation charge, last three advisories."
          >
            <ScrollBox className="propgrid-wrap">
              <table className="propgrid">
                <thead>
                  <tr>
                    <th className="propgrid__obj">Month</th>
                    <th className="propgrid__num">WESM spot market</th>
                    <th className="propgrid__num">Power supply agreements</th>
                    <th className="propgrid__num">Independent producers</th>
                    <th className="propgrid__num">Generation charge</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {d.mix_history!.map((m) => (
                    <tr key={m.period}>
                      <td className="propgrid__obj mono">{m.period}</td>
                      <td className="propgrid__num mono">{m.wesm_pct}%</td>
                      <td className="propgrid__num mono">{m.psa_pct}%</td>
                      <td className="propgrid__num mono">{m.ipp_pct}%</td>
                      <td className="propgrid__num mono">
                        {php(m.generation_charge_php_kwh)}
                      </td>
                      <td>
                        <Source href={m.src_news} label="source" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollBox>
            <p className="note">{d.mix_history_note}</p>
            {d.june_moves && (
              <p className="note">
                June changes by supply source, the one month with a public breakdown:
                power supply agreements +{php(d.june_moves.psa_delta_php_kwh)} (54%
                dollar-denominated, coal and LNG prices), First Gas{' '}
                {php(d.june_moves.ipp_delta_php_kwh)} (better dispatch at Sta. Rita and
                San Lorenzo). <Source href={d.june_moves.src_psa} label="source" />
              </p>
            )}
          </Panel>
        )}

        <div className="scn__results">
          <Panel
            title="Bilateral contracts limit the bill impact of a WESM price change"
            subtitle={`Using Meralco's June 2026 supply mix for a ${num(kwh)} kWh reference household.`}
          >
            <div className="stat-row">
              <StatTile
                label="WESM spot-price change"
                value={`${move >= 0 ? '+' : ''}${php(move)}`}
                hint={`from ${php(base)} baseline`}
                tone={move > 0.001 ? 'accent' : move < -0.001 ? 'positive' : 'default'}
              />
              <StatTile
                label="Generation charge"
                value={php(genBuffered)}
                hint={`base ${php(genBase)}, ${pct(ptf, 0)} passes through`}
              />
              <StatTile
                label="Monthly bill impact"
                value={`${billBuffered >= 0 ? '+' : ''}${php(billBuffered, 0)}`}
                hint="after bilateral contracts"
                tone={
                  billBuffered > 1 ? 'accent' : billBuffered < -1 ? 'positive' : 'default'
                }
              />
            </div>
            <p className="note">
              A full-spot reading would put this at{' '}
              <b>
                {billNaive >= 0 ? '+' : ''}
                {php(billNaive, 0)}/month
              </b>{' '}
              (the full WESM change times {num(kwh)} kWh). Bilateral contracts absorb{' '}
              <b>{php(Math.abs(saved), 0)}</b> of it. The bill is less exposed to a spot
              price spike than the headline WESM number suggests.{' '}
              <Source href={d.src_bill} label="bill source" />
            </p>
          </Panel>

          <Panel
            title="Plant revenue and customer bills use different average prices"
            subtitle="Generation-weighted price (GWAP) is not the same as load-weighted price (LWAP)."
          >
            <p className="note">{d.gwap_lwap_note}</p>
            <p className="note">{d.disclaimer}</p>
          </Panel>
        </div>
      </div>
    </div>
  )
}
