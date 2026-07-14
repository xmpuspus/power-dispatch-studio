// Bring-your-own-data CSV import: a wide unit-parameters table (first column an
// object id, remaining columns friendly property headers) that resolves against
// the current object model and merges into a scenario's overrides. Client-side
// only: the caller reads the file with FileReader, nothing here ever touches the
// network. Pure and defensive: bad input turns into warnings, never a throw past
// this module, so a malformed file cannot crash the studio.
//
// Object ids are not always the plain name the CSV carries: a fleet generator's
// override id is `${grid}:${name}` (see baseObjects in model.ts), while the CSV
// only knows the unit name. Matching is done by id OR label, normalized, so a row
// keyed "CALACA U1" resolves to the real object and its real id, not the raw text.

import type { ClassId, ObjRow, Overrides } from './model'
import { overrideKey } from './model'

export interface HeaderMap {
  cls: ClassId
  prop: string
}

// friendly CSV header -> the model's cls:prop it edits. Add a header here and the
// parser, the template download, and the "resolves each header" test all pick it
// up together.
export const IMPORT_HEADERS: Record<string, HeaderMap> = {
  dependable_mw: { cls: 'generator', prop: 'capacity_mw' },
  fuel_price_php_kwh: { cls: 'generator', prop: 'marginal_cost' },
  forced_outage_pct: { cls: 'generator', prop: 'for_pct' },
  region_demand_mw: { cls: 'region', prop: 'demand_mw' },
  flow_limit_mw: { cls: 'interface', prop: 'limit_mw' },
  fuel_price: { cls: 'fuel', prop: 'cost' },
  fuel_avail_luzon_mw: { cls: 'fuel', prop: 'luzon_mw' },
  fuel_avail_visayas_mw: { cls: 'fuel', prop: 'visayas_mw' },
  fuel_avail_mindanao_mw: { cls: 'fuel', prop: 'mindanao_mw' },
}

// classes a row's optional `class` hint may restrict to. Storage is not an
// import target: the pipeline model does not carry a friendly header for it.
const HINTABLE_CLASSES = new Set<ClassId>(['generator', 'fuel', 'interface', 'region'])

export interface ImportResult {
  overrides: Overrides
  importedKeys: string[]
  matched: number
  skipped: string[]
  warnings: string[]
}

function normId(s: string): string {
  return s
    .trim()
    .toLowerCase()
    .replace(/[\s_-]+/g, '_')
}

function findObj(rows: ObjRow[], rawId: string): ObjRow | undefined {
  const key = normId(rawId)
  return rows.find((r) => normId(r.id) === key || normId(r.label) === key)
}

// minimal CSV line splitter, double-quote escaping only ("" inside a quoted
// field is a literal quote). Good enough for a numbers-and-names table without
// pulling in a CSV library for a client-only import.
function splitCsvLine(line: string): string[] {
  const out: string[] = []
  let cur = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const c = line[i]
    if (inQuotes) {
      if (c === '"') {
        if (line[i + 1] === '"') {
          cur += '"'
          i++
        } else {
          inQuotes = false
        }
      } else {
        cur += c
      }
    } else if (c === '"') {
      inQuotes = true
    } else if (c === ',') {
      out.push(cur)
      cur = ''
    } else {
      cur += c
    }
  }
  out.push(cur)
  return out
}

/**
 * Parse a wide unit-parameters CSV and resolve it against the current object
 * model. Never throws: a malformed file comes back as warnings with empty
 * overrides. Numbers only per cell; a non-numeric cell is a warning, not a
 * crash. Rows whose id matches no object in the target class land in
 * `skipped` (deduped by id), not silently dropped.
 */
export function parseImportCsv(
  csvText: string,
  objects: Record<ClassId, ObjRow[]>
): ImportResult {
  const overrides: Overrides = {}
  const importedKeys: string[] = []
  const skipped = new Set<string>()
  const warnings: string[] = []
  let matched = 0

  try {
    const lines = csvText.split(/\r\n|\r|\n/).filter((l) => l.trim().length > 0)
    if (lines.length < 2) {
      warnings.push('The file has no data rows.')
      return { overrides, importedKeys, matched, skipped: [], warnings }
    }

    const header = splitCsvLine(lines[0]).map((h) => h.trim().toLowerCase())
    const classCol = header.indexOf('class')
    const propCols: { idx: number; cls: ClassId; prop: string; header: string }[] = []
    for (let i = 1; i < header.length; i++) {
      if (i === classCol) continue
      const map = IMPORT_HEADERS[header[i]]
      if (!map) {
        warnings.push(`Unrecognized column "${header[i]}", ignored.`)
        continue
      }
      propCols.push({ idx: i, cls: map.cls, prop: map.prop, header: header[i] })
    }
    if (!propCols.length) {
      warnings.push(
        'No recognized property columns found. Download the template to see the supported headers.'
      )
      return { overrides, importedKeys, matched, skipped: [], warnings }
    }

    for (let li = 1; li < lines.length; li++) {
      const cells = splitCsvLine(lines[li])
      const rawId = (cells[0] ?? '').trim()
      if (!rawId) continue
      const hintRaw = classCol >= 0 ? (cells[classCol] ?? '').trim().toLowerCase() : ''
      const hint =
        hintRaw && HINTABLE_CLASSES.has(hintRaw as ClassId) ? (hintRaw as ClassId) : null
      if (hintRaw && !hint)
        warnings.push(`Row "${rawId}": unrecognized class "${hintRaw}", ignored.`)

      for (const col of propCols) {
        if (hint && col.cls !== hint) continue
        const raw = (cells[col.idx] ?? '').trim()
        if (!raw) continue
        const n = Number(raw)
        if (!Number.isFinite(n)) {
          warnings.push(
            `Row "${rawId}", column "${col.header}": "${raw}" is not a number, skipped.`
          )
          continue
        }
        const obj = findObj(objects[col.cls] ?? [], rawId)
        if (!obj) {
          skipped.add(rawId)
          continue
        }
        const key = overrideKey(col.cls, obj.id, col.prop)
        overrides[key] = n
        importedKeys.push(key)
        matched++
      }
    }
  } catch (e) {
    warnings.push(
      `Could not read that file: ${e instanceof Error ? e.message : String(e)}.`
    )
  }

  return {
    overrides,
    importedKeys: [...new Set(importedKeys)],
    matched,
    skipped: [...skipped],
    warnings,
  }
}

/** A small example CSV: the supported headers plus two worked rows, one per
 * class, so an analyst can see the format without reading this file. */
export function buildTemplateCsv(): string {
  const headers = ['id', 'class', ...Object.keys(IMPORT_HEADERS)]
  const blank = (n: number) => Array(n).fill('')
  const rowFor = (id: string, cls: string, values: Record<string, string>) => {
    const cells = blank(headers.length)
    cells[0] = id
    cells[1] = cls
    headers.forEach((h, i) => {
      if (h in values) cells[i] = values[h]
    })
    return cells.join(',')
  }
  const rows = [
    rowFor('CALACA U1', 'generator', {
      dependable_mw: '600',
      fuel_price_php_kwh: '2.15',
      forced_outage_pct: '8',
    }),
    rowFor('luzon', 'region', { region_demand_mw: '13500' }),
  ]
  return [headers.join(','), ...rows].join('\n')
}
