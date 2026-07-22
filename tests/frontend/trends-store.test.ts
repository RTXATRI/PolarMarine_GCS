import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { ConnectionRuntime, Robot } from '../../src/types'
import { useTrendsStore } from '../../src/stores/trends'
import { makeRobot } from './fixtures'

function connectedRobot(id = 'robot-a'): Robot {
  return makeRobot(id, {
    state: 'connected',
    activeMethod: 'network',
    endpoint: '192.0.2.10:9090',
    dataMode: 'virtual'
  })
}

function withTelemetry(robot: Robot, battery: number, latencyMs: number, speed: number): Robot {
  return { ...robot, battery, latencyMs, speed }
}

function withConnection(robot: Robot, connection: Partial<ConnectionRuntime>): Robot {
  return { ...robot, connection: { ...robot.connection, ...connection } }
}

describe('trends store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('records the first valid snapshot and samples at most once per second', () => {
    const trends = useTrendsStore()
    const robot = connectedRobot()

    trends.recordSnapshot([robot], 10_000)
    trends.recordSnapshot([withTelemetry(robot, 70, 60, 1)], 10_999)

    expect(trends.buffers['robot-a']).toEqual({
      battery: [80],
      latency: [50],
      speed: [0]
    })

    trends.recordSnapshot([withTelemetry(robot, 70, 60, 1)], 11_000)
    expect(trends.buffers['robot-a']).toEqual({
      battery: [80, 70],
      latency: [50, 60],
      speed: [0, 1]
    })
  })

  it('keeps only the latest 60 samples for each metric', () => {
    const trends = useTrendsStore()
    const robot = connectedRobot()

    for (let index = 0; index <= 60; index += 1) {
      trends.recordSnapshot(
        [withTelemetry(robot, index, 100 + index, index / 10)],
        index * 1000
      )
    }

    expect(trends.buffers['robot-a']?.battery).toEqual(Array.from({ length: 60 }, (_, index) => index + 1))
    expect(trends.buffers['robot-a']?.latency).toHaveLength(60)
    expect(trends.buffers['robot-a']?.latency.at(0)).toBe(101)
    expect(trends.buffers['robot-a']?.latency.at(-1)).toBe(160)
    expect(trends.buffers['robot-a']?.speed).toHaveLength(60)
    expect(trends.buffers['robot-a']?.speed.at(0)).toBeCloseTo(0.1)
    expect(trends.buffers['robot-a']?.speed.at(-1)).toBe(6)
  })

  it.each([
    ['disconnected', { state: 'disconnected', dataMode: 'none' }],
    ['error', { state: 'error', dataMode: 'none' }],
    ['no data channel', { state: 'connected', dataMode: 'none' }]
  ] as const)('clears a device when it becomes %s', (_label, connection) => {
    const trends = useTrendsStore()
    const robot = connectedRobot()
    trends.recordSnapshot([robot], 1000)

    trends.recordSnapshot([withConnection(robot, connection)], 2000)

    expect(trends.buffers['robot-a']).toBeUndefined()
  })

  it('accepts live data, clears missing devices, and resets all sampling state', () => {
    const trends = useTrendsStore()
    const virtualRobot = connectedRobot('robot-a')
    const liveRobot = withConnection(withTelemetry(connectedRobot('robot-b'), 55, 25, 2), {
      activeMethod: 'serial',
      endpoint: 'COM3',
      dataMode: 'live'
    })

    trends.recordSnapshot([virtualRobot, liveRobot], 3000)
    expect(trends.buffers['robot-b']).toEqual({ battery: [55], latency: [25], speed: [2] })

    trends.recordSnapshot([liveRobot], 4000)
    expect(trends.buffers['robot-a']).toBeUndefined()

    trends.clearAll()
    expect(trends.buffers).toEqual({})

    // Clearing also removes the second-level de-duplication marker.
    trends.recordSnapshot([liveRobot], 4000)
    expect(trends.buffers['robot-b']).toEqual({ battery: [55], latency: [25], speed: [2] })
  })
})
