import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import MissionView from '../../src/views/MissionView.vue'
import { useLogsStore } from '../../src/stores/logs'
import { useRobotsStore } from '../../src/stores/robots'
import { useSystemStore } from '../../src/stores/system'
import { postElectromagneticFix } from '../../src/services/backend-api'
import type { Robot } from '../../src/types'
import { makeRobot } from './fixtures'

vi.mock('../../src/services/backend-api', async importOriginal => {
  const actual = await importOriginal<typeof import('../../src/services/backend-api')>()
  return {
    ...actual,
    postElectromagneticFix: vi.fn()
  }
})

const postRelay = vi.mocked(postElectromagneticFix)

const ButtonStub = defineComponent({
  name: 'ElButtonStub',
  inheritAttrs: false,
  props: {
    type: String,
    disabled: Boolean,
    loading: Boolean
  },
  emits: ['click'],
  setup(props, { attrs, emit, slots }) {
    return () => h('button', {
      ...attrs,
      type: 'button',
      disabled: props.disabled,
      'data-button-type': props.type,
      'data-loading': String(props.loading),
      onClick: () => emit('click')
    }, slots.default?.())
  }
})

function connectedRobot(id: string, relayEnabled: boolean | null = null): Robot {
  const robot = makeRobot(id, {
    state: 'connected',
    activeMethod: 'network',
    endpoint: '192.168.1.249:9090',
    dataMode: 'live',
    commandMode: 'virtual'
  })
  robot.robotType = 'usv'
  robot.relayEnabled = relayEnabled
  return robot
}

async function mountActions(robot: Robot) {
  const store = useRobotsStore()
  store.replaceAll([robot])
  const wrapper = shallowMount(MissionView, {
    global: {
      stubs: {
        'el-button': ButtonStub,
        'el-form': true,
        'el-form-item': true,
        'el-progress': true,
        'el-switch': true,
        'el-table': true,
        'el-table-column': true
      }
    }
  })
  const vm = wrapper.vm as unknown as { tab: string }
  vm.tab = 'action'
  await nextTick()
  return wrapper
}

describe('CL-USV simple actions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useSystemStore().setBackendState('connected')
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows both extra actions only for CL-USV and removes its collect task', async () => {
    const clWrapper = await mountActions(connectedRobot('CL-USV', false))

    expect(clWrapper.find('[data-testid=electromagnetic-fix-button]').exists()).toBe(true)
    expect(clWrapper.find('[data-testid=wireless-charge-button]').exists()).toBe(true)
    expect(clWrapper.findAll('.simple-action-button')).toHaveLength(7)
    expect(clWrapper.text()).not.toContain('垃圾收集任务')
    clWrapper.unmount()

    const otherWrapper = await mountActions(connectedRobot('MricoCV-USV'))
    expect(otherWrapper.find('[data-testid=electromagnetic-fix-button]').exists()).toBe(false)
    expect(otherWrapper.find('[data-testid=wireless-charge-button]').exists()).toBe(false)
    expect(otherWrapper.findAll('.simple-action-button')).toHaveLength(5)
    expect(otherWrapper.text()).toContain('垃圾收集任务')
  })

  it('uses telemetry state for the relay label, availability and red color', async () => {
    const robot = connectedRobot('CL-USV', null)
    const wrapper = await mountActions(robot)
    const unknownButton = wrapper.find('[data-testid=electromagnetic-fix-button]')

    expect(unknownButton.text()).toContain('电磁固定：状态未知')
    expect(unknownButton.attributes('disabled')).toBeDefined()

    useRobotsStore().applyRobot({ ...robot, relayEnabled: false })
    await nextTick()
    const offButton = wrapper.find('[data-testid=electromagnetic-fix-button]')
    expect(offButton.text()).toContain('电磁固定：关')
    expect(offButton.classes()).not.toContain('relay-active')
    expect(offButton.attributes('data-button-type')).toBe('default')

    useRobotsStore().applyRobot({ ...robot, relayEnabled: true })
    await nextTick()
    const onButton = wrapper.find('[data-testid=electromagnetic-fix-button]')
    expect(onButton.text()).toContain('电磁固定：开')
    expect(onButton.classes()).toContain('relay-active')
    expect(onButton.attributes('data-button-type')).toBe('danger')
  })

  it('does not change relay color until the confirmed API snapshot arrives', async () => {
    let resolveRequest: ((robot: Robot) => void) | undefined
    const response = new Promise<Robot>(resolve => { resolveRequest = resolve })
    postRelay.mockReturnValueOnce(response)
    const robot = connectedRobot('CL-USV', false)
    const wrapper = await mountActions(robot)
    const button = wrapper.find('[data-testid=electromagnetic-fix-button]')

    await button.trigger('click')
    expect(postRelay).toHaveBeenCalledWith('CL-USV', true)
    expect(useRobotsStore().selected?.relayEnabled).toBe(false)
    expect(wrapper.find('[data-testid=electromagnetic-fix-button]').classes()).not.toContain('relay-active')

    resolveRequest?.({ ...robot, relayEnabled: true })
    await flushPromises()

    expect(useRobotsStore().selected?.relayEnabled).toBe(true)
    expect(wrapper.find('[data-testid=electromagnetic-fix-button]').classes()).toContain('relay-active')
  })

  it('keeps wireless charging off and reports no load after 500ms', async () => {
    vi.useFakeTimers()
    const errorMessage = vi.spyOn(ElMessage, 'error').mockImplementation(() => undefined)
    const wrapper = await mountActions(connectedRobot('CL-USV', false))
    const button = wrapper.find('[data-testid=wireless-charge-button]')

    await button.trigger('click')
    expect(wrapper.text()).toContain('无线充电：检测中')
    expect(errorMessage).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(500)
    await nextTick()

    expect(errorMessage).toHaveBeenCalledWith('检测无负载，禁止开启')
    expect(wrapper.text()).toContain('无线充电：关')
    expect(useLogsStore().logs[0]?.content).toContain('检测无负载，禁止开启')
  })
})
