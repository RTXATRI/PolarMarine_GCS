import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { shallowMount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ConnectionPanel from '../../src/components/connection/ConnectionPanel.vue'
import { ApiError } from '../../src/services/http'
import { useRobotsStore } from '../../src/stores/robots'
import { useSystemStore } from '../../src/stores/system'
import { makeRobot } from './fixtures'

const api = vi.hoisted(() => ({
  fetchSerialPorts: vi.fn(),
  fetchNetworkCandidates: vi.fn(),
  connectRobot: vi.fn()
}))

vi.mock('@/services/backend-api', () => api)

interface ConnectionPanelVm {
  method: 'serial' | 'network'
  serialPort: string
  baudRate: number
  networkHost: string
  networkPort: number
  networkCandidates: Array<{ host: string; hostname: string | null; port: number; latencyMs: number | null }>
  localError: string | null
  searchNetwork: () => Promise<void>
  submit: () => Promise<void>
}

describe('connection panel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useSystemStore().setBackendState('connected')
    api.fetchSerialPorts.mockResolvedValue([])
    api.fetchNetworkCandidates.mockResolvedValue([])
    api.connectRobot.mockReset()
  })

  it('prefills the saved profile and resets defaults for an unconfigured device', async () => {
    const configured = makeRobot('configured')
    configured.connectionProfile = { method: 'network', host: '192.168.1.20', port: 19090 }
    const wrapper = shallowMount(ConnectionPanel, { props: { robot: configured } })
    const vm = wrapper.vm as unknown as ConnectionPanelVm

    expect(vm.method).toBe('network')
    expect(vm.networkHost).toBe('192.168.1.20')
    expect(vm.networkPort).toBe(19090)

    await wrapper.setProps({ robot: makeRobot('unconfigured') })

    expect(vm.method).toBe('serial')
    expect(vm.serialPort).toBe('')
    expect(vm.baudRate).toBe(115200)
    expect(vm.networkHost).toBe('')
    expect(vm.networkPort).toBe(9090)
  })

  it('preserves a network draft across same-device snapshots with an unchanged serial profile', async () => {
    const robot = makeRobot('robot-a')
    robot.connectionProfile = { method: 'serial', port: 'COM3', baudRate: 115200 }
    const wrapper = shallowMount(ConnectionPanel, { props: { robot } })
    const vm = wrapper.vm as unknown as ConnectionPanelVm
    const candidate = { host: '192.168.1.20', hostname: 'robot.local', port: 19090, latencyMs: 7 }

    vm.method = 'network'
    vm.networkHost = '192.168.1.88'
    vm.networkPort = 19090
    vm.networkCandidates = [candidate]
    await nextTick()

    for (let index = 0; index < 3; index += 1) {
      const snapshot = makeRobot('robot-a')
      snapshot.connectionProfile = { method: 'serial', port: 'COM3', baudRate: 115200 }
      await wrapper.setProps({ robot: snapshot })
    }

    expect(vm.method).toBe('network')
    expect(vm.networkHost).toBe('192.168.1.88')
    expect(vm.networkPort).toBe(19090)
    expect(vm.networkCandidates).toEqual([candidate])
  })

  it('preserves a network draft across same-device snapshots without a saved profile', async () => {
    const wrapper = shallowMount(ConnectionPanel, { props: { robot: makeRobot('robot-a') } })
    const vm = wrapper.vm as unknown as ConnectionPanelVm
    vm.method = 'network'
    vm.networkHost = '198.51.100.25'
    vm.networkPort = 29090
    await nextTick()

    await wrapper.setProps({ robot: makeRobot('robot-a') })
    await wrapper.setProps({ robot: makeRobot('robot-a') })

    expect(vm.method).toBe('network')
    expect(vm.networkHost).toBe('198.51.100.25')
    expect(vm.networkPort).toBe(29090)
  })

  it('accepts a manually entered network endpoint and applies the successful snapshot', async () => {
    const robot = makeRobot('robot-a')
    const connected = makeRobot('robot-a', {
      state: 'connected',
      activeMethod: 'network',
      endpoint: '203.0.113.9:9090',
      dataMode: 'live',
      commandMode: 'virtual',
      connectedAt: new Date().toISOString()
    })
    api.connectRobot.mockResolvedValue(connected)
    const store = useRobotsStore()
    store.replaceAll([robot])
    const wrapper = shallowMount(ConnectionPanel, { props: { robot } })
    const vm = wrapper.vm as unknown as ConnectionPanelVm
    vm.method = 'network'
    vm.networkHost = '203.0.113.9'
    vm.networkPort = 9090
    await nextTick()

    await vm.submit()

    expect(api.connectRobot).toHaveBeenCalledWith('robot-a', {
      method: 'network',
      host: '203.0.113.9',
      port: 9090
    })
    expect(store.getById('robot-a')?.connection.state).toBe('connected')
    expect(store.sortedRobots[0].id).toBe('robot-a')
  })

  it('loads LAN candidates for the currently configured target port', async () => {
    const robot = makeRobot('robot-a')
    robot.connectionProfile = { method: 'network', host: '192.168.1.99', port: 19090 }
    api.fetchNetworkCandidates.mockResolvedValue([
      { host: '192.168.1.20', hostname: 'rosbridge.local', port: 19090, latencyMs: 8 }
    ])
    const wrapper = shallowMount(ConnectionPanel, { props: { robot } })
    const vm = wrapper.vm as unknown as ConnectionPanelVm

    await vm.searchNetwork()

    expect(api.fetchNetworkCandidates).toHaveBeenCalledWith(19090)
    expect(vm.networkCandidates).toEqual([
      { host: '192.168.1.20', hostname: 'rosbridge.local', port: 19090, latencyMs: 8 }
    ])
  })

  it('keeps a structured serial error retryable and succeeds on the next attempt', async () => {
    const robot = makeRobot('robot-a')
    robot.connectionProfile = { method: 'serial', port: 'COM3', baudRate: 115200 }
    const failed = makeRobot('robot-a', {
      state: 'error',
      activeMethod: 'serial',
      endpoint: 'COM3',
      error: { code: 'SERIAL_PORT_BUSY_OR_DENIED', message: 'COM3 已被占用或无访问权限' }
    })
    failed.connectionProfile = robot.connectionProfile
    const connected = makeRobot('robot-a', {
      state: 'connected',
      activeMethod: 'serial',
      endpoint: 'COM3',
      dataMode: 'none',
      connectedAt: new Date().toISOString()
    })
    connected.connectionProfile = robot.connectionProfile
    api.connectRobot
      .mockRejectedValueOnce(new ApiError(409, {
        code: 'SERIAL_PORT_BUSY_OR_DENIED',
        message: 'COM3 已被占用或无访问权限',
        robot: failed
      }, 'serial failed'))
      .mockResolvedValueOnce(connected)
    const store = useRobotsStore()
    store.replaceAll([robot])
    const wrapper = shallowMount(ConnectionPanel, { props: { robot } })
    const vm = wrapper.vm as unknown as ConnectionPanelVm

    await vm.submit()
    expect(vm.localError).toBe('COM3 已被占用或无访问权限')
    expect(store.getById('robot-a')?.connection.state).toBe('error')
    expect(store.getById('robot-a')?.connectionProfile).toEqual(robot.connectionProfile)

    await vm.submit()
    expect(api.connectRobot).toHaveBeenCalledTimes(2)
    expect(store.getById('robot-a')?.connection.state).toBe('connected')
  })
})
