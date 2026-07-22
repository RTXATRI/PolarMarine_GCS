import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useRobotsStore } from '../../src/stores/robots'
import { useSystemStore } from '../../src/stores/system'
import { useTrendsStore } from '../../src/stores/trends'
import { makeRobot } from './fixtures'

const api = vi.hoisted(() => ({
  fetchRobots: vi.fn(),
  fetchLogs: vi.fn(),
  fetchAlarms: vi.fn()
}))
const message = vi.hoisted(() => ({ error: vi.fn() }))

vi.mock('@/services/backend-api', () => api)
vi.mock('element-plus', () => ({ ElMessage: message }))

class FakeWebSocket {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSING = 2
  static readonly CLOSED = 3
  static instances: FakeWebSocket[] = []

  readonly url: string
  readyState = FakeWebSocket.CONNECTING
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  onclose: (() => void) | null = null

  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
  }

  open() {
    this.readyState = FakeWebSocket.OPEN
    this.onopen?.()
  }

  receive(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) })
  }

  fail() {
    this.onerror?.()
  }

  close() {
    this.readyState = FakeWebSocket.CLOSED
    this.onclose?.()
  }
}

describe('backend data source reconnect', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.useFakeTimers()
    setActivePinia(createPinia())
    FakeWebSocket.instances = []
    Object.defineProperty(globalThis, 'WebSocket', { configurable: true, value: FakeWebSocket })
    api.fetchLogs.mockResolvedValue([])
    api.fetchAlarms.mockResolvedValue([])
    message.error.mockReset()
  })

  afterEach(async () => {
    const source = await import('../../src/services/data-source')
    source.disconnectBackendStream()
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  it('keeps cached HTTP data gated until a snapshot, disables on close, and replaces it after reconnect', async () => {
    const stale = makeRobot('robot-a', {
      state: 'connected',
      activeMethod: 'network',
      endpoint: '192.0.2.10:9090',
      dataMode: 'virtual'
    })
    api.fetchRobots.mockResolvedValue([stale])
    const source = await import('../../src/services/data-source')
    await source.startBackendDataSource()
    const system = useSystemStore()
    const robots = useRobotsStore()
    const trends = useTrendsStore()

    expect(robots.getById('robot-a')?.connection.state).toBe('connected')
    expect(system.backendConnected).toBe(false)
    expect(FakeWebSocket.instances).toHaveLength(1)

    const first = FakeWebSocket.instances[0]
    first.open()
    expect(system.backendConnected).toBe(false)
    first.receive({ type: 'robot_state', data: [stale] })
    expect(system.backendConnected).toBe(true)
    expect(trends.buffers['robot-a']).toEqual({ battery: [80], latency: [50], speed: [0] })

    first.fail()
    first.close()
    expect(system.backendConnected).toBe(false)
    expect(trends.buffers).toEqual({})
    expect(message.error).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(1000)
    expect(FakeWebSocket.instances).toHaveLength(2)
    const recovered = makeRobot('robot-b', {
      state: 'connected',
      activeMethod: 'network',
      endpoint: '198.51.100.20:9090',
      dataMode: 'virtual'
    })
    const second = FakeWebSocket.instances[1]
    second.open()
    second.receive({ type: 'robot_state', data: [recovered] })

    expect(system.backendConnected).toBe(true)
    expect(robots.robots.map(robot => robot.id)).toEqual(['robot-b'])
    expect(robots.selectedId).toBe('robot-b')
    expect(trends.buffers).toEqual({
      'robot-b': { battery: [80], latency: [50], speed: [0] }
    })

    source.disconnectBackendStream()
    expect(trends.buffers).toEqual({})
  })
})
