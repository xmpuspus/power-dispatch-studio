/** Width for a value that is already a percentage of a whole. */
export function percentWidth(value: number): string {
  return `${Math.min(100, Math.max(0, value))}%`
}
