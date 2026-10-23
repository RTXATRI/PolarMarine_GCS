import { describe, expect, it } from 'vitest'
import { bd09ToWgs84, wgs84ToBd09 } from '@/shared/map/coordinates'

describe('map coordinate boundary', () => {
  it('keeps domain coordinates in WGS-84 across a Baidu adapter round trip', () => {
    const wgs84 = { longitude: 120.157, latitude: 30.2755 }
    const restored = bd09ToWgs84(wgs84ToBd09(wgs84))
    expect(Math.abs(restored.longitude - wgs84.longitude)).toBeLessThan(0.000002)
    expect(Math.abs(restored.latitude - wgs84.latitude)).toBeLessThan(0.000002)
  })

  it('does not offset coordinates outside China', () => {
    const point = { longitude: 0, latitude: 51.5 }
    const restored = bd09ToWgs84(wgs84ToBd09(point))
    expect(restored.longitude).toBeCloseTo(point.longitude, 5)
    expect(restored.latitude).toBeCloseTo(point.latitude, 5)
  })
})
