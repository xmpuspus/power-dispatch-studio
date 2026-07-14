import { describe, expect, it } from 'vitest'
import type { ClassId, ObjRow } from './model'
import { overrideKey } from './model'
import { IMPORT_HEADERS, buildTemplateCsv, parseImportCsv } from './importData'

// Hand-built objects, not baseObjects() output: the point of this fixture is the
// production id shape for a fleet generator, `${grid}:${name}`, which differs
// from the plain unit name the CSV carries. A test that keyed by the raw CSV
// string instead of the matched object's real id would pass here while silently
// no-opping in production.
const OBJECTS: Record<ClassId, ObjRow[]> = {
  generator: [
    {
      id: 'luzon:CALACA U1',
      cls: 'generator',
      label: 'CALACA U1',
      grid: 'luzon',
      props: { capacity_mw: 600, marginal_cost: 2.1, for_pct: 8 },
    },
  ],
  fuel: [
    { id: 'coal', cls: 'fuel', label: 'coal', props: { cost: 2.1, luzon_mw: 5000 } },
  ],
  region: [
    {
      id: 'luzon',
      cls: 'region',
      label: 'Luzon',
      grid: 'luzon',
      props: { demand_mw: 12000 },
    },
  ],
  interface: [
    {
      id: 'leyte_luzon_hvdc',
      cls: 'interface',
      label: 'Leyte-Luzon HVDC',
      props: { limit_mw: 250 },
    },
  ],
  storage: [],
}

describe('parseImportCsv round-trip', () => {
  it('resolves a bare unit name to the real grid-prefixed generator id', () => {
    const csv = [
      'id,class,dependable_mw,fuel_price_php_kwh',
      'CALACA U1,generator,650,2.30',
    ].join('\n')
    const r = parseImportCsv(csv, OBJECTS)
    expect(r.warnings).toEqual([])
    expect(r.matched).toBe(2)
    expect(r.overrides[overrideKey('generator', 'luzon:CALACA U1', 'capacity_mw')]).toBe(
      650
    )
    expect(
      r.overrides[overrideKey('generator', 'luzon:CALACA U1', 'marginal_cost')]
    ).toBe(2.3)
    expect(r.importedKeys).toContain(
      overrideKey('generator', 'luzon:CALACA U1', 'capacity_mw')
    )
    expect(r.importedKeys).toContain(
      overrideKey('generator', 'luzon:CALACA U1', 'marginal_cost')
    )
  })

  it('round-trips a multi-class CSV to the expected overrides and importedKeys', () => {
    const csv = [
      'id,class,dependable_mw,region_demand_mw,fuel_price,flow_limit_mw',
      'CALACA U1,generator,700,,,',
      'luzon,region,,13500,,',
      'coal,fuel,,,2.45,',
      'leyte_luzon_hvdc,interface,,,,300',
    ].join('\n')
    const r = parseImportCsv(csv, OBJECTS)
    expect(r.matched).toBe(4)
    expect(r.skipped).toEqual([])
    expect(r.overrides).toEqual({
      [overrideKey('generator', 'luzon:CALACA U1', 'capacity_mw')]: 700,
      [overrideKey('region', 'luzon', 'demand_mw')]: 13500,
      [overrideKey('fuel', 'coal', 'cost')]: 2.45,
      [overrideKey('interface', 'leyte_luzon_hvdc', 'limit_mw')]: 300,
    })
    expect(r.importedKeys.sort()).toEqual(Object.keys(r.overrides).sort())
  })

  it('the template CSV itself parses clean with no warnings', () => {
    const r = parseImportCsv(buildTemplateCsv(), OBJECTS)
    expect(r.warnings).toEqual([])
    expect(r.matched).toBeGreaterThan(0)
  })
})

describe('unmatched ids', () => {
  it('lands rows with no matching object in skipped, deduped, not silently dropped', () => {
    const csv = [
      'id,class,dependable_mw,fuel_price_php_kwh',
      'GHOST PLANT,generator,500,2.00',
    ].join('\n')
    const r = parseImportCsv(csv, OBJECTS)
    expect(r.skipped).toEqual(['GHOST PLANT'])
    expect(r.matched).toBe(0)
    expect(Object.keys(r.overrides)).toEqual([])
  })

  it('dedupes a repeated unmatched id across columns to one skipped entry', () => {
    const csv = [
      'id,class,dependable_mw,fuel_price_php_kwh,forced_outage_pct',
      'GHOST PLANT,generator,500,2.00,10',
    ].join('\n')
    const r = parseImportCsv(csv, OBJECTS)
    expect(r.skipped).toEqual(['GHOST PLANT'])
  })

  it('still applies the rows that do match alongside an unmatched row', () => {
    const csv = [
      'id,class,dependable_mw',
      'CALACA U1,generator,650',
      'GHOST PLANT,generator,500',
    ].join('\n')
    const r = parseImportCsv(csv, OBJECTS)
    expect(r.matched).toBe(1)
    expect(r.skipped).toEqual(['GHOST PLANT'])
    expect(r.overrides[overrideKey('generator', 'luzon:CALACA U1', 'capacity_mw')]).toBe(
      650
    )
  })
})

describe('non-numeric cells', () => {
  it('turns a non-numeric cell into a warning, never a throw, and skips just that cell', () => {
    const csv = [
      'id,class,dependable_mw,fuel_price_php_kwh',
      'CALACA U1,generator,not-a-number,2.30',
    ].join('\n')
    expect(() => parseImportCsv(csv, OBJECTS)).not.toThrow()
    const r = parseImportCsv(csv, OBJECTS)
    expect(r.warnings.some((w) => w.includes('not-a-number'))).toBe(true)
    expect(
      r.overrides[overrideKey('generator', 'luzon:CALACA U1', 'capacity_mw')]
    ).toBeUndefined()
    expect(
      r.overrides[overrideKey('generator', 'luzon:CALACA U1', 'marginal_cost')]
    ).toBe(2.3)
    expect(r.matched).toBe(1)
  })

  it('never throws on garbage input, empty input, or a header-only file', () => {
    expect(() => parseImportCsv('', OBJECTS)).not.toThrow()
    expect(() => parseImportCsv('not,a,csv,at,all\n\n\n', OBJECTS)).not.toThrow()
    expect(() => parseImportCsv('id,class,dependable_mw', OBJECTS)).not.toThrow()
    const empty = parseImportCsv('', OBJECTS)
    expect(empty.overrides).toEqual({})
    expect(empty.warnings.length).toBeGreaterThan(0)
  })
})

describe('header mapping resolves every supported header to its cls:prop key', () => {
  const idFor: Record<ClassId, string> = {
    generator: 'CALACA U1',
    fuel: 'coal',
    interface: 'leyte_luzon_hvdc',
    region: 'luzon',
    storage: '',
  }
  for (const [header, map] of Object.entries(IMPORT_HEADERS)) {
    it(`"${header}" resolves to ${map.cls}:${map.prop}`, () => {
      const id = idFor[map.cls]
      const csv = [`id,class,${header}`, `${id},${map.cls},42`].join('\n')
      const r = parseImportCsv(csv, OBJECTS)
      const realId = map.cls === 'generator' ? 'luzon:CALACA U1' : id
      expect(r.overrides[overrideKey(map.cls, realId, map.prop)]).toBe(42)
    })
  }
})

describe('class hint disambiguation', () => {
  it('restricts a row to columns matching its declared class', () => {
    // a fuel row that also happens to carry a generator-only column: the hint
    // means the generator column is ignored for this row, not misapplied.
    const csv = ['id,class,fuel_price,dependable_mw', 'coal,fuel,2.60,900'].join('\n')
    const r = parseImportCsv(csv, OBJECTS)
    expect(r.overrides[overrideKey('fuel', 'coal', 'cost')]).toBe(2.6)
    expect(Object.keys(r.overrides)).toHaveLength(1)
  })

  it('flags an unrecognized class hint and still ignores nothing silently', () => {
    const csv = ['id,class,fuel_price', 'coal,not-a-class,2.60'].join('\n')
    const r = parseImportCsv(csv, OBJECTS)
    expect(r.warnings.some((w) => w.includes('not-a-class'))).toBe(true)
    // no valid hint applied: the column still resolves against its own class
    expect(r.overrides[overrideKey('fuel', 'coal', 'cost')]).toBe(2.6)
  })
})
