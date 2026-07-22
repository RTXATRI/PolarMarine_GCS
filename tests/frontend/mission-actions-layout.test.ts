import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { shallowMount } from '@vue/test-utils'
import { nextTick } from 'vue'
import MissionView from '../../src/views/MissionView.vue'
import { useRobotsStore } from '../../src/stores/robots'
import { useSystemStore } from '../../src/stores/system'
import { makeRobot } from './fixtures'

describe('MissionView simple actions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useSystemStore().setBackendState('connected')
    useRobotsStore().replaceAll([
      makeRobot('robot-a', {
        state: 'connected',
        activeMethod: 'network',
        endpoint: '192.0.2.10:9090',
        dataMode: 'virtual'
      })
    ])
  })

  it('applies the same grid sizing hook to all five action buttons', async () => {
    const wrapper = shallowMount(MissionView, {
      global: {
        stubs: {
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

    const buttons = wrapper.findAll('.simple-action-button')
    expect(buttons).toHaveLength(5)
    for (const button of buttons) {
      expect(button.classes()).toContain('simple-action-button')
    }
  })
})
