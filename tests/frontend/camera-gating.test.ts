import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { nextTick } from 'vue'
import DeviceConnectionArea from '../../src/components/connection/DeviceConnectionArea.vue'
import ConnectionPanel from '../../src/components/connection/ConnectionPanel.vue'
import CameraGrid from '../../src/components/video/CameraGrid.vue'
import CameraTile from '../../src/components/video/CameraTile.vue'
import { useSystemStore } from '../../src/stores/system'
import { makeRobot } from './fixtures'

function installMediaDevices(getUserMedia: ReturnType<typeof vi.fn>, enumerateDevices = vi.fn().mockResolvedValue([])) {
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: {
      getUserMedia,
      enumerateDevices,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn()
    }
  })
  return enumerateDevices
}

describe('camera connection gating', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('does not mount or enumerate cameras for a disconnected robot', () => {
    const getUserMedia = vi.fn()
    const enumerateDevices = installMediaDevices(getUserMedia)
    useSystemStore().setBackendState('connected')

    const wrapper = shallowMount(DeviceConnectionArea, {
      props: { robot: makeRobot('robot-a') }
    })

    expect(wrapper.findComponent(CameraGrid).exists()).toBe(false)
    expect(wrapper.findComponent(ConnectionPanel).exists()).toBe(true)
    expect(getUserMedia).not.toHaveBeenCalled()
    expect(enumerateDevices).not.toHaveBeenCalled()
  })

  it('unmounts the camera area as soon as the backend link is lost', async () => {
    installMediaDevices(vi.fn())
    const system = useSystemStore()
    system.setBackendState('connected')
    const robot = makeRobot('robot-a', {
      state: 'connected',
      activeMethod: 'network',
      endpoint: '192.0.2.10:9090',
      dataMode: 'virtual'
    })
    const wrapper = shallowMount(DeviceConnectionArea, { props: { robot } })
    expect(wrapper.findComponent(CameraGrid).exists()).toBe(true)

    system.setBackendState('disconnected')
    await nextTick()

    expect(wrapper.findComponent(CameraGrid).exists()).toBe(false)
    expect(wrapper.text()).toContain('后端连接中断')
  })

  it('labels a ready PX4 connection without exposing implementation modes', () => {
    installMediaDevices(vi.fn())
    useSystemStore().setBackendState('connected')
    const robot = makeRobot('robot-a', {
      state: 'connected',
      activeMethod: 'network',
      endpoint: '192.168.1.249:9090',
      dataMode: 'live',
      commandMode: 'virtual'
    })

    const wrapper = shallowMount(DeviceConnectionArea, { props: { robot } })

    expect(wrapper.findComponent(CameraGrid).exists()).toBe(true)
    expect(wrapper.text()).toContain('数据已就绪')
    expect(wrapper.text()).not.toMatch(/虚拟|模拟|演示|未发送飞控/)
  })

  it('returns to the connection panel when the selected device drops offline', async () => {
    installMediaDevices(vi.fn())
    useSystemStore().setBackendState('connected')
    const connected = makeRobot('robot-a', {
      state: 'connected',
      activeMethod: 'serial',
      endpoint: 'COM3',
      dataMode: 'none'
    })
    const wrapper = shallowMount(DeviceConnectionArea, { props: { robot: connected } })
    expect(wrapper.findComponent(CameraGrid).exists()).toBe(true)

    const dropped = makeRobot('robot-a', {
      state: 'error',
      activeMethod: 'serial',
      endpoint: 'COM3',
      error: { code: 'SERIAL_CONNECTION_LOST', message: '串口已拔出' }
    })
    dropped.connectionProfile = { method: 'serial', port: 'COM3', baudRate: 115200 }
    await wrapper.setProps({ robot: dropped })

    expect(wrapper.findComponent(CameraGrid).exists()).toBe(false)
    expect(wrapper.findComponent(ConnectionPanel).exists()).toBe(true)
  })

  it('stops a stream that finishes opening after its tile was unmounted', async () => {
    let resolveStream: ((stream: MediaStream) => void) | undefined
    const pendingStream = new Promise<MediaStream>(resolve => { resolveStream = resolve })
    const getUserMedia = vi.fn().mockReturnValue(pendingStream)
    installMediaDevices(
      getUserMedia,
      vi.fn().mockResolvedValue([
        { kind: 'videoinput', deviceId: 'camera-1', groupId: 'group-1', label: 'Camera 1' }
      ])
    )
    localStorage.setItem('gcs.camera.robot-a.1', 'camera-1')
    vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined)
    const stop = vi.fn()
    const stream = { getTracks: () => [{ stop }] } as unknown as MediaStream

    const wrapper = shallowMount(CameraTile, {
      props: { robotId: 'robot-a', slotIndex: 1, label: '通道 1' }
    })
    await vi.waitFor(() => expect(getUserMedia).toHaveBeenCalledTimes(1))

    wrapper.unmount()
    resolveStream?.(stream)
    await flushPromises()

    expect(stop).toHaveBeenCalledTimes(1)
  })

  it('stops every active track when a connected camera tile is removed', async () => {
    const stopVideo = vi.fn()
    const stopAudio = vi.fn()
    const stream = {
      getTracks: () => [{ stop: stopVideo }, { stop: stopAudio }]
    } as unknown as MediaStream
    const getUserMedia = vi.fn().mockResolvedValue(stream)
    installMediaDevices(
      getUserMedia,
      vi.fn().mockResolvedValue([
        { kind: 'videoinput', deviceId: 'camera-1', groupId: 'group-1', label: 'Camera 1' }
      ])
    )
    localStorage.setItem('gcs.camera.robot-a.1', 'camera-1')
    const play = vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined)
    const wrapper = shallowMount(CameraTile, {
      props: { robotId: 'robot-a', slotIndex: 1, label: '通道 1' }
    })
    await vi.waitFor(() => expect(play).toHaveBeenCalledTimes(1))

    wrapper.unmount()

    expect(stopVideo).toHaveBeenCalledTimes(1)
    expect(stopAudio).toHaveBeenCalledTimes(1)
  })
})
