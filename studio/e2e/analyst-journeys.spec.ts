import { expect, test, type Page } from '@playwright/test'

async function openStudio(page: Page, view: string) {
  await page.goto(`./#v=${view}`)
  await expect(page.getByTestId('studio')).toBeVisible({ timeout: 30_000 })
}

async function openView(page: Page, view: string, label: string) {
  await page.evaluate((slug) => {
    window.location.hash = `v=${slug}`
  }, view)
  await expect(page.locator('.bar__searchtxt')).toHaveText(label)
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.clear())
})

test('replay to evidence to share keeps recorded and modeled values distinct', async ({
  page,
}) => {
  await openStudio(page, 'chronology')
  await page.getByLabel('Observed day to replay').selectOption('2026-07-22')

  const context = page.getByRole('region', {
    name: 'Result status and active assumptions',
  })
  await expect(context).toContainText('Recorded data with model replay')
  await expect(context).toContainText('Modeled prices are not recorded prices')
  const modeledMean = page.locator('.stat').filter({
    hasText: 'Modeled mean price, Luzon',
  })
  await expect(modeledMean).toContainText('₱6.00')

  await page.getByText('Evidence and sources', { exact: true }).click()
  await expect(page.getByText('IEMOP', { exact: false }).first()).toBeVisible()

  await page.getByRole('button', { name: 'Copy link' }).click()
  await expect(page.getByRole('status')).toHaveText(
    /Link copied|Share link ready in the address bar/
  )
  await expect(page).toHaveURL(/#m=/)
})

test('preset to run to named save to comparison explains the result', async ({
  page,
}) => {
  await openStudio(page, 'chronology')
  await page.getByLabel('Observed day to replay').selectOption('2026-07-22')
  await page.getByRole('button', { name: 'Save run' }).click()
  await expect(page.getByRole('status')).toHaveText('Run saved')

  await openView(page, 'quick-scenario', 'Scenario builder')
  await page.getByTestId('preset-dict-1500').click()
  await expect(page.getByLabel('Scenario name')).toHaveValue('DICT 1,500 MW reference')

  const context = page.getByRole('region', {
    name: 'Result status and active assumptions',
  })
  await expect(context).toContainText('Preview, not calculated')
  await expect(context).toContainText('+1,500 MW')
  await expect(context).toContainText('Press Run')

  await page.locator('.bar__run').click()
  await expect(page.getByText('Results current', { exact: true }).first()).toBeVisible()
  await expect(context).toContainText('Reference-case result')
  await expect(context).toContainText('not a recorded price or forecast')

  await openView(page, 'chronology', 'Hourly market replay')
  await expect(page.getByText('Cost-model replay', { exact: true }).last()).toBeVisible()
  await page.getByLabel('Run name').fill('DICT 1,500 MW reference, 22 July 2026')
  await page.getByRole('button', { name: 'Save run' }).click()
  await expect(page.getByRole('status')).toHaveText('Run saved')

  await openView(page, 'saved-runs', 'Saved runs')
  await expect(
    page.getByRole('region', { name: 'Result status and active assumptions' })
  ).toContainText('Saved model results')
  await expect(
    page.getByRole('cell', { name: 'Base Case, 2026-07-22', exact: true })
  ).toBeVisible()
  await expect(
    page.getByRole('cell', {
      name: 'DICT 1,500 MW reference, 22 July 2026',
      exact: true,
    })
  ).toBeVisible()
  const summary = page.getByRole('region', { name: 'Comparison summary' })
  await expect(summary).toContainText('Luzon modeled load')
  await expect(summary).toContainText('+1,500 MW')
  await expect(summary).toContainText(
    /Luzon had the largest mean-price change at [+-]₱\d+\.\d{2}\/kWh/
  )
  await expect(summary).toContainText(/Unserved energy changed by [+-][\d,.]+ MWh/)

  const chart = page.locator('svg.chart').last()
  await expect(chart).toContainText('A: Luzon')
  await expect(chart).toContainText('B: Luzon')
  await expect(chart.locator('[stroke-dasharray]')).toHaveCount(1)
})

test('CSV import to calculation to portable case and report preserves provenance', async ({
  page,
}) => {
  await openStudio(page, 'quick-scenario')
  await page.locator('input[type="file"][accept="text/csv,.csv"]').setInputFiles({
    name: 'analyst-input.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('id,class,region_demand_mw\nluzon,region,14500\n'),
  })
  await expect(page.getByText('Imported 1 value.', { exact: false })).toBeVisible()
  await expect(page.getByText('1 user-supplied value active')).toBeVisible()
  await expect(
    page.getByRole('region', { name: 'Result status and active assumptions' })
  ).toContainText('14,500 MW')

  await page.locator('.bar__run').click()
  await expect(page.getByText('Results current', { exact: true }).first()).toBeVisible()
  await openView(page, 'chronology', 'Hourly market replay')
  await page.getByLabel('Run name').fill('Imported Luzon demand case')
  await page.getByRole('button', { name: 'Save run' }).click()
  await expect(page.getByRole('status')).toHaveText('Run saved')

  await openView(page, 'saved-runs', 'Saved runs')
  const caseDownload = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export case' }).click()
  const caseFile = await caseDownload
  expect(caseFile.suggestedFilename()).toBe(
    'power-dispatch-case-imported-luzon-demand-case.json'
  )
  const casePath = await caseFile.path()
  expect(casePath).not.toBeNull()
  const caseData = JSON.parse(
    await (await import('node:fs/promises')).readFile(casePath!, 'utf8')
  )
  expect(caseData.schema).toBe('power-dispatch-case/v1')
  expect(caseData.run.importedKeys).toEqual(['region:luzon:demand_mw'])
  expect(caseData.run.assumptions[0].text).toContain('14,500 MW')
  expect(caseData.run.sourceNotes.join(' ')).toContain('IEMOP')
  expect(caseData.charts.hourlyPrices).toHaveLength(24)

  const reportDownload = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Report' }).click()
  const reportFile = await reportDownload
  const reportPath = await reportFile.path()
  const report = await (await import('node:fs/promises')).readFile(reportPath!, 'utf8')
  expect(report).toContain('Active assumptions')
  expect(report).toContain('User-supplied inputs (1)')
  expect(report).toContain('Calculation method:')
})
