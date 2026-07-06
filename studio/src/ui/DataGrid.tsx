import type { ReactNode } from 'react'

export interface Column<T> {
  key: string
  header: string
  align?: 'left' | 'right'
  mono?: boolean
  render: (row: T) => ReactNode
}

export function DataGrid<T>({
  columns,
  rows,
  getKey,
  empty = 'No rows.',
}: {
  columns: Column<T>[]
  rows: T[]
  getKey: (row: T, i: number) => string | number
  empty?: string
}) {
  return (
    <div className="grid-wrap">
      <table className="grid">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.align === 'right' ? 'is-num' : ''} scope="col">
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="grid__empty">
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((r, i) => (
              <tr key={getKey(r, i)}>
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className={`${c.align === 'right' ? 'is-num' : ''} ${c.mono ? 'mono' : ''}`}
                  >
                    {c.render(r)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
