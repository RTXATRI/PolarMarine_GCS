import { expect, test, type Locator, type Page } from '@playwright/test'
import { installVisualFixture } from './visual-fixture'

const pages = [
  { path: '/', name: 'overview' },
  { path: '/map', name: 'map' },
  { path: '/manual', name: 'manual' },
  { path: '/mission', name: 'mission' },
  { path: '/parameters', name: 'parameters' },
  { path: '/logs', name: 'logs' },
  { path: '/devices', name: 'devices' },
  { path: '/ros-debug', name: 'ros-debug' }
] as const

async function waitForStableShell(page: Page): Promise<void> {
  await expect(page.locator('.app-shell')).toBeVisible()
  await expect(page.getByText('六旋翼无人机 01').first()).toBeVisible()
  await expect(page.getByText(/系统正常|部分异常|等待设备连接/).first()).toBeVisible()
  await page.waitForLoadState('networkidle')
  await page.addStyleTag({
    content:
      '*,*::before,*::after{animation-duration:0s!important;transition-duration:0s!important;caret-color:transparent!important}'
  })
  await page.waitForTimeout(50)
}

async function box(locator: Locator) {
  const result = await locator.boundingBox()
  expect(result).not.toBeNull()
  return result!
}

test.describe('restored desktop visual baseline', () => {
  for (const target of pages) {
    test(`${target.name} dark at 1920x1080`, async ({ page }) => {
      await page.setViewportSize({ width: 1920, height: 1080 })
      await installVisualFixture(page, 'dark')
      await page.goto(target.path)
      await waitForStableShell(page)
      await expect(page).toHaveScreenshot(`dark-${target.name}-1920.png`, {
        animations: 'disabled',
        maxDiffPixelRatio: 0.01
      })
    })
  }

  for (const target of [
    { path: '/', name: 'overview' },
    { path: '/parameters', name: 'parameters' }
  ] as const) {
    test(`${target.name} light at 1920x1080`, async ({ page }) => {
      await page.setViewportSize({ width: 1920, height: 1080 })
      await installVisualFixture(page, 'light')
      await page.goto(target.path)
      await waitForStableShell(page)
      await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
      await expect(page).toHaveScreenshot(`light-${target.name}-1920.png`, {
        animations: 'disabled',
        maxDiffPixelRatio: 0.01
      })
    })
  }
})

test.describe('1366x768 desktop geometry', () => {
  for (const target of pages) {
    test(`${target.name} keeps persistent regions separated`, async ({ page }) => {
      await page.setViewportSize({ width: 1366, height: 768 })
      await installVisualFixture(page)
      await page.goto(target.path)
      await waitForStableShell(page)

      const top = await box(page.locator('.app-top'))
      const side = await box(page.locator('.app-side'))
      const main = await box(page.locator('.app-main'))
      const right = await box(page.locator('.app-right'))
      const bottom = await box(page.locator('.app-bottom'))

      expect(top.y).toBe(0)
      expect(top.height).toBe(48)
      expect(side.x + side.width).toBeLessThanOrEqual(main.x)
      expect(main.x + main.width).toBeLessThanOrEqual(right.x)
      expect(top.y + top.height).toBeLessThanOrEqual(main.y)
      expect(main.y + main.height).toBeLessThanOrEqual(bottom.y)
      expect(right.y + right.height).toBeLessThanOrEqual(bottom.y)
      expect(bottom.height).toBe(168)
      await expect(page.getByText('当前选中', { exact: true })).toHaveCount(0)
    })
  }
})
