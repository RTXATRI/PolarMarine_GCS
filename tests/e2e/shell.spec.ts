import { expect, test } from '@playwright/test'
import { installVisualFixture } from './visual-fixture'

test('loads the restored GCS shell from real API-shaped state', async ({ page }) => {
  await installVisualFixture(page)
  await page.goto('/')
  await expect(page.locator('.brand .title')).toContainText('PolarMarine GCS')
  await expect(page.getByRole('menuitem', { name: '设备管理' })).toBeVisible()
  await expect(page.getByText('六旋翼无人机 01').first()).toBeVisible()
  await expect(page.locator('.app-top')).toHaveCSS('height', '48px')
  await expect(page.locator('.app-side')).toHaveCSS('width', '200px')
  await expect(page.locator('.app-right')).toHaveCSS('width', '320px')
  await expect(page.locator('.app-bottom')).toHaveCSS('height', '168px')
  await expect(page.getByText('仿真数据')).toHaveCount(0)
})
