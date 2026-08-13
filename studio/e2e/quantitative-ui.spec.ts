import { expect, test } from '@playwright/test'

test('narrow layouts keep corrected quantitative states readable', async ({ page }) => {
  await page.setViewportSize({ width: 760, height: 900 })

  await page.goto('/#v=chronology&g=luzon')
  const duration = page.getByText('Price changed by less than ₱0.01/kWh')
  await expect(duration).toBeVisible()
  await expect(
    page.getByText(/₱6\.000 to ₱6\.00\d\/kWh across 24 modeled hours/)
  ).toBeVisible()

  await page.goto('/#v=market-power')
  await expect(page.getByText('the bars are not a compliance test')).toBeVisible()
  await expect(page.locator('.mixbars__cap')).toHaveCount(0)
  const firstFirm = page.locator('.mixbars__row').first()
  const firmShare = Number(
    (await firstFirm.locator('.mixbars__val').textContent())?.replace('%', '')
  )
  const trackWidth = await firstFirm
    .locator('.mixbars__track')
    .evaluate((node) => node.clientWidth)
  const fillWidth = await firstFirm
    .locator('.mixbars__fill')
    .evaluate((node) => node.clientWidth)
  expect(fillWidth / trackWidth).toBeCloseTo(firmShare / 100, 2)

  await page.goto('/#v=siting')
  await page.getByRole('button', { name: /STT GDC Fairview campus/ }).click()
  const flatLabel = page.getByText('0 MW throughout the day')
  await expect(flatLabel).toBeVisible()
  const labelBox = await flatLabel.boundingBox()
  const chartBox = await page.locator('.daystrip').boundingBox()
  expect(labelBox).not.toBeNull()
  expect(chartBox).not.toBeNull()
  expect(labelBox!.x).toBeGreaterThanOrEqual(chartBox!.x)
  expect(labelBox!.x + labelBox!.width).toBeLessThanOrEqual(chartBox!.x + chartBox!.width)

  await page.goto('/#v=native-week&g=luzon')
  await expect(
    page.getByText('Choose a battery size to calculate inter-day storage value')
  ).toBeVisible()
  await expect(page.getByLabel('Storage state of charge across the week')).toHaveCount(0)
  await page.getByLabel('Storage').selectOption('small')
  await expect(page.getByText('No storage dispatch')).toBeVisible()
  await expect(
    page.getByText('The selected battery did not charge or discharge during this week')
  ).toBeVisible()
  await expect(page.getByLabel('Storage state of charge across the week')).toHaveCount(0)
})
