import { expect, test, type Page } from '@playwright/test'

async function openScenario(page: Page) {
  await page.goto('./#v=quick-scenario')
  await expect(page.getByTestId('studio')).toBeVisible({ timeout: 30_000 })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.clear())
})

test('keyboard operation reaches and applies a preset', async ({ page }) => {
  await openScenario(page)
  let reached = false
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press('Tab')
    reached = await page.evaluate(
      () => document.activeElement?.getAttribute('data-testid') === 'preset-dict-1500'
    )
    if (reached) break
  }
  expect(reached).toBe(true)
  await page.keyboard.press('Enter')
  await expect(page.getByLabel('Scenario name')).toHaveValue('DICT 1,500 MW reference')
  await expect(
    page.getByRole('region', { name: 'Result status and active assumptions' })
  ).toContainText('Preview, not calculated')
})

test('visible controls have accessible names', async ({ page }) => {
  await openScenario(page)
  const unnamed = await page
    .locator('button, input, select, summary')
    .evaluateAll((elements) =>
      elements
        .filter((element) => {
          const style = getComputedStyle(element)
          return style.display !== 'none' && style.visibility !== 'hidden'
        })
        .filter((element) => {
          const labels =
            element instanceof HTMLInputElement || element instanceof HTMLSelectElement
              ? Array.from(element.labels ?? [])
                  .map((label) => label.textContent?.trim())
                  .join(' ')
              : ''
          const name =
            element.getAttribute('aria-label') ||
            element.getAttribute('title') ||
            labels ||
            element.textContent?.trim()
          return !name
        })
        .map((element) => element.outerHTML.slice(0, 160))
    )
  expect(unnamed).toEqual([])
})

test('200 percent zoom and narrow layouts keep the task controls in the viewport', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await openScenario(page)
  await page.evaluate(() => {
    document.documentElement.style.zoom = '2'
  })
  await expect(page.getByText('Start from an analyst task')).toBeVisible()
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <= document.documentElement.clientWidth + 2
    )
  ).toBe(true)

  await page.evaluate(() => {
    document.documentElement.style.zoom = '1'
  })
  await page.setViewportSize({ width: 375, height: 812 })
  await expect(page.getByTestId('preset-generator-outage')).toBeVisible()
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <= document.documentElement.clientWidth + 2
    )
  ).toBe(true)
  const card = await page.getByTestId('preset-generator-outage').boundingBox()
  expect(card).not.toBeNull()
  expect(card!.x).toBeGreaterThanOrEqual(0)
  expect(card!.x + card!.width).toBeLessThanOrEqual(375)
})

test('saved-result tables expose text labels and downloads without color', async ({
  page,
}) => {
  await page.addInitScript(() => {
    const hour = {
      hour: 19,
      price: { luzon: 6, visayas: 6, mindanao: 6 },
      marginal: { luzon: 'coal', visayas: 'coal', mindanao: 'coal' },
      demand: { luzon: 12000, visayas: 2500, mindanao: 2400 },
      shortfall: { luzon: 0, visayas: 0, mindanao: 0 },
      flowLV: 0,
      flowVM: 0,
      leyte: { sat: false, rent: 0 },
      mvip: { sat: false, rent: 0 },
      fuelGen: { luzon: {}, visayas: {}, mindanao: {} },
      socMwh: 0,
      chargeMw: 0,
      dischargeMw: 0,
    }
    const run = {
      id: 'a11y-run',
      name: 'Accessible saved run',
      savedAt: '2026-08-13T00:00:00Z',
      scenarioName: 'Base Case',
      overrides: {},
      date: '2026-07-22',
      span: 'day',
      engineVersion: 3,
      hours: [hour],
      summaries: [
        {
          date: '2026-07-22',
          meanPrice: hour.price,
          peakPrice: hour.price,
          unservedMwh: hour.shortfall,
          leyteRentMPhp: 0,
          mvipRentMPhp: 0,
        },
      ],
    }
    localStorage.setItem('power-dispatch-studio-runs-v1', JSON.stringify({ runs: [run] }))
  })
  await page.goto('./#v=saved-runs')
  await expect(page.getByTestId('studio')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByRole('columnheader', { name: 'Saved run' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Export case' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'CSV' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Report' })).toBeVisible()
})
