import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { shallowMount } from '@vue/test-utils'
import RightStatusPanel from '../../src/components/layout/RightStatusPanel.vue'
import { useRobotsStore } from '../../src/stores/robots'
import { useSystemStore } from '../../src/stores/system'
import { hasCommandChannel, hasUsableDataChannel } from '../../src/utils/connection'
import { makeRobot } from './fixtures'

describe('live MAVROS status presentation', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useSystemStore().setBackendState('connected')
  })

  it('shows MAVROS status without exposing internal operation modes', () => {
    const robot = makeRobot('Hexa-UAV', {
      state: 'connected',
      activeMethod: 'network',
      endpoint: '192.168.1.249:9090',
      dataMode: 'live',
      commandMode: 'virtual'
    })
    Object.assign(robot, {
      battery: 82,
      mode: '手动',
      px4Mode: 'POSCTL',
      missionStatus: '空闲',
      linkStatus: '正常',
      position: { lat: 30.2755, lon: 120.157 },
      altitude: 12.4,
      speed: 0.35,
      heading: 86.2,
      unlocked: false,
      lastCommAt: new Date().toISOString()
    })
    const store = useRobotsStore()
    store.replaceAll([robot])

    const wrapper = shallowMount(RightStatusPanel)

    expect(hasUsableDataChannel(store.selected)).toBe(true)
    expect(hasCommandChannel(store.selected)).toBe(true)
    expect(wrapper.text()).toContain('PX4 模式')
    expect(wrapper.text()).toContain('POSCTL')
    expect(wrapper.text()).toContain('任务状态')
    expect(wrapper.text()).not.toMatch(/虚拟|模拟|演示|未发送飞控|未写入飞控|真实状态未改变/)
  })

  it('does not treat an opened serial port as a command or telemetry channel', () => {
    const robot = makeRobot('Hexa-UAV', {
      state: 'connected',
      activeMethod: 'serial',
      endpoint: 'COM3',
      dataMode: 'none',
      commandMode: 'none'
    })

    expect(hasUsableDataChannel(robot)).toBe(false)
    expect(hasCommandChannel(robot)).toBe(false)
  })
})
