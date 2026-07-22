import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import MapCanvas from '../../src/components/map/MapCanvas.vue'
import { useRobotsStore } from '../../src/stores/robots'
import { useSystemStore } from '../../src/stores/system'
import { bd09ToWgs84, distanceM, wgs84ToBd09 } from '../../src/utils/geo'
import { DEFAULT_MAP_CENTER, resolveInitialMapCenter } from '../../src/utils/map-center'
import { makeRobot } from './fixtures'


function connectedRobot(id: string, lat: number, lon: number) {
  const robot = makeRobot(id, {
    state: 'connected',
    activeMethod: 'network',
    endpoint: '192.168.1.20:9090',
    dataMode: 'live',
    commandMode: 'virtual'
  })
  robot.position = { lat, lon }
  return robot
}


describe('map coordinate conversion and initial center', () => {
  it('performs the complete WGS-84 to BD-09 conversion and round trips within two metres', () => {
    const hangzhou = { lat: 30.3168, lon: 120.3505 }
    const converted = wgs84ToBd09(hangzhou.lon, hangzhou.lat)

    expect(converted.lng).toBeCloseTo(120.361466, 5)
    expect(converted.lat).toBeCloseTo(30.320834, 5)

    for (const point of [
      hangzhou,
      { lat: 31.767827, lon: 117.180026 }
    ]) {
      const bd = wgs84ToBd09(point.lon, point.lat)
      const restored = bd09ToWgs84(bd.lng, bd.lat)
      expect(distanceM(point.lat, point.lon, restored.lat, restored.lng)).toBeLessThan(2)
    }
  })

  it('uses Hangdian by default, selected connected position first, then the first positioned device', () => {
    const first = connectedRobot('first', 31.7, 117.1)
    const selected = connectedRobot('selected', 30.3, 120.2)
    const disconnected = makeRobot('disconnected')

    expect(resolveInitialMapCenter([first, selected], 'selected', false)).toEqual(DEFAULT_MAP_CENTER)
    expect(resolveInitialMapCenter([first, selected], 'selected', true)).toEqual(selected.position)
    expect(resolveInitialMapCenter([first, disconnected], 'disconnected', true)).toEqual(first.position)
    expect(resolveInitialMapCenter([disconnected], 'disconnected', true)).toEqual(DEFAULT_MAP_CENTER)
  })
})


interface CenterCall {
  point: FakePoint
  zoom: number
}

class FakePoint {
  constructor(public lng: number, public lat: number) {}
}

class FakeMapInstance {
  centerCalls: CenterCall[] = []
  overlays: unknown[] = []

  centerAndZoom(point: FakePoint, zoom: number) { this.centerCalls.push({ point, zoom }) }
  enableScrollWheelZoom() {}
  enableContinuousZoom() {}
  setMapType() {}
  addControl() {}
  addOverlay(overlay: unknown) { this.overlays.push(overlay) }
  removeOverlay(overlay: unknown) { this.overlays = this.overlays.filter(item => item !== overlay) }
  addEventListener() {}
  removeEventListener() {}
}

class FakeMarker {
  private position: FakePoint
  constructor(point: FakePoint) { this.position = point }
  setLabel() {}
  setPosition(point: FakePoint) { this.position = point }
  getPosition() { return this.position }
  addEventListener() {}
}

class FakeLabel {
  setStyle() {}
  setPosition() {}
}

class FakePolyline {
  setStrokeColor() {}
}


describe('MapCanvas one-time route positioning', () => {
  const maps: FakeMapInstance[] = []

  beforeEach(() => {
    setActivePinia(createPinia())
    maps.length = 0
    vi.stubGlobal('BMapGL', {
      Map: class extends FakeMapInstance {
        constructor() {
          super()
          maps.push(this)
        }
      },
      Point: FakePoint,
      Marker: FakeMarker,
      Label: FakeLabel,
      Polyline: FakePolyline,
      Size: class {},
      ScaleControl: class {},
      ZoomControl: class {},
      BMAP_NORMAL_MAP: 'normal',
      BMAP_SATELLITE_MAP: 'satellite',
      BMAP_EARTH_MAP: 'earth'
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('centers once while mounted and recomputes from the latest selection after remount', async () => {
    const robots = useRobotsStore()
    const system = useSystemStore()
    system.setBackendState('connected')
    const first = connectedRobot('first', 31.767827, 117.180026)
    const second = connectedRobot('second', 30.3168, 120.3505)
    robots.replaceAll([first, second])
    robots.select('first')

    const firstWrapper = mount(MapCanvas, {
      props: {
        goals: [],
        waypoints: [],
        taskZone: null,
        pickingMode: false,
        robotPosition: first.position
      }
    })
    await nextTick()

    expect(maps).toHaveLength(1)
    expect(maps[0].centerCalls).toHaveLength(1)
    expect(maps[0].centerCalls[0].zoom).toBe(18)
    const firstBd = wgs84ToBd09(first.position!.lon, first.position!.lat)
    expect(maps[0].centerCalls[0].point.lng).toBeCloseTo(firstBd.lng, 8)
    expect(maps[0].centerCalls[0].point.lat).toBeCloseTo(firstBd.lat, 8)

    robots.select('second')
    robots.applyRobot({ ...second, position: { lat: 30.4, lon: 120.4 } })
    await nextTick()
    expect(maps[0].centerCalls).toHaveLength(1)

    firstWrapper.unmount()
    const latestSecond = robots.getById('second')!
    const secondWrapper = mount(MapCanvas, {
      props: {
        goals: [],
        waypoints: [],
        taskZone: null,
        pickingMode: false,
        robotPosition: latestSecond.position
      }
    })
    await nextTick()

    expect(maps).toHaveLength(2)
    const latestBd = wgs84ToBd09(latestSecond.position!.lon, latestSecond.position!.lat)
    expect(maps[1].centerCalls).toHaveLength(1)
    expect(maps[1].centerCalls[0].point.lng).toBeCloseTo(latestBd.lng, 8)
    expect(maps[1].centerCalls[0].point.lat).toBeCloseTo(latestBd.lat, 8)

    secondWrapper.unmount()
  })
})
